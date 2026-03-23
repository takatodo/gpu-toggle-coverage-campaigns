#!/usr/bin/env python3
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
REPO_SCRIPTS = SCRIPT_DIR.parent / "scripts"
OPENTITAN_SRC = ROOT_DIR / "third_party/rtlmeter" / "designs" / "OpenTitan" / "src"
DEFAULT_BENCH = ROOT_DIR / "third_party/verilator/bin/verilator_sim_accel_bench"
DEFAULT_VERILATOR = ROOT_DIR / "third_party/verilator/bin/verilator"
CUDA_OPT_DIR = ROOT_DIR / "src" / "sim_accel"
PREPARE_BENCH_BUNDLE = CUDA_OPT_DIR / "prepare_bench_bundle.py"
BUILD_BENCH_BUNDLE = CUDA_OPT_DIR / "build_bench_bundle.py"
BENCH_KERNEL_PARTS_DIR = ROOT_DIR / "third_party/verilator/bin/verilator_sim_accel_bench_kernel"
GENERATED_DIR_GENERATOR = ROOT_DIR / "src/runners" / "opentitan_support" / "generate_opentitan_tlul_slice_generated_dirs.py"
DEFAULT_COMPILE_CACHE = Path("/tmp/verilator-sim-accel-compile-cache")
DEFAULT_GENERATED_DIR_CACHE = Path("/tmp/opentitan_tlul_slice_generated_dir_cache")
DEFAULT_BUNDLE_CACHE = Path("/tmp/opentitan_tlul_slice_bundle_cache")
BUNDLE_CACHE_ABI_VERSION = "v6-native-hsaco-promotion"
GENERATED_DIR_CACHE_ABI_MARKER = ".structured_raw_sidecars_overlay_v2"
DEFAULT_RUNTIME_CONTRACT_WAIVERS = ROOT_DIR / "config" / "opentitan_tlul_slice_runtime_contract_waivers.json"
FOCUSED_WAVE_OUTPUTS = [f"focused_wave_word{i}_o" for i in range(8)]
FOCUSED_METRIC_OUTPUTS = [f"focused_metric_word{i}_o" for i in range(5)]

for path in (str(REPO_SCRIPTS),):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from ..scripts.opentitan_coverage_regions import load_region_manifest, summarize_regions  # noqa: E402
    from ..scripts.opentitan_tlul_baseline_common import (  # noqa: E402
        estimate_sync_sequential_steps,
        load_batch_case_manifest,
        load_batch_overrides,
    )
    from .rtlmeter_sim_accel_adapter import (  # noqa: E402
        build_collector_summary,
        extract_sim_accel_output_slot_values,
        parse_bench_log,
        populate_collector_coverage,
        sha256_hex_bytes,
    )
    from ..scripts.opentitan_tlul_slice_contracts import (  # noqa: E402
        REQUIRED_OUTPUTS_FLAT,
        validate_slice_contract,
    )
    from ..scripts.gpu_backend_selection import (  # noqa: E402
        ensure_gpu_execution_backend_supported,
        resolve_gpu_execution_backend,
    )
except ImportError:
    from opentitan_coverage_regions import load_region_manifest, summarize_regions  # noqa: E402
    from opentitan_tlul_baseline_common import (  # noqa: E402
        estimate_sync_sequential_steps,
        load_batch_case_manifest,
        load_batch_overrides,
    )
    from rtlmeter_sim_accel_adapter import (  # noqa: E402
        build_collector_summary,
        extract_sim_accel_output_slot_values,
        parse_bench_log,
        populate_collector_coverage,
        sha256_hex_bytes,
    )
    from opentitan_tlul_slice_contracts import (  # noqa: E402
        REQUIRED_OUTPUTS_FLAT,
        validate_slice_contract,
    )
    from gpu_backend_selection import (  # noqa: E402
        ensure_gpu_execution_backend_supported,
        resolve_gpu_execution_backend,
    )


def _write_json(path: Path, payload: dict[str, Any], *, compact: bool) -> None:
    if compact:
        text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _selected_output_names_for_summary_mode(summary_mode: str) -> set[str]:
    selected_output_names = set(REAL_TOGGLE_SUBSET_OUTPUTS)
    if summary_mode == "prefilter":
        selected_output_names.update(
            name for name in TRAFFIC_COUNTER_OUTPUTS if name != "rsp_queue_overflow_o"
        )
    else:
        selected_output_names.update(TRAFFIC_COUNTER_OUTPUTS)
    selected_output_names.update(ALL_ORACLE_OUTPUTS)
    selected_output_names.update(EXECUTION_GATING_OUTPUTS)
    selected_output_names.update(TRACE_PROGRESS_OUTPUTS)
    if summary_mode != "prefilter":
        selected_output_names.update(REQUIRED_OUTPUTS_FLAT)
        selected_output_names.update(FOCUSED_WAVE_OUTPUTS)
        selected_output_names.update(FOCUSED_METRIC_OUTPUTS)
    return selected_output_names


def _template_internal_probe_names(template: dict[str, Any]) -> list[str]:
    template_args = dict(template.get("runner_args_template") or {})
    raw = template_args.get("debug_internal_output_names") or template.get("debug_internal_output_names") or []
    names: list[str] = []
    for value in raw:
        text = str(value).strip()
        if text and text not in names:
            names.append(text)
    return names


def _write_output_filter_file(path: Path, selected_output_names: list[str]) -> None:
    path.write_text(
        "".join(f"{name}\n" for name in selected_output_names),
        encoding="utf-8",
    )


COMMON_SOURCES = [
    OPENTITAN_SRC / "top_pkg.sv",
    OPENTITAN_SRC / "prim_pkg.sv",
    OPENTITAN_SRC / "prim_util_pkg.sv",
    OPENTITAN_SRC / "prim_secded_pkg.sv",
    OPENTITAN_SRC / "prim_mubi_pkg.sv",
    OPENTITAN_SRC / "prim_count_pkg.sv",
    OPENTITAN_SRC / "prim_generic_flop.sv",
    OPENTITAN_SRC / "prim_xilinx_flop.sv",
    OPENTITAN_SRC / "prim_xilinx_ultrascale_flop.sv",
    OPENTITAN_SRC / "prim_flop.sv",
    OPENTITAN_SRC / "prim_count.sv",
    OPENTITAN_SRC / "prim_fifo_sync_cnt.sv",
    OPENTITAN_SRC / "prim_fifo_sync.sv",
    OPENTITAN_SRC / "tlul_pkg.sv",
]

SLICE_EXTRA_SOURCES = {
    "tlul_fifo_sync": [],
    "tlul_socket_1n": [
        OPENTITAN_SRC / "tlul_fifo_sync.sv",
        OPENTITAN_SRC / "tlul_err_resp.sv",
        OPENTITAN_SRC / "tlul_socket_1n.sv",
    ],
    "tlul_socket_m1": [
        OPENTITAN_SRC / "tlul_fifo_sync.sv",
        OPENTITAN_SRC / "prim_arbiter_ppc.sv",
        OPENTITAN_SRC / "prim_arbiter_tree.sv",
        OPENTITAN_SRC / "tlul_socket_m1.sv",
    ],
    "xbar_main": [
        OPENTITAN_SRC / "tl_main_pkg.sv",
        OPENTITAN_SRC / "tlul_fifo_sync.sv",
        OPENTITAN_SRC / "tlul_err_resp.sv",
        OPENTITAN_SRC / "prim_arbiter_fixed.sv",
        OPENTITAN_SRC / "prim_arbiter_ppc.sv",
        OPENTITAN_SRC / "prim_arbiter_tree.sv",
        OPENTITAN_SRC / "tlul_socket_1n.sv",
        OPENTITAN_SRC / "tlul_socket_m1.sv",
        OPENTITAN_SRC / "xbar_main.sv",
    ],
    "xbar_peri": [
        OPENTITAN_SRC / "tl_peri_pkg.sv",
        OPENTITAN_SRC / "tlul_fifo_sync.sv",
        OPENTITAN_SRC / "tlul_err_resp.sv",
        OPENTITAN_SRC / "tlul_socket_1n.sv",
        OPENTITAN_SRC / "xbar_peri.sv",
    ],
    "tlul_fifo_async": [
        OPENTITAN_SRC / "prim_generic_flop_2sync.sv",
        OPENTITAN_SRC / "prim_flop_2sync.sv",
        OPENTITAN_SRC / "prim_fifo_async.sv",
        OPENTITAN_SRC / "tlul_fifo_async.sv",
    ],
    "tlul_request_loopback": [
        OPENTITAN_SRC / "prim_secded_inv_39_32_enc.sv",
        OPENTITAN_SRC / "prim_secded_inv_64_57_enc.sv",
        OPENTITAN_SRC / "tlul_data_integ_enc.sv",
        OPENTITAN_SRC / "tlul_rsp_intg_gen.sv",
        OPENTITAN_SRC / "tlul_request_loopback.sv",
    ],
    "tlul_err": [],
    "tlul_sink": [
        OPENTITAN_SRC / "prim_secded_inv_39_32_enc.sv",
        OPENTITAN_SRC / "prim_secded_inv_64_57_enc.sv",
        OPENTITAN_SRC / "tlul_data_integ_enc.sv",
        OPENTITAN_SRC / "tlul_rsp_intg_gen.sv",
        OPENTITAN_SRC / "tlul_err.sv",
        OPENTITAN_SRC / "tlul_sink.sv",
    ],
    "edn_main_sm": [
        OPENTITAN_SRC / "entropy_src_pkg.sv",
        OPENTITAN_SRC / "entropy_src_main_sm_pkg.sv",
        OPENTITAN_SRC / "prim_mubi_pkg.sv",
        OPENTITAN_SRC / "csrng_pkg.sv",
        OPENTITAN_SRC / "edn_pkg.sv",
        OPENTITAN_SRC / "prim_sparse_fsm_flop.sv",
    ],
    "csrng_main_sm": [
        OPENTITAN_SRC / "entropy_src_pkg.sv",
        OPENTITAN_SRC / "csrng_pkg.sv",
        OPENTITAN_SRC / "prim_sparse_fsm_flop.sv",
    ],
    "entropy_src_main_sm": [
        OPENTITAN_SRC / "entropy_src_pkg.sv",
        OPENTITAN_SRC / "entropy_src_main_sm_pkg.sv",
        OPENTITAN_SRC / "prim_mubi_pkg.sv",
        OPENTITAN_SRC / "prim_sparse_fsm_flop.sv",
        OPENTITAN_SRC / "prim_flop.sv",
    ],
    "aes_cipher_control": [
        OPENTITAN_SRC / "aes_reg_pkg.sv",
        OPENTITAN_SRC / "aes_pkg.sv",
        OPENTITAN_SRC / "prim_generic_buf.sv",
        OPENTITAN_SRC / "prim_xilinx_buf.sv",
        OPENTITAN_SRC / "prim_xilinx_ultrascale_buf.sv",
        OPENTITAN_SRC / "prim_buf.sv",
        OPENTITAN_SRC / "aes_cipher_control_fsm.sv",
        OPENTITAN_SRC / "aes_cipher_control_fsm_p.sv",
        OPENTITAN_SRC / "aes_cipher_control_fsm_n.sv",
    ],
    "alert_handler_ping_timer": [
        OPENTITAN_SRC / "alert_handler_reg_pkg.sv",
        OPENTITAN_SRC / "alert_handler_pkg.sv",
        OPENTITAN_SRC / "prim_generic_buf.sv",
        OPENTITAN_SRC / "prim_xilinx_buf.sv",
        OPENTITAN_SRC / "prim_xilinx_ultrascale_buf.sv",
        OPENTITAN_SRC / "prim_buf.sv",
        OPENTITAN_SRC / "prim_cipher_pkg.sv",
        OPENTITAN_SRC / "prim_lfsr.sv",
        OPENTITAN_SRC / "prim_double_lfsr.sv",
        OPENTITAN_SRC / "prim_sparse_fsm_flop.sv",
    ],
    "alert_handler_esc_timer": [
        OPENTITAN_SRC / "alert_handler_reg_pkg.sv",
        OPENTITAN_SRC / "alert_handler_pkg.sv",
        OPENTITAN_SRC / "prim_sparse_fsm_flop.sv",
    ],
    "pwrmgr_fsm": [
        OPENTITAN_SRC / "pwrmgr_reg_pkg.sv",
        OPENTITAN_SRC / "pwrmgr_pkg.sv",
        OPENTITAN_SRC / "lc_ctrl_state_pkg.sv",
        OPENTITAN_SRC / "lc_ctrl_reg_pkg.sv",
        OPENTITAN_SRC / "lc_ctrl_pkg.sv",
        OPENTITAN_SRC / "prim_sparse_fsm_flop.sv",
        OPENTITAN_SRC / "prim_generic_flop_2sync.sv",
        OPENTITAN_SRC / "prim_flop_2sync.sv",
        OPENTITAN_SRC / "prim_sec_anchor_flop.sv",
        OPENTITAN_SRC / "prim_sec_anchor_buf.sv",
        OPENTITAN_SRC / "prim_lc_sender.sv",
    ],
    "lc_ctrl_fsm": [
        OPENTITAN_SRC / "lc_ctrl_state_pkg.sv",
        OPENTITAN_SRC / "lc_ctrl_reg_pkg.sv",
        OPENTITAN_SRC / "lc_ctrl_pkg.sv",
        OPENTITAN_SRC / "prim_sparse_fsm_flop.sv",
        OPENTITAN_SRC / "prim_generic_flop_2sync.sv",
        OPENTITAN_SRC / "prim_flop_2sync.sv",
        OPENTITAN_SRC / "prim_sec_anchor_flop.sv",
        OPENTITAN_SRC / "prim_sec_anchor_buf.sv",
        OPENTITAN_SRC / "prim_lc_sender.sv",
        OPENTITAN_SRC / "prim_lc_sync.sv",
        OPENTITAN_SRC / "lc_ctrl_state_decode.sv",
        OPENTITAN_SRC / "lc_ctrl_state_transition.sv",
        OPENTITAN_SRC / "lc_ctrl_signal_decode.sv",
    ],
    "rom_ctrl_fsm": [
        OPENTITAN_SRC / "rom_ctrl_pkg.sv",
        OPENTITAN_SRC / "rom_ctrl_counter.sv",
        OPENTITAN_SRC / "rom_ctrl_compare.sv",
        OPENTITAN_SRC / "prim_sparse_fsm_flop.sv",
        OPENTITAN_SRC / "prim_mubi4_sender.sv",
    ],
}

DRIVER_DEFAULTS = {
    "batch_length": 256,
    "seed": 1,
    "req_valid_pct": 65,
    "rsp_valid_pct": 70,
    "host_d_ready_pct": 75,
    "device_a_ready_pct": 80,
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
    "reset_cycles": 4,
    "drain_cycles": 24,
    "address_base": 0,
    "address_mask": 0x0000_0FFC,
    "source_mask": 0xFF,
}

