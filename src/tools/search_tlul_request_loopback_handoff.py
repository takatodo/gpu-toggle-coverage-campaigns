#!/usr/bin/env python3
"""
Search for tlul_request_loopback validation settings that satisfy the hybrid handoff gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
VALIDATION_RUNNER = REPO_ROOT / "src" / "runners" / "run_tlul_request_loopback_stock_hybrid_validation.py"
DEFAULT_MDIR = REPO_ROOT / "work" / "vl_ir_exp" / "tlul_request_loopback_vl"
DEFAULT_OUTPUT_DIR = "handoff_search"
DEFAULT_JSON_OUT = "tlul_request_loopback_handoff_search_summary.json"


def _parse_int_list(raw: str) -> list[int]:
    values: list[int] = []
    for chunk in raw.split(","):
        text = chunk.strip()
        if not text:
            continue
        values.append(int(text, 0))
    if not values:
        raise ValueError(f"expected at least one integer in {raw!r}")
    return values


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _case_base(output_dir: Path, req_valid_pct: int, host_post_reset_cycles: int, steps: int) -> Path:
    return output_dir / f"req{req_valid_pct}_post{host_post_reset_cycles}_steps{steps}"


def _build_case_summary(
    *,
    req_valid_pct: int,
    host_post_reset_cycles: int,
    steps: int,
    validation_json: Path,
    proc: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    payload = _read_json(validation_json)
    host_probe = dict(payload.get("host_probe") or {})
    outputs = dict(payload.get("outputs") or {})
    promotion_gate = dict(payload.get("promotion_gate") or {})
    handoff_gate = dict(payload.get("handoff_gate") or {})
    promotion_assessment = dict(payload.get("promotion_assessment") or {})
    return {
        "req_valid_pct": req_valid_pct,
        "host_post_reset_cycles": host_post_reset_cycles,
        "steps": steps,
        "runner_returncode": proc.returncode,
        "validation_json": str(validation_json),
        "host_done_o": int(host_probe.get("done_o", 0)),
        "host_progress_cycle_count_o": int(host_probe.get("progress_cycle_count_o", 0)),
        "final_done_o": int(outputs.get("done_o", 0)),
        "final_progress_cycle_count_o": int(outputs.get("progress_cycle_count_o", 0)),
        "rsp_queue_overflow_o": int(outputs.get("rsp_queue_overflow_o", 0)),
        "promotion_gate_passed": bool(promotion_gate.get("passed", False)),
        "promotion_gate_blocked_by": list(promotion_gate.get("blocked_by") or []),
        "handoff_gate_passed": bool(handoff_gate.get("passed", False)),
        "handoff_gate_blocked_by": list(handoff_gate.get("blocked_by") or []),
        "promotion_assessment_decision": promotion_assessment.get("decision"),
    }


def _search_assessment(cases: list[dict[str, Any]]) -> dict[str, Any]:
    handoff_passes = [case for case in cases if case["handoff_gate_passed"]]
    promotion_only = [
        case for case in cases if case["promotion_gate_passed"] and not case["handoff_gate_passed"]
    ]
    host_incomplete_then_final_done = [
        case for case in cases if case["host_done_o"] == 0 and case["final_done_o"] == 1
    ]
    if handoff_passes:
        return {
            "decision": "handoff_case_found",
            "reason": "at least one searched case satisfied handoff_gate",
        }
    if host_incomplete_then_final_done:
        return {
            "decision": "completion_without_handoff_gate",
            "reason": "some searched cases reached final_done_o=1 from host_done_o=0, but still failed handoff_gate",
        }
    if promotion_only:
        return {
            "decision": "terminal_state_only_candidates_found",
            "reason": "searched cases reached promotion_gate without proving GPU-driven handoff",
        }
    return {
        "decision": "no_handoff_case_found_in_search_space",
        "reason": "searched cases did not produce any host_done_o=0 -> final_done_o=1 handoff candidates",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mdir", type=Path, default=DEFAULT_MDIR)
    parser.add_argument("--req-valid-values", default="80,84,88,92")
    parser.add_argument("--host-post-reset-values", default="96,104,112,116")
    parser.add_argument("--steps-values", default="56,112,256")
    parser.add_argument("--nstates", type=int, default=32)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--host-reset-cycles", type=int, default=4)
    parser.add_argument("--template", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    mdir = args.mdir.resolve()
    req_valid_values = _parse_int_list(args.req_valid_values)
    host_post_reset_values = _parse_int_list(args.host_post_reset_values)
    steps_values = _parse_int_list(args.steps_values)
    output_dir = (args.output_dir or (mdir / DEFAULT_OUTPUT_DIR)).resolve()
    json_out = (args.json_out or (mdir / DEFAULT_JSON_OUT)).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    cases: list[dict[str, Any]] = []
    failed_cases: list[dict[str, Any]] = []

    for req_valid_pct in req_valid_values:
        for host_post_reset_cycles in host_post_reset_values:
            for steps in steps_values:
                base = _case_base(output_dir, req_valid_pct, host_post_reset_cycles, steps)
                validation_json = base.with_suffix(".json")
                flow_json = output_dir / f"{base.name}_flow.json"
                host_report = output_dir / f"{base.name}_host.json"
                host_state = output_dir / f"{base.name}_host.bin"
                final_state = output_dir / f"{base.name}_final.bin"
                cmd = [
                    sys.executable,
                    str(VALIDATION_RUNNER),
                    "--mdir",
                    str(mdir),
                    "--nstates",
                    str(args.nstates),
                    "--steps",
                    str(steps),
                    "--block-size",
                    str(args.block_size),
                    "--host-reset-cycles",
                    str(args.host_reset_cycles),
                    "--host-post-reset-cycles",
                    str(host_post_reset_cycles),
                    "--host-set",
                    f"cfg_req_valid_pct_i={req_valid_pct}",
                    "--json-out",
                    str(validation_json),
                    "--flow-json-out",
                    str(flow_json),
                    "--host-report-out",
                    str(host_report),
                    "--host-state-out",
                    str(host_state),
                    "--final-state-out",
                    str(final_state),
                ]
                if args.template is not None:
                    cmd.extend(["--template", str(args.template.resolve())])
                proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
                if proc.returncode != 0 or not validation_json.is_file():
                    failed_cases.append(
                        {
                            "req_valid_pct": req_valid_pct,
                            "host_post_reset_cycles": host_post_reset_cycles,
                            "steps": steps,
                            "runner_returncode": proc.returncode,
                            "validation_json": str(validation_json),
                            "stdout_tail": "\n".join(proc.stdout.splitlines()[-20:]),
                            "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]),
                        }
                    )
                    continue
                cases.append(
                    _build_case_summary(
                        req_valid_pct=req_valid_pct,
                        host_post_reset_cycles=host_post_reset_cycles,
                        steps=steps,
                        validation_json=validation_json,
                        proc=proc,
                    )
                )

    handoff_passes = [case for case in cases if case["handoff_gate_passed"]]
    promotion_only = [
        case for case in cases if case["promotion_gate_passed"] and not case["handoff_gate_passed"]
    ]
    host_incomplete_then_final_done = [
        case for case in cases if case["host_done_o"] == 0 and case["final_done_o"] == 1
    ]
    payload = {
        "schema_version": 1,
        "target": "tlul_request_loopback",
        "mdir": str(mdir),
        "output_dir": str(output_dir),
        "runner": str(VALIDATION_RUNNER),
        "search_space": {
            "req_valid_values": req_valid_values,
            "host_post_reset_values": host_post_reset_values,
            "steps_values": steps_values,
            "nstates": args.nstates,
            "block_size": args.block_size,
            "host_reset_cycles": args.host_reset_cycles,
            "template": str(args.template.resolve()) if args.template is not None else None,
        },
        "total_cases": len(req_valid_values) * len(host_post_reset_values) * len(steps_values),
        "completed_cases": len(cases),
        "failed_cases": failed_cases,
        "handoff_passes": handoff_passes,
        "promotion_only": promotion_only,
        "host_incomplete_then_final_done": host_incomplete_then_final_done,
        "search_assessment": _search_assessment(cases),
        "cases": cases,
    }
    _write_json(json_out, payload)
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 0 if not failed_cases else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
