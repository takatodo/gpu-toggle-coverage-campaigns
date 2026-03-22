#!/usr/bin/env python3
"""Run a direct-LLVM probe from a flattened hw.module with explicit feedback cuts.

This is a bounded debugging/probing path for cases where the aggregate-lowered
single-module checkpoint still contains an internal SCC that blocks the direct
LLVM branch. It applies one or more selected feedback cuts, rewrites the
resulting `hw.module` into `func.func`, lowers through the existing CIRCT
`HW -> LLVM` bridge, reconciles unrealized casts, and optionally emits PTX.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import circt_tooling
import cut_hw_module_feedback_edge
import hw_module_to_func
import sv_to_circt_ptx


CUDA_OPT_DIR = Path(__file__).resolve().parent
ANALYZE_MLIR_GRAPH_SCC = CUDA_OPT_DIR / "analyze_mlir_graph_scc.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Aggregate-lowered hw.module MLIR")
    parser.add_argument("--out-dir", type=Path, required=True, help="Probe output directory")
    parser.add_argument(
        "--cut-spec",
        type=Path,
        required=True,
        help=(
            "JSON spec describing the selected feedback cuts. "
            "Either {'cuts': [...]} or a single cut object."
        ),
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=circt_tooling.DEFAULT_CIRCT_BUILD_DIR,
        help="CIRCT build directory used for default tool resolution",
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
        help="clang executable used for optional PTX emission",
    )
    parser.add_argument(
        "--cuda-arch",
        default=None,
        help="Optional CUDA GPU arch, for example sm_80",
    )
    parser.add_argument(
        "--stop-after",
        choices=("cut", "func", "llvm-dialect", "llvm-ir", "ptx"),
        default="llvm-ir",
        help="Stop after the named stage (default: llvm-ir)",
    )
    return parser.parse_args()


def _resolve_required_tool(
    explicit: str | None,
    fallback: Path | None,
    names: list[str],
    label: str,
) -> Path:
    path = circt_tooling.resolve_executable(explicit, fallback, names)
    if path is not None:
        return path
    raise RuntimeError(f"Could not find {label}.")


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _normalize_cut_spec(raw: object) -> list[dict[str, object]]:
    if isinstance(raw, dict) and "cuts" in raw:
        cuts = raw["cuts"]
    else:
        cuts = [raw]
    if not isinstance(cuts, list) or not cuts:
        raise ValueError("Cut spec must contain at least one cut")
    normalized: list[dict[str, object]] = []
    for idx, cut in enumerate(cuts):
        if not isinstance(cut, dict):
            raise ValueError(f"Cut #{idx} must be an object")
        source_value = str(cut["source_value"]).strip()
        replace_in_ops = cut["replace_in_ops"]
        if not isinstance(replace_in_ops, list) or not replace_in_ops:
            raise ValueError(f"Cut #{idx} must contain non-empty replace_in_ops")
        new_input_name = cut.get("new_input_name")
        normalized.append(
            {
                "source_value": source_value,
                "replace_in_ops": [str(item).strip() for item in replace_in_ops],
                "new_input_name": None if new_input_name is None else str(new_input_name).strip(),
            }
        )
    return normalized


def _run_scc(input_path: Path, output_path: Path, log_path: Path) -> dict[str, object]:
    cmd = [
        sys.executable,
        str(ANALYZE_MLIR_GRAPH_SCC),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]
    circt_tooling.run_checked(cmd, log_path=log_path)
    return json.loads(output_path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out_dir / "direct_feedback_probe_manifest.json"

    cut_spec_raw = json.loads(args.cut_spec.read_text(encoding="utf-8"))
    cuts = _normalize_cut_spec(cut_spec_raw)
    manifest: dict[str, object] = {
        "input": str(args.input.resolve()),
        "cut_spec": str(args.cut_spec.resolve()),
        "cuts": cuts,
        "build_dir": str(args.build_dir.resolve()),
        "stop_after": args.stop_after,
        "stages": {},
    }

    try:
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

        input_text = args.input.read_text(encoding="utf-8")
        cut_text = input_text
        for cut in cuts:
            cut_text = cut_hw_module_feedback_edge.rewrite(
                cut_text,
                source_value=str(cut["source_value"]),
                replace_in_ops=set(str(item) for item in cut["replace_in_ops"]),
                new_input_name=(
                    str(cut["new_input_name"])
                    if cut["new_input_name"] is not None
                    else str(cut["source_value"]) + "_cut"
                ),
            )

        cut_mlir_path = args.out_dir / "direct_feedback_cut.mlir"
        cut_mlir_path.write_text(cut_text, encoding="utf-8")
        cut_scc_path = args.out_dir / "direct_feedback_cut.scc.json"
        cut_scc_log = args.out_dir / "direct_feedback_cut.scc.log"
        cut_scc = _run_scc(cut_mlir_path, cut_scc_path, cut_scc_log)
        manifest["stages"]["cut"] = {
            "output": str(cut_mlir_path),
            "scc": str(cut_scc_path),
            "scc_summary": cut_scc,
        }
        if args.stop_after == "cut":
            _write_manifest(manifest_path, manifest)
            return 0

        func_mlir_path = args.out_dir / "direct_feedback_cut.func.mlir"
        func_mlir_path.write_text(hw_module_to_func.rewrite(cut_text), encoding="utf-8")
        manifest["stages"]["func"] = {
            "output": str(func_mlir_path),
        }
        if args.stop_after == "func":
            _write_manifest(manifest_path, manifest)
            return 0

        hwbitcast_mlir_path = args.out_dir / "direct_feedback_cut.hwbitcast.mlir"
        hwbitcast_log = args.out_dir / "direct_feedback_cut.hwbitcast.log"
        hwbitcast_cmd = [
            str(circt_opt),
            str(func_mlir_path),
            "--hw-convert-bitcasts=allow-partial-conversion=true",
            "-o",
            str(hwbitcast_mlir_path),
        ]
        circt_tooling.run_checked(hwbitcast_cmd, log_path=hwbitcast_log)

        llvm_dialect_path = args.out_dir / "direct_feedback_cut.llvm.mlir"
        llvm_dialect_log = args.out_dir / "direct_feedback_cut.llvm.log"
        llvm_dialect_cmd = [
            str(circt_opt),
            str(hwbitcast_mlir_path),
            "--convert-to-llvm",
            "-o",
            str(llvm_dialect_path),
        ]
        circt_tooling.run_checked(llvm_dialect_cmd, log_path=llvm_dialect_log)

        reconciled_path = args.out_dir / "direct_feedback_cut.llvm.reconciled.mlir"
        reconciled_log = args.out_dir / "direct_feedback_cut.llvm.reconciled.log"
        reconciled_cmd = [
            str(circt_opt),
            str(llvm_dialect_path),
            "--reconcile-unrealized-casts",
            "-o",
            str(reconciled_path),
        ]
        circt_tooling.run_checked(reconciled_cmd, log_path=reconciled_log)
        manifest["stages"]["llvm_dialect"] = {
            "hwbitcast_cmd": hwbitcast_cmd,
            "hwbitcast_log": str(hwbitcast_log),
            "hwbitcast_output": str(hwbitcast_mlir_path),
            "llvm_cmd": llvm_dialect_cmd,
            "llvm_log": str(llvm_dialect_log),
            "llvm_output": str(llvm_dialect_path),
            "reconciled_cmd": reconciled_cmd,
            "reconciled_log": str(reconciled_log),
            "reconciled_output": str(reconciled_path),
        }
        if args.stop_after == "llvm-dialect":
            _write_manifest(manifest_path, manifest)
            return 0

        llvm_ir_path = args.out_dir / "direct_feedback_cut.ll"
        llvm_ir_log = args.out_dir / "direct_feedback_cut.llvm_translate.log"
        llvm_ir_cmd = [
            str(mlir_translate),
            "--mlir-to-llvmir",
            str(reconciled_path),
            "-o",
            str(llvm_ir_path),
        ]
        circt_tooling.run_checked(llvm_ir_cmd, log_path=llvm_ir_log)
        manifest["stages"]["llvm_ir"] = {
            "cmd": llvm_ir_cmd,
            "log": str(llvm_ir_log),
            "output": str(llvm_ir_path),
        }
        if args.stop_after == "llvm-ir":
            _write_manifest(manifest_path, manifest)
            return 0

        ptx_path = args.out_dir / "direct_feedback_cut.ptx"
        ptx_log = args.out_dir / "direct_feedback_cut.ptx.log"
        ptx_cmd = sv_to_circt_ptx._emit_ptx(
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
        return 0
    except Exception as exc:  # Keep probe artifacts even on rewrite/parse failures.
        manifest["error"] = str(exc)
        _write_manifest(manifest_path, manifest)
        print(str(exc), file=sys.stderr)
        print(f"wrote {manifest_path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
