#!/usr/bin/env python3
from __future__ import annotations

import argparse
import heapq
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
REPO_SCRIPTS = ROOT_DIR / "src/scripts"
GPU_RUNNER = ROOT_DIR / "src/scripts/run_opentitan_tlul_slice_gpu_baseline.py"

for path in (str(REPO_SCRIPTS),):
    if path not in sys.path:
        sys.path.insert(0, path)

from opentitan_tlul_baseline_common import estimate_sync_sequential_steps, load_batch_overrides  # noqa: E402
from opentitan_tlul_slice_benchmark_profiles import (  # noqa: E402
    DEFAULT_FREEZE_JSON,
    load_benchmark_freeze,
    resolve_slice_profile,
)
from opentitan_tlul_slice_search_tuning import resolve_slice_search_tuning  # noqa: E402
from opentitan_tlul_trace_search_common import (  # noqa: E402
    DRIVER_DEFAULTS,
    PROFILE_FAMILIES,
    apply_sync_trace_variant,
    build_sync_driver,
    score_prefilter_case as _score_prefilter_case_common,
    select_trace_variants,
    variant_target_region,
)
from gpu_runtime_batch_policy import apply_runtime_batch_policy  # noqa: E402
from search_scope_runtime_policy import apply_search_scope_runtime_policy  # noqa: E402
from grpo_coverage_common import load_json as _load_grpo_json, select_policy_candidates  # noqa: E402

TRAFFIC_COUNTER_KEYS = (
    "host_req_accepted_o",
    "device_req_accepted_o",
    "device_rsp_accepted_o",
    "host_rsp_accepted_o",
)
ORACLE_KEYS = (
    "oracle_expected_ok_count_o",
    "oracle_expected_err_count_o",
    "oracle_observed_ok_count_o",
    "oracle_observed_err_count_o",
    "oracle_semantic_family_seen_o",
    "oracle_semantic_family_acked_o",
    "oracle_semantic_case_seen_o",
    "oracle_semantic_case_acked_o",
    "oracle_req_signature_o",
    "oracle_stalled_req_signature_o",
    "oracle_req_signature_delta_o",
    "oracle_req_signature_precommit_o",
    "oracle_stalled_req_signature_precommit_o",
    "oracle_stalled_req_signature_postcommit_o",
    "oracle_req_signature_delta_precommit_o",
    "oracle_req_signature_delta_postcommit_o",
    "oracle_req_field_delta_mask_o",
    "oracle_req_stable_violation_o",
    "oracle_pre_handshake_traffic_cycles_o",
)

TRACE_PROGRESS_KEYS = (
    "progress_cycle_count_o",
    "debug_phase_o",
    "debug_cycle_count_o",
    "debug_trace_live_o",
    "debug_trace_req_active_o",
    "trace_metric_max_reqfifo_depth_o",
    "trace_metric_max_rspfifo_depth_o",
    "trace_metric_reqfifo_nonempty_seen_o",
    "trace_metric_rspfifo_nonempty_seen_o",
    "trace_metric_a_data_mid_or_o",
    "trace_metric_a_address_window_or_o",
    "trace_metric_device_d_data_low_or_o",
    "trace_metric_device_d_data_upper_or_o",
    "trace_metric_d_data_low_or_o",
    "trace_metric_d_data_upper_or_o",
)
_PREFILTER_SCORE_KEY = "_prefilter_score"
_INIT_FILE_METRIC_INT_FIELDS = (
    "global_line_count",
    "per_state_override_line_count",
    "per_state_override_state_count",
    "range_override_line_count",
    "range_override_state_count",
    "seed_override_line_count",
    "seed_override_state_count",
    "non_seed_override_line_count",
    "non_seed_override_state_count",
    "explicit_state_count",
    "packed_case_count",
    "driver_signal_count",
    "total_line_count",
    "naive_full_override_line_estimate",
    "line_reduction_vs_naive",
)


def _execution_gate_values(case_summary: dict[str, Any]) -> dict[str, Any]:
    progress_cycle_count = _trace_progress_metric(case_summary, "progress_cycle_count_o")
    debug_phase = _trace_progress_metric(case_summary, "debug_phase_o")
    debug_trace_live = _trace_progress_metric(case_summary, "debug_trace_live_o")
    debug_trace_req_active = _trace_progress_metric(case_summary, "debug_trace_req_active_o")
    explicit_accepted = case_summary.get("accepted_traffic_sum")
    if explicit_accepted is not None:
        accepted_traffic_sum = int(explicit_accepted or 0)
    else:
        accepted_traffic_sum = sum(_traffic_metric(case_summary, key) for key in TRAFFIC_COUNTER_KEYS)
    execution_left_reset = int((debug_phase & 0x7) != 0) if isinstance(debug_phase, int) else 0
    execution_progressed = int(progress_cycle_count > 0)
    execution_live = int(
        debug_trace_live > 0 or debug_trace_req_active > 0 or execution_progressed > 0
    )
    execution_has_handshake = int(accepted_traffic_sum > 0)
    active_region_count = int(case_summary.get("active_region_count") or 0)
    points_hit = int(case_summary.get("real_subset_points_hit") or 0)
    if execution_has_handshake and active_region_count > 0 and points_hit > 0:
        truth_gate_status = "truth_alive"
    elif execution_has_handshake or execution_progressed:
        truth_gate_status = "proxy_only"
    else:
        truth_gate_status = "truth_dead"
    if execution_has_handshake:
        execution_status = "traffic_alive"
    elif execution_progressed or execution_live or execution_left_reset:
        execution_status = "progress_only"
    else:
        execution_status = "zero_activity"
    oracle_alive = int(case_summary.get("oracle_alive") or 0)
    mixed_commit_visibility = int(
        accepted_traffic_sum > 0
        and (debug_phase & 0x7) == 0
        and int(case_summary.get("debug_cycle_count_o") or 0) == 0
    )
    execution_signal_inconsistent = 0
    coverage_plane_inconsistent = int(
        (accepted_traffic_sum > 0 or oracle_alive > 0)
        and active_region_count <= 0
        and points_hit <= 0
    )
    return {
        "progress_cycle_count_o": int(progress_cycle_count),
        "debug_phase_o": int(debug_phase),
        "debug_trace_live_o": int(debug_trace_live),
        "debug_trace_req_active_o": int(debug_trace_req_active),
        "accepted_traffic_sum": int(accepted_traffic_sum),
        "execution_left_reset": int(execution_left_reset),
        "execution_progressed": int(execution_progressed),
        "execution_live": int(execution_live),
        "execution_has_handshake": int(execution_has_handshake),
        "execution_status": execution_status,
        "truth_gate_status": truth_gate_status,
        "execution_signal_inconsistent": execution_signal_inconsistent,
        "coverage_plane_inconsistent": coverage_plane_inconsistent,
        "mixed_commit_visibility": mixed_commit_visibility,
    }

_REQUEST_LOOPBACK_TARGET_REGION_BY_VARIANT = {
    "target-control-and-squash": "control_and_squash",
    "target-forward-request": "forward_request_path",
    "target-loopback-response": "loopback_response_path",
    "target-target-response-passthrough": "target_response_passthrough",
    "target-progress-and-backpressure": "progress_and_backpressure",
}

_REQUEST_LOOPBACK_VARIANT_PATCHES: dict[str, dict[str, int]] = {
    "target-control-and-squash": {
        "batch_length": 64,
        "drain_cycles": 80,
        "req_valid_pct": 98,
        "device_a_ready_pct": 18,
        "host_d_ready_pct": 98,
        "req_fill_target": 18,
        "put_full_pct": 25,
        "put_partial_pct": 25,
    },
    "target-forward-request": {
        "batch_length": 56,
        "drain_cycles": 72,
        "req_valid_pct": 98,
        "device_a_ready_pct": 100,
        "host_d_ready_pct": 98,
        "req_fill_target": 0,
        "put_full_pct": 45,
        "put_partial_pct": 45,
        "access_ack_data_pct": 100,
        "rsp_valid_pct": 100,
    },
    "target-loopback-response": {
        "batch_length": 64,
        "drain_cycles": 80,
        "req_valid_pct": 98,
        "device_a_ready_pct": 100,
        "host_d_ready_pct": 100,
        "req_fill_target": 34,
        "put_full_pct": 0,
        "put_partial_pct": 0,
        "access_ack_data_pct": 100,
        "rsp_valid_pct": 100,
    },
    "target-target-response-passthrough": {
        "batch_length": 64,
        "drain_cycles": 80,
        "req_valid_pct": 98,
        "device_a_ready_pct": 100,
        "host_d_ready_pct": 100,
        "req_fill_target": 0,
        "put_full_pct": 0,
        "put_partial_pct": 0,
        "access_ack_data_pct": 100,
        "rsp_valid_pct": 100,
        "rsp_error_pct": 35,
        "rsp_data_mode": 1,
        "rsp_data_hi_xor": 0xFFFF0000,
    },
    "target-progress-and-backpressure": {
        "batch_length": 72,
        "drain_cycles": 96,
        "req_valid_pct": 98,
        "device_a_ready_pct": 100,
        "host_d_ready_pct": 8,
        "req_fill_target": 0,
        "put_full_pct": 0,
        "put_partial_pct": 0,
        "access_ack_data_pct": 100,
        "rsp_valid_pct": 100,
        "rsp_error_pct": 20,
        "rsp_data_mode": 1,
        "rsp_data_hi_xor": 0xFFFF0000,
    },
}

_ROM_CTRL_FSM_TARGET_REGION_BY_VARIANT = {
    "target-rom-stream-low-to-kmac": "rom_stream_low_to_kmac",
    "target-top-digest-capture-progress": "top_digest_capture_progress",
    "target-kmac-vs-rom-race-resolution": "kmac_vs_rom_race_resolution",
    "target-checker-start-compare-done": "checker_start_compare_done",
    "target-terminal-done-bus-select-or-alert": "terminal_done_bus_select_or_alert",
}

_ROM_CTRL_FSM_VARIANT_PATCHES: dict[str, dict[str, int]] = {
    "target-rom-stream-low-to-kmac": {
        "batch_length": 64,
        "reset_cycles": 0,
        "drain_cycles": 24,
        "req_fill_target": 18,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 1,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "rsp_error_pct": 0,
        "rsp_fill_target": 3,
        "rsp_delay_max": 0,
    },
    "target-top-digest-capture-progress": {
        "batch_length": 72,
        "reset_cycles": 0,
        "drain_cycles": 28,
        "req_fill_target": 14,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 2,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "rsp_error_pct": 0,
        "rsp_fill_target": 4,
        "rsp_delay_max": 1,
    },
    "target-kmac-vs-rom-race-resolution": {
        "batch_length": 80,
        "reset_cycles": 0,
        "drain_cycles": 28,
        "req_fill_target": 16,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 3,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "rsp_error_pct": 0,
        "rsp_fill_target": 4,
        "rsp_delay_max": 1,
    },
    "target-checker-start-compare-done": {
        "batch_length": 88,
        "reset_cycles": 0,
        "drain_cycles": 32,
        "req_fill_target": 16,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 4,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-terminal-done-bus-select-or-alert": {
        "batch_length": 96,
        "reset_cycles": 0,
        "drain_cycles": 36,
        "req_fill_target": 18,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 5,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "rsp_error_pct": 8,
        "rsp_fill_target": 3,
        "rsp_delay_max": 1,
    },
}

