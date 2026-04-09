#!/usr/bin/env python3
"""
Rank the first stock-Verilator fallback candidates inside the VeeR family.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_DESIGNS_ROOT = REPO_ROOT / "third_party" / "rtlmeter" / "designs"
DEFAULT_RUNNERS_DIR = REPO_ROOT / "src" / "runners"
DEFAULT_BOOTSTRAP_JSONS = [
    REPO_ROOT / "work" / "veer_el2_gpu_cov_stock_verilator_cc_bootstrap.json",
    REPO_ROOT / "work" / "veer_eh1_gpu_cov_stock_verilator_cc_bootstrap.json",
    REPO_ROOT / "work" / "veer_eh2_gpu_cov_stock_verilator_cc_bootstrap.json",
]
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_veer_fallback_candidates.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_design_name(name: str) -> str:
    normalized = []
    for char in name:
        if char.isalnum():
            normalized.append(char.lower())
        else:
            normalized.append("_")
    return "".join(normalized).strip("_")


def _read_line_count(path: Path) -> int | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def build_candidates(
    *,
    bootstrap_payloads: list[dict[str, Any]],
    designs_root: Path,
    runners_dir: Path,
) -> dict[str, Any]:
    design_rows: list[dict[str, Any]] = []
    for payload in bootstrap_payloads:
        design = str(payload.get("design") or "")
        if not design:
            continue
        stem = _normalize_design_name(design)
        tb_path = designs_root / design / "src" / f"{stem}_gpu_cov_tb.sv"
        runner_path = runners_dir / f"run_{stem}_stock_hybrid_validation.py"
        row = {
            "design": design,
            "bootstrap_status": payload.get("status"),
            "compile_case": payload.get("compile_case"),
            "out_dir": payload.get("out_dir"),
            "classes_mk": payload.get("classes_mk"),
            "returncode": payload.get("returncode"),
            "verilog_source_count": payload.get("verilog_source_count"),
            "verilog_include_count": payload.get("verilog_include_count"),
            "top_module": payload.get("top_module"),
            "gpu_cov_tb_path": str(tb_path.resolve()),
            "gpu_cov_tb_exists": tb_path.is_file(),
            "gpu_cov_tb_line_count": _read_line_count(tb_path),
            "stock_hybrid_runner_path": str(runner_path.resolve()),
            "stock_hybrid_runner_exists": runner_path.is_file(),
        }
        design_rows.append(row)

    ready_rows = [
        row
        for row in design_rows
        if str(row.get("bootstrap_status")) == "ok" and bool(row.get("gpu_cov_tb_exists"))
    ]
    sorted_ready_rows = sorted(
        ready_rows,
        key=lambda row: (
            row.get("verilog_source_count") is None,
            int(row.get("verilog_source_count") or 0),
            row.get("verilog_include_count") is None,
            int(row.get("verilog_include_count") or 0),
            row.get("gpu_cov_tb_line_count") is None,
            int(row.get("gpu_cov_tb_line_count") or 0),
            str(row.get("design") or ""),
        ),
    )
    recommended_row = sorted_ready_rows[0] if sorted_ready_rows else None
    fallback_row = sorted_ready_rows[1] if len(sorted_ready_rows) > 1 else None

    if recommended_row is None:
        decision = {
            "status": "veer_fallback_bootstrap_blocked",
            "reason": "no_stock_verilator_bootstrap_ready_veer_design_is_available",
            "recommended_next_action": "repair_veer_stock_verilator_bootstrap_first",
        }
    else:
        decision = {
            "status": "recommend_first_veer_single_surface_candidate",
            "reason": (
                "the_recommended_design_is_bootstrap_ready_and_has_the_smallest_known_"
                "stock_verilator_compile_footprint_inside_the_veer_fallback_family"
            ),
            "recommended_first_design": recommended_row.get("design"),
            "fallback_design": fallback_row.get("design") if fallback_row else None,
            "recommended_next_action": "open_the_recommended_veer_design_as_the_first_fallback_surface",
        }

    family_runner = runners_dir / "run_veer_family_gpu_toggle_validation.py"
    return {
        "schema_version": 1,
        "scope": "campaign_veer_fallback_candidates",
        "family": "VeeR",
        "family_runner_path": str(family_runner.resolve()),
        "family_runner_exists": family_runner.is_file(),
        "candidate_rows": design_rows,
        "ready_candidate_count": len(sorted_ready_rows),
        "ready_candidates": [str(row.get("design")) for row in sorted_ready_rows],
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bootstrap-json",
        type=Path,
        action="append",
        dest="bootstrap_jsons",
        help="Bootstrap JSON to include; may be passed multiple times.",
    )
    parser.add_argument("--designs-root", type=Path, default=DEFAULT_DESIGNS_ROOT)
    parser.add_argument("--runners-dir", type=Path, default=DEFAULT_RUNNERS_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    bootstrap_jsons = args.bootstrap_jsons or DEFAULT_BOOTSTRAP_JSONS
    payload = build_candidates(
        bootstrap_payloads=[_read_json(path.resolve()) for path in bootstrap_jsons if path.resolve().is_file()],
        designs_root=args.designs_root.resolve(),
        runners_dir=args.runners_dir.resolve(),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
