#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


SYNC_GRAMMAR_PROFILES = [
    {
        "req_family": 0,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "req_fill_target": 0,
        "req_data_hi_xor": 0x00000000,
        "rsp_family": 0,
        "rsp_delay_mode": 0,
        "rsp_data_mode": 0,
        "rsp_fill_target": 0,
        "rsp_data_hi_xor": 0x00000000,
    },
    {
        "req_family": 1,
        "req_address_mode": 1,
        "req_data_mode": 1,
        "req_fill_target": 1,
        "req_data_hi_xor": 0xffff0000,
        "rsp_family": 0,
        "rsp_delay_mode": 0,
        "rsp_data_mode": 0,
        "rsp_fill_target": 0,
        "rsp_data_hi_xor": 0x00000000,
        "address_mask": 0x3C,
        "source_mask": 0x0F,
        "put_partial_pct": 78,
        "put_full_pct": 4,
        "rsp_valid_pct": 82,
    },
    {
        "req_family": 2,
        "req_address_mode": 2,
        "req_data_mode": 4,
        "req_fill_target": 2,
        "req_data_hi_xor": 0xff00ff00,
        "rsp_family": 1,
        "rsp_delay_mode": 1,
        "rsp_data_mode": 4,
        "rsp_fill_target": 1,
        "rsp_data_hi_xor": 0x00ff0000,
        "address_mask": 0xFC,
        "source_mask": 0x1F,
        "req_burst_len_max": 2,
        "rsp_delay_max": 1,
        "host_d_ready_pct": 68,
        "device_a_ready_pct": 92,
    },
    {
        "req_family": 3,
        "req_address_mode": 3,
        "req_data_mode": 3,
        "req_fill_target": 2,
        "req_data_hi_xor": 0xf0f00000,
        "rsp_family": 2,
        "rsp_delay_mode": 2,
        "rsp_data_mode": 2,
        "rsp_fill_target": 2,
        "rsp_data_hi_xor": 0xffff0000,
        "address_mask": 0x3FC,
        "source_mask": 0x3F,
        "req_burst_len_max": 4,
        "rsp_delay_max": 8,
        "req_valid_pct": 88,
        "device_a_ready_pct": 58,
    },
    {
        "req_family": 1,
        "req_address_mode": 0,
        "req_data_mode": 2,
        "req_fill_target": 1,
        "req_data_hi_xor": 0x00ff00ff,
        "rsp_family": 1,
        "rsp_delay_mode": 0,
        "rsp_data_mode": 1,
        "rsp_fill_target": 1,
        "rsp_data_hi_xor": 0x00ff00ff,
        "address_mask": 0xFFC,
        "source_mask": 0xFF,
        "put_partial_pct": 8,
        "put_full_pct": 76,
        "rsp_valid_pct": 72,
    },
    {
        "req_family": 2,
        "req_address_mode": 1,
        "req_data_mode": 3,
        "req_fill_target": 2,
        "req_data_hi_xor": 0xa5a50000,
        "rsp_family": 2,
        "rsp_delay_mode": 1,
        "rsp_data_mode": 2,
        "rsp_fill_target": 2,
        "rsp_data_hi_xor": 0x5a5a0000,
        "address_mask": 0xFC,
        "source_mask": 0x0F,
        "req_burst_len_max": 3,
        "rsp_delay_max": 3,
        "host_d_ready_pct": 54,
        "device_a_ready_pct": 96,
    },
    {
        "req_family": 3,
        "req_address_mode": 2,
        "req_data_mode": 4,
        "req_fill_target": 2,
        "req_data_hi_xor": 0xfffff000,
        "rsp_family": 3,
        "rsp_delay_mode": 2,
        "rsp_data_mode": 4,
        "rsp_fill_target": 2,
        "rsp_data_hi_xor": 0x0fff0000,
        "address_mask": 0x3FC,
        "source_mask": 0x1F,
        "req_burst_len_max": 1,
        "rsp_delay_max": 10,
        "rsp_error_pct": 6,
        "rsp_valid_pct": 44,
    },
    {
        "req_family": 0,
        "req_address_mode": 3,
        "req_data_mode": 1,
        "req_fill_target": 0,
        "req_data_hi_xor": 0x0f0f0000,
        "rsp_family": 1,
        "rsp_delay_mode": 3,
        "rsp_data_mode": 1,
        "rsp_fill_target": 2,
        "rsp_data_hi_xor": 0xf0f00000,
        "address_mask": 0xFFC,
        "source_mask": 0x3F,
        "req_valid_pct": 82,
        "host_d_ready_pct": 92,
        "drain_cycles": 24,
    },
    {
        "req_family": 1,
        "req_address_mode": 2,
        "req_data_mode": 4,
        "req_fill_target": 2,
        "req_data_hi_xor": 0x12340000,
        "rsp_family": 0,
        "rsp_delay_mode": 1,
        "rsp_data_mode": 3,
        "rsp_fill_target": 1,
        "rsp_data_hi_xor": 0x43210000,
        "address_mask": 0x3FC,
        "source_mask": 0x1F,
        "req_burst_len_max": 5,
        "put_full_pct": 18,
        "put_partial_pct": 42,
        "rsp_valid_pct": 50,
    },
    {
        "req_family": 2,
        "req_address_mode": 3,
        "req_data_mode": 0,
        "req_fill_target": 2,
        "req_data_hi_xor": 0xfff00000,
        "rsp_family": 1,
        "rsp_delay_mode": 2,
        "rsp_data_mode": 0,
        "rsp_fill_target": 2,
        "rsp_data_hi_xor": 0x00fff000,
        "address_mask": 0xFFC,
        "source_mask": 0x3F,
        "req_burst_len_max": 2,
        "req_valid_pct": 94,
        "host_d_ready_pct": 84,
        "device_a_ready_pct": 74,
    },
    {
        "req_family": 3,
        "req_address_mode": 1,
        "req_data_mode": 1,
        "req_fill_target": 2,
        "req_data_hi_xor": 0xdead0000,
        "rsp_family": 2,
        "rsp_delay_mode": 3,
        "rsp_data_mode": 2,
        "rsp_fill_target": 2,
        "rsp_data_hi_xor": 0xbeef0000,
        "address_mask": 0xFC,
        "source_mask": 0x0F,
        "req_burst_len_max": 6,
        "rsp_delay_max": 0,
        "rsp_error_pct": 0,
        "device_a_ready_pct": 48,
    },
    {
        "req_family": 0,
        "req_address_mode": 1,
        "req_data_mode": 4,
        "req_fill_target": 1,
        "req_data_hi_xor": 0x33000000,
        "rsp_family": 3,
        "rsp_delay_mode": 0,
        "rsp_data_mode": 3,
        "rsp_fill_target": 2,
        "rsp_data_hi_xor": 0xcc000000,
        "address_mask": 0x3C,
        "source_mask": 0xFF,
        "req_valid_pct": 58,
        "rsp_valid_pct": 90,
        "drain_cycles": 40,
    },
]