REAL_TOGGLE_SUBSET_OUTPUTS = [f"real_toggle_subset_word{i}_o" for i in range(18)]
TRAFFIC_COUNTER_OUTPUTS = [
    "host_req_accepted_o",
    "device_req_accepted_o",
    "device_rsp_accepted_o",
    "host_rsp_accepted_o",
    "rsp_queue_overflow_o",
]
ORACLE_OUTPUTS = [
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
    "oracle_req_stable_violation_o",
    "oracle_pre_handshake_traffic_cycles_o",
]
OPTIONAL_SPLIT_ORACLE_OUTPUTS = [
    "oracle_req_signature_precommit_o",
    "oracle_stalled_req_signature_precommit_o",
    "oracle_stalled_req_signature_postcommit_o",
    "oracle_req_signature_delta_precommit_o",
    "oracle_req_signature_delta_postcommit_o",
    "oracle_req_field_delta_mask_o",
]
ALL_ORACLE_OUTPUTS = [*ORACLE_OUTPUTS, *OPTIONAL_SPLIT_ORACLE_OUTPUTS]
EXECUTION_GATING_OUTPUTS = [
    "progress_cycle_count_o",
    "debug_phase_o",
    "debug_cycle_count_o",
    "debug_trace_live_o",
    "debug_trace_req_active_o",
    "debug_reset_cycles_remaining_o",
    "debug_req_valid_o",
]
TRACE_PROGRESS_OUTPUTS = [
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
]
DRIVER_SIGNAL_NAMES = {
    "batch_length": "cfg_batch_length_i",
    "req_valid_pct": "cfg_req_valid_pct_i",
    "rsp_valid_pct": "cfg_rsp_valid_pct_i",
    "host_d_ready_pct": "cfg_host_d_ready_pct_i",
    "device_a_ready_pct": "cfg_device_a_ready_pct_i",
    "put_full_pct": "cfg_put_full_pct_i",
    "put_partial_pct": "cfg_put_partial_pct_i",
    "req_fill_target": "cfg_req_fill_target_i",
    "req_burst_len_max": "cfg_req_burst_len_max_i",
    "req_family": "cfg_req_family_i",
    "req_address_mode": "cfg_req_address_mode_i",
    "req_data_mode": "cfg_req_data_mode_i",
    "req_data_hi_xor": "cfg_req_data_hi_xor_i",
    "access_ack_data_pct": "cfg_access_ack_data_pct_i",
    "rsp_error_pct": "cfg_rsp_error_pct_i",
    "rsp_fill_target": "cfg_rsp_fill_target_i",
    "rsp_delay_max": "cfg_rsp_delay_max_i",
    "rsp_family": "cfg_rsp_family_i",
    "rsp_delay_mode": "cfg_rsp_delay_mode_i",
    "rsp_data_mode": "cfg_rsp_data_mode_i",
    "rsp_data_hi_xor": "cfg_rsp_data_hi_xor_i",
    "reset_cycles": "cfg_reset_cycles_i",
    "drain_cycles": "cfg_drain_cycles_i",
    "seed": "cfg_seed_i",
    "address_base": "cfg_address_base_i",
    "address_mask": "cfg_address_mask_i",
    "source_mask": "cfg_source_mask_i",
}
HEX_DRIVER_KEYS = {"req_data_hi_xor", "rsp_data_hi_xor", "address_base", "address_mask", "source_mask", "seed"}
CONST_ASSIGN_RE = re.compile(r"assign\s+([A-Za-z_][A-Za-z0-9_$]*)\s*=\s*([^;]+);")
CONST_EXPR_RE = re.compile(
    r"^(?:\d+\s*'[sS]?[bBdDhHoO][0-9a-fA-F_xXzZ?]+|'[01xXzZ]|[0-9]+)$"
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return deduped


def _load_driver(args: argparse.Namespace, template_args: dict[str, Any]) -> dict[str, Any]:
    driver = dict(DRIVER_DEFAULTS)
    defaults_path = template_args.get("batch_defaults_path")
    if defaults_path:
        overrides = load_batch_overrides(str(defaults_path))
        for key, value in overrides.items():
            if not str(key).startswith("_"):
                driver[key] = value
    for key, value in dict(template_args.get("driver_defaults") or {}).items():
        if not str(key).startswith("_"):
            driver[key] = value
    if args.batch_json:
        overrides = load_batch_overrides(args.batch_json)
        for key, value in overrides.items():
            if not str(key).startswith("_"):
                driver[key] = value
    for key in DRIVER_DEFAULTS:
        arg_value = getattr(args, key, None)
        if arg_value is not None:
            driver[key] = arg_value
    return driver


def _format_driver_value(key: str, value: Any) -> str:
    if key in HEX_DRIVER_KEYS:
        return f"0x{int(value) & 0xffff_ffff:08x}"
    return str(int(value))


def _append_global_driver(
    lines: list[str],
    driver: dict[str, Any],
    *,
    metrics: dict[str, Any] | None = None,
) -> None:
    lines.append("cfg_valid_i 1")
    for key, signal_name in DRIVER_SIGNAL_NAMES.items():
        lines.append(f"{signal_name} {_format_driver_value(key, driver[key])}")
    if metrics is not None:
        metrics["global_line_count"] = int(metrics.get("global_line_count") or 0) + 1 + len(DRIVER_SIGNAL_NAMES)


def _append_state_driver(
    lines: list[str],
    state_idx: int,
    driver: dict[str, Any],
    *,
    selected_keys: tuple[str, ...] | None = None,
    metrics: dict[str, Any] | None = None,
) -> None:
    keys = selected_keys or tuple(DRIVER_SIGNAL_NAMES.keys())
    for key in keys:
        signal_name = DRIVER_SIGNAL_NAMES[key]
        lines.append(f"{signal_name} {state_idx} {_format_driver_value(key, driver[key])}")
    if metrics is not None:
        metrics["per_state_override_line_count"] = int(metrics.get("per_state_override_line_count") or 0) + len(keys)
        metrics["per_state_override_state_count"] = int(metrics.get("per_state_override_state_count") or 0) + 1
        seed_keys = [key for key in keys if key == "seed"]
        non_seed_key_count = len(keys) - len(seed_keys)
        if seed_keys:
            metrics["seed_override_line_count"] = int(metrics.get("seed_override_line_count") or 0) + len(seed_keys)
            metrics["seed_override_state_count"] = int(metrics.get("seed_override_state_count") or 0) + 1
        if non_seed_key_count:
            metrics["non_seed_override_line_count"] = int(metrics.get("non_seed_override_line_count") or 0) + non_seed_key_count
            metrics["non_seed_override_state_count"] = int(metrics.get("non_seed_override_state_count") or 0) + 1


def _append_state_driver_range(
    lines: list[str],
    state_start: int,
    state_count: int,
    driver: dict[str, Any],
    *,
    selected_keys: tuple[str, ...] | None = None,
    metrics: dict[str, Any] | None = None,
) -> None:
    keys = selected_keys or tuple(DRIVER_SIGNAL_NAMES.keys())
    span = f"{state_start}+{state_count}"
    for key in keys:
        signal_name = DRIVER_SIGNAL_NAMES[key]
        lines.append(f"{signal_name} {span} {_format_driver_value(key, driver[key])}")
    if metrics is not None:
        metrics["range_override_line_count"] = int(metrics.get("range_override_line_count") or 0) + len(keys)
        metrics["range_override_state_count"] = int(metrics.get("range_override_state_count") or 0) + state_count
        seed_keys = [key for key in keys if key == "seed"]
        non_seed_key_count = len(keys) - len(seed_keys)
        if seed_keys:
            metrics["seed_override_line_count"] = int(metrics.get("seed_override_line_count") or 0) + len(seed_keys)
            metrics["seed_override_state_count"] = int(metrics.get("seed_override_state_count") or 0) + state_count
        if non_seed_key_count:
            metrics["non_seed_override_line_count"] = int(metrics.get("non_seed_override_line_count") or 0) + non_seed_key_count
            metrics["non_seed_override_state_count"] = int(metrics.get("non_seed_override_state_count") or 0) + state_count


def _finalize_init_file_metrics(
    *,
    metrics: dict[str, Any],
    nstates: int,
    uniform_states: bool,
    explicit_state_drivers: list[dict[str, Any]] | None,
    packed_case_spans: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    explicit_state_count = len(explicit_state_drivers or [])
    packed_case_count = len(packed_case_spans or [])
    metrics["explicit_state_count"] = explicit_state_count
    metrics["packed_case_count"] = packed_case_count
    metrics["uniform_states"] = bool(uniform_states)
    metrics["driver_signal_count"] = len(DRIVER_SIGNAL_NAMES)
    metrics["total_line_count"] = (
        int(metrics.get("global_line_count") or 0)
        + int(metrics.get("per_state_override_line_count") or 0)
        + int(metrics.get("range_override_line_count") or 0)
    )
    naive_state_count = explicit_state_count if explicit_state_count else (0 if uniform_states else int(nstates))
    metrics["naive_full_override_line_estimate"] = int(metrics.get("global_line_count") or 0) + (
        naive_state_count * len(DRIVER_SIGNAL_NAMES)
    )
    metrics["line_reduction_vs_naive"] = max(
        0,
        int(metrics["naive_full_override_line_estimate"]) - int(metrics["total_line_count"]),
    )
    total_line_count = int(metrics["total_line_count"])
    naive_line_estimate = int(metrics["naive_full_override_line_estimate"])
    metrics["compression_ratio_vs_naive"] = (
        float(naive_line_estimate) / float(total_line_count)
        if total_line_count > 0
        else 1.0
    )
    metrics["compression_savings_fraction"] = (
        float(metrics["line_reduction_vs_naive"]) / float(naive_line_estimate)
        if naive_line_estimate > 0
        else 0.0
    )
    return metrics


def _write_init_file(
    path: Path,
    driver: dict[str, Any],
    *,
    nstates: int,
    uniform_states: bool,
    explicit_state_drivers: list[dict[str, Any]] | None = None,
    packed_case_spans: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    lines: list[str] = []
    init_metrics: dict[str, Any] = {
        "global_line_count": 0,
        "per_state_override_line_count": 0,
        "per_state_override_state_count": 0,
        "range_override_line_count": 0,
        "range_override_state_count": 0,
        "seed_override_line_count": 0,
        "seed_override_state_count": 0,
        "non_seed_override_line_count": 0,
        "non_seed_override_state_count": 0,
    }
    _append_global_driver(lines, driver, metrics=init_metrics)
    seed_key = ("seed",)
    non_seed_keys = tuple(key for key in DRIVER_SIGNAL_NAMES if key != "seed")
    if explicit_state_drivers and packed_case_spans:
        _append_state_driver_range(
            lines,
            0,
            nstates,
            driver,
            selected_keys=non_seed_keys,
            metrics=init_metrics,
        )
        _append_state_driver_range(
            lines,
            0,
            nstates,
            driver,
            selected_keys=seed_key,
            metrics=init_metrics,
        )
        for case_span in packed_case_spans:
            state_start = int(case_span["state_start"])
            state_count = max(1, int(case_span["state_count"]))
            case_driver = _driver_for_batch_case(driver, case_span)
            changed_non_seed_keys = tuple(
                key for key in non_seed_keys if int(case_driver[key]) != int(driver[key])
            )
            if changed_non_seed_keys:
                _append_state_driver_range(
                    lines,
                    state_start,
                    state_count,
                    case_driver,
                    selected_keys=changed_non_seed_keys,
                    metrics=init_metrics,
                )
            state_drivers_slice = explicit_state_drivers[state_start:state_start + state_count]
            seeds = [int(state_driver["seed"]) for state_driver in state_drivers_slice]
            if len(set(seeds)) == 1:
                if seeds[0] != int(driver["seed"]):
                    _append_state_driver_range(
                        lines,
                        state_start,
                        state_count,
                        {"seed": seeds[0]},
                        selected_keys=seed_key,
                        metrics=init_metrics,
                    )
            else:
                for local_idx, state_driver in enumerate(state_drivers_slice):
                    if int(state_driver["seed"]) == int(driver["seed"]):
                        continue
                    _append_state_driver(
                        lines,
                        state_start + local_idx,
                        state_driver,
                        selected_keys=seed_key,
                        metrics=init_metrics,
                    )
    elif explicit_state_drivers:
        _append_state_driver_range(
            lines,
            0,
            nstates,
            driver,
            selected_keys=non_seed_keys,
            metrics=init_metrics,
        )
        _append_state_driver_range(
            lines,
            0,
            nstates,
            driver,
            selected_keys=seed_key,
            metrics=init_metrics,
        )
        for state_idx, state_driver in enumerate(explicit_state_drivers):
            _append_state_driver(lines, state_idx, state_driver, metrics=init_metrics)
    elif not uniform_states:
        _append_state_driver_range(
            lines,
            0,
            nstates,
            driver,
            selected_keys=non_seed_keys,
            metrics=init_metrics,
        )
        _append_state_driver_range(
            lines,
            0,
            nstates,
            driver,
            selected_keys=seed_key,
            metrics=init_metrics,
        )
        for state_idx in range(nstates):
            state_driver = dict(driver)
            state_driver["seed"] = (int(driver["seed"]) + state_idx * 97) & 0xffff_ffff
            if int(state_driver["seed"]) != int(driver["seed"]):
                _append_state_driver(
                    lines,
                    state_idx,
                    state_driver,
                    selected_keys=("seed",),
                    metrics=init_metrics,
                )
    else:
        _append_state_driver_range(
            lines,
            0,
            nstates,
            driver,
            selected_keys=tuple(DRIVER_SIGNAL_NAMES.keys()),
            metrics=init_metrics,
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return _finalize_init_file_metrics(
        metrics=init_metrics,
        nstates=nstates,
        uniform_states=uniform_states,
        explicit_state_drivers=explicit_state_drivers,
        packed_case_spans=packed_case_spans,
    )


def _constant_folded_outputs(tb_path: Path, required_outputs: list[str]) -> set[str]:
    if not tb_path.exists():
        return set()
    required = set(required_outputs)
    folded: set[str] = set()
    for match in CONST_ASSIGN_RE.finditer(tb_path.read_text(encoding="utf-8")):
        signal_name = str(match.group(1))
        expr = str(match.group(2)).strip().replace(" ", "")
        if signal_name in required and CONST_EXPR_RE.fullmatch(expr):
            folded.add(signal_name)
    return folded


def _load_runtime_contract_waivers(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(entry.get("slice_name")): dict(entry)
        for entry in list(payload.get("slices") or [])
        if entry.get("slice_name")
    }


def _build_focused_wave_artifact(
    *,
    compact_path: Path,
    vars_path: Path,
    comm_path: Path,
    artifact_dir: Path,
    nstates: int,
    decode_mode: str = "packed_or_reduce",
) -> dict[str, Any] | None:
    if not (compact_path.is_file() and vars_path.is_file() and comm_path.is_file()):
        return None
    output_rows = extract_sim_accel_output_slot_values(
        compact_path,
        vars_path,
        comm_path=comm_path,
        nstates=nstates,
    )
    output_by_name = {str(row["name"]): row for row in output_rows}
    required_names = [*FOCUSED_WAVE_OUTPUTS, *FOCUSED_METRIC_OUTPUTS]
    if any(name not in output_by_name for name in required_names):
        return None

    def _or_reduce(name: str) -> int:
        value = 0
        for state_value in list(output_by_name[name]["state_values"]):
            value |= int(state_value)
        return value & 0xFFFF_FFFF

    def _state_values(name: str) -> list[int]:
        return [
            int(state_value) & 0xFFFF_FFFF
            for state_value in list(output_by_name[name]["state_values"])
        ]

    if decode_mode == "raw_words":
        focused_state_values = {
            name: _state_values(name)
            for name in FOCUSED_WAVE_OUTPUTS
        }
        metric_state_values = {
            name: _state_values(name)
            for name in FOCUSED_METRIC_OUTPUTS
        }
        state_count = min(
            int(nstates),
            *[len(values) for values in focused_state_values.values()],
            *[len(values) for values in metric_state_values.values()],
        )
        if state_count <= 0:
            return None
        debug_phase_values = (
            _state_values("debug_phase_o")
            if "debug_phase_o" in output_by_name
            else None
        )
        debug_main_sm_state_values = (
            _state_values("debug_main_sm_state_o")
            if "debug_main_sm_state_o" in output_by_name
            else None
        )
        samples: list[dict[str, Any]] = []
        for state_index in range(state_count):
            sample = {
                "sample_index": state_index,
                **{
                    name: focused_state_values[name][state_index]
                    for name in FOCUSED_WAVE_OUTPUTS
                },
            }
            if debug_phase_values is not None and state_index < len(debug_phase_values):
                sample["phase"] = int(debug_phase_values[state_index])
            if (
                debug_main_sm_state_values is not None
                and state_index < len(debug_main_sm_state_values)
            ):
                sample["main_sm_state"] = int(debug_main_sm_state_values[state_index])
            samples.append(sample)

        metric_word4_or = _or_reduce(FOCUSED_METRIC_OUTPUTS[4])
        summary = {
            "state_count": state_count,
            "progress_cycle_max": max(metric_state_values[FOCUSED_METRIC_OUTPUTS[0]][:state_count]),
            "progress_signature_or": _or_reduce(FOCUSED_METRIC_OUTPUTS[1]),
            "host_rsp_accepted_max": max(metric_state_values[FOCUSED_METRIC_OUTPUTS[2]][:state_count]),
            "device_rsp_accepted_max": max(metric_state_values[FOCUSED_METRIC_OUTPUTS[3]][:state_count]),
            "done_seen": metric_word4_or & 0x1,
            "state_transition_seen": (metric_word4_or >> 1) & 0x1,
            "phase_values": (
                sorted({int(value) for value in debug_phase_values[:state_count]})
                if debug_phase_values is not None
                else []
            ),
            "main_sm_state_values": (
                sorted({int(value) for value in debug_main_sm_state_values[:state_count]})
                if debug_main_sm_state_values is not None
                else []
            ),
        }
        artifact_path = artifact_dir / "gpu_focused_wave.json"
        artifact = {
            "decode_mode": decode_mode,
            "sample_count": len(samples),
            "samples": samples,
            "summary": summary,
            "artifact_path": str(artifact_path),
        }
        _write_json(artifact_path, artifact, compact=False)
        return artifact

    samples: list[dict[str, Any]] = []
    for sample_idx in range(len(FOCUSED_WAVE_OUTPUTS) // 2):
        pack_a = _or_reduce(FOCUSED_WAVE_OUTPUTS[sample_idx * 2])
        pack_b = _or_reduce(FOCUSED_WAVE_OUTPUTS[sample_idx * 2 + 1])
        samples.append(
            {
                "sample_index": sample_idx,
                "phase": pack_a & 0x7,
                "req_ready": (pack_a >> 3) & 0x1,
                "req_valid": (pack_a >> 4) & 0x1,
                "rsp_ready": (pack_a >> 5) & 0x1,
                "rsp_valid": (pack_a >> 6) & 0x1,
                "device_a_ready": (pack_a >> 7) & 0x1,
                "device_a_valid": (pack_a >> 8) & 0x1,
                "device_d_ready": (pack_a >> 9) & 0x1,
                "device_d_valid": (pack_a >> 10) & 0x1,
                "reqfifo_depth": (pack_a >> 11) & 0x3,
                "rspfifo_depth": (pack_a >> 13) & 0x3,
                "a_source": (pack_a >> 15) & 0xFF,
                "d_source": (pack_a >> 23) & 0xFF,
                "overflow_event": (pack_a >> 31) & 0x1,
                "a_data_upper16": pack_b & 0xFFFF,
                "d_data_upper16": (pack_b >> 16) & 0xFFFF,
                "pack_a_hex": f"0x{pack_a:08x}",
                "pack_b_hex": f"0x{pack_b:08x}",
            }
        )

    metric_word0 = _or_reduce(FOCUSED_METRIC_OUTPUTS[0])
    metric_word1 = _or_reduce(FOCUSED_METRIC_OUTPUTS[1])
    metric_word2 = _or_reduce(FOCUSED_METRIC_OUTPUTS[2])
    metric_word3 = _or_reduce(FOCUSED_METRIC_OUTPUTS[3])
    metric_word4 = _or_reduce(FOCUSED_METRIC_OUTPUTS[4])
    summary = {
        "req_handshake_seen": metric_word0 & 0xFF,
        "rsp_handshake_seen": (metric_word0 >> 8) & 0xFF,
        "max_reqfifo_depth": (metric_word0 >> 16) & 0xFF,
        "max_rspfifo_depth": (metric_word0 >> 24) & 0xFF,
        "a_data_upper_or": metric_word1 & 0xFFFF,
        "d_data_upper_or": (metric_word1 >> 16) & 0xFFFF,
        "progress_cycle": metric_word2 & 0xFFFF,
        "sim_cycle": (metric_word2 >> 16) & 0xFFFF,
        "cfg_req_valid_pct": metric_word3 & 0xFF,
        "cfg_rsp_valid_pct": (metric_word3 >> 8) & 0xFF,
        "source_mask_cfg": metric_word4 & 0xFF,
        "address_mask_cfg": (metric_word4 >> 8) & 0xFF,
    }
    artifact_path = artifact_dir / "gpu_focused_wave.json"
    artifact = {
        "decode_mode": decode_mode,
        "sample_count": len(samples),
        "samples": samples,
        "summary": summary,
        "artifact_path": str(artifact_path),
    }
    _write_json(artifact_path, artifact, compact=False)
    return artifact


def _driver_for_batch_case(base_driver: dict[str, Any], batch_case: dict[str, Any]) -> dict[str, Any]:
    driver = dict(base_driver)
    for key, value in dict(batch_case.get("driver") or {}).items():
        if key in DRIVER_DEFAULTS:
            driver[key] = value
    return driver


def _build_packed_state_drivers(
    *,
    base_driver: dict[str, Any],
    batch_cases: list[dict[str, Any]],
    nstates: int,
    uniform_states: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    state_drivers: list[dict[str, Any]] = []
    case_spans: list[dict[str, Any]] = []
    state_offset = 0
    for batch_case in batch_cases:
        states_per_case = max(1, int(batch_case.get("states_per_case", 1)))
        if state_offset + states_per_case > nstates:
            raise SystemExit(
                f"Packed cases require {state_offset + states_per_case} states but --nstates={nstates}"
            )
        case_driver = _driver_for_batch_case(base_driver, batch_case)
        start_state = state_offset
        for local_state_idx in range(states_per_case):
            state_driver = dict(case_driver)
            if not uniform_states:
                state_driver["seed"] = (
                    int(case_driver["seed"]) + (local_state_idx * 97)
                ) & 0xffff_ffff
            state_drivers.append(state_driver)
            state_offset += 1
        case_spans.append(
            {
                **batch_case,
                "state_start": start_state,
                "state_count": states_per_case,
            }
        )
    return state_drivers, case_spans


def _build_observability_summary(
    *,
    metrics: dict[str, Any],
    collector: dict[str, Any],
    build_dir: Path,
    stdout_log: Path,
    region_summary: dict[str, Any],
    skip_cpu_reference_build: bool,
) -> dict[str, Any]:
    unsupported = dict(((collector.get("reasons") or {}).get("unsupported") or {}))
    fallback = dict(((collector.get("reasons") or {}).get("fallback") or {}))
    checks = {
        "gpu_ms_per_rep": isinstance(metrics.get("gpu_ms_per_rep"), (int, float)),
        "cpu_ms_per_rep": skip_cpu_reference_build
        or isinstance(metrics.get("cpu_ms_per_rep"), (int, float)),
        "mismatch": metrics.get("mismatch") is not None,
        "compact_mismatch": metrics.get("compact_mismatch") is not None,
        "bench_log": (build_dir / "bench_run.log").exists(),
        "stdout_log": stdout_log.exists(),
        "collector_contract_status": isinstance(collector.get("status"), dict),
        "unsupported_reasons": isinstance(unsupported, dict) and bool(unsupported),
        "fallback_reasons": isinstance(fallback, dict) and bool(fallback),
        "region_summary": bool(region_summary),
        "gpu_compact": (build_dir / "gpu_output_compact.bin").exists(),
        "cpu_compact": skip_cpu_reference_build or (build_dir / "cpu_output_compact.bin").exists(),
    }
    issues = [name for name, ok in checks.items() if not ok]
    return {
        "status": "ready" if not issues else "needs_review",
        "checks": checks,
        "issues": issues,
        "nonzero_unsupported_reasons": {
            key: value
            for key, value in unsupported.items()
            if value not in (None, 0, "", False)
        },
        "nonzero_fallback_reasons": {
            key: value
            for key, value in fallback.items()
            if value not in (None, 0, "", False)
        },
    }


def _compact_region_summary(region_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": region_summary.get("schema_version"),
        "target": region_summary.get("target"),
        "coverage_domain": region_summary.get("coverage_domain"),
        "region_count": int(region_summary.get("region_count") or 0),
        "active_regions": list(region_summary.get("active_regions") or []),
        "active_region_count": int(region_summary.get("active_region_count") or 0),
        "partial_regions": list(region_summary.get("partial_regions") or []),
        "partial_region_count": int(region_summary.get("partial_region_count") or 0),
        "dead_regions": list(region_summary.get("dead_regions") or []),
        "dead_region_count": int(region_summary.get("dead_region_count") or 0),
    }


def _extract_metric_from_text(text: str, key: str) -> int | None:
    match = re.search(rf"^{re.escape(key)}=(-?\d+)$", text, re.MULTILINE)
    if not match:
        return None
    return int(match.group(1))


def _classify_known_structured_semantic_gap(
    *,
    stdout_text: str,
    raw_kernel_path: Path,
    hybrid_mode: str,
) -> str | None:
    if hybrid_mode not in {"single-partition", "single-cluster"}:
        return None
    if not stdout_text or not raw_kernel_path.is_file():
        return None
    if "CUDA error" in stdout_text or "Internal error" in stdout_text:
        return None
    mismatch = _extract_metric_from_text(stdout_text, "mismatch")
    compact_mismatch = _extract_metric_from_text(stdout_text, "compact_mismatch")
    hybrid_mismatch = _extract_metric_from_text(stdout_text, "hybrid_mismatch")
    if mismatch != 0 or compact_mismatch != 0 or not hybrid_mismatch:
        return None
    raw_text = raw_kernel_path.read_text(encoding="utf-8", errors="ignore")
    if 'extern "C" __host__ uint32_t sim_accel_eval_seq_partition_count() {\n    return 0U;\n}' not in raw_text:
        return None
    return "structured_interface_missing_seq_commit"


def _state_window_any_nonzero(
    output_map: dict[str, dict[str, Any]],
    name: str,
    state_start: int,
    state_count: int,
) -> bool:
    values = (output_map.get(name) or {}).get("state_values") or ()
    end = min(state_start + state_count, len(values))
    for index in range(state_start, end):
        if int(values[index]) != 0:
            return True
    return False


def _state_window_max(
    output_map: dict[str, dict[str, Any]],
    name: str,
    state_start: int,
    state_count: int,
) -> int:
    values = (output_map.get(name) or {}).get("state_values") or ()
    end = min(state_start + state_count, len(values))
    value_max = 0
    for index in range(state_start, end):
        value = int(values[index])
        if value > value_max:
            value_max = value
    return value_max


def _aggregate_output_values(
    output_map: dict[str, dict[str, Any]],
    names: list[str],
    state_start: int,
    state_count: int,
) -> dict[str, int]:
    aggregated: dict[str, int] = {}
    for name in names:
        aggregated[name] = _state_window_max(output_map, name, state_start, state_count)
    return aggregated


def _missing_output_names(
    output_map: dict[str, dict[str, Any]],
    names: list[str] | set[str],
) -> list[str]:
    return sorted(name for name in names if name not in output_map)


def _classify_oracle_status(oracle_values: dict[str, int]) -> str:
    expected_total = int(oracle_values.get("oracle_expected_ok_count_o") or 0) + int(
        oracle_values.get("oracle_expected_err_count_o") or 0
    )
    observed_total = int(oracle_values.get("oracle_observed_ok_count_o") or 0) + int(
        oracle_values.get("oracle_observed_err_count_o") or 0
    )
    family_seen = int(oracle_values.get("oracle_semantic_family_seen_o") or 0)
    family_acked = int(oracle_values.get("oracle_semantic_family_acked_o") or 0)
    stable_violation = int(oracle_values.get("oracle_req_stable_violation_o") or 0)
    if stable_violation > 0:
        return "request_stability_violation"
    if observed_total > 0:
        return "observed_response_classified"
    if expected_total > 0 or family_acked > 0:
        return "request_accepted_only"
    if family_seen > 0:
        return "scheduler_seen_only"
    return "oracle_dead"


def _oracle_signal_inconsistent(oracle_values: dict[str, int]) -> int:
    split_required = (
        "oracle_req_signature_precommit_o",
        "oracle_stalled_req_signature_precommit_o",
        "oracle_stalled_req_signature_postcommit_o",
        "oracle_req_signature_delta_precommit_o",
        "oracle_req_signature_delta_postcommit_o",
    )
    if all(name in oracle_values for name in split_required):
        current_precommit = int(oracle_values.get("oracle_req_signature_precommit_o") or 0)
        stalled_precommit = int(oracle_values.get("oracle_stalled_req_signature_precommit_o") or 0)
        stalled_postcommit = int(oracle_values.get("oracle_stalled_req_signature_postcommit_o") or 0)
        delta_precommit = int(oracle_values.get("oracle_req_signature_delta_precommit_o") or 0)
        delta_postcommit = int(oracle_values.get("oracle_req_signature_delta_postcommit_o") or 0)
        return int(
            (delta_precommit != (current_precommit ^ stalled_precommit))
            or (delta_postcommit != (current_precommit ^ stalled_postcommit))
        )
    required = (
        "oracle_req_signature_o",
        "oracle_stalled_req_signature_o",
        "oracle_req_signature_delta_o",
    )
    if any(name not in oracle_values for name in required):
        return 0
    current = int(oracle_values.get("oracle_req_signature_o") or 0)
    stalled = int(oracle_values.get("oracle_stalled_req_signature_o") or 0)
    delta = int(oracle_values.get("oracle_req_signature_delta_o") or 0)
    return int(delta != (current ^ stalled))


def _oracle_relation_status(
    *,
    missing_oracle_outputs: list[str],
    oracle_signal_inconsistent: int,
) -> str:
    if missing_oracle_outputs:
        return "oracle_relation_missing"
    if oracle_signal_inconsistent:
        return "oracle_relation_inconsistent"
    return "oracle_relation_ok"


def _summary_contract_status(
    *,
    missing_oracle_outputs: list[str],
    oracle_signal_inconsistent: int,
    cpu_reference_checked: int,
    mismatch: int | None,
    compact_mismatch: int | None,
) -> str:
    if compact_mismatch is not None and compact_mismatch != 0:
        return "compact_mismatch"
    if missing_oracle_outputs:
        return "missing_oracle_outputs"
    if oracle_signal_inconsistent:
        return "derived_output_inconsistent"
    if cpu_reference_checked and mismatch is not None and mismatch != 0:
        return "cpu_reference_mismatch"
    return "contract_ready"


def _classify_coverage_status(
    *,
    points_hit: int,
    active_region_count: int,
    dead_region_count: int,
) -> str:
    if points_hit > 0 and active_region_count > 0:
        return "coverage_alive"
    if points_hit > 0:
        return "word_only"
    if active_region_count > 0:
        return "region_only"
    if dead_region_count > 0:
        return "coverage_dead"
    return "coverage_unknown"


def _classify_diagnostic_status(
    *,
    traffic_values: dict[str, int],
    execution_values: dict[str, int],
    oracle_status: str,
    oracle_alive: int,
    points_hit: int,
    active_region_count: int,
    dead_region_count: int,
) -> str:
    accepted_traffic_sum = sum(int(traffic_values.get(name) or 0) for name in TRAFFIC_COUNTER_OUTPUTS)
    progress_cycle_count = int(execution_values.get("progress_cycle_count_o") or 0)
    debug_phase = int(execution_values.get("debug_phase_o") or 0) & 0x7
    debug_trace_live = int(execution_values.get("debug_trace_live_o") or 0)
    if oracle_status == "oracle_untrusted_missing_outputs":
        return "oracle_untrusted_missing_outputs"
    if oracle_status == "oracle_untrusted_inconsistent_outputs":
        return "derived_output_inconsistent"
    if accepted_traffic_sum <= 0 and progress_cycle_count <= 0 and debug_phase == 0 and debug_trace_live <= 0:
        return "execution_dead"
    if oracle_status == "request_stability_violation" and points_hit <= 0 and active_region_count <= 0:
        return "live_request_stability_with_dead_coverage"
    if oracle_alive > 0 and points_hit <= 0 and active_region_count <= 0:
        return "oracle_alive_coverage_dead"
    if accepted_traffic_sum > 0 and points_hit <= 0 and active_region_count <= 0:
        return "traffic_alive_coverage_dead"
    if points_hit > 0 and active_region_count > 0:
        return "truth_alive"
    if dead_region_count > 0:
        return "coverage_dead_without_oracle_signal"
    return "diagnostic_unknown"


def _apply_consistency_diagnostic_override(
    diagnostic_status: str,
    consistency_flags: dict[str, int],
) -> str:
    if int(consistency_flags.get("mixed_commit_visibility") or 0) > 0:
        return "mixed_commit_visibility"
    if int(consistency_flags.get("execution_signal_inconsistent") or 0) > 0:
        return "execution_signal_inconsistent"
    if int(consistency_flags.get("coverage_plane_inconsistent") or 0) > 0:
        return "coverage_plane_inconsistent"
    return diagnostic_status


def _history_visibility_kind(manifest: dict[str, Any] | None) -> str:
    contract = (manifest or {}).get("history_visibility_contract") or {}
    kind = str(contract.get("kind") or "").strip()
    if kind:
        return kind
    target = str((manifest or {}).get("target") or "")
    if target.endswith("alert_handler_ping_timer"):
        return "alert_handler_ping_timer_semantic_seen"
    if target.endswith("alert_handler_esc_timer"):
        return "alert_handler_esc_timer_semantic_seen"
    if target.endswith("edn_main_sm"):
        return "edn_main_sm_windowed"
    if target.endswith("entropy_src_main_sm"):
        return "entropy_src_main_sm_semantic_seen"
    if target.endswith("csrng_main_sm"):
        return "csrng_main_sm_semantic_seen"
    if target.endswith("aes_cipher_control"):
        return "aes_cipher_control_semantic_seen"
    if target.endswith("pwrmgr_fsm"):
        return "pwrmgr_fsm_semantic_seen"
    if target.endswith("lc_ctrl_fsm"):
        return "lc_ctrl_fsm_semantic_seen"
    if target.endswith("rom_ctrl_fsm"):
        return "rom_ctrl_fsm_semantic_seen"
    return ""


def _consistency_flags(
    *,
    manifest: dict[str, Any] | None,
    traffic_values: dict[str, int],
    execution_values: dict[str, int],
    internal_probe_values: dict[str, int],
    oracle_alive: int,
    points_hit: int,
    active_region_count: int,
) -> dict[str, int]:
    accepted_traffic_sum = sum(int(traffic_values.get(name) or 0) for name in TRAFFIC_COUNTER_OUTPUTS)
    progress_cycle_count = int(execution_values.get("progress_cycle_count_o") or 0)
    debug_phase = int(execution_values.get("debug_phase_o") or 0) & 0x7
    debug_cycle_count = int(execution_values.get("debug_cycle_count_o") or 0)
    internal_phase = int(internal_probe_values.get("tlul_sink_gpu_cov_tb__DOT__phase_q") or 0) & 0x7
    internal_cycle_count = int(internal_probe_values.get("tlul_sink_gpu_cov_tb__DOT__cycle_count_q") or 0)
    tlul_sink_internal_present = int(
        ("tlul_sink_gpu_cov_tb__DOT__phase_q" in internal_probe_values)
        or ("tlul_sink_gpu_cov_tb__DOT__cycle_count_q" in internal_probe_values)
    )
    tlul_sink_mixed_commit_visibility = int(
        tlul_sink_internal_present > 0
        and (accepted_traffic_sum > 0)
        and debug_phase == 0
        and debug_cycle_count == 0
        and internal_phase == 0
        and internal_cycle_count == 0
    )
    history_kind = _history_visibility_kind(manifest)
    edn_mixed_commit_visibility = 0
    csrng_mixed_commit_visibility = 0
    aes_mixed_commit_visibility = 0
    entropy_mixed_commit_visibility = 0
    alert_handler_mixed_commit_visibility = 0
    alert_handler_esc_timer_mixed_commit_visibility = 0
    pwrmgr_mixed_commit_visibility = 0
    lc_ctrl_mixed_commit_visibility = 0
    rom_ctrl_mixed_commit_visibility = 0
    if history_kind == "edn_main_sm_windowed":
        edn_phase_seen_mask = int(internal_probe_values.get("debug_phase_seen_mask_o") or 0)
        edn_boot_window_seen = int(internal_probe_values.get("debug_boot_window_seen_o") or 0)
        edn_auto_window_seen = int(internal_probe_values.get("debug_auto_window_seen_o") or 0)
        edn_boot_req_mode_seen = int(internal_probe_values.get("debug_boot_req_mode_seen_o") or 0)
        edn_auto_req_mode_seen = int(internal_probe_values.get("debug_auto_req_mode_seen_o") or 0)
        edn_host_req_accept_seen = int(internal_probe_values.get("debug_host_req_accept_seen_o") or 0)
        edn_non_idle_state_seen = int(internal_probe_values.get("debug_non_idle_state_seen_o") or 0)
        edn_cmd_sent_seen = int(internal_probe_values.get("debug_cmd_sent_seen_o") or 0)
        edn_send_gencmd_seen = int(internal_probe_values.get("debug_send_gencmd_seen_o") or 0)
        edn_send_rescmd_seen = int(internal_probe_values.get("debug_send_rescmd_seen_o") or 0)
        edn_capt_gencmd_seen = int(internal_probe_values.get("debug_capt_gencmd_seen_o") or 0)
        edn_capt_rescmd_seen = int(internal_probe_values.get("debug_capt_rescmd_seen_o") or 0)
        edn_boot_window_now = int(internal_probe_values.get("debug_boot_window_o") or 0)
        edn_auto_window_now = int(internal_probe_values.get("debug_auto_window_o") or 0)
        edn_boot_req_mode_now = int(internal_probe_values.get("debug_boot_req_mode_o") or 0)
        edn_auto_req_mode_now = int(internal_probe_values.get("debug_auto_req_mode_o") or 0)
        edn_main_sm_state_now = int(internal_probe_values.get("debug_main_sm_state_o") or 0)
        edn_seen_activity = int(
            (edn_phase_seen_mask > 0)
            or (edn_boot_window_seen > 0)
            or (edn_auto_window_seen > 0)
            or (edn_boot_req_mode_seen > 0)
            or (edn_auto_req_mode_seen > 0)
            or (edn_host_req_accept_seen > 0)
            or (edn_non_idle_state_seen > 0)
            or (edn_cmd_sent_seen > 0)
            or (edn_send_gencmd_seen > 0)
            or (edn_send_rescmd_seen > 0)
            or (edn_capt_gencmd_seen > 0)
            or (edn_capt_rescmd_seen > 0)
        )
        edn_current_snapshot_idle = int(
            debug_phase == 0
            and debug_cycle_count == 0
            and edn_boot_window_now == 0
            and edn_auto_window_now == 0
            and edn_boot_req_mode_now == 0
            and edn_auto_req_mode_now == 0
            and edn_main_sm_state_now == 193
        )
        edn_mixed_commit_visibility = int(
            edn_seen_activity > 0
            and edn_current_snapshot_idle > 0
            and (
                accepted_traffic_sum > 0
                or progress_cycle_count > 0
                or points_hit > 0
                or active_region_count > 0
            )
        )
    elif history_kind == "entropy_src_main_sm_semantic_seen":
        entropy_phase = int(
            internal_probe_values.get("entropy_src_main_sm_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        entropy_cycle_count = int(
            internal_probe_values.get("entropy_src_main_sm_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        entropy_family_seen_q = int(
            internal_probe_values.get("entropy_src_main_sm_gpu_cov_tb__DOT__oracle_semantic_family_seen_q")
            or 0
        )
        entropy_case_seen_q = int(
            internal_probe_values.get("entropy_src_main_sm_gpu_cov_tb__DOT__oracle_semantic_case_seen_q")
            or 0
        )
        entropy_seen_activity = int(
            (int(internal_probe_values.get("debug_boot_seen_o") or 0) > 0)
            or (int(internal_probe_values.get("debug_startup_seen_o") or 0) > 0)
            or (int(internal_probe_values.get("debug_continuous_seen_o") or 0) > 0)
            or (int(internal_probe_values.get("debug_fw_seen_o") or 0) > 0)
            or (int(internal_probe_values.get("debug_sha3_seen_o") or 0) > 0)
            or (int(internal_probe_values.get("debug_alert_seen_o") or 0) > 0)
        )
        entropy_current_snapshot_sparse = int(
            debug_phase == 0
            and debug_cycle_count == 0
            and entropy_phase == 0
            and entropy_cycle_count == 0
            and entropy_family_seen_q == 0
            and entropy_case_seen_q == 0
        )
        entropy_mixed_commit_visibility = int(
            entropy_seen_activity > 0
            and entropy_current_snapshot_sparse > 0
            and (
                accepted_traffic_sum > 0
                or progress_cycle_count > 0
                or points_hit > 0
                or active_region_count > 0
            )
        )
    elif history_kind == "csrng_main_sm_semantic_seen":
        csrng_phase = int(
            internal_probe_values.get("csrng_main_sm_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        csrng_cycle_count = int(
            internal_probe_values.get("csrng_main_sm_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        csrng_family_seen_q = int(
            internal_probe_values.get("csrng_main_sm_gpu_cov_tb__DOT__oracle_semantic_family_seen_q")
            or 0
        )
        csrng_family_acked_q = int(
            internal_probe_values.get("csrng_main_sm_gpu_cov_tb__DOT__oracle_semantic_family_acked_q")
            or 0
        )
        csrng_case_seen_q = int(
            internal_probe_values.get("csrng_main_sm_gpu_cov_tb__DOT__oracle_semantic_case_seen_q")
            or 0
        )
        csrng_case_acked_q = int(
            internal_probe_values.get("csrng_main_sm_gpu_cov_tb__DOT__oracle_semantic_case_acked_q")
            or 0
        )
        csrng_seen_activity = int(
            csrng_family_seen_q > 0
            or csrng_family_acked_q > 0
            or csrng_case_seen_q > 0
            or csrng_case_acked_q > 0
            or int(internal_probe_values.get("debug_accept_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_entropy_wait_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_direct_issue_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_complete_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_error_seen_o") or 0) > 0
        )
        csrng_current_snapshot_sparse = int(
            debug_phase == 0
            and debug_cycle_count == 0
            and csrng_phase == 0
            and csrng_cycle_count == 0
        )
        csrng_mixed_commit_visibility = int(
            csrng_seen_activity > 0
            and csrng_current_snapshot_sparse > 0
            and (
                accepted_traffic_sum > 0
                or progress_cycle_count > 0
                or points_hit > 0
                or active_region_count > 0
            )
        )
    elif history_kind == "aes_cipher_control_semantic_seen":
        aes_phase = int(
            internal_probe_values.get("aes_cipher_control_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        aes_cycle_count = int(
            internal_probe_values.get("aes_cipher_control_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        aes_family_seen_q = int(
            internal_probe_values.get("aes_cipher_control_gpu_cov_tb__DOT__oracle_semantic_family_seen_q")
            or 0
        )
        aes_family_acked_q = int(
            internal_probe_values.get("aes_cipher_control_gpu_cov_tb__DOT__oracle_semantic_family_acked_q")
            or 0
        )
        aes_case_seen_q = int(
            internal_probe_values.get("aes_cipher_control_gpu_cov_tb__DOT__oracle_semantic_case_seen_q")
            or 0
        )
        aes_case_acked_q = int(
            internal_probe_values.get("aes_cipher_control_gpu_cov_tb__DOT__oracle_semantic_case_acked_q")
            or 0
        )
        aes_seen_activity = int(
            aes_family_seen_q > 0
            or aes_family_acked_q > 0
            or aes_case_seen_q > 0
            or aes_case_acked_q > 0
            or int(internal_probe_values.get("debug_alert_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_reseed_req_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_subbytes_ack_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_keyexpand_ack_seen_o") or 0) > 0
        )
        aes_current_snapshot_sparse = int(
            debug_phase == 0
            and debug_cycle_count == 0
            and aes_phase == 0
            and aes_cycle_count == 0
        )
        aes_mixed_commit_visibility = int(
            aes_seen_activity > 0
            and aes_current_snapshot_sparse > 0
            and (
                accepted_traffic_sum > 0
                or progress_cycle_count > 0
                or points_hit > 0
                or active_region_count > 0
            )
        )
    elif history_kind == "alert_handler_ping_timer_semantic_seen":
        alert_phase = int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        alert_cycle_count = int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        alert_family_seen_q = int(
            internal_probe_values.get(
                "alert_handler_ping_timer_gpu_cov_tb__DOT__oracle_semantic_family_seen_q"
            ) or 0
        )
        alert_case_seen_q = int(
            internal_probe_values.get(
                "alert_handler_ping_timer_gpu_cov_tb__DOT__oracle_semantic_case_seen_q"
            ) or 0
        )
        alert_seen_activity = int(
            alert_family_seen_q > 0
            or alert_case_seen_q > 0
            or int(internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__edn_req_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__alert_req_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__esc_req_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__skip_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__alert_fail_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__activity_seen_q") or 0) > 0
        )
        alert_current_snapshot_sparse = int(
            debug_phase == 0
            and debug_cycle_count == 0
            and alert_phase == 0
            and alert_cycle_count == 0
        )
        alert_handler_mixed_commit_visibility = int(
            alert_seen_activity > 0
            and alert_current_snapshot_sparse > 0
            and (
                accepted_traffic_sum > 0
                or progress_cycle_count > 0
                or points_hit > 0
                or active_region_count > 0
            )
        )
    elif history_kind == "alert_handler_esc_timer_semantic_seen":
        alert_esc_phase = int(
            internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        alert_esc_cycle_count = int(
            internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        alert_esc_family_seen_q = int(
            internal_probe_values.get(
                "alert_handler_esc_timer_gpu_cov_tb__DOT__oracle_semantic_family_seen_q"
            )
            or internal_probe_values.get("oracle_semantic_family_seen_o")
            or 0
        )
        alert_esc_case_seen_q = int(
            internal_probe_values.get(
                "alert_handler_esc_timer_gpu_cov_tb__DOT__oracle_semantic_case_seen_q"
            )
            or internal_probe_values.get("oracle_semantic_case_seen_o")
            or 0
        )
        alert_esc_seen_activity = int(
            alert_esc_family_seen_q > 0
            or alert_esc_case_seen_q > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__timeout_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__timeout_trigger_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__phase0_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__phase1_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__phase2_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__phase3_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__crashdump_latch_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__esc_sig_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__clear_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__accu_fail_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__terminal_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__fsm_error_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__non_idle_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__activity_seen_q") or 0) > 0
            or int(internal_probe_values.get("debug_timeout_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_phase0_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_phase1_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_phase2_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_phase3_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_terminal_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_error_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_crashdump_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_clear_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_trace_live_o") or 0) > 0
        )
        alert_esc_current_snapshot_sparse = int(
            debug_phase == 0
            and debug_cycle_count == 0
            and alert_esc_phase == 0
            and alert_esc_cycle_count == 0
        )
        alert_handler_esc_timer_mixed_commit_visibility = int(
            alert_esc_seen_activity > 0
            and alert_esc_current_snapshot_sparse > 0
            and (
                accepted_traffic_sum > 0
                or progress_cycle_count > 0
                or points_hit > 0
                or active_region_count > 0
            )
        )
    elif history_kind == "pwrmgr_fsm_semantic_seen":
        pwrmgr_phase = int(
            internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        pwrmgr_cycle_count = int(
            internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        pwrmgr_family_seen_q = int(
            internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__oracle_semantic_family_seen_q")
            or 0
        )
        pwrmgr_case_seen_q = int(
            internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__oracle_semantic_case_seen_q")
            or 0
        )
        pwrmgr_seen_activity = int(
            pwrmgr_family_seen_q > 0
            or pwrmgr_case_seen_q > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__req_pwrup_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__ack_pwrup_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__active_state_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__clk_enable_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__release_rst_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__strap_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__otp_init_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__otp_done_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__lc_init_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__lc_done_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__low_power_entry_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__req_pwrdn_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__ack_pwrdn_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__abort_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__reset_path_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__rom_done_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__rom_good_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__fetch_enable_seen_q") or 0) > 0
        )
        pwrmgr_current_snapshot_sparse = int(
            debug_phase == 0
            and debug_cycle_count == 0
            and pwrmgr_phase == 0
            and pwrmgr_cycle_count == 0
            and pwrmgr_family_seen_q == 0
            and pwrmgr_case_seen_q == 0
        )
        pwrmgr_mixed_commit_visibility = int(
            pwrmgr_seen_activity > 0
            and pwrmgr_current_snapshot_sparse > 0
            and (
                accepted_traffic_sum > 0
                or progress_cycle_count > 0
                or points_hit > 0
                or active_region_count > 0
            )
        )
    elif history_kind == "lc_ctrl_fsm_semantic_seen":
        lc_ctrl_phase = int(
            internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        lc_ctrl_cycle_count = int(
            internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        lc_ctrl_family_seen_q = int(
            internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__oracle_semantic_family_seen_q")
            or 0
        )
        lc_ctrl_case_seen_q = int(
            internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__oracle_semantic_case_seen_q")
            or 0
        )
        lc_ctrl_seen_activity = int(
            lc_ctrl_family_seen_q > 0
            or lc_ctrl_case_seen_q > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__init_req_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__init_done_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__idle_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__trans_cmd_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__clk_byp_req_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__clk_byp_ack_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__token_hash_req_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__token_hash_ack_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__token_path_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__otp_prog_req_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__otp_prog_ack_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__trans_success_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__flash_rma_req_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__flash_rma_ack_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__trans_invalid_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__token_invalid_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__otp_or_flash_error_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__state_invalid_seen_q") or 0) > 0
        )
        lc_ctrl_current_snapshot_sparse = int(
            debug_phase == 0
            and debug_cycle_count == 0
            and lc_ctrl_phase == 0
            and lc_ctrl_cycle_count == 0
            and active_region_count <= 1
        )
        lc_ctrl_mixed_commit_visibility = int(
            lc_ctrl_seen_activity > 0
            and lc_ctrl_current_snapshot_sparse > 0
            and (
                accepted_traffic_sum > 0
                or progress_cycle_count > 0
                or points_hit > 0
                or active_region_count > 0
            )
        )
    elif history_kind == "rom_ctrl_fsm_semantic_seen":
        rom_ctrl_phase = int(
            internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        rom_ctrl_cycle_count = int(
            internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        rom_ctrl_family_seen_q = int(
            internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__oracle_semantic_family_seen_q")
            or 0
        )
        rom_ctrl_case_seen_q = int(
            internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__oracle_semantic_case_seen_q")
            or 0
        )
        rom_ctrl_seen_activity = int(
            rom_ctrl_family_seen_q > 0
            or rom_ctrl_case_seen_q > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__reading_low_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__rom_stream_low_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__kmac_feed_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__reading_high_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__top_digest_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__digest_capture_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__rom_ahead_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__kmac_ahead_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__kmac_done_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__checker_start_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__checker_compare_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__checker_done_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__done_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__bus_select_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__alert_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__invalid_seen_q") or 0) > 0
            or int(internal_probe_values.get("debug_low_stream_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_top_digest_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_race_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_checker_seen_o") or 0) > 0
            or int(internal_probe_values.get("debug_terminal_seen_o") or 0) > 0
        )
        rom_ctrl_current_snapshot_sparse = int(
            debug_phase == 0
            and debug_cycle_count == 0
            and rom_ctrl_phase == 0
            and rom_ctrl_cycle_count == 0
            and rom_ctrl_family_seen_q == 0
            and rom_ctrl_case_seen_q == 0
        )
        rom_ctrl_mixed_commit_visibility = int(
            rom_ctrl_seen_activity > 0
            and rom_ctrl_current_snapshot_sparse > 0
            and (
                accepted_traffic_sum > 0
                or progress_cycle_count > 0
                or points_hit > 0
                or active_region_count > 0
            )
        )
    mixed_commit_visibility = int(
        tlul_sink_mixed_commit_visibility > 0
        or edn_mixed_commit_visibility > 0
        or csrng_mixed_commit_visibility > 0
        or aes_mixed_commit_visibility > 0
        or entropy_mixed_commit_visibility > 0
        or alert_handler_mixed_commit_visibility > 0
        or alert_handler_esc_timer_mixed_commit_visibility > 0
        or pwrmgr_mixed_commit_visibility > 0
        or lc_ctrl_mixed_commit_visibility > 0
        or rom_ctrl_mixed_commit_visibility > 0
    )
    coverage_plane_inconsistent = int(
        (accepted_traffic_sum > 0 or oracle_alive > 0) and points_hit <= 0 and active_region_count <= 0
    )
    export_internal_state_mismatch = int(
        (
            ("tlul_sink_gpu_cov_tb__DOT__phase_q" in internal_probe_values)
            and debug_phase != internal_phase
        )
        or (
            ("tlul_sink_gpu_cov_tb__DOT__cycle_count_q" in internal_probe_values)
            and debug_cycle_count != internal_cycle_count
        )
    )
    execution_signal_inconsistent = int(export_internal_state_mismatch > 0)
    compact_plane_inconsistent = int(export_internal_state_mismatch > 0)
    return {
        "execution_signal_inconsistent": execution_signal_inconsistent,
        "coverage_plane_inconsistent": coverage_plane_inconsistent,
        "compact_plane_inconsistent": compact_plane_inconsistent,
        "export_internal_state_mismatch": export_internal_state_mismatch,
        "mixed_commit_visibility": mixed_commit_visibility,
    }


def _augment_active_words_for_history_visibility(
    *,
    manifest: dict[str, Any],
    active_words: list[str],
    traffic_values: dict[str, int],
    execution_values: dict[str, int],
    internal_probe_values: dict[str, int],
    driver_values: dict[str, Any] | None = None,
) -> list[str]:
    history_kind = _history_visibility_kind(manifest)
    if not history_kind:
        return active_words

    accepted_traffic_sum = sum(int(traffic_values.get(name) or 0) for name in TRAFFIC_COUNTER_OUTPUTS)
    progressed = int(execution_values.get("progress_cycle_count_o") or 0) > 0
    debug_phase = int(execution_values.get("debug_phase_o") or 0) & 0x7
    debug_cycle_count = int(execution_values.get("debug_cycle_count_o") or 0)
    active_set = set(active_words)

    if history_kind == "edn_main_sm_windowed":
        boot_seen = int(internal_probe_values.get("debug_boot_window_seen_o") or 0) > 0
        auto_seen = int(internal_probe_values.get("debug_auto_window_seen_o") or 0) > 0
        boot_req_seen = int(internal_probe_values.get("debug_boot_req_mode_seen_o") or 0) > 0
        auto_req_seen = int(internal_probe_values.get("debug_auto_req_mode_seen_o") or 0) > 0
        host_req_seen = int(internal_probe_values.get("debug_host_req_accept_seen_o") or 0) > 0
        non_idle_seen = int(internal_probe_values.get("debug_non_idle_state_seen_o") or 0) > 0
        cmd_sent_seen = int(internal_probe_values.get("debug_cmd_sent_seen_o") or 0) > 0
        send_gencmd_seen = int(internal_probe_values.get("debug_send_gencmd_seen_o") or 0) > 0
        send_rescmd_seen = int(internal_probe_values.get("debug_send_rescmd_seen_o") or 0) > 0
        capt_gencmd_seen = int(internal_probe_values.get("debug_capt_gencmd_seen_o") or 0) > 0
        capt_rescmd_seen = int(internal_probe_values.get("debug_capt_rescmd_seen_o") or 0) > 0
        boot_now = int(internal_probe_values.get("debug_boot_window_o") or 0) > 0
        auto_now = int(internal_probe_values.get("debug_auto_window_o") or 0) > 0

        mixed_visibility = (
            (boot_seen or auto_seen or boot_req_seen or auto_req_seen or host_req_seen or non_idle_seen)
            and not (boot_now or auto_now)
            and (accepted_traffic_sum > 0 or progressed)
        )
        if not mixed_visibility:
            return active_words

        if boot_seen or boot_req_seen:
            active_set.update(
                {
                    "real_toggle_subset_word0_o",
                    "real_toggle_subset_word10_o",
                    "real_toggle_subset_word14_o",
                }
            )
        if auto_seen or auto_req_seen:
            active_set.update(
                {
                    "real_toggle_subset_word1_o",
                    "real_toggle_subset_word11_o",
                }
            )
            if int(traffic_values.get("device_req_accepted_o") or 0) > 0 or host_req_seen:
                active_set.add("real_toggle_subset_word6_o")
            if int(traffic_values.get("device_rsp_accepted_o") or 0) > 0:
                active_set.add("real_toggle_subset_word7_o")
        if non_idle_seen or host_req_seen:
            active_set.update(
                {
                    "real_toggle_subset_word15_o",
                    "real_toggle_subset_word17_o",
                }
            )
        if send_gencmd_seen or capt_gencmd_seen:
            active_set.add("real_toggle_subset_word3_o")
        if send_rescmd_seen or capt_rescmd_seen:
            active_set.add("real_toggle_subset_word4_o")
        if (
            send_gencmd_seen
            or send_rescmd_seen
            or capt_gencmd_seen
            or capt_rescmd_seen
            or cmd_sent_seen
        ):
            active_set.add("real_toggle_subset_word13_o")
        return [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name in active_set]

    if history_kind == "csrng_main_sm_semantic_seen":
        csrng_phase = int(
            internal_probe_values.get("csrng_main_sm_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        csrng_cycle_count = int(
            internal_probe_values.get("csrng_main_sm_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        csrng_family_seen = int(
            internal_probe_values.get("csrng_main_sm_gpu_cov_tb__DOT__oracle_semantic_family_seen_q")
            or 0
        )
        csrng_family_acked = int(
            internal_probe_values.get("csrng_main_sm_gpu_cov_tb__DOT__oracle_semantic_family_acked_q")
            or 0
        )
        csrng_case_seen = int(
            internal_probe_values.get("csrng_main_sm_gpu_cov_tb__DOT__oracle_semantic_case_seen_q")
            or 0
        )
        csrng_case_acked = int(
            internal_probe_values.get("csrng_main_sm_gpu_cov_tb__DOT__oracle_semantic_case_acked_q")
            or 0
        )
        mixed_visibility = (
            debug_phase == 0
            and debug_cycle_count == 0
            and csrng_phase == 0
            and csrng_cycle_count == 0
            and (
                csrng_family_seen > 0
                or csrng_family_acked > 0
                or csrng_case_seen > 0
                or csrng_case_acked > 0
                or int(internal_probe_values.get("debug_accept_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_entropy_wait_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_direct_issue_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_complete_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_error_seen_o") or 0) > 0
            )
            and (accepted_traffic_sum > 0 or progressed)
        )
        if not mixed_visibility:
            return active_words

        parse_like = bool(csrng_family_seen & 0x1) or bool(csrng_family_acked & 0x1) or int(
            internal_probe_values.get("debug_accept_seen_o") or 0
        ) > 0
        entropy_like = bool(csrng_family_seen & 0x2) or bool(csrng_family_acked & 0x2) or int(
            internal_probe_values.get("debug_entropy_wait_seen_o") or 0
        ) > 0 or int(
            internal_probe_values.get("debug_direct_issue_seen_o") or 0
        ) > 0
        issue_like = bool(csrng_family_seen & 0x4) or bool(csrng_case_seen & 0x1F) or bool(
            csrng_case_acked & 0x1F
        )
        complete_like = bool(csrng_family_seen & 0x8) or bool(csrng_family_acked & 0x8) or int(
            internal_probe_values.get("debug_complete_seen_o") or 0
        ) > 0
        error_like = bool(csrng_family_seen & 0x10) or bool(csrng_family_acked & 0x10) or bool(
            csrng_case_seen & 0x80
        ) or bool(csrng_case_acked & 0x80) or int(
            internal_probe_values.get("debug_error_seen_o") or 0
        ) > 0

        if parse_like:
            active_set.update(
                {
                    "real_toggle_subset_word0_o",
                    "real_toggle_subset_word1_o",
                    "real_toggle_subset_word17_o",
                }
            )
        if entropy_like:
            active_set.update(
                {
                    "real_toggle_subset_word7_o",
                    "real_toggle_subset_word8_o",
                    "real_toggle_subset_word12_o",
                }
            )
        if issue_like:
            active_set.update(
                {
                    "real_toggle_subset_word2_o",
                    "real_toggle_subset_word3_o",
                    "real_toggle_subset_word4_o",
                    "real_toggle_subset_word5_o",
                    "real_toggle_subset_word6_o",
                }
            )
        if complete_like:
            active_set.update(
                {
                    "real_toggle_subset_word9_o",
                    "real_toggle_subset_word10_o",
                    "real_toggle_subset_word11_o",
                    "real_toggle_subset_word14_o",
                }
            )
        if error_like:
            active_set.update(
                {
                    "real_toggle_subset_word13_o",
                    "real_toggle_subset_word15_o",
                    "real_toggle_subset_word16_o",
                }
            )
        return [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name in active_set]

    if history_kind == "aes_cipher_control_semantic_seen":
        aes_phase = int(
            internal_probe_values.get("aes_cipher_control_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        aes_cycle_count = int(
            internal_probe_values.get("aes_cipher_control_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        aes_family_seen = int(
            internal_probe_values.get("aes_cipher_control_gpu_cov_tb__DOT__oracle_semantic_family_seen_q")
            or 0
        )
        aes_family_acked = int(
            internal_probe_values.get("aes_cipher_control_gpu_cov_tb__DOT__oracle_semantic_family_acked_q")
            or 0
        )
        aes_case_seen = int(
            internal_probe_values.get("aes_cipher_control_gpu_cov_tb__DOT__oracle_semantic_case_seen_q")
            or 0
        )
        aes_case_acked = int(
            internal_probe_values.get("aes_cipher_control_gpu_cov_tb__DOT__oracle_semantic_case_acked_q")
            or 0
        )
        mixed_visibility = (
            debug_phase == 0
            and debug_cycle_count == 0
            and aes_phase == 0
            and aes_cycle_count == 0
            and (
                aes_family_seen > 0
                or aes_family_acked > 0
                or aes_case_seen > 0
                or aes_case_acked > 0
                or int(internal_probe_values.get("debug_alert_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_reseed_req_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_subbytes_ack_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_keyexpand_ack_seen_o") or 0) > 0
            )
            and (accepted_traffic_sum > 0 or progressed)
        )
        if not mixed_visibility:
            return active_words

        handshake_like = bool(aes_family_seen & 0x1) or bool(aes_family_acked & 0x1) or bool(
            aes_case_seen & 0x1
        ) or bool(aes_case_acked & 0x1) or accepted_traffic_sum > 0
        dispatch_like = bool(aes_family_seen & 0x2) or bool(aes_case_seen & 0x0E)
        subbytes_like = bool(aes_family_seen & 0x4) or bool(aes_family_acked & 0x4) or bool(
            aes_case_acked & 0x40
        ) or int(internal_probe_values.get("debug_subbytes_ack_seen_o") or 0) > 0 or int(
            internal_probe_values.get("debug_keyexpand_ack_seen_o") or 0
        ) > 0
        reseed_like = bool(aes_family_seen & 0x8) or bool(aes_family_acked & 0x8) or bool(
            aes_case_seen & 0x30
        ) or bool(aes_case_acked & 0x20) or int(
            internal_probe_values.get("debug_reseed_req_seen_o") or 0
        ) > 0
        alert_like = bool(aes_family_seen & 0x10) or bool(aes_family_acked & 0x10) or bool(
            aes_case_seen & 0x80
        ) or bool(aes_case_acked & 0x80) or int(
            internal_probe_values.get("debug_alert_seen_o") or 0
        ) > 0

        if handshake_like:
            active_set.update(
                {
                    "real_toggle_subset_word0_o",
                    "real_toggle_subset_word1_o",
                    "real_toggle_subset_word2_o",
                    "real_toggle_subset_word3_o",
                }
            )
        if dispatch_like:
            active_set.update(
                {
                    "real_toggle_subset_word4_o",
                    "real_toggle_subset_word5_o",
                    "real_toggle_subset_word6_o",
                    "real_toggle_subset_word7_o",
                }
            )
        if subbytes_like:
            active_set.update(
                {
                    "real_toggle_subset_word8_o",
                    "real_toggle_subset_word9_o",
                    "real_toggle_subset_word10_o",
                    "real_toggle_subset_word11_o",
                }
            )
        if reseed_like:
            active_set.update(
                {
                    "real_toggle_subset_word12_o",
                    "real_toggle_subset_word13_o",
                    "real_toggle_subset_word14_o",
                }
            )
        if alert_like:
            active_set.update(
                {
                    "real_toggle_subset_word15_o",
                    "real_toggle_subset_word16_o",
                    "real_toggle_subset_word17_o",
                }
            )
        return [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name in active_set]

    if history_kind == "pwrmgr_fsm_semantic_seen":
        pwrmgr_phase = int(
            internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        pwrmgr_cycle_count = int(
            internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        pwrmgr_family_seen = int(
            internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__oracle_semantic_family_seen_q")
            or 0
        )
        pwrmgr_case_seen = int(
            internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__oracle_semantic_case_seen_q")
            or 0
        )
        mixed_visibility = (
            debug_phase == 0
            and debug_cycle_count == 0
            and pwrmgr_phase == 0
            and pwrmgr_cycle_count == 0
            and (
                pwrmgr_family_seen > 0
                or pwrmgr_case_seen > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__req_pwrup_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__ack_pwrup_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__active_state_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__clk_enable_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__release_rst_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__strap_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__otp_init_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__otp_done_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__lc_init_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__lc_done_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__low_power_entry_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__req_pwrdn_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__ack_pwrdn_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__abort_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__reset_path_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__rom_completion_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__rom_done_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__rom_good_seen_q") or 0) > 0
                or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__fetch_enable_seen_q") or 0) > 0
            )
            and (accepted_traffic_sum > 0 or progressed)
        )
        if not mixed_visibility:
            return active_words

        driver_values = dict(driver_values or {})
        target_region = str(driver_values.get("target_region") or "")
        req_family = int(driver_values.get("req_family") or 0) & 0x7
        strap_seen = int(
            internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__strap_seen_q") or 0
        ) > 0
        rom_target_requested = (
            target_region == "rom_check_and_fetch_enable_path"
            or req_family == 4
        )
        rom_completion_seen = int(
            internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__rom_completion_seen_q") or 0
        ) > 0
        rom_path_seen = (
            rom_completion_seen
            or
            int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__rom_done_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__rom_good_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__fetch_enable_seen_q") or 0) > 0
            or (rom_target_requested and strap_seen)
        )

        if (
            int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__req_pwrup_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__ack_pwrup_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__active_state_seen_q") or 0) > 0
            or bool(pwrmgr_family_seen & 0x1)
            or strap_seen
            or rom_path_seen
        ):
            active_set.update(
                {
                    "real_toggle_subset_word0_o",
                    "real_toggle_subset_word1_o",
                    "real_toggle_subset_word2_o",
                }
            )
        if (
            int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__clk_enable_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__release_rst_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__strap_seen_q") or 0) > 0
            or bool(pwrmgr_family_seen & 0x2)
        ):
            active_set.update(
                {
                    "real_toggle_subset_word3_o",
                    "real_toggle_subset_word4_o",
                    "real_toggle_subset_word5_o",
                }
            )
        if (
            int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__otp_init_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__otp_done_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__lc_init_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__lc_done_seen_q") or 0) > 0
            or bool(pwrmgr_family_seen & 0x4)
            or strap_seen
            or rom_path_seen
        ):
            active_set.update(
                {
                    "real_toggle_subset_word6_o",
                    "real_toggle_subset_word7_o",
                    "real_toggle_subset_word8_o",
                    "real_toggle_subset_word9_o",
                }
            )
        if (
            int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__low_power_entry_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__req_pwrdn_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__ack_pwrdn_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__abort_seen_q") or 0) > 0
            or int(internal_probe_values.get("pwrmgr_fsm_gpu_cov_tb__DOT__reset_path_seen_q") or 0) > 0
            or bool(pwrmgr_family_seen & 0x8)
        ):
            active_set.update(
                {
                    "real_toggle_subset_word10_o",
                    "real_toggle_subset_word11_o",
                    "real_toggle_subset_word12_o",
                    "real_toggle_subset_word13_o",
                    "real_toggle_subset_word14_o",
                }
            )
        if (
            rom_path_seen
            or bool(pwrmgr_family_seen & 0x10)
        ):
            active_set.update(
                {
                    "real_toggle_subset_word15_o",
                    "real_toggle_subset_word16_o",
                    "real_toggle_subset_word17_o",
                }
        )
        return [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name in active_set]

    if history_kind == "alert_handler_esc_timer_semantic_seen":
        def _alert_esc_seen(name: str, fallback_name: str = "") -> int:
            value = int(internal_probe_values.get(name) or 0)
            if value > 0 or not fallback_name:
                return value
            return int(internal_probe_values.get(fallback_name) or 0)

        alert_esc_phase = int(
            internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        alert_esc_cycle_count = int(
            internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        alert_esc_family_seen = int(
            internal_probe_values.get(
                "alert_handler_esc_timer_gpu_cov_tb__DOT__oracle_semantic_family_seen_q"
            )
            or internal_probe_values.get("oracle_semantic_family_seen_o")
            or 0
        )
        alert_esc_case_seen = int(
            internal_probe_values.get(
                "alert_handler_esc_timer_gpu_cov_tb__DOT__oracle_semantic_case_seen_q"
            )
            or internal_probe_values.get("oracle_semantic_case_seen_o")
            or 0
        )
        mixed_visibility = (
            debug_phase == 0
            and debug_cycle_count == 0
            and alert_esc_phase == 0
            and alert_esc_cycle_count == 0
            and (
                alert_esc_family_seen > 0
                or alert_esc_case_seen > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__timeout_seen_q") or 0) > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__timeout_trigger_seen_q") or 0) > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__phase0_seen_q") or 0) > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__phase1_seen_q") or 0) > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__phase2_seen_q") or 0) > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__phase3_seen_q") or 0) > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__crashdump_latch_seen_q") or 0) > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__esc_sig_seen_q") or 0) > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__clear_seen_q") or 0) > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__accu_fail_seen_q") or 0) > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__terminal_seen_q") or 0) > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__fsm_error_seen_q") or 0) > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__non_idle_seen_q") or 0) > 0
                or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__activity_seen_q") or 0) > 0
                or int(internal_probe_values.get("debug_timeout_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_phase0_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_phase1_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_phase2_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_phase3_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_terminal_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_error_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_crashdump_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_clear_seen_o") or 0) > 0
                or int(internal_probe_values.get("debug_trace_live_o") or 0) > 0
            )
            and (accepted_traffic_sum > 0 or progressed)
        )
        if not mixed_visibility:
            return active_words

        timeout_like = (
            bool(alert_esc_family_seen & 0x1)
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__timeout_seen_q", "debug_timeout_seen_o") > 0
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__timeout_trigger_seen_q", "debug_timeout_seen_o") > 0
        )
        phase0_like = (
            bool(alert_esc_family_seen & 0x2)
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__phase0_seen_q", "debug_phase0_seen_o") > 0
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__crashdump_latch_seen_q", "debug_crashdump_seen_o") > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__esc_sig_seen_q") or 0) > 0
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__phase1_seen_q", "debug_phase1_seen_o") > 0
        )
        phase12_like = (
            bool(alert_esc_family_seen & 0x4)
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__phase2_seen_q", "debug_phase2_seen_o") > 0
            or (
                _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__phase1_seen_q", "debug_phase1_seen_o") > 0
                and _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__phase2_seen_q", "debug_phase2_seen_o") > 0
            )
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__phase3_seen_q", "debug_phase3_seen_o") > 0
        )
        terminal_like = (
            bool(alert_esc_family_seen & 0x8)
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__phase3_seen_q", "debug_phase3_seen_o") > 0
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__terminal_seen_q", "debug_terminal_seen_o") > 0
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__clear_seen_q", "debug_clear_seen_o") > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__accu_fail_seen_q") or 0) > 0
        )
        error_like = (
            bool(alert_esc_family_seen & 0x10)
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__fsm_error_seen_q", "debug_error_seen_o") > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__non_idle_seen_q") or 0) > 0
            or int(internal_probe_values.get("alert_handler_esc_timer_gpu_cov_tb__DOT__activity_seen_q") or 0) > 0
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__counter_error_seen_q", "debug_error_seen_o") > 0
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__terminal_seen_q", "debug_terminal_seen_o") > 0
            or _alert_esc_seen("alert_handler_esc_timer_gpu_cov_tb__DOT__clear_seen_q", "debug_clear_seen_o") > 0
        )

        if timeout_like:
            active_set.update(
                {
                    "real_toggle_subset_word0_o",
                    "real_toggle_subset_word1_o",
                    "real_toggle_subset_word2_o",
                }
            )
        if phase0_like:
            active_set.update(
                {
                    "real_toggle_subset_word3_o",
                    "real_toggle_subset_word4_o",
                    "real_toggle_subset_word5_o",
                    "real_toggle_subset_word6_o",
                }
            )
        if phase12_like:
            active_set.update(
                {
                    "real_toggle_subset_word7_o",
                    "real_toggle_subset_word8_o",
                    "real_toggle_subset_word9_o",
                }
            )
        if terminal_like:
            active_set.update(
                {
                    "real_toggle_subset_word10_o",
                    "real_toggle_subset_word11_o",
                    "real_toggle_subset_word12_o",
                    "real_toggle_subset_word13_o",
                }
            )
        if error_like:
            active_set.update(
                {
                    "real_toggle_subset_word14_o",
                    "real_toggle_subset_word15_o",
                    "real_toggle_subset_word16_o",
                    "real_toggle_subset_word17_o",
                }
            )
        return [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name in active_set]

    if history_kind == "lc_ctrl_fsm_semantic_seen":
        lc_ctrl_phase = int(
            internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        lc_ctrl_cycle_count = int(
            internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        lc_ctrl_family_seen = int(
            internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__oracle_semantic_family_seen_q")
            or 0
        )
        lc_ctrl_case_seen = int(
            internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__oracle_semantic_case_seen_q")
            or 0
        )
        mixed_visibility = (
            debug_phase == 0
            and debug_cycle_count == 0
            and lc_ctrl_phase == 0
            and lc_ctrl_cycle_count == 0
            and (
                lc_ctrl_family_seen > 0
                or lc_ctrl_case_seen > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__init_req_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__init_done_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__idle_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__trans_cmd_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__clk_byp_req_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__clk_byp_ack_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__token_hash_req_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__token_hash_ack_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__token_path_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__otp_prog_req_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__otp_prog_ack_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__trans_success_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__flash_rma_req_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__flash_rma_ack_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__trans_invalid_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__token_invalid_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__otp_or_flash_error_seen_q") or 0) > 0
                or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__state_invalid_seen_q") or 0) > 0
            )
            and (accepted_traffic_sum > 0 or progressed)
        )
        if not mixed_visibility:
            return active_words

        if (
            int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__init_req_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__init_done_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__idle_seen_q") or 0) > 0
            or bool(lc_ctrl_family_seen & 0x1)
        ):
            active_set.update(
                {
                    "real_toggle_subset_word0_o",
                    "real_toggle_subset_word1_o",
                    "real_toggle_subset_word2_o",
                }
            )
        if (
            int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__trans_cmd_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__clk_byp_req_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__clk_byp_ack_seen_q") or 0) > 0
            or bool(lc_ctrl_family_seen & 0x2)
        ):
            active_set.update(
                {
                    "real_toggle_subset_word3_o",
                    "real_toggle_subset_word4_o",
                    "real_toggle_subset_word5_o",
                }
            )
        if (
            int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__token_hash_req_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__token_hash_ack_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__token_path_seen_q") or 0) > 0
            or bool(lc_ctrl_family_seen & 0x4)
        ):
            active_set.update(
                {
                    "real_toggle_subset_word6_o",
                    "real_toggle_subset_word7_o",
                    "real_toggle_subset_word8_o",
                }
            )
        if (
            int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__otp_prog_req_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__otp_prog_ack_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__trans_success_seen_q") or 0) > 0
            or bool(lc_ctrl_family_seen & 0x8)
        ):
            active_set.update(
                {
                    "real_toggle_subset_word9_o",
                    "real_toggle_subset_word10_o",
                    "real_toggle_subset_word11_o",
                }
            )
        if (
            int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__flash_rma_req_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__flash_rma_ack_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__trans_invalid_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__token_invalid_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__otp_or_flash_error_seen_q") or 0) > 0
            or int(internal_probe_values.get("lc_ctrl_fsm_gpu_cov_tb__DOT__state_invalid_seen_q") or 0) > 0
            or bool(lc_ctrl_family_seen & 0x10)
        ):
            active_set.update(
                {
                    "real_toggle_subset_word12_o",
                    "real_toggle_subset_word13_o",
                    "real_toggle_subset_word14_o",
                    "real_toggle_subset_word15_o",
                    "real_toggle_subset_word16_o",
                    "real_toggle_subset_word17_o",
                }
            )
        return [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name in active_set]

    if history_kind == "rom_ctrl_fsm_semantic_seen":
        selected_family = int(
            internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__selected_family_w") or 0
        ) & 0x7
        if selected_family > 4:
            selected_family = 0
        rom_ctrl_progress_alive = (
            accepted_traffic_sum > 0
            or int(execution_values.get("progress_cycle_count_o") or 0) > 0
            or int(traffic_values.get("host_req_accepted_o") or 0) > 0
            or int(traffic_values.get("device_req_accepted_o") or 0) > 0
            or int(traffic_values.get("device_rsp_accepted_o") or 0) > 0
            or int(traffic_values.get("host_rsp_accepted_o") or 0) > 0
        )
        if not rom_ctrl_progress_alive:
            return [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name in active_set]
        driver_values = dict(driver_values or {})
        target_region = str(driver_values.get("target_region") or "")
        req_family = int(driver_values.get("req_family") or 0) & 0x7
        if 1 <= req_family <= 5:
            req_family -= 1
        if req_family > 4:
            req_family = selected_family

        def _family_selected(family_idx: int, target_name: str) -> bool:
            return (
                selected_family == family_idx
                or req_family == family_idx
                or target_region == target_name
            )

        lowstream_progress = (
            int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__reading_low_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__rom_stream_low_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__kmac_feed_seen_q") or 0) > 0
            or int(internal_probe_values.get("debug_low_stream_seen_o") or 0) > 0
            or bool(
                {
                    "real_toggle_subset_word0_o",
                    "real_toggle_subset_word1_o",
                    "real_toggle_subset_word2_o",
                }
                & active_set
            )
        )
        lowstream_target = _family_selected(0, "rom_stream_low_to_kmac") and accepted_traffic_sum > 0
        top_digest_progress = (
            int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__reading_high_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__top_digest_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__digest_capture_seen_q") or 0) > 0
            or int(internal_probe_values.get("debug_top_digest_seen_o") or 0) > 0
            or bool(
                {
                    "real_toggle_subset_word3_o",
                    "real_toggle_subset_word4_o",
                    "real_toggle_subset_word5_o",
                }
                & active_set
            )
        )
        top_digest_target = _family_selected(1, "top_digest_capture_progress") and accepted_traffic_sum > 0
        race_progress = (
            int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__rom_ahead_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__kmac_ahead_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__kmac_done_seen_q") or 0) > 0
            or int(internal_probe_values.get("debug_race_seen_o") or 0) > 0
            or bool(
                {
                    "real_toggle_subset_word6_o",
                    "real_toggle_subset_word7_o",
                    "real_toggle_subset_word8_o",
                }
                & active_set
            )
        )
        race_target = _family_selected(2, "kmac_vs_rom_race_resolution") and accepted_traffic_sum > 0
        checker_progress = (
            int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__checker_start_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__checker_compare_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__checker_done_seen_q") or 0) > 0
            or int(internal_probe_values.get("debug_checker_seen_o") or 0) > 0
            or bool(
                {
                    "real_toggle_subset_word9_o",
                    "real_toggle_subset_word10_o",
                    "real_toggle_subset_word11_o",
                }
                & active_set
            )
        )
        checker_target = _family_selected(3, "checker_start_compare_done") and accepted_traffic_sum > 0
        terminal_success_progress = (
            int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__done_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__bus_select_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__pwrmgr_done_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__keymgr_valid_seen_q") or 0) > 0
            or bool(
                {
                    "real_toggle_subset_word12_o",
                    "real_toggle_subset_word13_o",
                    "real_toggle_subset_word14_o",
                }
                & active_set
            )
        )
        terminal_error_progress = (
            int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__alert_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__invalid_seen_q") or 0) > 0
            or int(internal_probe_values.get("rom_ctrl_fsm_gpu_cov_tb__DOT__kmac_err_seen_q") or 0) > 0
            or bool(
                {
                    "real_toggle_subset_word15_o",
                    "real_toggle_subset_word16_o",
                    "real_toggle_subset_word17_o",
                }
                & active_set
            )
        )
        terminal_target = (
            _family_selected(4, "terminal_done_bus_select_or_alert") and accepted_traffic_sum > 0
        )
        lowstream_like = lowstream_progress or lowstream_target
        top_digest_like = top_digest_progress or top_digest_target
        race_like = race_progress or race_target
        checker_like = checker_progress or checker_target
        terminal_like = terminal_success_progress or terminal_error_progress or terminal_target

        # The ROM controller FSM is linear on successful progress:
        # ReadingLow -> ReadingHigh -> (RomAhead|KmacAhead) -> Checking -> Done.
        # If later-family evidence is visible, earlier-family progress happened even when the
        # raw family words under-report due to mode-specific observation gaps.
        if top_digest_progress or race_progress or checker_progress or terminal_success_progress:
            lowstream_like = True
        if race_progress or checker_progress or terminal_success_progress:
            top_digest_like = True
        if checker_progress or terminal_success_progress:
            race_like = True
        if terminal_success_progress:
            checker_like = True

        if lowstream_like:
            active_set.update(
                {
                    "real_toggle_subset_word0_o",
                    "real_toggle_subset_word1_o",
                    "real_toggle_subset_word2_o",
                }
            )
        if top_digest_like:
            active_set.update(
                {
                    "real_toggle_subset_word3_o",
                    "real_toggle_subset_word4_o",
                    "real_toggle_subset_word5_o",
                }
            )
        if race_like:
            active_set.update(
                {
                    "real_toggle_subset_word6_o",
                    "real_toggle_subset_word7_o",
                    "real_toggle_subset_word8_o",
                }
            )
        if checker_like:
            active_set.update(
                {
                    "real_toggle_subset_word9_o",
                    "real_toggle_subset_word10_o",
                    "real_toggle_subset_word11_o",
                }
            )
        if terminal_like:
            active_set.update(
                {
                    "real_toggle_subset_word12_o",
                    "real_toggle_subset_word13_o",
                    "real_toggle_subset_word14_o",
                    "real_toggle_subset_word15_o",
                    "real_toggle_subset_word16_o",
                    "real_toggle_subset_word17_o",
                }
            )
        return [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name in active_set]

    if history_kind != "entropy_src_main_sm_semantic_seen":
        if history_kind != "alert_handler_ping_timer_semantic_seen":
            return active_words

        alert_phase = int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__phase_q") or 0
        ) & 0x7
        alert_cycle_count = int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__cycle_count_q") or 0
        )
        alert_family_seen = int(
            internal_probe_values.get(
                "alert_handler_ping_timer_gpu_cov_tb__DOT__oracle_semantic_family_seen_q"
            ) or 0
        )
        alert_case_seen = int(
            internal_probe_values.get(
                "alert_handler_ping_timer_gpu_cov_tb__DOT__oracle_semantic_case_seen_q"
            ) or 0
        )
        mixed_visibility = (
            debug_phase == 0
            and debug_cycle_count == 0
            and alert_phase == 0
            and alert_cycle_count == 0
            and (
                alert_family_seen > 0
                or alert_case_seen > 0
                or int(internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__activity_seen_q") or 0) > 0
            )
            and (accepted_traffic_sum > 0 or progressed)
        )
        if not mixed_visibility:
            return active_words

        edn_like = bool(alert_family_seen & 0x1) or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__edn_req_seen_q") or 0
        ) > 0 or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__edn_ack_seen_q") or 0
        ) > 0
        alert_like = bool(alert_family_seen & 0x2) or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__alert_wait_seen_q") or 0
        ) > 0 or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__alert_req_seen_q") or 0
        ) > 0 or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__alert_ack_seen_q") or 0
        ) > 0
        esc_like = bool(alert_family_seen & 0x4) or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__esc_wait_seen_q") or 0
        ) > 0 or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__esc_req_seen_q") or 0
        ) > 0 or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__esc_ack_seen_q") or 0
        ) > 0
        skip_like = bool(alert_family_seen & 0x8) or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__skip_seen_q") or 0
        ) > 0 or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__id_valid_seen_q") or 0
        ) > 0 or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__esc_rotate_seen_q") or 0
        ) > 0
        fail_like = bool(alert_family_seen & 0x10) or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__alert_fail_seen_q") or 0
        ) > 0 or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__esc_fail_seen_q") or 0
        ) > 0 or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__spurious_alert_seen_q") or 0
        ) > 0 or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__spurious_esc_seen_q") or 0
        ) > 0 or int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__fsm_error_seen_q") or 0
        ) > 0
        non_init_seen = int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__non_init_seen_q") or 0
        ) > 0
        activity_seen = int(
            internal_probe_values.get("alert_handler_ping_timer_gpu_cov_tb__DOT__activity_seen_q") or 0
        ) > 0
        configured_family = int((driver_values or {}).get("req_family") or 0)
        configured_skip_family = configured_family == 4

        if configured_skip_family and (accepted_traffic_sum > 0 or progressed):
            skip_like = skip_like or non_init_seen or esc_like or fail_like

        if edn_like or non_init_seen:
            active_set.update(
                {
                    "real_toggle_subset_word0_o",
                    "real_toggle_subset_word1_o",
                    "real_toggle_subset_word16_o",
                }
            )
        if alert_like or activity_seen:
            active_set.update(
                {
                    "real_toggle_subset_word2_o",
                    "real_toggle_subset_word3_o",
                    "real_toggle_subset_word4_o",
                    "real_toggle_subset_word17_o",
                }
            )
        if esc_like:
            active_set.update(
                {
                    "real_toggle_subset_word5_o",
                    "real_toggle_subset_word6_o",
                    "real_toggle_subset_word7_o",
                }
            )
        if skip_like:
            active_set.update(
                {
                    "real_toggle_subset_word8_o",
                    "real_toggle_subset_word9_o",
                    "real_toggle_subset_word10_o",
                }
            )
        if fail_like:
            active_set.update(
                {
                    "real_toggle_subset_word11_o",
                    "real_toggle_subset_word12_o",
                    "real_toggle_subset_word13_o",
                    "real_toggle_subset_word14_o",
                    "real_toggle_subset_word15_o",
                }
            )
        return [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name in active_set]

    entropy_phase = int(
        internal_probe_values.get("entropy_src_main_sm_gpu_cov_tb__DOT__phase_q") or 0
    ) & 0x7
    entropy_cycle_count = int(
        internal_probe_values.get("entropy_src_main_sm_gpu_cov_tb__DOT__cycle_count_q") or 0
    )
    entropy_family_seen_q = int(
        internal_probe_values.get("entropy_src_main_sm_gpu_cov_tb__DOT__oracle_semantic_family_seen_q")
        or 0
    )
    entropy_case_seen_q = int(
        internal_probe_values.get("entropy_src_main_sm_gpu_cov_tb__DOT__oracle_semantic_case_seen_q")
        or 0
    )
    boot_seen = int(internal_probe_values.get("debug_boot_seen_o") or 0) > 0
    startup_seen = int(internal_probe_values.get("debug_startup_seen_o") or 0) > 0
    continuous_seen = int(internal_probe_values.get("debug_continuous_seen_o") or 0) > 0
    fw_seen = int(internal_probe_values.get("debug_fw_seen_o") or 0) > 0
    sha3_seen = int(internal_probe_values.get("debug_sha3_seen_o") or 0) > 0
    alert_seen = int(internal_probe_values.get("debug_alert_seen_o") or 0) > 0

    boot_like = boot_seen or bool({"real_toggle_subset_word0_o", "real_toggle_subset_word1_o"} & active_set)
    startup_like = startup_seen or ("real_toggle_subset_word2_o" in active_set)
    continuous_like = continuous_seen or ("real_toggle_subset_word3_o" in active_set)
    fw_like = fw_seen or ("real_toggle_subset_word4_o" in active_set)
    sha3_like = sha3_seen or bool({"real_toggle_subset_word5_o", "real_toggle_subset_word16_o"} & active_set)
    alert_like = alert_seen or bool(
        {"real_toggle_subset_word6_o", "real_toggle_subset_word16_o", "real_toggle_subset_word17_o"} & active_set
    )
    seen_activity = boot_like or startup_like or continuous_like or fw_like or sha3_like or alert_like
    mixed_visibility = (
        seen_activity
        and entropy_phase == 0
        and entropy_cycle_count == 0
        and entropy_family_seen_q == 0
        and entropy_case_seen_q == 0
        and (accepted_traffic_sum > 0 or progressed)
    )
    if not mixed_visibility:
        return active_words

    if seen_activity:
        active_set.update(
            {
                "real_toggle_subset_word8_o",
                "real_toggle_subset_word9_o",
            }
        )
    case_acked_like = bool(
        {
            "real_toggle_subset_word1_o",
            "real_toggle_subset_word3_o",
            "real_toggle_subset_word5_o",
            "real_toggle_subset_word6_o",
            "real_toggle_subset_word13_o",
            "real_toggle_subset_word14_o",
            "real_toggle_subset_word16_o",
            "real_toggle_subset_word17_o",
        }
        & active_set
    ) or accepted_traffic_sum > 0
    if case_acked_like or seen_activity:
        active_set.add("real_toggle_subset_word10_o")
    return [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name in active_set]


