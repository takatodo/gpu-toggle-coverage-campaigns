#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = Path("/home/takatodo/GEM_try")
REPO_SCRIPTS = ROOT_DIR / "scripts"

if str(REPO_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(REPO_SCRIPTS))

from opentitan_tlul_baseline_common import load_batch_overrides  # noqa: E402
from opentitan_tlul_trace_search_common import DRIVER_DEFAULTS as TRACE_DRIVER_DEFAULTS  # noqa: E402


DRIVER_PATCH_KEYS = (
    "access_ack_data_pct",
    "address_base",
    "address_mask",
    "batch_length",
    "device_a_ready_pct",
    "drain_cycles",
    "host_d_ready_pct",
    "put_full_pct",
    "put_partial_pct",
    "req_address_mode",
    "req_burst_len_max",
    "req_data_hi_xor",
    "req_data_mode",
    "req_family",
    "req_fill_target",
    "req_valid_pct",
    "reset_cycles",
    "rsp_data_hi_xor",
    "rsp_data_mode",
    "rsp_delay_max",
    "rsp_delay_mode",
    "rsp_error_pct",
    "rsp_family",
    "rsp_fill_target",
    "rsp_valid_pct",
    "source_mask",
    "trace_replay_enable",
)

LAUNCH_PATCH_KEYS = (
    "trace_length",
    "batch_length",
    "gpu_nstates",
    "states_per_case",
    "keep_top_k",
    "cases",
)


GRPO_POLICY_PROFILES: dict[str, dict[str, float]] = {
    "throughput": {
        "diversity_weight": 0.0,
        "rarity_weight": 0.05,
        "frequency_novelty_weight": 0.02,
    },
    "balanced": {
        "diversity_weight": 0.12,
        "rarity_weight": 0.08,
        "frequency_novelty_weight": 0.05,
    },
    "diversity": {
        "diversity_weight": 0.25,
        "rarity_weight": 0.10,
        "frequency_novelty_weight": 0.08,
    },
}


GRPO_REWARD_PROFILES: dict[str, dict[str, float]] = {
    "throughput": {
        "execution_weight": 0.50,
        "breadth_weight": 0.20,
        "concentration_weight": 0.05,
        "target_activation_weight": 0.05,
        "target_dead_penalty_weight": 0.02,
        "structural_weight": 0.05,
        "coverage_log_bonus_weight": 0.10,
        "runtime_penalty_weight": 0.05,
        "execution_gate_zero_scale": 0.25,
        "truth_gate_zero_scale": 0.80,
    },
    "balanced": {
        "execution_weight": 0.40,
        "breadth_weight": 0.30,
        "concentration_weight": 0.10,
        "target_activation_weight": 0.10,
        "target_dead_penalty_weight": 0.05,
        "structural_weight": 0.10,
        "coverage_log_bonus_weight": 0.05,
        "runtime_penalty_weight": 0.10,
        "execution_gate_zero_scale": 0.25,
        "truth_gate_zero_scale": 0.75,
    },
    "breadth": {
        "execution_weight": 0.20,
        "breadth_weight": 0.45,
        "concentration_weight": 0.15,
        "target_activation_weight": 0.15,
        "target_dead_penalty_weight": 0.10,
        "structural_weight": 0.05,
        "coverage_log_bonus_weight": 0.01,
        "runtime_penalty_weight": 0.15,
        "execution_gate_zero_scale": 0.20,
        "truth_gate_zero_scale": 0.55,
    },
    "marginal_breadth": {
        "execution_weight": 0.15,
        "breadth_weight": 0.20,
        "concentration_weight": 0.15,
        "target_activation_weight": 0.08,
        "target_dead_penalty_weight": 0.10,
        "structural_weight": 0.02,
        "coverage_log_bonus_weight": 0.0,
        "runtime_penalty_weight": 0.10,
        "execution_gate_zero_scale": 0.20,
        "truth_gate_zero_scale": 0.45,
        "target_region_rarity_weight": 0.25,
        "multi_region_bonus_weight": 0.25,
        "target_isolation_penalty_weight": 0.20,
        "dead_word_penalty_weight": 0.12,
    },
    "closure": {
        "execution_weight": 0.12,
        "breadth_weight": 0.18,
        "concentration_weight": 0.12,
        "target_activation_weight": 0.05,
        "target_dead_penalty_weight": 0.10,
        "structural_weight": 0.02,
        "coverage_log_bonus_weight": 0.0,
        "runtime_penalty_weight": 0.08,
        "execution_gate_zero_scale": 0.20,
        "truth_gate_zero_scale": 0.45,
        "target_region_rarity_weight": 0.20,
        "multi_region_bonus_weight": 0.22,
        "activation_novelty_weight": 0.26,
        "closure_progress_weight": 0.20,
        "target_isolation_penalty_weight": 0.20,
        "dead_word_penalty_weight": 0.10,
    },
}