SYNC_GRAMMAR_COMBOS = [
    (
        profile["req_family"],
        profile["req_address_mode"],
        profile["req_data_mode"],
        profile["rsp_family"],
        profile["rsp_delay_mode"],
        profile["rsp_data_mode"],
    )
    for profile in SYNC_GRAMMAR_PROFILES
]

SYNC_DEAD_WORD_PROFILES = [
    {
        "req_family": 3,
        "req_address_mode": 3,
        "req_data_mode": 4,
        "req_fill_target": 2,
        "req_burst_len_max": 8,
        "req_data_hi_xor": 0xFFFF0000,
        "rsp_family": 3,
        "rsp_delay_mode": 0,
        "rsp_data_mode": 4,
        "rsp_fill_target": 2,
        "rsp_delay_max": 0,
        "rsp_data_hi_xor": 0xFFF00000,
        "batch_length": 48,
        "drain_cycles": 64,
        "req_valid_pct": 96,
        "rsp_valid_pct": 96,
        "host_d_ready_pct": 96,
        "device_a_ready_pct": 96,
        "put_full_pct": 92,
        "put_partial_pct": 0,
        "address_mask": 0x3FC,
        "source_mask": 0x3F,
    },
    {
        "req_family": 2,
        "req_address_mode": 2,
        "req_data_mode": 4,
        "req_fill_target": 2,
        "req_burst_len_max": 6,
        "req_data_hi_xor": 0xFF00FF00,
        "rsp_family": 1,
        "rsp_delay_mode": 1,
        "rsp_data_mode": 4,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
        "rsp_data_hi_xor": 0x00FF0000,
        "batch_length": 40,
        "drain_cycles": 56,
        "req_valid_pct": 92,
        "rsp_valid_pct": 90,
        "host_d_ready_pct": 94,
        "device_a_ready_pct": 94,
        "put_full_pct": 78,
        "put_partial_pct": 6,
        "address_mask": 0xFFC,
        "source_mask": 0x1F,
    },
    {
        "req_family": 1,
        "req_address_mode": 1,
        "req_data_mode": 4,
        "req_fill_target": 2,
        "req_burst_len_max": 5,
        "req_data_hi_xor": 0xDEAD0000,
        "rsp_family": 2,
        "rsp_delay_mode": 2,
        "rsp_data_mode": 4,
        "rsp_fill_target": 2,
        "rsp_delay_max": 2,
        "rsp_data_hi_xor": 0xBEEF0000,
        "batch_length": 36,
        "drain_cycles": 48,
        "req_valid_pct": 90,
        "rsp_valid_pct": 88,
        "host_d_ready_pct": 90,
        "device_a_ready_pct": 92,
        "put_full_pct": 64,
        "put_partial_pct": 12,
        "address_mask": 0x3FC,
        "source_mask": 0xFF,
    },
]