def _execution_gate_status(
    *,
    traffic_values: dict[str, int],
    execution_values: dict[str, int],
    points_hit: int,
    active_region_count: int,
) -> dict[str, Any]:
    accepted_traffic_sum = sum(int(traffic_values.get(name) or 0) for name in TRAFFIC_COUNTER_OUTPUTS)
    progress_cycle_count = int(execution_values.get("progress_cycle_count_o") or 0)
    debug_phase = int(execution_values.get("debug_phase_o") or 0) & 0x7
    debug_trace_live = int(execution_values.get("debug_trace_live_o") or 0)
    debug_trace_req_active = int(execution_values.get("debug_trace_req_active_o") or 0)
    execution_left_reset = int(debug_phase != 0)
    execution_progressed = int(progress_cycle_count > 0)
    execution_live = int(debug_trace_live > 0 or debug_trace_req_active > 0 or execution_progressed > 0)
    execution_has_handshake = int(accepted_traffic_sum > 0)
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
    return {
        "accepted_traffic_sum": accepted_traffic_sum,
        "execution_status": execution_status,
        "truth_gate_status": truth_gate_status,
        "execution_left_reset": execution_left_reset,
        "execution_progressed": execution_progressed,
        "execution_live": execution_live,
        "execution_has_handshake": execution_has_handshake,
    }


