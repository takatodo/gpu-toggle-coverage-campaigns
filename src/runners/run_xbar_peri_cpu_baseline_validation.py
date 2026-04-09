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
HOST_PROBE_TOOL = ROOT_DIR / "src" / "tools" / "run_tlul_slice_host_probe.py"
DEFAULT_MDIR = ROOT_DIR / "work" / "vl_ir_exp" / "xbar_peri_vl"
DEFAULT_TEMPLATE = ROOT_DIR / "config" / "slice_launch_templates" / "xbar_peri.json"
DEFAULT_JSON_OUT = ROOT_DIR / "output" / "validation" / "xbar_peri_cpu_baseline_validation.json"
DEFAULT_BINARY_NAME = "xbar_peri_cpu_baseline_probe"
DRIVER_SIGNAL_NAMES = {
    "batch_length": "cfg_batch_length_i",
    "req_valid_pct": "cfg_req_valid_pct_i",
    "rsp_valid_pct": "cfg_rsp_valid_pct_i",
    "host_d_ready_pct": "cfg_host_d_ready_pct_i",
    "device_a_ready_pct": "cfg_device_a_ready_pct_i",
    "put_full_pct": "cfg_put_full_pct_i",
    "put_partial_pct": "cfg_put_partial_pct_i",
    "req_fill_target": "cfg_req_fill_target_i",
    "req_burst_len_max": "cfg_req_burst_len_max_i",
    "req_family": "cfg_req_family_i",
    "req_address_mode": "cfg_req_address_mode_i",
    "req_data_mode": "cfg_req_data_mode_i",
    "req_data_hi_xor": "cfg_req_data_hi_xor_i",
    "access_ack_data_pct": "cfg_access_ack_data_pct_i",
    "rsp_error_pct": "cfg_rsp_error_pct_i",
    "rsp_fill_target": "cfg_rsp_fill_target_i",
    "rsp_delay_max": "cfg_rsp_delay_max_i",
    "rsp_family": "cfg_rsp_family_i",
    "rsp_delay_mode": "cfg_rsp_delay_mode_i",
    "rsp_data_mode": "cfg_rsp_data_mode_i",
    "rsp_data_hi_xor": "cfg_rsp_data_hi_xor_i",
    "drain_cycles": "cfg_drain_cycles_i",
    "address_mask": "cfg_address_mask_i",
    "source_mask": "cfg_source_mask_i",
}


def _load_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        return None


def _load_driver_defaults(template: Path) -> dict[str, int]:
    if not template.is_file():
        return {}
    payload = json.loads(template.read_text(encoding="utf-8"))
    defaults = dict(payload.get("runner_args_template", {}).get("driver_defaults") or {})
    parsed: dict[str, int] = {}
    for name, raw_value in defaults.items():
        signal_name = DRIVER_SIGNAL_NAMES.get(str(name), str(name))
        parsed[signal_name] = int(raw_value, 0) if isinstance(raw_value, str) else int(raw_value)
    return parsed


def _apply_overrides(settings: dict[str, int], raw_overrides: list[str]) -> dict[str, int]:
    updated = dict(settings)
    for raw in raw_overrides:
        if "=" not in raw:
            raise ValueError(f"bad --set {raw!r} (want field=value)")
        name, raw_value = raw.split("=", 1)
        updated[name] = int(raw_value, 0)
    return updated


def _build_probe_binary(
    mdir: Path,
    template: Path,
    binary_out: Path,
) -> tuple[list[str], subprocess.CompletedProcess[str]]:
    cmd = [
        sys.executable,
        str(HOST_PROBE_TOOL),
        "--mdir",
        str(mdir),
        "--template",
        str(template),
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
    settings: dict[str, int],
) -> tuple[list[str], subprocess.CompletedProcess[str], float]:
    cmd = [
        str(binary_path),
        "--reset-cycles",
        str(reset_cycles),
        "--post-reset-cycles",
        str(post_reset_cycles),
    ]
    for name in sorted(settings):
        cmd.extend(["--set", f"{name}={settings[name]}"])
    start = time.perf_counter()
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return cmd, proc, elapsed_ms