def clamp_int(value: int, lo: int, hi: int) -> int:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def clamp_pct(value: int) -> int:
    return clamp_int(value, 0, 100)


def prng_next(state: int) -> int:
    return (state * 1664525 + 1013904223) & 0xFFFF_FFFF


def mutate_sync_driver(base_driver: dict[str, Any], *, seed: int, mutation_mode: str) -> dict[str, Any]:
    if mutation_mode == "seed-only":
        return dict(base_driver)

    driver = dict(base_driver)
    state = seed & 0xFFFF_FFFF
    if state == 0:
        state = 1

    def next_word() -> int:
        nonlocal state
        state = prng_next(state)
        return state

    def mutate_pct(name: str, span: int, lo: int = 0, hi: int = 100) -> None:
        if name not in driver:
            return
        base = int(driver[name])
        delta = int(next_word() % (2 * span + 1)) - span
        driver[name] = clamp_int(base + delta, lo, hi)

    mutate_pct("req_valid_pct", 25, 5, 100)
    mutate_pct("rsp_valid_pct", 25, 5, 100)
    mutate_pct("host_d_ready_pct", 20, 5, 100)
    mutate_pct("device_a_ready_pct", 20, 5, 100)
    mutate_pct("rsp_error_pct", 20, 0, 100)

    if "rsp_delay_max" in driver:
        driver["rsp_delay_max"] = clamp_int(int(driver["rsp_delay_max"]) + (int(next_word() % 9) - 4), 0, 31)
    if "put_full_pct" in driver and "put_partial_pct" in driver:
        put_budget = 15 + int(next_word() % 71)
        put_full = int(next_word() % (put_budget + 1))
        driver["put_full_pct"] = clamp_pct(put_full)
        driver["put_partial_pct"] = clamp_pct(put_budget - put_full)
    if "req_burst_len_max" in driver:
        driver["req_burst_len_max"] = clamp_int(int(driver["req_burst_len_max"]) + (int(next_word() % 7) - 3), 0, 15)
    if "req_fill_target" in driver:
        driver["req_fill_target"] = clamp_int(int(driver["req_fill_target"]) + (int(next_word() % 3) - 1), 0, 2)
    if "rsp_fill_target" in driver:
        driver["rsp_fill_target"] = clamp_int(int(driver["rsp_fill_target"]) + (int(next_word() % 3) - 1), 0, 2)
    if "req_data_hi_xor" in driver:
        hi_masks = [0x00000000, 0x00ff0000, 0xff000000, 0xffff0000, 0xf0f00000, 0x0f0f0000]
        driver["req_data_hi_xor"] = hi_masks[int(next_word() % len(hi_masks))]
    if "rsp_data_hi_xor" in driver:
        hi_masks = [0x00000000, 0x00ff0000, 0xff000000, 0xffff0000, 0xf0f00000, 0x0f0f0000]
        driver["rsp_data_hi_xor"] = hi_masks[int(next_word() % len(hi_masks))]
    for key in (
        "req_family",
        "req_address_mode",
        "req_data_mode",
        "rsp_family",
        "rsp_delay_mode",
        "rsp_data_mode",
    ):
        if key in driver:
            driver[key] = clamp_int(int(next_word() % 5), 0, 4)

    if "address_base" in driver:
        driver["address_base"] = int(next_word() & 0xFFC)
    if "address_mask" in driver:
        mask_options = [0x3C, 0xFC, 0x3FC, 0xFFC]
        driver["address_mask"] = mask_options[int(next_word() % len(mask_options))]
    if "source_mask" in driver:
        source_options = [0x0F, 0x1F, 0x3F, 0xFF]
        driver["source_mask"] = source_options[int(next_word() % len(source_options))]
    if "batch_length" in driver:
        base_batch = int(driver["batch_length"])
        driver["batch_length"] = clamp_int(base_batch + (int(next_word() % 49) - 16), 8, 96)
    if "drain_cycles" in driver:
        driver["drain_cycles"] = clamp_int(int(driver["drain_cycles"]) + (int(next_word() % 17) - 8), 8, 128)

    if mutation_mode == "traffic-and-clocks":
        if "batch_length" in driver:
            driver["batch_length"] = clamp_int(24 + int(next_word() % 73), 24, 128)
        if "req_valid_pct" in driver:
            driver["req_valid_pct"] = clamp_int(45 + int(next_word() % 56), 20, 100)
        if "rsp_valid_pct" in driver:
            driver["rsp_valid_pct"] = clamp_int(45 + int(next_word() % 56), 20, 100)
        if "host_d_ready_pct" in driver:
            driver["host_d_ready_pct"] = clamp_int(10 + int(next_word() % 81), 5, 100)
        if "device_a_ready_pct" in driver:
            driver["device_a_ready_pct"] = clamp_int(10 + int(next_word() % 81), 5, 100)
        if "drain_cycles" in driver:
            driver["drain_cycles"] = clamp_int(16 + int(next_word() % 49), 16, 160)

    return driver


