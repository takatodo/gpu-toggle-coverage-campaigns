#!/usr/bin/env python3
"""Build and optionally smoke-test a staged sim-accel bench bundle."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

BUNDLE_CONFIG_NAME = "sim_accel_bundle_config.json"
EXECUTION_BACKENDS = ("auto", "cuda_source", "cuda_circt_cubin", "cuda_clang_ir", "cuda_vl_ir", "program_json_ir", "rocm_llvm")
_GPU_BINARY_ENV_VAR = "SIM_ACCEL_GPU_BINARY_PATH"
DEFAULT_ROCM_HIPIFY_CACHE_ROOT = Path(
    os.getenv("SIM_ACCEL_ROCM_HIPIFY_CACHE_ROOT", "/tmp/sim_accel_rocm_hipify_cache")
)
DEFAULT_ROCM_HIPIFY_FILE_CACHE_ROOT = Path(
    os.getenv("SIM_ACCEL_ROCM_HIPIFY_FILE_CACHE_ROOT", "/tmp/sim_accel_rocm_hipify_file_cache")
)


def _default_gpu_binary_metadata(*, launch_backend: str, execution_backend: str) -> dict[str, object]:
    if execution_backend == "cuda_circt_cubin" or launch_backend == "circt-cubin":
        return {
            "gpu_binary_kind": "cubin",
            "gpu_binary_relpath": "kernel_generated.full_all.circt.cubin",
            "gpu_binary_env_var": "SIM_ACCEL_GPU_BINARY_PATH",
            "gpu_binary_legacy_env_var": "SIM_ACCEL_CIRCT_CUBIN_PATH",
            "gpu_binary_required": True,
        }
    if execution_backend == "rocm_llvm":
        return {
            "gpu_binary_kind": "hsaco",
            "gpu_binary_relpath": "kernel_generated.full_all.hsaco",
            "gpu_binary_env_var": "SIM_ACCEL_GPU_BINARY_PATH",
            "gpu_binary_required": True,
        }
    if execution_backend == "cuda_clang_ir":
        return {
            "gpu_binary_kind": "ptx",
            "gpu_binary_relpath": "kernel_generated.full_all.clang_ir.ptx",
            "gpu_binary_env_var": "SIM_ACCEL_GPU_BINARY_PATH",
            "gpu_binary_required": True,
        }
    if execution_backend == "cuda_vl_ir":
        return {
            "gpu_binary_kind": "cubin",
            "gpu_binary_relpath": "kernel_generated.vl_ir.cubin",
            "gpu_binary_env_var": "SIM_ACCEL_GPU_BINARY_PATH",
            "gpu_binary_required": True,
        }
    if execution_backend == "program_json_ir":
        return {
            "gpu_binary_kind": "cubin",
            "gpu_binary_relpath": "kernel_generated.pj_ir.cubin",
            "gpu_binary_env_var": "SIM_ACCEL_GPU_BINARY_PATH",
            "gpu_binary_required": True,
        }
    return {
        "gpu_binary_kind": "embedded_cuda",
        "gpu_binary_relpath": "",
        "gpu_binary_env_var": "",
        "gpu_binary_required": False,
    }

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compile a bench bundle produced by prepare_bench_bundle.py using the "
            "object-mode flow from the existing sim-accel bench scripts."
        )
    )
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        required=True,
        help="Bench bundle directory produced by prepare_bench_bundle.py",
    )
    parser.add_argument(
        "--binary-name",
        default="bench_kernel",
        help="Output benchmark binary name inside the bundle directory",
    )
    parser.add_argument(
        "--obj-dir",
        type=Path,
        default=Path(".sim_accel_obj"),
        help="Object directory relative to --bundle-dir",
    )
    parser.add_argument(
        "--clean-obj-dir",
        action="store_true",
        help="Remove the object directory before compiling",
    )
    parser.add_argument(
        "--skip-cpu-ref",
        action="store_true",
        help="Do not compile kernel_generated.cpu.cpp even if present",
    )
    parser.add_argument(
        "--run-smoke",
        action="store_true",
        help="Run a small off-path smoke test and a single-cluster smoke test when clusters.tsv exists",
    )
    parser.add_argument(
        "--smoke-log-dir",
        type=Path,
        default=Path(".sim_accel_smoke"),
        help="Log directory relative to --bundle-dir for smoke runs",
    )
    parser.add_argument(
        "--smoke-nstates",
        type=int,
        default=4,
        help="State count for smoke runs",
    )
    parser.add_argument(
        "--smoke-gpu-reps",
        type=int,
        default=1,
        help="GPU repetitions for smoke runs",
    )
    parser.add_argument(
        "--smoke-cpu-reps",
        type=int,
        default=1,
        help="CPU repetitions for smoke runs",
    )
    parser.add_argument(
        "--smoke-sequential-steps",
        type=int,
        default=1,
        help="Sequential steps for smoke runs",
    )
    parser.add_argument(
        "--smoke-cluster-index",
        type=int,
        default=None,
        help="Override the cluster index used for the single-cluster smoke run",
    )
    parser.add_argument(
        "--bench-arg",
        action="append",
        default=[],
        help="Extra argument to append to every smoke bench invocation",
    )
    parser.add_argument(
        "--nvcc",
        default="nvcc",
        help="CUDA compiler executable",
    )
    parser.add_argument(
        "--cxx",
        default="g++",
        help="Host C++ compiler for kernel_generated.cpu.cpp",
    )
    parser.add_argument(
        "--nvcc-flag",
        action="append",
        default=[],
        help="Extra flag passed to nvcc for compile and link steps",
    )
    parser.add_argument(
        "--cxx-flag",
        action="append",
        default=[],
        help="Extra flag passed to the host C++ compiler",
    )
    parser.add_argument(
        "--execution-backend",
        choices=EXECUTION_BACKENDS,
        default="auto",
        help="Optional execution backend override for the staged bundle.",
    )
    parser.add_argument(
        "--hipcc",
        default=shutil.which("hipcc") or "hipcc",
        help="HIP compiler executable for the temporary ROCm bridge path",
    )
    parser.add_argument(
        "--hipify-perl",
        default=shutil.which("hipify-perl") or "/opt/rocm/bin/hipify-perl",
        help="hipify-perl executable for the temporary ROCm bridge path",
    )
    parser.add_argument(
        "--gfx-arch",
        default="",
        help="Override gfx arch for the temporary ROCm bridge path (for example gfx1201)",
    )
    parser.add_argument(
        "--rocm-hipify-jobs",
        type=int,
        default=max(1, min(8, os.cpu_count() or 1)),
        help="Parallel hipify-perl workers for the temporary ROCm bridge path",
    )
    parser.add_argument(
        "--rocm-hipcc-opt-level",
        default=os.getenv("SIM_ACCEL_ROCM_HIPCC_OPT_LEVEL", "O1"),
        help="Optimization level for hipcc in the temporary ROCm bridge path (for example O1)",
    )
    parser.add_argument(
        "--clang",
        default=shutil.which("clang-18") or shutil.which("clang") or "clang",
        help="clang executable for cuda_clang_ir device-side emit-llvm compilation",
    )
    parser.add_argument(
        "--llc",
        default=shutil.which("llc-18") or shutil.which("llc") or "",
        help="llc executable for LLVM IR to PTX conversion; falls back to clang -x ir if empty",
    )
    parser.add_argument(
        "--cuda-arch",
        default="",
        help="CUDA GPU architecture for cuda_clang_ir/cuda_vl_ir backend, e.g. sm_86; generic if empty",
    )
    parser.add_argument(
        "--llvm-link",
        default=shutil.which("llvm-link-18") or shutil.which("llvm-link") or "llvm-link",
        help="llvm-link executable for merging multiple LLVM IR files (cuda_vl_ir backend)",
    )
    return parser.parse_args()


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise RuntimeError(f"Missing {label}: {path}")
    return path


def _find_cpu_ref_source(bundle_dir: Path) -> Path | None:
    """Return the CPU reference source file path, or None if not found.

    Supports both the canonical name (kernel_generated.cpu.cpp) and the
    bundle-named variant (<tb>.sim_accel.kernel.cu.cpu.cpp) produced by
    Verilator when a monolithic kernel layout is used.
    """
    canonical = bundle_dir / "kernel_generated.cpu.cpp"
    if canonical.is_file():
        return canonical
    matches = sorted(bundle_dir.glob("*.cpu.cpp"))
    return matches[0] if matches else None


def _run_logged(
    cmd: list[str],
    *,
    cwd: Path,
    log_path: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env=merged_env,
    )
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"$ {shlex.join(cmd)}\n")
        if env:
            for key in sorted(env):
                fh.write(f"[env] {key}={env[key]}\n")
        if result.stdout:
            fh.write(result.stdout)
            if not result.stdout.endswith("\n"):
                fh.write("\n")
        if result.stderr:
            fh.write(result.stderr)
            if not result.stderr.endswith("\n"):
                fh.write("\n")
        fh.write(f"[exit={result.returncode}]\n\n")
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {shlex.join(cmd)}\n"
            f"See log: {log_path}"
        )
    return result


def _format_logged_command(
    cmd: list[str],
    *,
    env: dict[str, str] | None,
    stdout: str,
    stderr: str,
    returncode: int,
) -> str:
    lines = [f"$ {shlex.join(cmd)}\n"]
    if env:
        for key in sorted(env):
            lines.append(f"[env] {key}={env[key]}\n")
    if stdout:
        lines.append(stdout)
        if not stdout.endswith("\n"):
            lines.append("\n")
    if stderr:
        lines.append(stderr)
        if not stderr.endswith("\n"):
            lines.append("\n")
    lines.append(f"[exit={returncode}]\n\n")
    return "".join(lines)


def _load_bundle_config(bundle_dir: Path) -> dict[str, object]:
    config_path = bundle_dir / BUNDLE_CONFIG_NAME
    if not config_path.is_file():
        return {
            "launch_backend": "cuda",
            "supports_single_cluster_smoke": True,
            "supports_sequential_steps": False,
            "config_path": str(config_path),
        }
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config.setdefault("launch_backend", "cuda")
    config.setdefault(
        "execution_backend",
        "cuda_source" if str(config.get("launch_backend")) == "cuda" else "cuda_circt_cubin",
    )
    config.setdefault("execution_backend_request", "auto")
    config.setdefault("execution_backend_reason", "legacy_default")
    config.setdefault("compiler_backend", "nvptx")
    config.setdefault(
        "launcher_backend",
        "cuda_runtime" if str(config.get("launch_backend")) == "cuda" else "cuda_driver",
    )
    config.update(
        {
            key: config.get(key, value)
            for key, value in _default_gpu_binary_metadata(
                launch_backend=str(config.get("launch_backend") or "cuda"),
                execution_backend=str(config.get("execution_backend") or "cuda_source"),
            ).items()
        }
    )
    config.setdefault("supports_single_cluster_smoke", True)
    config.setdefault("supports_sequential_steps", True)
    config.setdefault("rocm_launch_mode", "")
    config.setdefault("rocm_launch_mode_request", "")
    config.setdefault("rocm_launch_mode_reason", "")
    config.setdefault("rocm_native_driver_relpath", "")
    config["config_path"] = str(config_path)
    return config


def _resolve_execution_backend(bundle_config: dict[str, object], requested: str) -> str:
    requested_normalized = str(requested or "auto").strip() or "auto"
    selected = (
        str(bundle_config.get("execution_backend") or "")
        if requested_normalized == "auto"
        else requested_normalized
    )
    launch_backend = str(bundle_config.get("launch_backend") or "cuda")
    if selected == "cuda_source" and launch_backend != "cuda":
        raise RuntimeError("execution_backend=cuda_source is inconsistent with launch_backend != cuda")
    if selected == "cuda_circt_cubin" and launch_backend != "circt-cubin":
        raise RuntimeError(
            "execution_backend=cuda_circt_cubin is inconsistent with launch_backend != circt-cubin"
        )
    if selected == "rocm_llvm" and launch_backend != "cuda":
        raise RuntimeError(
            "execution_backend=rocm_llvm currently supports only source-style launch bundles "
            "(launch_backend=cuda) via the temporary HIP bridge"
        )
    if selected == "cuda_clang_ir" and launch_backend not in ("cuda", "circt-cubin"):
        raise RuntimeError(
            "execution_backend=cuda_clang_ir requires launch_backend=cuda or circt-cubin"
        )
    if selected == "cuda_vl_ir" and launch_backend not in ("cuda", "circt-cubin"):
        raise RuntimeError(
            "execution_backend=cuda_vl_ir requires launch_backend=cuda or circt-cubin"
        )
    if selected == "program_json_ir" and launch_backend not in ("cuda", "circt-cubin"):
        raise RuntimeError(
            "execution_backend=program_json_ir requires launch_backend=cuda or circt-cubin"
        )
    return selected


def _resolve_rocm_launch_mode(bundle_config: dict[str, object], execution_backend: str) -> str:
    if execution_backend != "rocm_llvm":
        return ""
    selected = str(bundle_config.get("rocm_launch_mode") or "").strip() or "source-bridge"
    if selected not in {"source-bridge", "native-hsaco"}:
        raise RuntimeError(f"Unsupported rocm_launch_mode={selected!r}")
    return selected


def _gpu_binary_env(bundle_dir: Path, bundle_config: dict[str, object]) -> dict[str, str]:
    relpath = str(bundle_config.get("gpu_binary_relpath") or "").strip()
    env_var = str(bundle_config.get("gpu_binary_env_var") or "").strip()
    if not relpath or not env_var:
        return {}
    binary_path = str((bundle_dir / relpath).resolve())
    env = {env_var: binary_path}
    legacy_env_var = str(bundle_config.get("gpu_binary_legacy_env_var") or "").strip()
    if legacy_env_var and legacy_env_var != env_var:
        env[legacy_env_var] = binary_path
    return env


def _derive_gfx_arch(explicit: str) -> str:
    if explicit:
        return explicit
    override = os.getenv("HSA_OVERRIDE_GFX_VERSION", "").strip()
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", override)
    if match:
        return f"gfx{match.group(1)}{match.group(2)}{match.group(3)}"
    raise RuntimeError(
        "Could not derive gfx arch for the ROCm bridge. Pass --gfx-arch explicitly or set "
        "HSA_OVERRIDE_GFX_VERSION."
    )


def _gfx_to_hsa_override(gfx_arch: str) -> str:
    match = re.fullmatch(r"gfx(\d+)(\d)(\d)", gfx_arch)
    if not match:
        return ""
    return f"{match.group(1)}.{match.group(2)}.{match.group(3)}"


def _rocm_env(gfx_arch: str) -> dict[str, str]:
    env = {
        "ROCM_PATH": os.getenv("ROCM_PATH", "/opt/rocm"),
    }
    hip_preload = Path(env["ROCM_PATH"]) / "lib" / "libamdhip64.so"
    preload = os.getenv("LD_PRELOAD", "")
    if hip_preload.is_file():
        env["LD_PRELOAD"] = (
            str(hip_preload)
            if "libamdhip64.so" not in preload
            else preload
        )
    elif preload:
        env["LD_PRELOAD"] = preload
    env["HSA_OVERRIDE_GFX_VERSION"] = os.getenv(
        "HSA_OVERRIDE_GFX_VERSION", _gfx_to_hsa_override(gfx_arch)
    )
    return env


def _collect_rocm_bridge_files(
    bundle_dir: Path, cuda_sources: list[Path], *, include_cpu_ref: bool
) -> list[Path]:
    bridge_files = {path for path in cuda_sources}
    for pattern in ("*.h", "*.inc"):
        bridge_files.update(bundle_dir.glob(pattern))
    return sorted(bridge_files)


def _select_rocm_bridge_compile_sources(bundle_dir: Path, cuda_sources: list[Path]) -> tuple[list[Path], bool]:
    has_structured_kernels = any(
        re.fullmatch(r"kernel_generated\.(?:part|seqpart|cluster)\d+\.cu", path.name)
        for path in cuda_sources
    )
    monolithic = bundle_dir / "kernel_generated.cu"
    bench = bundle_dir / "bench_kernel.cu"
    if has_structured_kernels and monolithic.is_file() and bench.is_file():
        return [bench, monolithic], True
    return list(cuda_sources), False


def _filter_rocm_bridge_cuda_sources(cuda_sources: list[Path]) -> list[Path]:
    has_structured_kernels = any(
        re.fullmatch(r"kernel_generated\.(?:part|seqpart|cluster)\d+\.cu", path.name)
        for path in cuda_sources
    )
    if not has_structured_kernels:
        return list(cuda_sources)
    has_seq_partition = any(
        re.fullmatch(r"kernel_generated\.seqpart\d+\.cu", path.name)
        for path in cuda_sources
    )
    filtered = [
        path
        for path in cuda_sources
        if (
            not re.fullmatch(r"kernel_generated\.full_[^.]+\.cu", path.name)
            or path.name == "kernel_generated.full_comb.cu"
            or (path.name == "kernel_generated.full_seq.cu" and not has_seq_partition)
        )
    ]
    return filtered or list(cuda_sources)


def _bridge_fingerprint(bundle_dir: Path, files: list[Path]) -> dict[str, object]:
    digest = hashlib.sha256()
    entries: list[dict[str, object]] = []
    for src in sorted(files, key=lambda path: path.name):
        stat = src.stat()
        file_digest = hashlib.sha256()
        with src.open("rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                file_digest.update(chunk)
        rel = src.relative_to(bundle_dir)
        entry = {
            "path": str(rel),
            "size": stat.st_size,
            "content_sha256": file_digest.hexdigest(),
        }
        entries.append(entry)
        digest.update(str(rel).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(entry["content_sha256"].encode("ascii"))
        digest.update(b"\0")
    return {
        "version": 1,
        "entries": entries,
        "sha256": digest.hexdigest(),
    }


def _restore_rocm_bridge_cache(
    *,
    bridge_dir: Path,
    cache_dir: Path,
    expected_fingerprint: dict[str, object],
) -> bool:
    manifest_path = cache_dir / "bridge_manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        cached = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if cached != expected_fingerprint:
        return False
    expected_files = {str(entry["path"]) for entry in expected_fingerprint.get("entries", [])}
    expected_files.add("bridge_manifest.json")
    for rel in expected_files:
        if not (cache_dir / rel).is_file():
            return False
    if bridge_dir.exists():
        shutil.rmtree(bridge_dir)
    shutil.copytree(cache_dir, bridge_dir)
    for path in bridge_dir.rglob("*"):
        if path.is_file() and str(path.relative_to(bridge_dir)) not in expected_files:
            path.unlink()
    return True


def _rocm_bridge_cache_dir(fingerprint: dict[str, object]) -> Path:
    digest = str(fingerprint.get("sha256") or "").strip()
    if not digest:
        raise RuntimeError("ROCm bridge fingerprint is missing sha256")
    return DEFAULT_ROCM_HIPIFY_CACHE_ROOT / digest


def _rocm_hipify_file_cache_path(src: Path) -> tuple[Path, str]:
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    return DEFAULT_ROCM_HIPIFY_FILE_CACHE_ROOT / digest, digest


def _seed_rocm_hipify_file_cache_from_bridge_cache(
    bundle_dir: Path, files: list[Path]
) -> None:
    wanted: dict[str, tuple[Path, str]] = {}
    for src in files:
        cache_path, cache_key = _rocm_hipify_file_cache_path(src)
        if not cache_path.is_file():
            wanted[str(src.relative_to(bundle_dir))] = (cache_path, cache_key)
    if not wanted or not DEFAULT_ROCM_HIPIFY_CACHE_ROOT.is_dir():
        return
    for manifest_path in DEFAULT_ROCM_HIPIFY_CACHE_ROOT.glob("*/bridge_manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        cache_dir = manifest_path.parent
        for entry in manifest.get("entries", []):
            rel = str(entry.get("path", ""))
            content_sha256 = str(entry.get("content_sha256", ""))
            target = wanted.get(rel)
            if target is None:
                continue
            cache_path, cache_key = target
            if cache_key != content_sha256 or cache_path.is_file():
                continue
            cached_src = cache_dir / rel
            if not cached_src.is_file():
                continue
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            staging_path = cache_path.with_name(cache_path.name + ".tmp")
            shutil.copyfile(cached_src, staging_path)
            staging_path.replace(cache_path)


def _hipify_into_bridge_dir(
    bundle_dir: Path,
    bridge_dir: Path,
    files: list[Path],
    *,
    hipify_perl: str,
    build_log: Path,
    jobs: int,
) -> bool:
    fingerprint = _bridge_fingerprint(bundle_dir, files)
    cache_dir = _rocm_bridge_cache_dir(fingerprint)
    _seed_rocm_hipify_file_cache_from_bridge_cache(bundle_dir, files)
    if _restore_rocm_bridge_cache(
        bridge_dir=bridge_dir,
        cache_dir=cache_dir,
        expected_fingerprint=fingerprint,
    ):
        with build_log.open("a", encoding="utf-8") as fh:
            fh.write(f"[rocm_bridge_cache] hit=1 key={fingerprint['sha256']}\n\n")
        return True
    if bridge_dir.exists():
        shutil.rmtree(bridge_dir)
    bridge_dir.mkdir(parents=True, exist_ok=True)

    def _hipify_one(src: Path) -> tuple[str, dict[str, object]]:
        cache_path, cache_key = _rocm_hipify_file_cache_path(src)
        if cache_path.is_file():
            return src.name, {
                "stdout": cache_path.read_text(encoding="utf-8"),
                "stderr": "",
                "returncode": 0,
                "cache_hit": True,
                "cache_key": cache_key,
            }
        cmd = [hipify_perl, src.name]
        result = subprocess.run(
            cmd,
            cwd=bundle_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            staging_path = cache_path.with_name(cache_path.name + ".tmp")
            staging_path.write_text(result.stdout, encoding="utf-8")
            staging_path.replace(cache_path)
        return src.name, {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "cache_hit": False,
            "cache_key": cache_key,
        }

    ordered_results: dict[str, dict[str, object]] = {}
    max_workers = max(1, min(int(jobs), len(files)))
    if max_workers == 1:
        for src in files:
            name, result = _hipify_one(src)
            ordered_results[name] = result
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(_hipify_one, src): src.name for src in files}
            for future in concurrent.futures.as_completed(future_map):
                name, result = future.result()
                ordered_results[name] = result

    with build_log.open("a", encoding="utf-8") as fh:
        fh.write(f"[rocm_bridge_hipify_jobs] jobs={max_workers}\n\n")
        for src in files:
            result = ordered_results[src.name]
            fh.write(
                f"[rocm_bridge_file_cache] file={src.name} hit={1 if result['cache_hit'] else 0} key={result['cache_key']}\n"
            )
            fh.write(
                _format_logged_command(
                    [hipify_perl, src.name],
                    env=None,
                    stdout=str(result["stdout"]),
                    stderr=str(result["stderr"]),
                    returncode=int(result["returncode"]),
                )
            )
            if int(result["returncode"]) != 0:
                raise RuntimeError(
                    f"Command failed with exit code {result['returncode']}: {shlex.join([hipify_perl, src.name])}\n"
                    f"See log: {build_log}"
                )
            (bridge_dir / src.name).write_text(str(result["stdout"]), encoding="utf-8")
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = cache_dir.with_name(cache_dir.name + ".tmp")
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    shutil.copytree(bridge_dir, staging_dir)
    (staging_dir / "bridge_manifest.json").write_text(
        json.dumps(fingerprint, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    staging_dir.rename(cache_dir)
    with build_log.open("a", encoding="utf-8") as fh:
        fh.write(f"[rocm_bridge_cache] hit=0 key={fingerprint['sha256']}\n\n")
    return False


def _patch_rocm_launch_all_fallback(bridge_dir: Path) -> bool:
    link_path = bridge_dir / "kernel_generated.link.cu"
    if not link_path.is_file():
        return False
    text = link_path.read_text(encoding="utf-8")
    start = text.find('extern "C" __host__ uint32_t sim_accel_eval_seq_partition_count()')
    if start < 0:
        return False
    end = text.find('extern "C" __host__ uint32_t sim_accel_eval_cluster_count()', start)
    if end < 0:
        return False
    has_full_comb = (bridge_dir / "kernel_generated.full_comb.cu").is_file()
    has_partition = any(bridge_dir.glob("kernel_generated.part*.cu"))
    has_seq_partition = any(bridge_dir.glob("kernel_generated.seqpart*.cu"))
    has_full_seq = (bridge_dir / "kernel_generated.full_seq.cu").is_file()
    has_full_all = (bridge_dir / "kernel_generated.full_all.cu").is_file()
    fallback_ops: list[str] = []
    if has_full_comb:
        fallback_ops.extend(
            [
                "        sim_accel_eval_assignw_u32_full_comb<<<grid, block>>>(state_in, state_out, nstates);",
                "        status = hipGetLastError();",
                "        if (status != hipSuccess) return status;",
            ]
        )
    if has_full_seq:
        fallback_ops.extend(
            [
                "        sim_accel_eval_assignw_u32_full_seq<<<grid, block>>>(state_in, state_out, nstates);",
                "        status = hipGetLastError();",
                "        if (status != hipSuccess) return status;",
            ]
        )
    elif has_full_all:
        fallback_ops.extend(
            [
                "        sim_accel_eval_assignw_u32_full_all<<<grid, block>>>(state_in, state_out, nstates);",
                "        status = hipGetLastError();",
                "        if (status != hipSuccess) return status;",
            ]
        )
    elif has_partition:
        fallback_ops.extend(
            [
                "        sim_accel_eval_assignw_u32_part0<<<grid, block>>>(state_in, state_out, nstates);",
                "        status = hipGetLastError();",
                "        if (status != hipSuccess) return status;",
            ]
        )
    else:
        fallback_ops.extend(["        return hipErrorInvalidValue;"])

    seq_count_body: list[str]
    seq_launch_body: list[str]
    if has_seq_partition:
        seq_sources = sorted(bridge_dir.glob("kernel_generated.seqpart*.cu"))
        seq_cases = "\n".join(
            f"    case {int(re.fullmatch(r'kernel_generated\\.seqpart(\\d+)\\.cu', path.name).group(1))}U:\n"
            f"        sim_accel_eval_assignw_u32_seqpart{int(re.fullmatch(r'kernel_generated\\.seqpart(\\d+)\\.cu', path.name).group(1))}<<<grid, block>>>(state_in, state_out, nstates);\n"
            f"        return hipGetLastError();"
            for path in seq_sources
        )
        seq_count_body = [f"    return {len(seq_sources)}U;"]
        seq_launch_body = [
            "    switch (index) {",
            seq_cases,
            "    default:",
            "        return hipErrorInvalidValue;",
            "    }",
        ]
    elif has_full_seq:
        seq_count_body = ["    return 1U;"]
        seq_launch_body = [
            "    if (index != 0U) return hipErrorInvalidValue;",
            "    sim_accel_eval_assignw_u32_full_seq<<<grid, block>>>(state_in, state_out, nstates);",
            "    return hipGetLastError();",
        ]
    else:
        seq_count_body = ["    return 0U;"]
        seq_launch_body = ["    return hipErrorInvalidValue;"]

    replacement_lines = [
        'extern "C" __host__ uint32_t sim_accel_eval_seq_partition_count() {',
        *seq_count_body,
        "}",
        "",
        'extern "C" __host__ hipError_t sim_accel_eval_assignw_launch_seq_partition(uint32_t index,',
        "                                                                     const uint64_t* state_in,",
        "                                                                     uint64_t* state_out,",
        "                                                                     uint32_t nstates,",
        "                                                                     uint32_t block_size) {",
        "    const uint32_t block = block_size ? block_size : 256U;",
        "    const uint32_t grid = (nstates + block - 1U) / block;",
        *seq_launch_body,
        "}",
        "",
        'extern "C" __host__ hipError_t sim_accel_eval_assignw_launch_all(const uint64_t* state_in,',
        "                                                           uint64_t* state_out,",
        "                                                           uint32_t nstates,",
        "                                                           uint32_t block_size);",
        "",
        'extern "C" __host__ hipError_t sim_accel_eval_assignw_launch_all_inplace(uint64_t* state,',
        "                                                                   uint32_t nstates,",
        "                                                                   uint32_t block_size) {",
        "    return sim_accel_eval_assignw_launch_all(state, state, nstates, block_size);",
        "}",
        "",
        'extern "C" __host__ hipError_t sim_accel_eval_assignw_launch_all(const uint64_t* state_in,',
        "                                                           uint64_t* state_out,",
        "                                                           uint32_t nstates,",
        "                                                           uint32_t block_size) {",
        "    const uint32_t block = block_size ? block_size : 256U;",
        "    const uint32_t grid = (nstates + block - 1U) / block;",
        "    hipError_t status = hipSuccess;",
        "    if (state_in != state_out) {",
        "        status = hipMemcpy(state_out, state_in, sim_accel_eval_var_count() * static_cast<size_t>(nstates) * sizeof(uint64_t), hipMemcpyDeviceToDevice);",
        "        if (status != hipSuccess) return status;",
        "    }",
        *(
            # When fallback kernels (full_comb/full_seq/full_all/part0) are available, use them
            # directly — no partition loop needed.  This matches what the original CUDA link.cu
            # does (calls full_all without a partition-count check).  The seq_partition loop is
            # also skipped because fallback_ops already includes the sequential step.
            [
                *fallback_ops,
                "    return hipSuccess;",
            ]
            if fallback_ops
            else [
                # No direct kernels available: fall back to partition + seq-partition loops.
                "    const uint32_t partition_count = sim_accel_eval_partition_count();",
                "    if (partition_count == 0U) {",
                "        return hipSuccess;",
                "    }",
                "    for (uint32_t index = 0; index < partition_count; ++index) {",
                "        const uint64_t* partition_in =",
                "            sim_accel_eval_partition_read_from_output_count(index) ? state_out : state_in;",
                "        status = sim_accel_eval_assignw_launch_partition(index, partition_in, state_out, nstates, block_size);",
                "        if (status != hipSuccess) return status;",
                "    }",
                "    const uint32_t seq_partition_count = sim_accel_eval_seq_partition_count();",
                "    for (uint32_t index = 0; index < seq_partition_count; ++index) {",
                "        status = sim_accel_eval_assignw_launch_seq_partition(index, state_in, state_out, nstates, block_size);",
                "        if (status != hipSuccess) return status;",
                "    }",
                "    return hipSuccess;",
            ]
        ),
        "}",
        "",
    ]
    replacement = "\n".join(replacement_lines)
    link_path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
    return True


def _patch_cuda_seq_partition_fallback(bundle_dir: Path, *, force: bool = False) -> bool:
    link_path = bundle_dir / "kernel_generated.link.cu"
    if not link_path.is_file():
        return False
    has_seq_partition = any(bundle_dir.glob("kernel_generated.seqpart*.cu"))
    has_full_seq = (bundle_dir / "kernel_generated.full_seq.cu").is_file()
    if (has_seq_partition and not force) or not has_full_seq:
        return False
    text = link_path.read_text(encoding="utf-8")
    seq_count_pattern = re.compile(
        r'(extern "C" __host__ uint32_t sim_accel_eval_seq_partition_count\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    seq_launch_pattern = re.compile(
        r'(extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_seq_partition\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    seq_count_replacement = "    return 1U;"
    seq_launch_replacement = (
        "    const uint32_t block = block_size ? block_size : 256U;\n"
        "    const uint32_t grid = (nstates + block - 1U) / block;\n"
        "    if (index != 0U) return cudaErrorInvalidValue;\n"
        "    sim_accel_eval_assignw_u32_full_seq<<<grid, block>>>(state_in, state_out, nstates);\n"
        "    return cudaGetLastError();"
    )
    updated, seq_count_count = seq_count_pattern.subn(
        lambda match: match.group(1) + seq_count_replacement + match.group(3),
        text,
        count=1,
    )
    updated, seq_launch_count = seq_launch_pattern.subn(
        lambda match: match.group(1) + seq_launch_replacement + match.group(3),
        updated,
        count=1,
    )
    if seq_count_count == 0 and seq_launch_count == 0:
        return False
    if seq_count_count != 1 or seq_launch_count != 1:
        raise RuntimeError("Failed to patch CUDA seq-partition fallback in kernel_generated.link.cu")
    link_path.write_text(updated, encoding="utf-8")
    return True


def _patch_rocm_monolithic_launch_bridge(bridge_dir: Path) -> bool:
    kernel_path = bridge_dir / "kernel_generated.cu"
    if not kernel_path.is_file():
        return False
    text = kernel_path.read_text(encoding="utf-8")
    replacements = {
        "extern \"C\" __host__ cudaError_t sim_accel_eval_assignw_launch_partition(uint32_t index,\n"
        "                                                                 const uint64_t* state_in,\n"
        "                                                                 uint64_t* state_out,\n"
        "                                                                 uint32_t nstates,\n"
        "                                                                 uint32_t block_size) {\n":
            "extern \"C\" __host__ cudaError_t sim_accel_eval_assignw_launch_partition(uint32_t index,\n"
            "                                                                 const uint64_t* state_in,\n"
            "                                                                 uint64_t* state_out,\n"
            "                                                                 uint32_t nstates,\n"
            "                                                                 uint32_t block_size) {\n"
            "    (void)cudaGetLastError();\n",
        "extern \"C\" __host__ cudaError_t sim_accel_eval_assignw_launch_seq_partition(uint32_t index,\n"
        "                                                                     const uint64_t* state_in,\n"
        "                                                                     uint64_t* state_out,\n"
        "                                                                     uint32_t nstates,\n"
        "                                                                     uint32_t block_size) {\n":
            "extern \"C\" __host__ cudaError_t sim_accel_eval_assignw_launch_seq_partition(uint32_t index,\n"
            "                                                                     const uint64_t* state_in,\n"
            "                                                                     uint64_t* state_out,\n"
            "                                                                     uint32_t nstates,\n"
            "                                                                     uint32_t block_size) {\n"
            "    (void)cudaGetLastError();\n",
        "extern \"C\" __host__ cudaError_t sim_accel_eval_assignw_launch_all_inplace(uint64_t* state,\n"
        "                                                                   uint32_t nstates,\n"
        "                                                                   uint32_t block_size) {\n":
            "extern \"C\" __host__ cudaError_t sim_accel_eval_assignw_launch_all_inplace(uint64_t* state,\n"
            "                                                                   uint32_t nstates,\n"
            "                                                                   uint32_t block_size) {\n"
            "    (void)cudaGetLastError();\n",
        "extern \"C\" __host__ cudaError_t sim_accel_eval_assignw_launch_all(const uint64_t* state_in,\n"
        "                                                           uint64_t* state_out,\n"
        "                                                           uint32_t nstates,\n"
        "                                                           uint32_t block_size) {\n":
            "extern \"C\" __host__ cudaError_t sim_accel_eval_assignw_launch_all(const uint64_t* state_in,\n"
            "                                                           uint64_t* state_out,\n"
            "                                                           uint32_t nstates,\n"
            "                                                           uint32_t block_size) {\n"
            "    (void)cudaGetLastError();\n",
        "extern \"C\" __host__ cudaError_t sim_accel_eval_assignw_launch_cluster(uint32_t index,\n"
        "                                                               const uint64_t* state_in,\n"
        "                                                               uint64_t* state_out,\n"
        "                                                               uint32_t nstates,\n"
        "                                                               uint32_t block_size) {\n":
            "extern \"C\" __host__ cudaError_t sim_accel_eval_assignw_launch_cluster(uint32_t index,\n"
            "                                                               const uint64_t* state_in,\n"
            "                                                               uint64_t* state_out,\n"
            "                                                               uint32_t nstates,\n"
            "                                                               uint32_t block_size) {\n"
            "    (void)cudaGetLastError();\n",
    }
    updated = text
    applied = False
    for needle, replacement in replacements.items():
        if needle in updated:
            updated = updated.replace(needle, replacement, 1)
            applied = True
    if not applied:
        return False
    kernel_path.write_text(updated, encoding="utf-8")
    return True


def _patch_rocm_cuda_arch_guards(bridge_dir: Path) -> int:
    """Replace __CUDA_ARCH__ preprocessor guards with HIP-compatible equivalents.

    hipify-perl does not translate __CUDA_ARCH__ to __HIP_DEVICE_COMPILE__, so
    __host__ __device__ functions that guard device-side code with
    #if !defined(__CUDA_ARCH__) / #if defined(__CUDA_ARCH__) would always take the
    host branch under HIP, causing errors when host-only functions are called from
    device code.  This patch makes both CUDA and HIP guard forms equivalent.
    """
    replacements = [
        # #if !defined(__CUDA_ARCH__) → host-only in both CUDA and HIP
        ("#if !defined(__CUDA_ARCH__)",
         "#if !defined(__CUDA_ARCH__) && !defined(__HIP_DEVICE_COMPILE__)"),
        ("#elif !defined(__CUDA_ARCH__)",
         "#elif !defined(__CUDA_ARCH__) && !defined(__HIP_DEVICE_COMPILE__)"),
        # #ifndef __CUDA_ARCH__ → host-only in both CUDA and HIP
        ("#ifndef __CUDA_ARCH__",
         "#if !defined(__CUDA_ARCH__) && !defined(__HIP_DEVICE_COMPILE__)"),
        # #if defined(__CUDA_ARCH__) → device-only in both CUDA and HIP
        ("#if defined(__CUDA_ARCH__)",
         "#if defined(__CUDA_ARCH__) || defined(__HIP_DEVICE_COMPILE__)"),
        ("#elif defined(__CUDA_ARCH__)",
         "#elif defined(__CUDA_ARCH__) || defined(__HIP_DEVICE_COMPILE__)"),
        # #ifdef __CUDA_ARCH__ → device-only in both CUDA and HIP
        ("#ifdef __CUDA_ARCH__",
         "#if defined(__CUDA_ARCH__) || defined(__HIP_DEVICE_COMPILE__)"),
    ]
    patched = 0
    for path in sorted(bridge_dir.glob("**/*")):
        if not path.is_file():
            continue
        if path.suffix not in (".cu", ".cpp", ".c", ".h", ".inc", ".cuh"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        updated = text
        for needle, replacement in replacements:
            updated = updated.replace(needle, replacement)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            patched += 1
    return patched


def _patch_rocm_cluster_launch_bridge(bridge_dir: Path) -> list[int]:
    link_path = bridge_dir / "kernel_generated.link.cu"
    if not link_path.is_file():
        return []
    cluster_indices: list[int] = []
    for cluster_src in sorted(bridge_dir.glob("kernel_generated.cluster*.cu")):
        match = re.fullmatch(r"kernel_generated\.cluster(\d+)\.cu", cluster_src.name)
        if match:
            cluster_indices.append(int(match.group(1)))
    if not cluster_indices:
        return []
    text = link_path.read_text(encoding="utf-8")
    func_name = 'extern "C" __host__ hipError_t sim_accel_eval_assignw_launch_cluster('
    start = text.find(func_name)
    if start < 0:
        return []
    brace_start = text.find("{", start)
    if brace_start < 0:
        return []
    depth = 0
    end = None
    for idx in range(brace_start, len(text)):
        ch = text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break
    if end is None:
        return []
    cases = "\n".join(
        f"    case {cluster}U:\n"
        f"        sim_accel_eval_assignw_u32_cluster{cluster}<<<grid, block>>>(state_in, state_out, nstates);\n"
        f"        return hipGetLastError();"
        for cluster in cluster_indices
    )
    replacement = f'''extern "C" __host__ hipError_t sim_accel_eval_assignw_launch_cluster(uint32_t index,
                                                              const uint64_t* state_in,
                                                              uint64_t* state_out,
                                                              uint32_t nstates,
                                                              uint32_t block_size) {{
    const uint32_t block = block_size ? block_size : 256U;
    const uint32_t grid = (nstates + block - 1U) / block;
    switch (index) {{
{cases}
    default:
        return hipErrorInvalidValue;
    }}
}}'''
    link_path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
    return cluster_indices


def _build_rocm_bridge(
    *,
    args: argparse.Namespace,
    bundle_dir: Path,
    binary_path: Path,
    obj_dir: Path,
    build_log: Path,
    cuda_sources: list[Path],
    include_cpu_ref: bool,
) -> tuple[dict[str, str], int, list[int], bool]:
    gfx_arch = _derive_gfx_arch(args.gfx_arch)
    rocm_env = _rocm_env(gfx_arch)
    bridge_dir = obj_dir / "rocm_hipified"
    cuda_sources = _filter_rocm_bridge_cuda_sources(cuda_sources)
    compile_sources, use_monolithic_structured = _select_rocm_bridge_compile_sources(
        bundle_dir, cuda_sources
    )
    bridge_files = _collect_rocm_bridge_files(
        bundle_dir, compile_sources, include_cpu_ref=include_cpu_ref
    )
    bridge_cache_hit = _hipify_into_bridge_dir(
        bundle_dir,
        bridge_dir,
        bridge_files,
        hipify_perl=args.hipify_perl,
        build_log=build_log,
        jobs=args.rocm_hipify_jobs,
    )
    cuda_arch_patched = _patch_rocm_cuda_arch_guards(bridge_dir)
    with build_log.open("a", encoding="utf-8") as fh:
        fh.write(f"[rocm_bridge_cuda_arch_patch] files_patched={cuda_arch_patched}\n\n")
    if use_monolithic_structured:
        _patch_rocm_monolithic_launch_bridge(bridge_dir)
        with build_log.open("a", encoding="utf-8") as fh:
            fh.write("[rocm_bridge_compile_mode] structured_monolithic=1\n\n")
        cluster_indices = []
    else:
        _patch_rocm_launch_all_fallback(bridge_dir)
        cluster_indices = _patch_rocm_cluster_launch_bridge(bridge_dir)
    compile_units = [bridge_dir / src.name for src in compile_sources]
    host_objects: list[Path] = []
    include_separate_cpu_ref = include_cpu_ref and not use_monolithic_structured
    if include_separate_cpu_ref:
        cpu_src = _find_cpu_ref_source(bundle_dir)
        if cpu_src is not None:
            cpu_obj = obj_dir / "kernel_generated.cpu.o"
            cpu_cmd = [
                args.cxx,
                "-O3",
                "-std=c++17",
                "-I.",
                *args.cxx_flag,
                "-c",
                cpu_src.name,
                "-o",
                str(cpu_obj.relative_to(bundle_dir)),
            ]
            _run_logged(cpu_cmd, cwd=bundle_dir, log_path=build_log)
            host_objects.append(cpu_obj.resolve())
    cmd = [
        args.hipcc,
        f"-{args.rocm_hipcc_opt_level}",
        "-std=c++17",
        f"--offload-arch={gfx_arch}",
        "-I.",
        *args.nvcc_flag,
        *(path.name for path in compile_units),
        *(["-x", "none"] if host_objects else []),
        *(str(path) for path in host_objects),
        "-o",
        str(binary_path),
    ]
    _run_logged(cmd, cwd=bridge_dir, log_path=build_log, env=rocm_env)
    return rocm_env, len(compile_units) + len(host_objects), cluster_indices, bridge_cache_hit


def _build_rocm_native_hsaco(
    *,
    args: argparse.Namespace,
    bundle_dir: Path,
    binary_path: Path,
    obj_dir: Path,
    build_log: Path,
    bundle_config: dict[str, object],
    include_cpu_ref: bool,
) -> tuple[dict[str, str], int, list[int], bool]:
    gfx_arch = _derive_gfx_arch(args.gfx_arch)
    runtime_env = {
        **_rocm_env(gfx_arch),
        **_gpu_binary_env(bundle_dir, bundle_config),
    }
    native_dir = obj_dir / "rocm_native_hsaco"
    driver_relpath = str(bundle_config.get("rocm_native_driver_relpath") or "").strip()
    driver_name = driver_relpath or "kernel_generated.full_all.rocm_driver.cpp"
    compile_sources, cluster_indices = _collect_native_hsaco_sources(bundle_dir)
    compile_sources.append(_require_file(bundle_dir / driver_name, driver_name))
    native_files = _collect_rocm_bridge_files(
        bundle_dir,
        compile_sources,
        include_cpu_ref=include_cpu_ref,
    )
    native_cache_hit = _hipify_into_bridge_dir(
        bundle_dir,
        native_dir,
        native_files,
        hipify_perl=args.hipify_perl,
        build_log=build_log,
        jobs=args.rocm_hipify_jobs,
    )
    compile_units = [native_dir / src.name for src in compile_sources]
    host_objects: list[Path] = []
    if include_cpu_ref:
        cpu_src = _find_cpu_ref_source(bundle_dir)
        if cpu_src is not None:
            cpu_obj = obj_dir / "kernel_generated.cpu.o"
            cpu_cmd = [
                args.cxx,
                "-O3",
                "-std=c++17",
                "-I.",
                *args.cxx_flag,
                "-c",
                cpu_src.name,
                "-o",
                str(cpu_obj.relative_to(bundle_dir)),
            ]
            _run_logged(cpu_cmd, cwd=bundle_dir, log_path=build_log)
            host_objects.append(cpu_obj.resolve())
    cmd = [
        args.hipcc,
        f"-{args.rocm_hipcc_opt_level}",
        "-std=c++17",
        f"--offload-arch={gfx_arch}",
        "-I.",
        *args.nvcc_flag,
        *(path.name for path in compile_units),
        *(["-x", "none"] if host_objects else []),
        *(str(path) for path in host_objects),
        "-o",
        str(binary_path),
    ]
    _run_logged(cmd, cwd=native_dir, log_path=build_log, env=runtime_env)
    return runtime_env, len(compile_units) + len(host_objects), cluster_indices, native_cache_hit


_CLANG_IR_DRIVER_TEMPLATE = """\
// Generated by build_bench_bundle.py
// CUDA driver-API loader for sim_accel_eval_assignw_u32_full_all compiled via clang++ -emit-llvm.
#include <cuda.h>
#include <cuda_runtime.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern "C" uint32_t sim_accel_eval_var_count();