def _build_validation_payload(
    *,
    args: argparse.Namespace,
    settings: dict[str, int],
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
    steps_executed = int(host_report.get("drained_events", args.host_reset_cycles + args.host_post_reset_cycles)) if host_report else (
        args.host_reset_cycles + args.host_post_reset_cycles
    )
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "target": "xbar_peri",
        "backend": "stock_verilator_cpu_baseline",
        "clock_ownership": str((host_report or {}).get("clock_ownership") or "tb_timed_coroutine"),
        "support_tier": "campaign_reference_surface",
        "inputs": {
            "mdir": str(args.mdir.resolve()),
            "template": str(args.template.resolve()),
            "host_reset_cycles": args.host_reset_cycles,
            "host_post_reset_cycles": args.host_post_reset_cycles,
            "set": list(args.set),
            "configured_inputs": settings,
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
            "host_req_accepted_o": int(host_report.get("host_req_accepted_o", 0)) if host_report else None,
            "device_req_accepted_o": int(host_report.get("device_req_accepted_o", 0)) if host_report else None,
            "device_rsp_accepted_o": int(host_report.get("device_rsp_accepted_o", 0)) if host_report else None,
            "host_rsp_accepted_o": int(host_report.get("host_rsp_accepted_o", 0)) if host_report else None,
            "rsp_queue_overflow_o": int(host_report.get("rsp_queue_overflow_o", 0)) if host_report else None,
            "progress_cycle_count_o": int(host_report.get("progress_cycle_count_o", 0)) if host_report else None,
            "progress_signature_o": int(host_report.get("progress_signature_o", 0)) if host_report else None,
            "toggle_bitmap_words": toggle_words,
        },
        "coverage": coverage,
        "campaign_threshold": campaign_threshold,
        "campaign_measurement": {
            "bits_hit": int(coverage["bits_hit"]),
            "threshold_satisfied": status == "ok" and int(coverage["bits_hit"]) >= campaign_threshold["value"],
            "wall_time_ms": elapsed_ms if status == "ok" else None,
            "steps_executed": steps_executed,
        },
        "performance": {
            "wall_time_ms": elapsed_ms if status == "ok" else None,
            "steps_executed": steps_executed,
        },
        "caveats": [
            "CPU baseline measures the host probe binary wall clock after build; compile time is excluded from v1.",
            "This baseline reuses the xbar_peri timed-TB reference surface and does not imply design-visible GPU deltas.",
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
        description="Run the stock-Verilator CPU baseline validation for xbar_peri."
    )
    parser.add_argument("--mdir", type=Path, default=DEFAULT_MDIR)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--binary-out", type=Path)
    parser.add_argument("--host-report-out", type=Path)
    parser.add_argument("--host-reset-cycles", type=int, default=4)
    parser.add_argument("--host-post-reset-cycles", type=int, default=88)
    parser.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    parser.add_argument("--cfg-valid", type=int, choices=(0, 1), default=1)
    parser.add_argument("--campaign-threshold-bits", type=int, default=47)
    args = parser.parse_args(argv)

    mdir = args.mdir.resolve()
    args.template = args.template.resolve()
    args.json_out = args.json_out.resolve()
    args.binary_out = (args.binary_out or (mdir / DEFAULT_BINARY_NAME)).resolve()
    args.host_report_out = (args.host_report_out or (mdir / "xbar_peri_cpu_baseline_host_report.json")).resolve()
    settings = _load_driver_defaults(args.template)
    settings["cfg_valid_i"] = int(args.cfg_valid)
    settings = _apply_overrides(settings, list(args.set))

    build_cmd, build_proc = _build_probe_binary(mdir, args.template, args.binary_out)
    flow_cmd: list[str] = []
    flow_proc = subprocess.CompletedProcess(args=[str(args.binary_out)], returncode=1, stdout="", stderr="")
    elapsed_ms = 0.0
    host_report = None

    if build_proc.returncode == 0:
        flow_cmd, flow_proc, elapsed_ms = _run_probe_binary(
            args.binary_out,
            reset_cycles=args.host_reset_cycles,
            post_reset_cycles=args.host_post_reset_cycles,
            settings=settings,
        )
        host_report = _load_json(flow_proc.stdout)
        if host_report is not None:
            write_json(args.host_report_out, host_report)

    payload = _build_validation_payload(
        args=args,
        settings=settings,
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
