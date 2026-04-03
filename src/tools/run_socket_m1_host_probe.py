#!/usr/bin/env python3
"""
run_socket_m1_host_probe.py — build and run the minimal tlul_socket_m1 Phase C host probe.

This script:
  1. builds the generated Verilator archive closure inside --mdir
  2. links src/hybrid/socket_m1_host_probe.cpp against that closure
  3. optionally runs the resulting probe and writes its JSON summary
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_MDIR = REPO_ROOT / "work" / "vl_ir_exp" / "socket_m1_vl"
DEFAULT_BINARY = "socket_m1_host_probe"
MODEL_PREFIX = "Vtlul_socket_m1_gpu_cov_tb"
PROBE_SOURCE = REPO_ROOT / "src" / "hybrid" / "socket_m1_host_probe.cpp"
VERILATOR_ROOT = REPO_ROOT / "third_party" / "verilator"


def build_probe_binary(
    mdir: Path,
    binary_out: Path,
    *,
    cxx: str = "g++",
) -> Path:
    mdir = mdir.resolve()
    binary_out = binary_out.resolve()
    mk_path = mdir / f"{MODEL_PREFIX}.mk"
    if not mk_path.is_file():
        raise FileNotFoundError(f"{mk_path} not found")
    if not PROBE_SOURCE.is_file():
        raise FileNotFoundError(f"{PROBE_SOURCE} not found")

    env = os.environ.copy()
    env.setdefault("VERILATOR_ROOT", str(VERILATOR_ROOT))
    subprocess.run(
        ["make", "-C", str(mdir), "-f", mk_path.name, f"lib{MODEL_PREFIX}"],
        check=True,
        env=env,
    )

    binary_out.parent.mkdir(parents=True, exist_ok=True)
    compile_cmd = [
        cxx,
        "-std=c++20",
        "-O2",
        "-Wall",
        "-Wextra",
        f"-I{mdir}",
        "-isystem",
        str(VERILATOR_ROOT / "include"),
        "-isystem",
        str(VERILATOR_ROOT / "include" / "vltstd"),
        str(PROBE_SOURCE),
        str(mdir / f"lib{MODEL_PREFIX}.a"),
        str(mdir / "libverilated.a"),
        "-pthread",
        "-o",
        str(binary_out),
    ]
    subprocess.run(compile_cmd, check=True)
    return binary_out


def run_probe_binary(
    binary_path: Path,
    *,
    reset_cycles: int,
    post_reset_cycles: int,
    batch_length: int,
    seed: int,
    cfg_valid: int,
    state_out: Path | None = None,
) -> subprocess.CompletedProcess[str]:
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
    if state_out is not None:
        cmd.extend(["--state-out", str(state_out.resolve())])
    return subprocess.run(cmd, check=True, text=True, capture_output=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Build and run the tlul_socket_m1 host probe")
    p.add_argument(
        "--mdir",
        type=Path,
        default=DEFAULT_MDIR,
        help=f"Verilator --cc directory (default: {DEFAULT_MDIR})",
    )
    p.add_argument(
        "--binary-out",
        type=Path,
        help="Output path for the linked probe binary (default: <mdir>/socket_m1_host_probe)",
    )
    p.add_argument(
        "--build-only",
        action="store_true",
        help="Build the probe binary but do not run it",
    )
    p.add_argument(
        "--json-out",
        type=Path,
        help="Optional file for the probe JSON summary",
    )
    p.add_argument(
        "--state-out",
        type=Path,
        help="Optional raw root-state dump written by the probe",
    )
    p.add_argument("--reset-cycles", type=int, default=4, help="Cycles to hold rst_ni low")
    p.add_argument(
        "--post-reset-cycles",
        type=int,
        default=2,
        help="Cycles to run after releasing reset",
    )
    p.add_argument("--batch-length", type=int, default=1, help="cfg_batch_length_i value")
    p.add_argument("--seed", type=int, default=1, help="cfg_seed_i value")
    p.add_argument(
        "--cfg-valid",
        type=int,
        choices=(0, 1),
        default=1,
        help="cfg_valid_i value (0 or 1)",
    )
    args = p.parse_args()

    mdir = args.mdir.resolve()
    binary_out = (args.binary_out or (mdir / DEFAULT_BINARY)).resolve()
    binary_path = build_probe_binary(mdir, binary_out)
    if args.build_only:
        print(binary_path)
        return
    state_out = args.state_out.resolve() if args.state_out else None
    if state_out is not None:
        state_out.parent.mkdir(parents=True, exist_ok=True)

    result = run_probe_binary(
        binary_path,
        reset_cycles=args.reset_cycles,
        post_reset_cycles=args.post_reset_cycles,
        batch_length=args.batch_length,
        seed=args.seed,
        cfg_valid=args.cfg_valid,
        state_out=state_out,
    )
    if args.json_out:
        json_out = args.json_out.resolve()
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(result.stdout, encoding="utf-8")
    sys.stdout.write(result.stdout)


if __name__ == "__main__":
    main()