namespace {
CUmodule g_sim_accel_clang_ir_module = nullptr;
CUfunction g_sim_accel_clang_ir_kernel = nullptr;
char g_sim_accel_clang_ir_module_path[4096] = {};

static cudaError_t sim_accel_clang_ir_cuda_error(CUresult status) {
    return status == CUDA_SUCCESS ? cudaSuccess : cudaErrorUnknown;
}

static cudaError_t sim_accel_clang_ir_ensure_context() {
    CUresult status = cuInit(0);
    if (status != CUDA_SUCCESS) return sim_accel_clang_ir_cuda_error(status);
    const cudaError_t runtime_status = cudaFree(nullptr);
    if (runtime_status != cudaSuccess) return runtime_status;
    CUcontext ctx = nullptr;
    status = cuCtxGetCurrent(&ctx);
    if (status != CUDA_SUCCESS) return sim_accel_clang_ir_cuda_error(status);
    if (ctx) return cudaSuccess;
    CUdevice device = 0;
    status = cuDeviceGet(&device, 0);
    if (status != CUDA_SUCCESS) return sim_accel_clang_ir_cuda_error(status);
    status = cuDevicePrimaryCtxRetain(&ctx, device);
    if (status != CUDA_SUCCESS) return sim_accel_clang_ir_cuda_error(status);
    status = cuCtxSetCurrent(ctx);
    return sim_accel_clang_ir_cuda_error(status);
}
}  // namespace