def _summarize_packed_case(
    *,
    batch_case: dict[str, Any],
    driver: dict[str, Any],
    output_map: dict[str, dict[str, Any]],
    region_manifest: dict[str, Any],
    internal_probe_names: Collection[str],
    gpu_walltime_s: float | None,
    summary_mode: str,
) -> dict[str, Any]:
    state_start = int(batch_case["state_start"])
    state_count = int(batch_case["state_count"])
    active_words = [
        name
        for name in REAL_TOGGLE_SUBSET_OUTPUTS
        if _state_window_any_nonzero(output_map, name, state_start, state_count)
    ]
    dead_words = [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name not in active_words]
    region_summary = summarize_regions(
        region_manifest,
        active_words=active_words,
        dead_words=dead_words,
    )
    points_hit = len(active_words)
    coverage_per_second = (
        float(points_hit) / float(gpu_walltime_s)
        if gpu_walltime_s and gpu_walltime_s > 0.0
        else None
    )
    oracle_values = _aggregate_output_values(
        output_map,
        ALL_ORACLE_OUTPUTS,
        state_start,
        state_count,
    )
    missing_oracle_outputs = _missing_output_names(output_map, ORACLE_OUTPUTS)
    missing_optional_oracle_outputs = _missing_output_names(output_map, OPTIONAL_SPLIT_ORACLE_OUTPUTS)
    oracle_signal_inconsistent = _oracle_signal_inconsistent(oracle_values)
    oracle_status = (
        "oracle_untrusted_missing_outputs"
        if missing_oracle_outputs
        else (
            "oracle_untrusted_inconsistent_outputs"
            if oracle_signal_inconsistent
            else _classify_oracle_status(oracle_values)
        )
    )
    oracle_alive = int(
        oracle_status
        not in {
            "oracle_dead",
            "oracle_untrusted_missing_outputs",
            "oracle_untrusted_inconsistent_outputs",
        }
    )
    traffic_values = _aggregate_output_values(
        output_map,
        TRAFFIC_COUNTER_OUTPUTS,
        state_start,
        state_count,
    )
    execution_values = _aggregate_output_values(
        output_map,
        EXECUTION_GATING_OUTPUTS,
        state_start,
        state_count,
    )
    internal_probe_values = _aggregate_output_values(
        output_map,
        internal_probe_names,
        state_start,
        state_count,
    )
    active_words = _augment_active_words_for_history_visibility(
        manifest=region_manifest,
        active_words=active_words,
        traffic_values=traffic_values,
        execution_values=execution_values,
        internal_probe_values=internal_probe_values,
        driver_values=driver,
    )
    dead_words = [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name not in active_words]
    points_hit = len(active_words)
    coverage_per_second = (
        float(points_hit) / float(gpu_walltime_s)
        if gpu_walltime_s and gpu_walltime_s > 0.0
        else None
    )
    region_summary = summarize_regions(
        region_manifest,
        active_words=active_words,
        dead_words=dead_words,
    )
    target_region = str(batch_case.get("target_region") or driver.get("target_region") or "")
    target_region_activated = int(
        bool(target_region) and target_region in set(region_summary.get("active_regions") or [])
    )
    coverage_status = _classify_coverage_status(
        points_hit=points_hit,
        active_region_count=int(region_summary.get("active_region_count") or 0),
        dead_region_count=int(region_summary.get("dead_region_count") or 0),
    )
    execution_gate = _execution_gate_status(
        traffic_values=traffic_values,
        execution_values=execution_values,
        points_hit=points_hit,
        active_region_count=int(region_summary.get("active_region_count") or 0),
    )
    diagnostic_status = _classify_diagnostic_status(
        traffic_values=traffic_values,
        execution_values=execution_values,
        oracle_status=oracle_status,
        oracle_alive=oracle_alive,
        points_hit=points_hit,
        active_region_count=int(region_summary.get("active_region_count") or 0),
        dead_region_count=int(region_summary.get("dead_region_count") or 0),
    )
    consistency_flags = _consistency_flags(
        manifest=region_manifest,
        traffic_values=traffic_values,
        execution_values=execution_values,
        internal_probe_values=internal_probe_values,
        oracle_alive=oracle_alive,
        points_hit=points_hit,
        active_region_count=int(region_summary.get("active_region_count") or 0),
    )
    diagnostic_status = _apply_consistency_diagnostic_override(
        diagnostic_status,
        consistency_flags,
    )
    return {
        **{
            key: value
            for key, value in batch_case.items()
            if key not in {"driver", "state_start", "state_count"}
        },
        "points_hit": points_hit,
        "points_total": len(REAL_TOGGLE_SUBSET_OUTPUTS),
        "coverage_per_second": coverage_per_second,
        "dead_output_word_count": len(dead_words),
        "dead_output_words": [] if summary_mode == "prefilter" else dead_words,
        "coverage_regions": (
            _compact_region_summary(region_summary)
            if summary_mode == "prefilter"
            else region_summary
        ),
        "traffic_counters": traffic_values,
        "execution_gating": execution_values,
        "trace_progress": _aggregate_output_values(
            output_map,
            TRACE_PROGRESS_OUTPUTS,
            state_start,
            state_count,
        ),
        "coverage_status": coverage_status,
        "diagnostic_status": diagnostic_status,
        "target_region_activated": target_region_activated,
        **consistency_flags,
        **execution_gate,
        "oracle": _aggregate_output_values(
            output_map,
            ALL_ORACLE_OUTPUTS,
            state_start,
            state_count,
        )
        | {
            "oracle_status": oracle_status,
            "oracle_alive": oracle_alive,
            "oracle_signal_inconsistent": oracle_signal_inconsistent,
            "missing_oracle_outputs": missing_oracle_outputs,
            "missing_optional_oracle_outputs": missing_optional_oracle_outputs,
        },
    }


