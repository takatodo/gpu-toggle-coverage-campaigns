#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from stock_hybrid_validation_common import (
    campaign_threshold_toggle_bits_hit,
    parse_gpu_metrics,
    read_json_if_exists,
    toggle_coverage_summary,
    write_json,
)


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
FLOW_TOOL = ROOT_DIR / "src" / "tools" / "run_tlul_slice_host_gpu_flow.py"
DEFAULT_MDIR = ROOT_DIR / "work" / "vl_ir_exp" / "tlul_sink_vl"
DEFAULT_TEMPLATE = ROOT_DIR / "config" / "slice_launch_templates" / "tlul_sink.json"
DEFAULT_JSON_OUT = ROOT_DIR / "output" / "validation" / "tlul_sink_stock_hybrid_validation.json"
REFERENCE_GATE_NAME = "campaign_reference_surface_v1"
STANDARD_OUTPUT_NAMES = [
    "done_o",
    "cfg_signature_o",
    "host_req_accepted_o",
    "device_req_accepted_o",
    "device_rsp_accepted_o",
    "host_rsp_accepted_o",
    "rsp_queue_overflow_o",
    "progress_cycle_count_o",
    "progress_signature_o",
    "toggle_bitmap_word0_o",
    "toggle_bitmap_word1_o",
    "toggle_bitmap_word2_o",
]


def _template_defaults(path: Path) -> tuple[int, int]:
    if not path.is_file():
        return (32, 56)
    payload = json.loads(path.read_text(encoding="utf-8"))
    args = dict(payload.get("runner_args_template") or {})
    return (int(args.get("gpu_nstates", 32)), int(args.get("gpu_sequential_steps", 56)))


def _read_output_int(mapping: dict[str, Any], name: str) -> int:
    return int(mapping.get(name, 0))


def _selected_outputs(mapping: dict[str, Any]) -> dict[str, int]:
    return {name: _read_output_int(mapping, name) for name in STANDARD_OUTPUT_NAMES}


def _build_validation_payload(
    *,
    args: argparse.Namespace,
    flow_cmd: list[str],
    flow_json: dict[str, Any] | None,
    host_report: dict[str, Any] | None,
    proc: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    metrics = parse_gpu_metrics(proc.stdout)
    flow_timing = dict((flow_json or {}).get("campaign_timing") or {})
    campaign_wall_time_ms = flow_timing.get("wall_time_ms")
    if not isinstance(campaign_wall_time_ms, (int, float)):
        campaign_wall_time_ms = metrics.get("wall_time_ms")
    outputs = _selected_outputs(dict((flow_json or {}).get("outputs") or {}))
    toggle_words = [
        outputs["toggle_bitmap_word0_o"],
        outputs["toggle_bitmap_word1_o"],
        outputs["toggle_bitmap_word2_o"],
    ]
    toggle_summary = toggle_coverage_summary(toggle_words)
    status = "ok" if proc.returncode == 0 and flow_json is not None and host_report is not None else "error"
    host_outputs = _selected_outputs(host_report or {})
    gate_checks = {
        "outputs_match_host_probe": outputs == host_outputs,
        "rsp_queue_overflow_o": outputs["rsp_queue_overflow_o"] == 0,
        "toggle_coverage_any_hit": bool(toggle_summary["any_hit"]),
    }
    reference_gate = {
        "name": REFERENCE_GATE_NAME,
        "target_support_tier": "campaign_reference_surface",
        "description": (
            "A tlul_sink campaign reference surface passes when the generic timed-TB host probe and GPU replay "
            "agree on the checked-in outputs, rsp_queue_overflow_o remains zero, and the replay retains nonzero toggle coverage."
        ),
        "passed": all(gate_checks.values()),
        "blocked_by": [name for name, passed in gate_checks.items() if not passed],
        "criteria": {
            "outputs_match_host_probe": True,
            "rsp_queue_overflow_o": 0,
            "toggle_coverage_any_hit": True,
        },
        "observed": {
            "host_outputs": host_outputs,
            "gpu_outputs": outputs,
            "changed_watch_field_count": int((flow_json or {}).get("changed_watch_field_count") or 0),
            "state_delta_changed_byte_count": int(((flow_json or {}).get("state_delta") or {}).get("changed_byte_count") or 0),
            "toggle_bits_hit": int(toggle_summary["bits_hit"]),
        },
    }
    campaign_threshold = campaign_threshold_toggle_bits_hit(args.campaign_threshold_bits)
    gpu_runs = list((flow_json or {}).get("gpu_runs") or [])
    steps_executed = sum(int(run.get("steps", 0)) for run in gpu_runs)
    if steps_executed == 0:
        steps_executed = args.steps
    if isinstance(metrics, dict):
        metrics = dict(metrics)
        if flow_timing:
            metrics["campaign_timing"] = flow_timing
        metrics["campaign_wall_time_ms"] = float(campaign_wall_time_ms) if isinstance(campaign_wall_time_ms, (int, float)) else None
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "target": "tlul_sink",
        "backend": "stock_verilator_hybrid",
        "support_tier": "campaign_reference_surface",
        "clock_ownership": str((flow_json or {}).get("clock_ownership") or (host_report or {}).get("clock_ownership") or "tb_timed_coroutine"),
        "acceptance_gate": REFERENCE_GATE_NAME,
        "inputs": {
            "mdir": str(args.mdir.resolve()),
            "template": str(args.template.resolve()),
            "nstates": args.nstates,
            "steps": args.steps,
            "block_size": args.block_size,
            "host_reset_cycles": args.host_reset_cycles,
            "host_post_reset_cycles": args.host_post_reset_cycles,
            "host_overrides": list(args.host_set),
            "campaign_threshold_bits": args.campaign_threshold_bits,
        },
        "artifacts": {
            "runner_json": str(args.json_out.resolve()),
            "flow_json": str(args.flow_json_out.resolve()),
            "host_report": str(args.host_report_out.resolve()),
            "host_state": str(args.host_state_out.resolve()),
            "final_state": str(args.final_state_out.resolve()),
            "classifier_report": str((args.mdir.resolve() / "vl_classifier_report.json")),
        },
        "commands": {
            "flow": flow_cmd,
        },
        "flow_returncode": proc.returncode,
        "host_probe": host_report,
        "flow_summary": flow_json,
        "reference_gate": reference_gate,
        "outputs": outputs,
        "toggle_coverage": toggle_summary,
        "campaign_threshold": campaign_threshold,
        "campaign_measurement": {
            "bits_hit": int(toggle_summary["bits_hit"]),
            "threshold_satisfied": (
                status == "ok"
                and bool(reference_gate["passed"])
                and int(toggle_summary["bits_hit"]) >= campaign_threshold["value"]
            ),
            "wall_time_ms": float(campaign_wall_time_ms) if isinstance(campaign_wall_time_ms, (int, float)) else None,
            "steps_executed": steps_executed,
        },
        "performance": metrics,
        "caveats": [
            "campaign reference surface accepts stable host-probe-to-gpu output equivalence under tb_timed_coroutine ownership",
            "changed_watch_field_count remains informational; this runner does not require design-visible deltas for campaign comparison",
            "campaign_measurement.wall_time_ms sums the per-run run_vl_hybrid host wall times from the checked-in GPU replay and excludes host-probe diagnostics",
        ],
    }
    if proc.returncode != 0:
        payload["stdout_tail"] = "\n".join(proc.stdout.splitlines()[-40:])
        payload["stderr_tail"] = "\n".join(proc.stderr.splitlines()[-40:])
    return payload