def inject_sync_grammar_combo(driver: dict[str, Any], combo_index: int) -> dict[str, Any]:
    updated = dict(driver)
    profile = SYNC_GRAMMAR_PROFILES[combo_index % len(SYNC_GRAMMAR_PROFILES)]
    for key, value in profile.items():
        if key in updated:
            updated[key] = value
    if "put_full_pct" in updated and "put_partial_pct" in updated:
        put_budget = clamp_pct(int(updated["put_full_pct"]) + int(updated["put_partial_pct"]))
        if put_budget == 0:
            updated["put_full_pct"] = 0
            updated["put_partial_pct"] = 0
        elif int(updated["put_full_pct"]) + int(updated["put_partial_pct"]) != put_budget:
            full = clamp_pct(int(updated["put_full_pct"]))
            full = min(full, put_budget)
            updated["put_full_pct"] = full
            updated["put_partial_pct"] = put_budget - full
    return updated


def build_sync_candidate_driver(
    base_driver: dict[str, Any],
    *,
    seed: int,
    mutation_mode: str,
    combo_index: int | None = None,
) -> dict[str, Any]:
    driver = mutate_sync_driver(base_driver, seed=seed, mutation_mode=mutation_mode)
    if combo_index is not None and mutation_mode != "seed-only":
        driver = inject_sync_grammar_combo(driver, combo_index)
    return driver