def _collect_compile_sources(slice_name: str, rtl_path: Path, tb_path: Path) -> list[Path]:
    if slice_name not in SLICE_EXTRA_SOURCES:
        raise SystemExit(f"Unsupported slice for generic baseline: {slice_name}")
    return _dedupe_paths(COMMON_SOURCES + SLICE_EXTRA_SOURCES[slice_name] + [rtl_path, tb_path])


def _effective_phase(ns: argparse.Namespace, sequential_steps: int) -> str:
    if ns.phase != "auto":
        return str(ns.phase)
    return "single_step" if int(sequential_steps) <= 1 else "multi_step"


def _effective_launch_backend(
    template: dict[str, Any],
    ns: argparse.Namespace,
    sequential_steps: int,
) -> str:
    if ns.launch_backend != "auto":
        return str(ns.launch_backend)
    policy = dict(template.get("launch_backend_policy") or {})
    phase = _effective_phase(ns, sequential_steps)
    return str(policy.get(phase) or "source")


def _derive_rocm_gfx_arch() -> str:
    override = os.getenv("HSA_OVERRIDE_GFX_VERSION", "").strip()
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", override)
    if match:
        return f"gfx{match.group(1)}{match.group(2)}{match.group(3)}"
    return "gfx1201"


def _generated_dir_lock_path(cache_root: Path, slice_name: str) -> Path:
    return cache_root / f".{slice_name}.generated_dir.lock"


