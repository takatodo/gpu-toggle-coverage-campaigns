#!/usr/bin/env python3
"""
run_socket_m1_host_gpu_flow.py — minimal Phase C/D glue for tlul_socket_m1.

This script:
  1. runs the checked-in host probe to produce a stock-Verilator root-state image
  2. uploads that image into the GPU runner as the initial device state
  3. dumps the final device state and summarizes a few ABI-stable outputs
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_MDIR = REPO_ROOT / "work" / "vl_ir_exp" / "socket_m1_vl"
HOST_ABI = REPO_ROOT / "src" / "hybrid" / "host_abi.h"
HOST_PROBE = SCRIPT_DIR / "run_socket_m1_host_probe.py"
RUN_GPU = SCRIPT_DIR / "run_vl_hybrid.py"
SUPPORTED_TARGET = "tlul_socket_m1"
CLOCK_OWNERSHIP = "tb_timed_coroutine"


def _parse_socket_m1_abi() -> dict[str, int]:
    wanted = {
        "VL_SOCKET_M1_STORAGE_SIZE",
        "VL_SOCKET_M1_OFF_DONE_O",
        "VL_SOCKET_M1_OFF_CFG_SIGNATURE_O",
        "VL_SOCKET_M1_OFF_TOGGLE_BITMAP_WORD0_O",
        "VL_SOCKET_M1_OFF_TOGGLE_BITMAP_WORD1_O",
        "VL_SOCKET_M1_OFF_TOGGLE_BITMAP_WORD2_O",
    }
    values: dict[str, int] = {}
    for line in HOST_ABI.read_text(encoding="utf-8").splitlines():
        parts = line.strip().split()
        if len(parts) == 3 and parts[0] == "#define" and parts[1] in wanted:
            values[parts[1]] = int(parts[2], 0)
    missing = wanted - values.keys()
    if missing:
        raise RuntimeError(f"missing ABI defines in {HOST_ABI}: {sorted(missing)}")
    return values


def _read_u32_le(blob: bytes, offset: int) -> int:
    return int.from_bytes(blob[offset : offset + 4], "little", signed=False)


def main() -> None:
    p = argparse.ArgumentParser(description="Run tlul_socket_m1 host-probe -> GPU flow")
    p.add_argument("--mdir", type=Path, default=DEFAULT_MDIR, help=f"default: {DEFAULT_MDIR}")
    p.add_argument("--nstates", type=int, default=256, help="GPU parallel states")
    p.add_argument("--steps", type=int, default=1, help="GPU step count")
    p.add_argument("--block-size", type=int, default=256, help="CUDA block size")
    p.add_argument("--host-reset-cycles", type=int, default=4, help="host probe reset cycles")
    p.add_argument(
        "--host-post-reset-cycles",
        type=int,
        default=2,
        help="host probe cycles after releasing reset",
    )
    p.add_argument("--host-batch-length", type=int, default=1, help="host probe batch length")
    p.add_argument("--host-seed", type=int, default=1, help="host probe seed")
    p.add_argument(
        "--patch",
        action="append",
        default=[],
        metavar="GLOBAL_OFF:BYTE",
        help="Per-step HtoD patch forwarded to run_vl_hybrid.py",
    )
    p.add_argument("--json-out", type=Path, help="Optional summary JSON")
    p.add_argument("--host-report-out", type=Path, help="Optional host probe JSON path")
    p.add_argument("--host-state-out", type=Path, help="Optional host init-state path")
    p.add_argument("--final-state-out", type=Path, help="Optional final GPU state path")
    args = p.parse_args()

    mdir = args.mdir.resolve()
    host_report = (args.host_report_out or (mdir / "socket_m1_host_probe_report.json")).resolve()
    host_state = (args.host_state_out or (mdir / "socket_m1_host_init_state.bin")).resolve()
    final_state = (args.final_state_out or (mdir / "socket_m1_gpu_final_state.bin")).resolve()

    probe_cmd = [
        sys.executable,
        str(HOST_PROBE),
        "--mdir",
        str(mdir),
        "--json-out",
        str(host_report),
        "--state-out",
        str(host_state),
        "--reset-cycles",
        str(args.host_reset_cycles),
        "--post-reset-cycles",
        str(args.host_post_reset_cycles),
        "--batch-length",
        str(args.host_batch_length),
        "--seed",
        str(args.host_seed),
    ]
    subprocess.run(probe_cmd, check=True)

    gpu_cmd = [
        sys.executable,
        str(RUN_GPU),
        "--mdir",
        str(mdir),
        "--nstates",
        str(args.nstates),
        "--steps",
        str(args.steps),
        "--block-size",
        str(args.block_size),
        "--init-state",
        str(host_state),
        "--dump-state",
        str(final_state),
    ]
    for patch in args.patch:
        gpu_cmd.extend(["--patch", patch])
    subprocess.run(gpu_cmd, check=True)

    abi = _parse_socket_m1_abi()
    storage = abi["VL_SOCKET_M1_STORAGE_SIZE"]
    blob = final_state.read_bytes()
    if len(blob) < storage:
        raise RuntimeError(f"{final_state} shorter than one state: {len(blob)} < {storage}")
    state0 = blob[:storage]
    summary = {
        "target": SUPPORTED_TARGET,
        "clock_ownership": CLOCK_OWNERSHIP,
        "mdir": str(mdir),
        "nstates": args.nstates,
        "steps": args.steps,
        "block_size": args.block_size,
        "host_report": str(host_report),
        "host_state": str(host_state),
        "final_state": str(final_state),
        "storage_size": storage,
        "done_o": state0[abi["VL_SOCKET_M1_OFF_DONE_O"]],
        "cfg_signature_o": _read_u32_le(state0, abi["VL_SOCKET_M1_OFF_CFG_SIGNATURE_O"]),
        "toggle_bitmap_word0_o": _read_u32_le(
            state0,
            abi["VL_SOCKET_M1_OFF_TOGGLE_BITMAP_WORD0_O"],
        ),
        "toggle_bitmap_word1_o": _read_u32_le(
            state0,
            abi["VL_SOCKET_M1_OFF_TOGGLE_BITMAP_WORD1_O"],
        ),
        "toggle_bitmap_word2_o": _read_u32_le(
            state0,
            abi["VL_SOCKET_M1_OFF_TOGGLE_BITMAP_WORD2_O"],
        ),
        "patches": list(args.patch),
    }
    payload = json.dumps(summary, indent=2) + "\n"
    if args.json_out:
        json_out = args.json_out.resolve()
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)


if __name__ == "__main__":
    main()
