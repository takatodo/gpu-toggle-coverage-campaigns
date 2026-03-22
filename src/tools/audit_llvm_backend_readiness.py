#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
CUDA_OPT_DIR = ROOT_DIR / "src" / "sim_accel"
VERILATOR_BENCH_HELPERS = ROOT_DIR / "third_party" / "verilator" / "bin" / "verilator_sim_accel_bench.d"
DEFAULT_WORK_DIR = Path("/tmp/audit_llvm_backend_readiness")

README = CUDA_OPT_DIR / "README.md"
FULL_KERNEL_FUSER = CUDA_OPT_DIR / "full_kernel_fuser.py"
PREPARE_BUNDLE = CUDA_OPT_DIR / "prepare_bench_bundle.py"
RUN_SLICE_BASELINE = SCRIPT_DIR.parent / "runners" / "run_opentitan_tlul_slice_gpu_baseline.py"
GPU_RUNTIME_POLICY = SCRIPT_DIR / "gpu_runtime_batch_policy.py"
CAPTURE_RUNTIME_LOG = SCRIPT_DIR / "capture_runtime_log.py"
CACHE_HELPERS = VERILATOR_BENCH_HELPERS / "05_cache_materialize_helpers.sh"
BUILD_HELPERS = VERILATOR_BENCH_HELPERS / "07_build_run_phase.sh"
BUILD_BUNDLE = CUDA_OPT_DIR / "build_bench_bundle.py"
MEASURE_BENCH_BACKENDS = CUDA_OPT_DIR / "measure_bench_backends.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _tool_status(name: str) -> dict[str, Any]:
    path = shutil.which(name)
    return {"name": name, "found": bool(path), "path": path}


def _wsl_rocm_bridge_state() -> dict[str, Any]:
    preload = os.getenv("LD_PRELOAD", "")
    return {
        "dev_dxg_exists": os.path.exists("/dev/dxg"),
        "kfd_exists": os.path.exists("/dev/kfd"),
        "hsa_override_gfx_version": os.getenv("HSA_OVERRIDE_GFX_VERSION", ""),
        "ld_preload": preload,
        "hip_preload_enabled": "libamdhip64.so" in preload,
        "rocm_path": os.getenv("ROCM_PATH", ""),
        "rocm_wsl_bridge_ready": (
            os.path.exists("/dev/dxg")
            and bool(os.getenv("HSA_OVERRIDE_GFX_VERSION"))
            and "libamdhip64.so" in preload
        ),
    }


