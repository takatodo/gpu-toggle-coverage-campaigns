#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

from stock_hybrid_validation_common import (
    campaign_threshold_toggle_bits_hit,
    toggle_coverage_summary,
    write_json,
)


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
HOST_PROBE_TOOL = ROOT_DIR / "src" / "tools" / "run_socket_m1_host_probe.py"
DEFAULT_MDIR = ROOT_DIR / "work" / "vl_ir_exp" / "socket_m1_vl"
DEFAULT_JSON_OUT = ROOT_DIR / "output" / "validation" / "socket_m1_cpu_baseline_validation.json"
DEFAULT_BINARY_NAME = "socket_m1_cpu_baseline_probe"


def _load_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        return None


def _build_probe_binary(mdir: Path, binary_out: Path) -> tuple[list[str], subprocess.CompletedProcess[str]]:
    cmd = [
        sys.executable,
        str(HOST_PROBE_TOOL),
        "--mdir",
        str(mdir),
        "--binary-out",
        str(binary_out),
        "--build-only",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    return cmd, proc


def _run_probe_binary(
    binary_path: Path,
    *,
    reset_cycles: int,
    post_reset_cycles: int,
    batch_length: int,
    seed: int,
    cfg_valid: int,
) -> tuple[list[str], subprocess.CompletedProcess[str], float]:
    cmd = [
        str(binary_path),
        "--reset-cycles",
        str(reset_cycles),
        "--post-reset-cycles",
        str(post_reset_cycles),
        "--batch-length",
        str(batch_length),
        "--seed",
        str(seed),
        "--cfg-valid",
        str(cfg_valid),
    ]
    start = time.perf_counter()
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return cmd, proc, elapsed_ms


def _build_validation_payload(
    *,
    args: argparse.Namespace,
    build_cmd: list[str],
    flow_cmd: list[str],
    build_proc: subprocess.CompletedProcess[str],
    flow_proc: subprocess.CompletedProcess[str],
    elapsed_ms: float,
    host_report: dict[str, Any] | None,
) -> dict[str, Any]:
    status = "ok" if build_proc.returncode == 0 and flow_proc.returncode == 0 and host_report is not None else "error"
    toggle_words = [
        int(host_report.get("toggle_bitmap_word0_o", 0)) if host_report else 0,
        int(host_report.get("toggle_bitmap_word1_o", 0)) if host_report else 0,
        int(host_report.get("toggle_bitmap_word2_o", 0)) if host_report else 0,
    ]
    coverage = toggle_coverage_summary(toggle_words)
    campaign_threshold = campaign_threshold_toggle_bits_hit(args.campaign_threshold_bits)
    steps_executed = int(host_report.get("drained_events", args.reset_cycles + args.post_reset_cycles)) if host_report else (
        args.reset_cycles + args.post_reset_cycles
    )
    performance = {
        "wall_time_ms": elapsed_ms,
        "steps_executed": steps_executed,
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "target": "tlul_socket_m1",
        "backend": "stock_verilator_cpu_baseline",
        "inputs": {
            "mdir": str(args.mdir.resolve()),
            "reset_cycles": args.reset_cycles,
            "post_reset_cycles": args.post_reset_cycles,
            "batch_length": args.batch_length,
            "seed": args.seed,
            "cfg_valid": args.cfg_valid,
            "campaign_threshold_bits": args.campaign_threshold_bits,
        },
        "artifacts": {
            "runner_json": str(args.json_out.resolve()),
            "probe_binary": str(args.binary_out.resolve()),
            "host_report": str(args.host_report_out.resolve()),
        },
        "commands": {
            "build": build_cmd,
            "flow": flow_cmd,
        },
        "build_returncode": build_proc.returncode,
        "flow_returncode": flow_proc.returncode,
        "host_probe": host_report,
        "outputs": {
            "done_o": int(host_report.get("done_o", 0)) if host_report else None,
            "cfg_signature_o": int(host_report.get("cfg_signature_o", 0)) if host_report else None,
            "toggle_bitmap_words": toggle_words,
        },
        "coverage": coverage,
        "campaign_threshold": campaign_threshold,
        "campaign_measurement": {
            "bits_hit": int(coverage["bits_hit"]),
            "threshold_satisfied": status == "ok" and int(coverage["bits_hit"]) >= campaign_threshold["value"],
            "wall_time_ms": elapsed_ms if status == "ok" else elapsed_ms,
            "steps_executed": steps_executed,
        },
        "performance": performance,
        "caveats": [
            "CPU baseline measures the host probe binary wall clock after build; compile time is excluded from v1.",
            "Hybrid campaign_measurement.wall_time_ms currently comes from the checked-in hybrid runner and may differ in orchestration scope.",
        ],
    }
    if build_proc.returncode != 0:
        payload["build_stdout_tail"] = "\n".join(build_proc.stdout.splitlines()[-40:])
        payload["build_stderr_tail"] = "\n".join(build_proc.stderr.splitlines()[-40:])
    if flow_proc.returncode != 0:
        payload["stdout_tail"] = "\n".join(flow_proc.stdout.splitlines()[-40:])
        payload["stderr_tail"] = "\n".join(flow_proc.stderr.splitlines()[-40:])
    return payload


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Run the stock-Verilator CPU baseline validation for tlul_socket_m1."
    )
    parser.add_argument("--mdir", type=Path, default=DEFAULT_MDIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--binary-out", type=Path)
    parser.add_argument("--host-report-out", type=Path)
    parser.add_argument("--reset-cycles", type=int, default=4)
    parser.add_argument("--post-reset-cycles", type=int, default=2)
    parser.add_argument("--batch-length", type=int, default=1)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--cfg-valid", type=int, choices=(0, 1), default=1)
    parser.add_argument("--campaign-threshold-bits", type=int, default=3)
    args = parser.parse_args(argv)

    mdir = args.mdir.resolve()
    args.json_out = args.json_out.resolve()
    args.binary_out = (args.binary_out or (mdir / DEFAULT_BINARY_NAME)).resolve()
    args.host_report_out = (args.host_report_out or (mdir / "socket_m1_cpu_baseline_host_report.json")).resolve()

    build_cmd, build_proc = _build_probe_binary(mdir, args.binary_out)
    flow_cmd: list[str] = []
    flow_proc = subprocess.CompletedProcess(args=[str(args.binary_out)], returncode=1, stdout="", stderr="")
    elapsed_ms = 0.0
    host_report = None

    if build_proc.returncode == 0:
        flow_cmd, flow_proc, elapsed_ms = _run_probe_binary(
            args.binary_out,
            reset_cycles=args.reset_cycles,
            post_reset_cycles=args.post_reset_cycles,
            batch_length=args.batch_length,
            seed=args.seed,
            cfg_valid=args.cfg_valid,
        )
        host_report = _load_json(flow_proc.stdout)
        if host_report is not None:
            args.host_report_out.parent.mkdir(parents=True, exist_ok=True)
            args.host_report_out.write_text(json.dumps(host_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    payload = _build_validation_payload(
        args=args,
        build_cmd=build_cmd,
        flow_cmd=flow_cmd,
        build_proc=build_proc,
        flow_proc=flow_proc,
        elapsed_ms=elapsed_ms,
        host_report=host_report,
    )
    write_json(args.json_out, payload)
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
