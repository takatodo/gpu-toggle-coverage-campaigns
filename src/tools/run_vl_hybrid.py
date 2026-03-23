#!/usr/bin/env python3
"""
run_vl_hybrid.py — launch vl_eval_batch_gpu via src/hybrid/run_vl_hybrid (Phase D).

Requires: build_vl_gpu.py output (cubin + vl_batch_gpu.meta.json) and `make -C src/hybrid`.

Usage:
  python3 run_vl_hybrid.py --mdir <verilator-cc-dir> [--nstates N] [--steps S] [--patch O:V ...]
  python3 run_vl_hybrid.py --cubin path.cubin --storage-size BYTES --nstates N [--steps S] ...
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# WSL2: prefer host libcuda so Driver API sees the GPU (nvidia-smi can work without this).
_WSL_LIBCUDA = Path("/usr/lib/wsl/lib/libcuda.so.1")
if _WSL_LIBCUDA.is_file():
    prefix = "/usr/lib/wsl/lib"
    rest = os.environ.get("LD_LIBRARY_PATH", "")
    if rest and rest != prefix and not rest.startswith(prefix + ":"):
        os.environ["LD_LIBRARY_PATH"] = f"{prefix}:{rest}"
    elif not rest:
        os.environ["LD_LIBRARY_PATH"] = prefix

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
HYBRID_BIN = REPO_ROOT / "src" / "hybrid" / "run_vl_hybrid"


def main() -> None:
    p = argparse.ArgumentParser(description="Run hybrid GPU launch (vl_eval_batch_gpu)")
    p.add_argument(
        "--mdir",
        type=Path,
        help="Verilator --cc directory containing vl_batch_gpu.meta.json",
    )
    p.add_argument("--cubin", type=Path, help="Path to vl_batch_gpu.cubin")
    p.add_argument("--storage-size", type=int, help="Bytes per state (AoS stride)")
    p.add_argument("--nstates", type=int, default=4096, help="Parallel states (default 4096)")
    p.add_argument(
        "--steps",
        type=int,
        default=1,
        help="Repeat patch+launch cycle (default 1)",
    )
    p.add_argument("--block-size", type=int, default=256, help="CUDA block size (default 256)")
    p.add_argument(
        "--patch",
        action="append",
        default=[],
        metavar="GLOBAL_OFF:BYTE",
        help="Per-step HtoD patch (repeatable); byte decimal or 0xNN",
    )
    args = p.parse_args()

    if args.mdir:
        mdir = args.mdir.resolve()
        meta_path = mdir / "vl_batch_gpu.meta.json"
        if not meta_path.is_file():
            print(f"error: {meta_path} not found — run build_vl_gpu.py first", file=sys.stderr)
            sys.exit(1)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("schema_version") is None:
            print("warning: meta.json missing schema_version (older build)", file=sys.stderr)
        cubin = (mdir / meta["cubin"]).resolve()
        storage = int(meta["storage_size"])
    else:
        if not args.cubin or args.storage_size is None:
            p.error("either --mdir or both --cubin and --storage-size are required")
        cubin = args.cubin.resolve()
        storage = int(args.storage_size)

    if not cubin.is_file():
        print(f"error: cubin not found: {cubin}", file=sys.stderr)
        sys.exit(1)

    if not HYBRID_BIN.is_file():
        print(
            f"error: {HYBRID_BIN} not found — run: make -C {HYBRID_BIN.parent}",
            file=sys.stderr,
        )
        sys.exit(1)

    cmd = [
        str(HYBRID_BIN),
        str(cubin),
        str(storage),
        str(args.nstates),
        str(args.block_size),
        str(args.steps),
    ]
    for pat in args.patch:
        cmd.append(pat)
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
