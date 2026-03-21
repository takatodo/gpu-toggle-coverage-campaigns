#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SWEEP_RUNNER = SCRIPT_DIR / "run_opentitan_tlul_slice_trace_gpu_sweep.py"
INDEX_JSON = SCRIPT_DIR / "slice_launch_templates" / "index.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a same-budget policy-off / policy-on GRPO comparison for one slice."
    )
    parser.add_argument("--slice", required=True)
    parser.add_argument("--policy-json", required=True)
    parser.add_argument("--target-region", default="")
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--cases", type=int, default=32)
    parser.add_argument("--proposal-k", type=int, default=4)
    parser.add_argument(
        "--selection-mode",
        choices=("exact", "blend", "slice"),
        default="blend",
    )
    parser.add_argument("--json-out", default="")
    return parser.parse_args(argv)


def _template_path_for_slice(slice_name: str) -> Path:
    index_payload = _load_json(INDEX_JSON)
    for entry in list(index_payload.get("index") or []):
        if str(entry.get("slice_name")) == str(slice_name):
            return Path(str(entry.get("launch_template_path"))).expanduser().resolve()
    raise SystemExit(f"Unknown slice: {slice_name}")


def _run_case(
    *,
    template_path: Path,
    work_dir: Path,
    cases: int,
    use_policy: bool,
    policy_json: str,
    target_region: str,
    proposal_k: int,
    selection_mode: str,
) -> Path:
    cmd = [
        "python3",
        str(SWEEP_RUNNER),
        "--launch-template",
        str(template_path),
        "--work-dir",
        str(work_dir),
        "--phase",
        "campaign",
        "--execution-engine",
        "gpu",
        "--launch-backend",
        "source",
        "--cases",
        str(int(cases)),
        "--cleanup-non-topk",
    ]
    if use_policy:
        cmd.extend(
            [
                "--grpo-policy-json",
                str(policy_json),
                "--grpo-target-region",
                str(target_region),
                "--grpo-proposal-k",
                str(int(proposal_k)),
                "--grpo-selection-mode",
                str(selection_mode),
            ]
        )
    subprocess.run(cmd, cwd=SCRIPT_DIR, check=True)
    return work_dir / "summary.json"


def _summary_view(summary_payload: dict[str, Any]) -> dict[str, Any]:
    best_case = dict(summary_payload.get("best_case") or {})
    return {
        "best_case_index": best_case.get("case_index"),
        "best_variant_name": best_case.get("variant_name"),
        "best_target_region": best_case.get("target_region"),
        "best_points_hit": int(best_case.get("real_subset_points_hit") or 0),
        "best_points_total": int(best_case.get("real_subset_points_total") or 0),
        "dead_region_count": int(best_case.get("dead_region_count") or 0),
        "dead_output_word_count": int(best_case.get("dead_output_word_count") or 0),
        "coverage_per_second": float(best_case.get("real_subset_coverage_per_second") or 0.0),
        "evaluated_case_count": int(summary_payload.get("evaluated_case_count") or 0),
        "total_candidate_space": int(summary_payload.get("total_candidate_space") or 0),
        "grpo_proposal_count": int(summary_payload.get("grpo_proposal_count") or 0),
    }


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    template_path = _template_path_for_slice(ns.slice)
    work_dir = Path(ns.work_dir).expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    baseline_summary_json = _run_case(
        template_path=template_path,
        work_dir=work_dir / "policy_off",
        cases=int(ns.cases),
        use_policy=False,
        policy_json=str(ns.policy_json),
        target_region=str(ns.target_region),
        proposal_k=int(ns.proposal_k),
        selection_mode=str(ns.selection_mode),
    )
    grpo_summary_json = _run_case(
        template_path=template_path,
        work_dir=work_dir / "policy_on",
        cases=int(ns.cases),
        use_policy=True,
        policy_json=str(ns.policy_json),
        target_region=str(ns.target_region),
        proposal_k=int(ns.proposal_k),
        selection_mode=str(ns.selection_mode),
    )

    baseline_summary = _load_json(baseline_summary_json)
    grpo_summary = _load_json(grpo_summary_json)
    baseline_view = _summary_view(baseline_summary)
    grpo_view = _summary_view(grpo_summary)

    comparison = {
        "schema_version": "grpo-policy-compare-v1",
        "slice_name": str(ns.slice),
        "target_region": str(ns.target_region),
        "cases": int(ns.cases),
        "proposal_k": int(ns.proposal_k),
        "selection_mode": str(ns.selection_mode),
        "policy_json": str(Path(ns.policy_json).expanduser().resolve()),
        "policy_off_summary_json": str(baseline_summary_json),
        "policy_on_summary_json": str(grpo_summary_json),
        "policy_off": baseline_view,
        "policy_on": grpo_view,
        "delta": {
            "points_hit": int(grpo_view["best_points_hit"]) - int(baseline_view["best_points_hit"]),
            "dead_region_count": int(grpo_view["dead_region_count"]) - int(baseline_view["dead_region_count"]),
            "dead_output_word_count": int(grpo_view["dead_output_word_count"]) - int(baseline_view["dead_output_word_count"]),
            "coverage_per_second": float(grpo_view["coverage_per_second"]) - float(baseline_view["coverage_per_second"]),
            "evaluated_case_count": int(grpo_view["evaluated_case_count"]) - int(baseline_view["evaluated_case_count"]),
            "total_candidate_space": int(grpo_view["total_candidate_space"]) - int(baseline_view["total_candidate_space"]),
        },
    }

    json_out = (
        Path(ns.json_out).expanduser().resolve()
        if ns.json_out
        else work_dir / "comparison.json"
    )
    json_out.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
