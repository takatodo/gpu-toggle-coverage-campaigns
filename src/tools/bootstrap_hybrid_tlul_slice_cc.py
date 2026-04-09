#!/usr/bin/env python3
"""
Create work/vl_ir_exp/<slice>_vl (or --out-dir) with stock Verilator --cc output
(*_classes.mk, *.cpp) for build_vl_gpu.py / compare_vl_hybrid_modes.py.

Uses the same RTL file list as run_opentitan_tlul_slice_gpu_baseline for OpenTitan TLUL slices.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VERILATOR = ROOT / "third_party" / "verilator" / "bin" / "verilator"


def _load_baseline():
    path = ROOT / "src" / "runners" / "run_opentitan_tlul_slice_gpu_baseline.py"
    for p in (ROOT / "src", ROOT / "src" / "runners", ROOT / "src" / "scripts"):
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)
    spec = importlib.util.spec_from_file_location("ot_tlul_baseline", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _default_tb_candidates(baseline: object, slice_name: str) -> list[Path]:
    opentitan_src = Path(getattr(baseline, "OPENTITAN_SRC"))
    return [
        opentitan_src / f"{slice_name}_gpu_cov_tb.sv",
        opentitan_src / f"{slice_name}_cov_tb.sv",
    ]


def _resolve_tb_path(*, baseline: object, slice_name: str, tb_override: Path | None) -> tuple[Path, Path | None]:
    if tb_override is not None:
        tb = tb_override.expanduser().resolve()
        if not tb.is_file():
            raise FileNotFoundError(f"TB not found: {tb}")
        default_tb = next((path.resolve() for path in _default_tb_candidates(baseline, slice_name) if path.is_file()), None)
        return tb, default_tb

    for candidate in _default_tb_candidates(baseline, slice_name):
        if candidate.is_file():
            resolved = candidate.resolve()
            return resolved, resolved
    joined = ", ".join(str(path) for path in _default_tb_candidates(baseline, slice_name))
    raise FileNotFoundError(f"default GPU cov TB not found; looked for: {joined}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--slice-name",
        default="tlul_socket_m1",
        help="OpenTitan TLUL slice name (default: tlul_socket_m1)",
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Verilator -Mdir target (default: work/vl_ir_exp/<slice-name>_vl)",
    )
    p.add_argument(
        "--verilator",
        default=os.environ.get("VERILATOR", str(DEFAULT_VERILATOR)),
        help="verilator binary (default: $VERILATOR or third_party/verilator/bin/verilator)",
    )
    p.add_argument(
        "--tb-path",
        type=Path,
        default=None,
        help=(
            "Top-level testbench source path. Defaults to "
            "third_party/rtlmeter/designs/OpenTitan/src/<slice-name>_gpu_cov_tb.sv"
        ),
    )
    p.add_argument(
        "--top-module",
        default=None,
        help="Top module name passed to Verilator (default: inferred from --tb-path stem)",
    )
    p.add_argument(
        "--extra-source",
        action="append",
        default=[],
        help="Additional SystemVerilog source to compile alongside the inferred slice sources",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Remove out-dir before running Verilator",
    )
    args = p.parse_args(argv)

    baseline = _load_baseline()
    slice_name = str(args.slice_name)
    if slice_name not in baseline.SLICE_EXTRA_SOURCES:
        print(f"error: unsupported slice for generic baseline: {slice_name}", file=sys.stderr)
        return 1

    out_dir = (
        args.out_dir.expanduser().resolve()
        if args.out_dir is not None
        else (ROOT / "work" / "vl_ir_exp" / f"{slice_name}_vl").resolve()
    )
    vlr = Path(args.verilator).expanduser()
    if not vlr.is_file():
        print(f"error: verilator not found: {vlr}", file=sys.stderr)
        return 1

    rtl = baseline.OPENTITAN_SRC / f"{slice_name}.sv"
    try:
        tb, default_tb = _resolve_tb_path(
            baseline=baseline,
            slice_name=slice_name,
            tb_override=args.tb_path,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not rtl.is_file():
        print(f"error: RTL not found: {rtl}", file=sys.stderr)
        return 1
    sources = baseline._collect_compile_sources(slice_name, rtl, default_tb or tb)
    if default_tb is None or tb.resolve() != default_tb.resolve():
        sources.append(tb.resolve())
    for raw in args.extra_source:
        extra = Path(raw).expanduser().resolve()
        if not extra.is_file():
            print(f"error: extra source not found: {extra}", file=sys.stderr)
            return 1
        sources.append(extra)
    sources = baseline._dedupe_paths(sources)

    if args.force and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    inc = str(baseline.OPENTITAN_SRC)
    top = args.top_module or tb.stem
    cmd = [
        str(vlr),
        "--cc",
        "--flatten",
        "-Wno-fatal",
        "--top-module",
        top,
        "-Mdir",
        str(out_dir),
        "--timing",
        f"-I{inc}",
    ] + [str(s) for s in sources]

    env = os.environ.copy()
    env.setdefault("VERILATOR_ROOT", str(ROOT / "third_party" / "verilator"))
    print(" ".join(cmd))
    subprocess.run(cmd, check=True, cwd=str(out_dir), env=env)

    mks = list(out_dir.glob("*_classes.mk"))
    if not mks:
        print("error: Verilator finished but no *_classes.mk in out-dir", file=sys.stderr)
        return 1
    print(f"ok: {out_dir}  ({mks[0].name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
