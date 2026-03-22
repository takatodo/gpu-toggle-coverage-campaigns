#!/usr/bin/env python3
"""Run the direct CIRCT frontend/PTX flow on an RTLMeter case descriptor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import rtlmeter_case_to_full_all


CUDA_OPT_DIR = Path(__file__).resolve().parent
SV_TO_CIRCT_PTX = CUDA_OPT_DIR / "sv_to_circt_ptx.py"
NORMALIZE_SV_INTERFACE_REFS = CUDA_OPT_DIR / "normalize_sv_interface_refs.py"
DEFAULT_RTLMETER_ROOT = rtlmeter_case_to_full_all.DEFAULT_RTLMETER_ROOT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve an RTLMeter case descriptor and forward its SystemVerilog "
            "sources, include dirs, defines, and top module into sv_to_circt_ptx.py."
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
        help="Output directory passed to sv_to_circt_ptx.py",
    )
    parser.add_argument(
        "--rtlmeter-root",
        type=Path,
        default=DEFAULT_RTLMETER_ROOT,
        help="Absolute path to the RTLMeter repository",
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
        default="import",
        help="Forwarded to sv_to_circt_ptx.py (default: import)",
    )
    parser.add_argument(
        "--import-mode",
        choices=("ir-hw", "ir-moore", "ir-llhd", "full"),
        default="ir-hw",
        help="Forwarded to sv_to_circt_ptx.py (default: ir-hw)",
    )
    parser.add_argument(
        "--async-resets-as-sync",
        action="store_true",
        help="Forwarded to sv_to_circt_ptx.py for --import-mode full",
    )
    parser.add_argument(
        "--auto-feedback-sweep-on-scc",
        action="store_true",
        help="Forwarded to sv_to_circt_ptx.py",
    )
    parser.add_argument(
        "--feedback-sweep-stop-after",
        choices=("cut", "func", "llvm-dialect", "llvm-ir", "ptx"),
        default="llvm-ir",
        help="Forwarded to sv_to_circt_ptx.py (default: llvm-ir)",
    )
    parser.add_argument(
        "--feedback-sweep-limit",
        type=int,
        default=0,
        help="Forwarded to sv_to_circt_ptx.py (default: all cycle edges)",
    )
    parser.add_argument(
        "--auto-feedback-probe-on-scc",
        action="store_true",
        help="Forwarded to sv_to_circt_ptx.py",
    )
    parser.add_argument(
        "--feedback-probe-stop-after",
        choices=("cut", "func", "llvm-dialect", "llvm-ir", "ptx"),
        default="llvm-ir",
        help="Forwarded to sv_to_circt_ptx.py (default: llvm-ir)",
    )
    parser.add_argument(
        "--single-unit",
        dest="single_unit",
        action="store_true",
        default=True,
        help="Force circt-verilog --single-unit across the case source list (default: on)",
    )
    parser.add_argument(
        "--no-single-unit",
        dest="single_unit",
        action="store_false",
        help="Disable circt-verilog --single-unit",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=CUDA_OPT_DIR / "third_party" / "circt" / "build-simaccel",
        help="Forwarded to sv_to_circt_ptx.py",
    )
    parser.add_argument(
        "--circt-verilog-path",
        default=None,
        help="Forwarded to sv_to_circt_ptx.py",
    )
    parser.add_argument(
        "--circt-opt-path",
        default=None,
        help="Forwarded to sv_to_circt_ptx.py",
    )
    parser.add_argument(
        "--mlir-translate-path",
        default=None,
        help="Forwarded to sv_to_circt_ptx.py",
    )
    parser.add_argument(
        "--clang-path",
        default="clang",
        help="Forwarded to sv_to_circt_ptx.py",
    )
    parser.add_argument(
        "--cuda-arch",
        default="sm_80",
        help="Forwarded to sv_to_circt_ptx.py (default: sm_80)",
    )
    parser.add_argument(
        "--extra-define",
        action="append",
        default=[],
        help="Additional macro definition appended after descriptor-derived defines",
    )
    parser.add_argument(
        "--extra-include-dir",
        action="append",
        default=[],
        help="Additional include directory appended after descriptor-derived directories",
    )
    parser.add_argument(
        "--normalize-interface-manifest",
        action="append",
        default=[],
        help=(
            "Optional interface manifest JSON produced by extract_sv_interface_manifest.py. "
            "Each manifest is applied in sequence before running sv_to_circt_ptx.py."
        ),
    )
    parser.add_argument(
        "--top-module-override",
        default=None,
        help="Override the RTLMeter case top module passed to sv_to_circt_ptx.py",
    )
    parser.add_argument(
        "--exclude-source-basename",
        action="append",
        default=[],
        help="Drop any source file whose basename matches one of these values before invoking CIRCT",
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


def _remap_include_dirs(include_dirs: list[str], *, source_root: Path, normalized_root: Path) -> list[str]:
    remapped: list[str] = []
    for include_dir in include_dirs:
        include_path = Path(include_dir).resolve()
        try:
            rel = include_path.relative_to(source_root)
        except ValueError:
            remapped.append(str(include_path))
            continue
        remapped.append(str((normalized_root / rel).resolve()))
    return _unique_preserve_order(remapped + include_dirs)


def _sanitize_veer_tb_top_for_import(*, case_name: str, stage_dir: Path) -> None:
    if not case_name.startswith("VeeR-"):
        return
    tb_top = stage_dir / "designs" / case_name.split(":", 1)[0] / "src" / "tb_top.sv"
    if not tb_top.exists():
        return
    text = tb_top.read_text(encoding="utf-8")
    replacements = {
        "lmem.awvalid": "lmem_axi_awvalid",
        "lmem.awaddr": "mux_axi_awaddr",
        "lmem.wdata": "mux_axi_wdata",
    }
    updated = text
    for old, new in replacements.items():
        updated = updated.replace(old, new)
    if updated != text:
        tb_top.write_text(updated, encoding="utf-8")


def _sanitize_veer_core_for_import(*, case_name: str, stage_dir: Path) -> None:
    if not case_name.startswith("VeeR-"):
        return
    lsu_lsc = stage_dir / "designs" / case_name.split(":", 1)[0] / "src" / "el2_lsu_lsc_ctl.sv"
    if not lsu_lsc.exists():
        return
    text = lsu_lsc.read_text(encoding="utf-8")
    old = (
        "      rvdffe #($bits(el2_lsu_error_pkt_t)-2) lsu_error_pkt_rff       "
        "(.*, .din(lsu_error_pkt_m[$bits(el2_lsu_error_pkt_t)-1:2]), "
        ".dout(lsu_error_pkt_r[$bits(el2_lsu_error_pkt_t)-1:2]), "
        ".en(lsu_error_pkt_m.exc_valid | lsu_error_pkt_m.single_ecc_error | clk_override));"
    )
    new = "\n".join(
        [
            "      // CIRCT import workaround: avoid packed-struct bit slicing here.",
            "      rvdffs #(1)  lsu_error_pkt_rff_inst_type (.din(lsu_error_pkt_m.inst_type), .dout(lsu_error_pkt_r.inst_type), .en(lsu_error_pkt_m.exc_valid | lsu_error_pkt_m.single_ecc_error | clk_override), .clk(clk), .rst_l(rst_l));",
            "      rvdffs #(1)  lsu_error_pkt_rff_exc_type  (.din(lsu_error_pkt_m.exc_type),  .dout(lsu_error_pkt_r.exc_type),  .en(lsu_error_pkt_m.exc_valid | lsu_error_pkt_m.single_ecc_error | clk_override), .clk(clk), .rst_l(rst_l));",
            "      rvdffs #(4)  lsu_error_pkt_rff_mscause   (.din(lsu_error_pkt_m.mscause[3:0]), .dout(lsu_error_pkt_r.mscause[3:0]), .en(lsu_error_pkt_m.exc_valid | lsu_error_pkt_m.single_ecc_error | clk_override), .clk(clk), .rst_l(rst_l));",
            "      rvdffe #(32) lsu_error_pkt_rff_addr      (.din(lsu_error_pkt_m.addr[31:0]), .dout(lsu_error_pkt_r.addr[31:0]), .en(lsu_error_pkt_m.exc_valid | lsu_error_pkt_m.single_ecc_error | clk_override), .clk(clk), .rst_l(rst_l), .scan_mode(scan_mode));",
        ]
    )
    if old in text:
        text = text.replace(old, new)
    old_pkt = "\n".join(
        [
            "   rvdff #($bits(el2_lsu_pkt_t)-1) lsu_pkt_mff (.*, .din(lsu_pkt_m_in[$bits(el2_lsu_pkt_t)-1:1]), .dout(lsu_pkt_m[$bits(el2_lsu_pkt_t)-1:1]), .clk(lsu_c1_m_clk));",
            "   rvdff #($bits(el2_lsu_pkt_t)-1) lsu_pkt_rff (.*, .din(lsu_pkt_r_in[$bits(el2_lsu_pkt_t)-1:1]), .dout(lsu_pkt_r[$bits(el2_lsu_pkt_t)-1:1]), .clk(lsu_c1_r_clk));",
        ]
    )
    new_pkt = "\n".join(
        [
            "   // CIRCT import workaround: avoid packed-struct bit slicing here too.",
            "   rvdff #(13) lsu_pkt_mff (.din({lsu_pkt_m_in.fast_int, lsu_pkt_m_in.stack, lsu_pkt_m_in.by, lsu_pkt_m_in.half, lsu_pkt_m_in.word, lsu_pkt_m_in.dword, lsu_pkt_m_in.load, lsu_pkt_m_in.store, lsu_pkt_m_in.unsign, lsu_pkt_m_in.dma, lsu_pkt_m_in.store_data_bypass_d, lsu_pkt_m_in.load_ldst_bypass_d, lsu_pkt_m_in.store_data_bypass_m}), .dout({lsu_pkt_m.fast_int, lsu_pkt_m.stack, lsu_pkt_m.by, lsu_pkt_m.half, lsu_pkt_m.word, lsu_pkt_m.dword, lsu_pkt_m.load, lsu_pkt_m.store, lsu_pkt_m.unsign, lsu_pkt_m.dma, lsu_pkt_m.store_data_bypass_d, lsu_pkt_m.load_ldst_bypass_d, lsu_pkt_m.store_data_bypass_m}), .clk(lsu_c1_m_clk), .rst_l(rst_l));",
            "   rvdff #(13) lsu_pkt_rff (.din({lsu_pkt_r_in.fast_int, lsu_pkt_r_in.stack, lsu_pkt_r_in.by, lsu_pkt_r_in.half, lsu_pkt_r_in.word, lsu_pkt_r_in.dword, lsu_pkt_r_in.load, lsu_pkt_r_in.store, lsu_pkt_r_in.unsign, lsu_pkt_r_in.dma, lsu_pkt_r_in.store_data_bypass_d, lsu_pkt_r_in.load_ldst_bypass_d, lsu_pkt_r_in.store_data_bypass_m}), .dout({lsu_pkt_r.fast_int, lsu_pkt_r.stack, lsu_pkt_r.by, lsu_pkt_r.half, lsu_pkt_r.word, lsu_pkt_r.dword, lsu_pkt_r.load, lsu_pkt_r.store, lsu_pkt_r.unsign, lsu_pkt_r.dma, lsu_pkt_r.store_data_bypass_d, lsu_pkt_r.load_ldst_bypass_d, lsu_pkt_r.store_data_bypass_m}), .clk(lsu_c1_r_clk), .rst_l(rst_l));",
        ]
    )
    if old_pkt in text:
        text = text.replace(old_pkt, new_pkt)
    lsu_lsc.write_text(text, encoding="utf-8")


def _filter_sources_by_basename(sources: list[str], excluded_basenames: list[str]) -> list[str]:
    if not excluded_basenames:
        return sources
    excluded = set(excluded_basenames)
    return [source for source in sources if Path(source).name not in excluded]


def main() -> int:
    args = parse_args()
    rtlmeter_root = args.rtlmeter_root.resolve()
    compile_descr, execute_descr = rtlmeter_case_to_full_all._load_rtlmeter_case(args.case, rtlmeter_root)

    include_dirs = _unique_preserve_order(
        [str(Path(path).resolve().parent) for path in compile_descr.verilogIncludeFiles]
        + [str(Path(path).resolve()) for path in args.extra_include_dir]
    )
    defines = dict(sorted(compile_descr.verilogDefines.items()))
    for define in args.extra_define:
        if "=" in define:
            key, value = define.split("=", 1)
        else:
            key, value = define, "1"
        defines[str(key)] = str(value)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    top_module = args.top_module_override or compile_descr.topModule
    manifest = {
        "case": args.case,
        "compile_case": compile_descr.case,
        "design_dir": compile_descr.designDir,
        "top_module": top_module,
        "import_mode": args.import_mode,
        "async_resets_as_sync": args.async_resets_as_sync,
        "stop_after": args.stop_after,
        "single_unit": args.single_unit,
        "verilog_sources": list(compile_descr.verilogSourceFiles),
        "include_dirs": include_dirs,
        "defines": defines,
        "execute_args": list(execute_descr.args),
        "execute_files": list(execute_descr.files),
        "execute_tags": list(execute_descr.tags),
    }
    (args.out_dir / "rtlmeter_case_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    sources = [str(Path(path).resolve()) for path in compile_descr.verilogSourceFiles]
    sources = _filter_sources_by_basename(sources, args.exclude_source_basename)
    if args.normalize_interface_manifest:
        normalized_root = args.out_dir / "normalized_sources"
        current_sources = sources
        normalized_manifests: list[str] = []
        for idx, manifest_path in enumerate(args.normalize_interface_manifest):
            stage_dir = normalized_root / f"iface_{idx}"
            normalize_cmd = [
                sys.executable,
                str(NORMALIZE_SV_INTERFACE_REFS),
                "--interface-manifest",
                str(Path(manifest_path).resolve()),
                "--out-dir",
                str(stage_dir),
                *[
                    arg
                    for include_file in compile_descr.verilogIncludeFiles
                    for arg in ("--extra-file", str(Path(include_file).resolve()))
                ],
                *current_sources,
            ]
            subprocess.run(normalize_cmd, check=True)
            normalized_manifest = json.loads(
                (stage_dir / "normalized_interface_manifest.json").read_text(encoding="utf-8")
            )
            current_sources = (stage_dir / "normalized_sources.txt").read_text(encoding="utf-8").splitlines()
            include_dirs = _remap_include_dirs(
                include_dirs,
                source_root=Path(normalized_manifest["source_root"]).resolve(),
                normalized_root=stage_dir.resolve(),
            )
            _sanitize_veer_tb_top_for_import(case_name=args.case, stage_dir=stage_dir)
            _sanitize_veer_core_for_import(case_name=args.case, stage_dir=stage_dir)
            normalized_manifests.append(str((stage_dir / "normalized_interface_manifest.json").resolve()))
        sources = current_sources
        manifest["normalized_interface_manifests"] = normalized_manifests

    cmd = [
        sys.executable,
        str(SV_TO_CIRCT_PTX),
        "--out-dir",
        str(args.out_dir),
        "--build-dir",
        str(args.build_dir),
        "--stop-after",
        args.stop_after,
        "--import-mode",
        args.import_mode,
        "--clang-path",
        args.clang_path,
        "--cuda-arch",
        args.cuda_arch,
        "--top-module",
        top_module,
    ]
    if args.async_resets_as_sync:
        cmd.append("--async-resets-as-sync")
    if args.auto_feedback_sweep_on_scc:
        cmd.append("--auto-feedback-sweep-on-scc")
    cmd.extend(["--feedback-sweep-stop-after", args.feedback_sweep_stop_after])
    if args.feedback_sweep_limit > 0:
        cmd.extend(["--feedback-sweep-limit", str(args.feedback_sweep_limit)])
    if args.auto_feedback_probe_on_scc:
        cmd.append("--auto-feedback-probe-on-scc")
    cmd.extend(["--feedback-probe-stop-after", args.feedback_probe_stop_after])
    if args.single_unit:
        cmd.append("--single-unit")
    if args.circt_verilog_path:
        cmd.extend(["--circt-verilog-path", args.circt_verilog_path])
    if args.circt_opt_path:
        cmd.extend(["--circt-opt-path", args.circt_opt_path])
    if args.mlir_translate_path:
        cmd.extend(["--mlir-translate-path", args.mlir_translate_path])
    for include_dir in include_dirs:
        cmd.extend(["-I", include_dir])
    for key, value in defines.items():
        cmd.extend(["-D", f"{key}={value}"])
    cmd.extend(sources)

    (args.out_dir / "rtlmeter_case_command.sh").write_text(
        subprocess.list2cmdline(cmd) + "\n",
        encoding="utf-8",
    )
    proc = subprocess.run(cmd, check=False)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
