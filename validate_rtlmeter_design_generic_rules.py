#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER = SCRIPT_DIR / "run_rtlmeter_design_rule_guided_sweep.py"
ASSIGNMENTS_JSON = SCRIPT_DIR / "rtlmeter_design_toggle_rule_assignments.json"
DEFAULT_JSON_OUT = SCRIPT_DIR / "rtlmeter_design_generic_rule_validation.json"
DEFAULT_MD_OUT = SCRIPT_DIR / "rtlmeter_design_generic_rule_validation.md"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate design-level generic rules by running RTLMeter gpu_cov sweep/campaign smokes."
    )
    parser.add_argument("--assignments-json", default=str(ASSIGNMENTS_JSON))
    parser.add_argument("--designs", nargs="*", default=[])
    parser.add_argument("--phases", nargs="*", choices=("sweep", "campaign"), default=["sweep", "campaign"])
    parser.add_argument("--execution-engine", choices=("gpu", "cpu"), default="gpu")
    parser.add_argument("--work-root", default=str(SCRIPT_DIR / "rtlmeter_rule_guided_validation"))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    assignments_payload = _load_json(Path(ns.assignments_json).expanduser().resolve())
    rows = list(assignments_payload.get("rows") or [])
    selected_designs = list(ns.designs) if ns.designs else [str(row.get("design")) for row in rows]
    assignment_lookup = {
        str(row.get("design") or ""): dict(row)
        for row in rows
    }

    work_root = Path(ns.work_root).expanduser().resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    result_rows: list[dict[str, Any]] = []
    for design in selected_designs:
        assignment = assignment_lookup.get(design)
        if not assignment:
            raise SystemExit(f"Missing design assignment for {design}")
        configuration = str(assignment.get("configuration") or "gpu_cov")
        for phase in ns.phases:
            work_dir = work_root / design / configuration / phase
            work_dir.mkdir(parents=True, exist_ok=True)
            run_json = work_dir / "run.json"
            cmd = [
                "python3",
                str(RUNNER),
                "--design",
                design,
                "--configuration",
                configuration,
                "--phase",
                phase,
                "--execution-engine",
                ns.execution_engine,
                "--work-dir",
                str(work_dir),
                "--json-out",
                str(run_json),
            ]
            status = "passed"
            error = ""
            try:
                subprocess.run(cmd, cwd=SCRIPT_DIR, check=True)
                summary = _load_json(work_dir / "summary.json")
                best_case = dict(summary.get("best_case") or {})
            except subprocess.CalledProcessError as exc:
                status = "failed"
                error = f"command exited with status {exc.returncode}"
                summary = {}
                best_case = {}
            result_rows.append(
                {
                    "design": design,
                    "configuration": configuration,
                    "rule_family": str(assignment.get("rule_family") or ""),
                    "phase": phase,
                    "status": status,
                    "error": error,
                    "execution_engine": ns.execution_engine,
                    "selected_case_count": int(summary.get("selected_case_count") or 0),
                    "best_case_hit": int(best_case.get("best_case_hit") or 0),
                    "dead_region_count": int(best_case.get("dead_region_count") or 0),
                    "dead_output_word_count": int(best_case.get("dead_output_word_count") or 0),
                    "gpu_cps": float(best_case.get("gpu_cps") or 0.0),
                    "summary_json": str((work_dir / "summary.json").resolve()),
                    "run_json": str(run_json.resolve()),
                }
            )

    payload = {
        "schema_version": "rtlmeter-design-generic-rule-validation-v1",
        "rows": result_rows,
    }
    json_out = Path(ns.json_out).expanduser().resolve()
    md_out = Path(ns.md_out).expanduser().resolve()
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# RTLMeter Design Generic Rule Validation",
        "",
        "| Design | Config | Rule | Phase | Status | Cases | Hit | Dead Regions | Dead Words | GPU CPS |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in result_rows:
        lines.append(
            "| {design} | {configuration} | {rule_family} | {phase} | {status} | {selected_case_count} | {best_case_hit} | {dead_region_count} | {dead_output_word_count} | {gpu_cps:.4f} |".format(
                **row
            )
        )
    md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json_out)
    print(md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