def _detect_pipeline_status(work_dir: Path) -> dict[str, Any]:
    readme = _read(README) if README.is_file() else ""
    fuser = _read(FULL_KERNEL_FUSER) if FULL_KERNEL_FUSER.is_file() else ""
    prepare = _read(PREPARE_BUNDLE) if PREPARE_BUNDLE.is_file() else ""
    slice = _read(RUN_SLICE_BASELINE) if RUN_SLICE_BASELINE.is_file() else ""
    policy = _read(GPU_RUNTIME_POLICY) if GPU_RUNTIME_POLICY.is_file() else ""
    runtime_log = _read(CAPTURE_RUNTIME_LOG) if CAPTURE_RUNTIME_LOG.is_file() else ""
    cache_helpers = _read(CACHE_HELPERS) if CACHE_HELPERS.is_file() else ""
    build_bundle = _read(BUILD_BUNDLE) if BUILD_BUNDLE.is_file() else ""
    measure_backends = _read(MEASURE_BENCH_BACKENDS) if MEASURE_BENCH_BACKENDS.is_file() else ""
    build_helpers = _read(BUILD_HELPERS) if BUILD_HELPERS.is_file() else ""
    smoke_summary = _load_optional_json(work_dir / "rocm_llvm_hsaco_smoke.json")
    sim_accel_smoke_summary = _load_optional_json(work_dir / "rocm_sim_accel_launch_all_smoke.json")
    build_bundle_smoke_summary = _load_optional_json(work_dir / "rocm_build_bench_bundle_smoke.json")
    wrapper_smoke_summary = _load_optional_json(work_dir / "rocm_verilator_sim_accel_bench_smoke.json")
    wrapper_single_cluster_smoke_summary = _load_optional_json(work_dir / "rocm_verilator_sim_accel_bench_single_cluster_smoke.json")
    native_hsaco_mainline_probe_summary = _load_optional_json(work_dir / "rocm_native_hsaco_mainline_probe.json")
    mainline_runner_smoke_summary = _load_optional_json(work_dir / "rocm_mainline_runner_smoke.json")
    mainline_runner_single_cluster_smoke_summary = _load_optional_json(
        work_dir / "rocm_mainline_runner_single_cluster_smoke.json"
    )
    mainline_runner_single_partition_smoke_summary = _load_optional_json(
        work_dir / "rocm_mainline_runner_single_partition_smoke.json"
    )
    structured_second_wave_waiver_summary = _load_optional_json(
        work_dir / "rocm_structured_second_wave_semantic_gap_waiver.json"
    )
    mainline_structured_bundle_probe_summary = _load_optional_json(
        work_dir / "rocm_mainline_structured_bundle_probe.json"
    )
    rtlmeter_runner_smoke_summary = _load_optional_json(work_dir / "rocm_rtlmeter_runner_smoke.json")
    rtlmeter_runner_single_cluster_smoke_summary = _load_optional_json(work_dir / "rocm_rtlmeter_runner_single_cluster_smoke.json")
    native_general_bundle_smoke_summary = _load_optional_json(work_dir / "rocm_native_general_bundle_smoke.json")

    llvm_nvptx = bool(re.search(r'nvptx64-nvidia-cuda', fuser))
    llvm_amdgpu_lowering = bool(re.search(r'target triple = "amdgcn|--target=amdgcn|-march=amdgpu', fuser))
    llvm_explicit_selector = "--llvm-backend-target" in fuser
    ptx_emit = "--emit-ptx" in readme and "ptxas" in readme
    launch_choices = sorted(set(re.findall(r'choices=\(([^)]*?)\)', prepare)))
    launch_backend_circt = "circt-cubin" in prepare
    launch_backend_cuda = '"cuda"' in prepare or "'cuda'" in prepare
    prepare_has_execution_backend = "--execution-backend" in prepare
    build_has_execution_backend = "--execution-backend" in build_bundle
    prepare_has_generic_gpu_binary_abi = "SIM_ACCEL_GPU_BINARY_PATH" in prepare and "gpu_binary_env_var" in prepare
    build_has_generic_gpu_binary_abi = "gpu_binary_env_var" in build_bundle and "_gpu_binary_env(" in build_bundle
    measure_uses_generic_gpu_binary_abi = "gpu_binary_env_var" in measure_backends
    standalone_rocm_smoke_pass = bool(smoke_summary.get("pass"))
    sim_accel_launch_all_rocm_smoke_pass = bool(sim_accel_smoke_summary.get("pass"))
    build_bench_bundle_rocm_smoke_pass = bool(build_bundle_smoke_summary.get("pass"))
    build_bench_bundle_single_cluster_rocm_smoke_pass = bool(
        build_bundle_smoke_summary.get("single_cluster_pass")
    )
    wrapper_rocm_smoke_pass = bool(wrapper_smoke_summary.get("pass"))
    wrapper_rocm_smoke_reached_run = bool(wrapper_smoke_summary.get("wrapper_reached_run"))
    wrapper_single_cluster_rocm_smoke_pass = bool(wrapper_single_cluster_smoke_summary.get("pass"))
    native_hsaco_mainline_probe_pass = bool(native_hsaco_mainline_probe_summary.get("pass"))
    native_hsaco_mainline_launch_reached = (
        str(native_hsaco_mainline_probe_summary.get("run", {}).get("runtime_gpu_api") or "") == "hip"
    )
    native_hsaco_mainline_mismatch = int(
        native_hsaco_mainline_probe_summary.get("run", {}).get("mismatch") or 0
    )
    native_hsaco_mainline_first_mismatch_var_name = str(
        native_hsaco_mainline_probe_summary.get("run", {}).get("first_mismatch_var_name") or ""
    )
    mainline_runner_rocm_smoke_pass = bool(mainline_runner_smoke_summary.get("pass"))
    mainline_runner_native_hsaco_mode = bool(mainline_runner_smoke_summary.get("native_hsaco_mode"))
    mainline_runner_single_cluster_rocm_smoke_pass = bool(
        mainline_runner_single_cluster_smoke_summary.get("pass")
    )
    mainline_runner_single_partition_rocm_smoke_pass = bool(
        mainline_runner_single_partition_smoke_summary.get("pass")
    )
    mainline_runner_single_cluster_native_hsaco_mode = (
        "rocm_launch_mode=native-hsaco"
        in str(mainline_runner_single_cluster_smoke_summary.get("runner_run", {}).get("stdout") or "")
    )
    mainline_runner_single_partition_native_hsaco_mode = (
        "rocm_launch_mode=native-hsaco"
        in str(mainline_runner_single_partition_smoke_summary.get("runner_run", {}).get("stdout") or "")
    )
    mainline_runner_single_cluster_next_blocker = str(
        mainline_runner_single_cluster_smoke_summary.get("next_blocker") or ""
    )
    mainline_runner_single_partition_next_blocker = str(
        mainline_runner_single_partition_smoke_summary.get("next_blocker") or ""
    )
    structured_second_wave_waiver_canonicalized = bool(
        structured_second_wave_waiver_summary.get("waiver_canonicalized")
    )
    mainline_structured_bundle_probe_next_blocker = str(
        mainline_structured_bundle_probe_summary.get("next_blocker") or ""
    )
    rtlmeter_runner_rocm_smoke_pass = bool(rtlmeter_runner_smoke_summary.get("pass"))
    rtlmeter_runner_native_hsaco_mode = bool(rtlmeter_runner_smoke_summary.get("native_hsaco_mode"))
    rtlmeter_runner_next_blocker = str(rtlmeter_runner_smoke_summary.get("next_blocker") or "")
    rtlmeter_runner_single_cluster_rocm_smoke_pass = bool(
        rtlmeter_runner_single_cluster_smoke_summary.get("pass")
    )
    rtlmeter_runner_single_cluster_next_blocker = str(
        rtlmeter_runner_single_cluster_smoke_summary.get("next_blocker") or ""
    )
    native_general_bundle_off_pass = bool(
        ((native_general_bundle_smoke_summary.get("cases") or {}).get("off") or {}).get("pass")
    )
    native_general_bundle_single_cluster_soft_accepted = bool(
        ((native_general_bundle_smoke_summary.get("cases") or {}).get("single_cluster") or {}).get(
            "soft_accepted"
        )
    )
    native_general_bundle_single_partition_soft_accepted = bool(
        ((native_general_bundle_smoke_summary.get("cases") or {}).get("single_partition") or {}).get(
            "soft_accepted"
        )
    )
    native_general_bundle_waiver_canonicalized = bool(
        native_general_bundle_smoke_summary.get("waiver_canonicalized")
    )
    native_general_bundle_next_blocker = str(
        native_general_bundle_smoke_summary.get("next_blocker") or ""
    )
    slice_uses_cuda_bundle = 'bundle_launch_backend = "cuda"' in slice
    runtime_detects_rocm_bridge = "rocm_wsl_bridge" in policy and "rocm_wsl_bridge" in runtime_log
    arch_detect_uses_nvidia_smi = "nvidia-smi" in cache_helpers
    bench_wrapper_detects_rocm_bridge = "detect_rocm_wsl_bridge_backend" in cache_helpers
    bench_wrapper_has_explicit_backend_selection = "SIM_ACCEL_EXECUTION_BACKEND_SELECTED" in cache_helpers
    bench_wrapper_rejects_unimplemented_backend = "Unsupported execution backend for verilator_sim_accel_bench" in build_helpers

    compiler_backend = "nvptx_only"
    if llvm_explicit_selector:
        compiler_backend = "nvptx_only_explicit_selector"
    if prepare_has_generic_gpu_binary_abi and build_has_generic_gpu_binary_abi:
        compiler_backend = "nvptx_only_generic_gpu_binary_abi"
    if llvm_amdgpu_lowering:
        compiler_backend = "mixed_or_amdgpu_present"

    launcher_backend = "cuda_only"
    if launch_backend_circt and launch_backend_cuda:
        launcher_backend = "cuda_or_cuda_driver_bundle"

    return {
        "compiler_backend_status": compiler_backend,
        "llvm_nvptx_evidence": llvm_nvptx,
        "llvm_amdgpu_evidence": llvm_amdgpu_lowering,
        "llvm_explicit_selector": llvm_explicit_selector,
        "ptx_emit_documented": ptx_emit,
        "launcher_backend_status": launcher_backend,
        "prepare_bundle_supports_circt_cubin": launch_backend_circt,
        "prepare_bundle_supports_cuda": launch_backend_cuda,
        "prepare_bundle_has_execution_backend": prepare_has_execution_backend,
        "build_bundle_has_execution_backend": build_has_execution_backend,
        "prepare_bundle_has_generic_gpu_binary_abi": prepare_has_generic_gpu_binary_abi,
        "build_bundle_has_generic_gpu_binary_abi": build_has_generic_gpu_binary_abi,
        "measure_uses_generic_gpu_binary_abi": measure_uses_generic_gpu_binary_abi,
        "standalone_rocm_smoke_pass": standalone_rocm_smoke_pass,
        "sim_accel_launch_all_rocm_smoke_pass": sim_accel_launch_all_rocm_smoke_pass,
        "build_bench_bundle_rocm_smoke_pass": build_bench_bundle_rocm_smoke_pass,
        "build_bench_bundle_single_cluster_rocm_smoke_pass": build_bench_bundle_single_cluster_rocm_smoke_pass,
        "wrapper_rocm_smoke_pass": wrapper_rocm_smoke_pass,
        "wrapper_rocm_smoke_reached_run": wrapper_rocm_smoke_reached_run,
        "wrapper_single_cluster_rocm_smoke_pass": wrapper_single_cluster_rocm_smoke_pass,
        "native_hsaco_mainline_probe_pass": native_hsaco_mainline_probe_pass,
        "native_hsaco_mainline_launch_reached": native_hsaco_mainline_launch_reached,
        "native_hsaco_mainline_mismatch": native_hsaco_mainline_mismatch,
        "native_hsaco_mainline_first_mismatch_var_name": native_hsaco_mainline_first_mismatch_var_name,
        "mainline_runner_rocm_smoke_pass": mainline_runner_rocm_smoke_pass,
        "mainline_runner_native_hsaco_mode": mainline_runner_native_hsaco_mode,
        "mainline_runner_single_cluster_rocm_smoke_pass": mainline_runner_single_cluster_rocm_smoke_pass,
        "mainline_runner_single_partition_rocm_smoke_pass": mainline_runner_single_partition_rocm_smoke_pass,
        "mainline_runner_single_cluster_native_hsaco_mode": mainline_runner_single_cluster_native_hsaco_mode,
        "mainline_runner_single_partition_native_hsaco_mode": mainline_runner_single_partition_native_hsaco_mode,
        "mainline_runner_single_cluster_next_blocker": mainline_runner_single_cluster_next_blocker,
        "mainline_runner_single_partition_next_blocker": mainline_runner_single_partition_next_blocker,
        "structured_second_wave_waiver_canonicalized": structured_second_wave_waiver_canonicalized,
        "mainline_structured_bundle_probe_next_blocker": mainline_structured_bundle_probe_next_blocker,
        "rtlmeter_runner_rocm_smoke_pass": rtlmeter_runner_rocm_smoke_pass,
        "rtlmeter_runner_native_hsaco_mode": rtlmeter_runner_native_hsaco_mode,
        "rtlmeter_runner_next_blocker": rtlmeter_runner_next_blocker,
        "rtlmeter_runner_single_cluster_rocm_smoke_pass": rtlmeter_runner_single_cluster_rocm_smoke_pass,
        "rtlmeter_runner_single_cluster_next_blocker": rtlmeter_runner_single_cluster_next_blocker,
        "native_general_bundle_off_pass": native_general_bundle_off_pass,
        "native_general_bundle_single_cluster_soft_accepted": native_general_bundle_single_cluster_soft_accepted,
        "native_general_bundle_single_partition_soft_accepted": native_general_bundle_single_partition_soft_accepted,
        "native_general_bundle_waiver_canonicalized": native_general_bundle_waiver_canonicalized,
        "native_general_bundle_next_blocker": native_general_bundle_next_blocker,
        "slice_runner_uses_cuda_bundle_alias": slice_uses_cuda_bundle,
        "runtime_detects_rocm_bridge": runtime_detects_rocm_bridge,
        "arch_detect_uses_nvidia_smi": arch_detect_uses_nvidia_smi,
        "bench_wrapper_detects_rocm_bridge": bench_wrapper_detects_rocm_bridge,
        "bench_wrapper_has_explicit_backend_selection": bench_wrapper_has_explicit_backend_selection,
        "bench_wrapper_rejects_unimplemented_backend": bench_wrapper_rejects_unimplemented_backend,
        "evidence_paths": {
            "readme": str(README),
            "full_kernel_fuser": str(FULL_KERNEL_FUSER),
            "prepare_bench_bundle": str(PREPARE_BUNDLE),
            "build_bench_bundle": str(BUILD_BUNDLE),
            "run_opentitan_tlul_slice_gpu_baseline": str(RUN_SLICE_BASELINE),
            "gpu_runtime_batch_policy": str(GPU_RUNTIME_POLICY),
            "capture_runtime_log": str(CAPTURE_RUNTIME_LOG),
            "cache_helpers": str(CACHE_HELPERS),
            "build_helpers": str(BUILD_HELPERS),
            "measure_bench_backends": str(MEASURE_BENCH_BACKENDS),
            "rocm_llvm_hsaco_smoke": str(work_dir / "rocm_llvm_hsaco_smoke.json"),
            "rocm_sim_accel_launch_all_smoke": str(work_dir / "rocm_sim_accel_launch_all_smoke.json"),
            "rocm_build_bench_bundle_smoke": str(work_dir / "rocm_build_bench_bundle_smoke.json"),
            "rocm_wrapper_smoke": str(work_dir / "rocm_verilator_sim_accel_bench_smoke.json"),
            "rocm_wrapper_single_cluster_smoke": str(work_dir / "rocm_verilator_sim_accel_bench_single_cluster_smoke.json"),
            "rocm_native_hsaco_mainline_probe": str(work_dir / "rocm_native_hsaco_mainline_probe.json"),
            "rocm_mainline_runner_smoke": str(work_dir / "rocm_mainline_runner_smoke.json"),
            "rocm_mainline_runner_single_cluster_smoke": str(work_dir / "rocm_mainline_runner_single_cluster_smoke.json"),
            "rocm_mainline_runner_single_partition_smoke": str(work_dir / "rocm_mainline_runner_single_partition_smoke.json"),
            "rocm_structured_second_wave_semantic_gap_waiver": str(
                work_dir / "rocm_structured_second_wave_semantic_gap_waiver.json"
            ),
            "rocm_mainline_structured_bundle_probe": str(work_dir / "rocm_mainline_structured_bundle_probe.json"),
            "rocm_rtlmeter_runner_smoke": str(work_dir / "rocm_rtlmeter_runner_smoke.json"),
            "rocm_rtlmeter_runner_single_cluster_smoke": str(work_dir / "rocm_rtlmeter_runner_single_cluster_smoke.json"),
            "rocm_native_general_bundle_smoke": str(work_dir / "rocm_native_general_bundle_smoke.json"),
        },
    }


