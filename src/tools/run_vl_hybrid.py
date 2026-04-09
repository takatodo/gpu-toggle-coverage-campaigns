#!/usr/bin/env python3
"""
run_vl_hybrid.py — launch vl_eval_batch_gpu via src/hybrid/run_vl_hybrid (Phase D).

Requires: build_vl_gpu.py output (cubin + vl_batch_gpu.meta.json) and `make -C src/hybrid`.

Usage:
  python3 run_vl_hybrid.py --mdir <verilator-cc-dir> [--nstates N] [--steps S] [--patch O:V ...]
  python3 run_vl_hybrid.py --cubin path.cubin --storage-size BYTES --nstates N [--steps S] ...
  python3 run_vl_hybrid.py --mdir <verilator-cc-dir> --dump-state out.bin
  python3 run_vl_hybrid.py --mdir <verilator-cc-dir> --init-state init.bin
  python3 run_vl_hybrid.py --cubin path.cubin --storage-size BYTES --kernels k0,k1,k2
  python3 run_vl_hybrid.py --mdir <verilator-cc-dir> --trace-stages
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import compare_vl_hybrid_modes as cmp

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
_POINTER_SIZED_HOST_ONLY_FIELDS = {"__VdlySched"}
_FULLY_ZEROED_HOST_ONLY_FIELDS = {"vlNamep"}


def _parse_kernel_list(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    items = [part.strip() for part in raw.split(",")]
    return [item for item in items if item]


def _sanitize_host_only_internals(
    blob: bytes, layout: list[dict[str, int | str]]
) -> tuple[bytes, list[dict[str, int]]]:
    patched = bytearray(blob)
    pointer_size = struct.calcsize("P")
    applied: list[dict[str, int]] = []
    for entry in layout:
        name = str(entry["name"])
        offset = int(entry["offset"])
        size = int(entry["size"])
        if name in _POINTER_SIZED_HOST_ONLY_FIELDS:
            preserve = min(pointer_size, size)
            start = offset + preserve
            end = offset + size
            if start < end:
                patched[start:end] = b"\x00" * (end - start)
                applied.append(
                    {
                        "field_name": name,
                        "offset": offset,
                        "size": size,
                        "sanitized_start": start,
                        "sanitized_end": end,
                        "preserved_prefix_bytes": preserve,
                    }
                )
        elif name in _FULLY_ZEROED_HOST_ONLY_FIELDS:
            end = offset + size
            patched[offset:end] = b"\x00" * size
            applied.append(
                {
                    "field_name": name,
                    "offset": offset,
                    "size": size,
                    "sanitized_start": offset,
                    "sanitized_end": end,
                    "preserved_prefix_bytes": 0,
                }
            )
    return bytes(patched), applied


def _prepare_sanitized_init_state(
    *, mdir: Path, init_state: Path
) -> tuple[Path, list[dict[str, int]]] | None:
    layout = cmp.probe_root_layout(mdir)
    if not layout:
        return None
    sanitized_blob, applied = _sanitize_host_only_internals(init_state.read_bytes(), layout)
    if not applied:
        return None
    fd, tmp_path = tempfile.mkstemp(prefix="run_vl_hybrid_init_", suffix=".bin")
    os.close(fd)
    tmp = Path(tmp_path)
    tmp.write_bytes(sanitized_blob)
    return tmp, applied


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
    p.add_argument(
        "--dump-state",
        type=Path,
        help="Optional raw binary dump of final device storage after all launches",
    )
    p.add_argument(
        "--init-state",
        type=Path,
        help="Optional raw binary state image uploaded before any patches/launches",
    )
    p.add_argument(
        "--sanitize-host-only-internals",
        action="store_true",
        help=(
            "Rewrite host-only internal fields in --init-state before upload. "
            "Currently sanitizes __VdlySched tail bytes and zeros vlNamep when present."
        ),
    )
    p.add_argument(
        "--kernels",
        help="Optional comma-separated kernel override; bypasses meta launch_sequence when set",
    )
    p.add_argument(
        "--trace-stages",
        action="store_true",
        help="Emit stage trace lines from the CUDA runner to help localize module-load vs launch failures.",
    )
    args = p.parse_args()
    launch_sequence = None

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
        launch_sequence = meta.get("launch_sequence")
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
    env = os.environ.copy()
    kernel_override = _parse_kernel_list(args.kernels)
    if kernel_override is not None:
        env["RUN_VL_HYBRID_KERNELS"] = ",".join(kernel_override)
    elif launch_sequence:
        env["RUN_VL_HYBRID_KERNELS"] = ",".join(str(x) for x in launch_sequence)
    else:
        env.pop("RUN_VL_HYBRID_KERNELS", None)
    if args.dump_state:
        dump_state = args.dump_state.resolve()
        dump_state.parent.mkdir(parents=True, exist_ok=True)
        env["RUN_VL_HYBRID_DUMP_STATE"] = str(dump_state)
    else:
        env.pop("RUN_VL_HYBRID_DUMP_STATE", None)
    if args.trace_stages:
        env["RUN_VL_HYBRID_TRACE_STAGES"] = "1"
    else:
        env.pop("RUN_VL_HYBRID_TRACE_STAGES", None)
    sanitized_init_tmp: Path | None = None
    if args.init_state:
        init_state = args.init_state.resolve()
        if args.sanitize_host_only_internals:
            if not args.mdir:
                p.error("--sanitize-host-only-internals requires --mdir")
            sanitized = _prepare_sanitized_init_state(mdir=mdir, init_state=init_state)
            if sanitized is not None:
                sanitized_init_tmp, applied = sanitized
                init_state = sanitized_init_tmp
                details = ", ".join(
                    f"{entry['field_name']}[{entry['sanitized_start']}:{entry['sanitized_end']}]"
                    for entry in applied
                )
                print(
                    "info: sanitized host-only init-state regions: "
                    f"{details} -> {sanitized_init_tmp}",
                    file=sys.stderr,
                )
        env["RUN_VL_HYBRID_INIT_STATE"] = str(init_state)
    else:
        env.pop("RUN_VL_HYBRID_INIT_STATE", None)
    try:
        subprocess.run(cmd, check=True, env=env)
    finally:
        if sanitized_init_tmp is not None:
            sanitized_init_tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