SLICE_GRPO_POLICY_PROFILE_HINTS: dict[str, str] = {
    "alert_handler_ping_timer": "diversity",
    "csrng_main_sm": "diversity",
    "edn_main_sm": "diversity",
    "lc_ctrl_fsm": "diversity",
    "rom_ctrl_fsm": "diversity",
    "tlul_socket_1n": "diversity",
    "tlul_socket_m1": "diversity",
    "tlul_request_loopback": "balanced",
}


SLICE_GRPO_TARGET_REGION_HINTS: dict[str, str] = {
    "alert_handler_ping_timer": "id_skip_and_rotation",
    "csrng_main_sm": "instantiate_reseed_generate_update_split",
    "edn_main_sm": "request_accept_and_progress",
    "lc_ctrl_fsm": "flash_rma_and_terminal_error_path",
    "rom_ctrl_fsm": "checker_start_compare_done",
    "tlul_socket_1n": "reqfifo_storage_upper",
    "tlul_socket_m1": "response_select_path",
    "tlul_request_loopback": "loopback_response_path",
    "xbar_peri": "reqfifo_storage_upper",
    "xbar_main": "reqfifo_storage_upper",
}


SLICE_GRPO_SELECTION_MODE_HINTS: dict[str, str] = {
    "alert_handler_ping_timer": "closure",
    "csrng_main_sm": "closure",
    "edn_main_sm": "closure",
    "lc_ctrl_fsm": "closure",
    "rom_ctrl_fsm": "closure",
    "tlul_socket_1n": "closure",
    "tlul_socket_m1": "closure",
    "tlul_request_loopback": "blend",
    "xbar_peri": "closure",
    "xbar_main": "closure",
}


