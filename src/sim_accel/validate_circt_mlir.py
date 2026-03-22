#!/usr/bin/env python3
"""Validate CIRCT-inspired MLIR with a local or PATH circt-opt."""

from __future__ import annotations

import argparse
from pathlib import Path

import circt_tooling


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run circt-opt over kernel_generated.full_all.circt.mlir and write "
            "a normalized validated MLIR plus a validation log."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input .circt.mlir file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional validated output path (default: <input>.validated.mlir)",
    )
    parser.add_argument(
        "--circt-opt-path",
        default=None,
        help="Explicit circt-opt executable path",
    )
    parser.add_argument(
        "--circt-build-dir",
        type=Path,
        default=circt_tooling.DEFAULT_CIRCT_BUILD_DIR,
        help=f"Fallback CIRCT build dir (default: {circt_tooling.DEFAULT_CIRCT_BUILD_DIR})",
    )
    parser.add_argument(
        "--pipeline",
        default="canonicalize,cse",
        help="Comma-separated circt-opt passes (default: canonicalize,cse)",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Optional validation log path (default: <input>.validate.log)",
    )
    parser.add_argument(
        "--disallow-unregistered",
        action="store_true",
        help="Fail instead of adding --allow-unregistered-dialect for simaccel.* ops",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve() if args.output is not None else input_path.with_suffix(
        ".validated.mlir"
    )
    log_path = args.log.resolve() if args.log is not None else input_path.with_suffix(
        ".validate.log"
    )
    passes = [part.strip() for part in args.pipeline.split(",") if part.strip()]
    summary = circt_tooling.validate_circt_mlir(
        input_path,
        circt_opt_path=args.circt_opt_path,
        build_dir=args.circt_build_dir,
        output_path=output_path,
        pipeline=passes,
        allow_unregistered=not args.disallow_unregistered,
        log_path=log_path,
    )
    print(f"validated {summary['output']}")
    print(f"log {summary['log']}")
    print(f"circt-opt {summary['circt_opt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