extern "C" __host__ cudaError_t sim_accel_eval_assignw_clang_ir_unload_module() {
    if (!g_sim_accel_clang_ir_module) return cudaSuccess;
    const CUresult status = cuModuleUnload(g_sim_accel_clang_ir_module);
    g_sim_accel_clang_ir_module = nullptr;
    g_sim_accel_clang_ir_kernel = nullptr;
    g_sim_accel_clang_ir_module_path[0] = '\\0';
    return sim_accel_clang_ir_cuda_error(status);
}

extern "C" __host__ cudaError_t sim_accel_eval_assignw_clang_ir_load_module(const char* ptx_path) {
    if (!ptx_path || !ptx_path[0]) return cudaErrorInvalidValue;
    cudaError_t status = sim_accel_clang_ir_ensure_context();
    if (status != cudaSuccess) return status;
    if (g_sim_accel_clang_ir_module &&
            strcmp(g_sim_accel_clang_ir_module_path, ptx_path) == 0)
        return cudaSuccess;
    status = sim_accel_eval_assignw_clang_ir_unload_module();
    if (status != cudaSuccess) return status;
    CUresult driver_status = cuModuleLoad(&g_sim_accel_clang_ir_module, ptx_path);
    if (driver_status != CUDA_SUCCESS) return sim_accel_clang_ir_cuda_error(driver_status);
    driver_status = cuModuleGetFunction(&g_sim_accel_clang_ir_kernel,
                                        g_sim_accel_clang_ir_module,
                                        "sim_accel_eval_assignw_u32_full_all");
    if (driver_status != CUDA_SUCCESS) {
        sim_accel_eval_assignw_clang_ir_unload_module();
        return sim_accel_clang_ir_cuda_error(driver_status);
    }
    strncpy(g_sim_accel_clang_ir_module_path, ptx_path,
            sizeof(g_sim_accel_clang_ir_module_path) - 1U);
    g_sim_accel_clang_ir_module_path[sizeof(g_sim_accel_clang_ir_module_path) - 1U] = '\\0';
    return cudaSuccess;
}

