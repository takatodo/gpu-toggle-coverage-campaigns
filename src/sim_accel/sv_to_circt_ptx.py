#!/usr/bin/env python3
"""Run a direct SystemVerilog -> CIRCT -> LLVM/PTX flow without Verilator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

import circt_tooling

CUDA_OPT_DIR = Path(__file__).resolve().parent
SWEEP_DIRECT_LLVM_FEEDBACK_CUTS = CUDA_OPT_DIR / "sweep_direct_llvm_feedback_cuts.py"
DIRECT_LLVM_FEEDBACK_PROBE = CUDA_OPT_DIR / "direct_llvm_feedback_probe.py"

IMPORT_MODE_TO_FLAG = {
    "ir-hw": "--ir-hw",
    "ir-moore": "--ir-moore",
    "ir-llhd": "--ir-llhd",
    "full": None,
}

IMPORT_MODE_TO_BASENAME = {
    "ir-hw": "circt_verilog.hw.mlir",
    "ir-moore": "circt_verilog.moore.mlir",
    "ir-llhd": "circt_verilog.llhd.mlir",
    "full": "circt_verilog.full.mlir",
}

ALLOWED_ARC_LLHD_OPS = {
    "llhd.combinational",
    "llhd.yield",
}

LLHD_OP_RE = re.compile(r"\b(llhd\.[A-Za-z_][A-Za-z0-9_]+)\b")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Import SystemVerilog with CIRCT's Slang frontend, lower the "
            "result through a direct CIRCT lowering path, and optionally emit PTX."
        )
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for imported MLIR, logs, LLVM IR, and PTX",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=circt_tooling.DEFAULT_CIRCT_BUILD_DIR,
        help=(
            "CIRCT build directory used for default tool resolution "
            f"(default: {circt_tooling.DEFAULT_CIRCT_BUILD_DIR})"
        ),
    )
    parser.add_argument(
        "--circt-verilog-path",
        default=None,
        help="Explicit circt-verilog executable path",
    )
    parser.add_argument(
        "--circt-opt-path",
        default=None,
        help="Explicit circt-opt executable path",
    )
    parser.add_argument(
        "--mlir-translate-path",
        default=None,
        help="Explicit mlir-translate executable path",
    )
    parser.add_argument(
        "--clang-path",
        default="clang",
        help="clang executable used for PTX emission when llc is unavailable",
    )
    parser.add_argument(
        "--cuda-arch",
        default=None,
        help="Optional CUDA GPU arch, for example sm_80",
    )
    parser.add_argument(
        "--stop-after",
        choices=(
            "import",
            "core",
            "pre-arc",
            "direct-llvm-probe",
            "direct-llvm-clean",
            "direct-llvm-agg",
            "direct-llvm-feedback-sweep",
            "direct-llvm-feedback-probe",
            "arcs",
            "llvm-dialect",
            "llvm-ir",
            "ptx",
        ),
        default="ptx",
        help="Stop after the named stage (default: ptx)",
    )
    parser.add_argument(
        "--import-mode",
        choices=tuple(IMPORT_MODE_TO_FLAG),
        default="ir-hw",
        help=(
            "circt-verilog import mode. Use ir-moore to preserve the Moore "
            "frontend boundary and run convert-moore-to-core explicitly."
        ),
    )
    parser.add_argument(
        "--async-resets-as-sync",
        action="store_true",
        help=(
            "When using --import-mode full, pass async resets through arc-strip-sv "
            "as synchronous resets."
        ),
    )
    parser.add_argument(
        "--auto-feedback-sweep-on-scc",
        action="store_true",
        help=(
            "After direct-llvm-agg, automatically run the bounded feedback-cut sweep "
            "when the aggregate-lowered artifact still contains a nontrivial SCC."
        ),
    )
    parser.add_argument(
        "--feedback-sweep-stop-after",
        choices=("cut", "func", "llvm-dialect", "llvm-ir", "ptx"),
        default="llvm-ir",
        help="Stop stage forwarded to sweep_direct_llvm_feedback_cuts.py (default: llvm-ir)",
    )
    parser.add_argument(
        "--feedback-sweep-limit",
        type=int,
        default=0,
        help="Optional candidate cap forwarded to the feedback sweep (default: all cycle edges)",
    )
    parser.add_argument(
        "--auto-feedback-probe-on-scc",
        action="store_true",
        help=(
            "After the feedback sweep selects a best cut, automatically run the "
            "bounded direct-LLVM feedback probe when the aggregate-lowered artifact "
            "still contains a nontrivial SCC."
        ),
    )
    parser.add_argument(
        "--feedback-probe-stop-after",
        choices=("cut", "func", "llvm-dialect", "llvm-ir", "ptx"),
        default="llvm-ir",
        help="Stop stage forwarded to direct_llvm_feedback_probe.py (default: llvm-ir)",
    )
    parser.add_argument(
        "--top-module",
        action="append",
        default=[],
        help="Top module to import; may be passed multiple times",
    )
    parser.add_argument(
        "-I",
        "--include-dir",
        action="append",
        default=[],
        help="Additional include search path",
    )
    parser.add_argument(
        "--isystem",
        action="append",
        default=[],
        help="Additional system include search path",
    )
    parser.add_argument(
        "-y",
        "--libdir",
        action="append",
        default=[],
        help="Library search path for missing modules",
    )
    parser.add_argument(
        "-Y",
        "--libext",
        action="append",
        default=[],
        help="Additional library file extension",
    )
    parser.add_argument(
        "-D",
        "--define",
        action="append",
        default=[],
        help="Macro definition forwarded to circt-verilog",
    )
    parser.add_argument(
        "-U",
        "--undefine",
        action="append",
        default=[],
        help="Macro undefinition forwarded to circt-verilog",
    )
    parser.add_argument(
        "-C",
        "--command-file",
        action="append",
        default=[],
        help="Command/filelist passed through to circt-verilog",
    )
    parser.add_argument(
        "--single-unit",
        action="store_true",
        help="Treat all sources as one compilation unit",
    )
    parser.add_argument(
        "--ignore-unknown-modules",
        action="store_true",
        help="Allow unresolved module/interface/program instantiations",
    )
    parser.add_argument(
        "--allow-use-before-declare",
        action="store_true",
        help="Allow names to be used before declaration",
    )
    parser.add_argument(
        "sources",
        nargs="*",
        help="SystemVerilog source files; may be empty when --command-file is used",
    )
    args = parser.parse_args()
    if not args.sources and not args.command_file:
        parser.error("Pass at least one source file or one --command-file.")
    return args


def _resolve_required_tool(
    explicit: str | None,
    fallback: Path | None,
    names: list[str],
    label: str,
    hint: str | None = None,
) -> Path:
    path = circt_tooling.resolve_executable(explicit, fallback, names)
    if path is not None:
        return path
    detail = f"Could not find {label}."
    if hint:
        detail += f" {hint}"
    raise RuntimeError(detail)


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _emit_ptx(
    llvm_path: Path,
    ptx_path: Path,
    *,
    clang_path: str,
    cuda_arch: str | None,
    log_path: Path,
) -> list[str]:
    llc_path = circt_tooling.resolve_executable(None, None, ["llc-18", "llc"])
    if llc_path is not None:
        cmd = [str(llc_path), "-march=nvptx64"]
        if cuda_arch:
            cmd.append(f"-mcpu={cuda_arch}")
        cmd.extend(["-o", str(ptx_path), str(llvm_path)])
        circt_tooling.run_checked(cmd, log_path=log_path)
        return cmd

    clang_bin = _resolve_required_tool(
        clang_path,
        None,
        [clang_path],
        "clang",
        hint="Pass --clang-path or install clang in PATH.",
    )
    cmd = [
        str(clang_bin),
        "-S",
        "-x",
        "ir",
        "--target=nvptx64-nvidia-cuda",
        "-nocudalib",
    ]
    if cuda_arch:
        cmd.append(f"--cuda-gpu-arch={cuda_arch}")
    cmd.extend([str(llvm_path), "-o", str(ptx_path)])
    circt_tooling.run_checked(cmd, log_path=log_path)
    return cmd


def _summarize_arc_illegal_llhd_ops(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in LLHD_OP_RE.finditer(path.read_text(encoding="utf-8", errors="ignore")):
        op_name = match.group(1)
        if op_name in ALLOWED_ARC_LLHD_OPS:
            continue
        counts[op_name] = counts.get(op_name, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    script_dir = Path(__file__).resolve().parent
    manifest_path = out_dir / "sv_to_circt_ptx_manifest.json"
    manifest: dict[str, object] = {
        "build_dir": str(args.build_dir.resolve()),
        "cuda_arch": args.cuda_arch,
        "import_mode": args.import_mode,
        "async_resets_as_sync": args.async_resets_as_sync,
        "sources": [str(Path(source).resolve()) for source in args.sources],
        "command_files": [str(Path(path).resolve()) for path in args.command_file],
        "top_modules": list(args.top_module),
        "stop_after": args.stop_after,
        "stages": {},
    }

    try:
        circt_verilog = _resolve_required_tool(
            args.circt_verilog_path,
            circt_tooling.default_circt_verilog_path(args.build_dir),
            ["circt-verilog"],
            "circt-verilog",
            hint=(
                "Re-run bootstrap_circt_tools.py with --enable-slang-frontend, "
                "or pass --circt-verilog-path."
            ),
        )
        circt_opt = _resolve_required_tool(
            args.circt_opt_path,
            circt_tooling.default_circt_opt_path(args.build_dir),
            ["circt-opt"],
            "circt-opt",
        )
        mlir_translate = _resolve_required_tool(
            args.mlir_translate_path,
            circt_tooling.default_mlir_translate_path(args.build_dir),
            ["mlir-translate"],
            "mlir-translate",
        )

        imported_mlir_path = out_dir / IMPORT_MODE_TO_BASENAME[args.import_mode]
        import_log = out_dir / "circt_verilog.log"
        import_cmd = [
            str(circt_verilog),
            "-o",
            str(imported_mlir_path),
        ]
        mode_flag = IMPORT_MODE_TO_FLAG[args.import_mode]
        if mode_flag is not None:
            import_cmd.insert(1, mode_flag)
        for top in args.top_module:
            import_cmd.extend(["--top", top])
        for include_dir in args.include_dir:
            import_cmd.append(f"-I{include_dir}")
        for include_dir in args.isystem:
            import_cmd.extend(["--isystem", include_dir])
        for libdir in args.libdir:
            import_cmd.append(f"-y{libdir}")
        for libext in args.libext:
            import_cmd.append(f"-Y{libext}")
        for define in args.define:
            import_cmd.append(f"-D{define}")
        for undefine in args.undefine:
            import_cmd.append(f"-U{undefine}")
        for command_file in args.command_file:
            import_cmd.append(f"-C{command_file}")
        if args.single_unit:
            import_cmd.append("--single-unit")
        if args.ignore_unknown_modules:
            import_cmd.append("--ignore-unknown-modules")
        if args.allow_use_before_declare:
            import_cmd.append("--allow-use-before-declare")
        import_cmd.extend(args.sources)
        circt_tooling.run_checked(import_cmd, log_path=import_log)
        manifest["circt_verilog"] = str(circt_verilog)
        manifest["stages"]["import"] = {
            "cmd": import_cmd,
            "log": str(import_log),
            "output": str(imported_mlir_path),
        }
        if args.stop_after == "import":
            _write_manifest(manifest_path, manifest)
            print(f"wrote {imported_mlir_path}")
            print(f"wrote {import_log}")
            print(f"wrote {manifest_path}")
            return 0

        lowering_input_path = imported_mlir_path
        if args.import_mode == "ir-moore":
            core_mlir_path = out_dir / "circt_verilog.core.mlir"
            core_log = out_dir / "circt_verilog.core.log"
            core_cmd = [
                str(circt_opt),
                str(imported_mlir_path),
                "--convert-moore-to-core",
                "-o",
                str(core_mlir_path),
            ]
            circt_tooling.run_checked(core_cmd, log_path=core_log)
            manifest["circt_opt"] = str(circt_opt)
            manifest["stages"]["core"] = {
                "cmd": core_cmd,
                "log": str(core_log),
                "output": str(core_mlir_path),
            }
            lowering_input_path = core_mlir_path
            if args.stop_after == "core":
                _write_manifest(manifest_path, manifest)
                print(f"wrote {imported_mlir_path}")
                print(f"wrote {import_log}")
                print(f"wrote {core_mlir_path}")
                print(f"wrote {core_log}")
                print(f"wrote {manifest_path}")
                return 0
        elif args.stop_after == "core":
            raise RuntimeError("--stop-after core requires --import-mode ir-moore")
        elif args.import_mode == "full":
            pre_arc_mlir_path = out_dir / "circt_verilog.pre_arc.mlir"
            pre_arc_log = out_dir / "circt_verilog.pre_arc.log"
            strip_sv_flag = "--arc-strip-sv"
            if args.async_resets_as_sync:
                strip_sv_flag = "--arc-strip-sv=async-resets-as-sync"
            pre_arc_cmd = [
                str(circt_opt),
                str(imported_mlir_path),
                strip_sv_flag,
                "--llhd-inline-calls",
                "--llhd-lower-processes",
                "--llhd-wrap-procedural-ops",
                "--llhd-deseq",
                "--llhd-hoist-signals",
                "--llhd-combine-drives",
                "--llhd-mem2reg",
                "--llhd-sig2reg",
                "--llhd-remove-control-flow",
                "--cse",
                "-o",
                str(pre_arc_mlir_path),
            ]
            circt_tooling.run_checked(pre_arc_cmd, log_path=pre_arc_log)
            manifest["circt_opt"] = str(circt_opt)
            manifest["stages"]["pre_arc"] = {
                "cmd": pre_arc_cmd,
                "log": str(pre_arc_log),
                "output": str(pre_arc_mlir_path),
            }
            pre_arc_bridge_path = out_dir / "circt_verilog.pre_arc_bridge.mlir"
            pre_arc_bridge_log = out_dir / "circt_verilog.pre_arc_bridge.log"
            pre_arc_bridge_cmd = [
                sys.executable,
                str(script_dir / "lower_llhd_zero_delay_nets.py"),
                "--input",
                str(pre_arc_mlir_path),
                "--output",
                str(pre_arc_bridge_path),
            ]
            circt_tooling.run_checked(pre_arc_bridge_cmd, log_path=pre_arc_bridge_log)
            manifest["stages"]["pre_arc_bridge"] = {
                "cmd": pre_arc_bridge_cmd,
                "log": str(pre_arc_bridge_log),
                "input": str(pre_arc_mlir_path),
                "output": str(pre_arc_bridge_path),
            }
            lowering_input_path = pre_arc_bridge_path
            if args.stop_after == "pre-arc":
                _write_manifest(manifest_path, manifest)
                print(f"wrote {imported_mlir_path}")
                print(f"wrote {import_log}")
                print(f"wrote {pre_arc_mlir_path}")
                print(f"wrote {pre_arc_log}")
                print(f"wrote {pre_arc_bridge_path}")
                print(f"wrote {pre_arc_bridge_log}")
                print(f"wrote {manifest_path}")
                return 0

        direct_llvm_probe_path = out_dir / "circt_direct.ext_flat.mlir"
        direct_llvm_probe_log = out_dir / "circt_direct.ext_flat.log"
        direct_llvm_probe_cmd = [
            str(circt_opt),
            str(lowering_input_path),
            "--externalize-registers",
            "--hw-flatten-modules",
            "--cse",
            "-o",
            str(direct_llvm_probe_path),
        ]
        circt_tooling.run_checked(direct_llvm_probe_cmd, log_path=direct_llvm_probe_log)
        manifest["stages"]["direct_llvm_probe"] = {
            "cmd": direct_llvm_probe_cmd,
            "log": str(direct_llvm_probe_log),
            "output": str(direct_llvm_probe_path),
        }
        if args.stop_after == "direct-llvm-probe":
            _write_manifest(manifest_path, manifest)
            print(f"wrote {imported_mlir_path}")
            print(f"wrote {import_log}")
            if args.import_mode == "ir-moore":
                print(f"wrote {lowering_input_path}")
                print(f"wrote {out_dir / 'circt_verilog.core.log'}")
            if args.import_mode == "full":
                print(f"wrote {out_dir / 'circt_verilog.pre_arc.log'}")
                print(f"wrote {out_dir / 'circt_verilog.pre_arc.mlir'}")
                print(f"wrote {lowering_input_path}")
                print(f"wrote {out_dir / 'circt_verilog.pre_arc_bridge.log'}")
            print(f"wrote {direct_llvm_probe_path}")
            print(f"wrote {direct_llvm_probe_log}")
            print(f"wrote {manifest_path}")
            return 0

        direct_llvm_clean_path = out_dir / "circt_direct.ext_clean.mlir"
        direct_llvm_clean_log = out_dir / "circt_direct.ext_clean.log"
        direct_llvm_clean_cmd = [
            str(circt_opt),
            str(direct_llvm_probe_path),
            "--hw-convert-bitcasts",
            "--canonicalize",
            "--cse",
            "--llhd-unroll-loops",
            "--llhd-remove-control-flow",
            "--canonicalize",
            "--cse",
            "-o",
            str(direct_llvm_clean_path),
        ]
        circt_tooling.run_checked(direct_llvm_clean_cmd, log_path=direct_llvm_clean_log)
        manifest["stages"]["direct_llvm_clean"] = {
            "cmd": direct_llvm_clean_cmd,
            "log": str(direct_llvm_clean_log),
            "input": str(direct_llvm_probe_path),
            "output": str(direct_llvm_clean_path),
        }
        if args.stop_after == "direct-llvm-clean":
            _write_manifest(manifest_path, manifest)
            print(f"wrote {imported_mlir_path}")
            print(f"wrote {import_log}")
            if args.import_mode == "ir-moore":
                print(f"wrote {lowering_input_path}")
                print(f"wrote {out_dir / 'circt_verilog.core.log'}")
            if args.import_mode == "full":
                print(f"wrote {out_dir / 'circt_verilog.pre_arc.log'}")
                print(f"wrote {out_dir / 'circt_verilog.pre_arc.mlir'}")
                print(f"wrote {lowering_input_path}")
                print(f"wrote {out_dir / 'circt_verilog.pre_arc_bridge.log'}")
            print(f"wrote {direct_llvm_probe_path}")
            print(f"wrote {direct_llvm_probe_log}")
            print(f"wrote {direct_llvm_clean_path}")
            print(f"wrote {direct_llvm_clean_log}")
            print(f"wrote {manifest_path}")
            return 0

        direct_llvm_agg_path = out_dir / "circt_direct.ext_clean_agg.mlir"
        direct_llvm_agg_log = out_dir / "circt_direct.ext_clean_agg.log"
        direct_llvm_agg_cmd = [
            str(circt_opt),
            str(direct_llvm_clean_path),
            "--hw-aggregate-to-comb",
            "--hw-convert-bitcasts",
            "--canonicalize",
            "--cse",
            "-o",
            str(direct_llvm_agg_path),
        ]
        circt_tooling.run_checked(direct_llvm_agg_cmd, log_path=direct_llvm_agg_log)
        manifest["stages"]["direct_llvm_agg"] = {
            "cmd": direct_llvm_agg_cmd,
            "log": str(direct_llvm_agg_log),
            "input": str(direct_llvm_clean_path),
            "output": str(direct_llvm_agg_path),
        }
        direct_llvm_scc_path = out_dir / "circt_direct.ext_clean_agg.scc.json"
        direct_llvm_scc_log = out_dir / "circt_direct.ext_clean_agg.scc.log"
        direct_llvm_scc_cmd = [
            sys.executable,
            str(CUDA_OPT_DIR / "analyze_mlir_graph_scc.py"),
            "--input",
            str(direct_llvm_agg_path),
            "--output",
            str(direct_llvm_scc_path),
        ]
        circt_tooling.run_checked(direct_llvm_scc_cmd, log_path=direct_llvm_scc_log)
        direct_llvm_scc = _read_json(direct_llvm_scc_path)
        manifest["stages"]["direct_llvm_scc"] = {
            "cmd": direct_llvm_scc_cmd,
            "log": str(direct_llvm_scc_log),
            "input": str(direct_llvm_agg_path),
            "output": str(direct_llvm_scc_path),
            "summary": direct_llvm_scc,
        }
        if args.stop_after == "direct-llvm-agg":
            _write_manifest(manifest_path, manifest)
            print(f"wrote {imported_mlir_path}")
            print(f"wrote {import_log}")
            if args.import_mode == "ir-moore":
                print(f"wrote {lowering_input_path}")
                print(f"wrote {out_dir / 'circt_verilog.core.log'}")
            if args.import_mode == "full":
                print(f"wrote {out_dir / 'circt_verilog.pre_arc.log'}")
                print(f"wrote {out_dir / 'circt_verilog.pre_arc.mlir'}")
                print(f"wrote {lowering_input_path}")
                print(f"wrote {out_dir / 'circt_verilog.pre_arc_bridge.log'}")
            print(f"wrote {direct_llvm_probe_path}")
            print(f"wrote {direct_llvm_probe_log}")
            print(f"wrote {direct_llvm_clean_path}")
            print(f"wrote {direct_llvm_clean_log}")
            print(f"wrote {direct_llvm_agg_path}")
            print(f"wrote {direct_llvm_agg_log}")
            print(f"wrote {direct_llvm_scc_path}")
            print(f"wrote {direct_llvm_scc_log}")
            print(f"wrote {manifest_path}")
            return 0

        should_run_feedback_sweep = (
            args.stop_after == "direct-llvm-feedback-sweep"
            or (
                args.auto_feedback_sweep_on_scc
                and int(direct_llvm_scc.get("largest_scc_size", 0)) > 0
            )
        )
        if should_run_feedback_sweep:
            direct_feedback_sweep_dir = out_dir / "direct_feedback_sweep"
            direct_feedback_best_cut_spec = out_dir / "direct_feedback_cut_best.json"
            direct_feedback_sweep_cmd = [
                sys.executable,
                str(SWEEP_DIRECT_LLVM_FEEDBACK_CUTS),
                "--input",
                str(direct_llvm_agg_path),
                "--scc-json",
                str(direct_llvm_scc_path),
                "--out-dir",
                str(direct_feedback_sweep_dir),
                "--build-dir",
                str(args.build_dir),
                "--stop-after",
                args.feedback_sweep_stop_after,
                "--emit-best-cut-spec",
                str(direct_feedback_best_cut_spec),
            ]
            if args.feedback_sweep_limit > 0:
                direct_feedback_sweep_cmd.extend(
                    ["--limit", str(args.feedback_sweep_limit)]
                )
            if args.cuda_arch:
                direct_feedback_sweep_cmd.extend(["--cuda-arch", args.cuda_arch])
            direct_feedback_sweep_log = out_dir / "direct_feedback_sweep.log"
            circt_tooling.run_checked(
                direct_feedback_sweep_cmd, log_path=direct_feedback_sweep_log
            )
            direct_feedback_sweep_summary_path = (
                direct_feedback_sweep_dir / "direct_feedback_sweep_summary.json"
            )
            direct_feedback_sweep_summary = _read_json(direct_feedback_sweep_summary_path)
            manifest["stages"]["direct_llvm_feedback_sweep"] = {
                "cmd": direct_feedback_sweep_cmd,
                "log": str(direct_feedback_sweep_log),
                "output_dir": str(direct_feedback_sweep_dir),
                "summary": direct_feedback_sweep_summary,
                "best_cut_spec": str(direct_feedback_best_cut_spec),
            }
            if args.stop_after == "direct-llvm-feedback-sweep":
                _write_manifest(manifest_path, manifest)
                print(f"wrote {imported_mlir_path}")
                print(f"wrote {import_log}")
                if args.import_mode == "ir-moore":
                    print(f"wrote {lowering_input_path}")
                    print(f"wrote {out_dir / 'circt_verilog.core.log'}")
                if args.import_mode == "full":
                    print(f"wrote {out_dir / 'circt_verilog.pre_arc.log'}")
                    print(f"wrote {out_dir / 'circt_verilog.pre_arc.mlir'}")
                    print(f"wrote {lowering_input_path}")
                    print(f"wrote {out_dir / 'circt_verilog.pre_arc_bridge.log'}")
                print(f"wrote {direct_llvm_probe_path}")
                print(f"wrote {direct_llvm_probe_log}")
                print(f"wrote {direct_llvm_clean_path}")
                print(f"wrote {direct_llvm_clean_log}")
                print(f"wrote {direct_llvm_agg_path}")
                print(f"wrote {direct_llvm_agg_log}")
                print(f"wrote {direct_llvm_scc_path}")
                print(f"wrote {direct_llvm_scc_log}")
                print(f"wrote {direct_feedback_sweep_summary_path}")
                print(f"wrote {direct_feedback_sweep_log}")
                print(f"wrote {direct_feedback_best_cut_spec}")
                print(f"wrote {manifest_path}")
                return 0

            should_run_feedback_probe = (
                args.stop_after == "direct-llvm-feedback-probe"
                or (
                    args.auto_feedback_probe_on_scc
                    and int(direct_llvm_scc.get("largest_scc_size", 0)) > 0
                )
            )
            if should_run_feedback_probe:
                direct_feedback_probe_dir = out_dir / "direct_feedback_probe"
                direct_feedback_probe_cmd = [
                    sys.executable,
                    str(DIRECT_LLVM_FEEDBACK_PROBE),
                    "--input",
                    str(direct_llvm_agg_path),
                    "--out-dir",
                    str(direct_feedback_probe_dir),
                    "--cut-spec",
                    str(direct_feedback_best_cut_spec),
                    "--build-dir",
                    str(args.build_dir),
                    "--stop-after",
                    args.feedback_probe_stop_after,
                ]
                if args.cuda_arch:
                    direct_feedback_probe_cmd.extend(["--cuda-arch", args.cuda_arch])
                direct_feedback_probe_log = out_dir / "direct_feedback_probe.log"
                circt_tooling.run_checked(
                    direct_feedback_probe_cmd, log_path=direct_feedback_probe_log
                )
                direct_feedback_probe_manifest_path = (
                    direct_feedback_probe_dir / "direct_feedback_probe_manifest.json"
                )
                direct_feedback_probe_manifest = _read_json(
                    direct_feedback_probe_manifest_path
                )
                manifest["stages"]["direct_llvm_feedback_probe"] = {
                    "cmd": direct_feedback_probe_cmd,
                    "log": str(direct_feedback_probe_log),
                    "output_dir": str(direct_feedback_probe_dir),
                    "manifest": direct_feedback_probe_manifest,
                }
                if args.stop_after == "direct-llvm-feedback-probe":
                    _write_manifest(manifest_path, manifest)
                    print(f"wrote {imported_mlir_path}")
                    print(f"wrote {import_log}")
                    if args.import_mode == "ir-moore":
                        print(f"wrote {lowering_input_path}")
                        print(f"wrote {out_dir / 'circt_verilog.core.log'}")
                    if args.import_mode == "full":
                        print(f"wrote {out_dir / 'circt_verilog.pre_arc.log'}")
                        print(f"wrote {out_dir / 'circt_verilog.pre_arc.mlir'}")
                        print(f"wrote {lowering_input_path}")
                        print(f"wrote {out_dir / 'circt_verilog.pre_arc_bridge.log'}")
                    print(f"wrote {direct_llvm_probe_path}")
                    print(f"wrote {direct_llvm_probe_log}")
                    print(f"wrote {direct_llvm_clean_path}")
                    print(f"wrote {direct_llvm_clean_log}")
                    print(f"wrote {direct_llvm_agg_path}")
                    print(f"wrote {direct_llvm_agg_log}")
                    print(f"wrote {direct_llvm_scc_path}")
                    print(f"wrote {direct_llvm_scc_log}")
                    print(f"wrote {direct_feedback_sweep_summary_path}")
                    print(f"wrote {direct_feedback_sweep_log}")
                    print(f"wrote {direct_feedback_best_cut_spec}")
                    print(f"wrote {direct_feedback_probe_manifest_path}")
                    print(f"wrote {direct_feedback_probe_log}")
                    print(f"wrote {manifest_path}")
                    return 0

        arc_preflight_path = out_dir / "circt_direct.arc_preflight.json"
        illegal_llhd_ops = _summarize_arc_illegal_llhd_ops(lowering_input_path)
        arc_preflight = {
            "input": str(lowering_input_path),
            "allowed_llhd_ops": sorted(ALLOWED_ARC_LLHD_OPS),
            "illegal_llhd_ops": illegal_llhd_ops,
        }
        arc_preflight_path.write_text(
            json.dumps(arc_preflight, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        manifest["stages"]["arc_preflight"] = {
            "output": str(arc_preflight_path),
            "illegal_llhd_ops": illegal_llhd_ops,
        }
        if illegal_llhd_ops:
            summary = ", ".join(
                f"{name}={count}" for name, count in list(illegal_llhd_ops.items())[:8]
            )
            raise RuntimeError(
                "Arc lowering preflight failed: CIRCT ConvertToArcs only legalizes "
                f"{', '.join(sorted(ALLOWED_ARC_LLHD_OPS))}, but input still contains "
                f"other LLHD ops ({summary})."
            )
        elif args.stop_after == "pre-arc":
            raise RuntimeError("--stop-after pre-arc requires --import-mode full")

        arcs_mlir_path = out_dir / "circt_direct.arcs.mlir"
        arcs_log = out_dir / "circt_direct.arcs.log"
        arcs_cmd = [
            str(circt_opt),
            str(lowering_input_path),
            "--convert-to-arcs",
            "-o",
            str(arcs_mlir_path),
        ]
        circt_tooling.run_checked(arcs_cmd, log_path=arcs_log)
        manifest["circt_opt"] = str(circt_opt)
        manifest["stages"]["arcs"] = {
            "cmd": arcs_cmd,
            "log": str(arcs_log),
            "output": str(arcs_mlir_path),
        }
        if args.stop_after == "arcs":
            _write_manifest(manifest_path, manifest)
            print(f"wrote {imported_mlir_path}")
            print(f"wrote {import_log}")
            if args.import_mode == "ir-moore":
                print(f"wrote {lowering_input_path}")
                print(f"wrote {out_dir / 'circt_verilog.core.log'}")
            if args.import_mode == "full":
                print(f"wrote {out_dir / 'circt_verilog.pre_arc.log'}")
                print(f"wrote {out_dir / 'circt_verilog.pre_arc.mlir'}")
                print(f"wrote {lowering_input_path}")
                print(f"wrote {out_dir / 'circt_verilog.pre_arc_bridge.log'}")
            print(f"wrote {arc_preflight_path}")
            print(f"wrote {arcs_mlir_path}")
            print(f"wrote {arcs_log}")
            print(f"wrote {manifest_path}")
            return 0

        arc_llvm_mlir_path = out_dir / "circt_direct.arc_llvm.mlir"
        arc_llvm_log = out_dir / "circt_direct.arc_llvm.log"
        arc_llvm_cmd = [
            str(circt_opt),
            str(arcs_mlir_path),
            "--hw-flatten-modules",
            "--cse",
            "--arc-canonicalizer",
            "--arc-split-loops",
            "--arc-infer-state-properties",
            "--cse",
            "--arc-canonicalizer",
            "--arc-lower-state",
            "--arc-inline",
            "--arc-merge-ifs",
            "--cse",
            "--arc-canonicalizer",
            "--arc-lower-arcs-to-funcs",
            "--arc-allocate-state",
            "--arc-lower-clocks-to-funcs",
            "--cse",
            "--arc-canonicalizer",
            "--lower-arc-to-llvm",
            "-o",
            str(arc_llvm_mlir_path),
        ]
        circt_tooling.run_checked(arc_llvm_cmd, log_path=arc_llvm_log)
        manifest["stages"]["llvm_dialect"] = {
            "cmd": arc_llvm_cmd,
            "log": str(arc_llvm_log),
            "output": str(arc_llvm_mlir_path),
        }
        if args.stop_after == "llvm-dialect":
            _write_manifest(manifest_path, manifest)
            print(f"wrote {imported_mlir_path}")
            print(f"wrote {import_log}")
            if args.import_mode == "ir-moore":
                print(f"wrote {lowering_input_path}")
                print(f"wrote {out_dir / 'circt_verilog.core.log'}")
            if args.import_mode == "full":
                print(f"wrote {out_dir / 'circt_verilog.pre_arc.log'}")
                print(f"wrote {out_dir / 'circt_verilog.pre_arc.mlir'}")
                print(f"wrote {lowering_input_path}")
                print(f"wrote {out_dir / 'circt_verilog.pre_arc_bridge.log'}")
            print(f"wrote {arc_preflight_path}")
            print(f"wrote {arcs_mlir_path}")
            print(f"wrote {arcs_log}")
            print(f"wrote {arc_llvm_mlir_path}")
            print(f"wrote {arc_llvm_log}")
            print(f"wrote {manifest_path}")
            return 0

        arc_llvm_reconciled_path = out_dir / "circt_direct.arc_llvm.reconciled.mlir"
        arc_llvm_reconciled_log = out_dir / "circt_direct.arc_llvm.reconciled.log"
        arc_llvm_reconciled_cmd = [
            str(circt_opt),
            str(arc_llvm_mlir_path),
            "--reconcile-unrealized-casts",
            "-o",
            str(arc_llvm_reconciled_path),
        ]
        circt_tooling.run_checked(
            arc_llvm_reconciled_cmd, log_path=arc_llvm_reconciled_log
        )
        manifest["stages"]["llvm_dialect_reconciled"] = {
            "cmd": arc_llvm_reconciled_cmd,
            "log": str(arc_llvm_reconciled_log),
            "input": str(arc_llvm_mlir_path),
            "output": str(arc_llvm_reconciled_path),
        }

        llvm_ir_path = out_dir / "circt_direct.ll"
        llvm_ir_log = out_dir / "circt_direct.llvm_translate.log"
        llvm_ir_cmd = [
            str(mlir_translate),
            "--mlir-to-llvmir",
            str(arc_llvm_reconciled_path),
            "-o",
            str(llvm_ir_path),
        ]
        circt_tooling.run_checked(llvm_ir_cmd, log_path=llvm_ir_log)
        manifest["mlir_translate"] = str(mlir_translate)
        manifest["stages"]["llvm_ir"] = {
            "cmd": llvm_ir_cmd,
            "log": str(llvm_ir_log),
            "output": str(llvm_ir_path),
        }
        if args.stop_after == "llvm-ir":
            _write_manifest(manifest_path, manifest)
            print(f"wrote {imported_mlir_path}")
            print(f"wrote {import_log}")
            if args.import_mode == "ir-moore":
                print(f"wrote {lowering_input_path}")
                print(f"wrote {out_dir / 'circt_verilog.core.log'}")
            if args.import_mode == "full":
                print(f"wrote {out_dir / 'circt_verilog.pre_arc.log'}")
                print(f"wrote {out_dir / 'circt_verilog.pre_arc.mlir'}")
                print(f"wrote {lowering_input_path}")
                print(f"wrote {out_dir / 'circt_verilog.pre_arc_bridge.log'}")
            print(f"wrote {arc_preflight_path}")
            print(f"wrote {arcs_mlir_path}")
            print(f"wrote {arcs_log}")
            print(f"wrote {arc_llvm_mlir_path}")
            print(f"wrote {arc_llvm_log}")
            print(f"wrote {arc_llvm_reconciled_path}")
            print(f"wrote {arc_llvm_reconciled_log}")
            print(f"wrote {llvm_ir_path}")
            print(f"wrote {llvm_ir_log}")
            print(f"wrote {manifest_path}")
            return 0

        ptx_path = out_dir / "circt_direct.ptx"
        ptx_log = out_dir / "circt_direct.ptx.log"
        ptx_cmd = _emit_ptx(
            llvm_ir_path,
            ptx_path,
            clang_path=args.clang_path,
            cuda_arch=args.cuda_arch,
            log_path=ptx_log,
        )
        manifest["stages"]["ptx"] = {
            "cmd": ptx_cmd,
            "log": str(ptx_log),
            "output": str(ptx_path),
        }
        _write_manifest(manifest_path, manifest)
        print(f"wrote {imported_mlir_path}")
        print(f"wrote {import_log}")
        if args.import_mode == "ir-moore":
            print(f"wrote {lowering_input_path}")
            print(f"wrote {out_dir / 'circt_verilog.core.log'}")
        if args.import_mode == "full":
            print(f"wrote {out_dir / 'circt_verilog.pre_arc.log'}")
            print(f"wrote {out_dir / 'circt_verilog.pre_arc.mlir'}")
            print(f"wrote {lowering_input_path}")
            print(f"wrote {out_dir / 'circt_verilog.pre_arc_bridge.log'}")
        print(f"wrote {arc_preflight_path}")
        print(f"wrote {arcs_mlir_path}")
        print(f"wrote {arcs_log}")
        print(f"wrote {arc_llvm_mlir_path}")
        print(f"wrote {arc_llvm_log}")
        print(f"wrote {arc_llvm_reconciled_path}")
        print(f"wrote {arc_llvm_reconciled_log}")
        print(f"wrote {llvm_ir_path}")
        print(f"wrote {llvm_ir_log}")
        print(f"wrote {ptx_path}")
        print(f"wrote {ptx_log}")
        print(f"wrote {manifest_path}")
        return 0
    except RuntimeError as exc:
        manifest["error"] = str(exc)
        _write_manifest(manifest_path, manifest)
        print(str(exc), file=sys.stderr)
        print(f"wrote {manifest_path}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        manifest["error"] = f"Command failed with exit code {exc.returncode}: {' '.join(exc.cmd)}"
        _write_manifest(manifest_path, manifest)
        print(manifest["error"], file=sys.stderr)
        print(f"wrote {manifest_path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