def _classify_overall(env_state: dict[str, Any], pipeline: dict[str, Any]) -> dict[str, str]:
    environment_status = (
        "rocm_wsl_bridge_visible" if env_state["rocm_wsl_bridge_ready"] else "gpu_visibility_unconfirmed"
    )
    portability_status = "cuda_fixed"
    if pipeline["compiler_backend_status"] in {
        "nvptx_only_explicit_selector",
        "nvptx_only_generic_gpu_binary_abi",
        "mixed_or_amdgpu_present",
    }:
        portability_status = "partially_abstracted"
    if pipeline.get("standalone_rocm_smoke_pass"):
        portability_status = "standalone_rocm_lane_proven"
    if pipeline.get("sim_accel_launch_all_rocm_smoke_pass"):
        portability_status = "sim_accel_launch_all_standalone_proven"
    if pipeline.get("build_bench_bundle_rocm_smoke_pass"):
        portability_status = "build_bench_bundle_rocm_bridge_proven"
    if pipeline.get("wrapper_rocm_smoke_reached_run"):
        portability_status = "wrapper_rocm_bridge_runs_functional_mismatch"
    if pipeline.get("wrapper_rocm_smoke_pass"):
        portability_status = "wrapper_rocm_bridge_proven"
    if pipeline.get("mainline_runner_rocm_smoke_pass"):
        portability_status = "mainline_runner_rocm_bridge_proven"
    if pipeline.get("rtlmeter_runner_rocm_smoke_pass"):
        portability_status = "rtlmeter_runner_rocm_bridge_proven"
    if pipeline.get("wrapper_single_cluster_rocm_smoke_pass"):
        portability_status = "wrapper_single_cluster_rocm_bridge_proven"
    if pipeline.get("build_bench_bundle_single_cluster_rocm_smoke_pass"):
        portability_status = "build_bench_bundle_single_cluster_rocm_bridge_proven"
    if pipeline.get("rtlmeter_runner_single_cluster_rocm_smoke_pass"):
        portability_status = "rtlmeter_runner_single_cluster_rocm_bridge_proven"
    if (
        pipeline.get("mainline_runner_single_cluster_rocm_smoke_pass")
        and pipeline.get("mainline_runner_single_partition_rocm_smoke_pass")
    ):
        portability_status = "mainline_second_wave_rocm_bridge_proven_with_semantic_gap_waiver"
    if pipeline.get("structured_second_wave_waiver_canonicalized"):
        portability_status = "mainline_second_wave_rocm_bridge_canonicalized"
    if pipeline.get("native_hsaco_mainline_launch_reached"):
        portability_status = "native_hsaco_mainline_launch_proven_functional_mismatch"
    if pipeline.get("native_hsaco_mainline_probe_pass"):
        portability_status = "native_hsaco_mainline_proven"
    if pipeline.get("mainline_runner_rocm_smoke_pass") and pipeline.get("mainline_runner_native_hsaco_mode"):
        portability_status = "native_hsaco_mainline_off_proven"
    if (
        pipeline.get("mainline_runner_single_cluster_rocm_smoke_pass")
        and pipeline.get("mainline_runner_single_partition_rocm_smoke_pass")
        and pipeline.get("mainline_runner_single_cluster_native_hsaco_mode")
        and pipeline.get("mainline_runner_single_partition_native_hsaco_mode")
    ):
        portability_status = "native_hsaco_second_wave_proven_with_semantic_gap_waiver"
    if (
        pipeline.get("structured_second_wave_waiver_canonicalized")
        and pipeline.get("mainline_runner_single_cluster_native_hsaco_mode")
        and pipeline.get("mainline_runner_single_partition_native_hsaco_mode")
    ):
        portability_status = "native_hsaco_second_wave_canonicalized"
    if pipeline.get("rtlmeter_runner_rocm_smoke_pass") and pipeline.get("rtlmeter_runner_native_hsaco_mode"):
        portability_status = "native_hsaco_rtlmeter_runner_proven"
    if pipeline.get("native_general_bundle_off_pass"):
        portability_status = "native_hsaco_general_bundle_off_proven"
    if pipeline.get("native_general_bundle_waiver_canonicalized"):
        portability_status = "native_hsaco_general_bundle_second_wave_canonicalized"
    if (
        pipeline.get("rtlmeter_runner_rocm_smoke_pass")
        and pipeline.get("rtlmeter_runner_native_hsaco_mode")
        and pipeline.get("native_general_bundle_waiver_canonicalized")
    ):
        portability_status = "native_hsaco_scope_limited_portability_complete"
    next_blocker = (
        "launch_runtime_and_codegen_still_assume_nvptx_ptxas_nvcc"
        if portability_status == "cuda_fixed"
        else "remaining_backend_abstraction"
    )
    if pipeline.get("standalone_rocm_smoke_pass"):
        next_blocker = "integrate_standalone_rocm_smoke_into_sim_accel_bundle"
    if pipeline.get("sim_accel_launch_all_rocm_smoke_pass"):
        next_blocker = "integrate_rocm_launch_all_smoke_into_build_bench_bundle"
    if pipeline.get("build_bench_bundle_rocm_smoke_pass"):
        next_blocker = "integrate_rocm_bridge_into_verilator_sim_accel_bench_wrapper"
    if pipeline.get("wrapper_rocm_smoke_reached_run"):
        next_blocker = "fix_wrapper_generated_launch_all_functional_mismatch"
    if pipeline.get("wrapper_rocm_smoke_pass"):
        next_blocker = "promote_wrapper_rocm_bridge_into_mainline_runner_validation"
    if pipeline.get("mainline_runner_rocm_smoke_pass"):
        next_blocker = "promote_rocm_bridge_into_rtlmeter_runner_validation"
    if pipeline.get("rtlmeter_runner_rocm_smoke_pass"):
        next_blocker = "open_partition_cluster_second_wave_or_promote_true_hsaco_mainline"
    if pipeline.get("wrapper_single_cluster_rocm_smoke_pass"):
        next_blocker = "promote_rocm_single_cluster_into_bundle_and_runner_validation"
    if pipeline.get("build_bench_bundle_single_cluster_rocm_smoke_pass"):
        next_blocker = "promote_rocm_single_cluster_into_mainline_and_rtlmeter_runner_validation"
    if pipeline.get("rtlmeter_runner_single_cluster_rocm_smoke_pass"):
        next_blocker = "open_partition_cluster_second_wave_or_promote_true_hsaco_mainline"
    if (
        pipeline.get("mainline_runner_single_cluster_rocm_smoke_pass")
        and pipeline.get("mainline_runner_single_partition_rocm_smoke_pass")
    ):
        next_blocker = "canonicalize_structured_second_wave_semantic_gap_waiver"
    if pipeline.get("rtlmeter_runner_single_cluster_next_blocker") == "select_cluster_sane_rtlmeter_single_cluster_target":
        next_blocker = "select_cluster_sane_rtlmeter_single_cluster_target"
    if pipeline.get("mainline_structured_bundle_probe_next_blocker") == "structured_bundle_generation_missing_for_mainline_second_wave":
        next_blocker = "structured_bundle_generation_missing_for_mainline_second_wave"
    if pipeline.get("mainline_runner_single_cluster_next_blocker") == "select_cluster_sane_mainline_single_cluster_target":
        next_blocker = "select_cluster_sane_mainline_single_cluster_target"
    if pipeline.get("mainline_runner_single_cluster_next_blocker") == "fix_rocm_mainline_runner_single_cluster_launch_error":
        next_blocker = "fix_rocm_mainline_runner_single_cluster_launch_error"
    if pipeline.get("mainline_runner_single_cluster_next_blocker") == "single_cluster_semantic_gap_missing_seq_commit":
        next_blocker = "single_cluster_semantic_gap_missing_seq_commit"
    if pipeline.get("mainline_runner_single_partition_next_blocker") == "single_partition_semantic_gap_missing_seq_commit":
        next_blocker = "structured_second_wave_semantic_gap_missing_seq_commit"
    if pipeline.get("mainline_runner_single_cluster_next_blocker") == "canonicalize_structured_second_wave_semantic_gap_waiver":
        next_blocker = "canonicalize_structured_second_wave_semantic_gap_waiver"
    if pipeline.get("mainline_runner_single_partition_next_blocker") == "canonicalize_structured_second_wave_semantic_gap_waiver":
        next_blocker = "canonicalize_structured_second_wave_semantic_gap_waiver"
    if pipeline.get("mainline_runner_single_cluster_next_blocker") == "fix_rocm_mainline_runner_single_cluster_hybrid_mismatch":
        next_blocker = "fix_rocm_mainline_runner_single_cluster_hybrid_mismatch"
    if pipeline.get("structured_second_wave_waiver_canonicalized"):
        next_blocker = "promote_true_hsaco_mainline"
    if pipeline.get("native_hsaco_mainline_launch_reached"):
        next_blocker = "fix_native_hsaco_full_all_semantic_mismatch"
    if pipeline.get("native_hsaco_mainline_probe_pass"):
        next_blocker = "integrate_native_hsaco_into_build_bench_bundle_and_wrapper"
    if pipeline.get("mainline_runner_rocm_smoke_pass") and pipeline.get("mainline_runner_native_hsaco_mode"):
        next_blocker = "promote_native_hsaco_into_wrapper_and_second_wave"
    if (
        pipeline.get("mainline_runner_single_cluster_rocm_smoke_pass")
        and pipeline.get("mainline_runner_single_partition_rocm_smoke_pass")
        and pipeline.get("mainline_runner_single_cluster_native_hsaco_mode")
        and pipeline.get("mainline_runner_single_partition_native_hsaco_mode")
    ):
        next_blocker = "canonicalize_native_hsaco_second_wave_semantic_gap_waiver"
    if (
        pipeline.get("structured_second_wave_waiver_canonicalized")
        and pipeline.get("mainline_runner_single_cluster_native_hsaco_mode")
        and pipeline.get("mainline_runner_single_partition_native_hsaco_mode")
    ):
        next_blocker = "promote_native_hsaco_into_rtlmeter_runner_and_general_bundle_flows"
    if pipeline.get("rtlmeter_runner_rocm_smoke_pass") and pipeline.get("rtlmeter_runner_native_hsaco_mode"):
        next_blocker = "promote_native_hsaco_into_general_bundle_flows"
    if pipeline.get("rtlmeter_runner_next_blocker") == "fix_native_hsaco_rtlmeter_launch_all_illegal_state":
        next_blocker = "fix_native_hsaco_rtlmeter_launch_all_illegal_state"
    if pipeline.get("rtlmeter_runner_next_blocker") == "fix_native_hsaco_rtlmeter_semantic_mismatch":
        next_blocker = "fix_native_hsaco_rtlmeter_semantic_mismatch"
    if pipeline.get("native_general_bundle_off_pass"):
        next_blocker = "canonicalize_native_hsaco_general_bundle_second_wave_semantic_gap_waiver"
    if pipeline.get("native_general_bundle_next_blocker") == "general_bundle_native_second_wave_semantic_gap_waiver_already_canonicalized":
        next_blocker = "resume_gpro_coverage_improvement_and_scope_expansion"
    if (
        pipeline.get("rtlmeter_runner_rocm_smoke_pass")
        and pipeline.get("rtlmeter_runner_native_hsaco_mode")
        and pipeline.get("native_general_bundle_waiver_canonicalized")
    ):
        next_blocker = "resume_gpro_coverage_improvement_and_scope_expansion"
    return {
        "environment_status": environment_status,
        "llvm_backend_status": pipeline["compiler_backend_status"],
        "runtime_launcher_status": pipeline["launcher_backend_status"],
        "portability_status": portability_status,
        "next_blocker": next_blocker,
    }