extern "C" __host__ cudaError_t sim_accel_eval_assignw_clang_ir_launch_all(
        const char* ptx_path,
        const uint64_t* state_in,
        uint64_t* state_out,
        uint32_t nstates,
        uint32_t block_size) {
    if (!state_in || !state_out || block_size == 0U) return cudaErrorInvalidValue;
    cudaError_t status = sim_accel_eval_assignw_clang_ir_load_module(ptx_path);
    if (status != cudaSuccess) return status;
    if (state_in != state_out) {
        const size_t copy_bytes = static_cast<size_t>(sim_accel_eval_var_count())
                                * static_cast<size_t>(nstates)
                                * sizeof(uint64_t);
        status = cudaMemcpy(state_out, state_in, copy_bytes, cudaMemcpyDeviceToDevice);
        if (status != cudaSuccess) return status;
    }
    const uint32_t grid_x = (nstates + block_size - 1U) / block_size;
    const uint64_t* kernel_state_in = state_in;
    uint64_t* kernel_state_out = state_out;
    uint32_t kernel_nstates = nstates;
    void* params[] = {&kernel_state_in, &kernel_state_out, &kernel_nstates};
    const CUresult driver_status = cuLaunchKernel(
        g_sim_accel_clang_ir_kernel,
        grid_x, 1U, 1U,
        block_size, 1U, 1U,
        0U, nullptr, params, nullptr);
    return sim_accel_clang_ir_cuda_error(driver_status);
}

