#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .gpu_runtime_batch_policy import classify_gpu_runtime_tier
except ImportError:
    from gpu_runtime_batch_policy import classify_gpu_runtime_tier


PLAN_MD = Path("/tmp/audit_llvm_backend_readiness/llvm_backend_portability_plan.md")
READINESS_MD = Path("/tmp/audit_llvm_backend_readiness/llvm_backend_readiness.md")


def resolve_gpu_execution_backend(
    *,
    requested: str,
    launch_backend: str = "",
    execution_engine: str = "gpu",
    selection_policy: str = "auto",
) -> dict[str, Any]:
    requested_normalized = str(requested or "auto").strip() or "auto"
    launch_backend_normalized = str(launch_backend or "").strip()
    selection_policy_normalized = str(selection_policy or "auto").strip() or "auto"

    if execution_engine != "gpu":
        return {
            "request": requested_normalized,
            "selected": "host_only",
            "execution_engine": execution_engine,
            "supported_in_current_runner": True,
            "portability_status": "host_only_execution",
            "reason": "non_gpu_execution",
            "detected_gpu_backend": "",
            "detected_gpu_reason": "",
            "tier": "",
            "memory_total_mib_known": False,
        }

    runtime_policy = classify_gpu_runtime_tier(
        execution_engine="gpu",
        policy_mode="auto",
        selection_policy=selection_policy_normalized,
    )
    gpu = dict(runtime_policy.get("gpu") or {})
    detected_gpu_backend = str(gpu.get("backend") or "")
    detected_gpu_reason = str(gpu.get("reason") or "")

    if requested_normalized != "auto":
        selected = requested_normalized
        reason = "explicit_request"
    elif selection_policy_normalized == "rocm_only":
        selected = "rocm_llvm"
        reason = "selection_policy_rocm_only"
    elif selection_policy_normalized == "cuda_only":
        selected = "cuda_circt_cubin" if launch_backend_normalized == "circt-cubin" else "cuda_source"
        reason = "selection_policy_cuda_only"
    elif detected_gpu_backend == "rocm_wsl_bridge":
        selected = "rocm_llvm"
        reason = (
            "selection_policy_prefer_rocm"
            if selection_policy_normalized == "prefer_rocm"
            else "auto_selected_from_rocm_wsl_bridge"
        )
    elif launch_backend_normalized == "circt-cubin":
        selected = "cuda_circt_cubin"
        reason = (
            "selection_policy_prefer_cuda"
            if selection_policy_normalized == "prefer_cuda"
            else "auto_selected_from_circt_cubin_launch_backend"
        )
    else:
        selected = "cuda_source"
        reason = (
            "selection_policy_prefer_cuda"
            if selection_policy_normalized == "prefer_cuda"
            else "auto_selected_from_cuda_source_launch_backend"
        )

    supported_in_current_runner = selected in {"cuda_source", "cuda_circt_cubin", "rocm_llvm"}
    portability_status = (
        "current_runner_supported"
        if supported_in_current_runner
        else "portable_lane_missing"
    )
    return {
        "request": requested_normalized,
        "selected": selected,
        "execution_engine": execution_engine,
        "supported_in_current_runner": supported_in_current_runner,
        "portability_status": portability_status,
        "reason": reason,
        "detected_gpu_backend": detected_gpu_backend,
        "detected_gpu_reason": detected_gpu_reason,
        "selection_policy": str(runtime_policy.get("selection_policy") or selection_policy_normalized),
        "gpu_candidates": list(runtime_policy.get("gpu_candidates") or []),
        "tier": str(runtime_policy.get("tier") or ""),
        "memory_total_mib_known": bool(runtime_policy.get("memory_total_mib_known")),
    }


def ensure_gpu_execution_backend_supported(selection: dict[str, Any], *, runner_name: str) -> None:
    if str(selection.get("execution_engine") or "") != "gpu":
        return
    if bool(selection.get("supported_in_current_runner")):
        return
    selected = str(selection.get("selected") or "")
    reason = str(selection.get("reason") or "")
    raise SystemExit(
        f"{runner_name} selected unsupported GPU backend '{selected}' "
        f"(reason={reason}). Current mainline runners still assume "
        "NVPTX/PTX plus CUDA launch. See "
        f"{READINESS_MD} and {PLAN_MD}."
    )
