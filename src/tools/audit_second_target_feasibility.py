#!/usr/bin/env python3
"""
Audit the current second-target candidate set and summarize concrete blockers.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
INDEX_PATH = REPO_ROOT / "config" / "slice_launch_templates" / "index.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "second_target_feasibility_audit.json"
DEFAULT_CANDIDATES = [
    "tlul_fifo_sync",
    "tlul_socket_1n",
    "tlul_err",
    "tlul_sink",
]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_repo_path(raw: str | None) -> Path | None:
    if not raw:
        return None
    return (REPO_ROOT / raw).resolve()


def _load_index(path: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json(path)
    rows = payload.get("index") or []
    return {str(row["slice_name"]): dict(row) for row in rows}


def _guess_host_probe_report_path(mdir: Path, candidate: str) -> Path:
    return mdir / f"{candidate}_host_probe_report.json"


def _guess_watch_summary_path(mdir: Path, candidate: str) -> Path:
    return mdir / f"{candidate}_host_gpu_flow_watch_summary.json"


def _guess_watch_search_path(mdir: Path) -> Path:
    return mdir / "watch_handoff_search" / "summary.json"


def _evaluate_candidate(index_row: dict[str, Any]) -> dict[str, Any]:
    candidate = str(index_row["slice_name"])
    template_path = _resolve_repo_path(index_row.get("launch_template_path"))
    template_exists = bool(template_path and template_path.is_file())
    template_payload = _read_json(template_path) if template_exists else {}
    runner_args = dict(template_payload.get("runner_args_template") or {})
    coverage_tb = _resolve_repo_path(
        runner_args.get("coverage_tb_path")
        or template_payload.get("static_features", {}).get("coverage_tb_path")
    )
    rtl_path = _resolve_repo_path(
        runner_args.get("rtl_path")
        or template_payload.get("static_features", {}).get("rtl_path")
    )
    mdir = (REPO_ROOT / "work" / "vl_ir_exp" / f"{candidate}_vl").resolve()
    cpu_replay_wrapper = (
        REPO_ROOT
        / "third_party"
        / "rtlmeter"
        / "designs"
        / "OpenTitan"
        / "src"
        / f"{candidate}_gpu_cov_cpu_replay_tb.sv"
    ).resolve()

    watch_summary_path = _guess_watch_summary_path(mdir, candidate)
    watch_summary = _read_json(watch_summary_path) if watch_summary_path.is_file() else None
    watch_search_path = _guess_watch_search_path(mdir)
    watch_search = _read_json(watch_search_path) if watch_search_path.is_file() else None

    blocker = "unknown"
    if not template_exists:
        blocker = "missing_template"
    elif coverage_tb is None or not coverage_tb.is_file():
        blocker = "missing_coverage_tb_source"
    elif rtl_path is None or not rtl_path.is_file():
        blocker = "missing_rtl_source"
    elif not (mdir / "vl_batch_gpu.cubin").is_file():
        blocker = "no_build_artifacts"
    elif not _guess_host_probe_report_path(mdir, candidate).is_file():
        blocker = "no_host_probe_artifact"
    elif watch_summary is not None and int(watch_summary.get("changed_watch_field_count", 0)) == 0:
        blocker = "no_gpu_driven_deltas_under_current_model"
    else:
        blocker = "ready_for_next_experiment"

    return {
        "slice_name": candidate,
        "status": index_row.get("status"),
        "can_prepare_launch": bool(index_row.get("can_prepare_launch")),
        "can_run_pilot": bool(index_row.get("can_run_pilot")),
        "template_path": str(template_path) if template_path else None,
        "template_exists": template_exists,
        "coverage_tb_path": str(coverage_tb) if coverage_tb else None,
        "coverage_tb_exists": bool(coverage_tb and coverage_tb.is_file()),
        "rtl_path": str(rtl_path) if rtl_path else None,
        "rtl_exists": bool(rtl_path and rtl_path.is_file()),
        "mdir": str(mdir),
        "build_artifacts": {
            "cubin": (mdir / "vl_batch_gpu.cubin").is_file(),
            "meta": (mdir / "vl_batch_gpu.meta.json").is_file(),
            "classifier_report": (mdir / "vl_classifier_report.json").is_file(),
        },
        "host_probe_report": str(_guess_host_probe_report_path(mdir, candidate)),
        "host_probe_exists": _guess_host_probe_report_path(mdir, candidate).is_file(),
        "watch_summary_path": str(watch_summary_path),
        "watch_summary_exists": watch_summary is not None,
        "watch_changed_field_count": (
            int(watch_summary.get("changed_watch_field_count", 0)) if watch_summary is not None else None
        ),
        "watch_search_path": str(watch_search_path),
        "watch_search_exists": watch_search is not None,
        "watch_search_decision": (
            watch_search.get("search_assessment", {}).get("decision") if watch_search is not None else None
        ),
        "cpu_replay_wrapper_path": str(cpu_replay_wrapper),
        "cpu_replay_wrapper_exists": cpu_replay_wrapper.is_file(),
        "current_blocker": blocker,
    }


def _build_recommendation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_name = {row["slice_name"]: row for row in rows}
    if by_name.get("tlul_fifo_sync", {}).get("cpu_replay_wrapper_exists"):
        thin_top_seed = "tlul_fifo_sync"
    else:
        thin_top_seed = "tlul_socket_1n"
    missing_tier2 = [
        row["slice_name"]
        for row in rows
        if row["slice_name"] in {"tlul_err", "tlul_sink"} and row["current_blocker"] == "missing_coverage_tb_source"
    ]
    return {
        "if_promote_thinner_host_driven_top": {
            "recommended_seed": thin_top_seed,
            "reason": (
                "tlul_fifo_sync already has a checked-in *_gpu_cov_cpu_replay_tb.sv wrapper, "
                "while tlul_socket_1n does not."
                if thin_top_seed == "tlul_fifo_sync"
                else "no existing cpu replay wrapper was found for tlul_fifo_sync"
            ),
        },
        "if_keep_current_tb_timed_model": {
            "recommended_action": (
                "restore_or_generate_tier2_coverage_tb_sources" if missing_tier2 else "defer_second_target"
            ),
            "blocked_candidates": missing_tier2,
        },
        "if_no_new_mechanism_this_milestone": {
            "recommended_action": "defer_second_target_and_keep_socket_m1_as_only_supported_target"
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=INDEX_PATH)
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args(argv)

    index = _load_index(args.index.resolve())
    candidates = list(args.candidate) if args.candidate else list(DEFAULT_CANDIDATES)
    rows = [_evaluate_candidate(index[name]) for name in candidates]
    payload = {
        "schema_version": 1,
        "candidates": rows,
        "recommendation": _build_recommendation(rows),
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.json_out)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
