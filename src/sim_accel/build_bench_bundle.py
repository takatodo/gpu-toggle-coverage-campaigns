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
from pathlib import Path

BUNDLE_CONFIG_NAME = "sim_accel_bundle_config.json"
EXECUTION_BACKENDS = ("auto", "cuda_source", "cuda_circt_cubin", "rocm_llvm")
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
    return parser.parse_args()


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise RuntimeError(f"Missing {label}: {path}")
    return path


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
        "    const uint32_t partition_count = sim_accel_eval_partition_count();",
        "    if (partition_count == 0U) {",
        *fallback_ops,
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
        cpu_src = bundle_dir / "kernel_generated.cpu.cpp"
        if cpu_src.is_file():
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
        cpu_src = bundle_dir / "kernel_generated.cpu.cpp"
        if cpu_src.is_file():
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
    rocm_launch_mode = _resolve_rocm_launch_mode(bundle_config, execution_backend)
    build_log = bundle_dir / ("build_hipcc.log" if execution_backend == "rocm_llvm" else "build_nvcc.log")
    effective_compiler_backend = (
        (
            "rocdl_hsaco_native"
            if execution_backend == "rocm_llvm" and rocm_launch_mode == "native-hsaco"
            else "rocm_bridge_source"
        )
        if execution_backend == "rocm_llvm"
        else str(bundle_config.get("compiler_backend", "nvptx"))
    )
    effective_launcher_backend = (
        (
            "hip_module"
            if execution_backend == "rocm_llvm" and rocm_launch_mode == "native-hsaco"
            else "hip_runtime"
        )
        if execution_backend == "rocm_llvm"
        else str(bundle_config.get("launcher_backend", "cuda_runtime"))
    )

    _require_file(bundle_dir / "bench_kernel.cu", "bench_kernel.cu")
    _require_file(bundle_dir / "kernel_generated.link.cu", "kernel_generated.link.cu")
    if (
        bool(bundle_config.get("gpu_binary_required"))
        and (execution_backend != "rocm_llvm" or rocm_launch_mode == "native-hsaco")
    ):
        gpu_binary_relpath = str(bundle_config.get("gpu_binary_relpath") or "").strip()
        if gpu_binary_relpath:
            _require_file(bundle_dir / gpu_binary_relpath, gpu_binary_relpath)
    if launch_backend == "circt-cubin":
        _require_file(
            bundle_dir / "kernel_generated.full_all.circt_driver.cpp",
            "kernel_generated.full_all.circt_driver.cpp",
        )
    if not args.skip_cpu_ref and not (bundle_dir / "kernel_generated.cpu.cpp").is_file():
        args.skip_cpu_ref = True

    if args.clean_obj_dir and obj_dir.exists():
        shutil.rmtree(obj_dir)
    obj_dir.mkdir(parents=True, exist_ok=True)
    build_log.write_text("", encoding="utf-8")

    cuda_sources = _collect_cuda_sources(bundle_dir, launch_backend=launch_backend)
    compiled_rocm_bridge = 0
    compiled_rocm_native = 0
    rocm_cluster_indices: list[int] = []
    rocm_smoke_env: dict[str, str] | None = None
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
            cpu_src = _require_file(bundle_dir / "kernel_generated.cpu.cpp", "kernel_generated.cpu.cpp")
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
    print(f"compiled_cuda_sources={len(cuda_sources)}")
    print(f"compiled_rocm_bridge={compiled_rocm_bridge}")
    print(f"compiled_rocm_native={compiled_rocm_native}")
    print(f"compiled_rocm_clusters={len(rocm_cluster_indices)}")
    print(f"rocm_bridge_cache_hit={1 if rocm_bridge_cache_hit else 0}")
    print(f"rocm_native_cache_hit={1 if rocm_native_cache_hit else 0}")
    print(
        f"rocm_hipcc_opt_level={args.rocm_hipcc_opt_level if execution_backend == 'rocm_llvm' else ''}"
    )
    print(f"compiled_circt_driver={1 if launch_backend == 'circt-cubin' else 0}")
    print(f"compiled_cpu_ref={0 if args.skip_cpu_ref else 1}")

    if not args.run_smoke:
        return 0

    smoke_log_dir.mkdir(parents=True, exist_ok=True)
    smoke_base = _build_smoke_base(
        args,
        binary_path,
        supports_sequential_steps=bool(bundle_config.get("supports_sequential_steps", True)),
    )
    smoke_env: dict[str, str] | None = (
        rocm_smoke_env
        if execution_backend == "rocm_llvm"
        else (_gpu_binary_env(bundle_dir, bundle_config) or None)
    )

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
