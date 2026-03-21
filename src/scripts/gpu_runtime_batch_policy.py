#!/usr/bin/env python3
from __future__ import annotations

import math
import os
import subprocess
from typing import Any


_TIERS = {
    "small": {
        "max_memory_mib": 10 * 1024,
        "candidate_scale": 0.5,
        "state_scale": 0.5,
        "topk_scale": 0.75,
    },
    "medium": {
        "max_memory_mib": 14 * 1024,
        "candidate_scale": 0.75,
        "state_scale": 0.75,
        "topk_scale": 1.0,
    },
    "baseline": {
        "max_memory_mib": 20 * 1024,
        "candidate_scale": 1.0,
        "state_scale": 1.0,
        "topk_scale": 1.0,
    },
    "large": {
        "max_memory_mib": 28 * 1024,
        "candidate_scale": 1.5,
        "state_scale": 1.25,
        "topk_scale": 1.25,
    },
    "xlarge": {
        "max_memory_mib": None,
        "candidate_scale": 2.0,
        "state_scale": 1.5,
        "topk_scale": 1.5,
    },
}


def _quantize(value: int, *, quantum: int, minimum: int) -> int:
    if value <= minimum:
        return minimum
    return max(minimum, int(math.ceil(value / float(quantum))) * quantum)


def _env_memory_override() -> int | None:
    for name in (
        "SIM_ACCEL_GPU_MEMORY_MIB",
        "GPU_RUNTIME_MEMORY_MIB",
        "ROCM_GPU_MEMORY_MIB",
    ):
        raw = os.getenv(name, "").strip()
        if not raw:
            continue
        try:
            value = int(raw)
        except ValueError:
            continue
        if value > 0:
            return value
    return None


def _rocm_wsl_bridge_enabled() -> bool:
    preload = os.getenv("LD_PRELOAD", "")
    return (
        os.path.exists("/dev/dxg")
        and bool(os.getenv("HSA_OVERRIDE_GFX_VERSION"))
        and "libamdhip64.so" in preload
    )


def _gpu_selection_policy_from_env(default: str = "auto") -> str:
    raw = os.getenv("SIM_ACCEL_GPU_SELECTION_POLICY", "").strip()
    return raw or default


