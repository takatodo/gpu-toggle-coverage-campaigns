#!/usr/bin/env python3
"""Run an HDL -> sim-accel raw CUDA/program JSON -> fused full_all pipeline.

This wrapper keeps the experimental flow under opt/gpu/cuda. It does not add
new hooks to Verilator itself. Instead it orchestrates:

1. `verilator --sim-accel-only` to emit raw generated CUDA sidecars
2. optionally `verilator --sim-accel-ir-only` to emit sim_accel.program.json
3. a fuser backend to build fused CUDA/LLVM/PTX artifacts
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
CUDA_OPT_DIR = SCRIPT_PATH.parent
ROOT_DIR = SCRIPT_PATH.parents[2]
VERILATOR_ROOT = ROOT_DIR / "third_party" / "verilator"
DEFAULT_VERILATOR = VERILATOR_ROOT / "bin" / "verilator"
FUSER_SCRIPT = CUDA_OPT_DIR / "full_kernel_fuser.py"
PROGRAM_JSON_FUSER_SCRIPT = CUDA_OPT_DIR / "program_json_to_full_all.py"


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def _run_command(cmd: list[str], *, log_path: Path, env: dict[str, str]) -> None:
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        check=False,
    )
    log_path.write_text(proc.stdout, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {proc.returncode}: {_shell_join(cmd)}\n"
            f"See log: {log_path}"
        )


def _required_path(path: Path, label: str) -> Path:
    if not path.exists():
        raise RuntimeError(f"Expected {label} not found: {path}")
    return path


def _collect_raw_artifacts(kernel_base: Path) -> dict[str, str]:
    required = {
        "kernel_cu": _required_path(kernel_base, "generated kernel").resolve(),
        "vars_tsv": _required_path(
            kernel_base.with_name(kernel_base.name + ".vars.tsv"),
            "generated vars.tsv",
        ).resolve(),
        "link_cu": _required_path(
            kernel_base.with_name(kernel_base.name + ".link.cu"),
            "generated link.cu",
        ).resolve(),
    }
    optional = {}
    optional_suffixes = {
        ".full_comb.cu": "full_comb_cu",
        ".full_seq.cu": "full_seq_cu",
        ".api.h": "api_h",
        ".cpu.cpp": "cpu_cpp",
        ".deps.tsv": "deps_tsv",
        ".comm.tsv": "comm_tsv",
        ".partitions.tsv": "partitions_tsv",
        ".clusters.tsv": "clusters_tsv",
        ".preload_targets.tsv": "preload_targets_tsv",
        ".preload_target_elements.tsv": "preload_target_elements_tsv",
        ".preload_targets.json": "preload_targets_json",
    }
    for suffix, key in optional_suffixes.items():
        candidate = kernel_base.with_name(kernel_base.name + suffix)
        if candidate.exists():
            optional[key] = str(candidate.resolve())
    for candidate in sorted(kernel_base.parent.glob(kernel_base.name + ".part*.cu")):
        optional[candidate.name] = str(candidate.resolve())
    for candidate in sorted(kernel_base.parent.glob(kernel_base.name + ".cluster*.cu")):
        optional[candidate.name] = str(candidate.resolve())
    return {
        **{key: str(value) for key, value in required.items()},
        **optional,
    }


def _collect_program_json_artifact(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {"program_json": str(path.resolve())}


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate sim-accel CUDA from HDL with Verilator and then build "
            "fused full_all CUDA/LLVM/PTX artifacts under opt/gpu/cuda."
        )
    )
    parser.add_argument("--top-module", required=True, help="Top module name passed to Verilator")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output directory for raw/fused artifacts")
    parser.add_argument(
        "--verilator",
        type=Path,
        default=DEFAULT_VERILATOR,
        help=f"Path to verilator executable (default: {DEFAULT_VERILATOR})",
    )
    parser.add_argument(
        "--kernel-basename",
        default=None,
        help="Override raw generated kernel basename (default: <top>.sim_accel.kernel.cu)",
    )
    parser.add_argument(
        "--sim-accel-assigns-per-kernel",
        type=int,
        default=None,
        help="Forwarded to Verilator as --sim-accel-assigns-per-kernel",
    )
    parser.add_argument(
        "--keep-mdir",
        action="store_true",
        help="Keep the dedicated raw/obj_dir around in the output manifest",
    )
    parser.add_argument(
        "--program-json-backend",
        action="store_true",
        help=(
            "Build fused artifacts from sim_accel.program.json instead of reparsing raw CUDA"
        ),
    )
    parser.add_argument(
        "--emit-raw-cuda-sidecars",
        action="store_true",
        help=(
            "When --program-json-backend is set, also run the raw --sim-accel-only "
            "codegen pass for debugging/reference artifacts"
        ),
    )
    parser.add_argument(
        "--hybrid-abi",
        choices=("synthetic-full-all", "full-all-only"),
        default="synthetic-full-all",
        help=(
            "Program-JSON standalone link metadata mode. synthetic-full-all exposes "
            "one synthetic partition/cluster; full-all-only disables partition/cluster "
            "ABI and keeps launch_all as the only active path."
        ),
    )
    parser.add_argument(
        "--emit-ptx",
        action="store_true",
        help="Forward --emit-ptx to full_kernel_fuser.py",
    )
    parser.add_argument(
        "--emit-circt-ptx",
        action="store_true",
        help="Forward --emit-circt-ptx to program_json_to_full_all.py",
    )
    parser.add_argument(
        "--validate-llvm",
        action="store_true",
        help="Forward --validate-llvm to full_kernel_fuser.py",
    )
    parser.add_argument(
        "--validate-circt",
        action="store_true",
        help="Forward --validate-circt to program_json_to_full_all.py",
    )
    parser.add_argument(
        "--circt-opt-path",
        default=None,
        help="Explicit circt-opt executable path used when --validate-circt is set",
    )
    parser.add_argument(
        "--circt-build-dir",
        type=Path,
        default=None,
        help="Fallback CIRCT build directory forwarded when --validate-circt is set",
    )
    parser.add_argument(
        "--circt-pipeline",
        default="canonicalize,cse",
        help="Comma-separated circt-opt pass pipeline used by --validate-circt",
    )
    parser.add_argument(
        "--disallow-unregistered-circt",
        action="store_true",
        help="Do not add --allow-unregistered-dialect for simaccel.* ops during CIRCT validation",
    )
    parser.add_argument(
        "--validate-ptx",
        action="store_true",
        help="Forward --validate-ptx to full_kernel_fuser.py",
    )
    parser.add_argument(
        "--emit-hsaco",
        action="store_true",
        help="Forward --emit-hsaco to program_json_to_full_all.py",
    )
    parser.add_argument(
        "--validate-circt-ptx",
        action="store_true",
        help="Forward --validate-circt-ptx to program_json_to_full_all.py",
    )
    parser.add_argument(
        "--clang-path",
        default="clang",
        help="clang executable used when --emit-ptx/--validate-ptx is set",
    )
    parser.add_argument(
        "--mlir-translate-path",
        default=None,
        help="Explicit mlir-translate executable path used when --emit-circt-ptx is set",
    )
    parser.add_argument(
        "--ptxas-path",
        default="ptxas",
        help="ptxas executable used when --validate-ptx is set",
    )
    parser.add_argument(
        "--ld-lld-path",
        default=shutil.which("ld.lld") or "ld.lld",
        help="ld.lld executable used when --emit-hsaco is set",
    )
    parser.add_argument(
        "--cuda-arch",
        default=None,
        help="Optional CUDA GPU arch forwarded to full_kernel_fuser.py, for example sm_80",
    )
    parser.add_argument(
        "--gfx-arch",
        default="",
        help="Optional gfx arch forwarded to program_json_to_full_all.py when --emit-hsaco is set",
    )
    parser.add_argument(
        "verilator_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to Verilator after `--`, including RTL files",
    )
    args = parser.parse_args()
    if args.verilator_args and args.verilator_args[0] == "--":
        args.verilator_args = args.verilator_args[1:]
    if not args.verilator_args:
        parser.error("Missing Verilator RTL arguments. Pass them after `--`.")
    if (args.validate_circt or args.emit_circt_ptx or args.validate_circt_ptx) and not args.program_json_backend:
        parser.error(
            "--validate-circt/--emit-circt-ptx/--validate-circt-ptx currently require --program-json-backend."
        )
    return args


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir.resolve()
    raw_dir = out_dir / "raw"
    fused_dir = out_dir / "fused"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fused_dir.mkdir(parents=True, exist_ok=True)

    kernel_basename = args.kernel_basename or f"{args.top_module}.sim_accel.kernel.cu"
    kernel_base = raw_dir / kernel_basename
    mdir = raw_dir / "obj_dir"
    program_json_path = raw_dir / f"{args.top_module}.sim_accel.program.json"
    program_json_mdir = raw_dir / "obj_dir_program_json"

    env = os.environ.copy()
    env.setdefault("VERILATOR_ROOT", str(VERILATOR_ROOT))
    manifest_path = out_dir / "pipeline_manifest.json"
    run_raw_codegen = (not args.program_json_backend) or args.emit_raw_cuda_sidecars

    verilator_cmd = [
        str(args.verilator),
        "--Wno-fatal",
        "--no-skip-identical",
        "--top-module",
        args.top_module,
        "--Mdir",
        str(mdir),
        "--sim-accel-only",
        "--sim-accel-output",
        str(kernel_base),
    ]
    if args.sim_accel_assigns_per_kernel is not None:
        verilator_cmd.extend(
            ["--sim-accel-assigns-per-kernel", str(args.sim_accel_assigns_per_kernel)]
        )
    verilator_cmd.extend(args.verilator_args)
    verilator_log = raw_dir / "verilator_codegen.log"
    manifest = {
        "schema_version": "sim-accel-opt-gpu-cuda-hdl-flow-v1",
        "verilator_root": str(VERILATOR_ROOT),
        "top_module": args.top_module,
        "kernel_basename": kernel_basename,
        "commands": {
            "verilator": _shell_join(verilator_cmd),
        },
        "logs": {
            "verilator": str(verilator_log.resolve()),
        },
        "raw_dir": str(raw_dir.resolve()),
        "fused_dir": str(fused_dir.resolve()),
        "raw_artifacts": {},
        "fused_artifacts": {},
        "verilator_status": "pending" if run_raw_codegen else "not_requested",
        "program_json_status": "not_requested",
        "fuser_status": "not_started",
        "fuser_backend": "cuda-sidecar",
        "hybrid_abi": args.hybrid_abi if args.program_json_backend else "raw-cuda-sidecar",
    }
    raw_artifacts: dict[str, str] = {}
    if run_raw_codegen:
        try:
            _run_command(verilator_cmd, log_path=verilator_log, env=env)
            manifest["verilator_status"] = "completed"
        except RuntimeError as exc:
            manifest["verilator_status"] = "failed"
            manifest["error"] = str(exc)
            if args.keep_mdir:
                manifest["mdir"] = str(mdir.resolve())
            _write_manifest(manifest_path, manifest)
            raise
        raw_artifacts.update(_collect_raw_artifacts(kernel_base))
    else:
        manifest["commands"].pop("verilator", None)
        manifest["logs"].pop("verilator", None)
        manifest.pop("kernel_basename", None)

    raw_artifacts.update(_collect_program_json_artifact(program_json_path))
    manifest["raw_artifacts"] = raw_artifacts
    fused_artifacts: dict[str, str] = {}
    fuser_cmd: list[str] | None = None
    fuser_log = fused_dir / "full_kernel_fuser.log"
    missing_full_artifacts: list[str] = []

    if args.program_json_backend:
        manifest["fuser_backend"] = "program-json"
        program_json_cmd = [
            str(args.verilator),
            "--Wno-fatal",
            "--no-skip-identical",
            "--top-module",
            args.top_module,
            "--Mdir",
            str(program_json_mdir),
            "--sim-accel-ir-output",
            str(program_json_path),
        ]
        if args.sim_accel_assigns_per_kernel is not None:
            program_json_cmd.extend(
                ["--sim-accel-assigns-per-kernel", str(args.sim_accel_assigns_per_kernel)]
            )
        program_json_cmd.extend(args.verilator_args)
        program_json_log = raw_dir / "verilator_program_json.log"
        manifest["commands"]["verilator_program_json"] = _shell_join(program_json_cmd)
        manifest["logs"]["verilator_program_json"] = str(program_json_log.resolve())
        manifest["program_json_status"] = "pending"
        try:
            _run_command(program_json_cmd, log_path=program_json_log, env=env)
            manifest["program_json_status"] = "completed"
        except RuntimeError as exc:
            manifest["program_json_status"] = "failed"
            manifest["error"] = str(exc)
            if args.keep_mdir:
                manifest["mdir"] = str(mdir.resolve())
                manifest["program_json_mdir"] = str(program_json_mdir.resolve())
            _write_manifest(manifest_path, manifest)
            raise
        raw_artifacts.update(_collect_program_json_artifact(program_json_path))
        manifest["raw_artifacts"] = raw_artifacts
        fuser_cmd = [
            sys.executable,
            str(PROGRAM_JSON_FUSER_SCRIPT),
            "--program-json",
            raw_artifacts["program_json"],
            "--out-dir",
            str(fused_dir),
            "--hybrid-abi",
            args.hybrid_abi,
        ]
    else:
        missing_full_artifacts = [
            key for key in ("full_comb_cu", "full_seq_cu") if key not in raw_artifacts
        ]
        if not missing_full_artifacts:
            fuser_cmd = [
                sys.executable,
                str(FUSER_SCRIPT),
                "--full-comb",
                raw_artifacts["full_comb_cu"],
                "--full-seq",
                raw_artifacts["full_seq_cu"],
                "--link",
                raw_artifacts["link_cu"],
                "--out-dir",
                str(fused_dir),
            ]
    if fuser_cmd is not None:
        if args.validate_llvm:
            fuser_cmd.append("--validate-llvm")
        if args.validate_circt:
            fuser_cmd.append("--validate-circt")
            if args.circt_opt_path:
                fuser_cmd.extend(["--circt-opt-path", args.circt_opt_path])
            if args.circt_build_dir:
                fuser_cmd.extend(["--circt-build-dir", str(args.circt_build_dir)])
            if args.circt_pipeline:
                fuser_cmd.extend(["--circt-pipeline", args.circt_pipeline])
            if args.disallow_unregistered_circt:
                fuser_cmd.append("--disallow-unregistered-circt")
        if args.emit_circt_ptx or args.validate_circt_ptx:
            fuser_cmd.extend(["--emit-circt-ptx", "--clang-path", args.clang_path])
            if args.mlir_translate_path:
                fuser_cmd.extend(["--mlir-translate-path", args.mlir_translate_path])
        if args.validate_circt_ptx:
            fuser_cmd.extend(["--validate-circt-ptx", "--ptxas-path", args.ptxas_path])
        if args.emit_ptx or args.validate_ptx:
            fuser_cmd.extend(["--emit-ptx", "--clang-path", args.clang_path])
        if args.validate_ptx:
            fuser_cmd.extend(["--validate-ptx", "--ptxas-path", args.ptxas_path])
        if args.emit_hsaco:
            fuser_cmd.extend(["--emit-hsaco", "--ld-lld-path", args.ld_lld_path])
            if args.gfx_arch:
                fuser_cmd.extend(["--gfx-arch", args.gfx_arch])
        if args.cuda_arch:
            fuser_cmd.extend(["--cuda-arch", args.cuda_arch])
        manifest["commands"]["fuser"] = _shell_join(fuser_cmd)
        manifest["logs"]["fuser"] = str(fuser_log.resolve())
        try:
            _run_command(fuser_cmd, log_path=fuser_log, env=env)
            manifest["fuser_status"] = "completed"
        except RuntimeError as exc:
            manifest["fuser_status"] = "failed"
            manifest["error"] = str(exc)
            if args.keep_mdir:
                manifest["mdir"] = str(mdir.resolve())
            _write_manifest(manifest_path, manifest)
            raise
        fused_artifacts = {
            path.name: str(path.resolve())
            for path in sorted(fused_dir.iterdir())
            if path.is_file()
        }
        manifest["fused_artifacts"] = fused_artifacts

    if fuser_cmd is None:
        manifest["fuser_status"] = "skipped_missing_full_kernels"
        manifest["missing_full_artifacts"] = missing_full_artifacts
    if args.keep_mdir:
        manifest["mdir"] = str(mdir.resolve())
        if args.program_json_backend:
            manifest["program_json_mdir"] = str(program_json_mdir.resolve())

    _write_manifest(manifest_path, manifest)

    print(f"wrote {manifest_path}")
    print(f"raw_dir={raw_dir}")
    print(f"fused_dir={fused_dir}")
    if missing_full_artifacts:
        print(f"skipped_fuser_missing={','.join(missing_full_artifacts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