extern "C" __host__ cudaError_t sim_accel_eval_assignw_clang_ir_launch_all_inplace(
        const char* ptx_path,
        uint64_t* state,
        uint32_t nstates,
        uint32_t block_size) {
    return sim_accel_eval_assignw_clang_ir_launch_all(ptx_path, state, state, nstates, block_size);
}
"""


def _patch_link_for_clang_ir(link_text: str, *, ptx_relpath: str) -> str:
    """Patch kernel_generated.link.cu to redirect full_all launches to the clang_ir driver."""
    if "sim_accel_eval_assignw_clang_ir_bundle_ptx_path" in link_text:
        return link_text  # already patched
    if "#include <stdlib.h>" not in link_text:
        link_text = link_text.replace(
            "#include <stdint.h>\n",
            "#include <stdint.h>\n#include <stdlib.h>\n",
            1,
        )
    helper_block = (
        '\nextern "C" __host__ cudaError_t sim_accel_eval_assignw_clang_ir_launch_all(\n'
        "    const char* ptx_path,\n"
        "    const uint64_t* state_in,\n"
        "    uint64_t* state_out,\n"
        "    uint32_t nstates,\n"
        "    uint32_t block_size);\n"
        'extern "C" __host__ cudaError_t sim_accel_eval_assignw_clang_ir_launch_all_inplace(\n'
        "    const char* ptx_path,\n"
        "    uint64_t* state,\n"
        "    uint32_t nstates,\n"
        "    uint32_t block_size);\n"
        "static const char* sim_accel_eval_assignw_clang_ir_bundle_ptx_path() {\n"
        f'    const char* override_path = getenv("{_GPU_BINARY_ENV_VAR}");\n'
        "    if (override_path && override_path[0] != '\\0') return override_path;\n"
        f'    return "{ptx_relpath}";\n'
        "}\n"
    )
    helper_anchor = 'extern "C" __global__ void sim_accel_eval_assignw_u32_full_all('
    if helper_anchor not in link_text:
        raise RuntimeError(
            "Could not find full-all kernel declaration in kernel_generated.link.cu; "
            "cuda_clang_ir requires a bundle built with the standalone fuser path"
        )
    link_text = link_text.replace(helper_anchor, helper_block + "\n" + helper_anchor, 1)

    inplace_replacement = (
        "    return sim_accel_eval_assignw_clang_ir_launch_all_inplace(\n"
        "        sim_accel_eval_assignw_clang_ir_bundle_ptx_path(),\n"
        "        state,\n"
        "        nstates,\n"
        "        block_size);"
    )
    all_replacement = (
        "    return sim_accel_eval_assignw_clang_ir_launch_all(\n"
        "        sim_accel_eval_assignw_clang_ir_bundle_ptx_path(),\n"
        "        state_in,\n"
        "        state_out,\n"
        "        nstates,\n"
        "        block_size);"
    )

    # Patch static helper functions (new-style link.cu from program_json_to_full_all.py)
    full_inplace_pattern = re.compile(
        r'(static __host__ cudaError_t sim_accel_eval_launch_full_all_inplace_impl\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    full_all_pattern = re.compile(
        r'(static __host__ cudaError_t sim_accel_eval_launch_full_all_impl\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    link_text, _ = full_inplace_pattern.subn(
        lambda m: m.group(1) + inplace_replacement + m.group(3), link_text, count=1
    )
    link_text, _ = full_all_pattern.subn(
        lambda m: m.group(1) + all_replacement + m.group(3), link_text, count=1
    )

    # Always patch the extern "C" wrappers (both old-style and new-style link.cu)
    inplace_pattern = re.compile(
        r'(extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_all_inplace\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    all_pattern = re.compile(
        r'(extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_all\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    link_text, inplace_count = inplace_pattern.subn(
        lambda m: m.group(1) + inplace_replacement + m.group(3), link_text, count=1
    )
    link_text, all_count = all_pattern.subn(
        lambda m: m.group(1) + all_replacement + m.group(3), link_text, count=1
    )
    if inplace_count != 1 or all_count != 1:
        raise RuntimeError("Failed to patch launch_all wrappers for cuda_clang_ir backend")
    return link_text


def _build_cuda_clang_ir(
    *,
    args: argparse.Namespace,
    bundle_dir: Path,
    binary_path: Path,
    obj_dir: Path,
    build_log: Path,
    bundle_config: dict[str, object],
    include_cpu_ref: bool,
) -> tuple[dict[str, str], int, bool]:
    cuda_arch = str(getattr(args, "cuda_arch", "") or "").strip()
    clang_bin = str(getattr(args, "clang", "") or "").strip() or (
        shutil.which("clang-18") or shutil.which("clang") or "clang"
    )
    llc_bin = str(getattr(args, "llc", "") or "").strip() or (
        shutil.which("llc-18") or shutil.which("llc") or ""
    )

    clang_ir_dir = obj_dir / "cuda_clang_ir"
    clang_ir_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: compile kernel_generated.full_all.cu → LLVM IR with clang
    full_all_cu = _require_file(
        bundle_dir / "kernel_generated.full_all.cu",
        "kernel_generated.full_all.cu",
    )
    ll_path = bundle_dir / "kernel_generated.full_all.clang_ir.ll"
    emit_cmd = [
        clang_bin,
        "-x", "cuda",
        "--cuda-device-only",
        "-emit-llvm",
        "-S",
        "-O3",
        "-I.",
        *([f"--cuda-gpu-arch={cuda_arch}"] if cuda_arch else []),
        full_all_cu.name,
        "-o", str(ll_path.relative_to(bundle_dir)),
    ]
    _run_logged(emit_cmd, cwd=bundle_dir, log_path=build_log)

    # Step 2: LLVM IR → PTX
    ptx_relpath = "kernel_generated.full_all.clang_ir.ptx"
    ptx_path = bundle_dir / ptx_relpath
    if llc_bin:
        ptx_cmd: list[str] = [llc_bin, "-march=nvptx64"]
        if cuda_arch:
            ptx_cmd.append(f"-mcpu={cuda_arch}")
        ptx_cmd += [str(ll_path), "-o", str(ptx_path)]
    else:
        ptx_cmd = [
            clang_bin,
            "-S",
            "-x", "ir",
            "--target=nvptx64-nvidia-cuda",
            "-nocudalib",
            *([f"--cuda-gpu-arch={cuda_arch}"] if cuda_arch else []),
            str(ll_path),
            "-o", str(ptx_path),
        ]
    _run_logged(ptx_cmd, cwd=bundle_dir, log_path=build_log)

    # Step 3: patch link.cu → redirect launch_all to clang_ir driver
    link_text = (bundle_dir / "kernel_generated.link.cu").read_text(encoding="utf-8")
    patched_link = clang_ir_dir / "kernel_generated.link.cu"
    patched_link.write_text(
        _patch_link_for_clang_ir(link_text, ptx_relpath=ptx_relpath), encoding="utf-8"
    )

    # Step 4: write driver source
    driver_src = clang_ir_dir / "kernel_generated.full_all.clang_ir_driver.cpp"
    driver_src.write_text(_CLANG_IR_DRIVER_TEMPLATE, encoding="utf-8")

    # Step 5: collect nvcc sources (all .cu except full_all.cu; use patched link.cu)
    fixed: list[Path] = [
        _require_file(bundle_dir / "bench_kernel.cu", "bench_kernel.cu"),
        patched_link,
    ]
    extra: list[Path] = []
    for pattern in (
        "kernel_generated.part*.cu",
        "kernel_generated.seqpart*.cu",
        "kernel_generated.cluster*.cu",
    ):
        extra.extend(sorted(bundle_dir.glob(pattern)))
    for p in sorted(bundle_dir.glob("kernel_generated.full_*.cu")):
        if p.name != "kernel_generated.full_all.cu":
            extra.append(p)
    nvcc_sources = fixed + extra

    effective_nvcc_flags = [
        *args.nvcc_flag,
        *(["-DSIM_ACCEL_SKIP_CPU_REFERENCE_BUILD=1"] if not include_cpu_ref else []),
    ]

    link_objects: list[Path] = []
    for src in nvcc_sources:
        obj = obj_dir / f"{src.name}.o"
        cmd = [
            args.nvcc,
            "-O3",
            "-std=c++17",
            "-rdc=true",
            "-I.",
            f"-I{bundle_dir}",
            *effective_nvcc_flags,
            "-c",
            str(src),
            "-o",
            str(obj),
        ]
        _run_logged(cmd, cwd=bundle_dir, log_path=build_log)
        link_objects.append(obj)

    # Compile clang_ir driver with nvcc
    driver_obj = obj_dir / "kernel_generated.full_all.clang_ir_driver.o"
    _run_logged(
        [
            args.nvcc,
            "-O3",
            "-std=c++17",
            "-rdc=true",
            "-I.",
            *args.nvcc_flag,
            "-c",
            str(driver_src),
            "-o",
            str(driver_obj),
        ],
        cwd=bundle_dir,
        log_path=build_log,
    )
    link_objects.append(driver_obj)

    # Compile CPU reference
    if include_cpu_ref:
        cpu_src = _find_cpu_ref_source(bundle_dir)
        if cpu_src is not None:
            cpu_obj = obj_dir / "kernel_generated.cpu.o"
            _run_logged(
                [
                    args.cxx,
                    "-O3",
                    "-std=c++17",
                    "-I.",
                    *args.cxx_flag,
                    "-c",
                    str(cpu_src),
                    "-o",
                    str(cpu_obj),
                ],
                cwd=bundle_dir,
                log_path=build_log,
            )
            link_objects.append(cpu_obj)

    # Link
    _run_logged(
        [
            args.nvcc,
            "-O3",
            "-std=c++17",
            "-rdc=true",
            *effective_nvcc_flags,
            *(str(p) for p in link_objects),
            "-lcuda",
            "-o",
            args.binary_name,
        ],
        cwd=bundle_dir,
        log_path=build_log,
    )

    smoke_env = _gpu_binary_env(bundle_dir, bundle_config)
    compiled_count = len(nvcc_sources) + 1 + (
        1 if include_cpu_ref and _find_cpu_ref_source(bundle_dir) is not None else 0
    )
    return smoke_env, compiled_count, False


_VL_IR_DRIVER_TEMPLATE = """\
// Generated by build_bench_bundle.py
// CUDA driver-API loader for Verilator-generated full_comb + full_seq kernels compiled via clang++ -emit-llvm.
#include <cuda.h>
#include <cuda_runtime.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

extern "C" uint32_t sim_accel_eval_var_count();

namespace {
CUmodule g_sim_accel_vl_ir_module = nullptr;
CUfunction g_sim_accel_vl_ir_comb_kernel = nullptr;
CUfunction g_sim_accel_vl_ir_seq_kernel = nullptr;
char g_sim_accel_vl_ir_module_path[4096] = {};

static cudaError_t sim_accel_vl_ir_cuda_error(CUresult status) {
    return status == CUDA_SUCCESS ? cudaSuccess : cudaErrorUnknown;
}

static cudaError_t sim_accel_vl_ir_ensure_context() {
    CUresult status = cuInit(0);
    if (status != CUDA_SUCCESS) return sim_accel_vl_ir_cuda_error(status);
    const cudaError_t runtime_status = cudaFree(nullptr);
    if (runtime_status != cudaSuccess) return runtime_status;
    CUcontext ctx = nullptr;
    status = cuCtxGetCurrent(&ctx);
    if (status != CUDA_SUCCESS) return sim_accel_vl_ir_cuda_error(status);
    if (ctx) return cudaSuccess;
    CUdevice device = 0;
    status = cuDeviceGet(&device, 0);
    if (status != CUDA_SUCCESS) return sim_accel_vl_ir_cuda_error(status);
    status = cuDevicePrimaryCtxRetain(&ctx, device);
    if (status != CUDA_SUCCESS) return sim_accel_vl_ir_cuda_error(status);
    status = cuCtxSetCurrent(ctx);
    return sim_accel_vl_ir_cuda_error(status);
}
}  // namespace

extern "C" __host__ cudaError_t sim_accel_eval_assignw_vl_ir_unload_module() {
    if (!g_sim_accel_vl_ir_module) return cudaSuccess;
    const CUresult status = cuModuleUnload(g_sim_accel_vl_ir_module);
    g_sim_accel_vl_ir_module = nullptr;
    g_sim_accel_vl_ir_comb_kernel = nullptr;
    g_sim_accel_vl_ir_seq_kernel = nullptr;
    g_sim_accel_vl_ir_module_path[0] = '\\0';
    return sim_accel_vl_ir_cuda_error(status);
}

extern "C" __host__ cudaError_t sim_accel_eval_assignw_vl_ir_load_module(const char* ptx_path) {
    if (!ptx_path || !ptx_path[0]) return cudaErrorInvalidValue;
    cudaError_t status = sim_accel_vl_ir_ensure_context();
    if (status != cudaSuccess) return status;
    if (g_sim_accel_vl_ir_module &&
            strcmp(g_sim_accel_vl_ir_module_path, ptx_path) == 0)
        return cudaSuccess;
    status = sim_accel_eval_assignw_vl_ir_unload_module();
    if (status != cudaSuccess) return status;
    CUresult driver_status = cuModuleLoad(&g_sim_accel_vl_ir_module, ptx_path);
    if (driver_status != CUDA_SUCCESS) return sim_accel_vl_ir_cuda_error(driver_status);
    driver_status = cuModuleGetFunction(&g_sim_accel_vl_ir_comb_kernel,
                                        g_sim_accel_vl_ir_module,
                                        "sim_accel_eval_assignw_u32_full_comb");
    if (driver_status != CUDA_SUCCESS) {
        sim_accel_eval_assignw_vl_ir_unload_module();
        return sim_accel_vl_ir_cuda_error(driver_status);
    }
    driver_status = cuModuleGetFunction(&g_sim_accel_vl_ir_seq_kernel,
                                        g_sim_accel_vl_ir_module,
                                        "sim_accel_eval_assignw_u32_full_seq");
    if (driver_status != CUDA_SUCCESS) {
        sim_accel_eval_assignw_vl_ir_unload_module();
        return sim_accel_vl_ir_cuda_error(driver_status);
    }
    strncpy(g_sim_accel_vl_ir_module_path, ptx_path,
            sizeof(g_sim_accel_vl_ir_module_path) - 1U);
    g_sim_accel_vl_ir_module_path[sizeof(g_sim_accel_vl_ir_module_path) - 1U] = '\\0';
    return cudaSuccess;
}

