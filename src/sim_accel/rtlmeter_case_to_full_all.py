#!/usr/bin/env python3
"""Run the sim-accel CUDA midend flow on an RTLMeter case descriptor."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import yaml


CUDA_OPT_DIR = Path(__file__).resolve().parent


def _discover_gem_root(script_dir: Path) -> Path:
    for candidate in (script_dir, *script_dir.parents):
        if (candidate / "verilator").is_dir() and (candidate / "rtlmeter").is_dir():
            return candidate
    raise RuntimeError(
        "Could not infer GEM root from script location; pass --rtlmeter-root explicitly."
    )


GEM_ROOT = _discover_gem_root(CUDA_OPT_DIR)
DEFAULT_RTLMETER_ROOT = GEM_ROOT / "rtlmeter"
HDL_TO_FULL_ALL = CUDA_OPT_DIR / "hdl_to_full_all.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve an RTLMeter case descriptor and forward its Verilog sources, "
            "include dirs, defines, and top module into hdl_to_full_all.py."
        )
    )
    parser.add_argument(
        "--case",
        required=True,
        help="RTLMeter case triplet <DESIGN>:<CONFIG>:<TEST>",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory passed to hdl_to_full_all.py",
    )
    parser.add_argument(
        "--rtlmeter-root",
        type=Path,
        default=DEFAULT_RTLMETER_ROOT,
        help="Absolute path to the RTLMeter repository",
    )
    parser.add_argument(
        "--hybrid-abi",
        choices=("synthetic-full-all", "full-all-only"),
        default="full-all-only",
        help="Forwarded to hdl_to_full_all.py",
    )
    parser.add_argument(
        "--program-json-backend",
        action="store_true",
        default=True,
        help="Use sim_accel.program.json as the primary backend input (default: on)",
    )
    parser.add_argument(
        "--emit-raw-cuda-sidecars",
        action="store_true",
        help="Also request raw --sim-accel-only sidecars for reference",
    )
    parser.add_argument(
        "--validate-circt",
        action="store_true",
        help="Forward --validate-circt",
    )
    parser.add_argument(
        "--emit-circt-ptx",
        action="store_true",
        help="Forward --emit-circt-ptx",
    )
    parser.add_argument(
        "--validate-circt-ptx",
        action="store_true",
        help="Forward --validate-circt-ptx",
    )
    parser.add_argument(
        "--validate-llvm",
        action="store_true",
        help="Forward --validate-llvm",
    )
    parser.add_argument(
        "--emit-ptx",
        action="store_true",
        help="Forward --emit-ptx",
    )
    parser.add_argument(
        "--validate-ptx",
        action="store_true",
        help="Forward --validate-ptx",
    )
    parser.add_argument(
        "--cuda-arch",
        default="sm_80",
        help="Forward --cuda-arch (default: sm_80)",
    )
    parser.add_argument(
        "--circt-build-dir",
        type=Path,
        default=CUDA_OPT_DIR / "third_party" / "circt" / "build-simaccel",
        help="Forwarded to hdl_to_full_all.py",
    )
    parser.add_argument(
        "--circt-opt-path",
        default=None,
        help="Forwarded to hdl_to_full_all.py",
    )
    parser.add_argument(
        "--mlir-translate-path",
        default=None,
        help="Forwarded to hdl_to_full_all.py",
    )
    parser.add_argument(
        "--ptxas-path",
        default="ptxas",
        help="Forwarded to hdl_to_full_all.py",
    )
    parser.add_argument(
        "--clang-path",
        default="clang",
        help="Forwarded to hdl_to_full_all.py",
    )
    parser.add_argument(
        "--timing-mode",
        choices=("auto", "timing", "no-timing"),
        default="timing",
        help="Inject --timing/--no-timing unless descriptor already specifies one",
    )
    parser.add_argument(
        "--extra-verilator-arg",
        action="append",
        default=[],
        help="Extra raw Verilator argument appended after descriptor-derived arguments",
    )
    return parser.parse_args()


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _apply_descriptor_defaults(desc: dict) -> dict:
    desc = dict(desc or {})
    desc["compile"] = dict(desc.get("compile") or {})
    desc["execute"] = dict(desc.get("execute") or {})
    desc["execute"]["common"] = dict(desc["execute"].get("common") or {})
    desc["execute"]["tests"] = {k: dict(v or {}) for k, v in (desc["execute"].get("tests") or {}).items()}
    configs = desc.get("configurations", {"default": {}}) or {"default": {}}
    desc["configurations"] = {}
    for name, cfg in configs.items():
        cfg = dict(cfg or {})
        cfg["compile"] = dict(cfg.get("compile") or {})
        cfg["execute"] = dict(cfg.get("execute") or {})
        cfg["execute"]["common"] = dict(cfg["execute"].get("common") or {})
        cfg["execute"]["tests"] = {
            k: dict(v or {}) for k, v in (cfg["execute"].get("tests") or {}).items()
        }
        desc["configurations"][name] = cfg
    return desc


def _gather_scalar(key: str, *descs: dict) -> str | None:
    result: str | None = None
    for desc in descs:
        value = desc.get(key)
        if value is not None:
            result = str(value)
    return result


def _gather_list(key: str, *descs: dict) -> list[str]:
    result: list[str] = []
    for desc in descs:
        result.extend(str(value) for value in desc.get(key, []))
    return result


def _gather_dict(key: str, *descs: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for desc in descs:
        result.update((str(k), str(v)) for k, v in desc.get(key, {}).items())
    return result


def _load_rtlmeter_case(case: str, rtlmeter_root: Path) -> tuple[object, object]:
    design, config, test = case.split(":")
    design_dir = rtlmeter_root / "designs" / design
    descriptor_path = design_dir / "descriptor.yaml"
    desc = _apply_descriptor_defaults(yaml.safe_load(descriptor_path.read_text(encoding="utf-8")))

    root_compile = desc["compile"]
    cfg_compile = desc["configurations"][config]["compile"]
    compile_descr = SimpleNamespace()
    compile_descr.case = f"{design}:{config}"
    compile_descr.design = design
    compile_descr.config = config
    compile_descr.designDir = str(design_dir.resolve())
    compile_descr.topModule = _gather_scalar("topModule", root_compile, cfg_compile)
    compile_descr.verilogSourceFiles = [
        str((design_dir / rel).resolve()) for rel in _gather_list("verilogSourceFiles", root_compile, cfg_compile)
    ]
    compile_descr.verilogSourceFiles.append(
        str((rtlmeter_root / "rtl" / "__rtlmeter_utils.sv").resolve())
    )
    compile_descr.verilogIncludeFiles = [
        str((design_dir / rel).resolve()) for rel in _gather_list("verilogIncludeFiles", root_compile, cfg_compile)
    ]
    compile_descr.verilogIncludeFiles.append(
        str((rtlmeter_root / "rtl" / "__rtlmeter_top_include.vh").resolve())
    )
    compile_descr.verilogDefines = _gather_dict("verilogDefines", root_compile, cfg_compile)
    main_clock = _gather_scalar("mainClock", root_compile, cfg_compile)
    if main_clock is not None:
        compile_descr.verilogDefines["__RTLMETER_MAIN_CLOCK"] = main_clock
    compile_descr.verilatorArgs = _gather_list("verilatorArgs", root_compile, cfg_compile)

    root_execute_common = desc["execute"]["common"]
    root_execute_test = desc["execute"]["tests"].get(test, {})
    cfg_execute_common = desc["configurations"][config]["execute"]["common"]
    cfg_execute_test = desc["configurations"][config]["execute"]["tests"].get(test, {})
    execute_descr = SimpleNamespace()
    execute_descr.case = case
    execute_descr.args = _gather_list(
        "args", root_execute_common, root_execute_test, cfg_execute_common, cfg_execute_test
    )
    execute_descr.files = [
        str((design_dir / rel).resolve())
        for rel in _gather_list("files", root_execute_common, root_execute_test, cfg_execute_common, cfg_execute_test)
    ]
    execute_descr.tags = _gather_list(
        "tags", root_execute_common, root_execute_test, cfg_execute_common, cfg_execute_test
    )
    return compile_descr, execute_descr


def _build_verilator_args(args: argparse.Namespace, compile_descr: object) -> list[str]:
    verilator_args: list[str] = []
    descr_args = list(compile_descr.verilatorArgs)
    if args.timing_mode != "auto" and "--timing" not in descr_args and "--no-timing" not in descr_args:
        verilator_args.append("--timing" if args.timing_mode == "timing" else "--no-timing")
    verilator_args.extend(descr_args)

    include_dirs = _unique_preserve_order(
        [str(Path(path).resolve().parent) for path in compile_descr.verilogIncludeFiles]
    )
    if include_dirs:
        verilator_args.append("+incdir+" + "+".join(include_dirs))
    for key, value in sorted(compile_descr.verilogDefines.items()):
        verilator_args.append(f"+define+{key}={value}")
    verilator_args.extend(str(Path(path).resolve()) for path in compile_descr.verilogSourceFiles)
    verilator_args.extend(args.extra_verilator_arg)
    return verilator_args


def main() -> int:
    args = parse_args()
    rtlmeter_root = args.rtlmeter_root.resolve()
    compile_descr, execute_descr = _load_rtlmeter_case(args.case, rtlmeter_root)
    verilator_args = _build_verilator_args(args, compile_descr)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "case": args.case,
        "compile_case": compile_descr.case,
        "design_dir": compile_descr.designDir,
        "top_module": compile_descr.topModule,
        "verilog_source_count": len(compile_descr.verilogSourceFiles),
        "verilog_include_count": len(compile_descr.verilogIncludeFiles),
        "verilog_define_count": len(compile_descr.verilogDefines),
        "execute_args": list(execute_descr.args),
        "execute_files": list(execute_descr.files),
        "execute_tags": list(execute_descr.tags),
    }
    (args.out_dir / "rtlmeter_case_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        str(HDL_TO_FULL_ALL),
        "--top-module",
        compile_descr.topModule,
        "--out-dir",
        str(args.out_dir),
        "--hybrid-abi",
        args.hybrid_abi,
        "--clang-path",
        args.clang_path,
        "--ptxas-path",
        args.ptxas_path,
        "--cuda-arch",
        args.cuda_arch,
        "--circt-build-dir",
        str(args.circt_build_dir),
    ]
    if args.program_json_backend:
        cmd.append("--program-json-backend")
    if args.emit_raw_cuda_sidecars:
        cmd.append("--emit-raw-cuda-sidecars")
    if args.validate_circt:
        cmd.append("--validate-circt")
    if args.emit_circt_ptx:
        cmd.append("--emit-circt-ptx")
    if args.validate_circt_ptx:
        cmd.append("--validate-circt-ptx")
    if args.validate_llvm:
        cmd.append("--validate-llvm")
    if args.emit_ptx:
        cmd.append("--emit-ptx")
    if args.validate_ptx:
        cmd.append("--validate-ptx")
    if args.circt_opt_path:
        cmd.extend(["--circt-opt-path", args.circt_opt_path])
    if args.mlir_translate_path:
        cmd.extend(["--mlir-translate-path", args.mlir_translate_path])
    cmd.append("--")
    cmd.extend(verilator_args)

    (args.out_dir / "rtlmeter_case_command.sh").write_text(
        subprocess.list2cmdline(cmd) + "\n",
        encoding="utf-8",
    )
    subprocess.run(cmd, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
