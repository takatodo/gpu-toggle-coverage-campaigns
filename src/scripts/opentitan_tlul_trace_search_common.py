#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

try:
    from .opentitan_tlul_sync_crv import SYNC_DEAD_WORD_PROFILES, SYNC_GRAMMAR_PROFILES  # noqa: E402
except ImportError:
    from opentitan_tlul_sync_crv import SYNC_DEAD_WORD_PROFILES, SYNC_GRAMMAR_PROFILES  # noqa: E402


TARGET_REGION_BY_VARIANT = {
    "target-reqfifo-upper": "reqfifo_storage_upper",
    "target-reqfifo-upper-hold": "reqfifo_storage_upper",
    "target-reqfifo-upper-filldrain": "reqfifo_storage_upper",
    "target-rspfifo-upper": "rspfifo_storage_upper",
    "target-rspfifo-upper-backpressure": "rspfifo_storage_upper",
    "target-rspfifo-upper-burst": "rspfifo_storage_upper",
    "target-response-payload": "response_payload",
    "target-response-payload-burst": "response_payload",
    "target-response-payload-mirror": "response_payload",
    "target-routing-control": "routing_control",
    "target-device-request-merge": "device_request_merge",
    "target-response-select-path": "response_select_path",
    "target-host-response-path": "host_response_path",
    "target-error-or-drop-path": "error_or_drop_path",
}

TRACE_VARIANTS = (
    "base",
    "upper-heavy",
    "fill-drain",
    "response-heavy",
    *TARGET_REGION_BY_VARIANT.keys(),
)

PRIORITIZED_TRACE_VARIANTS = (
    "base",
    "upper-heavy",
    "fill-drain",
    "response-heavy",
    "target-reqfifo-upper",
    "target-rspfifo-upper",
    "target-response-payload",
    "target-reqfifo-upper-hold",
    "target-rspfifo-upper-backpressure",
    "target-response-payload-burst",
    "target-reqfifo-upper-filldrain",
    "target-rspfifo-upper-burst",
    "target-response-payload-mirror",
)

TARGET_REGION_REPRESENTATIVE_VARIANTS = (
    "target-reqfifo-upper",
    "target-rspfifo-upper",
    "target-response-payload",
)

DRIVER_DEFAULTS = {
    "batch_length": 12,
    "seed": 1,
    "req_valid_pct": 65,
    "rsp_valid_pct": 70,
    "host_d_ready_pct": 75,
    "device_a_ready_pct": 80,
    "reset_cycles": 4,
    "drain_cycles": 16,
    "put_full_pct": 34,
    "put_partial_pct": 33,
    "req_fill_target": 2,
    "req_burst_len_max": 0,
    "req_family": 0,
    "req_address_mode": 0,
    "req_data_mode": 0,
    "req_data_hi_xor": 0,
    "access_ack_data_pct": 50,
    "rsp_error_pct": 10,
    "rsp_fill_target": 2,
    "rsp_delay_max": 4,
    "rsp_family": 0,
    "rsp_delay_mode": 0,
    "rsp_data_mode": 0,
    "rsp_data_hi_xor": 0,
    "trace_replay_enable": 0,
    "address_base": 0,
    "address_mask": 0xFFC,
    "source_mask": 0xFF,
}

PROFILE_FAMILIES = ("default", "dead-region", "mixed")