extern "C" __host__ cudaError_t sim_accel_eval_assignw_vl_ir_launch_all(
        const char* ptx_path,
        const uint64_t* state_in,
        uint64_t* state_out,
        uint32_t nstates,
        uint32_t block_size) {
    if (!state_in || !state_out || block_size == 0U) return cudaErrorInvalidValue;
    cudaError_t status = sim_accel_eval_assignw_vl_ir_load_module(ptx_path);
    if (status != cudaSuccess) return status;
    if (state_in != state_out) {
        const size_t copy_bytes = static_cast<size_t>(sim_accel_eval_var_count())
                                * static_cast<size_t>(nstates)
                                * sizeof(uint64_t);
        status = cudaMemcpy(state_out, state_in, copy_bytes, cudaMemcpyDeviceToDevice);
        if (status != cudaSuccess) return status;
    }
    const uint32_t grid_x = (nstates + block_size - 1U) / block_size;
    const uint64_t* kernel_state_in = state_in;
    uint64_t* kernel_state_out = state_out;
    uint32_t kernel_nstates = nstates;
    void* params[] = {&kernel_state_in, &kernel_state_out, &kernel_nstates};
    CUresult driver_status = cuLaunchKernel(
        g_sim_accel_vl_ir_comb_kernel,
        grid_x, 1U, 1U,
        block_size, 1U, 1U,
        0U, nullptr, params, nullptr);
    if (driver_status != CUDA_SUCCESS) return sim_accel_vl_ir_cuda_error(driver_status);
    driver_status = cuLaunchKernel(
        g_sim_accel_vl_ir_seq_kernel,
        grid_x, 1U, 1U,
        block_size, 1U, 1U,
        0U, nullptr, params, nullptr);
    return sim_accel_vl_ir_cuda_error(driver_status);
}