def apply_sync_wave_plateau_bias(
    base_driver: dict[str, Any],
    *,
    iteration_index: int,
    max_reqfifo_depth: int,
    max_rspfifo_depth: int,
    unique_a_data_upper16: int,
    unique_d_data_upper16: int,
    dead_output_word_count: int,
    novelty_points: int,
) -> dict[str, Any]:
    driver = dict(base_driver)
    if novelty_points > 0 and dead_output_word_count <= 5:
        return driver

    shallow_queue = max_reqfifo_depth <= 0 and max_rspfifo_depth <= 0
    narrow_upper_data = unique_a_data_upper16 <= 1 and unique_d_data_upper16 <= 1
    if not shallow_queue and not narrow_upper_data and dead_output_word_count <= 8:
        return driver

    profile = SYNC_GRAMMAR_PROFILES[(iteration_index + 6) % len(SYNC_GRAMMAR_PROFILES)]
    for key, value in profile.items():
        if key in driver:
            driver[key] = value

    if shallow_queue:
        driver["batch_length"] = max(int(driver.get("batch_length", 12)), 32)
        driver["drain_cycles"] = max(int(driver.get("drain_cycles", 16)), 40)
        driver["req_valid_pct"] = max(int(driver.get("req_valid_pct", 65)), 88)
        driver["rsp_valid_pct"] = max(int(driver.get("rsp_valid_pct", 70)), 88)
        driver["device_a_ready_pct"] = max(int(driver.get("device_a_ready_pct", 80)), 90)
        driver["host_d_ready_pct"] = max(int(driver.get("host_d_ready_pct", 75)), 90)
        driver["req_fill_target"] = 2
        driver["rsp_fill_target"] = 2
        driver["req_burst_len_max"] = max(int(driver.get("req_burst_len_max", 0)), 6)

    if narrow_upper_data:
        upper_masks = [0xFFFF0000, 0xFF00FF00, 0xF0F00000, 0xDEAD0000]
        upper_mask = upper_masks[iteration_index % len(upper_masks)]
        driver["req_data_mode"] = 4
        driver["rsp_data_mode"] = 4
        driver["req_data_hi_xor"] = upper_mask
        driver["rsp_data_hi_xor"] = ((upper_mask >> 4) | 0x00F00000) & 0xFFFF0000
        driver["req_family"] = 3 if shallow_queue else 2
        driver["rsp_family"] = 3 if shallow_queue else 1
        driver["req_address_mode"] = 3
        driver["rsp_delay_mode"] = 2 if shallow_queue else 1
        driver["source_mask"] = 0x3F
        driver["address_mask"] = 0x3FC

    return driver


def build_sync_dead_word_driver(
    base_driver: dict[str, Any],
    *,
    iteration_index: int,
    candidate_index: int,
) -> dict[str, Any]:
    driver = dict(base_driver)
    profile = SYNC_DEAD_WORD_PROFILES[
        (iteration_index + candidate_index) % len(SYNC_DEAD_WORD_PROFILES)
    ]
    for key, value in profile.items():
        if key in driver:
            driver[key] = value
    return driver
