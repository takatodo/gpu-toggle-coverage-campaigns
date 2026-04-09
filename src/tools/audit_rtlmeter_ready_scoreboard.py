#!/usr/bin/env python3
"""
Audit the OpenTitan ready-for-campaign slice set and emit a tier scoreboard.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
INDEX_PATH = REPO_ROOT / "config" / "slice_launch_templates" / "index.json"
VALIDATION_DIR = REPO_ROOT / "output" / "validation"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "rtlmeter_ready_scoreboard.json"

TIER_SUPPORTED = "Tier S"
TIER_REFERENCE = "Tier R"
TIER_BUILD_PROBE = "Tier B"
TIER_TEMPLATE = "Tier T"
TIER_MISSING = "Tier M"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_repo_path(raw: str | None) -> Path | None:
    if not raw:
        return None
    return (REPO_ROOT / raw).resolve()


def _load_ready_index(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    rows = payload.get("index") or []
    return [dict(row) for row in rows if row.get("status") == "ready_for_campaign"]


def _load_validation_index(validation_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not validation_dir.is_dir():
        return result
    for path in validation_dir.glob("*_stock_hybrid_validation.json"):
        payload = _read_json(path)
        target = payload.get("target")
        if isinstance(target, str) and target:
            result[target] = {
                "path": str(path.resolve()),
                "status": payload.get("status"),
                "support_tier": payload.get("support_tier"),
                "acceptance_gate": payload.get("acceptance_gate"),
            }
    return result


def _candidate_mdirs(slice_name: str) -> list[Path]:
    raw_names = [f"{slice_name}_host", slice_name]
    if slice_name.startswith("tlul_"):
        bare_name = slice_name.removeprefix("tlul_")
        raw_names.append(f"{bare_name}_host")
        raw_names.append(bare_name)
    return [(REPO_ROOT / "work" / "vl_ir_exp" / f"{name}_vl").resolve() for name in raw_names]


def _find_mdir(slice_name: str) -> Path | None:
    for candidate in _candidate_mdirs(slice_name):
        if candidate.is_dir():
            return candidate
    return None


def _host_probe_report_path(mdir: Path | None) -> Path | None:
    if mdir is None:
        return None
    design_key = mdir.name.removesuffix("_vl")
    if design_key.endswith("_host"):
        return mdir / f"{design_key}_probe_report.json"
    return mdir / f"{design_key}_host_probe_report.json"


def _watch_summary_path(mdir: Path | None) -> Path | None:
    if mdir is None:
        return None
    design_key = mdir.name.removesuffix("_vl")
    if design_key.endswith("_host"):
        return mdir / f"{design_key}_gpu_flow_watch_summary.json"
    return mdir / f"{design_key}_host_gpu_flow_watch_summary.json"


def _tier_from_row(
    validation: dict[str, Any] | None,
    coverage_tb_exists: bool,
    host_probe_exists: bool,
    build_cubin_exists: bool,
) -> tuple[str, str]:
    if validation is not None:
        support_tier = str(validation.get("support_tier") or "")
        if "reference" in support_tier:
            return TIER_REFERENCE, "stable_validation_reference"
        return TIER_SUPPORTED, "stable_validation_supported"
    if build_cubin_exists and host_probe_exists:
        return TIER_BUILD_PROBE, "build_and_probe_artifacts_exist"
    if coverage_tb_exists:
        return TIER_TEMPLATE, "coverage_tb_source_exists_but_no_probe"
    return TIER_MISSING, "coverage_tb_source_missing"


def _evaluate_row(
    index_row: dict[str, Any],
    validation_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    slice_name = str(index_row["slice_name"])
    template_path = _resolve_repo_path(index_row.get("launch_template_path"))
    template_payload = _read_json(template_path) if template_path and template_path.is_file() else {}
    runner_args = dict(template_payload.get("runner_args_template") or {})
    static_features = dict(template_payload.get("static_features") or {})

    coverage_tb_path = _resolve_repo_path(
        runner_args.get("coverage_tb_path") or static_features.get("coverage_tb_path")
    )
    rtl_path = _resolve_repo_path(runner_args.get("rtl_path") or static_features.get("rtl_path"))
    validation = validation_index.get(slice_name)
    mdir = _find_mdir(slice_name)
    host_probe_path = _host_probe_report_path(mdir)
    watch_summary = _watch_summary_path(mdir)
    build_cubin = (mdir / "vl_batch_gpu.cubin") if mdir is not None else None
    build_meta = (mdir / "vl_batch_gpu.meta.json") if mdir is not None else None
    classifier_report = (mdir / "vl_classifier_report.json") if mdir is not None else None

    tier, basis = _tier_from_row(
        validation=validation,
        coverage_tb_exists=bool(coverage_tb_path and coverage_tb_path.is_file()),
        host_probe_exists=bool(host_probe_path and host_probe_path.is_file()),
        build_cubin_exists=bool(build_cubin and build_cubin.is_file()),
    )

    return {
        "slice_name": slice_name,
        "status": index_row.get("status"),
        "tier": tier,
        "tier_basis": basis,
        "template_path": str(template_path) if template_path else None,
        "template_exists": bool(template_path and template_path.is_file()),
        "rtl_path": str(rtl_path) if rtl_path else None,
        "rtl_exists": bool(rtl_path and rtl_path.is_file()),
        "coverage_tb_path": str(coverage_tb_path) if coverage_tb_path else None,
        "coverage_tb_exists": bool(coverage_tb_path and coverage_tb_path.is_file()),
        "mdir": str(mdir) if mdir is not None else None,
        "build_artifacts": {
            "cubin": bool(build_cubin and build_cubin.is_file()),
            "meta": bool(build_meta and build_meta.is_file()),
            "classifier_report": bool(classifier_report and classifier_report.is_file()),
        },
        "host_probe_report": str(host_probe_path) if host_probe_path else None,
        "host_probe_exists": bool(host_probe_path and host_probe_path.is_file()),
        "watch_summary_path": str(watch_summary) if watch_summary else None,
        "watch_summary_exists": bool(watch_summary and watch_summary.is_file()),
        "validation": validation,
    }


def _build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tier_counts = Counter(row["tier"] for row in rows)
    return {
        "ready_count": len(rows),
        "tier_counts": {
            TIER_SUPPORTED: tier_counts.get(TIER_SUPPORTED, 0),
            TIER_REFERENCE: tier_counts.get(TIER_REFERENCE, 0),
            TIER_BUILD_PROBE: tier_counts.get(TIER_BUILD_PROBE, 0),
            TIER_TEMPLATE: tier_counts.get(TIER_TEMPLATE, 0),
            TIER_MISSING: tier_counts.get(TIER_MISSING, 0),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=INDEX_PATH)
    parser.add_argument("--validation-dir", type=Path, default=VALIDATION_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args(argv)

    ready_rows = _load_ready_index(args.index.resolve())
    validation_index = _load_validation_index(args.validation_dir.resolve())
    rows = [_evaluate_row(row, validation_index) for row in ready_rows]
    payload = {
        "schema_version": 1,
        "scope": "opentitan_ready_for_campaign",
        "summary": _build_summary(rows),
        "rows": sorted(rows, key=lambda row: row["slice_name"]),
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.json_out)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