def _detect_first_nvidia_gpu() -> dict[str, Any]:
    cmd = [
        "nvidia-smi",
        "--query-gpu=name,memory.total",
        "--format=csv,noheader,nounits",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return {"available": False, "reason": "nvidia_smi_failed", "stderr": proc.stderr.strip()}
    first = ""
    for line in proc.stdout.splitlines():
        if line.strip():
            first = line.strip()
            break
    if not first:
        return {"available": False, "reason": "no_gpu_rows"}
    parts = [part.strip() for part in first.split(",")]
    if len(parts) < 2:
        return {"available": False, "reason": "unexpected_nvidia_smi_format", "raw": first}
    try:
        memory_total_mib = int(parts[-1])
    except ValueError:
        return {"available": False, "reason": "invalid_memory_total", "raw": first}
    return {
        "available": True,
        "backend": "cuda",
        "name": ",".join(parts[:-1]).strip(),
        "memory_total_mib": memory_total_mib,
    }


def _detect_gpu_candidates() -> list[dict[str, Any]]:
    env_override = _env_memory_override()
    if env_override is not None:
        return [
            {
                "available": True,
                "backend": "override",
                "name": "memory-override",
                "memory_total_mib": env_override,
            }
        ]
    candidates: list[dict[str, Any]] = []
    detected = _detect_first_nvidia_gpu()
    if detected.get("available"):
        candidates.append(detected)
    if _rocm_wsl_bridge_enabled():
        candidates.append(
            {
                "available": True,
                "backend": "rocm_wsl_bridge",
                "name": "rocm-wsl-bridge",
                "memory_total_mib": None,
                "reason": "wsl_dxg_bridge_with_hip_preload",
            }
        )
    return candidates


def _select_gpu_candidate(
    candidates: list[dict[str, Any]],
    *,
    selection_policy: str,
) -> dict[str, Any]:
    if not candidates:
        return {"available": False, "reason": "no_gpu_candidates"}

    normalized = str(selection_policy or "auto").strip() or "auto"
    by_backend = {
        str(candidate.get("backend") or ""): candidate
        for candidate in candidates
        if candidate.get("available")
    }

    if normalized in {"auto", "prefer_cuda"} and "cuda" in by_backend:
        selected = dict(by_backend["cuda"])
        selected["selection_reason"] = "cuda_preferred"
        return selected
    if normalized == "prefer_rocm" and "rocm_wsl_bridge" in by_backend:
        selected = dict(by_backend["rocm_wsl_bridge"])
        selected["selection_reason"] = "rocm_preferred"
        return selected
    if normalized == "cuda_only":
        if "cuda" in by_backend:
            selected = dict(by_backend["cuda"])
            selected["selection_reason"] = "cuda_only"
            return selected
        return {"available": False, "reason": "cuda_only_without_cuda_candidate"}
    if normalized == "rocm_only":
        if "rocm_wsl_bridge" in by_backend:
            selected = dict(by_backend["rocm_wsl_bridge"])
            selected["selection_reason"] = "rocm_only"
            return selected
        return {"available": False, "reason": "rocm_only_without_rocm_candidate"}
    if normalized == "prefer_rocm" and "cuda" in by_backend:
        selected = dict(by_backend["cuda"])
        selected["selection_reason"] = "rocm_preferred_fell_back_to_cuda"
        return selected
    if normalized in {"auto", "prefer_cuda"} and "rocm_wsl_bridge" in by_backend:
        selected = dict(by_backend["rocm_wsl_bridge"])
        selected["selection_reason"] = "cuda_preferred_fell_back_to_rocm"
        return selected

    selected = dict(candidates[0])
    selected["selection_reason"] = "first_candidate_fallback"
    return selected


def classify_gpu_runtime_tier(
    *,
    execution_engine: str,
    policy_mode: str = "auto",
    memory_total_mib_override: int | None = None,
    selection_policy: str = "auto",
) -> dict[str, Any]:
    if str(execution_engine) != "gpu":
        return {
            "enabled": False,
            "policy_mode": str(policy_mode),
            "tier": "cpu",
            "reason": "execution_engine_cpu",
        }
    if str(policy_mode) == "off":
        return {
            "enabled": False,
            "policy_mode": str(policy_mode),
            "tier": "disabled",
            "reason": "policy_disabled",
        }
    effective_selection_policy = _gpu_selection_policy_from_env(selection_policy)
    candidates = (
        [
            {
                "available": True,
                "backend": "override",
                "name": "override",
                "memory_total_mib": int(memory_total_mib_override),
            }
        ]
        if memory_total_mib_override is not None and int(memory_total_mib_override) > 0
        else _detect_gpu_candidates()
    )
    detected = _select_gpu_candidate(
        candidates,
        selection_policy=effective_selection_policy,
    )
    if not detected.get("available"):
        return {
            "enabled": False,
            "policy_mode": str(policy_mode),
            "selection_policy": effective_selection_policy,
            "tier": "undetected",
            "reason": str(detected.get("reason") or "gpu_detection_failed"),
            "gpu": detected,
            "gpu_candidates": candidates,
        }
    memory_total_mib_raw = detected.get("memory_total_mib")
    selected_tier = "baseline"
    tier_config = dict(_TIERS["baseline"])
    memory_total_mib: int | None = None
    if memory_total_mib_raw is not None:
        memory_total_mib = int(memory_total_mib_raw)
        selected_tier = "xlarge"
        tier_config = dict(_TIERS["xlarge"])
        for tier_name, config in _TIERS.items():
            limit = config["max_memory_mib"]
            if limit is None or memory_total_mib <= int(limit):
                selected_tier = tier_name
                tier_config = dict(config)
                break
    return {
        "enabled": True,
        "policy_mode": str(policy_mode),
        "selection_policy": effective_selection_policy,
        "tier": selected_tier,
        "gpu": detected,
        "gpu_candidates": candidates,
        "memory_total_mib_known": memory_total_mib is not None,
        "candidate_scale": float(tier_config["candidate_scale"]),
        "state_scale": float(tier_config["state_scale"]),
        "topk_scale": float(tier_config["topk_scale"]),
    }


def apply_runtime_batch_policy(
    *,
    search_defaults: dict[str, Any],
    execution_engine: str,
    phase: str,
    policy_mode: str = "auto",
    memory_total_mib_override: int | None = None,
) -> dict[str, Any]:
    policy = classify_gpu_runtime_tier(
        execution_engine=execution_engine,
        policy_mode=policy_mode,
        memory_total_mib_override=memory_total_mib_override,
    )
    adjusted = dict(search_defaults)
    if not policy.get("enabled"):
        return {
            "policy": policy,
            "adjusted_search_defaults": adjusted,
        }

    candidate_scale = float(policy["candidate_scale"])
    state_scale = float(policy["state_scale"])
    topk_scale = float(policy["topk_scale"])

    if phase == "campaign":
        candidate_key = "pilot_campaign_candidate_count"
        candidate_quantum = max(1, int(search_defaults.get(candidate_key) or 64) // 2)
    else:
        candidate_key = "pilot_sweep_cases"
        candidate_quantum = max(1, int(search_defaults.get(candidate_key) or 64) // 4)
    candidate_value = int(search_defaults.get(candidate_key) or 0)
    if candidate_value > 0:
        adjusted[candidate_key] = _quantize(
            max(1, int(round(candidate_value * candidate_scale))),
            quantum=max(1, candidate_quantum),
            minimum=max(1, min(candidate_value, candidate_quantum)),
        )

    gpu_nstates = int(search_defaults.get("gpu_nstates") or 0)
    if gpu_nstates > 0:
        adjusted["gpu_nstates"] = _quantize(
            max(1, int(round(gpu_nstates * state_scale))),
            quantum=max(1, min(gpu_nstates, 32)),
            minimum=max(1, min(gpu_nstates, 32)),
        )

    campaign_gpu_nstates = int(search_defaults.get("campaign_gpu_nstates") or 0)
    if campaign_gpu_nstates > 0:
        adjusted["campaign_gpu_nstates"] = _quantize(
            max(1, int(round(campaign_gpu_nstates * state_scale))),
            quantum=max(1, min(campaign_gpu_nstates, 32)),
            minimum=max(1, min(campaign_gpu_nstates, 32)),
        )

    keep_top_k = int(search_defaults.get("keep_top_k") or 0)
    if keep_top_k > 0:
        adjusted["keep_top_k"] = _quantize(
            max(1, int(round(keep_top_k * topk_scale))),
            quantum=max(1, min(keep_top_k, 4)),
            minimum=1,
        )

    return {
        "policy": policy,
        "adjusted_search_defaults": adjusted,
    }