extern "C" __host__ cudaError_t sim_accel_eval_assignw_vl_ir_launch_all_inplace(
        const char* ptx_path,
        uint64_t* state,
        uint32_t nstates,
        uint32_t block_size) {
    return sim_accel_eval_assignw_vl_ir_launch_all(ptx_path, state, state, nstates, block_size);
}
"""


def _patch_link_for_vl_ir(link_text: str, *, ptx_relpath: str) -> str:
    """Patch kernel_generated.link.cu to redirect full_all launches to the vl_ir driver."""
    if "sim_accel_eval_assignw_vl_ir_bundle_ptx_path" in link_text:
        return link_text  # already patched
    if "#include <stdlib.h>" not in link_text:
        link_text = link_text.replace(
            "#include <stdint.h>\n",
            "#include <stdint.h>\n#include <stdlib.h>\n",
            1,
        )
    helper_block = (
        '\nextern "C" __host__ cudaError_t sim_accel_eval_assignw_vl_ir_launch_all(\n'
        "    const char* ptx_path,\n"
        "    const uint64_t* state_in,\n"
        "    uint64_t* state_out,\n"
        "    uint32_t nstates,\n"
        "    uint32_t block_size);\n"
        'extern "C" __host__ cudaError_t sim_accel_eval_assignw_vl_ir_launch_all_inplace(\n'
        "    const char* ptx_path,\n"
        "    uint64_t* state,\n"
        "    uint32_t nstates,\n"
        "    uint32_t block_size);\n"
        "static const char* sim_accel_eval_assignw_vl_ir_bundle_ptx_path() {\n"
        f'    const char* override_path = getenv("{_GPU_BINARY_ENV_VAR}");\n'
        "    if (override_path && override_path[0] != '\\0') return override_path;\n"
        f'    return "{ptx_relpath}";\n'
        "}\n"
    )
    # Prefer to anchor before full_comb (Verilator-native), fall back to full_all
    helper_anchor_comb = 'extern "C" __global__ void sim_accel_eval_assignw_u32_full_comb('
    helper_anchor_all = 'extern "C" __global__ void sim_accel_eval_assignw_u32_full_all('
    if helper_anchor_comb in link_text:
        link_text = link_text.replace(helper_anchor_comb, helper_block + "\n" + helper_anchor_comb, 1)
    elif helper_anchor_all in link_text:
        link_text = link_text.replace(helper_anchor_all, helper_block + "\n" + helper_anchor_all, 1)
    else:
        raise RuntimeError(
            "Could not find full_comb or full_all kernel declaration in kernel_generated.link.cu; "
            "cuda_vl_ir requires a Verilator --sim-accel-only bundle"
        )

    inplace_replacement = (
        "    return sim_accel_eval_assignw_vl_ir_launch_all_inplace(\n"
        "        sim_accel_eval_assignw_vl_ir_bundle_ptx_path(),\n"
        "        state,\n"
        "        nstates,\n"
        "        block_size);"
    )
    all_replacement = (
        "    return sim_accel_eval_assignw_vl_ir_launch_all(\n"
        "        sim_accel_eval_assignw_vl_ir_bundle_ptx_path(),\n"
        "        state_in,\n"
        "        state_out,\n"
        "        nstates,\n"
        "        block_size);"
    )

    # Patch static helper functions (new-style link.cu from program_json_to_full_all.py)
    full_inplace_pattern = re.compile(
        r'(static __host__ cudaError_t sim_accel_eval_launch_full_all_inplace_impl\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    full_all_pattern = re.compile(
        r'(static __host__ cudaError_t sim_accel_eval_launch_full_all_impl\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    link_text, _ = full_inplace_pattern.subn(
        lambda m: m.group(1) + inplace_replacement + m.group(3), link_text, count=1
    )
    link_text, _ = full_all_pattern.subn(
        lambda m: m.group(1) + all_replacement + m.group(3), link_text, count=1
    )

    # Always patch the extern "C" wrappers
    inplace_pattern = re.compile(
        r'(extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_all_inplace\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    all_pattern = re.compile(
        r'(extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_all\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    link_text, inplace_count = inplace_pattern.subn(
        lambda m: m.group(1) + inplace_replacement + m.group(3), link_text, count=1
    )
    link_text, all_count = all_pattern.subn(
        lambda m: m.group(1) + all_replacement + m.group(3), link_text, count=1
    )
    if inplace_count != 1 or all_count != 1:
        raise RuntimeError("Failed to patch launch_all wrappers for cuda_vl_ir backend")
    return link_text


def _build_cuda_vl_ir(
    *,
    args: argparse.Namespace,
    bundle_dir: Path,
    binary_path: Path,
    obj_dir: Path,
    build_log: Path,
    bundle_config: dict[str, object],
    include_cpu_ref: bool,
) -> tuple[dict[str, str], int, bool]:
    cuda_arch = str(getattr(args, "cuda_arch", "") or "").strip()
    clang_bin = str(getattr(args, "clang", "") or "").strip() or (
        shutil.which("clang-18") or shutil.which("clang") or "clang"
    )
    llc_bin = str(getattr(args, "llc", "") or "").strip() or (
        shutil.which("llc-18") or shutil.which("llc") or ""
    )
    llvm_link_bin = str(getattr(args, "llvm_link", "") or "").strip() or (
        shutil.which("llvm-link-18") or shutil.which("llvm-link") or "llvm-link"
    )

    vl_ir_dir = obj_dir / "cuda_vl_ir"
    vl_ir_dir.mkdir(parents=True, exist_ok=True)

    full_comb_cu = _require_file(
        bundle_dir / "kernel_generated.full_comb.cu",
        "kernel_generated.full_comb.cu",
    )
    full_seq_cu = _require_file(
        bundle_dir / "kernel_generated.full_seq.cu",
        "kernel_generated.full_seq.cu",
    )

    emit_flags = [
        clang_bin,
        "-x", "cuda",
        "--cuda-device-only",
        "-emit-llvm",
        "-S",
        "-O1",
        "-fbracket-depth=1024",
        "-I.",
        *([f"--cuda-gpu-arch={cuda_arch}"] if cuda_arch else []),
    ]

    # Step 1a: full_comb.cu → LLVM IR
    comb_ll = bundle_dir / "kernel_generated.full_comb.vl_ir.ll"
    _run_logged(
        emit_flags + [full_comb_cu.name, "-o", str(comb_ll.relative_to(bundle_dir))],
        cwd=bundle_dir,
        log_path=build_log,
    )

    # Step 1b: full_seq.cu → LLVM IR
    seq_ll = bundle_dir / "kernel_generated.full_seq.vl_ir.ll"
    _run_logged(
        emit_flags + [full_seq_cu.name, "-o", str(seq_ll.relative_to(bundle_dir))],
        cwd=bundle_dir,
        log_path=build_log,
    )

    # Step 2: llvm-link → merged IR
    merged_ll = bundle_dir / "kernel_generated.vl_ir.ll"
    _run_logged(
        [llvm_link_bin, str(comb_ll), str(seq_ll), "-o", str(merged_ll)],
        cwd=bundle_dir,
        log_path=build_log,
    )

    # Step 3: LLVM IR → PTX
    ptx_relpath = "kernel_generated.vl_ir.ptx"
    ptx_path = bundle_dir / ptx_relpath
    if llc_bin:
        ptx_cmd: list[str] = [llc_bin, "-march=nvptx64"]
        if cuda_arch:
            ptx_cmd.append(f"-mcpu={cuda_arch}")
        ptx_cmd += [str(merged_ll), "-o", str(ptx_path)]
    else:
        ptx_cmd = [
            clang_bin,
            "-S",
            "-x", "ir",
            "--target=nvptx64-nvidia-cuda",
            "-nocudalib",
            *([f"--cuda-gpu-arch={cuda_arch}"] if cuda_arch else []),
            str(merged_ll),
            "-o", str(ptx_path),
        ]
    _run_logged(ptx_cmd, cwd=bundle_dir, log_path=build_log)

    # Step 3b: ptxas → cubin (avoid 2-min JIT penalty at runtime)
    ptxas_bin = shutil.which("ptxas") or "ptxas"
    cubin_relpath = "kernel_generated.vl_ir.cubin"
    cubin_path = bundle_dir / cubin_relpath
    ptxas_cmd = [ptxas_bin]
    if cuda_arch:
        ptxas_cmd += ["--gpu-name", cuda_arch]
    ptxas_cmd += [str(ptx_path), "-o", str(cubin_path)]
    _run_logged(ptxas_cmd, cwd=bundle_dir, log_path=build_log)

    # Step 4: patch link.cu → redirect launch_all to vl_ir driver
    link_text = (bundle_dir / "kernel_generated.link.cu").read_text(encoding="utf-8")
    patched_link = vl_ir_dir / "kernel_generated.link.cu"
    patched_link.write_text(
        _patch_link_for_vl_ir(link_text, ptx_relpath=cubin_relpath), encoding="utf-8"
    )

    # Step 5: write driver source
    driver_src = vl_ir_dir / "kernel_generated.vl_ir_driver.cpp"
    driver_src.write_text(_VL_IR_DRIVER_TEMPLATE, encoding="utf-8")

    # Step 6: collect nvcc sources
    # full_comb.cu is compiled to PTX only (not called via CUDA runtime API from link.cu).
    # full_seq.cu must be compiled by nvcc because link.cu's launch_seq_partition calls it
    # via <<<>>> syntax. It is also included in the PTX for the vl_ir driver's launch_all path.
    # full_all.cu is kept in nvcc sources so the linker can satisfy the extern __global__
    # forward declaration in link.cu (the kernel body is never called at runtime).
    fixed: list[Path] = [
        _require_file(bundle_dir / "bench_kernel.cu", "bench_kernel.cu"),
        patched_link,
    ]
    extra: list[Path] = []
    for pattern in (
        "kernel_generated.part*.cu",
        "kernel_generated.seqpart*.cu",
        "kernel_generated.cluster*.cu",
    ):
        extra.extend(sorted(bundle_dir.glob(pattern)))
    for p in sorted(bundle_dir.glob("kernel_generated.full_*.cu")):
        if p.name != "kernel_generated.full_comb.cu":
            extra.append(p)  # full_seq.cu + full_all.cu compiled by nvcc; full_comb.cu PTX only
    nvcc_sources = fixed + extra

    # When CPU reference is skipped, suppress bench_kernel.cu's CPU reference calls.
    effective_nvcc_flags = [
        *args.nvcc_flag,
        *(["-DSIM_ACCEL_SKIP_CPU_REFERENCE_BUILD=1"] if not include_cpu_ref else []),
    ]

    link_objects: list[Path] = []
    for src in nvcc_sources:
        obj = obj_dir / f"{src.name}.o"
        cmd = [
            args.nvcc,
            "-O3",
            "-std=c++17",
            "-rdc=true",
            "-I.",
            f"-I{bundle_dir}",
            *effective_nvcc_flags,
            "-c",
            str(src),
            "-o",
            str(obj),
        ]
        _run_logged(cmd, cwd=bundle_dir, log_path=build_log)
        link_objects.append(obj)

    # Compile vl_ir driver with nvcc
    driver_obj = obj_dir / "kernel_generated.vl_ir_driver.o"
    _run_logged(
        [
            args.nvcc,
            "-O3",
            "-std=c++17",
            "-rdc=true",
            "-I.",
            *args.nvcc_flag,
            "-c",
            str(driver_src),
            "-o",
            str(driver_obj),
        ],
        cwd=bundle_dir,
        log_path=build_log,
    )
    link_objects.append(driver_obj)

    # Compile CPU reference
    if include_cpu_ref:
        cpu_src = _find_cpu_ref_source(bundle_dir)
        if cpu_src is not None:
            cpu_obj = obj_dir / "kernel_generated.cpu.o"
            _run_logged(
                [
                    args.cxx,
                    "-O3",
                    "-std=c++17",
                    "-I.",
                    *args.cxx_flag,
                    "-c",
                    str(cpu_src),
                    "-o",
                    str(cpu_obj),
                ],
                cwd=bundle_dir,
                log_path=build_log,
            )
            link_objects.append(cpu_obj)

    # Link
    _run_logged(
        [
            args.nvcc,
            "-O3",
            "-std=c++17",
            "-rdc=true",
            *effective_nvcc_flags,
            *(str(p) for p in link_objects),
            "-lcuda",
            "-o",
            args.binary_name,
        ],
        cwd=bundle_dir,
        log_path=build_log,
    )

    smoke_env = _gpu_binary_env(bundle_dir, bundle_config)
    compiled_count = len(nvcc_sources) + 1 + (
        1 if include_cpu_ref and _find_cpu_ref_source(bundle_dir) is not None else 0
    )
    return smoke_env, compiled_count, False


def _build_pj_ir(
    *,
    args: argparse.Namespace,
    bundle_dir: Path,
    binary_path: Path,
    obj_dir: Path,
    build_log: Path,
    bundle_config: dict[str, object],
    include_cpu_ref: bool,
) -> tuple[dict[str, str], int, bool]:
    """Build bench using program.json → LLVM IR → opt → llc → ptxas (cubin) pipeline.

    Avoids nvcc/hipcc for GPU kernel compilation.  Produces an offline-compiled cubin
    so cuModuleLoad doesn't trigger the 2-minute JIT penalty of our larger PTX.
    """
    cuda_arch = str(getattr(args, "cuda_arch", "") or "").strip()
    llc_bin = str(getattr(args, "llc", "") or "").strip() or (
        shutil.which("llc-18") or shutil.which("llc") or "llc"
    )
    llvm_link_bin = str(getattr(args, "llvm_link", "") or "").strip() or (
        shutil.which("llvm-link-18") or shutil.which("llvm-link") or "llvm-link"
    )
    opt_bin = shutil.which("opt-18") or shutil.which("opt") or "opt"
    ptxas_bin = shutil.which("ptxas") or "ptxas"

    pj_ir_dir = obj_dir / "pj_ir"
    pj_ir_dir.mkdir(parents=True, exist_ok=True)

    # Locate program.json (Verilator --sim-accel-ir-only output)
    program_json_files = sorted(bundle_dir.glob("*.program.json"))
    if not program_json_files:
        raise RuntimeError("program_json_ir: no *.program.json found in bundle_dir")
    program_json = program_json_files[0]

    # Step 1: program.json → LLVM IR text for comb + seq kernels
    pj_ir_script = Path(__file__).resolve().parent / "program_json_to_llvm_ir.py"
    comb_ll = pj_ir_dir / "pj_ir.comb.ll"
    seq_ll = pj_ir_dir / "pj_ir.seq.ll"
    gen_cmd = [
        sys.executable, str(pj_ir_script),
        str(program_json),
        "--target", "nvptx",
        "--out-comb", str(comb_ll),
        "--out-seq", str(seq_ll),
    ]
    if cuda_arch:
        gen_cmd += ["--cpu", cuda_arch]
    _run_logged(gen_cmd, cwd=bundle_dir, log_path=build_log)

    # Step 2: generate preload_word stub (returns 0; real preload data is in state memory)
    stub_ll = pj_ir_dir / "preload_stub.ll"
    stub_ll.write_text(
        'target triple = "nvptx64-nvidia-cuda"\n'
        "define i64 @sim_accel_preload_word(i32, i32, i32) {\n"
        "  ret i64 0\n"
        "}\n",
        encoding="utf-8",
    )

    # Step 3: llvm-link → merged bitcode
    merged_bc = pj_ir_dir / "pj_ir.linked.bc"
    _run_logged(
        [llvm_link_bin, str(comb_ll), str(seq_ll), str(stub_ll), "-o", str(merged_bc)],
        cwd=bundle_dir,
        log_path=build_log,
    )

    # Step 4: opt-18 -O3 (our emitted IR is unoptimized; clang-based vl_ir skips this)
    opt_bc = pj_ir_dir / "pj_ir.opt.bc"
    _run_logged(
        [opt_bin, "-O3", str(merged_bc), "-o", str(opt_bc)],
        cwd=bundle_dir,
        log_path=build_log,
    )

    # Step 5: llc → PTX
    ptx_path = pj_ir_dir / "pj_ir.ptx"
    llc_cmd = [llc_bin, "-march=nvptx64"]
    if cuda_arch:
        llc_cmd.append(f"-mcpu={cuda_arch}")
    llc_cmd += ["-O3", str(opt_bc), "-o", str(ptx_path)]
    _run_logged(llc_cmd, cwd=bundle_dir, log_path=build_log)

    # Step 6: ptxas → cubin  (offline compile avoids the ~2-minute JIT penalty)
    cubin_relpath = "kernel_generated.pj_ir.cubin"
    cubin_path = bundle_dir / cubin_relpath
    ptxas_cmd = [ptxas_bin]
    if cuda_arch:
        ptxas_cmd += ["--gpu-name", cuda_arch]
    ptxas_cmd += [str(ptx_path), "-o", str(cubin_path)]
    _run_logged(ptxas_cmd, cwd=bundle_dir, log_path=build_log)

    # Steps 7+: build bench binary identical to cuda_vl_ir
    # (same driver template; same launch mechanism; different GPU binary path)
    link_text = (bundle_dir / "kernel_generated.link.cu").read_text(encoding="utf-8")
    patched_link = pj_ir_dir / "kernel_generated.link.cu"
    patched_link.write_text(
        _patch_link_for_vl_ir(link_text, ptx_relpath=cubin_relpath), encoding="utf-8"
    )

    driver_src = pj_ir_dir / "kernel_generated.vl_ir_driver.cpp"
    driver_src.write_text(_VL_IR_DRIVER_TEMPLATE, encoding="utf-8")

    fixed: list[Path] = [
        _require_file(bundle_dir / "bench_kernel.cu", "bench_kernel.cu"),
        patched_link,
    ]
    extra: list[Path] = []
    for pattern in (
        "kernel_generated.part*.cu",
        "kernel_generated.seqpart*.cu",
        "kernel_generated.cluster*.cu",
    ):
        extra.extend(sorted(bundle_dir.glob(pattern)))
    for p in sorted(bundle_dir.glob("kernel_generated.full_*.cu")):
        if p.name != "kernel_generated.full_comb.cu":
            extra.append(p)
    nvcc_sources = fixed + extra

    effective_nvcc_flags = [
        *args.nvcc_flag,
        *(["-DSIM_ACCEL_SKIP_CPU_REFERENCE_BUILD=1"] if not include_cpu_ref else []),
    ]

    link_objects: list[Path] = []
    for src in nvcc_sources:
        obj = pj_ir_dir / f"{src.name}.o"
        _run_logged(
            [
                args.nvcc, "-O3", "-std=c++17", "-rdc=true", "-I.", f"-I{bundle_dir}",
                *effective_nvcc_flags,
                "-c", str(src), "-o", str(obj),
            ],
            cwd=bundle_dir,
            log_path=build_log,
        )
        link_objects.append(obj)

    driver_obj = pj_ir_dir / "kernel_generated.vl_ir_driver.o"
    _run_logged(
        [
            args.nvcc, "-O3", "-std=c++17", "-rdc=true", "-I.", *args.nvcc_flag,
            "-c", str(driver_src), "-o", str(driver_obj),
        ],
        cwd=bundle_dir,
        log_path=build_log,
    )
    link_objects.append(driver_obj)

    if include_cpu_ref:
        cpu_src = _find_cpu_ref_source(bundle_dir)
        if cpu_src is not None:
            cpu_obj = pj_ir_dir / "kernel_generated.cpu.o"
            _run_logged(
                [
                    args.cxx, "-O3", "-std=c++17", "-I.", *args.cxx_flag,
                    "-c", str(cpu_src), "-o", str(cpu_obj),
                ],
                cwd=bundle_dir,
                log_path=build_log,
            )
            link_objects.append(cpu_obj)

    _run_logged(
        [
            args.nvcc, "-O3", "-std=c++17", "-rdc=true", *effective_nvcc_flags,
            *(str(p) for p in link_objects),
            "-lcuda", "-o", args.binary_name,
        ],
        cwd=bundle_dir,
        log_path=build_log,
    )

    smoke_env = _gpu_binary_env(bundle_dir, bundle_config)
    compiled_count = len(nvcc_sources) + 1 + (
        1 if include_cpu_ref and _find_cpu_ref_source(bundle_dir) is not None else 0
    )
    return smoke_env, compiled_count, False


def _collect_cuda_sources(bundle_dir: Path, *, launch_backend: str) -> list[Path]:
    fixed = [
        _require_file(bundle_dir / "bench_kernel.cu", "bench_kernel.cu"),
        _require_file(bundle_dir / "kernel_generated.link.cu", "kernel_generated.link.cu"),
    ]
    extra: list[Path] = []
    for pattern in (
        "kernel_generated.part*.cu",
        "kernel_generated.seqpart*.cu",
        "kernel_generated.cluster*.cu",
    ):
        extra.extend(sorted(bundle_dir.glob(pattern)))
    if launch_backend != "circt-cubin":
        extra.extend(sorted(bundle_dir.glob("kernel_generated.full_*.cu")))
    if extra:
        return fixed + extra
    fallback = bundle_dir / "kernel_generated.cu"
    if fallback.is_file() and launch_backend != "circt-cubin":
        return fixed + [fallback]
    return fixed


def _collect_native_hsaco_sources(bundle_dir: Path) -> tuple[list[Path], list[int]]:
    fixed = [
        _require_file(bundle_dir / "bench_kernel.cu", "bench_kernel.cu"),
        _require_file(bundle_dir / "kernel_generated.link.cu", "kernel_generated.link.cu"),
    ]
    cluster_indices: list[int] = []
    extra: list[Path] = []
    for pattern in (
        "kernel_generated.part*.cu",
        "kernel_generated.seqpart*.cu",
        "kernel_generated.cluster*.cu",
    ):
        for path in sorted(bundle_dir.glob(pattern)):
            extra.append(path)
            match = re.fullmatch(r"kernel_generated\.cluster(\d+)\.cu", path.name)
            if match:
                cluster_indices.append(int(match.group(1)))
    for basename in ("kernel_generated.full_comb.cu", "kernel_generated.full_seq.cu"):
        path = bundle_dir / basename
        if path.is_file():
            extra.append(path)
    return fixed + extra, cluster_indices


def _first_cluster_index(clusters_tsv: Path) -> int | None:
    if not clusters_tsv.is_file():
        return None
    with clusters_tsv.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            try:
                assign_count = int(row.get("assign_count", "0"))
                index = int(row.get("index", "0"))
            except ValueError:
                continue
            if assign_count > 0:
                return index
    return None


def _check_smoke_metrics(log_path: Path, *, expect_hybrid: bool) -> None:
    text = log_path.read_text(encoding="utf-8")
    metrics = {}
    for key in ("mismatch", "compact_mismatch", "hybrid_mismatch"):
        match = re.search(rf"\b{key}=(-?\d+)\b", text)
        if match:
            metrics[key] = int(match.group(1))
    for key in ("mismatch", "compact_mismatch"):
        if metrics.get(key, 0) != 0:
            raise RuntimeError(f"{log_path.name}: {key}={metrics[key]}")
    if expect_hybrid and metrics.get("hybrid_mismatch", 0) != 0:
        raise RuntimeError(f"{log_path.name}: hybrid_mismatch={metrics['hybrid_mismatch']}")


def _build_smoke_base(
    args: argparse.Namespace, binary_path: Path, *, supports_sequential_steps: bool
) -> list[str]:
    cmd = [
        str(binary_path),
        "--nstates",
        str(args.smoke_nstates),
        "--gpu-reps",
        str(args.smoke_gpu_reps),
        "--cpu-reps",
        str(args.smoke_cpu_reps),
        *args.bench_arg,
    ]
    if supports_sequential_steps:
        cmd.extend(["--sequential-steps", str(args.smoke_sequential_steps)])
    return cmd


def main() -> int:
    args = parse_args()
    bundle_dir = args.bundle_dir.resolve()
    binary_path = bundle_dir / args.binary_name
    obj_dir = args.obj_dir if args.obj_dir.is_absolute() else bundle_dir / args.obj_dir
    smoke_log_dir = (
        args.smoke_log_dir if args.smoke_log_dir.is_absolute() else bundle_dir / args.smoke_log_dir
    )
    bundle_config = _load_bundle_config(bundle_dir)
    launch_backend = str(bundle_config.get("launch_backend", "cuda"))
    execution_backend = _resolve_execution_backend(bundle_config, args.execution_backend)
    # When the requested execution backend differs from what the bundle was originally built for,
    # refresh the gpu_binary_* metadata fields to match the actual backend.
    if execution_backend != str(bundle_config.get("execution_backend", "")):
        bundle_config.update(
            _default_gpu_binary_metadata(
                launch_backend=launch_backend,
                execution_backend=execution_backend,
            )
        )
    rocm_launch_mode = _resolve_rocm_launch_mode(bundle_config, execution_backend)
    build_log = bundle_dir / ("build_hipcc.log" if execution_backend == "rocm_llvm" else "build_nvcc.log")
    if execution_backend == "rocm_llvm":
        effective_compiler_backend = (
            "rocdl_hsaco_native" if rocm_launch_mode == "native-hsaco" else "rocm_bridge_source"
        )
        effective_launcher_backend = (
            "hip_module" if rocm_launch_mode == "native-hsaco" else "hip_runtime"
        )
    elif execution_backend == "cuda_clang_ir":
        effective_compiler_backend = "clang_llvm_ptx"
        effective_launcher_backend = "cuda_driver"
    elif execution_backend == "cuda_vl_ir":
        effective_compiler_backend = "clang_llvm_ptx_vl"
        effective_launcher_backend = "cuda_driver"
    else:
        effective_compiler_backend = str(bundle_config.get("compiler_backend", "nvptx"))
        effective_launcher_backend = str(bundle_config.get("launcher_backend", "cuda_runtime"))

    _require_file(bundle_dir / "bench_kernel.cu", "bench_kernel.cu")
    _require_file(bundle_dir / "kernel_generated.link.cu", "kernel_generated.link.cu")
    _ptx_build_backends = {"cuda_clang_ir", "cuda_vl_ir", "program_json_ir"}
    if (
        bool(bundle_config.get("gpu_binary_required"))
        and execution_backend not in _ptx_build_backends
        and (execution_backend != "rocm_llvm" or rocm_launch_mode == "native-hsaco")
    ):
        gpu_binary_relpath = str(bundle_config.get("gpu_binary_relpath") or "").strip()
        if gpu_binary_relpath:
            _require_file(bundle_dir / gpu_binary_relpath, gpu_binary_relpath)
    if launch_backend == "circt-cubin" and execution_backend not in _ptx_build_backends:
        _require_file(
            bundle_dir / "kernel_generated.full_all.circt_driver.cpp",
            "kernel_generated.full_all.circt_driver.cpp",
        )
    if not args.skip_cpu_ref and _find_cpu_ref_source(bundle_dir) is None:
        args.skip_cpu_ref = True

    if args.clean_obj_dir and obj_dir.exists():
        shutil.rmtree(obj_dir)
    obj_dir.mkdir(parents=True, exist_ok=True)
    build_log.write_text("", encoding="utf-8")

    cuda_sources = _collect_cuda_sources(bundle_dir, launch_backend=launch_backend)
    compiled_rocm_bridge = 0
    compiled_rocm_native = 0
    compiled_clang_ir = 0
    compiled_vl_ir = 0
    rocm_cluster_indices: list[int] = []
    rocm_smoke_env: dict[str, str] | None = None
    clang_ir_smoke_env: dict[str, str] | None = None
    vl_ir_smoke_env: dict[str, str] | None = None
    rocm_bridge_cache_hit = False
    rocm_native_cache_hit = False

    if execution_backend == "rocm_llvm":
        if rocm_launch_mode == "native-hsaco":
            (
                rocm_smoke_env,
                compiled_rocm_native,
                rocm_cluster_indices,
                rocm_native_cache_hit,
            ) = _build_rocm_native_hsaco(
                args=args,
                bundle_dir=bundle_dir,
                binary_path=binary_path,
                obj_dir=obj_dir,
                build_log=build_log,
                bundle_config=bundle_config,
                include_cpu_ref=not args.skip_cpu_ref,
            )
        else:
            (
                rocm_smoke_env,
                compiled_rocm_bridge,
                rocm_cluster_indices,
                rocm_bridge_cache_hit,
            ) = _build_rocm_bridge(
                args=args,
                bundle_dir=bundle_dir,
                binary_path=binary_path,
                obj_dir=obj_dir,
                build_log=build_log,
                cuda_sources=cuda_sources,
                include_cpu_ref=not args.skip_cpu_ref,
            )
    elif execution_backend == "cuda_clang_ir":
        clang_ir_smoke_env, compiled_clang_ir, _ = _build_cuda_clang_ir(
            args=args,
            bundle_dir=bundle_dir,
            binary_path=binary_path,
            obj_dir=obj_dir,
            build_log=build_log,
            bundle_config=bundle_config,
            include_cpu_ref=not args.skip_cpu_ref,
        )
    elif execution_backend == "cuda_vl_ir":
        vl_ir_smoke_env, compiled_vl_ir, _ = _build_cuda_vl_ir(
            args=args,
            bundle_dir=bundle_dir,
            binary_path=binary_path,
            obj_dir=obj_dir,
            build_log=build_log,
            bundle_config=bundle_config,
            include_cpu_ref=not args.skip_cpu_ref,
        )
    elif execution_backend == "program_json_ir":
        vl_ir_smoke_env, compiled_vl_ir, _ = _build_pj_ir(
            args=args,
            bundle_dir=bundle_dir,
            binary_path=binary_path,
            obj_dir=obj_dir,
            build_log=build_log,
            bundle_config=bundle_config,
            include_cpu_ref=not args.skip_cpu_ref,
        )
    else:
        cuda_seq_fallback_applied = _patch_cuda_seq_partition_fallback(bundle_dir)
        if cuda_seq_fallback_applied:
            with build_log.open("a", encoding="utf-8") as fh:
                fh.write("[cuda_seq_partition_fallback] applied=1 mode=full_seq\n\n")
        link_objects: list[Path] = []
        for src in cuda_sources:
            obj = obj_dir / f"{src.name}.o"
            cmd = [
                args.nvcc,
                "-O3",
                "-std=c++17",
                "-rdc=true",
                "-I.",
                *args.nvcc_flag,
                "-c",
                src.name,
                "-o",
                str(obj.relative_to(bundle_dir)),
            ]
            _run_logged(cmd, cwd=bundle_dir, log_path=build_log)
            link_objects.append(obj)

        if launch_backend == "circt-cubin":
            driver_src = _require_file(
                bundle_dir / "kernel_generated.full_all.circt_driver.cpp",
                "kernel_generated.full_all.circt_driver.cpp",
            )
            driver_obj = obj_dir / "kernel_generated.full_all.circt_driver.o"
            driver_cmd = [
                args.nvcc,
                "-O3",
                "-std=c++17",
                "-rdc=true",
                "-I.",
                *args.nvcc_flag,
                "-c",
                driver_src.name,
                "-o",
                str(driver_obj.relative_to(bundle_dir)),
            ]
            _run_logged(driver_cmd, cwd=bundle_dir, log_path=build_log)
            link_objects.append(driver_obj)

        if not args.skip_cpu_ref:
            _cpu_src = _find_cpu_ref_source(bundle_dir)
            if _cpu_src is None:
                raise RuntimeError("CPU reference source not found (kernel_generated.cpu.cpp or *.cpu.cpp)")
            cpu_src = _cpu_src
            cpu_obj = obj_dir / "kernel_generated.cpu.o"
            cpu_cmd = [
                args.cxx,
                "-O3",
                "-std=c++17",
                "-I.",
                *args.cxx_flag,
                "-c",
                cpu_src.name,
                "-o",
                str(cpu_obj.relative_to(bundle_dir)),
            ]
            _run_logged(cpu_cmd, cwd=bundle_dir, log_path=build_log)
            link_objects.append(cpu_obj)

        link_cmd = [
            args.nvcc,
            "-O3",
            "-std=c++17",
            "-rdc=true",
            *args.nvcc_flag,
            *(str(path.relative_to(bundle_dir)) for path in link_objects),
            *(["-lcuda"] if launch_backend == "circt-cubin" else []),
            "-o",
            args.binary_name,
        ]
        _run_logged(link_cmd, cwd=bundle_dir, log_path=build_log)

    print(f"bundle_dir={bundle_dir}")
    print(f"binary={binary_path}")
    print(f"build_log={build_log}")
    print(f"bundle_config={bundle_config['config_path']}")
    print(f"launch_backend={launch_backend}")
    print(f"execution_backend={execution_backend}")
    print(f"rocm_launch_mode={rocm_launch_mode}")
    print(f"compiler_backend={effective_compiler_backend}")
    print(f"launcher_backend={effective_launcher_backend}")
    print(f"gpu_binary_kind={bundle_config.get('gpu_binary_kind', 'embedded_cuda')}")
    print(f"gpu_binary_relpath={bundle_config.get('gpu_binary_relpath', '')}")
    print(f"gpu_binary_env_var={bundle_config.get('gpu_binary_env_var', '')}")
    print(f"compiled_cuda_sources={len(cuda_sources) if execution_backend not in ('cuda_clang_ir', 'cuda_vl_ir', 'program_json_ir', 'rocm_llvm') else 0}")
    print(f"compiled_clang_ir_sources={compiled_clang_ir}")
    print(f"compiled_vl_ir_sources={compiled_vl_ir}")
    print(f"compiled_rocm_bridge={compiled_rocm_bridge}")
    print(f"compiled_rocm_native={compiled_rocm_native}")
    print(f"compiled_rocm_clusters={len(rocm_cluster_indices)}")
    print(f"rocm_bridge_cache_hit={1 if rocm_bridge_cache_hit else 0}")
    print(f"rocm_native_cache_hit={1 if rocm_native_cache_hit else 0}")
    print(
        f"rocm_hipcc_opt_level={args.rocm_hipcc_opt_level if execution_backend == 'rocm_llvm' else ''}"
    )
    print(f"compiled_circt_driver={1 if launch_backend == 'circt-cubin' and execution_backend not in ('cuda_clang_ir', 'cuda_vl_ir', 'program_json_ir') else 0}")
    print(f"compiled_cpu_ref={0 if args.skip_cpu_ref else 1}")

    if not args.run_smoke:
        return 0

    smoke_log_dir.mkdir(parents=True, exist_ok=True)
    smoke_base = _build_smoke_base(
        args,
        binary_path,
        supports_sequential_steps=bool(bundle_config.get("supports_sequential_steps", True)),
    )
    if execution_backend == "rocm_llvm":
        smoke_env: dict[str, str] | None = rocm_smoke_env
    elif execution_backend == "cuda_clang_ir":
        smoke_env = clang_ir_smoke_env or None
    elif execution_backend in ("cuda_vl_ir", "program_json_ir"):
        smoke_env = vl_ir_smoke_env or None
    else:
        smoke_env = _gpu_binary_env(bundle_dir, bundle_config) or None

    off_log = smoke_log_dir / "smoke_off.log"
    off_log.write_text("", encoding="utf-8")
    _run_logged(smoke_base, cwd=bundle_dir, log_path=off_log, env=smoke_env)
    _check_smoke_metrics(off_log, expect_hybrid=False)
    print(f"smoke_off_log={off_log}")

    cluster_index = args.smoke_cluster_index
    if cluster_index is None:
        cluster_index = _first_cluster_index(bundle_dir / "kernel_generated.clusters.tsv")
    supports_single_cluster_smoke = bool(bundle_config.get("supports_single_cluster_smoke", True))
    if not supports_single_cluster_smoke:
        print("smoke_single_cluster=skipped")
        reason = f"launch_backend:{launch_backend}"
        print(f"smoke_single_cluster_reason={reason}")
        return 0
    if cluster_index is None:
        print("smoke_single_cluster=skipped")
        return 0

    cluster_log = smoke_log_dir / "smoke_single_cluster.log"
    cluster_log.write_text("", encoding="utf-8")
    cluster_cmd = smoke_base + [
        "--hybrid-mode",
        "single-cluster",
        "--hybrid-cluster-index",
        str(cluster_index),
    ]
    _run_logged(cluster_cmd, cwd=bundle_dir, log_path=cluster_log, env=smoke_env)
    _check_smoke_metrics(cluster_log, expect_hybrid=True)
    print(f"smoke_single_cluster_log={cluster_log}")
    print(f"smoke_single_cluster_index={cluster_index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