SLICE_GRPO_REWARD_PROFILE_HINTS: dict[str, str] = {
    "alert_handler_ping_timer": "closure",
    "csrng_main_sm": "closure",
    "edn_main_sm": "closure",
    "entropy_src_main_sm": "closure",
    "aes_cipher_control": "closure",
    "lc_ctrl_fsm": "closure",
    "rom_ctrl_fsm": "closure",
    "tlul_socket_1n": "closure",
    "tlul_socket_m1": "closure",
    "tlul_fifo_async": "closure",
    "tlul_request_loopback": "balanced",
    "xbar_main": "closure",
    "xbar_peri": "closure",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def missing_region_context_key(
    *,
    slice_name: str,
    profile_family: str,
    missing_regions: list[str],
) -> str:
    normalized_regions = sorted(
        {
            str(region or "").strip()
            for region in list(missing_regions or [])
            if str(region or "").strip()
        }
    )
    region_text = ",".join(normalized_regions)
    return "::".join((str(slice_name or "").strip(), region_text, str(profile_family or "").strip()))


def template_region_names(template_payload: dict[str, Any]) -> list[str]:
    runner_args = dict(template_payload.get("runner_args_template") or {})
    manifest_path_raw = str(runner_args.get("coverage_manifest_path") or "").strip()
    if not manifest_path_raw:
        return []
    manifest_path = Path(manifest_path_raw).expanduser().resolve()
    if not manifest_path.exists():
        return []
    manifest_payload = load_json(manifest_path)
    names: list[str] = []
    for region in list(manifest_payload.get("regions") or []):
        name = str(dict(region).get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def summary_active_region_union(summary_payload: dict[str, Any]) -> list[str]:
    merge_view_raw = str(summary_payload.get("campaign_merge_view_json") or "").strip()
    if merge_view_raw:
        merge_view_path = Path(merge_view_raw).expanduser().resolve()
        if merge_view_path.exists():
            merge_view_payload = load_json(merge_view_path)
            return [
                str(region).strip()
                for region in list(merge_view_payload.get("active_region_union") or [])
                if str(region).strip()
            ]
    best_case = dict(summary_payload.get("best_case") or {})
    return [
        str(region).strip()
        for region in list(best_case.get("active_regions") or [])
        if str(region).strip()
    ]


def missing_regions_from_summary(
    *,
    summary_payload: dict[str, Any],
    template_payload: dict[str, Any],
) -> list[str]:
    template_regions = template_region_names(template_payload)
    if not template_regions:
        return []
    active_region_union = set(summary_active_region_union(summary_payload))
    if not active_region_union:
        covered_targets = {
            str(region).strip()
            for region in dict(summary_payload.get("best_by_target_region") or {}).keys()
            if str(region).strip()
        }
        active_region_union = covered_targets
    return [region for region in template_regions if region not in active_region_union]


def maybe_gpro_run_payload(summary_json: Path) -> dict[str, Any]:
    candidate = summary_json.with_name("gpro_run.json")
    if not candidate.exists():
        return {}
    payload = load_json(candidate)
    if not isinstance(payload, dict):
        return {}
    return payload


def template_driver_defaults(template_payload: dict[str, Any]) -> dict[str, Any]:
    runner_args = dict(template_payload.get("runner_args_template") or {})
    merged: dict[str, Any] = {}
    defaults_path = str(runner_args.get("batch_defaults_path") or "").strip()
    if defaults_path:
        merged.update(
            {
                key: value
                for key, value in load_batch_overrides(defaults_path).items()
                if not str(key).startswith("_")
            }
        )
    merged.update(
        {
            key: value
            for key, value in dict(runner_args.get("driver_defaults") or {}).items()
            if not str(key).startswith("_")
        }
    )
    return merged


def normalize_driver_payload(driver_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in dict(driver_payload or {}).items()
        if not str(key).startswith("_")
    }


def case_driver_payload(case_summary: dict[str, Any]) -> dict[str, Any]:
    batch_json_raw = str(case_summary.get("batch_json") or "").strip()
    if batch_json_raw:
        batch_json_path = Path(batch_json_raw).expanduser().resolve()
        if batch_json_path.exists():
            return normalize_driver_payload(load_batch_overrides(str(batch_json_path)))
    return normalize_driver_payload(dict(case_summary.get("driver") or {}))


def build_driver_patch(
    *,
    driver_payload: dict[str, Any],
    template_defaults: dict[str, Any],
) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    for key in DRIVER_PATCH_KEYS:
        if key not in driver_payload:
            continue
        current = driver_payload.get(key)
        default = template_defaults.get(key, TRACE_DRIVER_DEFAULTS.get(key))
        if current != default:
            patch[key] = current
    return patch


def build_launch_patch(
    *,
    case_summary: dict[str, Any],
    summary_payload: dict[str, Any],
    gpro_payload: dict[str, Any],
) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    effective_defaults = dict(summary_payload.get("effective_search_defaults") or {})
    gpro_defaults = dict(gpro_payload.get("gpro_defaults") or {})
    baseline = {
        "trace_length": gpro_defaults.get("trace_length"),
        "batch_length": gpro_defaults.get("batch_length"),
        "gpu_nstates": effective_defaults.get("gpu_nstates", gpro_defaults.get("gpu_nstates")),
        "states_per_case": summary_payload.get("states_per_case", gpro_defaults.get("states_per_case")),
        "keep_top_k": effective_defaults.get("keep_top_k", gpro_defaults.get("keep_top_k")),
        "cases": effective_defaults.get("pilot_sweep_cases", gpro_defaults.get("cases")),
    }
    current = {
        "trace_length": gpro_defaults.get("trace_length"),
        "batch_length": case_driver_payload(case_summary).get("batch_length", gpro_defaults.get("batch_length")),
        "gpu_nstates": effective_defaults.get("gpu_nstates", gpro_defaults.get("gpu_nstates")),
        "states_per_case": summary_payload.get("states_per_case", gpro_defaults.get("states_per_case")),
        "keep_top_k": effective_defaults.get("keep_top_k", gpro_defaults.get("keep_top_k")),
        "cases": effective_defaults.get("pilot_sweep_cases", gpro_defaults.get("cases")),
    }
    for key in LAUNCH_PATCH_KEYS:
        if current.get(key) != baseline.get(key) and current.get(key) is not None:
            patch[key] = current[key]
    return patch


def action_patch_from_case(
    *,
    case_summary: dict[str, Any],
    summary_payload: dict[str, Any],
    template_payload: dict[str, Any],
    gpro_payload: dict[str, Any],
) -> dict[str, Any]:
    driver_payload = case_driver_payload(case_summary)
    template_defaults = template_driver_defaults(template_payload)
    return {
        "variant_name": str(case_summary.get("variant_name") or "base"),
        "driver_patch": build_driver_patch(
            driver_payload=driver_payload,
            template_defaults=template_defaults,
        ),
        "launch_patch": build_launch_patch(
            case_summary=case_summary,
            summary_payload=summary_payload,
            gpro_payload=gpro_payload,
        ),
    }


def canonical_action_key(action_patch: dict[str, Any]) -> str:
    return json.dumps(
        {
            "variant_name": str(action_patch.get("variant_name") or "base"),
            "driver_patch": dict(action_patch.get("driver_patch") or {}),
            "launch_patch": dict(action_patch.get("launch_patch") or {}),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _is_numeric_value(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _normalized_numeric_distance(lhs: Any, rhs: Any) -> float:
    lhs_value = float(lhs)
    rhs_value = float(rhs)
    scale = max(abs(lhs_value), abs(rhs_value), 1.0)
    return min(1.0, abs(lhs_value - rhs_value) / scale)


def action_patch_distance(lhs: dict[str, Any], rhs: dict[str, Any]) -> float:
    lhs_patch = dict(lhs or {})
    rhs_patch = dict(rhs or {})
    lhs_driver = dict(lhs_patch.get("driver_patch") or {})
    rhs_driver = dict(rhs_patch.get("driver_patch") or {})
    lhs_launch = dict(lhs_patch.get("launch_patch") or {})
    rhs_launch = dict(rhs_patch.get("launch_patch") or {})

    total = 0.0
    count = 0

    if str(lhs_patch.get("variant_name") or "base") != str(rhs_patch.get("variant_name") or "base"):
        total += 1.0
    count += 1

    for key in sorted(set(lhs_driver) | set(rhs_driver)):
        lhs_value = lhs_driver.get(key)
        rhs_value = rhs_driver.get(key)
        if lhs_value is None and rhs_value is None:
            continue
        if _is_numeric_value(lhs_value) and _is_numeric_value(rhs_value):
            total += _normalized_numeric_distance(lhs_value, rhs_value)
        else:
            total += 0.0 if lhs_value == rhs_value else 1.0
        count += 1

    for key in sorted(set(lhs_launch) | set(rhs_launch)):
        lhs_value = lhs_launch.get(key)
        rhs_value = rhs_launch.get(key)
        if lhs_value is None and rhs_value is None:
            continue
        if _is_numeric_value(lhs_value) and _is_numeric_value(rhs_value):
            total += _normalized_numeric_distance(lhs_value, rhs_value)
        else:
            total += 0.0 if lhs_value == rhs_value else 1.0
        count += 1

    if count <= 0:
        return 0.0
    return total / float(count)


def action_patch_diversity_score(
    action_patch: dict[str, Any],
    selected_action_patches: list[dict[str, Any]],
) -> float:
    if not selected_action_patches:
        return 0.0
    distances = [
        action_patch_distance(action_patch, selected_patch)
        for selected_patch in selected_action_patches
    ]
    if not distances:
        return 0.0
    return min(distances)


def resolve_grpo_policy_profile(
    profile_name: str,
    *,
    diversity_weight: float | None = None,
    rarity_weight: float | None = None,
    frequency_novelty_weight: float | None = None,
) -> dict[str, float]:
    profile_key = str(profile_name or "diversity").strip() or "diversity"
    if profile_key not in GRPO_POLICY_PROFILES:
        raise KeyError(f"Unknown GRPO policy profile: {profile_key}")
    base = dict(GRPO_POLICY_PROFILES[profile_key])
    if diversity_weight is not None:
        base["diversity_weight"] = float(diversity_weight)
    if rarity_weight is not None:
        base["rarity_weight"] = float(rarity_weight)
    if frequency_novelty_weight is not None:
        base["frequency_novelty_weight"] = float(frequency_novelty_weight)
    base["policy_profile"] = profile_key
    return base


def resolve_grpo_reward_profile(profile_name: str) -> dict[str, float]:
    profile_key = str(profile_name or "balanced").strip() or "balanced"
    if profile_key not in GRPO_REWARD_PROFILES:
        raise KeyError(f"Unknown GRPO reward profile: {profile_key}")
    base = dict(GRPO_REWARD_PROFILES[profile_key])
    base["reward_profile"] = profile_key
    return base


def recommended_grpo_target_region(slice_name: str) -> str:
    return str(SLICE_GRPO_TARGET_REGION_HINTS.get(str(slice_name or "").strip()) or "")


def recommended_grpo_selection_mode(slice_name: str) -> str:
    slice_key = str(slice_name or "").strip()
    explicit = str(SLICE_GRPO_SELECTION_MODE_HINTS.get(slice_key) or "").strip()
    if explicit:
        return explicit
    if recommended_grpo_reward_profile(slice_key) == "closure":
        return "closure"
    return "blend"


def recommended_grpo_policy_profile(slice_name: str) -> str:
    return str(SLICE_GRPO_POLICY_PROFILE_HINTS.get(str(slice_name or "").strip()) or "")


def recommended_grpo_reward_profile(slice_name: str) -> str:
    return str(SLICE_GRPO_REWARD_PROFILE_HINTS.get(str(slice_name or "").strip()) or "balanced")


def context_key(
    *,
    slice_name: str,
    target_region: str,
    profile_family: str,
) -> str:
    return "::".join(
        (
            str(slice_name or "").strip(),
            str(target_region or "").strip(),
            str(profile_family or "").strip(),
        )
    )


def slice_only_context_key(
    *,
    slice_name: str,
    profile_family: str,
) -> str:
    return "::".join((str(slice_name or "").strip(), "*", str(profile_family or "").strip()))


def _policy_candidate_key(candidate: dict[str, Any]) -> str:
    action_key = str(candidate.get("action_key") or "").strip()
    if action_key:
        return action_key
    return json.dumps(
        dict(candidate.get("action_patch") or {}),
        sort_keys=True,
        separators=(",", ":"),
    )


def _policy_candidate_target_regions(candidate: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(region or "").strip()
            for region in list(candidate.get("target_regions") or [])
            if str(region or "").strip()
        }
    )


def select_policy_candidates(
    *,
    exact_candidates: list[dict[str, Any]],
    missing_candidates: list[dict[str, Any]],
    slice_candidates: list[dict[str, Any]],
    limit: int,
    selection_mode: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    selected_target_regions: set[str] = set()
    selected_from_counts = {
        "exact": 0,
        "missing": 0,
        "slice": 0,
    }
    context_pool_sizes = {
        "exact": len(list(exact_candidates or [])),
        "missing": len(list(missing_candidates or [])),
        "slice": len(list(slice_candidates or [])),
    }

    normalized_limit = max(1, int(limit))
    mode = str(selection_mode or "exact").strip() or "exact"

    def _append_unique(
        source_name: str,
        source_rows: list[dict[str, Any]],
        quota: int | None = None,
        *,
        prefer_new_target_region: bool = False,
    ) -> None:
        remaining = normalized_limit - len(selected)
        if remaining <= 0:
            return
        if quota is not None:
            remaining = min(remaining, max(0, int(quota)))
        rows = list(source_rows or [])
        if prefer_new_target_region and rows and selected_target_regions:
            preferred: list[dict[str, Any]] = []
            fallback: list[dict[str, Any]] = []
            for candidate in rows:
                target_regions = _policy_candidate_target_regions(candidate)
                if target_regions and not set(target_regions).issubset(selected_target_regions):
                    preferred.append(candidate)
                else:
                    fallback.append(candidate)
            rows = preferred + fallback
        for candidate in rows:
            if remaining <= 0:
                break
            candidate_key = _policy_candidate_key(candidate)
            if candidate_key in seen:
                continue
            selected.append(candidate)
            seen.add(candidate_key)
            selected_target_regions.update(_policy_candidate_target_regions(candidate))
            selected_from_counts[source_name] = int(selected_from_counts[source_name]) + 1
            remaining -= 1

    def _fill_priority(order: list[str]) -> None:
        source_map = {
            "exact": list(exact_candidates or []),
            "missing": list(missing_candidates or []),
            "slice": list(slice_candidates or []),
        }
        for source_name in order:
            _append_unique(source_name, source_map[source_name])

    if mode == "slice":
        _fill_priority(["slice", "missing", "exact"])
    elif mode == "missing":
        _fill_priority(["missing", "slice", "exact"])
    elif mode == "closure":
        if missing_candidates:
            missing_quota = max(1, (normalized_limit + 1) // 2)
            _append_unique("missing", list(missing_candidates or []), missing_quota)
        if slice_candidates:
            slice_quota = max(1, normalized_limit - len(selected))
            _append_unique(
                "slice",
                list(slice_candidates or []),
                slice_quota,
                prefer_new_target_region=True,
            )
        _fill_priority(["missing", "slice", "exact"])
    elif mode == "blend":
        quota = max(1, normalized_limit // 3)
        _append_unique("exact", list(exact_candidates or []), quota)
        _append_unique(
            "missing",
            list(missing_candidates or []),
            quota,
            prefer_new_target_region=True,
        )
        _append_unique(
            "slice",
            list(slice_candidates or []),
            normalized_limit - len(selected),
            prefer_new_target_region=True,
        )
        _fill_priority(["exact", "missing", "slice"])
    else:
        _fill_priority(["exact", "missing", "slice"])

    if mode == "closure":
        if selected_from_counts["missing"] > 0 or selected_from_counts["slice"] > 0:
            selection_source = "closure_missing_slice_blend"
        elif selected_from_counts["exact"] > 0:
            selection_source = "closure_exact_fallback"
        else:
            selection_source = "closure_blend"
    elif mode == "blend":
        if selected_from_counts["missing"] > 0 or selected_from_counts["slice"] > 0:
            selection_source = "exact_missing_slice_blend"
        elif selected_from_counts["exact"] > 0:
            selection_source = "exact_context_blend_fallback"
        else:
            selection_source = "exact_missing_slice_blend"
    elif mode == "slice":
        selection_source = (
            "slice_context"
            if selected_from_counts["slice"] > 0
            else ("missing_region_context" if selected_from_counts["missing"] > 0 else "exact_context")
        )
    elif mode == "missing":
        selection_source = (
            "missing_region_context"
            if selected_from_counts["missing"] > 0
            else ("slice_context_fallback" if selected_from_counts["slice"] > 0 else "exact_context")
        )
    else:
        selection_source = (
            "exact_context"
            if selected_from_counts["exact"] > 0
            else ("missing_region_context" if selected_from_counts["missing"] > 0 else "slice_context_fallback")
        )

    if selected_from_counts["missing"] > 0:
        primary_source = "missing"
    elif selected_from_counts["slice"] > 0:
        primary_source = "slice"
    elif selected_from_counts["exact"] > 0:
        primary_source = "exact"
    else:
        primary_source = ""

    return selected[:normalized_limit], {
        "selection_mode": mode,
        "selection_source": selection_source,
        "primary_source": primary_source,
        "context_pool_sizes": context_pool_sizes,
        "selected_from_counts": selected_from_counts,
    }


def group_id(
    *,
    summary_json: Path,
    target_region: str,
) -> str:
    return f"{summary_json.resolve()}::{str(target_region or '').strip()}"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _log_norm(value: Any, *, reference: float) -> float:
    numeric = max(0.0, float(value or 0.0))
    if reference <= 0.0:
        return 0.0
    return _clamp01(math.log1p(numeric) / math.log1p(reference))


def _accepted_traffic_sum(case_summary: dict[str, Any]) -> float:
    explicit = case_summary.get("accepted_traffic_sum")
    if explicit is not None:
        return float(explicit or 0.0)
    traffic = dict(case_summary.get("traffic_counters") or {})
    return float(
        sum(
            int(case_summary.get(key) or traffic.get(key) or 0)
            for key in (
                "host_req_accepted_o",
                "device_req_accepted_o",
                "device_rsp_accepted_o",
                "host_rsp_accepted_o",
            )
        )
    )


def _progress_cycle_count(case_summary: dict[str, Any]) -> float:
    explicit = case_summary.get("progress_cycle_count_o")
    if explicit is not None:
        return float(explicit or 0.0)
    execution_gating = dict(case_summary.get("execution_gating") or {})
    if "progress_cycle_count_o" in execution_gating:
        return float(execution_gating.get("progress_cycle_count_o") or 0.0)
    trace_progress = dict(case_summary.get("trace_progress") or {})
    return float(trace_progress.get("progress_cycle_count_o") or 0.0)


def _region_count(case_summary: dict[str, Any]) -> float:
    active_region_count = float(case_summary.get("active_region_count") or 0.0)
    dead_region_count = float(case_summary.get("dead_region_count") or 0.0)
    explicit_regions = float(case_summary.get("region_count") or 0.0)
    inferred = active_region_count + dead_region_count
    return max(1.0, explicit_regions, inferred)


def _dominant_region_share_proxy(case_summary: dict[str, Any]) -> float:
    active_region_count = float(case_summary.get("active_region_count") or 0.0)
    if active_region_count <= 0.0:
        return 1.0
    return _clamp01(1.0 / active_region_count)


def structural_prior_terms_from_template(template_payload: dict[str, Any] | None) -> dict[str, float]:
    static_features = dict((template_payload or {}).get("static_features") or {})
    if not static_features:
        return {
            "structural_witness_exclusive_fraction": 0.0,
            "structural_region_separability": 0.0,
            "structural_reachability": 0.0,
            "structural_cdc_penalty": 0.0,
            "structural_control_penalty": 0.0,
            "structural_prior_score": 0.0,
        }
    region_count = max(1.0, float(static_features.get("region_count") or 0.0))
    singleton_region_count = float(static_features.get("singleton_region_count") or 0.0)
    witness_exclusive_fraction = _clamp01(float(static_features.get("exclusive_word_fraction") or 0.0))
    structural_connectivity = dict(static_features.get("structural_connectivity") or {})
    reachability = _clamp01(
        0.5 * float(structural_connectivity.get("reachable_output_fraction") or 0.0)
        + 0.5 * float(structural_connectivity.get("avg_input_reach_fraction") or 0.0)
    )
    region_separability = _clamp01(1.0 - (singleton_region_count / region_count))
    cdc_penalty = 0.25 if bool(static_features.get("multi_clock")) else 0.0
    connectivity_class = str(structural_connectivity.get("structural_connectivity_class") or "")
    control_penalty = 0.15 if connectivity_class == "narrow_structural_spread" else 0.0
    structural_prior_score = _clamp01(
        0.4 * witness_exclusive_fraction
        + 0.3 * region_separability
        + 0.3 * reachability
        - cdc_penalty
        - control_penalty
    )
    return {
        "structural_witness_exclusive_fraction": witness_exclusive_fraction,
        "structural_region_separability": region_separability,
        "structural_reachability": reachability,
        "structural_cdc_penalty": cdc_penalty,
        "structural_control_penalty": control_penalty,
        "structural_prior_score": structural_prior_score,
    }


def reward_terms_from_case(
    case_summary: dict[str, Any],
    *,
    template_payload: dict[str, Any] | None = None,
    reward_profile: str = "balanced",
) -> dict[str, float]:
    points_hit = float(case_summary.get("real_subset_points_hit") or 0.0)
    points_total = max(1.0, float(case_summary.get("real_subset_points_total") or 0.0))
    dead_regions = float(case_summary.get("dead_region_count") or 0.0)
    dead_words = float(case_summary.get("dead_output_word_count") or 0.0)
    target_region_activated = float(case_summary.get("target_region_activated") or 0.0)
    target_region_still_dead = float(case_summary.get("target_region_still_dead") or 0.0)
    coverage_per_second = float(case_summary.get("real_subset_coverage_per_second") or 0.0)
    active_region_count = float(case_summary.get("active_region_count") or 0.0)
    region_count = _region_count(case_summary)
    normalized_hit = points_hit / points_total
    accepted_traffic_sum = _accepted_traffic_sum(case_summary)
    progress_cycle_count = _progress_cycle_count(case_summary)
    union_fraction = _clamp01(active_region_count / region_count)
    dead_region_fraction = _clamp01(dead_regions / region_count)
    dead_word_fraction = _clamp01(dead_words / points_total)
    dominant_region_share_proxy = _dominant_region_share_proxy(case_summary)
    multi_region_bonus = _clamp01((active_region_count - 1.0) / max(1.0, region_count - 1.0))
    target_isolation_penalty = (
        1.0
        if target_region_activated > 0.0 and active_region_count <= 1.0
        else 0.0
    )
    closure_progress_bonus = _clamp01(
        0.6 * union_fraction + 0.4 * max(0.0, normalized_hit - dead_word_fraction)
    )
    activation_novelty_bonus = _clamp01(target_region_activated * multi_region_bonus)
    execution_progress_norm = _log_norm(progress_cycle_count, reference=64.0)
    execution_traffic_norm = _log_norm(accepted_traffic_sum, reference=16.0)
    execution_score = _clamp01(0.6 * execution_progress_norm + 0.4 * execution_traffic_norm)
    breadth_score = _clamp01(
        0.45 * union_fraction
        + 0.35 * normalized_hit
        + 0.20 * (1.0 - dead_region_fraction)
    )
    concentration_score = _clamp01(1.0 - dominant_region_share_proxy)
    runtime_proxy_penalty = 0.0 if coverage_per_second > 0.0 else 1.0
    structural_terms = structural_prior_terms_from_template(template_payload)
    reward_profile_terms = resolve_grpo_reward_profile(reward_profile)
    continuous_reward = (
        float(reward_profile_terms["execution_weight"]) * execution_score
        + float(reward_profile_terms["breadth_weight"]) * breadth_score
        + float(reward_profile_terms["concentration_weight"]) * concentration_score
        + float(reward_profile_terms["target_activation_weight"]) * target_region_activated
        + float(reward_profile_terms["structural_weight"]) * float(structural_terms.get("structural_prior_score") or 0.0)
        + float(reward_profile_terms.get("target_region_rarity_weight") or 0.0) * 0.0
        + float(reward_profile_terms.get("multi_region_bonus_weight") or 0.0) * multi_region_bonus
        + float(reward_profile_terms.get("activation_novelty_weight") or 0.0) * activation_novelty_bonus
        + float(reward_profile_terms.get("closure_progress_weight") or 0.0) * closure_progress_bonus
        - float(reward_profile_terms["target_dead_penalty_weight"]) * target_region_still_dead
        - float(reward_profile_terms.get("target_isolation_penalty_weight") or 0.0) * target_isolation_penalty
        - float(reward_profile_terms.get("dead_word_penalty_weight") or 0.0) * dead_word_fraction
    )
    compact_truth_proxy = 1.0 if (active_region_count > 0.0 and points_hit > 0.0) else 0.0
    compact_execution_proxy = 1.0 if (compact_truth_proxy > 0.0 and coverage_per_second > 0.0) else 0.0
    execution_gate = 1.0 if (accepted_traffic_sum > 0.0 and progress_cycle_count > 0.0) else (0.5 if compact_execution_proxy > 0.0 else 0.0)
    truth_gate = 1.0 if (accepted_traffic_sum > 0.0 and active_region_count > 0.0 and points_hit > 0.0) else compact_truth_proxy
    reward = continuous_reward
    if execution_gate <= 0.0:
        reward *= float(reward_profile_terms["execution_gate_zero_scale"])
    elif truth_gate <= 0.0:
        reward *= float(reward_profile_terms["truth_gate_zero_scale"])
    reward += float(reward_profile_terms["coverage_log_bonus_weight"]) * math.log1p(max(0.0, coverage_per_second))
    reward -= float(reward_profile_terms["runtime_penalty_weight"]) * runtime_proxy_penalty
    reward = max(0.0, reward)
    return {
        "points_hit": points_hit,
        "normalized_hit": normalized_hit,
        "dead_regions": dead_regions,
        "dead_words": dead_words,
        "dead_word_fraction": dead_word_fraction,
        "target_region_activated": target_region_activated,
        "target_region_still_dead": target_region_still_dead,
        "target_region_rarity_bonus": 0.0,
        "multi_region_bonus": multi_region_bonus,
        "activation_novelty_bonus": activation_novelty_bonus,
        "closure_progress_bonus": closure_progress_bonus,
        "target_isolation_penalty": target_isolation_penalty,
        "active_region_count": active_region_count,
        "region_count": region_count,
        "union_fraction": union_fraction,
        "dead_region_fraction": dead_region_fraction,
        "dominant_region_share_proxy": dominant_region_share_proxy,
        "progress_cycle_count": progress_cycle_count,
        "accepted_traffic_sum": accepted_traffic_sum,
        "execution_progress_norm": execution_progress_norm,
        "execution_traffic_norm": execution_traffic_norm,
        "execution_score": execution_score,
        "breadth_score": breadth_score,
        "concentration_score": concentration_score,
        "coverage_log": math.log1p(max(0.0, coverage_per_second)),
        "runtime_proxy_penalty": runtime_proxy_penalty,
        "execution_gate": execution_gate,
        "truth_gate": truth_gate,
        "compact_truth_proxy": compact_truth_proxy,
        "compact_execution_proxy": compact_execution_proxy,
        "continuous_reward": continuous_reward,
        "reward": reward,
        "reward_profile": str(reward_profile_terms["reward_profile"]),
        **reward_profile_terms,
        **structural_terms,
    }


def reward_from_terms(terms: dict[str, float]) -> float:
    explicit = terms.get("reward")
    if explicit is not None:
        return float(explicit)
    execution_weight = float(terms.get("execution_weight") or 0.40)
    breadth_weight = float(terms.get("breadth_weight") or 0.30)
    concentration_weight = float(terms.get("concentration_weight") or 0.10)
    target_activation_weight = float(terms.get("target_activation_weight") or 0.10)
    target_dead_penalty_weight = float(terms.get("target_dead_penalty_weight") or 0.05)
    structural_weight = float(terms.get("structural_weight") or 0.10)
    target_region_rarity_weight = float(terms.get("target_region_rarity_weight") or 0.0)
    multi_region_bonus_weight = float(terms.get("multi_region_bonus_weight") or 0.0)
    activation_novelty_weight = float(terms.get("activation_novelty_weight") or 0.0)
    closure_progress_weight = float(terms.get("closure_progress_weight") or 0.0)
    target_isolation_penalty_weight = float(terms.get("target_isolation_penalty_weight") or 0.0)
    dead_word_penalty_weight = float(terms.get("dead_word_penalty_weight") or 0.0)
    return max(
        0.0,
        execution_weight * float(terms.get("execution_score") or 0.0)
        + breadth_weight * float(terms.get("breadth_score") or 0.0)
        + concentration_weight * float(terms.get("concentration_score") or 0.0)
        + target_activation_weight * float(terms.get("target_region_activated") or 0.0)
        + structural_weight * float(terms.get("structural_prior_score") or 0.0)
        + target_region_rarity_weight * float(terms.get("target_region_rarity_bonus") or 0.0)
        + multi_region_bonus_weight * float(terms.get("multi_region_bonus") or 0.0)
        + activation_novelty_weight * float(terms.get("activation_novelty_bonus") or 0.0)
        + closure_progress_weight * float(terms.get("closure_progress_bonus") or 0.0)
        - target_dead_penalty_weight * float(terms.get("target_region_still_dead") or 0.0)
        - target_isolation_penalty_weight * float(terms.get("target_isolation_penalty") or 0.0)
        - dead_word_penalty_weight * float(terms.get("dead_word_fraction") or 0.0),
    )


def frontier_from_summary(
    *,
    case_summary: dict[str, Any],
    summary_payload: dict[str, Any],
    template_payload: dict[str, Any],
    gpro_payload: dict[str, Any],
) -> dict[str, Any]:
    runner_args = dict(template_payload.get("runner_args_template") or {})
    effective_defaults = dict(summary_payload.get("effective_search_defaults") or {})
    best_case = dict(summary_payload.get("best_case") or {})
    return {
        "slice_name": str(summary_payload.get("slice_name") or template_payload.get("slice_name") or ""),
        "target": str(summary_payload.get("target") or template_payload.get("target") or ""),
        "phase": str(gpro_payload.get("phase") or "campaign"),
        "profile_family": str(summary_payload.get("profile_family") or runner_args.get("profile_family") or ""),
        "target_region": str(case_summary.get("target_region") or ""),
        "points_total": int(case_summary.get("real_subset_points_total") or 0),
        "best_case_points_hit": int(best_case.get("real_subset_points_hit") or 0),
        "best_case_dead_region_count": int(best_case.get("dead_region_count") or 0),
        "dead_region_count": int(case_summary.get("dead_region_count") or 0),
        "dead_output_word_count": int(case_summary.get("dead_output_word_count") or 0),
        "gpu_nstates": int(effective_defaults.get("gpu_nstates") or 0),
        "states_per_case": int(summary_payload.get("states_per_case") or runner_args.get("states_per_case") or 0),
        "batch_length": int(case_driver_payload(case_summary).get("batch_length") or runner_args.get("batch_length") or 0),
        "trace_length": int(dict(gpro_payload.get("gpro_defaults") or {}).get("trace_length") or runner_args.get("trace_length") or 0),
        "keep_top_k": int(effective_defaults.get("keep_top_k") or runner_args.get("keep_top_k") or 0),
        "pilot_cases": int(effective_defaults.get("pilot_sweep_cases") or dict(gpro_payload.get("gpro_defaults") or {}).get("cases") or 0),
    }


def stable_softmax(scores: list[float]) -> list[float]:
    if not scores:
        return []
    max_score = max(scores)
    exps = [math.exp(score - max_score) for score in scores]
    total = sum(exps)
    if total <= 0.0:
        return [1.0 / float(len(scores)) for _ in scores]
    return [value / total for value in exps]


def safe_group_advantages(rewards: list[float]) -> list[float]:
    if not rewards:
        return []
    if len(rewards) == 1:
        return [0.0]
    mean = sum(rewards) / float(len(rewards))
    variance = sum((reward - mean) ** 2 for reward in rewards) / float(len(rewards))
    std = math.sqrt(max(variance, 1e-12))
    return [(reward - mean) / std for reward in rewards]
