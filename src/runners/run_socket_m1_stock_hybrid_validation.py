#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
FLOW_TOOL = ROOT_DIR / "src" / "tools" / "run_socket_m1_host_gpu_flow.py"
DEFAULT_MDIR = ROOT_DIR / "work" / "vl_ir_exp" / "socket_m1_vl"
DEFAULT_JSON_OUT = ROOT_DIR / "output" / "validation" / "socket_m1_stock_hybrid_validation.json"

_OK_RE = re.compile(
    r"^ok: steps=(?P<steps>\d+) kernels_per_step=(?P<kernels>\d+) "
    r"patches_per_step=(?P<patches>\d+) grid=(?P<grid>\d+) block=(?P<block>\d+) "
    r"nstates=(?P<nstates>\d+) storage=(?P<storage>\d+) B$"
)
_GPU_MS_RE = re.compile(
    r"^gpu_kernel_time_ms: total=(?P<total>[0-9.]+)\s+per_launch=(?P<per_launch>[0-9.]+)"
)
_GPU_US_RE = re.compile(r"^gpu_kernel_time: per_state=(?P<per_state_us>[0-9.]+) us")
_WALL_MS_RE = re.compile(r"^wall_time_ms: (?P<wall_ms>[0-9.]+)")
_DEVICE_RE = re.compile(r"^device \d+: (?P<device>.+)$")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json_if_exists(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_gpu_metrics(stdout: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _DEVICE_RE.match(line)
        if match:
            metrics["device_name"] = match.group("device")
            continue
        match = _OK_RE.match(line)
        if match:
            metrics["runner_shape"] = {
                "steps": int(match.group("steps")),
                "kernels_per_step": int(match.group("kernels")),
                "patches_per_step": int(match.group("patches")),
                "grid": int(match.group("grid")),
                "block": int(match.group("block")),
                "nstates": int(match.group("nstates")),
                "storage_size": int(match.group("storage")),
            }
            continue
        match = _GPU_MS_RE.match(line)
        if match:
            metrics["gpu_kernel_time_ms"] = {
                "total": float(match.group("total")),
                "per_launch": float(match.group("per_launch")),
            }
            continue
        match = _GPU_US_RE.match(line)
        if match:
            metrics["gpu_kernel_time_per_state_us"] = float(match.group("per_state_us"))
            continue
        match = _WALL_MS_RE.match(line)
        if match:
            metrics["wall_time_ms"] = float(match.group("wall_ms"))
    shape = metrics.get("runner_shape")
    gpu_ms = metrics.get("gpu_kernel_time_ms")
    if isinstance(shape, dict) and isinstance(gpu_ms, dict):
        total_ms = gpu_ms.get("total")
        nstates = shape.get("nstates")
        steps = shape.get("steps")
        kernels_per_step = shape.get("kernels_per_step")
        if isinstance(total_ms, float) and total_ms > 0.0 and isinstance(nstates, int) and isinstance(steps, int):
            metrics["throughput"] = {
                "state_steps_per_second": (nstates * steps * 1000.0) / total_ms,
            }
            if isinstance(kernels_per_step, int):
                metrics["throughput"]["kernel_launches"] = steps * kernels_per_step
    return metrics


def _build_validation_payload(
    *,
    args: argparse.Namespace,
    flow_cmd: list[str],
    flow_json: dict[str, Any] | None,
    host_report: dict[str, Any] | None,
    proc: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    metrics = _parse_gpu_metrics(proc.stdout)
    toggle_words = [
        int(flow_json.get("toggle_bitmap_word0_o", 0)) if flow_json else 0,
        int(flow_json.get("toggle_bitmap_word1_o", 0)) if flow_json else 0,
        int(flow_json.get("toggle_bitmap_word2_o", 0)) if flow_json else 0,
    ]
    toggle_bits_hit = sum(word.bit_count() for word in toggle_words)
    status = "ok" if proc.returncode == 0 and flow_json is not None else "error"
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "target": "tlul_socket_m1",
        "backend": "stock_verilator_hybrid",
        "clock_ownership": "tb_timed_coroutine",
        "acceptance_gate": "ignore_verilator_internal_final_state",
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
        },
        "artifacts": {
            "runner_json": str(args.json_out.resolve()),
            "flow_json": str(args.flow_json_out.resolve()),
            "host_report": str(args.host_report_out.resolve()),
            "host_state": str(args.host_state_out.resolve()),
            "final_state": str(args.final_state_out.resolve()),
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
        "toggle_coverage": {
            "artifact_type": "toggle_bitmap_words",
            "words_nonzero": sum(1 for word in toggle_words if word != 0),
            "bits_hit": toggle_bits_hit,
            "any_hit": toggle_bits_hit > 0,
        },
        "performance": metrics,
        "caveats": [
            "first supported flow keeps the timed clock coroutine in tlul_socket_m1_gpu_cov_tb",
            "Phase B strict_final_state is still unresolved; supported gate is ignore_verilator_internal_final_state",
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

    flow_json = _read_json_if_exists(args.flow_json_out)
    host_report = _read_json_if_exists(args.host_report_out)
    payload = _build_validation_payload(
        args=args,
        flow_cmd=flow_cmd,
        flow_json=flow_json,
        host_report=host_report,
        proc=proc,
    )
    _write_json(args.json_out, payload)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