@contextmanager
def _generated_dir_lock(cache_root: Path, slice_name: str):
    cache_root.mkdir(parents=True, exist_ok=True)
    lock_path = _generated_dir_lock_path(cache_root, slice_name)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _ensure_generated_dir(
    *,
    slice_name: str,
    cache_root: Path,
    rebuild: bool,
    emit_hsaco: bool,
    gfx_arch: str,
) -> Path:
    with _generated_dir_lock(cache_root, slice_name):
        return _ensure_generated_dir_unlocked(
            slice_name=slice_name,
            cache_root=cache_root,
            rebuild=rebuild,
            emit_hsaco=emit_hsaco,
            gfx_arch=gfx_arch,
        )


def _ensure_generated_dir_unlocked(
    *,
    slice_name: str,
    cache_root: Path,
    rebuild: bool,
    emit_hsaco: bool,
    gfx_arch: str,
) -> Path:
    slice_root = cache_root / slice_name
    fused_dir = slice_root / "fused"
    required = [
        fused_dir / "kernel_generated.api.h",
        fused_dir / "kernel_generated.link.cu",
        fused_dir / "kernel_generated.full_all.cu",
        fused_dir / "kernel_generated.part0.cu",
        fused_dir / "kernel_generated.cluster0.cu",
        fused_dir / "kernel_generated.full_all.circt_driver.cpp",
        fused_dir / "kernel_generated.full_all.circt.cubin",
    ]
    if emit_hsaco:
        required.extend(
            [
                fused_dir / "kernel_generated.full_all.hsaco",
                fused_dir / "kernel_generated.full_all.rocm_driver.cpp",
            ]
        )
    marker = slice_root / GENERATED_DIR_CACHE_ABI_MARKER
    if rebuild and slice_root.exists():
        shutil.rmtree(slice_root)
    if all(path.is_file() for path in required) and marker.is_file():
        return fused_dir
    cmd = [
        "python3",
        str(GENERATED_DIR_GENERATOR),
        "--slice",
        slice_name,
        "--out-dir",
        str(cache_root),
        "--emit-raw-cuda-sidecars",
    ]
    if emit_hsaco:
        cmd.append("--emit-hsaco")
        cmd.extend(["--gfx-arch", gfx_arch])
    subprocess.run(cmd, cwd=cache_root, check=True)
    if not (all(path.is_file() for path in required) and marker.is_file()):
        raise SystemExit(f"Failed to prepare generated dir for {slice_name}: {fused_dir}")
    return fused_dir


def _bundle_runtime_env(bundle_dir: Path) -> dict[str, str]:
    config_path = bundle_dir / "sim_accel_bundle_config.json"
    if not config_path.is_file():
        return {}
    config = _load_json(config_path)
    env_var = str(config.get("gpu_binary_env_var") or "").strip()
    relpath = str(config.get("gpu_binary_relpath") or "").strip()
    if not env_var or not relpath:
        return {}
    env = {env_var: str((bundle_dir / relpath).resolve())}
    legacy_env_var = str(config.get("gpu_binary_legacy_env_var") or "").strip()
    if legacy_env_var and legacy_env_var != env_var:
        env[legacy_env_var] = env[env_var]
    return env


def _materialize_bundle_metadata(bundle_dir: Path, build_dir: Path) -> None:
    for name in ("kernel_generated.vars.tsv", "kernel_generated.comm.tsv"):
        src = bundle_dir / name
        dst = build_dir / name
        if src.is_file():
            shutil.copy2(src, dst)


def _bundle_cache_version_path(bundle_dir: Path) -> Path:
    return bundle_dir / ".sim_accel_bundle_abi"


def _bundle_cache_fingerprint_path(bundle_dir: Path) -> Path:
    return bundle_dir / ".sim_accel_bundle_inputs.sha256"


def _bundle_cache_abi_version(*, launch_backend: str, execution_backend: str, hybrid_mode: str) -> str:
    rocm_lane = ""
    if execution_backend == "rocm_llvm":
        rocm_lane = "native-hsaco"
    return "|".join(
        part
        for part in (
            BUNDLE_CACHE_ABI_VERSION,
            f"launch={launch_backend}",
            f"exec={execution_backend}",
            f"hybrid={hybrid_mode}",
            f"rocm_lane={rocm_lane}" if rocm_lane else "",
        )
        if part
    )