def _write_outputs(payload: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "llvm_backend_readiness.json"
    md_path = out_dir / "llvm_backend_readiness.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = payload["summary"]
    env_state = payload["environment"]
    lines = [
        "# LLVM Backend Readiness",
        "",
        f"- environment_status: `{summary['environment_status']}`",
        f"- llvm_backend_status: `{summary['llvm_backend_status']}`",
        f"- runtime_launcher_status: `{summary['runtime_launcher_status']}`",
        f"- portability_status: `{summary['portability_status']}`",
        f"- next_blocker: `{summary['next_blocker']}`",
        "",
        "## Environment",
        "",
        f"- platform: `{payload['platform']}`",
        f"- /dev/dxg: `{env_state['dev_dxg_exists']}`",
        f"- /dev/kfd: `{env_state['kfd_exists']}`",
        f"- HSA_OVERRIDE_GFX_VERSION: `{env_state['hsa_override_gfx_version'] or 'unset'}`",
        f"- HIP preload enabled: `{env_state['hip_preload_enabled']}`",
        "",
        "## Findings",
        "",
        "- The current LLVM path emits NVPTX/PTX rather than AMDGPU/ROCDL.",
        "- The current launch path is still CUDA or CUDA-driver based (`cuda` / `circt-cubin`).",
        "- Bundle/build/wrapper layers now carry an explicit execution-backend selector rather than relying on implicit CUDA-only defaults.",
        "- The lower bundle/build path now carries a generic GPU-binary ABI (`SIM_ACCEL_GPU_BINARY_PATH`) instead of hard-coding a cubin-only env contract.",
        f"- Standalone ROCm smoke passed: `{payload['pipeline']['standalone_rocm_smoke_pass']}`.",
        f"- Standalone sim-accel launch_all ROCm smoke passed: `{payload['pipeline']['sim_accel_launch_all_rocm_smoke_pass']}`.",
        f"- build_bench_bundle ROCm smoke passed: `{payload['pipeline']['build_bench_bundle_rocm_smoke_pass']}`.",
        f"- build_bench_bundle ROCm single-cluster smoke passed: `{payload['pipeline']['build_bench_bundle_single_cluster_rocm_smoke_pass']}`.",
        f"- verilator_sim_accel_bench wrapper ROCm smoke passed: `{payload['pipeline']['wrapper_rocm_smoke_pass']}`.",
        f"- verilator_sim_accel_bench wrapper ROCm smoke reached benchmark run: `{payload['pipeline']['wrapper_rocm_smoke_reached_run']}`.",
        f"- native hsaco mainline launch reached Radeon: `{payload['pipeline']['native_hsaco_mainline_launch_reached']}`.",
        f"- native hsaco mainline probe passed: `{payload['pipeline']['native_hsaco_mainline_probe_pass']}`.",
        f"- native hsaco mainline mismatch count: `{payload['pipeline']['native_hsaco_mainline_mismatch']}`.",
        f"- native hsaco first mismatch var: `{payload['pipeline']['native_hsaco_mainline_first_mismatch_var_name'] or 'none'}`.",
        f"- mainline OpenTitan runner ROCm smoke passed: `{payload['pipeline']['mainline_runner_rocm_smoke_pass']}`.",
        f"- mainline OpenTitan runner native hsaco mode: `{payload['pipeline']['mainline_runner_native_hsaco_mode']}`.",
        f"- mainline OpenTitan runner ROCm single-cluster smoke passed: `{payload['pipeline']['mainline_runner_single_cluster_rocm_smoke_pass']}`.",
        f"- mainline OpenTitan runner ROCm single-partition smoke passed: `{payload['pipeline']['mainline_runner_single_partition_rocm_smoke_pass']}`.",
        f"- structured second-wave semantic-gap waiver canonicalized: `{payload['pipeline']['structured_second_wave_waiver_canonicalized']}`.",
        f"- RTLMeter runner ROCm smoke passed: `{payload['pipeline']['rtlmeter_runner_rocm_smoke_pass']}`.",
        f"- RTLMeter runner native hsaco mode: `{payload['pipeline']['rtlmeter_runner_native_hsaco_mode']}`.",
        f"- RTLMeter runner ROCm single-cluster smoke passed: `{payload['pipeline']['rtlmeter_runner_single_cluster_rocm_smoke_pass']}`.",
        f"- native general bundle off passed: `{payload['pipeline']['native_general_bundle_off_pass']}`.",
        f"- native general bundle single-cluster soft-accepted: `{payload['pipeline']['native_general_bundle_single_cluster_soft_accepted']}`.",
        f"- native general bundle single-partition soft-accepted: `{payload['pipeline']['native_general_bundle_single_partition_soft_accepted']}`.",
        f"- native general bundle semantic-gap waiver canonicalized: `{payload['pipeline']['native_general_bundle_waiver_canonicalized']}`.",
        f"- verilator_sim_accel_bench wrapper single-cluster ROCm smoke passed: `{payload['pipeline']['wrapper_single_cluster_rocm_smoke_pass']}`.",
        f"- mainline structured-bundle probe blocker: `{payload['pipeline']['mainline_structured_bundle_probe_next_blocker'] or 'none'}`.",
        "- Output-side runtime detection now recognizes a WSL ROCm bridge and does not automatically mark the GPU as unavailable.",
        "- The next portability step is no longer wrapper wiring, OpenTitan runner smoke, second-wave waiver formalization, native full_all parity, RTLMeter admission, or native general-bundle off wiring; the current scope-limited portability milestone is met and the project can return to GPRO improvement plus resumed family validation.",
        "",
        "## Evidence",
        "",
        f"- [README]({README})",
        f"- [full_kernel_fuser.py]({FULL_KERNEL_FUSER})",
        f"- [prepare_bench_bundle.py]({PREPARE_BUNDLE})",
        f"- [build_bench_bundle.py]({BUILD_BUNDLE})",
        f"- [run_opentitan_tlul_slice_gpu_baseline.py]({RUN_SLICE_BASELINE})",
        f"- [gpu_runtime_batch_policy.py]({GPU_RUNTIME_POLICY})",
        f"- [capture_runtime_log.py]({CAPTURE_RUNTIME_LOG})",
        f"- [05_cache_materialize_helpers.sh]({CACHE_HELPERS})",
        f"- [07_build_run_phase.sh]({BUILD_HELPERS})",
        f"- [measure_bench_backends.py]({MEASURE_BENCH_BACKENDS})",
        f"- [rocm_llvm_hsaco_smoke.json]({out_dir / 'rocm_llvm_hsaco_smoke.json'})",
        f"- [rocm_sim_accel_launch_all_smoke.json]({out_dir / 'rocm_sim_accel_launch_all_smoke.json'})",
        f"- [rocm_build_bench_bundle_smoke.json]({out_dir / 'rocm_build_bench_bundle_smoke.json'})",
        f"- [rocm_verilator_sim_accel_bench_smoke.json]({out_dir / 'rocm_verilator_sim_accel_bench_smoke.json'})",
        f"- [rocm_verilator_sim_accel_bench_single_cluster_smoke.json]({out_dir / 'rocm_verilator_sim_accel_bench_single_cluster_smoke.json'})",
        f"- [rocm_native_hsaco_mainline_probe.json]({out_dir / 'rocm_native_hsaco_mainline_probe.json'})",
        f"- [rocm_mainline_runner_smoke.json]({out_dir / 'rocm_mainline_runner_smoke.json'})",
        f"- [rocm_mainline_structured_bundle_probe.json]({out_dir / 'rocm_mainline_structured_bundle_probe.json'})",
        f"- [rocm_rtlmeter_runner_smoke.json]({out_dir / 'rocm_rtlmeter_runner_smoke.json'})",
        f"- [rocm_rtlmeter_runner_single_cluster_smoke.json]({out_dir / 'rocm_rtlmeter_runner_single_cluster_smoke.json'})",
        f"- [rocm_native_general_bundle_smoke.json]({out_dir / 'rocm_native_general_bundle_smoke.json'})",
    ]
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Audit LLVM backend readiness for ROCm portability.")
    parser.add_argument(
        "--work-dir",
        default=str(DEFAULT_WORK_DIR),
        help="Directory for smoke-test result JSONs and output reports (default: %(default)s)",
    )
    ns = parser.parse_args()
    work_dir = Path(ns.work_dir).expanduser().resolve()
    payload = {
        "schema_version": "llvm-backend-readiness-v1",
        "platform": platform.platform(),
        "environment": _wsl_rocm_bridge_state(),
        "tool_status": {
            name: _tool_status(name)
            for name in ("hipcc", "rocminfo", "rocm-smi", "clinfo", "nvcc", "nvidia-smi")
        },
        "tool_probes": {
            "rocminfo": _run(["rocminfo"]),
            "rocm_smi": _run(["rocm-smi"]),
            "clinfo": _run(["clinfo"]),
        },
    }
    payload["pipeline"] = _detect_pipeline_status(work_dir)
    payload["summary"] = _classify_overall(payload["environment"], payload["pipeline"])
    json_path, md_path = _write_outputs(payload, work_dir)
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
