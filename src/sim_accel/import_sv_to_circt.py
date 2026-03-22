#!/usr/bin/env python3
"""Run CIRCT's SystemVerilog frontend and capture import artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import circt_tooling


MODE_TO_FLAG = {
    "preprocess": "--E",
    "lint-only": "--lint-only",
    "parse-only": "--parse-only",
    "ir-moore": "--ir-moore",
    "ir-llhd": "--ir-llhd",
    "ir-hw": "--ir-hw",
    "full": None,
}

MODE_TO_BASENAME = {
    "preprocess": "circt_verilog.preprocessed.sv",
    "lint-only": "circt_verilog.lint.txt",
    "parse-only": "circt_verilog.parse.txt",
    "ir-moore": "circt_verilog.moore.mlir",
    "ir-llhd": "circt_verilog.llhd.mlir",
    "ir-hw": "circt_verilog.hw.mlir",
    "full": "circt_verilog.full.mlir",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Import SystemVerilog into CIRCT using circt-verilog and capture the "
            "result under a dedicated output directory."
        )
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for imported MLIR/log/manifest artifacts",
    )
    parser.add_argument(
        "--mode",
        choices=tuple(MODE_TO_FLAG),
        default="ir-moore",
        help="circt-verilog lowering mode (default: ir-moore)",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=circt_tooling.DEFAULT_CIRCT_BUILD_DIR,
        help=f"CIRCT build directory used for default tool resolution (default: {circt_tooling.DEFAULT_CIRCT_BUILD_DIR})",
    )
    parser.add_argument(
        "--circt-verilog-path",
        default=None,
        help="Explicit circt-verilog executable path",
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
        "--output-name",
        default=None,
        help="Override the default output artifact name",
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


def main() -> int:
    args = parse_args()
    circt_verilog = circt_tooling.resolve_executable(
        args.circt_verilog_path,
        circt_tooling.default_circt_verilog_path(args.build_dir),
        ["circt-verilog"],
    )
    if circt_verilog is None:
        raise RuntimeError(
            "circt-verilog not found. Re-run bootstrap_circt_tools.py with "
            "--enable-slang-frontend, or pass --circt-verilog-path."
        )

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    output_name = args.output_name or MODE_TO_BASENAME[args.mode]
    output_path = out_dir / output_name
    log_path = out_dir / "circt_verilog.log"
    manifest_path = out_dir / "circt_verilog_manifest.json"

    cmd = [str(circt_verilog)]
    mode_flag = MODE_TO_FLAG[args.mode]
    if mode_flag:
        cmd.append(mode_flag)
    cmd.extend(["-o", str(output_path)])
    for top in args.top_module:
        cmd.extend(["--top", top])
    for include_dir in args.include_dir:
        cmd.append(f"-I{include_dir}")
    for include_dir in args.isystem:
        cmd.extend(["--isystem", include_dir])
    for libdir in args.libdir:
        cmd.append(f"-y{libdir}")
    for libext in args.libext:
        cmd.append(f"-Y{libext}")
    for define in args.define:
        cmd.append(f"-D{define}")
    for undefine in args.undefine:
        cmd.append(f"-U{undefine}")
    for command_file in args.command_file:
        cmd.append(f"-C{command_file}")
    if args.single_unit:
        cmd.append("--single-unit")
    if args.ignore_unknown_modules:
        cmd.append("--ignore-unknown-modules")
    if args.allow_use_before_declare:
        cmd.append("--allow-use-before-declare")
    cmd.extend(args.sources)

    circt_tooling.run_checked(cmd, log_path=log_path)
    manifest = {
        "circt_verilog": str(circt_verilog),
        "build_dir": str(args.build_dir.resolve()),
        "mode": args.mode,
        "sources": [str(Path(source).resolve()) for source in args.sources],
        "command_files": [str(Path(path).resolve()) for path in args.command_file],
        "top_modules": list(args.top_module),
        "output": str(output_path),
        "log": str(log_path),
        "cmd": cmd,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output_path}")
    print(f"wrote {log_path}")
    print(f"wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