_LC_CTRL_FSM_TARGET_REGION_BY_VARIANT = {
    "target-init-request-and-idle-progress": "init_request_and_idle_progress",
    "target-clock-bypass-and-transition-progress": "clock_bypass_and_transition_progress",
    "target-token-hash-accept-vs-error": "token_hash_accept_vs_error",
    "target-otp-program-request-ack-progress": "otp_program_request_ack_progress",
    "target-flash-rma-and-terminal-error-path": "flash_rma_and_terminal_error_path",
}

_LC_CTRL_FSM_VARIANT_PATCHES: dict[str, dict[str, int]] = {
    "target-init-request-and-idle-progress": {
        "batch_length": 64,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_fill_target": 4,
        "req_family": 1,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "rsp_error_pct": 0,
    },
    "target-clock-bypass-and-transition-progress": {
        "batch_length": 80,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_fill_target": 8,
        "req_family": 2,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "rsp_error_pct": 0,
    },
    "target-token-hash-accept-vs-error": {
        "batch_length": 80,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_fill_target": 8,
        "req_family": 3,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "rsp_error_pct": 0,
    },
    "target-otp-program-request-ack-progress": {
        "batch_length": 80,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_fill_target": 8,
        "req_family": 4,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "rsp_error_pct": 0,
    },
    "target-flash-rma-and-terminal-error-path": {
        "batch_length": 96,
        "req_valid_pct": 96,
        "rsp_valid_pct": 100,
        "req_fill_target": 10,
        "req_family": 5,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "rsp_error_pct": 24,
    },
}

_ALERT_HANDLER_PING_TIMER_TARGET_REGION_BY_VARIANT = {
    "target-edn-reseed-and-entropy": "edn_reseed_and_entropy",
    "target-alert-wait-issue-ack": "alert_wait_issue_ack",
    "target-esc-wait-issue-ack": "esc_wait_issue_ack",
    "target-id-skip-and-rotation": "id_skip_and_rotation",
    "target-fail-or-spurious-terminal": "fail_or_spurious_terminal",
}

_ALERT_HANDLER_PING_TIMER_VARIANT_PATCHES: dict[str, dict[str, int]] = {
    "target-edn-reseed-and-entropy": {
        "batch_length": 24,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_fill_target": 6,
        "req_family": 1,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-alert-wait-issue-ack": {
        "batch_length": 24,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_fill_target": 4,
        "req_family": 2,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-esc-wait-issue-ack": {
        "batch_length": 24,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_fill_target": 4,
        "req_family": 3,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-id-skip-and-rotation": {
        "batch_length": 24,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_fill_target": 4,
        "req_family": 4,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-fail-or-spurious-terminal": {
        "batch_length": 24,
        "req_valid_pct": 92,
        "rsp_valid_pct": 100,
        "req_fill_target": 4,
        "req_family": 5,
        "rsp_error_pct": 40,
        "rsp_fill_target": 1,
        "rsp_delay_max": 2,
    },
}

_ALERT_HANDLER_ESC_TIMER_TARGET_REGION_BY_VARIANT = {
    "target-timeout-countdown-progress": "timeout_countdown_progress",
    "target-phase0-entry-and-crashdump": "phase0_entry_and_crashdump",
    "target-phase1-phase2-progress": "phase1_phase2_progress",
    "target-phase3-terminal-escalation": "phase3_terminal_escalation",
    "target-fsm-error-or-counter-fault": "fsm_error_or_counter_fault",
}

_ALERT_HANDLER_ESC_TIMER_VARIANT_PATCHES: dict[str, dict[str, int]] = {
    "target-timeout-countdown-progress": {
        "batch_length": 24,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_fill_target": 6,
        "req_family": 1,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-phase0-entry-and-crashdump": {
        "batch_length": 24,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_fill_target": 4,
        "req_family": 2,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-phase1-phase2-progress": {
        "batch_length": 28,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_fill_target": 6,
        "req_family": 3,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-phase3-terminal-escalation": {
        "batch_length": 32,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_fill_target": 8,
        "req_family": 4,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-fsm-error-or-counter-fault": {
        "batch_length": 24,
        "req_valid_pct": 92,
        "rsp_valid_pct": 100,
        "req_fill_target": 4,
        "req_family": 5,
        "rsp_error_pct": 40,
        "rsp_fill_target": 1,
        "rsp_delay_max": 2,
    },
}

_ENTROPY_SRC_MAIN_SM_TARGET_REGION_BY_VARIANT = {
    "target-boot-bypass-progress": "boot_bypass_progress",
    "target-startup-health-test-progress": "startup_health_test_progress",
    "target-continuous-sha3-pipeline": "continuous_sha3_pipeline",
    "target-fw-override-insert-and-digest": "fw_override_insert_and_digest",
    "target-alert-or-error-terminal": "alert_or_error_terminal",
}

_ENTROPY_SRC_MAIN_SM_VARIANT_PATCHES: dict[str, dict[str, int]] = {
    "target-boot-bypass-progress": {
        "batch_length": 80,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 2,
        "req_address_mode": 0,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-startup-health-test-progress": {
        "batch_length": 80,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 1,
        "req_address_mode": 0,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-continuous-sha3-pipeline": {
        "batch_length": 96,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 1,
        "req_address_mode": 1,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-fw-override-insert-and-digest": {
        "batch_length": 80,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 3,
        "req_address_mode": 0,
        "rsp_error_pct": 0,
        "rsp_fill_target": 3,
        "rsp_delay_max": 1,
    },
    "target-alert-or-error-terminal": {
        "batch_length": 80,
        "req_valid_pct": 92,
        "rsp_valid_pct": 100,
        "req_family": 4,
        "req_address_mode": 0,
        "rsp_error_pct": 48,
        "rsp_fill_target": 1,
        "rsp_delay_max": 1,
    },
}

_EDN_MAIN_SM_TARGET_REGION_BY_VARIANT = {
    "target-boot-sequence-progress": "boot_sequence_progress",
    "target-auto-request-progress": "auto_request_progress",
    "target-software-port-accept": "software_port_accept",
    "target-reseed-vs-generate-dispatch": "reseed_vs_generate_dispatch",
    "target-request-accept-and-progress": "request_accept_and_progress",
    "target-reject-or-error-terminal": "reject_or_error_terminal",
}

