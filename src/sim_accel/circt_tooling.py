#!/usr/bin/env python3
"""Helpers for bootstrapping and validating a local CIRCT toolchain."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


CUDA_OPT_DIR = Path(__file__).resolve().parent
THIRD_PARTY_DIR = CUDA_OPT_DIR / "third_party"
CIRCT_DIR = THIRD_PARTY_DIR / "circt"
DEFAULT_PYTOOLS_PREFIX = THIRD_PARTY_DIR / ".local-pytools"
DEFAULT_CIRCT_BUILD_DIR = CIRCT_DIR / "build-simaccel"


def _shell_join(parts: list[str]) -> str:
    return " ".join(subprocess.list2cmdline([part]) for part in parts)


def run_checked(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    log_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    if log_path is None:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd is not None else None,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    else:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as log_file:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd) if cwd is not None else None,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            assert proc.stdout is not None
            output_chunks: list[str] = []
            for chunk in proc.stdout:
                log_file.write(chunk)
                log_file.flush()
                output_chunks.append(chunk)
            returncode = proc.wait()
            proc = subprocess.CompletedProcess(
                cmd,
                returncode,
                "".join(output_chunks),
                None,
            )
    if proc.returncode != 0:
        detail = f"Command failed with exit code {proc.returncode}: {_shell_join(cmd)}"
        if log_path is not None:
            detail += f"\nSee log: {log_path}"
        raise RuntimeError(detail)
    return proc


def ensure_python_build_tools(
    *,
    prefix: Path = DEFAULT_PYTOOLS_PREFIX,
    python_exe: str = sys.executable,
) -> dict[str, Path]:
    prefix = prefix.resolve()
    python_paths = sorted(
        path
        for pattern in ("local/lib/python*/dist-packages", "local/lib/python*/site-packages")
        for path in prefix.glob(pattern)
        if path.is_dir()
    )
    candidate_bin_dirs = [prefix / "bin", prefix / "local" / "bin"]
    bin_dir = next(
        (candidate for candidate in candidate_bin_dirs if (candidate / "cmake").exists() and (candidate / "ninja").exists()),
        candidate_bin_dirs[0],
    )
    cmake_path = bin_dir / "cmake"
    ninja_path = bin_dir / "ninja"
    if cmake_path.exists() and ninja_path.exists():
        return {
            "prefix": prefix,
            "bin_dir": bin_dir,
            "cmake": cmake_path,
            "ninja": ninja_path,
            "python_paths": python_paths,
        }
    run_checked(
        [
            python_exe,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            "--upgrade",
            "--prefix",
            str(prefix),
            "cmake",
            "ninja",
        ]
    )
    for candidate in candidate_bin_dirs:
        if (candidate / "cmake").exists() and (candidate / "ninja").exists():
            bin_dir = candidate
            cmake_path = candidate / "cmake"
            ninja_path = candidate / "ninja"
            break
    if not cmake_path.exists() or not ninja_path.exists():
        raise RuntimeError(
            f"Failed to install cmake/ninja under {prefix}; expected {cmake_path} and {ninja_path}"
        )
    python_paths = sorted(
        path
        for pattern in ("local/lib/python*/dist-packages", "local/lib/python*/site-packages")
        for path in prefix.glob(pattern)
        if path.is_dir()
    )
    return {
        "prefix": prefix,
        "bin_dir": bin_dir,
        "cmake": cmake_path,
        "ninja": ninja_path,
        "python_paths": python_paths,
    }


def ensure_circt_llvm_submodule(circt_dir: Path = CIRCT_DIR) -> Path:
    circt_dir = circt_dir.resolve()
    llvm_root = circt_dir / "llvm"
    llvm_source = llvm_root / "llvm"
    if llvm_source.exists():
        return llvm_source
    run_checked(
        ["git", "submodule", "update", "--init", "--depth", "1", "llvm"],
        cwd=circt_dir,
    )
    if not llvm_source.exists():
        raise RuntimeError(f"CIRCT llvm submodule did not materialize: {llvm_source}")
    return llvm_source


def default_circt_opt_path(build_dir: Path = DEFAULT_CIRCT_BUILD_DIR) -> Path:
    return build_dir.resolve() / "bin" / "circt-opt"


def default_mlir_opt_path(build_dir: Path = DEFAULT_CIRCT_BUILD_DIR) -> Path:
    return build_dir.resolve() / "bin" / "mlir-opt"


def default_mlir_translate_path(build_dir: Path = DEFAULT_CIRCT_BUILD_DIR) -> Path:
    return build_dir.resolve() / "bin" / "mlir-translate"


def default_circt_verilog_path(build_dir: Path = DEFAULT_CIRCT_BUILD_DIR) -> Path:
    return build_dir.resolve() / "bin" / "circt-verilog"


def resolve_executable(explicit: str | None, fallback: Path | None, names: list[str]) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists():
            return path.resolve()
    if fallback is not None and fallback.exists():
        return fallback.resolve()
    for name in names:
        found = shutil.which(name)
        if found is not None:
            return Path(found).resolve()
    return None


def _read_cmake_cache_bool(build_dir: Path, key: str) -> bool | None:
    cache_path = build_dir / "CMakeCache.txt"
    if not cache_path.exists():
        return None
    needle = f"{key}:BOOL="
    for line in cache_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(needle):
            continue
        value = line[len(needle) :].strip().upper()
        if value == "ON":
            return True
        if value == "OFF":
            return False
    return None


def bootstrap_circt_tools(
    *,
    prefix: Path = DEFAULT_PYTOOLS_PREFIX,
    build_dir: Path = DEFAULT_CIRCT_BUILD_DIR,
    build_type: str = "Release",
    jobs: int | None = None,
    force_configure: bool = False,
    enable_slang_frontend: bool = False,
    c_compiler: str | None = None,
    cxx_compiler: str | None = None,
    configure_log: Path | None = None,
    build_log: Path | None = None,
) -> dict[str, str]:
    tools = ensure_python_build_tools(prefix=prefix)
    llvm_source = ensure_circt_llvm_submodule(CIRCT_DIR)
    build_dir = build_dir.resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PATH"] = str(tools["bin_dir"]) + os.pathsep + env.get("PATH", "")
    if tools["python_paths"]:
        env["PYTHONPATH"] = os.pathsep.join(str(path) for path in tools["python_paths"]) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )

    cmake_cache = build_dir / "CMakeCache.txt"
    cached_slang_frontend = _read_cmake_cache_bool(build_dir, "CIRCT_SLANG_FRONTEND_ENABLED")
    need_configure = (
        force_configure
        or not cmake_cache.exists()
        or (enable_slang_frontend and cached_slang_frontend is not True)
    )
    if need_configure:
        configure_cmd = [
            str(tools["cmake"]),
            "-G",
            "Ninja",
            str(llvm_source),
            "-B",
            str(build_dir),
            f"-DCMAKE_BUILD_TYPE={build_type}",
            "-DLLVM_TARGETS_TO_BUILD=host",
            "-DLLVM_ENABLE_PROJECTS=mlir",
            "-DLLVM_EXTERNAL_PROJECTS=circt",
            f"-DLLVM_EXTERNAL_CIRCT_SOURCE_DIR={CIRCT_DIR}",
            "-DLLVM_ENABLE_ASSERTIONS=ON",
            "-DLLVM_INCLUDE_TESTS=OFF",
            "-DLLVM_INCLUDE_EXAMPLES=OFF",
            "-DLLVM_BUILD_EXAMPLES=OFF",
            "-DLLVM_ENABLE_BINDINGS=OFF",
            "-DLLVM_ENABLE_TERMINFO=OFF",
        ]
        if enable_slang_frontend:
            configure_cmd.append("-DCIRCT_SLANG_FRONTEND_ENABLED=ON")
        if c_compiler:
            configure_cmd.append(f"-DCMAKE_C_COMPILER={c_compiler}")
        if cxx_compiler:
            configure_cmd.append(f"-DCMAKE_CXX_COMPILER={cxx_compiler}")
        run_checked(configure_cmd, cwd=CIRCT_DIR, env=env, log_path=configure_log)

    build_cmd = [
        str(tools["cmake"]),
        "--build",
        str(build_dir),
        "--target",
        "mlir-opt",
        "circt-opt",
        "mlir-translate",
    ]
    if enable_slang_frontend:
        build_cmd.append("circt-verilog")
    if jobs is not None and jobs > 0:
        build_cmd.extend(["--parallel", str(jobs)])
    run_checked(build_cmd, cwd=CIRCT_DIR, env=env, log_path=build_log)

    circt_verilog = default_circt_verilog_path(build_dir)
    manifest = {
        "circt_dir": str(CIRCT_DIR.resolve()),
        "llvm_source": str(llvm_source.resolve()),
        "build_dir": str(build_dir),
        "cmake": str(Path(tools["cmake"]).resolve()),
        "ninja": str(Path(tools["ninja"]).resolve()),
        "circt_opt": str(default_circt_opt_path(build_dir)),
        "mlir_opt": str(default_mlir_opt_path(build_dir)),
        "mlir_translate": str(default_mlir_translate_path(build_dir)),
        "circt_verilog": str(circt_verilog) if circt_verilog.exists() else None,
        "build_type": build_type,
        "slang_frontend_enabled": bool(enable_slang_frontend or cached_slang_frontend),
    }
    (build_dir / "simaccel_circt_toolchain.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def validate_circt_mlir(
    input_path: Path,
    *,
    circt_opt_path: str | None = None,
    build_dir: Path = DEFAULT_CIRCT_BUILD_DIR,
    output_path: Path | None = None,
    pipeline: list[str] | None = None,
    allow_unregistered: bool = True,
    log_path: Path | None = None,
) -> dict[str, object]:
    input_path = input_path.resolve()
    if output_path is None:
        output_path = input_path.with_suffix(".validated.mlir")
    circt_opt = resolve_executable(
        circt_opt_path,
        default_circt_opt_path(build_dir),
        ["circt-opt"],
    )
    if circt_opt is None:
        raise RuntimeError(
            "circt-opt not found. Run bootstrap_circt_tools.py first or pass --circt-opt-path."
        )

    text = input_path.read_text(encoding="utf-8")
    has_simaccel_ops = '"simaccel.' in text
    passes = pipeline or ["canonicalize", "cse"]
    cmd = [str(circt_opt), str(input_path), "-o", str(output_path)]
    if has_simaccel_ops and allow_unregistered:
        cmd.append("--allow-unregistered-dialect")
    for pass_name in passes:
        cmd.append(f"--{pass_name}")
    run_checked(cmd, log_path=log_path)
    return {
        "input": str(input_path),
        "output": str(output_path.resolve()),
        "log": str(log_path.resolve()) if log_path is not None else None,
        "circt_opt": str(circt_opt),
        "passes": passes,
        "has_simaccel_ops": has_simaccel_ops,
        "allow_unregistered": has_simaccel_ops and allow_unregistered,
    }


def translate_llvm_dialect_to_llvm_ir(
    input_path: Path,
    *,
    mlir_translate_path: str | None = None,
    build_dir: Path = DEFAULT_CIRCT_BUILD_DIR,
    output_path: Path | None = None,
    log_path: Path | None = None,
) -> dict[str, object]:
    input_path = input_path.resolve()
    if output_path is None:
        output_path = input_path.with_suffix(".ll")
    mlir_translate = resolve_executable(
        mlir_translate_path,
        default_mlir_translate_path(build_dir),
        ["mlir-translate"],
    )
    if mlir_translate is None:
        raise RuntimeError(
            "mlir-translate not found. Re-run bootstrap_circt_tools.py or pass --mlir-translate-path."
        )
    cmd = [
        str(mlir_translate),
        "--mlir-to-llvmir",
        str(input_path),
    ]
    proc = run_checked(cmd, log_path=log_path)
    output_path.write_text(proc.stdout, encoding="utf-8")
    return {
        "input": str(input_path),
        "output": str(output_path.resolve()),
        "log": str(log_path.resolve()) if log_path is not None else None,
        "mlir_translate": str(mlir_translate),
    }
