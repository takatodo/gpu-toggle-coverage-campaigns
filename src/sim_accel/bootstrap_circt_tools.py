#!/usr/bin/env python3
"""Bootstrap a local CIRCT toolchain under opt/gpu/cuda/third_party."""

from __future__ import annotations

import argparse
from pathlib import Path

import circt_tooling


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install local cmake/ninja, initialize the CIRCT llvm submodule, "
            "and build CIRCT tools under opt/gpu/cuda."
        )
    )
    parser.add_argument(
        "--prefix",
        type=Path,
        default=circt_tooling.DEFAULT_PYTOOLS_PREFIX,
        help=f"Local pip prefix for cmake/ninja (default: {circt_tooling.DEFAULT_PYTOOLS_PREFIX})",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=circt_tooling.DEFAULT_CIRCT_BUILD_DIR,
        help=f"CIRCT build directory (default: {circt_tooling.DEFAULT_CIRCT_BUILD_DIR})",
    )
    parser.add_argument(
        "--build-type",
        default="Release",
        help="CMake build type passed to CIRCT/LLVM (default: Release)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=None,
        help="Optional parallel job count passed to cmake --build --parallel",
    )
    parser.add_argument(
        "--force-configure",
        action="store_true",
        help="Re-run CMake configure even when CMakeCache.txt already exists",
    )
    parser.add_argument(
        "--enable-slang-frontend",
        action="store_true",
        help="Configure CIRCT with CIRCT_SLANG_FRONTEND_ENABLED=ON and build circt-verilog",
    )
    parser.add_argument(
        "--c-compiler",
        default=None,
        help="Optional C compiler override",
    )
    parser.add_argument(
        "--cxx-compiler",
        default=None,
        help="Optional C++ compiler override",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build_dir = args.build_dir.resolve()
    manifest = circt_tooling.bootstrap_circt_tools(
        prefix=args.prefix,
        build_dir=build_dir,
        build_type=args.build_type,
        jobs=args.jobs,
        force_configure=args.force_configure,
        enable_slang_frontend=args.enable_slang_frontend,
        c_compiler=args.c_compiler,
        cxx_compiler=args.cxx_compiler,
        configure_log=build_dir / "configure.log",
        build_log=build_dir / "build.log",
    )
    print(f"wrote {build_dir / 'simaccel_circt_toolchain.json'}")
    print(f"configured {manifest['build_dir']}")
    print(f"circt-opt {manifest['circt_opt']}")
    print(f"mlir-opt {manifest['mlir_opt']}")
    if manifest.get("circt_verilog"):
        print(f"circt-verilog {manifest['circt_verilog']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