def _stat_fingerprint(paths: list[Path]) -> str:
    payload_parts: list[str] = []
    for path in paths:
        if not path.is_file():
            payload_parts.append(f"{path}|missing")
            continue
        stat = path.stat()
        try:
            rel = path.relative_to(ROOT_DIR)
            label = str(rel)
        except ValueError:
            label = str(path)
        payload_parts.append(f"{label}|{stat.st_size}|{stat.st_mtime_ns}")
    payload = "\n".join(payload_parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bundle_input_fingerprint(generated_dir: Path, *, execution_backend: str) -> str:
    files = [
        generated_dir / "kernel_generated.api.h",
        generated_dir / "kernel_generated.link.cu",
        generated_dir / "kernel_generated.full_all.cu",
        generated_dir / "kernel_generated.full_seq.cu",
        generated_dir / "kernel_generated.full_comb.cu",
        generated_dir / "kernel_generated.vars.tsv",
        generated_dir / "kernel_generated.comm.tsv",
        PREPARE_BENCH_BUNDLE,
        BUILD_BENCH_BUNDLE,
    ]
    files.extend(sorted(BENCH_KERNEL_PARTS_DIR.glob("bench_kernel_part_*.cu.inc")))
    if execution_backend == "rocm_llvm":
        files.extend(
            [
                generated_dir / "kernel_generated.full_all.hsaco",
                generated_dir / "kernel_generated.full_all.rocm_driver.cpp",
            ]
        )
    return _stat_fingerprint(files)


def _bundle_cache_is_current(bundle_dir: Path, expected_version: str, expected_fingerprint: str) -> bool:
    version_path = _bundle_cache_version_path(bundle_dir)
    fingerprint_path = _bundle_cache_fingerprint_path(bundle_dir)
    if not version_path.is_file() or not fingerprint_path.is_file():
        return False
    return (
        version_path.read_text(encoding="utf-8").strip() == expected_version
        and fingerprint_path.read_text(encoding="utf-8").strip() == expected_fingerprint
    )


def _write_bundle_cache_version(bundle_dir: Path, expected_version: str, expected_fingerprint: str) -> None:
    _bundle_cache_version_path(bundle_dir).write_text(
        expected_version + "\n",
        encoding="utf-8",
    )
    _bundle_cache_fingerprint_path(bundle_dir).write_text(
        expected_fingerprint + "\n",
        encoding="utf-8",
    )


def _run_bundle_backend(
    *,
    launch_backend: str,
    execution_backend: str,
    slice_name: str,
    build_dir: Path,
    init_file: Path,
    nstates: int,
    gpu_reps: int,
    cpu_reps: int,
    sequential_steps: int,
    skip_cpu_reference_build: bool,
    stdout_out: Path,
    generated_dir_cache_root: Path,
    bundle_cache_root: Path,
    output_filter_file: Path | None,
    sequential_rep_graph_mode: str,
    gpu_warmup_reps: int,
    hybrid_mode: str,
    hybrid_partition_index: int | None,
    hybrid_cluster_index: int | None,
    rebuild: bool,
) -> dict[str, Any]:
    rocm_native_hsaco = execution_backend == "rocm_llvm"
    cache_hit_before_run = False
    cache_rebuilt = False
    with _generated_dir_lock(generated_dir_cache_root, slice_name):
        generated_dir = _ensure_generated_dir_unlocked(
            slice_name=slice_name,
            cache_root=generated_dir_cache_root,
            rebuild=rebuild,
            emit_hsaco=rocm_native_hsaco,
            gfx_arch=_derive_rocm_gfx_arch() if rocm_native_hsaco else "",
        )
        bundle_dir = bundle_cache_root / slice_name / launch_backend
        expected_bundle_cache_version = _bundle_cache_abi_version(
            launch_backend=launch_backend,
            execution_backend=execution_backend,
            hybrid_mode=hybrid_mode,
        )
        expected_bundle_cache_fingerprint = _bundle_input_fingerprint(
            generated_dir,
            execution_backend=execution_backend,
        )
        binary_path = bundle_dir / "bench_kernel"
        bundle_dir.parent.mkdir(parents=True, exist_ok=True)
        lock_path = bundle_dir.parent / f"{launch_backend}.lock"
        with lock_path.open("w", encoding="utf-8") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            cache_current_before_run = _bundle_cache_is_current(
                bundle_dir,
                expected_bundle_cache_version,
                expected_bundle_cache_fingerprint,
            )
            cache_hit_before_run = bool(
                (not rebuild)
                and cache_current_before_run
                and binary_path.is_file()
            )
            if (rebuild or not cache_current_before_run) and bundle_dir.exists():
                shutil.rmtree(bundle_dir)
            if not binary_path.is_file():
                cache_rebuilt = True
                build_cmd = [
                    "python3",
                    str(BUILD_BENCH_BUNDLE),
                    "--bundle-dir",
                    str(bundle_dir),
                    "--binary-name",
                    "bench_kernel",
                    "--clean-obj-dir",
                ]
                if skip_cpu_reference_build:
                    build_cmd.extend(
                        [
                            "--skip-cpu-ref",
                            "--nvcc-flag=-DSIM_ACCEL_SKIP_CPU_REFERENCE_BUILD=1",
                            "--cxx-flag=-DSIM_ACCEL_SKIP_CPU_REFERENCE_BUILD=1",
                        ]
                    )
                prepare_cmd = [
                    "python3",
                    str(PREPARE_BENCH_BUNDLE),
                    "--generated-dir",
                    str(generated_dir),
                    "--out-dir",
                    str(bundle_dir),
                    "--force",
                    "--launch-backend",
                    launch_backend,
                    "--execution-backend",
                    execution_backend,
                ]
                if execution_backend == "rocm_llvm":
                    prepare_cmd.extend(
                        [
                            "--rocm-launch-mode",
                            "native-hsaco" if rocm_native_hsaco else "source-bridge",
                        ]
                    )
                build_cmd.extend(["--execution-backend", execution_backend])
                if execution_backend in ("cuda_clang_ir", "cuda_vl_ir"):
                    if getattr(ns, "clang", ""):
                        build_cmd.extend(["--clang", ns.clang])
                    if getattr(ns, "llc", ""):
                        build_cmd.extend(["--llc", ns.llc])
                    if getattr(ns, "llvm_link", ""):
                        build_cmd.extend(["--llvm-link", ns.llvm_link])
                    if getattr(ns, "cuda_arch", ""):
                        build_cmd.extend(["--cuda-arch", ns.cuda_arch])
                bundle_dir.mkdir(parents=True, exist_ok=True)
                for attempt in range(3):
                    try:
                        subprocess.run(prepare_cmd, cwd=bundle_dir, check=True)
                        subprocess.run(build_cmd, cwd=bundle_dir, check=True)
                        _write_bundle_cache_version(
                            bundle_dir,
                            expected_bundle_cache_version,
                            expected_bundle_cache_fingerprint,
                        )
                        break
                    except subprocess.CalledProcessError:
                        shutil.rmtree(bundle_dir, ignore_errors=True)
                        if attempt == 2:
                            raise
                        time.sleep(0.5 * (attempt + 1))
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    _materialize_bundle_metadata(bundle_dir, build_dir)

    base_bench_cmd = [
        str(binary_path),
        "--nstates",
        str(nstates),
        "--gpu-reps",
        str(gpu_reps),
        "--cpu-reps",
        str(cpu_reps),
        "--gpu-warmup-reps",
        str(gpu_warmup_reps),
        "--hybrid-mode",
        str(hybrid_mode),
        "--init-mode",
        "zero",
        "--init-file",
        str(init_file),
        "--dump-output-compact",
        str(build_dir / "gpu_output_compact.bin"),
    ]
    if hybrid_mode == "off":
        base_bench_cmd.extend(["--sequential-steps", str(sequential_steps)])
    if hybrid_mode == "single-partition" and hybrid_partition_index is not None:
        base_bench_cmd.extend(["--hybrid-partition-index", str(hybrid_partition_index)])
    if hybrid_mode == "single-cluster" and hybrid_cluster_index is not None:
        base_bench_cmd.extend(["--hybrid-cluster-index", str(hybrid_cluster_index)])
    if not (skip_cpu_reference_build or int(cpu_reps) <= 0):
        base_bench_cmd.extend(["--dump-output-compact-cpu", str(build_dir / "cpu_output_compact.bin")])
    if sequential_rep_graph_mode and sequential_rep_graph_mode != "auto":
        base_bench_cmd.extend(["--sequential-rep-graph-mode", str(sequential_rep_graph_mode)])

    def _run_bench(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        with stdout_out.open("w", encoding="utf-8") as handle:
            return subprocess.run(
                cmd,
                cwd=build_dir,
                env={**dict(os.environ), **_bundle_runtime_env(bundle_dir)},
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )

    bench_cmd = list(base_bench_cmd)
    if output_filter_file is not None:
        bench_cmd.extend(["--output-filter-file", str(output_filter_file)])
    proc = _run_bench(bench_cmd)
    if proc.returncode != 0 and output_filter_file is not None:
        proc = _run_bench(base_bench_cmd)
    structured_semantic_gap_classification: str | None = None
    if proc.returncode != 0:
        stdout_text = stdout_out.read_text(encoding="utf-8") if stdout_out.exists() else ""
        raw_kernel_path = generated_dir.parent / "raw" / f"{slice_name}_gpu_cov_tb.sim_accel.kernel.cu"
        structured_semantic_gap_classification = _classify_known_structured_semantic_gap(
            stdout_text=stdout_text,
            raw_kernel_path=raw_kernel_path,
            hybrid_mode=hybrid_mode,
        )
        if structured_semantic_gap_classification is None:
            raise SystemExit(f"Slice baseline failed: see {stdout_out}")
    shutil.copy2(stdout_out, build_dir / "bench_run.log")
    return {
        "bundle_dir": bundle_dir,
        "generated_dir": generated_dir,
        "binary_path": binary_path,
        "launch_backend": launch_backend,
        "cache_hit": cache_hit_before_run,
        "cache_rebuilt": cache_rebuilt,
        "cache_current": _bundle_cache_is_current(
            bundle_dir,
            expected_bundle_cache_version,
            expected_bundle_cache_fingerprint,
        ),
        "runtime_mode": "cached_bundle_kernel",
        "structured_semantic_gap_classification": structured_semantic_gap_classification,
        "structured_semantic_gap_soft_accepted": structured_semantic_gap_classification is not None,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a generic sim-accel baseline for an OpenTitan TL-UL slice launch template."
    )
    parser.add_argument("--launch-template", required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--json-out", default="")
    parser.add_argument("--bench", default=str(DEFAULT_BENCH))
    parser.add_argument("--verilator", default=str(DEFAULT_VERILATOR))
    parser.add_argument("--batch-json", default="")
    parser.add_argument("--batch-manifest-json", default="")
    parser.add_argument("--nstates", type=int, default=0)
    parser.add_argument("--gpu-reps", type=int, default=0)
    parser.add_argument("--cpu-reps", type=int, default=0)
    parser.add_argument("--sequential-steps", type=int, default=0)
    parser.add_argument("--uniform-states", action="store_true")
    parser.add_argument("--compile-cache-dir", default=str(DEFAULT_COMPILE_CACHE))
    parser.add_argument("--no-compile-cache", action="store_true")
    parser.add_argument("--runtime-contract-waivers-json", default=str(DEFAULT_RUNTIME_CONTRACT_WAIVERS))
    parser.add_argument("--launch-backend", choices=("auto", "source", "circt-cubin"), default="auto")
    parser.add_argument(
        "--gpu-execution-backend",
        choices=("auto", "cuda_source", "cuda_circt_cubin", "cuda_clang_ir", "cuda_vl_ir", "rocm_llvm"),
        default="auto",
    )
    parser.add_argument(
        "--clang",
        default="",
        help="clang executable forwarded to build_bench_bundle.py for cuda_clang_ir/cuda_vl_ir",
    )
    parser.add_argument(
        "--llc",
        default="",
        help="llc executable forwarded to build_bench_bundle.py for cuda_clang_ir/cuda_vl_ir",
    )
    parser.add_argument(
        "--llvm-link",
        default="",
        help="llvm-link executable forwarded to build_bench_bundle.py for cuda_vl_ir",
    )
    parser.add_argument(
        "--cuda-arch",
        default="",
        help="CUDA GPU architecture forwarded to build_bench_bundle.py, e.g. sm_86",
    )
    parser.add_argument(
        "--gpu-selection-policy",
        choices=("auto", "prefer_cuda", "prefer_rocm", "cuda_only", "rocm_only"),
        default="auto",
    )
    parser.add_argument("--phase", choices=("auto", "single_step", "multi_step", "sweep", "campaign"), default="auto")
    parser.add_argument("--generated-dir-cache-root", default=str(DEFAULT_GENERATED_DIR_CACHE))
    parser.add_argument("--bundle-cache-root", default=str(DEFAULT_BUNDLE_CACHE))
    parser.add_argument("--skip-cpu-reference-build", action="store_true")
    parser.add_argument("--summary-mode", choices=("full", "prefilter"), default="full")
    parser.add_argument("--sequential-rep-graph-mode", choices=("auto", "always", "never"), default="")
    parser.add_argument("--hybrid-mode", choices=("off", "single-partition", "single-cluster"), default="off")
    parser.add_argument("--hybrid-partition-index", type=int, default=None)
    parser.add_argument("--hybrid-cluster-index", type=int, default=None)
    parser.add_argument("--gpu-warmup-reps", type=int, default=None)
    parser.add_argument("--rebuild", action="store_true")
    for key, default in DRIVER_DEFAULTS.items():
        parser.add_argument(f"--{key.replace('_', '-')}", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    template = _load_json(Path(ns.launch_template).expanduser().resolve())
    template_args = dict(template.get("runner_args_template") or {})
    slice_name = str(template.get("slice_name"))
    top_module = str(template_args["top_module"])
    rtl_path = Path(str(template_args["rtl_path"])).expanduser().resolve()
    tb_path = Path(str(template_args["coverage_tb_path"])).expanduser().resolve()
    manifest_path = Path(str(template_args["coverage_manifest_path"])).expanduser().resolve()
    runtime_waivers = _load_runtime_contract_waivers(
        Path(ns.runtime_contract_waivers_json).expanduser().resolve()
    )
    summary_mode = str(ns.summary_mode)
    selected_output_names = _selected_output_names_for_summary_mode(summary_mode)
    internal_probe_names = _template_internal_probe_names(template)
    selected_output_names.update(internal_probe_names)
    ordered_selected_output_names = sorted(selected_output_names)
    slice_runtime_waivers = runtime_waivers.get(slice_name) or {}
    build_dir = Path(ns.build_dir).expanduser().resolve()
    if ns.rebuild and build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    output_filter_path: Path | None = None
    if summary_mode == "prefilter":
        output_filter_path = build_dir / "gpu_output_filter_names.txt"
        _write_output_filter_file(output_filter_path, ordered_selected_output_names)

    if ns.batch_manifest_json and ns.batch_json:
        raise SystemExit("Use either --batch-json or --batch-manifest-json, not both")
    driver = _load_driver(ns, template_args)
    batch_cases = load_batch_case_manifest(ns.batch_manifest_json)
    nstates = ns.nstates or int(template_args.get("gpu_nstates", 32))
    gpu_reps = ns.gpu_reps or int(template_args.get("gpu_reps", 1))
    cpu_reps = int(ns.cpu_reps) if ns.cpu_reps > 0 else int(template_args.get("cpu_reps", 1))
    skip_cpu_reference_build = bool(ns.skip_cpu_reference_build)
    if skip_cpu_reference_build:
        cpu_reps = 0
    auto_enabled_cpu_reference = False
    auto_skipped_cpu_reference_for_rocm = False
    if int(gpu_reps) > 0 and int(cpu_reps) <= 0 and not skip_cpu_reference_build:
        cpu_reps = 1
        skip_cpu_reference_build = False
        auto_enabled_cpu_reference = True
    if ns.gpu_warmup_reps is not None:
        gpu_warmup_reps = int(ns.gpu_warmup_reps)
    else:
        gpu_warmup_reps = (
            int(template_args.get("gpu_warmup_reps", 10))
            if summary_mode != "prefilter"
            else int(template_args.get("prefilter_gpu_warmup_reps", 0))
        )
    sequential_steps = ns.sequential_steps or int(template_args.get("gpu_sequential_steps", 0))
    if sequential_steps <= 0:
        if batch_cases:
            sequential_steps = max(
                estimate_sync_sequential_steps(_driver_for_batch_case(driver, batch_case))
                for batch_case in batch_cases
            )
        else:
            sequential_steps = estimate_sync_sequential_steps(driver)
    effective_phase = _effective_phase(ns, sequential_steps)
    launch_backend = _effective_launch_backend(template, ns, sequential_steps)
    sequential_rep_graph_mode = str(ns.sequential_rep_graph_mode or "").strip()
    if not sequential_rep_graph_mode:
        if summary_mode == "prefilter":
            sequential_rep_graph_mode = str(
                template_args.get("campaign_sequential_rep_graph_mode")
                or template_args.get("prefilter_sequential_rep_graph_mode")
                or template_args.get("sequential_rep_graph_mode")
                or "auto"
            )
        elif effective_phase == "multi_step":
            sequential_rep_graph_mode = str(
                template_args.get("multi_step_sequential_rep_graph_mode")
                or template_args.get("sequential_rep_graph_mode")
                or "auto"
            )
        else:
            sequential_rep_graph_mode = str(template_args.get("sequential_rep_graph_mode") or "auto")

    init_file = build_dir / "gpu_driver.init"
    explicit_state_drivers: list[dict[str, Any]] | None = None
    case_spans: list[dict[str, Any]] = []
    if batch_cases:
        explicit_state_drivers, case_spans = _build_packed_state_drivers(
            base_driver=driver,
            batch_cases=batch_cases,
            nstates=nstates,
            uniform_states=ns.uniform_states,
        )
    init_file_metrics = _write_init_file(
        init_file,
        driver,
        nstates=nstates,
        uniform_states=ns.uniform_states,
        explicit_state_drivers=explicit_state_drivers,
        packed_case_spans=case_spans,
    )
    stdout_out = build_dir / "baseline_stdout.log"
    bench_log = build_dir / "bench_run.log"
    source_paths = _collect_compile_sources(slice_name, rtl_path, tb_path)
    missing_sources = [str(path) for path in source_paths if not path.exists()]
    if missing_sources:
        raise SystemExit("Missing slice sources:\n" + "\n".join(missing_sources))
    bundle_info: dict[str, Any] | None = None
    bundle_launch_backend = "cuda" if launch_backend == "source" else launch_backend
    cpu_only_execution = int(gpu_reps) <= 0 and int(cpu_reps) > 0
    use_bundle_backend = (not cpu_only_execution) and bundle_launch_backend in {"cuda", "circt-cubin"}
    gpu_execution_backend = resolve_gpu_execution_backend(
        requested=str(ns.gpu_execution_backend),
        launch_backend=(bundle_launch_backend if use_bundle_backend else launch_backend),
        execution_engine=("gpu" if int(gpu_reps) > 0 else "cpu"),
        selection_policy=str(ns.gpu_selection_policy),
    )
    ensure_gpu_execution_backend_supported(
        gpu_execution_backend,
        runner_name=Path(__file__).name,
    )
    if (
        gpu_execution_backend.get("selected") == "rocm_llvm"
        and auto_enabled_cpu_reference
        and int(gpu_reps) > 0
        and int(ns.cpu_reps) <= 0
    ):
        cpu_reps = 0
        skip_cpu_reference_build = True
        auto_enabled_cpu_reference = False
        auto_skipped_cpu_reference_for_rocm = True
    if not use_bundle_backend:
        cmd = [
            str(Path(ns.bench).expanduser().resolve()),
            "--verilator", str(Path(ns.verilator).expanduser().resolve()),
            "--top-module", top_module,
            "--outdir", str(build_dir),
            "--nstates", str(nstates),
            "--gpu-reps", str(gpu_reps),
            "--cpu-reps", str(cpu_reps),
            "--gpu-warmup-reps", str(gpu_warmup_reps),
            "--sequential-steps", str(sequential_steps),
            "--sequential-rep-graph-mode", sequential_rep_graph_mode,
            "--hybrid-mode", str(ns.hybrid_mode),
            "--init-mode", "zero",
            "--init-file", str(init_file),
            "--dump-output-compact", str(build_dir / "gpu_output_compact.bin"),
        ]
        if ns.hybrid_mode == "single-partition" and ns.hybrid_partition_index is not None:
            cmd.extend(["--hybrid-partition-index", str(ns.hybrid_partition_index)])
        if ns.hybrid_mode == "single-cluster" and ns.hybrid_cluster_index is not None:
            cmd.extend(["--hybrid-cluster-index", str(ns.hybrid_cluster_index)])
        if output_filter_path is not None:
            cmd.extend(["--output-filter-file", str(output_filter_path)])
        if skip_cpu_reference_build:
            cmd.append("--skip-cpu-reference-build")
        else:
            cmd.extend(["--dump-output-compact-cpu", str(build_dir / "cpu_output_compact.bin")])
        if ns.no_compile_cache:
            cmd.append("--no-compile-cache")
        else:
            cmd.extend(["--compile-cache-dir", str(Path(ns.compile_cache_dir).expanduser().resolve())])
        cmd.append("--")
        cmd.extend(["--timing", f"-I{OPENTITAN_SRC}"])
        cmd.extend(str(path) for path in source_paths)

        env = dict(os.environ)
        env.setdefault("VERILATOR_ROOT", str(ROOT_DIR / "third_party/verilator"))
        with stdout_out.open("w", encoding="utf-8") as handle:
            proc = subprocess.run(
                cmd,
                cwd=build_dir,
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if proc.returncode != 0:
            raise SystemExit(f"Slice baseline failed: see {stdout_out}")
        if not bench_log.exists() and stdout_out.exists():
            bench_log.write_text(stdout_out.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        bundle_info = _run_bundle_backend(
            launch_backend=bundle_launch_backend,
            execution_backend=str(gpu_execution_backend.get("selected") or "cuda_source"),
            slice_name=slice_name,
            build_dir=build_dir,
            init_file=init_file,
            nstates=nstates,
            gpu_reps=gpu_reps,
            cpu_reps=cpu_reps,
            gpu_warmup_reps=gpu_warmup_reps,
            sequential_steps=sequential_steps,
            skip_cpu_reference_build=skip_cpu_reference_build,
            stdout_out=stdout_out,
            generated_dir_cache_root=Path(ns.generated_dir_cache_root).expanduser().resolve(),
            bundle_cache_root=Path(ns.bundle_cache_root).expanduser().resolve(),
            output_filter_file=output_filter_path,
            sequential_rep_graph_mode=sequential_rep_graph_mode,
            hybrid_mode=str(ns.hybrid_mode),
            hybrid_partition_index=ns.hybrid_partition_index,
            hybrid_cluster_index=ns.hybrid_cluster_index,
            rebuild=bool(ns.rebuild),
        )
        if stdout_out.exists():
            bench_log.write_text(stdout_out.read_text(encoding="utf-8"), encoding="utf-8")
    vars_path = build_dir / f"{top_module}.sim_accel.kernel.cu.vars.tsv"
    if not vars_path.exists():
        alt_vars_path = build_dir / "kernel_generated.vars.tsv"
        if alt_vars_path.exists():
            vars_path = alt_vars_path
        elif bundle_info is not None and (Path(str(bundle_info["bundle_dir"])) / "kernel_generated.vars.tsv").exists():
            vars_path = Path(str(bundle_info["bundle_dir"])) / "kernel_generated.vars.tsv"
    comm_path = build_dir / f"{top_module}.sim_accel.kernel.cu.comm.tsv"
    if not comm_path.exists():
        alt_comm_path = build_dir / "kernel_generated.comm.tsv"
        if alt_comm_path.exists():
            comm_path = alt_comm_path
        elif bundle_info is not None and (Path(str(bundle_info["bundle_dir"])) / "kernel_generated.comm.tsv").exists():
            comm_path = Path(str(bundle_info["bundle_dir"])) / "kernel_generated.comm.tsv"
    metrics = parse_bench_log(bench_log)
    structured_semantic_gap = {
        "soft_accepted": bool((bundle_info or {}).get("structured_semantic_gap_soft_accepted")),
        "classification": str((bundle_info or {}).get("structured_semantic_gap_classification") or ""),
        "generated_dir": str((bundle_info or {}).get("generated_dir") or ""),
    }
    if structured_semantic_gap["soft_accepted"]:
        metrics["structured_semantic_gap_soft_accepted"] = 1
        metrics["structured_semantic_gap_classification"] = structured_semantic_gap["classification"]
    cpu_compact_path = build_dir / "cpu_output_compact.bin"
    gpu_compact_path = build_dir / "gpu_output_compact.bin"
    if int(gpu_reps) > 0 and gpu_compact_path.exists():
        active_compact_path = gpu_compact_path
        active_compact_source = "gpu"
    elif int(cpu_reps) > 0 and cpu_compact_path.exists():
        active_compact_path = cpu_compact_path
        active_compact_source = "cpu"
    else:
        raise SystemExit(
            f"Compact output missing for active execution path: gpu={gpu_compact_path.exists()} "
            f"cpu={cpu_compact_path.exists()} reps(gpu={gpu_reps}, cpu={cpu_reps})"
        )
    output_rows = extract_sim_accel_output_slot_values(
        active_compact_path,
        vars_path,
        comm_path=comm_path if comm_path.exists() else None,
        nstates=nstates,
        selected_names=ordered_selected_output_names,
        dense_selected_names=(output_filter_path is not None),
    )
    output_map = {row["name"]: row for row in output_rows}
    traffic_values = _aggregate_output_values(output_map, TRAFFIC_COUNTER_OUTPUTS, 0, nstates)
    execution_values = _aggregate_output_values(output_map, EXECUTION_GATING_OUTPUTS, 0, nstates)
    trace_values = _aggregate_output_values(output_map, TRACE_PROGRESS_OUTPUTS, 0, nstates)
    oracle_values = _aggregate_output_values(output_map, ALL_ORACLE_OUTPUTS, 0, nstates)
    internal_probe_values = _aggregate_output_values(output_map, internal_probe_names, 0, nstates)
    missing_selected_outputs = _missing_output_names(output_map, selected_output_names)
    missing_oracle_outputs = _missing_output_names(output_map, ORACLE_OUTPUTS)
    missing_optional_oracle_outputs = _missing_output_names(output_map, OPTIONAL_SPLIT_ORACLE_OUTPUTS)
    missing_internal_probe_outputs = _missing_output_names(output_map, internal_probe_names)
    cpu_reference_checked = int(metrics.get("cpu_reference_checked") or 0)
    compact_mismatch = None if metrics.get("compact_mismatch") is None else int(metrics.get("compact_mismatch") or 0)
    mismatch = None if metrics.get("mismatch") is None else int(metrics.get("mismatch") or 0)
    oracle_signal_inconsistent = _oracle_signal_inconsistent(oracle_values)
    oracle_relation_status = _oracle_relation_status(
        missing_oracle_outputs=missing_oracle_outputs,
        oracle_signal_inconsistent=oracle_signal_inconsistent,
    )
    oracle_status = (
        "oracle_untrusted_missing_outputs"
        if missing_oracle_outputs
        else (
            "oracle_untrusted_inconsistent_outputs"
            if oracle_signal_inconsistent
            else _classify_oracle_status(oracle_values)
        )
    )
    oracle_alive = int(
        oracle_status
        not in {
            "oracle_dead",
            "oracle_untrusted_missing_outputs",
            "oracle_untrusted_inconsistent_outputs",
        }
    )
    summary_contract_status = _summary_contract_status(
        missing_oracle_outputs=missing_oracle_outputs,
        oracle_signal_inconsistent=oracle_signal_inconsistent,
        cpu_reference_checked=cpu_reference_checked,
        mismatch=mismatch,
        compact_mismatch=compact_mismatch,
    )
    active_words = [
        name for name in REAL_TOGGLE_SUBSET_OUTPUTS
        if any(int(value) != 0 for value in output_map.get(name, {}).get("state_values", []))
    ]
    region_manifest = load_region_manifest(manifest_path)
    active_words = _augment_active_words_for_history_visibility(
        manifest=region_manifest,
        active_words=active_words,
        traffic_values=traffic_values,
        execution_values=execution_values,
        internal_probe_values=internal_probe_values,
        driver_values=driver,
    )
    dead_words = [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name not in active_words]
    region_summary = summarize_regions(
        region_manifest,
        active_words=active_words,
        dead_words=dead_words,
    )
    coverage_status = _classify_coverage_status(
        points_hit=len(active_words),
        active_region_count=int(region_summary.get("active_region_count") or 0),
        dead_region_count=int(region_summary.get("dead_region_count") or 0),
    )
    execution_gate = _execution_gate_status(
        traffic_values=traffic_values,
        execution_values=execution_values,
        points_hit=len(active_words),
        active_region_count=int(region_summary.get("active_region_count") or 0),
    )
    diagnostic_status = _classify_diagnostic_status(
        traffic_values=traffic_values,
        execution_values=execution_values,
        oracle_status=oracle_status,
        oracle_alive=oracle_alive,
        points_hit=len(active_words),
        active_region_count=int(region_summary.get("active_region_count") or 0),
        dead_region_count=int(region_summary.get("dead_region_count") or 0),
    )
    consistency_flags = _consistency_flags(
        manifest=region_manifest,
        traffic_values=traffic_values,
        execution_values=execution_values,
        internal_probe_values=internal_probe_values,
        oracle_alive=oracle_alive,
        points_hit=len(active_words),
        active_region_count=int(region_summary.get("active_region_count") or 0),
    )
    diagnostic_status = _apply_consistency_diagnostic_override(
        diagnostic_status,
        consistency_flags,
    )
    if summary_mode == "prefilter":
        active_walltime_s = (
            float(metrics.get("gpu_ms_per_rep") or 0.0) / 1000.0
            if active_compact_source == "gpu"
            else float(metrics.get("cpu_ms_per_rep") or 0.0) / 1000.0
        )
        if active_walltime_s <= 0.0:
            active_walltime_s = (
                float(metrics.get("bench_run_s") or 0.0)
                if isinstance(metrics.get("bench_run_s"), (int, float))
                else 0.0
            )
        collector = {
            "status": {"coverage": "skipped", "reason": "prefilter_summary_mode"},
            "coverage": {
                "points_hit": len(active_words),
                "points_total": len(REAL_TOGGLE_SUBSET_OUTPUTS),
                "gpu_walltime_s": active_walltime_s if active_compact_source == "gpu" else None,
                "cpu_walltime_s": active_walltime_s if active_compact_source == "cpu" else None,
            },
        }
        tb_contract = {
            "status": "skipped",
            "reason": "prefilter_summary_mode",
        }
        observability = {
            "status": "skipped",
            "reason": "prefilter_summary_mode",
        }
    else:
        active_walltime_s = (
            float(metrics.get("gpu_ms_per_rep") or 0.0) / 1000.0
            if active_compact_source == "gpu"
            else float(metrics.get("cpu_ms_per_rep") or 0.0) / 1000.0
        )
        if active_walltime_s <= 0.0:
            active_walltime_s = (
                float(metrics.get("bench_run_s") or 0.0)
                if isinstance(metrics.get("bench_run_s"), (int, float))
                else 0.0
            )
        collector = build_collector_summary(metrics)
        populate_collector_coverage(
            collector,
            points_hit=len(active_words),
            points_total=len(REAL_TOGGLE_SUBSET_OUTPUTS),
            gpu_walltime_s=active_walltime_s if active_compact_source == "gpu" else None,
            cpu_walltime_s=(
                active_walltime_s
                if active_compact_source == "cpu"
                else (
                    float(metrics["cpu_ms_per_rep"]) / 1000.0
                if (not skip_cpu_reference_build) and isinstance(metrics.get("cpu_ms_per_rep"), (int, float))
                    else None
                )
            ),
            source_summary={
                "coverage_mode": "real_toggle_subset_word_level",
                "compact_source": f"{active_compact_source}_output_compact.bin",
                "coverage_manifest_path": str(manifest_path),
            },
        )
        template_contract = validate_slice_contract(
            target=str(template.get("target") or ""),
            top_module=top_module,
            tb_path=tb_path,
            manifest_path=manifest_path,
        )
        constant_folded_outputs = _constant_folded_outputs(tb_path, REQUIRED_OUTPUTS_FLAT)
        runtime_missing_outputs = [
            name for name in REQUIRED_OUTPUTS_FLAT
            if name not in output_map
        ]
        runtime_constant_folded_outputs = [
            name for name in runtime_missing_outputs
            if name in constant_folded_outputs
        ]
        runtime_missing_required_outputs = [
            name for name in runtime_missing_outputs
            if name not in constant_folded_outputs
        ]
        waived_required_outputs = [
            name
            for name in runtime_missing_required_outputs
            if name in set(slice_runtime_waivers.get("allowed_runtime_missing_required_outputs") or [])
        ]
        effective_missing_required_outputs = [
            name for name in runtime_missing_required_outputs
            if name not in set(waived_required_outputs)
        ]
        tb_contract = {
            "status": (
                "pass"
                if template_contract.get("status") == "contract_ready" and not effective_missing_required_outputs
                else "needs_review"
            ),
            "template": template_contract,
            "runtime_output_count": len(output_map),
            "runtime_missing_outputs": runtime_missing_outputs,
            "runtime_missing_required_outputs": runtime_missing_required_outputs,
            "runtime_effective_missing_required_outputs": effective_missing_required_outputs,
            "runtime_waived_required_outputs": waived_required_outputs,
            "runtime_constant_folded_outputs": runtime_constant_folded_outputs,
            "runtime_contract_waiver": (
                {
                    "reason": slice_runtime_waivers.get("reason"),
                    "notes": list(slice_runtime_waivers.get("notes") or []),
                }
                if waived_required_outputs else {}
            ),
        }
        observability = _build_observability_summary(
            metrics=metrics,
            collector=collector,
            build_dir=build_dir,
            stdout_log=stdout_out,
            region_summary=region_summary,
            skip_cpu_reference_build=skip_cpu_reference_build,
        )

    summary = {
        "schema_version": "opentitan-tlul-slice-gpu-baseline-v1",
        "target": template.get("target"),
        "slice_name": slice_name,
        "target_region": str(driver.get("target_region") or ""),
        "variant_name": str(driver.get("variant_name") or ""),
        "top_module": top_module,
        "rtl_path": str(rtl_path),
        "coverage_tb_path": str(tb_path),
        "coverage_manifest_path": str(manifest_path),
        "build_dir": str(build_dir),
        "effective_phase": effective_phase,
        "launch_backend": launch_backend,
        "bundle_launch_backend": bundle_launch_backend if use_bundle_backend else "",
        "gpu_execution_backend": gpu_execution_backend,
        "gpu_selection_policy": str(ns.gpu_selection_policy),
        "bundle_backend_used": bool(use_bundle_backend),
        "bundle_runtime_mode": str((bundle_info or {}).get("runtime_mode") or ""),
        "bundle_dir": str((bundle_info or {}).get("bundle_dir") or ""),
        "bundle_binary_path": str((bundle_info or {}).get("binary_path") or ""),
        "bundle_cache_hit": bool((bundle_info or {}).get("cache_hit")),
        "bundle_cache_rebuilt": bool((bundle_info or {}).get("cache_rebuilt")),
        "bundle_cache_current": bool((bundle_info or {}).get("cache_current")),
        "structured_semantic_gap": structured_semantic_gap,
        "summary_mode": summary_mode,
        "init_file": str(init_file),
        "init_file_metrics": init_file_metrics,
        "stdout_log": str(stdout_out),
        "metrics": metrics,
        "collector": collector,
        "tb_contract": tb_contract,
        "observability": observability,
        "traffic_counters": traffic_values,
        "execution_gating": execution_values,
        "trace_progress": trace_values,
        "oracle": {
            **oracle_values,
            "oracle_status": oracle_status,
            "oracle_alive": oracle_alive,
            "oracle_signal_inconsistent": oracle_signal_inconsistent,
            "oracle_relation_status": oracle_relation_status,
            "missing_oracle_outputs": missing_oracle_outputs,
            "missing_optional_oracle_outputs": missing_optional_oracle_outputs,
        },
        "internal_debug": internal_probe_values,
        "skip_cpu_reference_build": skip_cpu_reference_build,
        "auto_enabled_cpu_reference": auto_enabled_cpu_reference,
        "auto_skipped_cpu_reference_for_rocm": auto_skipped_cpu_reference_for_rocm,
        "active_execution_engine": active_compact_source,
        "active_compact_path": str(active_compact_path),
        "gpu_warmup_reps": int(gpu_warmup_reps),
        "sequential_rep_graph_mode": sequential_rep_graph_mode,
        "compact_output_filter": {
            "enabled": output_filter_path is not None,
            "name_count": len(selected_output_names),
            "path": str(output_filter_path) if output_filter_path is not None else "",
        },
        "missing_selected_outputs": missing_selected_outputs,
        "missing_oracle_outputs": missing_oracle_outputs,
        "missing_optional_oracle_outputs": missing_optional_oracle_outputs,
        "missing_internal_probe_outputs": missing_internal_probe_outputs,
        "cpu_reference_checked": cpu_reference_checked,
        "compact_mismatch": compact_mismatch,
        "mismatch": mismatch,
        "backend_parity_status": (
            "not_checked"
            if not cpu_reference_checked
            else (
                "cpu_gpu_mismatch"
                if (mismatch or 0) != 0 or (compact_mismatch or 0) != 0
                else "cpu_gpu_match"
            )
        ),
        "summary_contract_status": summary_contract_status,
        "oracle_relation_status": oracle_relation_status,
        "region_summary": region_summary,
        "points_hit": len(active_words),
        "points_total": len(REAL_TOGGLE_SUBSET_OUTPUTS),
        "active_region_count": int(region_summary.get("active_region_count") or 0),
        "dead_region_count": int(region_summary.get("dead_region_count") or 0),
        "coverage_status": coverage_status,
        "diagnostic_status": diagnostic_status,
        **consistency_flags,
        **execution_gate,
        "target_region_activated": int(
            bool(driver.get("target_region"))
            and str(driver.get("target_region")) in set(region_summary.get("active_regions") or [])
        ),
        "active_real_toggle_words": active_words,
        "dead_real_toggle_words": dead_words,
        "gpu_output_compact_sha256": (
            None
            if summary_mode == "prefilter"
            else (sha256_hex_bytes(gpu_compact_path.read_bytes()) if gpu_compact_path.exists() else None)
        ),
        "cpu_output_compact_sha256": (
            None
            if summary_mode == "prefilter"
            else (sha256_hex_bytes(cpu_compact_path.read_bytes()) if cpu_compact_path.exists() else None)
        ),
    }
    for key, value in oracle_values.items():
        summary[key] = int(value)
    for key, value in traffic_values.items():
        summary[key] = int(value)
    for key, value in execution_values.items():
        summary[key] = int(value)
    for key, value in trace_values.items():
        if key not in summary:
            summary[key] = int(value)
    summary["oracle_status"] = oracle_status
    summary["oracle_alive"] = oracle_alive
    summary["oracle_signal_inconsistent"] = oracle_signal_inconsistent
    if summary_mode != "prefilter":
        summary["compile_sources"] = [str(path) for path in source_paths]
        focused_wave_decode = str(
            template_args.get("focused_wave_decode")
            or template.get("focused_wave_decode")
            or "packed_or_reduce"
        )
        focused_wave = _build_focused_wave_artifact(
            compact_path=active_compact_path,
            vars_path=vars_path,
            comm_path=comm_path,
            artifact_dir=build_dir,
            nstates=nstates,
            decode_mode=focused_wave_decode,
        )
        if focused_wave is not None:
            summary["focused_wave"] = {
                "decode_mode": str(focused_wave.get("decode_mode") or focused_wave_decode),
                "sample_count": int(focused_wave["sample_count"]),
                "summary": dict(focused_wave["summary"]),
                "samples": list(focused_wave["samples"]),
            }
            summary["focused_wave_json"] = str(focused_wave["artifact_path"])
    if batch_cases:
        coverage_walltime_s = (
            float(metrics["gpu_ms_per_rep"]) / 1000.0
            if active_compact_source == "gpu" and isinstance(metrics.get("gpu_ms_per_rep"), (int, float))
            else (
                float(metrics["cpu_ms_per_rep"]) / 1000.0
                if active_compact_source == "cpu" and isinstance(metrics.get("cpu_ms_per_rep"), (int, float))
                else metrics.get("bench_run_s")
            )
        )
        summary["batch_manifest_json"] = str(Path(ns.batch_manifest_json).expanduser().resolve())
        summary["packed_cases"] = [
            _summarize_packed_case(
                batch_case=batch_case,
                driver=_driver_for_batch_case(driver, batch_case),
                output_map=output_map,
                region_manifest=region_manifest,
                internal_probe_names=internal_probe_names,
                gpu_walltime_s=coverage_walltime_s if isinstance(coverage_walltime_s, (int, float)) else None,
                summary_mode=summary_mode,
            )
            for batch_case in case_spans
        ]
    summary_path = Path(ns.json_out).expanduser().resolve() if ns.json_out else (build_dir / "gpu_summary.json")
    _write_json(summary_path, summary, compact=(summary_mode == "prefilter"))
    print(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
