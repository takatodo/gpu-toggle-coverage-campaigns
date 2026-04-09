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
FLOW_TOOL = ROOT_DIR / "src" / "tools" / "run_socket_m1_host_gpu_flow.py"
DEFAULT_MDIR = ROOT_DIR / "work" / "vl_ir_exp" / "socket_m1_vl"
DEFAULT_JSON_OUT = ROOT_DIR / "output" / "validation" / "socket_m1_stock_hybrid_validation.json"


def _build_validation_payload(
    *,
    args: argparse.Namespace,
    flow_cmd: list[str],
    flow_json: dict[str, Any] | None,
    host_report: dict[str, Any] | None,
    proc: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    metrics = parse_gpu_metrics(proc.stdout)
    toggle_words = [
        int(flow_json.get("toggle_bitmap_word0_o", 0)) if flow_json else 0,
        int(flow_json.get("toggle_bitmap_word1_o", 0)) if flow_json else 0,
        int(flow_json.get("toggle_bitmap_word2_o", 0)) if flow_json else 0,
    ]
    status = "ok" if proc.returncode == 0 and flow_json is not None else "error"
    toggle_summary = toggle_coverage_summary(toggle_words)
    campaign_threshold = campaign_threshold_toggle_bits_hit(args.campaign_threshold_bits)
    campaign_measurement = {
        "bits_hit": int(toggle_summary["bits_hit"]),
        "threshold_satisfied": status == "ok" and int(toggle_summary["bits_hit"]) >= campaign_threshold["value"],
        "wall_time_ms": metrics.get("wall_time_ms"),
        "steps_executed": args.steps,
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "target": "tlul_socket_m1",
        "backend": "stock_verilator_hybrid",
        "support_tier": "first_supported_target",
        "clock_ownership": "tb_timed_coroutine",
        "acceptance_gate": "phase_b_endpoint",
        "inputs": {
            "mdir": str(args.mdir.resolve()),
            "nstates": args.nstates,
            "steps": args.steps,
            "block_size": args.block_size,
            "host_reset_cycles": args.host_reset_cycles,
            "host_post_reset_cycles": args.host_post_reset_cycles,
            "host_batch_length": args.host_batch_length,
            "host_seed": args.host_seed,
            "patches": list(args.patch),
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
        "outputs": {
            "done_o": int(flow_json.get("done_o", 0)) if flow_json else None,
            "cfg_signature_o": int(flow_json.get("cfg_signature_o", 0)) if flow_json else None,
            "toggle_bitmap_words": toggle_words,
        },
        "toggle_coverage": toggle_summary,
        "campaign_threshold": campaign_threshold,
        "campaign_measurement": campaign_measurement,
        "performance": metrics,
        "caveats": [
            "first supported flow keeps the timed clock coroutine in tlul_socket_m1_gpu_cov_tb",
            "Phase B is complete at phase_b_endpoint; strict_final_state remains optional Verilator-bookkeeping refinement",
        ],
    }
    if proc.returncode != 0:
        payload["stdout_tail"] = "\n".join(proc.stdout.splitlines()[-40:])
        payload["stderr_tail"] = "\n".join(proc.stderr.splitlines()[-40:])
    return payload


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Run the first supported stock-Verilator hybrid validation for tlul_socket_m1."
    )
    parser.add_argument("--mdir", type=Path, default=DEFAULT_MDIR)
    parser.add_argument("--nstates", type=int, default=256)
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--host-reset-cycles", type=int, default=4)
    parser.add_argument("--host-post-reset-cycles", type=int, default=2)
    parser.add_argument("--host-batch-length", type=int, default=1)
    parser.add_argument("--host-seed", type=int, default=1)
    parser.add_argument("--campaign-threshold-bits", type=int, default=3)
    parser.add_argument("--patch", action="append", default=[], metavar="GLOBAL_OFF:BYTE")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--flow-json-out", type=Path)
    parser.add_argument("--host-report-out", type=Path)
    parser.add_argument("--host-state-out", type=Path)
    parser.add_argument("--final-state-out", type=Path)
    args = parser.parse_args(argv)

    mdir = args.mdir.resolve()
    args.json_out = args.json_out.resolve()
    args.flow_json_out = (args.flow_json_out or (mdir / "socket_m1_host_gpu_flow_summary.json")).resolve()
    args.host_report_out = (
        args.host_report_out or (mdir / "socket_m1_host_probe_report.json")
    ).resolve()
    args.host_state_out = (args.host_state_out or (mdir / "socket_m1_host_init_state.bin")).resolve()
    args.final_state_out = (args.final_state_out or (mdir / "socket_m1_gpu_final_state.bin")).resolve()

    flow_cmd = [
        sys.executable,
        str(FLOW_TOOL),
        "--mdir",
        str(mdir),
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
        "--host-batch-length",
        str(args.host_batch_length),
        "--host-seed",
        str(args.host_seed),
        "--json-out",
        str(args.flow_json_out),
        "--host-report-out",
        str(args.host_report_out),
        "--host-state-out",
        str(args.host_state_out),
        "--final-state-out",
        str(args.final_state_out),
    ]
    for patch in args.patch:
        flow_cmd.extend(["--patch", patch])

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
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
