#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER = SCRIPT_DIR / "run_toggle_coverage_rule_guided_sweep.py"
ASSIGNMENTS_JSON = SCRIPT_DIR / "toggle_coverage_rule_assignments.json"
DEFAULT_JSON_OUT = SCRIPT_DIR / "toggle_coverage_generic_rule_validation.json"
DEFAULT_MD_OUT = SCRIPT_DIR / "toggle_coverage_generic_rule_validation.md"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate generic toggle-coverage rules by running rule-guided sweep/campaign smokes."
    )
    parser.add_argument("--assignments-json", default=str(ASSIGNMENTS_JSON))
    parser.add_argument("--slices", nargs="*", default=[])
    parser.add_argument("--phases", nargs="*", choices=("sweep", "campaign"), default=["sweep", "campaign"])
    parser.add_argument("--sweep-cases", type=int, default=16)
    parser.add_argument("--campaign-cases", type=int, default=32)
    parser.add_argument("--execution-engine", choices=("gpu", "cpu"), default="gpu")
    parser.add_argument("--work-root", default=str(SCRIPT_DIR / "rule_guided_validation"))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    return parser.parse_args(argv)


def _default_slices(rows: list[dict[str, Any]]) -> list[str]:
    chosen: list[str] = []
    seen: set[str] = set()
    for row in rows:
        name = str(row.get("slice_name") or "")
        if not name or name in seen:
            continue
        chosen.append(name)
        seen.add(name)
    return chosen


def _summary_fields(summary: dict[str, Any]) -> dict[str, Any]:
    best_case = dict(summary.get("best_case") or {})
    return {
        "best_case_hit": int(best_case.get("real_subset_points_hit") or 0),
        "dead_region_count": int(best_case.get("dead_region_count") or 0),
        "dead_output_word_count": int(best_case.get("dead_output_word_count") or 0),
        "gpu_cps": float(best_case.get("real_subset_coverage_per_second") or 0.0),
        "selected_case_count": int(summary.get("selected_case_count") or 0),
    }


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    assignments_payload = _load_json(Path(ns.assignments_json).expanduser().resolve())
    rows = list(assignments_payload.get("rows") or [])
    selected_slices = list(ns.slices) if ns.slices else _default_slices(rows)
    assignment_by_slice = {str(row.get("slice_name")): dict(row) for row in rows}

    work_root = Path(ns.work_root).expanduser().resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    result_rows: list[dict[str, Any]] = []
    for slice_name in selected_slices:
        assignment = assignment_by_slice.get(slice_name)
        if not assignment:
            raise SystemExit(f"Missing rule assignment for slice {slice_name}")
        for phase in ns.phases:
            phase_cases = int(ns.campaign_cases if phase == "campaign" else ns.sweep_cases)
            work_dir = work_root / slice_name / phase
            work_dir.mkdir(parents=True, exist_ok=True)
            run_json = work_dir / "run.json"
            cmd = [
                "python3",
                str(RUNNER),
                "--slice",
                slice_name,
                "--phase",
                phase,
                "--execution-engine",
                ns.execution_engine,
                "--cases",
                str(phase_cases),
                "--work-dir",
                str(work_dir),
                "--json-out",
                str(run_json),
            ]
            subprocess.run(cmd, cwd=SCRIPT_DIR, check=True)
            summary = _load_json(work_dir / "summary.json")
            result_rows.append(
                {
                    "slice_name": slice_name,
                    "rule_family": str(assignment.get("rule_family") or ""),
                    "phase": phase,
                    "execution_engine": ns.execution_engine,
                    "cases": phase_cases,
                    "summary_json": str((work_dir / "summary.json").resolve()),
                    "run_json": str(run_json.resolve()),
                    **_summary_fields(summary),
                }
            )

    payload = {
        "schema_version": "toggle-coverage-generic-rule-validation-v1",
        "rows": result_rows,
    }
    json_out = Path(ns.json_out).expanduser().resolve()
    md_out = Path(ns.md_out).expanduser().resolve()
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Toggle Coverage Generic Rule Validation",
        "",
        "| Slice | Rule | Phase | Cases | Hit | Dead Regions | Dead Words | GPU CPS |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in result_rows:
        lines.append(
            "| {slice_name} | {rule_family} | {phase} | {cases} | {best_case_hit} | {dead_region_count} | {dead_output_word_count} | {gpu_cps:.4f} |".format(
                **row
            )
        )
    md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json_out)
    print(md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