def main(argv: list[str]) -> int:
    default_nstates, default_steps = _template_defaults(DEFAULT_TEMPLATE)
    parser = argparse.ArgumentParser(
        description="Run the stock-Verilator hybrid campaign-reference validation for tlul_sink."
    )
    parser.add_argument("--mdir", type=Path, default=DEFAULT_MDIR)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--nstates", type=int, default=default_nstates)
    parser.add_argument("--steps", type=int, default=default_steps)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--host-reset-cycles", type=int, default=4)
    parser.add_argument("--host-post-reset-cycles", type=int, default=2)
    parser.add_argument("--host-set", action="append", default=[], metavar="FIELD=VALUE")
    parser.add_argument("--campaign-threshold-bits", type=int, default=5)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--flow-json-out", type=Path)
    parser.add_argument("--host-report-out", type=Path)
    parser.add_argument("--host-state-out", type=Path)
    parser.add_argument("--final-state-out", type=Path)
    args = parser.parse_args(argv)

    mdir = args.mdir.resolve()
    args.template = args.template.resolve()
    args.json_out = args.json_out.resolve()
    args.flow_json_out = (args.flow_json_out or (mdir / "tlul_sink_host_gpu_flow_summary.json")).resolve()
    args.host_report_out = (args.host_report_out or (mdir / "tlul_sink_host_probe_report.json")).resolve()
    args.host_state_out = (args.host_state_out or (mdir / "tlul_sink_host_init_state.bin")).resolve()
    args.final_state_out = (args.final_state_out or (mdir / "tlul_sink_gpu_final_state.bin")).resolve()

    flow_cmd = [
        sys.executable,
        str(FLOW_TOOL),
        "--mdir",
        str(mdir),
        "--template",
        str(args.template),
        "--target",
        "tlul_sink",
        "--support-tier",
        "campaign_reference_surface",
        "--nstates",
        str(args.nstates),
        "--steps",
        str(args.steps),
        "--block-size",
        str(args.block_size),
        "--host-reset-cycles",
        str(args.host_reset_cycles),
        "--host-post-reset-cycles",
        str(args.host_post_reset_cycles),
        "--json-out",
        str(args.flow_json_out),
        "--host-report-out",
        str(args.host_report_out),
        "--host-state-out",
        str(args.host_state_out),
        "--final-state-out",
        str(args.final_state_out),
    ]
    for host_set in args.host_set:
        flow_cmd.extend(["--host-set", host_set])

    proc = subprocess.run(flow_cmd, text=True, capture_output=True, check=False)
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)

    flow_json = read_json_if_exists(args.flow_json_out)
    host_report = read_json_if_exists(args.host_report_out)
    payload = _build_validation_payload(
        args=args,
        flow_cmd=flow_cmd,
        flow_json=flow_json,
        host_report=host_report,
        proc=proc,
    )
    write_json(args.json_out, payload)
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