_EDN_MAIN_SM_VARIANT_PATCHES: dict[str, dict[str, int]] = {
    "target-boot-sequence-progress": {
        "batch_length": 32,
        "req_fill_target": 20,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "rsp_error_pct": 0,
        "rsp_family": 0,
        "req_family": 1,
        "req_address_mode": 1,
        "req_data_mode": 0,
        "rsp_fill_target": 8,
        "rsp_delay_max": 0,
    },
    "target-auto-request-progress": {
        "batch_length": 32,
        "req_fill_target": 2,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "rsp_error_pct": 0,
        "rsp_family": 0,
        "req_family": 2,
        "req_address_mode": 1,
        "req_data_mode": 1,
        "rsp_fill_target": 6,
        "rsp_delay_max": 0,
    },
    "target-software-port-accept": {
        "batch_length": 24,
        "req_fill_target": 1,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "rsp_error_pct": 0,
        "rsp_family": 0,
        "req_family": 3,
        "req_address_mode": 0,
        "req_data_mode": 2,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-reseed-vs-generate-dispatch": {
        "batch_length": 40,
        "req_fill_target": 2,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "rsp_error_pct": 0,
        "rsp_family": 1,
        "req_family": 2,
        "req_address_mode": 1,
        "req_data_mode": 1,
        "rsp_fill_target": 7,
        "rsp_delay_max": 0,
    },
    "target-request-accept-and-progress": {
        "batch_length": 40,
        "req_fill_target": 4,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "rsp_error_pct": 0,
        "rsp_family": 0,
        "req_family": 2,
        "req_address_mode": 3,
        "req_data_mode": 1,
        "rsp_fill_target": 4,
        "rsp_delay_max": 0,
    },
    "target-reject-or-error-terminal": {
        "batch_length": 24,
        "req_fill_target": 4,
        "req_valid_pct": 88,
        "rsp_valid_pct": 100,
        "rsp_error_pct": 40,
        "rsp_family": 0,
        "req_family": 3,
        "req_address_mode": 2,
        "req_data_mode": 2,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
}

_AES_CIPHER_CONTROL_TARGET_REGION_BY_VARIANT = {
    "target-input-output-handshake-progress": "input_output_handshake_progress",
    "target-cipher-vs-keyexpand-dispatch": "cipher_vs_keyexpand_dispatch",
    "target-subbytes-wait-vs-ack": "subbytes_wait_vs_ack",
    "target-prng-reseed-and-clear-control": "prng_reseed_and_clear_control",
    "target-alert-or-multirail-error": "alert_or_multirail_error",
}

_AES_CIPHER_CONTROL_VARIANT_PATCHES: dict[str, dict[str, int]] = {
    "target-input-output-handshake-progress": {
        "batch_length": 24,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 0,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "host_d_ready_pct": 92,
        "device_a_ready_pct": 92,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-cipher-vs-keyexpand-dispatch": {
        "batch_length": 28,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 0,
        "req_address_mode": 1,
        "req_data_mode": 0,
        "host_d_ready_pct": 88,
        "device_a_ready_pct": 88,
        "rsp_error_pct": 0,
        "rsp_fill_target": 3,
        "rsp_delay_max": 1,
    },
    "target-subbytes-wait-vs-ack": {
        "batch_length": 28,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 0,
        "req_address_mode": 2,
        "req_data_mode": 0,
        "host_d_ready_pct": 40,
        "device_a_ready_pct": 40,
        "rsp_error_pct": 0,
        "rsp_fill_target": 4,
        "rsp_delay_max": 2,
    },
    "target-prng-reseed-and-clear-control": {
        "batch_length": 24,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 3,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "host_d_ready_pct": 72,
        "device_a_ready_pct": 72,
        "rsp_error_pct": 0,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
    "target-alert-or-multirail-error": {
        "batch_length": 24,
        "req_valid_pct": 92,
        "rsp_valid_pct": 100,
        "req_family": 5,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "host_d_ready_pct": 80,
        "device_a_ready_pct": 80,
        "rsp_error_pct": 36,
        "rsp_fill_target": 2,
        "rsp_delay_max": 1,
    },
}

_CSRNG_MAIN_SM_TARGET_REGION_BY_VARIANT = {
    "target-command-parse-progress": "command_parse_progress",
    "target-entropy-wait-vs-direct-issue": "entropy_wait_vs_direct_issue",
    "target-instantiate-reseed-generate-update-split": "instantiate_reseed_generate_update_split",
    "target-command-complete-return": "command_complete_return",
    "target-terminal-error-hold": "terminal_error_hold",
}

_CSRNG_MAIN_SM_VARIANT_PATCHES: dict[str, dict[str, int]] = {
    "target-command-parse-progress": {
        "batch_length": 24,
        "req_fill_target": 12,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "rsp_error_pct": 0,
        "req_family": 0,
        "rsp_fill_target": 1,
        "rsp_delay_max": 2,
    },
    "target-entropy-wait-vs-direct-issue": {
        "batch_length": 24,
        "req_fill_target": 8,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "rsp_error_pct": 0,
        "req_family": 1,
        "rsp_fill_target": 2,
        "rsp_delay_max": 2,
    },
    "target-instantiate-reseed-generate-update-split": {
        "batch_length": 32,
        "req_fill_target": 12,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "rsp_error_pct": 0,
        "req_family": 1,
        "rsp_fill_target": 1,
        "rsp_delay_max": 1,
    },
    "target-command-complete-return": {
        "batch_length": 28,
        "req_fill_target": 10,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "rsp_error_pct": 0,
        "req_family": 0,
        "rsp_fill_target": 0,
        "rsp_delay_max": 0,
    },
    "target-terminal-error-hold": {
        "batch_length": 24,
        "req_fill_target": 8,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 0,
        "rsp_error_pct": 40,
        "rsp_fill_target": 0,
        "rsp_delay_max": 0,
    },
}

_PWRMGR_FSM_TARGET_REGION_BY_VARIANT = {
    "target-powerup-request-ack-progress": "powerup_request_ack_progress",
    "target-clock-enable-status-progress": "clock_enable_status_progress",
    "target-otp-lc-init-and-done": "otp_lc_init_and_done",
    "target-low-power-entry-vs-abort-reset": "low_power_entry_vs_abort_reset",
    "target-rom-check-and-fetch-enable-path": "rom_check_and_fetch_enable_path",
}

_PWRMGR_FSM_VARIANT_PATCHES: dict[str, dict[str, int]] = {
    "target-powerup-request-ack-progress": {
        "batch_length": 24,
        "req_fill_target": 8,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 0,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "rsp_error_pct": 0,
        "rsp_fill_target": 1,
        "rsp_delay_max": 1,
    },
    "target-clock-enable-status-progress": {
        "batch_length": 28,
        "req_fill_target": 10,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 0,
        "req_address_mode": 0,
        "req_data_mode": 1,
        "rsp_error_pct": 0,
        "rsp_fill_target": 1,
        "rsp_delay_max": 1,
    },
    "target-otp-lc-init-and-done": {
        "batch_length": 32,
        "req_fill_target": 12,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 0,
        "req_address_mode": 0,
        "req_data_mode": 2,
        "rsp_error_pct": 0,
        "rsp_fill_target": 1,
        "rsp_delay_max": 1,
    },
    "target-low-power-entry-vs-abort-reset": {
        "batch_length": 32,
        "req_fill_target": 10,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 1,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "rsp_error_pct": 36,
        "rsp_fill_target": 1,
        "rsp_delay_max": 1,
    },
    "target-rom-check-and-fetch-enable-path": {
        "batch_length": 36,
        "req_fill_target": 12,
        "req_valid_pct": 100,
        "rsp_valid_pct": 100,
        "req_family": 4,
        "req_address_mode": 0,
        "req_data_mode": 0,
        "rsp_error_pct": 0,
        "rsp_fill_target": 1,
        "rsp_delay_max": 1,
    },
}


def _normalize_region_budget(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, int] = {}
    for region, quota in raw.items():
        region_name = str(region or "").strip()
        if not region_name:
            continue
        quota_int = int(quota or 0)
        if quota_int <= 0:
            continue
        normalized[region_name] = quota_int
    return normalized


def _parse_region_budget_arg(raw: str) -> dict[str, int]:
    text = str(raw or "").strip()
    if not text:
        return {}
    candidate_path = Path(text).expanduser()
    if candidate_path.exists():
        return _normalize_region_budget(json.loads(candidate_path.read_text(encoding="utf-8")))
    return _normalize_region_budget(json.loads(text))


def _default_region_budget(cases: list[dict[str, Any]]) -> dict[str, int]:
    regions = sorted({str(case.get("target_region") or "") for case in cases if str(case.get("target_region") or "")})
    return {region: 1 for region in regions}


def _region_budget_cases(cases: list[dict[str, Any]], region_budget: dict[str, int]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_case_index: set[int] = set()
    for region, quota in sorted(region_budget.items()):
        if int(quota) <= 0:
            continue
        region_cases = [
            case for case in cases if str(case.get("target_region") or "") == region
        ]
        for case in heapq.nlargest(int(quota), region_cases, key=score_prefilter_case):
            case_index = int(case["case_index"])
            if case_index in seen_case_index:
                continue
            selected.append(case)
            seen_case_index.add(case_index)
    return selected


def score_prefilter_case(case_summary: dict[str, Any]) -> tuple[Any, ...]:
    cached = case_summary.get(_PREFILTER_SCORE_KEY)
    if cached is not None:
        return cached
    execution_gate = _execution_gate_values(case_summary)
    precomputed = case_summary.get("prefilter_score")
    if precomputed is not None:
        score = tuple(precomputed)
        if len(score) < 14:
            score = (
                execution_gate["execution_has_handshake"],
                execution_gate["execution_progressed"],
                execution_gate["execution_left_reset"],
                execution_gate["execution_live"],
                execution_gate["accepted_traffic_sum"],
                *score,
            )
        case_summary[_PREFILTER_SCORE_KEY] = score
        return score
    score = (
        execution_gate["execution_has_handshake"],
        execution_gate["execution_progressed"],
        execution_gate["execution_left_reset"],
        execution_gate["execution_live"],
        execution_gate["accepted_traffic_sum"],
        *_score_prefilter_case_common(case_summary),
    )
    case_summary[_PREFILTER_SCORE_KEY] = score
    return score


def rank_prefilter_cases(
    cases: list[dict[str, Any]],
    keep_top_k: int,
    region_budget: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    effective_region_budget = _normalize_region_budget(region_budget)
    if not effective_region_budget:
        effective_region_budget = _default_region_budget(cases)
    if keep_top_k <= 0 and not effective_region_budget:
        return sorted(cases, key=score_prefilter_case, reverse=True)

    selected = list(heapq.nlargest(max(0, keep_top_k), cases, key=score_prefilter_case))
    seen_case_index = {int(case["case_index"]) for case in selected}
    for region_case in _region_budget_cases(cases, effective_region_budget):
        case_index_int = int(region_case["case_index"])
        if case_index_int in seen_case_index:
            continue
        selected.append(region_case)
        seen_case_index.add(case_index_int)
    return sorted(selected, key=score_prefilter_case, reverse=True)


def _update_region_case_pool(
    region_case_pool: dict[str, list[dict[str, Any]]],
    cases: list[dict[str, Any]],
    region_budget: dict[str, int] | None = None,
) -> None:
    normalized_budget = _normalize_region_budget(region_budget)
    pending_by_region: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        region = str(case.get("target_region") or "")
        if not region:
            continue
        pending_by_region.setdefault(region, []).append(case)
    for region, new_cases in pending_by_region.items():
        quota = int(normalized_budget.get(region) or 0) if normalized_budget else 1
        if quota <= 0:
            continue
        current_cases = list(region_case_pool.get(region) or [])
        region_case_pool[region] = list(
            heapq.nlargest(
                quota,
                current_cases + new_cases,
                key=score_prefilter_case,
            )
        )


def _update_incremental_topk(
    current_topk: list[dict[str, Any]],
    new_cases: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return list(current_topk) + list(new_cases)
    if not current_topk:
        return list(heapq.nlargest(limit, new_cases, key=score_prefilter_case))
    return list(heapq.nlargest(limit, list(current_topk) + list(new_cases), key=score_prefilter_case))


def _selected_prefilter_cases(
    topk_cases: list[dict[str, Any]],
    region_case_pool: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    selected = list(topk_cases)
    seen_case_index = {
        int(case["case_index"]) for case in selected if case.get("case_index") is not None
    }
    for region in sorted(region_case_pool):
        for region_case in list(region_case_pool.get(region) or []):
            case_index = region_case.get("case_index")
            if case_index is None:
                continue
            case_index_int = int(case_index)
            if case_index_int in seen_case_index:
                continue
            selected.append(region_case)
            seen_case_index.add(case_index_int)
    return sorted(selected, key=score_prefilter_case, reverse=True)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any], *, compact: bool) -> None:
    if compact:
        text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _template_defaults(template_args: dict[str, Any]) -> dict[str, Any]:
    defaults_path = template_args.get("batch_defaults_path")
    defaults: dict[str, Any] = {}
    if defaults_path:
        overrides = load_batch_overrides(str(defaults_path))
        defaults.update({key: value for key, value in overrides.items() if not str(key).startswith("_")})
    defaults.update(
        {
            key: value
            for key, value in dict(template_args.get("driver_defaults") or {}).items()
            if not str(key).startswith("_")
        }
    )
    return defaults


def _slice_trace_variants(
    slice_name: str,
    search_tuning: dict[str, Any],
    limit: int,
) -> list[str]:
    raw_variants = list(search_tuning.get("trace_variants") or [])
    custom_variants = [str(variant).strip() for variant in raw_variants if str(variant).strip()]
    if custom_variants:
        capped = max(1, min(int(limit), len(custom_variants)))
        return custom_variants[:capped]
    return select_trace_variants(int(limit))


def _slice_variant_target_region(slice_name: str, variant_name: str) -> str | None:
    normalized_slice = str(slice_name or "")
    if normalized_slice == "rom_ctrl_fsm":
        return _ROM_CTRL_FSM_TARGET_REGION_BY_VARIANT.get(str(variant_name or ""))
    if normalized_slice == "lc_ctrl_fsm":
        return _LC_CTRL_FSM_TARGET_REGION_BY_VARIANT.get(str(variant_name or ""))
    if normalized_slice == "tlul_request_loopback":
        return _REQUEST_LOOPBACK_TARGET_REGION_BY_VARIANT.get(str(variant_name or ""))
    if normalized_slice == "alert_handler_ping_timer":
        return _ALERT_HANDLER_PING_TIMER_TARGET_REGION_BY_VARIANT.get(str(variant_name or ""))
    if normalized_slice == "alert_handler_esc_timer":
        return _ALERT_HANDLER_ESC_TIMER_TARGET_REGION_BY_VARIANT.get(str(variant_name or ""))
    if normalized_slice == "entropy_src_main_sm":
        return _ENTROPY_SRC_MAIN_SM_TARGET_REGION_BY_VARIANT.get(str(variant_name or ""))
    if normalized_slice == "edn_main_sm":
        return _EDN_MAIN_SM_TARGET_REGION_BY_VARIANT.get(str(variant_name or ""))
    if normalized_slice == "aes_cipher_control":
        return _AES_CIPHER_CONTROL_TARGET_REGION_BY_VARIANT.get(str(variant_name or ""))
    if normalized_slice == "csrng_main_sm":
        return _CSRNG_MAIN_SM_TARGET_REGION_BY_VARIANT.get(str(variant_name or ""))
    if normalized_slice == "pwrmgr_fsm":
        return _PWRMGR_FSM_TARGET_REGION_BY_VARIANT.get(str(variant_name or ""))
    return variant_target_region(variant_name)


def _apply_slice_trace_variant(
    *,
    slice_name: str,
    driver: dict[str, Any],
    variant_name: str,
    variant_index: int,
    seed: int,
) -> dict[str, Any]:
    normalized_slice = str(slice_name or "")
    if normalized_slice == "rom_ctrl_fsm":
        updated = dict(driver)
        variant = str(variant_name or "")
        for key, value in _ROM_CTRL_FSM_VARIANT_PATCHES.get(variant, {}).items():
            updated[key] = value
        if variant == "target-kmac-vs-rom-race-resolution":
            updated["req_address_mode"] = int(seed) & 0x1
            updated["req_fill_target"] = 14 + (int(seed) % 5)
            updated["batch_length"] = 72 + ((int(seed) & 0x1) * 8)
            updated["rsp_delay_max"] = int(seed) & 0x1
        elif variant == "target-terminal-done-bus-select-or-alert":
            alert_mode = (((int(seed) >> 1) & 0x3) == 0)
            updated["req_fill_target"] = 16 + (int(seed) % 5)
            updated["batch_length"] = 88 + ((int(seed) & 0x1) * 8)
            updated["rsp_family"] = 1 if alert_mode else 0
            updated["rsp_error_pct"] = 56 if alert_mode else 8
        elif variant == "target-top-digest-capture-progress":
            updated["req_fill_target"] = 12 + (int(seed) % 5)
            updated["batch_length"] = 64 + ((int(seed) & 0x1) * 8)
        elif variant == "target-rom-stream-low-to-kmac":
            updated["req_fill_target"] = 16 + (int(seed) % 6)
        elif variant == "target-checker-start-compare-done":
            updated["req_fill_target"] = 14 + (int(seed) % 5)
            updated["batch_length"] = 80 + ((int(seed) & 0x1) * 8)
            updated["req_data_mode"] = 1 if ((int(seed) & 0x3) == 0) else 0
        updated["seed"] = int(seed)
        target_region = _slice_variant_target_region(slice_name, variant_name)
        if target_region:
            updated["target_region"] = target_region
        return updated
    if normalized_slice == "lc_ctrl_fsm":
        updated = dict(driver)
        for key, value in _LC_CTRL_FSM_VARIANT_PATCHES.get(str(variant_name or ""), {}).items():
            updated[key] = value
        if str(variant_name or "") == "target-token-hash-accept-vs-error":
            updated["req_address_mode"] = int(seed) & 0x1
        elif str(variant_name or "") == "target-flash-rma-and-terminal-error-path":
            updated["req_address_mode"] = int(seed) % 3
        updated["seed"] = int(seed)
        target_region = _slice_variant_target_region(slice_name, variant_name)
        if target_region:
            updated["target_region"] = target_region
        return updated
    if normalized_slice == "alert_handler_ping_timer":
        updated = dict(driver)
        for key, value in _ALERT_HANDLER_PING_TIMER_VARIANT_PATCHES.get(str(variant_name or ""), {}).items():
            updated[key] = value
        updated["seed"] = int(seed)
        target_region = _slice_variant_target_region(slice_name, variant_name)
        if target_region:
            updated["target_region"] = target_region
        return updated
    if normalized_slice == "alert_handler_esc_timer":
        updated = dict(driver)
        for key, value in _ALERT_HANDLER_ESC_TIMER_VARIANT_PATCHES.get(str(variant_name or ""), {}).items():
            updated[key] = value
        updated["seed"] = int(seed)
        target_region = _slice_variant_target_region(slice_name, variant_name)
        if target_region:
            updated["target_region"] = target_region
        return updated
    if normalized_slice == "entropy_src_main_sm":
        updated = dict(driver)
        for key, value in _ENTROPY_SRC_MAIN_SM_VARIANT_PATCHES.get(str(variant_name or ""), {}).items():
            updated[key] = value
        if str(variant_name or "") == "target-continuous-sha3-pipeline":
            updated["req_address_mode"] = 1 + (int(seed) & 0x1)
        updated["seed"] = int(seed)
        target_region = _slice_variant_target_region(slice_name, variant_name)
        if target_region:
            updated["target_region"] = target_region
        return updated
    if normalized_slice == "aes_cipher_control":
        updated = dict(driver)
        for key, value in _AES_CIPHER_CONTROL_VARIANT_PATCHES.get(str(variant_name or ""), {}).items():
            updated[key] = value
        if str(variant_name or "") == "target-cipher-vs-keyexpand-dispatch":
            updated["req_family"] = int(seed) % 3
            updated["req_address_mode"] = (int(seed) >> 1) % 3
        elif str(variant_name or "") == "target-subbytes-wait-vs-ack":
            updated["host_d_ready_pct"] = 20 + ((int(seed) & 0x3) * 20)
            updated["device_a_ready_pct"] = 20 + (((int(seed) >> 2) & 0x3) * 20)
        elif str(variant_name or "") == "target-prng-reseed-and-clear-control":
            updated["req_family"] = 3 + (int(seed) & 0x1)
            updated["req_data_mode"] = int(seed) & 0x1
        updated["seed"] = int(seed)
        target_region = _slice_variant_target_region(slice_name, variant_name)
        if target_region:
            updated["target_region"] = target_region
        return updated
    if normalized_slice == "edn_main_sm":
        updated = dict(driver)
        for key, value in _EDN_MAIN_SM_VARIANT_PATCHES.get(str(variant_name or ""), {}).items():
            updated[key] = value
        if str(variant_name or "") == "target-reseed-vs-generate-dispatch":
            updated["req_address_mode"] = 1 + (int(seed) & 0x1)
        updated["seed"] = int(seed)
        target_region = _slice_variant_target_region(slice_name, variant_name)
        if target_region:
            updated["target_region"] = target_region
        return updated
    if normalized_slice == "csrng_main_sm":
        updated = dict(driver)
        for key, value in _CSRNG_MAIN_SM_VARIANT_PATCHES.get(str(variant_name or ""), {}).items():
            updated[key] = value
        if str(variant_name or "") == "target-entropy-wait-vs-direct-issue":
            updated["req_address_mode"] = 1 + (int(seed) & 0x1)
        elif str(variant_name or "") == "target-instantiate-reseed-generate-update-split":
            updated["req_family"] = 1 + (int(seed) % 5)
            updated["req_address_mode"] = int(seed) & 0x1
            updated["req_data_mode"] = (int(seed) >> 1) & 0x1
        updated["seed"] = int(seed)
        target_region = _slice_variant_target_region(slice_name, variant_name)
        if target_region:
            updated["target_region"] = target_region
        return updated
    if normalized_slice == "pwrmgr_fsm":
        updated = dict(driver)
        for key, value in _PWRMGR_FSM_VARIANT_PATCHES.get(str(variant_name or ""), {}).items():
            updated[key] = value
        if str(variant_name or "") == "target-low-power-entry-vs-abort-reset":
            updated["req_family"] = 1 + (int(seed) % 3)
            updated["req_address_mode"] = int(seed) & 0x1
            updated["req_data_mode"] = (int(seed) >> 1) & 0x1
        elif str(variant_name or "") == "target-rom-check-and-fetch-enable-path":
            updated["req_address_mode"] = int(seed) & 0x1
            updated["req_fill_target"] = 10 + (int(seed) % 4)
        elif str(variant_name or "") == "target-otp-lc-init-and-done":
            updated["req_fill_target"] = 10 + (int(seed) % 3)
        elif str(variant_name or "") == "target-clock-enable-status-progress":
            updated["req_fill_target"] = 8 + (int(seed) % 3)
        updated["seed"] = int(seed)
        target_region = _slice_variant_target_region(slice_name, variant_name)
        if target_region:
            updated["target_region"] = target_region
        return updated
    if normalized_slice != "tlul_request_loopback":
        return apply_sync_trace_variant(
            driver,
            variant_name=variant_name,
            variant_index=variant_index,
            seed=seed,
        )
    updated = dict(driver)
    for key, value in _REQUEST_LOOPBACK_VARIANT_PATCHES.get(str(variant_name or ""), {}).items():
        updated[key] = value
    updated["seed"] = int(seed)
    target_region = _slice_variant_target_region(slice_name, variant_name)
    if target_region:
        updated["target_region"] = target_region
    return updated


def _bool_with_template(cli_value: bool | None, template_value: Any) -> bool:
    if cli_value is None:
        return bool(template_value)
    return bool(cli_value)


def _int_with_template(cli_value: int, template_value: Any, fallback: int) -> int:
    if int(cli_value) > 0:
        return int(cli_value)
    if template_value is not None:
        return int(template_value)
    return int(fallback)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a slice-generic OpenTitan TL-UL GPU sweep using a launch template."
    )
    parser.add_argument("--launch-template", required=True)
    parser.add_argument("--work-dir", default="")
    parser.add_argument("--cases", type=int, default=0)
    parser.add_argument("--variants-per-case", type=int, default=0)
    parser.add_argument("--seed-fanout", type=int, default=0)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--keep-top-k", type=int, default=0)
    parser.add_argument("--cleanup-non-topk", action="store_true")
    parser.add_argument("--trace-length", type=int, default=0)
    parser.add_argument("--batch-length", type=int, default=0)
    parser.add_argument("--profile-family", default="")
    parser.add_argument("--gpu-sequential-steps", type=int, default=0)
    parser.add_argument("--gpu-nstates", type=int, default=0)
    parser.add_argument("--states-per-case", type=int, default=0)
    parser.add_argument("--cases-per-launch", type=int, default=0)
    parser.add_argument("--gpu-reps", type=int, default=0)
    parser.add_argument("--cpu-reps", type=int, default=0)
    parser.add_argument("--sequential-rep-graph-mode", choices=("auto", "always", "never"), default="")
    parser.add_argument("--benchmark-freeze-json", default=str(DEFAULT_FREEZE_JSON))
    parser.add_argument(
        "--profile-scenario",
        choices=("auto", "single_step_small", "multi_step_medium"),
        default="auto",
    )
    parser.add_argument("--phase", choices=("sweep", "campaign"), default="sweep")
    parser.add_argument("--region-budget-json", default="")
    parser.add_argument("--execution-engine", choices=("gpu", "cpu"), default="gpu")
    parser.add_argument(
        "--gpu-runtime-policy",
        choices=("auto", "off"),
        default="off",
        help="Optionally scale cases/nstates/top-k from the direct runner using detected GPU memory tier.",
    )
    parser.add_argument(
        "--gpu-memory-total-mib",
        type=int,
        default=0,
        help="Override detected GPU memory for direct-run batching policy validation.",
    )
    parser.add_argument(
        "--search-scope-policy",
        choices=("auto", "off"),
        default="auto",
        help="Shape sweep budgets from the evaluated search-scope estimator.",
    )
    parser.add_argument(
        "--search-scope-json",
        default=str(ROOT_DIR / "config/opentitan_tlul_search_scope_estimate.json"),
    )
    parser.add_argument(
        "--search-scope-graph-json",
        default=str(ROOT_DIR / "config/opentitan_tlul_search_scope_graph.json"),
    )
    parser.add_argument("--launch-backend", choices=("auto", "source", "circt-cubin"), default="auto")
    parser.add_argument("--generated-dir-cache-root", default="/tmp/opentitan_tlul_slice_generated_dir_cache")
    parser.add_argument("--dead-word-bias", action="store_true", default=None)
    parser.add_argument("--uniform-states", action="store_true", default=None)
    parser.add_argument("--rebuild-first", action="store_true")
    parser.add_argument("--compile-cache-dir", default="/tmp/verilator-sim-accel-compile-cache")
    parser.add_argument("--no-compile-cache", action="store_true")
    parser.add_argument("--cases-jsonl-out", default="")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--grpo-policy-json", default="")
    parser.add_argument("--grpo-target-region", default="")
    parser.add_argument("--grpo-proposal-k", type=int, default=0)
    parser.add_argument("--grpo-missing-region", action="append", default=[])
    parser.add_argument(
        "--grpo-selection-mode",
        choices=("exact", "blend", "slice", "missing", "closure"),
        default="exact",
    )
    return parser.parse_args(argv)


def _jsonl_case_record(case_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_index": case_summary["case_index"],
        "profile_index": case_summary.get("profile_index"),
        "profile_family": case_summary.get("profile_family"),
        "profile_slot": case_summary.get("profile_slot"),
        "seed_slot": case_summary.get("seed_slot"),
        "variant_name": case_summary.get("variant_name"),
        "target_region": case_summary.get("target_region"),
        "seed": case_summary["seed"],
        "batch_json": case_summary["batch_json"],
        "real_subset_points_hit": case_summary.get("real_subset_points_hit"),
        "real_subset_points_total": case_summary.get("real_subset_points_total"),
        "real_subset_coverage_per_second": case_summary.get("real_subset_coverage_per_second"),
        "active_region_count": case_summary.get("active_region_count"),
        "dead_region_count": case_summary.get("dead_region_count"),
        "dead_output_word_count": case_summary.get("dead_output_word_count"),
        "accepted_traffic_sum": case_summary.get("accepted_traffic_sum"),
        "execution_status": case_summary.get("execution_status"),
        "truth_gate_status": case_summary.get("truth_gate_status"),
        "coverage_status": case_summary.get("coverage_status"),
        "diagnostic_status": case_summary.get("diagnostic_status"),
        "oracle_status": case_summary.get("oracle_status"),
        "oracle_alive": case_summary.get("oracle_alive"),
        "missing_oracle_outputs": list(case_summary.get("missing_oracle_outputs") or []),
        "summary_path": case_summary.get("summary_path"),
    }


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


def _campaign_merge_case_record(case_summary: dict[str, Any]) -> dict[str, Any]:
    target_region = str(case_summary.get("target_region") or "")
    active_regions = [str(region) for region in list(case_summary.get("active_regions") or [])]
    dead_regions = {str(region) for region in list(case_summary.get("dead_regions") or [])}
    score = score_prefilter_case(case_summary)
    execution_gate = _execution_gate_values(case_summary)
    record = {
        "case_index": int(case_summary["case_index"]),
        "seed_slot": int(case_summary.get("seed_slot") or 0),
        "variant_name": case_summary.get("variant_name"),
        "target_region": target_region,
        "seed": int(case_summary["seed"]),
        "batch_json": case_summary["batch_json"],
        "prefilter_stage": case_summary.get("prefilter_stage", "coarse-packed"),
        "recommended_sequential_steps": case_summary.get("recommended_sequential_steps"),
        "real_subset_points_hit": int(case_summary.get("real_subset_points_hit") or 0),
        "real_subset_points_total": int(case_summary.get("real_subset_points_total") or 0),
        "real_subset_coverage_per_second": float(
            case_summary.get("real_subset_coverage_per_second") or 0.0
        ),
        "active_region_count": int(case_summary.get("active_region_count") or len(active_regions)),
        "dead_region_count": int(case_summary.get("dead_region_count") or 0),
        "dead_output_word_count": int(case_summary.get("dead_output_word_count") or 0),
        "target_region_activated": int(bool(target_region and target_region in set(active_regions))),
        "target_region_still_dead": int(bool(target_region and target_region in dead_regions)),
        "accepted_traffic_sum": execution_gate["accepted_traffic_sum"],
        "execution_status": execution_gate["execution_status"],
        "truth_gate_status": execution_gate["truth_gate_status"],
        "coverage_status": case_summary.get("coverage_status"),
        "diagnostic_status": case_summary.get("diagnostic_status"),
        "progress_cycle_count_o": execution_gate["progress_cycle_count_o"],
        "debug_phase_o": execution_gate["debug_phase_o"],
        "oracle_status": str(case_summary.get("oracle_status") or ""),
        "oracle_alive": int(case_summary.get("oracle_alive") or 0),
        "missing_oracle_outputs": list(case_summary.get("missing_oracle_outputs") or []),
        "prefilter_score": list(score),
    }
    return record


def _summary_case_record(case_summary: dict[str, Any], *, lean: bool) -> dict[str, Any]:
    if lean:
        return _campaign_merge_case_record(case_summary)
    return {
        key: value
        for key, value in case_summary.items()
        if key not in {"driver", "trace_summary"} and not str(key).startswith("_")
    }


def _compact_campaign_case_summary(case_summary: dict[str, Any]) -> dict[str, Any]:
    active_regions = [str(region) for region in list(case_summary.get("active_regions") or [])]
    score = score_prefilter_case(case_summary)
    execution_gate = _execution_gate_values(case_summary)
    compact = {
        "case_index": int(case_summary["case_index"]),
        "profile_index": case_summary.get("profile_index"),
        "profile_family": case_summary.get("profile_family"),
        "profile_slot": case_summary.get("profile_slot"),
        "seed_slot": case_summary.get("seed_slot"),
        "variant_name": case_summary.get("variant_name"),
        "target_region": case_summary.get("target_region"),
        "seed": int(case_summary["seed"]),
        "batch_json": case_summary.get("batch_json"),
        "driver": case_summary.get("driver"),
        "case_dir": case_summary.get("case_dir"),
        "launch_dir": case_summary.get("launch_dir"),
        "summary_path": case_summary.get("summary_path"),
        "real_subset_points_hit": int(case_summary.get("real_subset_points_hit") or 0),
        "real_subset_points_total": int(case_summary.get("real_subset_points_total") or 0),
        "real_subset_coverage_per_second": float(
            case_summary.get("real_subset_coverage_per_second") or 0.0
        ),
        "active_region_count": int(case_summary.get("active_region_count") or len(active_regions)),
        "dead_region_count": int(case_summary.get("dead_region_count") or 0),
        "dead_output_word_count": int(case_summary.get("dead_output_word_count") or 0),
        "active_regions": active_regions,
        "prefilter_stage": case_summary.get("prefilter_stage", "coarse-packed"),
        "recommended_sequential_steps": case_summary.get("recommended_sequential_steps"),
        "target_region_activated": int(case_summary.get("target_region_activated") or 0),
        "target_region_still_dead": int(case_summary.get("target_region_still_dead") or 0),
        "accepted_traffic_sum": execution_gate["accepted_traffic_sum"],
        "execution_status": execution_gate["execution_status"],
        "truth_gate_status": execution_gate["truth_gate_status"],
        "coverage_status": case_summary.get("coverage_status"),
        "diagnostic_status": case_summary.get("diagnostic_status"),
        "progress_cycle_count_o": execution_gate["progress_cycle_count_o"],
        "debug_phase_o": execution_gate["debug_phase_o"],
        "oracle_status": str(case_summary.get("oracle_status") or ""),
        "oracle_alive": int(case_summary.get("oracle_alive") or 0),
        "missing_oracle_outputs": list(case_summary.get("missing_oracle_outputs") or []),
        "prefilter_score": list(score),
    }
    return compact


def _active_region_union(cases: list[dict[str, Any]]) -> list[str]:
    active_regions: set[str] = set()
    for case in cases:
        for region in list(case.get("active_regions") or []):
            active_regions.add(str(region))
    return sorted(active_regions)


def _normalize_init_file_metrics(raw: Any) -> dict[str, Any]:
    payload = dict(raw or {})
    normalized = {
        field: int(payload.get(field) or 0)
        for field in _INIT_FILE_METRIC_INT_FIELDS
    }
    normalized["uniform_states"] = bool(payload.get("uniform_states"))
    total_line_count = int(normalized["total_line_count"])
    naive_line_estimate = int(normalized["naive_full_override_line_estimate"])
    normalized["compression_ratio_vs_naive"] = (
        float(naive_line_estimate) / float(total_line_count)
        if total_line_count > 0
        else 1.0
    )
    normalized["compression_savings_fraction"] = (
        float(normalized["line_reduction_vs_naive"]) / float(naive_line_estimate)
        if naive_line_estimate > 0
        else 0.0
    )
    return normalized


def _build_launch_generation_rollup(launch_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    if not launch_summaries:
        return {
            "launch_count": 0,
            "bundle_cache_hit_count": 0,
            "bundle_cache_hit_rate": 0.0,
            "init_file_metrics": _normalize_init_file_metrics({}),
        }
    init_totals = {field: 0 for field in _INIT_FILE_METRIC_INT_FIELDS}
    bundle_cache_hit_count = 0
    for launch_summary in launch_summaries:
        if bool(launch_summary.get("bundle_cache_hit")):
            bundle_cache_hit_count += 1
        init_metrics = _normalize_init_file_metrics(launch_summary.get("init_file_metrics"))
        for field in _INIT_FILE_METRIC_INT_FIELDS:
            init_totals[field] += int(init_metrics.get(field) or 0)
    normalized_totals = _normalize_init_file_metrics(init_totals)
    return {
        "launch_count": len(launch_summaries),
        "bundle_cache_hit_count": bundle_cache_hit_count,
        "bundle_cache_hit_rate": float(bundle_cache_hit_count) / float(len(launch_summaries)),
        "init_file_metrics": normalized_totals,
    }


def _build_slice_base_driver(
    *,
    slice_name: str,
    case_index: int,
    seed: int,
    batch_length: int,
    profile_family: str,
) -> dict[str, Any]:
    if str(slice_name or "") == "csrng_main_sm":
        driver = dict(DRIVER_DEFAULTS)
        driver.update(
            {
                "seed": int(seed),
                "batch_length": int(batch_length),
                "profile_family": str(profile_family or "mixed"),
                "profile_slot": 0,
                "req_valid_pct": 92,
                "rsp_valid_pct": 96,
                "reset_cycles": 4,
                "drain_cycles": 16,
                "req_fill_target": 8,
                "req_family": 0,
                "req_address_mode": 0,
                "req_data_mode": 0,
                "rsp_error_pct": 4,
                "rsp_fill_target": 1,
                "rsp_delay_max": 2,
                "trace_replay_enable": 0,
            }
        )
        return driver
    if str(slice_name or "") != "edn_main_sm":
        return build_sync_driver(
            case_index,
            seed,
            batch_length,
            profile_family=profile_family,
        )
    driver = dict(DRIVER_DEFAULTS)
    driver.update(
        {
            "seed": int(seed),
            "batch_length": int(batch_length),
            "profile_family": str(profile_family or "mixed"),
            "profile_slot": 0,
            "req_valid_pct": 88,
            "rsp_valid_pct": 96,
            "reset_cycles": 4,
            "drain_cycles": 16,
            "req_fill_target": 6,
            "rsp_error_pct": 6,
            "rsp_family": 0,
            "req_family": 0,
            "req_address_mode": 0,
            "req_data_mode": 0,
            "req_data_hi_xor": 0,
            "access_ack_data_pct": 50,
            "rsp_fill_target": 2,
            "rsp_delay_max": 4,
            "rsp_delay_mode": 0,
            "rsp_data_mode": 0,
            "rsp_data_hi_xor": 0,
            "trace_replay_enable": 0,
        }
    )
    return driver


def _dedupe_cases_by_index(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[int, dict[str, Any]] = {}
    for case in cases:
        case_index = int(case["case_index"])
        current = deduped.get(case_index)
        if current is None or score_prefilter_case(case) > score_prefilter_case(current):
            deduped[case_index] = case
    return list(deduped.values())


def _build_case_candidate(
    *,
    slice_name: str,
    case_index: int,
    variant_name: str,
    variant_index: int,
    seed_slot: int,
    global_case_index: int,
    seed: int,
    batch_length: int,
    profile_family: str,
    template_driver_defaults: dict[str, Any],
    work_dir: Path,
    persist_batch_json: bool,
) -> dict[str, Any]:
    case_dir = work_dir / f"case_{global_case_index:05d}"
    if persist_batch_json:
        case_dir.mkdir(parents=True, exist_ok=True)
    driver = _build_slice_base_driver(
        slice_name=slice_name,
        case_index=case_index,
        seed=seed,
        batch_length=batch_length,
        profile_family=profile_family,
    )
    for key, value in template_driver_defaults.items():
        if key in DRIVER_DEFAULTS and key not in {"seed", "batch_length"}:
            driver[key] = value
    driver = _apply_slice_trace_variant(
        slice_name=slice_name,
        driver=driver,
        variant_name=variant_name,
        variant_index=variant_index,
        seed=seed,
    )
    batch_json = case_dir / "batch.json"
    if persist_batch_json:
        batch_json.write_text(
            json.dumps({"driver": driver}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return {
        "case_index": global_case_index,
        "profile_index": case_index,
        "profile_family": driver.get("profile_family"),
        "profile_slot": driver.get("profile_slot"),
        "seed_slot": int(seed_slot),
        "variant_name": variant_name,
        "target_region": _slice_variant_target_region(slice_name, variant_name),
        "seed": seed,
        "batch_json": str(batch_json),
        "driver": driver,
        "trace_summary": None,
        "case_dir": str(case_dir.resolve()),
    }


def _apply_driver_patch(driver: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    updated = dict(driver)
    for key, value in dict(patch or {}).items():
        updated[key] = value
    return updated


def _load_grpo_candidates(
    *,
    policy_json: str,
    slice_name: str,
    profile_family: str,
    target_region: str,
    missing_regions: list[str],
    proposal_k: int,
    selection_mode: str,
) -> list[dict[str, Any]]:
    raw_path = str(policy_json or "").strip()
    if not raw_path:
        return []
    payload = _load_grpo_json(Path(raw_path).expanduser().resolve())
    contexts = dict(payload.get("contexts") or {})
    missing_region_contexts = dict(payload.get("missing_region_contexts") or {})
    slice_contexts = dict(payload.get("slice_contexts") or {})
    exact_key = "::".join((str(slice_name or "").strip(), str(target_region or "").strip(), str(profile_family or "").strip()))
    missing_key = "::".join(
        (
            str(slice_name or "").strip(),
            ",".join(
                sorted(
                    {
                        str(region or "").strip()
                        for region in list(missing_regions or [])
                        if str(region or "").strip()
                    }
                )
            ),
            str(profile_family or "").strip(),
        )
    )
    slice_key = "::".join((str(slice_name or "").strip(), "*", str(profile_family or "").strip()))
    exact_candidates = list(contexts.get(exact_key) or [])
    missing_candidates = list(missing_region_contexts.get(missing_key) or [])
    slice_candidates = list(slice_contexts.get(slice_key) or [])

    limit = int(proposal_k) if int(proposal_k) > 0 else max(len(exact_candidates), len(slice_candidates))
    if limit <= 0:
        return []
    selected, _selection_meta = select_policy_candidates(
        exact_candidates=exact_candidates,
        missing_candidates=missing_candidates,
        slice_candidates=slice_candidates,
        limit=limit,
        selection_mode=str(selection_mode or "exact"),
    )
    return selected[:limit]


def _build_grpo_case_candidate(
    *,
    slice_name: str,
    proposal: dict[str, Any],
    global_case_index: int,
    seed: int,
    seed_slot: int,
    batch_length: int,
    profile_family: str,
    template_driver_defaults: dict[str, Any],
    work_dir: Path,
    persist_batch_json: bool,
) -> dict[str, Any]:
    action_patch = dict(proposal.get("action_patch") or {})
    variant_name = str(action_patch.get("variant_name") or "base")
    driver = _build_slice_base_driver(
        slice_name=slice_name,
        case_index=0,
        seed=seed,
        batch_length=batch_length,
        profile_family=profile_family,
    )
    for key, value in template_driver_defaults.items():
        if key in DRIVER_DEFAULTS and key not in {"seed", "batch_length"}:
            driver[key] = value
    driver = _apply_driver_patch(driver, dict(action_patch.get("driver_patch") or {}))
    if "batch_length" in dict(action_patch.get("launch_patch") or {}):
        driver["batch_length"] = int(dict(action_patch.get("launch_patch") or {}).get("batch_length") or driver.get("batch_length") or batch_length)
    driver["seed"] = int(seed)
    target_region = str(proposal.get("target_regions", [""])[0] if isinstance(proposal.get("target_regions"), list) and proposal.get("target_regions") else "")
    if not target_region:
        target_region = _slice_variant_target_region(slice_name, variant_name)
    case_dir = work_dir / f"case_{global_case_index:05d}"
    if persist_batch_json:
        case_dir.mkdir(parents=True, exist_ok=True)
    batch_json = case_dir / "batch.json"
    if persist_batch_json:
        batch_json.write_text(
            json.dumps({"driver": driver}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return {
        "case_index": global_case_index,
        "profile_index": 0,
        "profile_family": driver.get("profile_family"),
        "profile_slot": driver.get("profile_slot"),
        "seed_slot": int(seed_slot),
        "variant_name": variant_name,
        "target_region": target_region,
        "seed": seed,
        "batch_json": str(batch_json),
        "driver": driver,
        "trace_summary": None,
        "case_dir": str(case_dir.resolve()),
        "grpo_action_patch": action_patch,
    }


def _ensure_candidate_batch_json(case_summary: dict[str, Any]) -> str:
    batch_json_raw = str(case_summary.get("batch_json") or "").strip()
    case_dir_raw = str(case_summary.get("case_dir") or "").strip()
    if batch_json_raw:
        batch_json_path = Path(batch_json_raw).expanduser().resolve()
    elif case_dir_raw:
        batch_json_path = Path(case_dir_raw).expanduser().resolve() / "batch.json"
    else:
        raise SystemExit("Case summary is missing both batch_json and case_dir")
    if batch_json_path.is_file():
        case_summary["batch_json"] = str(batch_json_path)
        case_summary["case_dir"] = str(batch_json_path.parent.resolve())
        return str(batch_json_path)
    driver = dict(case_summary.get("driver") or {})
    if not driver:
        raise SystemExit(f"Cannot materialize batch_json without driver payload: {batch_json_path}")
    batch_json_path.parent.mkdir(parents=True, exist_ok=True)
    batch_json_path.write_text(
        json.dumps({"driver": driver}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    case_summary["batch_json"] = str(batch_json_path)
    case_summary["case_dir"] = str(batch_json_path.parent.resolve())
    return str(batch_json_path)


def _run_gpu_launch(
    *,
    ns: argparse.Namespace,
    template: dict[str, Any],
    template_path: Path,
    work_dir: Path,
    launch_index: int,
    candidates: list[dict[str, Any]],
    states_per_case: int,
) -> tuple[list[dict[str, Any]], Path, dict[str, Any]]:
    launch_dir = work_dir / f"launch_{launch_index:03d}"
    launch_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = launch_dir / "batch_manifest.json"
    manifest_payload = {
        "target": template.get("target"),
        "cases": [
            {
                "case_index": case["case_index"],
                "profile_index": case["profile_index"],
                "profile_family": case.get("profile_family"),
                "profile_slot": case.get("profile_slot"),
                "seed_slot": case.get("seed_slot"),
                "variant_name": case["variant_name"],
                "target_region": case.get("target_region"),
                "seed": case["seed"],
                "batch_json": case["batch_json"],
                "driver": case.get("driver"),
                "states_per_case": states_per_case,
            }
            for case in candidates
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    gpu_summary_path = launch_dir / "gpu_summary.json"
    launch_sequential_steps = max(
        int(ns.gpu_sequential_steps),
        max(estimate_sync_sequential_steps(case["driver"]) for case in candidates),
    )
    execution_engine = str(ns.execution_engine)
    launch_backend = str(ns.launch_backend)
    sequential_rep_graph_mode = str(ns.sequential_rep_graph_mode or "").strip()
    gpu_reps = int(ns.gpu_reps)
    cpu_reps = 0
    skip_cpu_reference_build = True
    if execution_engine == "cpu":
        launch_backend = "source"
        gpu_reps = 0
        cpu_reps = max(1, int(ns.cpu_reps))
        skip_cpu_reference_build = False
    cmd = [
        "python3",
        str(GPU_RUNNER),
        "--launch-template",
        str(template_path),
        "--phase",
        str(ns.phase),
        "--launch-backend",
        launch_backend,
        "--generated-dir-cache-root",
        str(Path(ns.generated_dir_cache_root).expanduser().resolve()),
        "--build-dir",
        str(launch_dir / "gpu"),
        "--json-out",
        str(gpu_summary_path),
        "--batch-manifest-json",
        str(manifest_path),
        "--nstates",
        str(len(candidates) * states_per_case),
        "--gpu-reps",
        str(gpu_reps),
        "--cpu-reps",
        str(cpu_reps),
        "--sequential-steps",
        str(launch_sequential_steps),
        "--summary-mode",
        "prefilter",
    ]
    if sequential_rep_graph_mode:
        cmd.extend(["--sequential-rep-graph-mode", sequential_rep_graph_mode])
    if skip_cpu_reference_build:
        cmd.append("--skip-cpu-reference-build")
    if bool(ns.uniform_states):
        cmd.append("--uniform-states")
    if ns.no_compile_cache:
        cmd.append("--no-compile-cache")
    else:
        cmd.extend(["--compile-cache-dir", str(Path(ns.compile_cache_dir).expanduser().resolve())])
    if ns.rebuild_first and launch_index == 0:
        cmd.append("--rebuild")
    subprocess.run(cmd, cwd=SCRIPT_DIR, check=True)
    gpu_summary = _load_json(gpu_summary_path)
    packed_cases = gpu_summary.get("packed_cases") or []
    launch_generation_summary = {
        "launch_index": int(launch_index),
        "launch_dir": str(launch_dir.resolve()),
        "summary_json": str(gpu_summary_path),
        "bundle_cache_hit": bool(gpu_summary.get("bundle_cache_hit")),
        "bundle_runtime_mode": str(gpu_summary.get("bundle_runtime_mode") or ""),
        "init_file_metrics": _normalize_init_file_metrics(gpu_summary.get("init_file_metrics")),
    }
    packed_by_index = {
        int(case["case_index"]): case
        for case in packed_cases
        if case.get("case_index") is not None
    }
    launch_case_summaries: list[dict[str, Any]] = []
    for candidate in candidates:
        packed_case = packed_by_index.get(int(candidate["case_index"]))
        if packed_case is None:
            raise SystemExit(
                f"Packed GPU summary missing case_index={candidate['case_index']} in {gpu_summary_path}"
            )
        region_summary = packed_case.get("coverage_regions") or {}
        active_regions = [str(region) for region in list(region_summary.get("active_regions") or [])]
        dead_regions = {str(region) for region in list(region_summary.get("dead_regions") or [])}
        traffic_counters = dict(packed_case.get("traffic_counters") or {})
        execution_gating = dict(packed_case.get("execution_gating") or {})
        trace_progress = dict(packed_case.get("trace_progress") or {})
        oracle = dict(packed_case.get("oracle") or {})
        target_region = str(candidate.get("target_region") or "")
        case_summary = {
            "case_index": candidate["case_index"],
            "profile_index": candidate["profile_index"],
            "profile_family": candidate.get("profile_family"),
            "profile_slot": candidate.get("profile_slot"),
            "seed_slot": candidate.get("seed_slot"),
            "variant_name": candidate["variant_name"],
            "target_region": target_region,
            "seed": candidate["seed"],
            "batch_json": candidate["batch_json"],
            "driver": candidate.get("driver"),
            "case_dir": candidate.get("case_dir"),
            "real_subset_points_hit": packed_case.get("points_hit"),
            "real_subset_points_total": packed_case.get("points_total"),
            "real_subset_coverage_per_second": packed_case.get("coverage_per_second"),
            "active_region_count": region_summary.get("active_region_count"),
            "dead_region_count": region_summary.get("dead_region_count"),
            "active_regions": active_regions,
            "dead_output_word_count": packed_case.get("dead_output_word_count"),
            "launch_dir": str(launch_dir.resolve()),
            "summary_path": str(gpu_summary_path),
            "prefilter_stage": "coarse-packed",
            "recommended_sequential_steps": launch_sequential_steps,
            "target_region_activated": int(
                bool(target_region and target_region in set(active_regions))
            ),
            "target_region_still_dead": int(
                bool(target_region and target_region in dead_regions)
            ),
        }
        for key in TRAFFIC_COUNTER_KEYS:
            case_summary[key] = int(traffic_counters.get(key) or 0)
        for key in (
            "progress_cycle_count_o",
            "debug_phase_o",
            "debug_cycle_count_o",
            "debug_trace_live_o",
            "debug_trace_req_active_o",
            "debug_reset_cycles_remaining_o",
            "debug_req_valid_o",
        ):
            case_summary[key] = int(execution_gating.get(key) or 0)
        for key in TRACE_PROGRESS_KEYS:
            if key not in case_summary:
                case_summary[key] = int(trace_progress.get(key) or 0)
        for key in ORACLE_KEYS:
            case_summary[key] = int(oracle.get(key) or 0)
        if oracle:
            case_summary["oracle_status"] = str(oracle.get("oracle_status") or "")
            case_summary["oracle_alive"] = int(oracle.get("oracle_alive") or 0)
            case_summary["oracle_signal_inconsistent"] = int(oracle.get("oracle_signal_inconsistent") or 0)
            case_summary["missing_oracle_outputs"] = list(oracle.get("missing_oracle_outputs") or [])
        case_summary["coverage_status"] = str(packed_case.get("coverage_status") or "")
        case_summary["diagnostic_status"] = str(packed_case.get("diagnostic_status") or "")
        case_summary.update(_execution_gate_values(case_summary))
        launch_case_summaries.append(
            case_summary
        )
    return launch_case_summaries, launch_dir, launch_generation_summary


def _best_cases_by_target_region(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    best_by_region: dict[str, dict[str, Any]] = {}
    for case in cases:
        region = str(case.get("target_region") or "")
        if not region:
            continue
        current_best = best_by_region.get(region)
        if current_best is None or score_prefilter_case(case) > score_prefilter_case(current_best):
            best_by_region[region] = case
    return best_by_region


def main(argv: list[str]) -> int:
    wall_start = time.perf_counter()
    ns = parse_args(argv)
    template_path = Path(ns.launch_template).expanduser().resolve()
    template = _load_json(template_path)
    template_args = dict(template.get("runner_args_template") or {})
    search_tuning = resolve_slice_search_tuning(str(template.get("slice_name")), template_args)
    benchmark_freeze = load_benchmark_freeze(ns.benchmark_freeze_json)
    benchmark_profile = resolve_slice_profile(
        benchmark_freeze,
        slice_name=str(template.get("slice_name")),
        phase="sweep",
        profile_scenario=str(ns.profile_scenario),
    )
    work_dir = Path(
        ns.work_dir or str(template_args.get("work_dir") or (SCRIPT_DIR / "slice_pilots" / template["slice_name"]))
    ).expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    json_out = Path(ns.json_out).expanduser().resolve() if ns.json_out else work_dir / "summary.json"
    emit_cases_jsonl = bool(ns.cases_jsonl_out) or str(ns.phase) != "campaign"
    cases_jsonl_out = (
        Path(ns.cases_jsonl_out).expanduser().resolve()
        if ns.cases_jsonl_out
        else (work_dir / "cases.jsonl" if emit_cases_jsonl else None)
    )

    ns.cases = _int_with_template(ns.cases, template_args.get("cases"), 1024)
    ns.variants_per_case = _int_with_template(ns.variants_per_case, template_args.get("variants_per_case"), 4)
    ns.seed_fanout = _int_with_template(ns.seed_fanout, template_args.get("seed_fanout"), 1)
    ns.batch_length = _int_with_template(ns.batch_length, template_args.get("batch_length"), DRIVER_DEFAULTS["batch_length"])
    ns.trace_length = _int_with_template(ns.trace_length, template_args.get("trace_length"), 12)
    ns.gpu_sequential_steps = _int_with_template(
        ns.gpu_sequential_steps,
        benchmark_profile.get("sequential_steps", template_args.get("gpu_sequential_steps")),
        56,
    )
    ns.gpu_nstates = _int_with_template(
        ns.gpu_nstates,
        benchmark_profile.get("nstates", template_args.get("gpu_nstates")),
        32,
    )
    ns.gpu_reps = _int_with_template(
        ns.gpu_reps,
        benchmark_profile.get("gpu_reps", template_args.get("gpu_reps")),
        1,
    )
    ns.cpu_reps = _int_with_template(
        ns.cpu_reps,
        benchmark_profile.get("cpu_reps", template_args.get("cpu_reps")),
        1,
    )
    if str(ns.execution_engine) == "cpu":
        ns.gpu_reps = 0
        ns.cpu_reps = max(1, int(ns.cpu_reps))
        ns.launch_backend = "source"
    else:
        ns.cpu_reps = 0
    ns.keep_top_k = _int_with_template(ns.keep_top_k, template_args.get("keep_top_k"), 16)
    ns.uniform_states = _bool_with_template(ns.uniform_states, template_args.get("uniform_states"))
    ns.dead_word_bias = _bool_with_template(ns.dead_word_bias, template_args.get("dead_word_bias"))
    ns.profile_family = str(ns.profile_family or template_args.get("profile_family") or search_tuning.get("profile_family") or "mixed")
    ns.region_budget = _parse_region_budget_arg(ns.region_budget_json) if ns.region_budget_json else _normalize_region_budget(
        template_args.get("region_budget") or search_tuning.get("region_budget")
    )
    if ns.profile_family not in PROFILE_FAMILIES:
        raise SystemExit(f"Unsupported --profile-family value: {ns.profile_family}")

    shard_index = max(0, int(ns.shard_index))
    shard_count = max(1, int(ns.shard_count))
    if shard_index >= shard_count:
        raise SystemExit(f"--shard-index must be < --shard-count ({shard_index} >= {shard_count})")

    keep_top_k = int(ns.keep_top_k)
    states_per_case = max(
        1,
        int(ns.states_per_case)
        if int(ns.states_per_case) > 0
        else int(template_args.get("states_per_case") or search_tuning.get("states_per_case") or 4),
    )
    policy_input_defaults = {
        "pilot_sweep_cases": int(ns.cases),
        "gpu_nstates": int(ns.gpu_nstates),
        "keep_top_k": keep_top_k,
    }
    policy_result = apply_runtime_batch_policy(
        search_defaults=policy_input_defaults,
        execution_engine=str(ns.execution_engine),
        phase="sweep",
        policy_mode=str(ns.gpu_runtime_policy),
        memory_total_mib_override=(int(ns.gpu_memory_total_mib) if int(ns.gpu_memory_total_mib) > 0 else None),
    )
    effective_search_defaults = dict(policy_result["adjusted_search_defaults"])
    scope_policy_result = apply_search_scope_runtime_policy(
        slice_name=str(template.get("slice_name") or ""),
        search_defaults=effective_search_defaults,
        phase="sweep",
        region_budget=dict(ns.region_budget),
        policy_mode=str(ns.search_scope_policy),
        scope_json=str(ns.search_scope_json),
        graph_json=str(ns.search_scope_graph_json),
    )
    effective_search_defaults = dict(scope_policy_result["adjusted_search_defaults"])
    ns.region_budget = dict(scope_policy_result["adjusted_region_budget"])
    ns.cases = int(effective_search_defaults.get("pilot_sweep_cases") or int(ns.cases))
    ns.gpu_nstates = int(effective_search_defaults.get("gpu_nstates") or int(ns.gpu_nstates))
    keep_top_k = int(effective_search_defaults.get("keep_top_k") or keep_top_k)
    ns.keep_top_k = keep_top_k
    cases_per_launch = max(1, int(ns.cases_per_launch) or max(1, int(ns.gpu_nstates) // states_per_case))
    template_driver_defaults = _template_defaults(template_args)
    selected_variants = _slice_trace_variants(
        str(template.get("slice_name") or ""),
        search_tuning,
        int(ns.variants_per_case),
    )
    grpo_candidates = _load_grpo_candidates(
        policy_json=str(ns.grpo_policy_json or ""),
        slice_name=str(template.get("slice_name") or ""),
        profile_family=str(ns.profile_family),
        target_region=str(ns.grpo_target_region or ""),
        missing_regions=[str(region) for region in list(ns.grpo_missing_region or [])],
        proposal_k=int(ns.grpo_proposal_k),
        selection_mode=str(ns.grpo_selection_mode or "exact"),
    )
    seed_fanout = max(1, int(ns.seed_fanout))
    total_cases = max(1, int(ns.cases))
    if grpo_candidates:
        total_candidate_space = total_cases * len(grpo_candidates) * seed_fanout
    else:
        total_candidate_space = total_cases * len(selected_variants) * seed_fanout

    retained_cases: list[dict[str, Any]] = []
    retained_topk_cases: list[dict[str, Any]] = []
    region_case_pool: dict[str, list[dict[str, Any]]] = {}
    retained_case_dirs: set[str] = set()
    retained_launch_dirs: set[str] = set()
    launch_generation_summaries: list[dict[str, Any]] = []
    global_case_index = 0
    evaluated_case_count = 0
    launch_index = 0
    pending_candidates: list[dict[str, Any]] = []
    jsonl_handle = None
    if cases_jsonl_out is not None:
        cases_jsonl_out.parent.mkdir(parents=True, exist_ok=True)
        jsonl_handle = cases_jsonl_out.open("w", encoding="utf-8")

    def flush_pending() -> None:
        nonlocal launch_index, retained_cases, retained_topk_cases, retained_case_dirs
        nonlocal retained_launch_dirs, evaluated_case_count
        if not pending_candidates:
            return
        launch_case_summaries, launch_dir, launch_generation_summary = _run_gpu_launch(
            ns=ns,
            template=template,
            template_path=template_path,
            work_dir=work_dir,
            launch_index=launch_index,
            candidates=list(pending_candidates),
            states_per_case=states_per_case,
        )
        launch_generation_summaries.append(launch_generation_summary)
        if str(ns.phase) == "campaign":
            launch_case_summaries = [
                _compact_campaign_case_summary(case_summary) for case_summary in launch_case_summaries
            ]
        launch_index += 1
        _update_region_case_pool(region_case_pool, launch_case_summaries, ns.region_budget)
        if keep_top_k > 0:
            retained_topk_cases = _update_incremental_topk(
                retained_topk_cases,
                launch_case_summaries,
                keep_top_k,
            )
            retained_cases = _selected_prefilter_cases(
                retained_topk_cases,
                region_case_pool,
            )
        else:
            retained_pool = _dedupe_cases_by_index(
                retained_cases
                + launch_case_summaries
                + [
                    case
                    for region_cases in region_case_pool.values()
                    for case in region_cases
                ]
            )
            retained_cases = rank_prefilter_cases(retained_pool, keep_top_k, ns.region_budget)
        current_retained_case_dirs = {
            str(Path(str(case["batch_json"])).resolve().parent) for case in retained_cases
        }
        current_retained_launch_dirs = {
            str(Path(str(case["launch_dir"])).resolve()) for case in retained_cases if case.get("launch_dir")
        }
        if ns.cleanup_non_topk and keep_top_k > 0:
            dropped_case_dirs = retained_case_dirs - current_retained_case_dirs
            current_case_dirs = {str(Path(candidate["case_dir"]).resolve()) for candidate in pending_candidates}
            for candidate_dir in current_case_dirs:
                if candidate_dir not in current_retained_case_dirs:
                    dropped_case_dirs.add(candidate_dir)
            for dropped_dir in sorted(dropped_case_dirs):
                shutil.rmtree(dropped_dir, ignore_errors=True)
            dropped_launch_dirs = retained_launch_dirs - current_retained_launch_dirs
            launch_dir_resolved = str(launch_dir.resolve())
            if launch_dir_resolved not in current_retained_launch_dirs:
                dropped_launch_dirs.add(launch_dir_resolved)
            for dropped_dir in sorted(dropped_launch_dirs):
                shutil.rmtree(dropped_dir, ignore_errors=True)
        retained_case_dirs = current_retained_case_dirs
        retained_launch_dirs = current_retained_launch_dirs
        for case_summary in launch_case_summaries:
            if jsonl_handle is not None:
                jsonl_handle.write(json.dumps(_jsonl_case_record(case_summary), sort_keys=True) + "\n")
            evaluated_case_count += 1
        pending_candidates.clear()

    for case_index in range(total_cases):
        base_seed = int(ns.seed_start) + case_index
        if grpo_candidates:
            for proposal_index, proposal in enumerate(grpo_candidates):
                for seed_slot in range(seed_fanout):
                    seed = base_seed + (proposal_index * 97) + (seed_slot * 1009)
                    if (global_case_index % shard_count) != shard_index:
                        global_case_index += 1
                        continue
                    pending_candidates.append(
                        _build_grpo_case_candidate(
                            slice_name=str(template.get("slice_name") or ""),
                            proposal=proposal,
                            global_case_index=global_case_index,
                            seed=seed,
                            seed_slot=seed_slot,
                            batch_length=int(ns.batch_length),
                            profile_family=str(ns.profile_family),
                            template_driver_defaults=template_driver_defaults,
                            work_dir=work_dir,
                            persist_batch_json=emit_cases_jsonl,
                        )
                    )
                    if len(pending_candidates) >= cases_per_launch:
                        flush_pending()
                    global_case_index += 1
        else:
            for variant_index, variant_name in enumerate(selected_variants):
                for seed_slot in range(seed_fanout):
                    seed = base_seed + (variant_index * 97) + (seed_slot * 1009)
                    if (global_case_index % shard_count) != shard_index:
                        global_case_index += 1
                        continue
                    pending_candidates.append(
                        _build_case_candidate(
                            slice_name=str(template.get("slice_name") or ""),
                            case_index=case_index,
                            variant_name=variant_name,
                            variant_index=variant_index,
                            seed_slot=seed_slot,
                            global_case_index=global_case_index,
                            seed=seed,
                            batch_length=int(ns.batch_length),
                            profile_family=str(ns.profile_family),
                            template_driver_defaults=template_driver_defaults,
                            work_dir=work_dir,
                            persist_batch_json=emit_cases_jsonl,
                        )
                    )
                    if len(pending_candidates) >= cases_per_launch:
                        flush_pending()
                    global_case_index += 1
    flush_pending()
    if jsonl_handle is not None:
        jsonl_handle.close()

    if keep_top_k > 0:
        ranked = _selected_prefilter_cases(
            retained_topk_cases,
            region_case_pool,
        )
    else:
        ranked = rank_prefilter_cases(
            _dedupe_cases_by_index(
                retained_cases
                + [
                    case
                    for region_cases in region_case_pool.values()
                    for case in region_cases
                ]
            ),
            keep_top_k,
            ns.region_budget,
        )
    for case in ranked:
        _ensure_candidate_batch_json(case)
    if ns.cleanup_non_topk and keep_top_k > 0:
        kept_case_dirs = {str(Path(case["batch_json"]).resolve().parent) for case in ranked}
        for case_dir in work_dir.glob("case_*"):
            if str(case_dir.resolve()) not in kept_case_dirs:
                shutil.rmtree(case_dir, ignore_errors=True)
        kept_launch_dirs = {
            str(Path(str(case["launch_dir"])).resolve()) for case in ranked if case.get("launch_dir")
        }
        for launch_dir in work_dir.glob("launch_*"):
            if str(launch_dir.resolve()) not in kept_launch_dirs:
                shutil.rmtree(launch_dir, ignore_errors=True)

    best_by_target_region_final = _best_cases_by_target_region(ranked)
    lean_summary = str(ns.phase) == "campaign"
    ranked_campaign_view = [_campaign_merge_case_record(case) for case in ranked]
    best_case_campaign_view = ranked_campaign_view[0] if ranked_campaign_view else None
    best_by_target_region_campaign_view = {
        region: _campaign_merge_case_record(case)
        for region, case in sorted(best_by_target_region_final.items())
    }
    if lean_summary:
        ranked_summary_view = ranked_campaign_view
        best_case_summary = best_case_campaign_view
        best_by_target_region_summary = best_by_target_region_campaign_view
    else:
        ranked_summary_view = [_summary_case_record(case, lean=False) for case in ranked]
        best_case_summary = ranked_summary_view[0] if ranked_summary_view else None
        best_by_target_region_summary = {
            region: _summary_case_record(case, lean=False)
            for region, case in sorted(best_by_target_region_final.items())
        }
    campaign_merge_view_path = json_out.with_name(f"{json_out.stem}.campaign_merge_view.json")
    payload = {
        "target": template.get("target"),
        "slice_name": template.get("slice_name"),
        "launch_template": str(template_path),
        "execution_engine": str(ns.execution_engine),
        "benchmark_profile": benchmark_profile or None,
        "evaluated_case_count": evaluated_case_count,
        "total_candidate_space": total_candidate_space,
        "profile_family": str(ns.profile_family),
        "seed_fanout": seed_fanout,
        "region_budget": dict(ns.region_budget),
        "gpu_runtime_policy": policy_result["policy"],
        "search_scope_policy": scope_policy_result["policy"],
        "effective_search_defaults": {
            **effective_search_defaults,
            "states_per_case": states_per_case,
            "cases_per_launch": cases_per_launch,
        },
        "shard_index": shard_index,
        "shard_count": shard_count,
        "states_per_case": states_per_case,
        "cases_per_launch": cases_per_launch,
        "cases_jsonl_path": str(cases_jsonl_out) if cases_jsonl_out is not None else "",
        "campaign_merge_view_json": str(campaign_merge_view_path),
        "cases": ranked_summary_view,
        "best_case": best_case_summary,
        "best_by_target_region": best_by_target_region_summary,
        "execution": {
            "wall_clock_s": time.perf_counter() - wall_start,
            "launch_count": launch_index,
        },
        "launch_generation": _build_launch_generation_rollup(launch_generation_summaries),
        "grpo_policy_json": str(ns.grpo_policy_json or ""),
        "grpo_target_region": str(ns.grpo_target_region or ""),
        "grpo_missing_regions": [str(region) for region in list(ns.grpo_missing_region or []) if str(region).strip()],
        "grpo_proposal_count": len(grpo_candidates),
        "grpo_selection_mode": str(ns.grpo_selection_mode or "exact"),
    }
    if lean_summary:
        payload["ranked_case_indices"] = [int(case["case_index"]) for case in ranked_campaign_view]
    else:
        payload["ranking"] = ranked_campaign_view
    _write_json(json_out, payload, compact=lean_summary)
    campaign_merge_view = {
        "evaluated_case_count": evaluated_case_count,
        "total_candidate_space": total_candidate_space,
        "best_case": best_case_campaign_view,
        "cases": ranked_campaign_view,
        "active_region_union": _active_region_union(ranked),
        "launch_generation": payload.get("launch_generation"),
    }
    _write_json(campaign_merge_view_path, campaign_merge_view, compact=True)
    print(f"summary_json={json_out}")
    best = payload["best_case"]
    if best is not None:
        print(
            "best_case="
            f"{best['case_index']} seed={best['seed']} "
            f"gpu_hit={best['real_subset_points_hit']} "
            f"dead_regions={best['dead_region_count']} "
            f"dead_words={best['dead_output_word_count']} "
            f"gpu_cps={best['real_subset_coverage_per_second']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