def _select_sync_profile(case_index: int, profile_family: str) -> tuple[dict[str, Any], str, int]:
    family = str(profile_family or "default")
    grammar_count = len(SYNC_GRAMMAR_PROFILES)
    dead_count = len(SYNC_DEAD_WORD_PROFILES)
    if family == "dead-region":
        slot = case_index % dead_count
        return dict(SYNC_DEAD_WORD_PROFILES[slot]), "dead-region", slot
    if family == "mixed":
        if (case_index % 2) == 0:
            slot = (case_index // 2) % grammar_count
            return dict(SYNC_GRAMMAR_PROFILES[slot]), "default", slot
        slot = (case_index // 2) % dead_count
        return dict(SYNC_DEAD_WORD_PROFILES[slot]), "dead-region", slot
    slot = case_index % grammar_count
    return dict(SYNC_GRAMMAR_PROFILES[slot]), "default", slot


def build_sync_driver(
    case_index: int,
    seed: int,
    batch_length: int,
    *,
    profile_family: str = "default",
) -> dict[str, Any]:
    driver = dict(DRIVER_DEFAULTS)
    profile, resolved_family, profile_slot = _select_sync_profile(case_index, profile_family)
    driver.update(profile)
    driver["seed"] = int(seed)
    driver["batch_length"] = int(batch_length)
    driver["profile_family"] = resolved_family
    driver["profile_slot"] = int(profile_slot)
    return driver


def variant_target_region(variant_name: str) -> str | None:
    return TARGET_REGION_BY_VARIANT.get(str(variant_name))


def select_trace_variants(limit: int) -> list[str]:
    capped = max(1, min(int(limit), len(TRACE_VARIANTS)))
    if capped <= len(TARGET_REGION_REPRESENTATIVE_VARIANTS) + 1:
        compact_priority = ("base", *TARGET_REGION_REPRESENTATIVE_VARIANTS)
        selected: list[str] = []
        for variant in compact_priority:
            if variant in TRACE_VARIANTS and variant not in selected:
                selected.append(variant)
            if len(selected) >= capped:
                return selected
        return selected
    selected: list[str] = []
    seen: set[str] = set()
    for variant in PRIORITIZED_TRACE_VARIANTS:
        if variant not in TRACE_VARIANTS or variant in seen:
            continue
        selected.append(variant)
        seen.add(variant)
        if len(selected) >= capped:
            return selected
    for variant in TRACE_VARIANTS:
        if variant in seen:
            continue
        selected.append(variant)
        if len(selected) >= capped:
            return selected
    return selected


def apply_sync_trace_variant(
    driver: dict[str, Any],
    *,
    variant_name: str,
    variant_index: int,
    seed: int,
) -> dict[str, Any]:
    updated = dict(driver)
    target_region = variant_target_region(variant_name)
    if variant_name == "upper-heavy":
        updated["req_data_mode"] = 4
        updated["rsp_data_mode"] = 4
        updated["req_data_hi_xor"] = [0xFFFF0000, 0xFF00FF00, 0xF0F00000][variant_index % 3]
        updated["rsp_data_hi_xor"] = [0xFFF00000, 0x00FF0000, 0x0FF00000][variant_index % 3]
        updated["req_family"] = max(int(updated.get("req_family", 0)), 2)
        updated["rsp_family"] = max(int(updated.get("rsp_family", 0)), 1)
    elif variant_name == "fill-drain":
        updated["req_fill_target"] = 2
        updated["rsp_fill_target"] = 2
        updated["req_burst_len_max"] = max(int(updated.get("req_burst_len_max", 0)), 6 + (variant_index % 3))
        updated["req_valid_pct"] = 92
        updated["rsp_valid_pct"] = 92
        updated["host_d_ready_pct"] = 94
        updated["device_a_ready_pct"] = 94
        updated["drain_cycles"] = max(int(updated.get("drain_cycles", 16)), 48 + 8 * (variant_index % 2))
        updated["put_full_pct"] = max(int(updated.get("put_full_pct", 34)), 78)
        updated["put_partial_pct"] = min(int(updated.get("put_partial_pct", 33)), 6)
    elif variant_name == "response-heavy":
        updated["rsp_family"] = 3
        updated["trace_replay_enable"] = 1
        updated["rsp_delay_mode"] = variant_index % 3
        updated["rsp_delay_max"] = 0 if variant_index % 2 == 0 else 1
        updated["rsp_data_mode"] = 4
        updated["rsp_data_hi_xor"] = [0xFFFF0000, 0xBEEF0000, 0x00FF0000][variant_index % 3]
        updated["access_ack_data_pct"] = 90
        updated["rsp_valid_pct"] = 96
        updated["host_d_ready_pct"] = 96
    elif target_region == "reqfifo_storage_upper":
        updated["trace_replay_enable"] = 1
        updated["req_family"] = 3
        updated["req_address_mode"] = 1 + (variant_index % 2)
        updated["req_data_mode"] = 4
        updated["req_data_hi_xor"] = [0xFFFF0000, 0xFF00FF00, 0xF0F00000][variant_index % 3]
        updated["req_fill_target"] = 2
        updated["req_burst_len_max"] = max(int(updated.get("req_burst_len_max", 0)), 8 + (variant_index % 4))
        updated["req_valid_pct"] = 96
        updated["device_a_ready_pct"] = 20 + 8 * (variant_index % 3)
        updated["host_d_ready_pct"] = 92
        updated["put_full_pct"] = 90
        updated["put_partial_pct"] = 2 + (variant_index % 3)
        updated["rsp_valid_pct"] = 35
        if variant_name == "target-reqfifo-upper-hold":
            updated["batch_length"] = max(int(updated.get("batch_length", 12)), 40)
            updated["drain_cycles"] = max(int(updated.get("drain_cycles", 16)), 64)
            updated["device_a_ready_pct"] = 8 + 4 * (variant_index % 2)
            updated["host_d_ready_pct"] = 98
            updated["req_burst_len_max"] = max(int(updated.get("req_burst_len_max", 0)), 12)
        elif variant_name == "target-reqfifo-upper-filldrain":
            updated["batch_length"] = max(int(updated.get("batch_length", 12)), 56)
            updated["drain_cycles"] = max(int(updated.get("drain_cycles", 16)), 72)
            updated["req_fill_target"] = 2
            updated["rsp_fill_target"] = 2
            updated["req_valid_pct"] = 98
            updated["rsp_valid_pct"] = 96
            updated["device_a_ready_pct"] = 28
            updated["host_d_ready_pct"] = 98
            updated["req_burst_len_max"] = max(int(updated.get("req_burst_len_max", 0)), 14)
    elif target_region == "rspfifo_storage_upper":
        updated["trace_replay_enable"] = 1
        updated["req_family"] = 2 + (variant_index % 2)
        updated["req_address_mode"] = 2
        updated["req_data_mode"] = 4
        updated["req_data_hi_xor"] = [0xFF00FF00, 0xFFFF0000, 0xDEAD0000][variant_index % 3]
        updated["req_fill_target"] = 2
        updated["req_burst_len_max"] = max(int(updated.get("req_burst_len_max", 0)), 6 + (variant_index % 3))
        updated["req_valid_pct"] = 94
        updated["device_a_ready_pct"] = 92
        updated["rsp_family"] = 3
        updated["rsp_fill_target"] = 2
        updated["rsp_delay_mode"] = variant_index % 3
        updated["rsp_delay_max"] = 0 if variant_index % 2 == 0 else 1
        updated["rsp_valid_pct"] = 98
        updated["host_d_ready_pct"] = 16 + 8 * (variant_index % 3)
        updated["rsp_data_mode"] = 4
        updated["rsp_data_hi_xor"] = [0xFFF00000, 0xBEEF0000, 0x00FF0000][variant_index % 3]
        updated["access_ack_data_pct"] = 95
        if variant_name == "target-rspfifo-upper-backpressure":
            updated["batch_length"] = max(int(updated.get("batch_length", 12)), 48)
            updated["drain_cycles"] = max(int(updated.get("drain_cycles", 16)), 64)
            updated["host_d_ready_pct"] = 4 + 4 * (variant_index % 2)
            updated["rsp_valid_pct"] = 100
            updated["access_ack_data_pct"] = 100
            updated["rsp_delay_max"] = 0
        elif variant_name == "target-rspfifo-upper-burst":
            updated["batch_length"] = max(int(updated.get("batch_length", 12)), 48)
            updated["req_burst_len_max"] = max(int(updated.get("req_burst_len_max", 0)), 10)
            updated["req_valid_pct"] = 98
            updated["device_a_ready_pct"] = 98
            updated["rsp_valid_pct"] = 98
            updated["host_d_ready_pct"] = 20
    elif target_region == "response_payload":
        updated["trace_replay_enable"] = 1
        updated["req_family"] = 2 + (variant_index % 2)
        updated["req_address_mode"] = variant_index % 3
        updated["req_data_mode"] = 4
        updated["req_data_hi_xor"] = [0xFFFF0000, 0xA5A50000, 0x12340000][variant_index % 3]
        updated["req_fill_target"] = 1 + (variant_index % 2)
        updated["req_burst_len_max"] = max(int(updated.get("req_burst_len_max", 0)), 4 + (variant_index % 3))
        updated["req_valid_pct"] = 88
        updated["device_a_ready_pct"] = 88
        updated["rsp_family"] = 3
        updated["rsp_delay_mode"] = variant_index % 3
        updated["rsp_delay_max"] = 0 if variant_index % 2 == 0 else 2
        updated["rsp_valid_pct"] = 98
        updated["host_d_ready_pct"] = 96
        updated["rsp_data_mode"] = 4
        updated["rsp_data_hi_xor"] = [0xFFFF0000, 0xBEEF0000, 0x0FF00000][variant_index % 3]
        updated["access_ack_data_pct"] = 100
        if variant_name == "target-response-payload-burst":
            updated["batch_length"] = max(int(updated.get("batch_length", 12)), 40)
            updated["req_burst_len_max"] = max(int(updated.get("req_burst_len_max", 0)), 8)
            updated["req_valid_pct"] = 96
            updated["device_a_ready_pct"] = 96
            updated["rsp_valid_pct"] = 100
            updated["host_d_ready_pct"] = 88
            updated["rsp_delay_max"] = 0
        elif variant_name == "target-response-payload-mirror":
            updated["req_data_mode"] = 4
            updated["rsp_data_mode"] = 4
            updated["req_data_hi_xor"] = [0xFFFF0000, 0xC0DE0000, 0xFACE0000][variant_index % 3]
            updated["rsp_data_hi_xor"] = updated["req_data_hi_xor"]
            updated["rsp_delay_mode"] = 0
            updated["rsp_delay_max"] = 0
            updated["rsp_valid_pct"] = 100
            updated["access_ack_data_pct"] = 100
    elif target_region == "routing_control":
        updated["trace_replay_enable"] = 1
        updated["batch_length"] = max(int(updated.get("batch_length", 12)), 48)
        updated["drain_cycles"] = max(int(updated.get("drain_cycles", 16)), 72)
        updated["req_fill_target"] = max(int(updated.get("req_fill_target", 0)), 4)
        updated["req_family"] = 3
        updated["req_address_mode"] = 1 + (variant_index % 3)
        updated["req_data_mode"] = 2
        updated["req_data_hi_xor"] = [0xFFFF0000, 0x00FF0000, 0xA5A50000][variant_index % 3]
        updated["req_valid_pct"] = 98
        updated["device_a_ready_pct"] = 24 + 8 * (variant_index % 3)
        updated["host_d_ready_pct"] = 92
        updated["rsp_fill_target"] = max(int(updated.get("rsp_fill_target", 0)), 2)
        updated["rsp_family"] = 1
        updated["rsp_delay_mode"] = 1
        updated["rsp_delay_max"] = max(int(updated.get("rsp_delay_max", 0)), 2)
    elif target_region == "device_request_merge":
        updated["trace_replay_enable"] = 1
        updated["batch_length"] = max(int(updated.get("batch_length", 12)), 56)
        updated["drain_cycles"] = max(int(updated.get("drain_cycles", 16)), 80)
        updated["req_fill_target"] = max(int(updated.get("req_fill_target", 0)), 4)
        updated["req_burst_len_max"] = max(int(updated.get("req_burst_len_max", 0)), 12)
        updated["req_family"] = 2 + (variant_index % 2)
        updated["req_address_mode"] = 3
        updated["req_data_mode"] = 1
        updated["req_data_hi_xor"] = [0xF0F00000, 0xFF00FF00, 0xDEAD0000][variant_index % 3]
        updated["req_valid_pct"] = 100
        updated["device_a_ready_pct"] = 16 + 8 * (variant_index % 2)
        updated["host_d_ready_pct"] = 88
        updated["rsp_fill_target"] = max(int(updated.get("rsp_fill_target", 0)), 3)
        updated["rsp_family"] = 1
        updated["rsp_delay_mode"] = 2
        updated["rsp_delay_max"] = max(int(updated.get("rsp_delay_max", 0)), 3)
    elif target_region == "response_select_path":
        updated["trace_replay_enable"] = 1
        updated["batch_length"] = max(int(updated.get("batch_length", 12)), 48)
        updated["drain_cycles"] = max(int(updated.get("drain_cycles", 16)), 72)
        updated["req_fill_target"] = max(int(updated.get("req_fill_target", 0)), 3)
        updated["req_family"] = 1 + (variant_index % 3)
        updated["req_address_mode"] = 2 + (variant_index % 2)
        updated["req_data_mode"] = 3
        updated["req_data_hi_xor"] = [0xA5A50000, 0x5A5A0000, 0xFACE0000][variant_index % 3]
        updated["req_valid_pct"] = 96
        updated["device_a_ready_pct"] = 88
        updated["host_d_ready_pct"] = 56 + 8 * (variant_index % 3)
        updated["access_ack_data_pct"] = 100
        updated["rsp_fill_target"] = max(int(updated.get("rsp_fill_target", 0)), 4)
        updated["rsp_family"] = 3
        updated["rsp_delay_mode"] = variant_index % 3
        updated["rsp_delay_max"] = 0 if variant_index % 2 == 0 else 1
        updated["rsp_data_mode"] = 4
        updated["rsp_data_hi_xor"] = [0xFFFF0000, 0xBEEF0000, 0x00FF0000][variant_index % 3]
    elif target_region == "host_response_path":
        updated["trace_replay_enable"] = 1
        updated["batch_length"] = max(int(updated.get("batch_length", 12)), 48)
        updated["drain_cycles"] = max(int(updated.get("drain_cycles", 16)), 72)
        updated["req_fill_target"] = max(int(updated.get("req_fill_target", 0)), 3)
        updated["req_family"] = 1
        updated["req_address_mode"] = 2
        updated["req_data_mode"] = 4
        updated["req_data_hi_xor"] = [0xFFFF0000, 0xC0DE0000, 0x12340000][variant_index % 3]
        updated["req_valid_pct"] = 94
        updated["device_a_ready_pct"] = 92
        updated["host_d_ready_pct"] = 100
        updated["access_ack_data_pct"] = 100
        updated["rsp_fill_target"] = max(int(updated.get("rsp_fill_target", 0)), 3)
        updated["rsp_family"] = 2
        updated["rsp_delay_mode"] = 0
        updated["rsp_delay_max"] = 0
        updated["rsp_data_mode"] = 4
        updated["rsp_data_hi_xor"] = [0xFFF00000, 0xF0FF0000, 0xBEEF0000][variant_index % 3]
    elif target_region == "error_or_drop_path":
        updated["trace_replay_enable"] = 1
        updated["batch_length"] = max(int(updated.get("batch_length", 12)), 56)
        updated["drain_cycles"] = max(int(updated.get("drain_cycles", 16)), 96)
        updated["req_fill_target"] = max(int(updated.get("req_fill_target", 0)), 2)
        updated["req_family"] = 3
        updated["req_address_mode"] = 3
        updated["req_data_mode"] = 3
        updated["req_valid_pct"] = 90
        updated["device_a_ready_pct"] = 72
        updated["host_d_ready_pct"] = 24 + 8 * (variant_index % 2)
        updated["rsp_error_pct"] = max(int(updated.get("rsp_error_pct", 0)), 55)
        updated["rsp_fill_target"] = max(int(updated.get("rsp_fill_target", 0)), 4)
        updated["rsp_family"] = 3
        updated["rsp_delay_mode"] = 2
        updated["rsp_delay_max"] = max(int(updated.get("rsp_delay_max", 0)), 4)
        updated["rsp_data_mode"] = 3
        updated["rsp_data_hi_xor"] = [0xDEAD0000, 0xFACE0000, 0xC0DE0000][variant_index % 3]
    updated["seed"] = int(seed)
    if target_region:
        updated["target_region"] = target_region
    return updated


def _traffic_metric(case_summary: dict[str, Any], key: str) -> int:
    if case_summary.get(key) is not None:
        return int(case_summary.get(key) or 0)
    traffic = case_summary.get("traffic_counters") or {}
    return int(traffic.get(key) or 0)


def _trace_progress_metric(case_summary: dict[str, Any], key: str) -> int:
    if case_summary.get(key) is not None:
        return int(case_summary.get(key) or 0)
    trace_progress = case_summary.get("trace_progress") or {}
    return int(trace_progress.get(key) or 0)


def _bit_is_set(value: int, bit_index: int) -> int:
    return 1 if ((int(value) >> int(bit_index)) & 0x1) else 0


def _bit_count(value: int, mask: int) -> int:
    return int(bin(int(value) & int(mask)).count("1"))


def _edn_target_region_progress(case_summary: dict[str, Any], target_region: str) -> tuple[int, int, int, int] | None:
    family_seen = int(case_summary.get("oracle_semantic_family_seen_o") or 0)
    family_acked = int(case_summary.get("oracle_semantic_family_acked_o") or 0)
    case_seen = int(case_summary.get("oracle_semantic_case_seen_o") or 0)
    case_acked = int(case_summary.get("oracle_semantic_case_acked_o") or 0)
    accepted_traffic = sum(
        _traffic_metric(case_summary, key)
        for key in (
            "host_req_accepted_o",
            "device_req_accepted_o",
            "device_rsp_accepted_o",
            "host_rsp_accepted_o",
        )
    )
    progress_cycle_count = _trace_progress_metric(case_summary, "progress_cycle_count_o")
    observed_err = int(case_summary.get("oracle_observed_err_count_o") or 0)

    if target_region == "boot_sequence_progress":
        return (
            1 if (_bit_is_set(family_seen, 0) or _bit_count(case_seen, 0x7) > 0) else 0,
            1 if (_bit_is_set(family_acked, 0) or _bit_count(case_acked, 0x7) > 0) else 0,
            _bit_count(case_seen, 0x7),
            _bit_count(case_acked, 0x7),
        )
    if target_region == "auto_request_progress":
        return (
            1 if (_bit_is_set(family_seen, 1) or _bit_count(case_seen, 0x38) > 0) else 0,
            1 if (_bit_is_set(family_acked, 1) or _bit_count(case_acked, 0x38) > 0) else 0,
            _bit_count(case_seen, 0x38),
            _bit_count(case_acked, 0x38),
        )
    if target_region == "software_port_accept":
        return (
            1 if (_bit_is_set(family_seen, 2) or _bit_is_set(case_seen, 6)) else 0,
            1 if (_bit_is_set(family_acked, 2) or _bit_is_set(case_acked, 6)) else 0,
            _traffic_metric(case_summary, "host_rsp_accepted_o"),
            _bit_count(case_acked, 1 << 6),
        )
    if target_region == "reseed_vs_generate_dispatch":
        return (
            1 if (_bit_is_set(family_seen, 3) or _bit_count(case_seen, 0x30) > 0) else 0,
            1 if (_bit_is_set(family_acked, 3) or _bit_count(case_acked, 0x30) > 0) else 0,
            _bit_count(case_seen, 0x30),
            _bit_count(case_acked, 0x30),
        )
    if target_region == "request_accept_and_progress":
        return (
            1 if (accepted_traffic > 0 or progress_cycle_count > 0) else 0,
            1 if (_traffic_metric(case_summary, "device_req_accepted_o") > 0 or _traffic_metric(case_summary, "device_rsp_accepted_o") > 0) else 0,
            accepted_traffic,
            progress_cycle_count,
        )
    if target_region == "reject_or_error_terminal":
        return (
            1 if (_bit_is_set(family_seen, 4) or _bit_is_set(case_seen, 7) or observed_err > 0) else 0,
            1 if (_bit_is_set(family_acked, 4) or _bit_is_set(case_acked, 7) or observed_err > 0) else 0,
            observed_err,
            _bit_count(case_acked, 1 << 7),
        )
    return None


def score_prefilter_case(
    case_summary: dict[str, Any],
) -> tuple[int, int, int, int, int, int, float]:
    precomputed = case_summary.get("prefilter_score")
    if precomputed is not None:
        return tuple(precomputed)
    target_region = str(case_summary.get("target_region") or "")
    if "target_region_activated" in case_summary:
        target_region_activated = int(bool(case_summary.get("target_region_activated")))
    else:
        active_regions = set(case_summary.get("active_regions") or [])
        target_region_activated = 1 if target_region and target_region in active_regions else 0
    if "target_region_still_dead" in case_summary:
        target_region_still_dead = int(bool(case_summary.get("target_region_still_dead")))
    else:
        dead_regions = set(case_summary.get("dead_regions") or [])
        target_region_still_dead = 1 if target_region and target_region in dead_regions else 0
    host_req_accepted = _traffic_metric(case_summary, "host_req_accepted_o")
    device_req_accepted = _traffic_metric(case_summary, "device_req_accepted_o")
    device_rsp_accepted = _traffic_metric(case_summary, "device_rsp_accepted_o")
    host_rsp_accepted = _traffic_metric(case_summary, "host_rsp_accepted_o")
    req_backlog = max(0, host_req_accepted - device_req_accepted)
    rsp_backlog = max(0, device_rsp_accepted - host_rsp_accepted)
    reqfifo_depth = _trace_progress_metric(case_summary, "trace_metric_max_reqfifo_depth_o")
    rspfifo_depth = _trace_progress_metric(case_summary, "trace_metric_max_rspfifo_depth_o")
    reqfifo_nonempty = _trace_progress_metric(case_summary, "trace_metric_reqfifo_nonempty_seen_o")
    rspfifo_nonempty = _trace_progress_metric(case_summary, "trace_metric_rspfifo_nonempty_seen_o")
    a_data_mid_or = _trace_progress_metric(case_summary, "trace_metric_a_data_mid_or_o")
    a_address_window_or = _trace_progress_metric(case_summary, "trace_metric_a_address_window_or_o")
    device_d_data_low_or = _trace_progress_metric(case_summary, "trace_metric_device_d_data_low_or_o")
    device_d_data_upper_or = _trace_progress_metric(
        case_summary, "trace_metric_device_d_data_upper_or_o"
    )
    d_data_low_or = _trace_progress_metric(case_summary, "trace_metric_d_data_low_or_o")
    d_data_upper_or = _trace_progress_metric(case_summary, "trace_metric_d_data_upper_or_o")
    edn_progress = _edn_target_region_progress(case_summary, target_region)
    if edn_progress is not None:
        target_region_progress = edn_progress
    elif target_region == "reqfifo_storage_upper":
        target_region_progress = (
            1 if reqfifo_depth > 0 or reqfifo_nonempty > 0 else 0,
            1 if (a_data_mid_or != 0 or a_address_window_or != 0) else 0,
            reqfifo_depth,
            (a_data_mid_or != 0) + (a_address_window_or != 0),
        )
    elif target_region == "rspfifo_storage_upper":
        target_region_progress = (
            1 if rspfifo_depth > 0 or rspfifo_nonempty > 0 or device_rsp_accepted > 0 else 0,
            1 if (device_d_data_low_or != 0 or d_data_low_or != 0) else 0,
            max(rspfifo_depth, device_rsp_accepted),
            int(device_d_data_low_or != 0) + int(d_data_low_or != 0),
        )
    elif target_region == "response_payload":
        target_region_progress = (
            1 if (host_rsp_accepted > 0 or device_rsp_accepted > 0) else 0,
            1
            if (
                device_d_data_low_or != 0
                or device_d_data_upper_or != 0
                or d_data_low_or != 0
                or d_data_upper_or != 0
            )
            else 0,
            host_rsp_accepted + device_rsp_accepted,
            sum(
                int(value != 0)
                for value in (
                    device_d_data_low_or,
                    device_d_data_upper_or,
                    d_data_low_or,
                    d_data_upper_or,
                )
            ),
        )
    elif target_region == "routing_control":
        target_region_progress = (
            1 if (host_req_accepted > 0 or device_req_accepted > 0 or req_backlog > 0) else 0,
            1 if (a_address_window_or != 0 or a_data_mid_or != 0) else 0,
            host_req_accepted + device_req_accepted + req_backlog,
            int(a_address_window_or != 0) + int(a_data_mid_or != 0) + int(reqfifo_depth > 0),
        )
    elif target_region == "device_request_merge":
        target_region_progress = (
            1 if (reqfifo_depth > 0 or reqfifo_nonempty > 0 or req_backlog > 0) else 0,
            1 if (a_address_window_or != 0 or a_data_mid_or != 0) else 0,
            max(reqfifo_depth, req_backlog),
            int(reqfifo_nonempty != 0) + int(a_address_window_or != 0) + int(a_data_mid_or != 0),
        )
    elif target_region == "response_select_path":
        target_region_progress = (
            1
            if (
                rspfifo_depth > 0
                or rspfifo_nonempty > 0
                or device_rsp_accepted > 0
                or host_rsp_accepted > 0
            )
            else 0,
            1
            if (
                device_d_data_upper_or != 0
                or d_data_upper_or != 0
                or device_d_data_low_or != 0
                or d_data_low_or != 0
            )
            else 0,
            max(rspfifo_depth, device_rsp_accepted + host_rsp_accepted),
            sum(
                int(value != 0)
                for value in (
                    device_d_data_low_or,
                    device_d_data_upper_or,
                    d_data_low_or,
                    d_data_upper_or,
                )
            ),
        )
    elif target_region == "host_response_path":
        target_region_progress = (
            1 if host_rsp_accepted > 0 else 0,
            1 if (d_data_low_or != 0 or d_data_upper_or != 0) else 0,
            host_rsp_accepted,
            int(d_data_low_or != 0) + int(d_data_upper_or != 0),
        )
    elif target_region == "error_or_drop_path":
        target_region_progress = (
            1 if (int(case_summary.get("rsp_queue_overflow_o") or 0) > 0 or rsp_backlog > 0) else 0,
            1
            if (
                int(case_summary.get("rsp_queue_overflow_o") or 0) > 0
                or device_d_data_upper_or != 0
                or d_data_upper_or != 0
            )
            else 0,
            int(case_summary.get("rsp_queue_overflow_o") or 0) + rsp_backlog,
            int(device_d_data_upper_or != 0) + int(d_data_upper_or != 0),
        )
    else:
        target_region_progress = (
            0,
            0,
            device_req_accepted + device_rsp_accepted + host_rsp_accepted,
            host_req_accepted,
        )
    hit_points = int(case_summary.get("real_subset_points_hit") or 0)
    dead_region_count = int(case_summary.get("dead_region_count") or 9999)
    coverage_per_second = float(case_summary.get("real_subset_coverage_per_second") or 0.0)
    return (
        target_region_activated,
        target_region_progress[0],
        target_region_progress[1],
        target_region_progress[2],
        target_region_progress[3],
        -target_region_still_dead,
        hit_points,
        -dead_region_count,
        coverage_per_second,
    )


def rank_prefilter_cases(cases: list[dict[str, Any]], keep_top_k: int) -> list[dict[str, Any]]:
    ranked = sorted(cases, key=score_prefilter_case, reverse=True)
    if keep_top_k > 0:
        selected: list[dict[str, Any]] = list(ranked[:keep_top_k])
        seen_case_index = {int(case["case_index"]) for case in selected}
        best_by_region: dict[str, dict[str, Any]] = {}
        for case in ranked:
            region = str(case.get("target_region") or "")
            if not region:
                continue
            best_by_region.setdefault(region, case)
        for region_case in best_by_region.values():
            case_index = int(region_case["case_index"])
            if case_index in seen_case_index:
                continue
            selected.append(region_case)
            seen_case_index.add(case_index)
        return sorted(selected, key=score_prefilter_case, reverse=True)
    return ranked


def score_head_to_head_case(case_summary: dict[str, Any]) -> tuple[float, int, int, int, int]:
    target_region = str(case_summary.get("target_region") or "")
    if target_region == "reqfifo_storage_upper":
        gpu_trace_progress = case_summary.get("gpu_trace_progress") or {}
        gpu_reqfifo_depth = int(gpu_trace_progress.get("max_reqfifo_depth", 0))
        gpu_reqfifo_nonempty = int(gpu_trace_progress.get("persistent_reqfifo_nonempty_seen", 0))
        gpu_a_data_mid = int(gpu_trace_progress.get("persistent_a_data_mid_nonzero", 0))
        gpu_a_address = int(gpu_trace_progress.get("persistent_a_address_window_nonzero", 0))
        target_region_progress = (
            1 if gpu_reqfifo_depth > 0 or gpu_reqfifo_nonempty > 0 else 0,
            1 if (gpu_a_data_mid != 0 or gpu_a_address != 0) else 0,
            gpu_reqfifo_depth,
            gpu_a_data_mid + gpu_a_address,
        )
    elif target_region == "rspfifo_storage_upper":
        gpu_trace_progress = case_summary.get("gpu_trace_progress") or {}
        gpu_rspfifo_depth = int(gpu_trace_progress.get("max_rspfifo_depth", 0))
        gpu_rspfifo_nonempty = int(gpu_trace_progress.get("persistent_rspfifo_nonempty_seen", 0))
        gpu_device_d_data_low = int(
            gpu_trace_progress.get("persistent_device_d_data_low_nonzero", 0)
        )
        gpu_d_data_low = int(gpu_trace_progress.get("persistent_d_data_low_nonzero", 0))
        target_region_progress = (
            1
            if gpu_rspfifo_depth > 0
            or gpu_rspfifo_nonempty > 0
            or int(case_summary.get("gpu_device_rsp_accepted_o") or 0) > 0
            else 0,
            1 if (gpu_device_d_data_low != 0 or gpu_d_data_low != 0) else 0,
            max(gpu_rspfifo_depth, int(case_summary.get("gpu_device_rsp_accepted_o") or 0)),
            gpu_device_d_data_low + gpu_d_data_low,
        )
    elif target_region == "response_payload":
        gpu_trace_progress = case_summary.get("gpu_trace_progress") or {}
        gpu_device_d_data_low = int(
            gpu_trace_progress.get("persistent_device_d_data_low_nonzero", 0)
        )
        gpu_device_d_data_upper = int(
            gpu_trace_progress.get("persistent_device_d_data_upper_nonzero", 0)
        )
        gpu_d_data_low = int(gpu_trace_progress.get("persistent_d_data_low_nonzero", 0))
        gpu_d_data_upper = int(gpu_trace_progress.get("persistent_d_data_upper_nonzero", 0))
        gpu_host_rsp = int(case_summary.get("gpu_host_rsp_accepted_o") or 0)
        gpu_device_rsp = int(case_summary.get("gpu_device_rsp_accepted_o") or 0)
        target_region_progress = (
            1 if (gpu_host_rsp > 0 or gpu_device_rsp > 0) else 0,
            1
            if (
                gpu_device_d_data_low != 0
                or gpu_device_d_data_upper != 0
                or gpu_d_data_low != 0
                or gpu_d_data_upper != 0
            )
            else 0,
            gpu_host_rsp + gpu_device_rsp,
            gpu_device_d_data_low
            + gpu_device_d_data_upper
            + gpu_d_data_low
            + gpu_d_data_upper,
        )
    elif target_region == "routing_control":
        gpu_trace_progress = case_summary.get("gpu_trace_progress") or {}
        gpu_a_address = int(gpu_trace_progress.get("persistent_a_address_window_nonzero", 0))
        gpu_a_data_mid = int(gpu_trace_progress.get("persistent_a_data_mid_nonzero", 0))
        gpu_reqfifo_depth = int(gpu_trace_progress.get("max_reqfifo_depth", 0))
        gpu_host_req = int(case_summary.get("gpu_host_req_accepted_o") or 0)
        gpu_device_req = int(case_summary.get("gpu_device_req_accepted_o") or 0)
        target_region_progress = (
            1 if (gpu_host_req > 0 or gpu_device_req > 0 or gpu_reqfifo_depth > 0) else 0,
            1 if (gpu_a_address != 0 or gpu_a_data_mid != 0) else 0,
            gpu_host_req + gpu_device_req + gpu_reqfifo_depth,
            gpu_a_address + gpu_a_data_mid + int(gpu_reqfifo_depth > 0),
        )
    elif target_region == "device_request_merge":
        gpu_trace_progress = case_summary.get("gpu_trace_progress") or {}
        gpu_reqfifo_depth = int(gpu_trace_progress.get("max_reqfifo_depth", 0))
        gpu_reqfifo_nonempty = int(gpu_trace_progress.get("persistent_reqfifo_nonempty_seen", 0))
        gpu_a_address = int(gpu_trace_progress.get("persistent_a_address_window_nonzero", 0))
        gpu_a_data_mid = int(gpu_trace_progress.get("persistent_a_data_mid_nonzero", 0))
        target_region_progress = (
            1 if (gpu_reqfifo_depth > 0 or gpu_reqfifo_nonempty > 0) else 0,
            1 if (gpu_a_address != 0 or gpu_a_data_mid != 0) else 0,
            gpu_reqfifo_depth,
            gpu_reqfifo_nonempty + gpu_a_address + gpu_a_data_mid,
        )
    elif target_region == "response_select_path":
        gpu_trace_progress = case_summary.get("gpu_trace_progress") or {}
        gpu_rspfifo_depth = int(gpu_trace_progress.get("max_rspfifo_depth", 0))
        gpu_rspfifo_nonempty = int(gpu_trace_progress.get("persistent_rspfifo_nonempty_seen", 0))
        gpu_device_d_data_low = int(
            gpu_trace_progress.get("persistent_device_d_data_low_nonzero", 0)
        )
        gpu_device_d_data_upper = int(
            gpu_trace_progress.get("persistent_device_d_data_upper_nonzero", 0)
        )
        gpu_d_data_low = int(gpu_trace_progress.get("persistent_d_data_low_nonzero", 0))
        gpu_d_data_upper = int(gpu_trace_progress.get("persistent_d_data_upper_nonzero", 0))
        target_region_progress = (
            1
            if (
                gpu_rspfifo_depth > 0
                or gpu_rspfifo_nonempty > 0
                or int(case_summary.get("gpu_device_rsp_accepted_o") or 0) > 0
                or int(case_summary.get("gpu_host_rsp_accepted_o") or 0) > 0
            )
            else 0,
            1
            if (
                gpu_device_d_data_low != 0
                or gpu_device_d_data_upper != 0
                or gpu_d_data_low != 0
                or gpu_d_data_upper != 0
            )
            else 0,
            max(
                gpu_rspfifo_depth,
                int(case_summary.get("gpu_device_rsp_accepted_o") or 0)
                + int(case_summary.get("gpu_host_rsp_accepted_o") or 0),
            ),
            gpu_rspfifo_nonempty
            + gpu_device_d_data_low
            + gpu_device_d_data_upper
            + gpu_d_data_low
            + gpu_d_data_upper,
        )
    elif target_region == "host_response_path":
        gpu_trace_progress = case_summary.get("gpu_trace_progress") or {}
        gpu_d_data_low = int(gpu_trace_progress.get("persistent_d_data_low_nonzero", 0))
        gpu_d_data_upper = int(gpu_trace_progress.get("persistent_d_data_upper_nonzero", 0))
        gpu_host_rsp = int(case_summary.get("gpu_host_rsp_accepted_o") or 0)
        target_region_progress = (
            1 if gpu_host_rsp > 0 else 0,
            1 if (gpu_d_data_low != 0 or gpu_d_data_upper != 0) else 0,
            gpu_host_rsp,
            gpu_d_data_low + gpu_d_data_upper,
        )
    elif target_region == "error_or_drop_path":
        target_region_progress = (
            1
            if (
                int(case_summary.get("gpu_rsp_queue_overflow_o") or 0) > 0
                or int(case_summary.get("gpu_device_rsp_accepted_o") or 0) == 0
            )
            else 0,
            1 if int(case_summary.get("gpu_rsp_queue_overflow_o") or 0) > 0 else 0,
            int(case_summary.get("gpu_rsp_queue_overflow_o") or 0),
            int(case_summary.get("gpu_rsp_queue_overflow_o") or 0),
        )
    else:
        target_region_progress = (
            0,
            0,
            int(case_summary.get("gpu_device_req_accepted_o") or 0)
            + int(case_summary.get("gpu_device_rsp_accepted_o") or 0)
            + int(case_summary.get("gpu_host_rsp_accepted_o") or 0),
            int(case_summary.get("gpu_host_req_accepted_o") or 0),
        )
    dead_regions = int(case_summary.get("gpu_dead_region_count") or 9999)
    novelty_proxy = int(case_summary.get("real_subset_gpu_points_hit") or 0)
    ratio = float(case_summary.get("real_subset_gpu_over_cpu") or 0.0)
    return (
        ratio,
        target_region_progress[0],
        target_region_progress[1],
        target_region_progress[2],
        novelty_proxy,
        -dead_regions,
    )


def load_ranked_prefilter_cases(summary_path: str | Path, top_k: int) -> list[dict[str, Any]]:
    payload = json.loads(Path(summary_path).expanduser().resolve().read_text(encoding="utf-8"))
    ranked = payload.get("ranking", [])
    cases = payload.get("cases", [])
    best_by_target_region = payload.get("best_by_target_region") or {}
    case_by_index = {int(case["case_index"]): case for case in cases}
    refine_trace_replay = bool(payload.get("refine_trace_replay"))
    selected = list(ranked[:top_k] if top_k > 0 else ranked)
    seen_case_index = {int(item["case_index"]) for item in selected if item.get("case_index") is not None}
    for region_case in best_by_target_region.values():
        case_index = int(region_case["case_index"])
        if case_index in seen_case_index:
            continue
        case = case_by_index.get(case_index)
        if case is None:
            continue
        selected.append(
            {
                "case_index": case_index,
                "prefilter_stage": region_case.get("prefilter_stage"),
            }
        )
        seen_case_index.add(case_index)
    built: list[dict[str, Any]] = []
    for rank_index, item in enumerate(selected):
        case_index = int(item["case_index"])
        case = case_by_index[case_index]
        prefilter_stage = str(case.get("prefilter_stage") or item.get("prefilter_stage") or "coarse-packed")
        built.append(
            {
                "rank_index": rank_index,
                "case_index": case_index,
                "seed": int(case["seed"]),
                "driver": dict(case["driver"]),
                "trace_summary": dict(case.get("trace_summary") or {}),
                "batch_payload": dict(case.get("batch_payload") or {}),
                "batch_json": str(Path(case["batch_json"]).expanduser().resolve()),
                "variant_name": case.get("variant_name"),
                "target_region": case.get("target_region"),
                "profile_family": case.get("driver", {}).get("profile_family"),
                "profile_slot": case.get("driver", {}).get("profile_slot"),
                "states_per_case": int(case.get("states_per_case") or 1),
                "prefilter_stage": prefilter_stage,
                "gpu_trace_replay": bool(
                    refine_trace_replay and prefilter_stage == "refined-single-gpu"
                ),
            }
        )
    return built
