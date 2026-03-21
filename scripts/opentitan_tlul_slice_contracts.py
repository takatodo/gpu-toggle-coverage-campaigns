#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


REQUIRED_CORE_INPUTS = [
    "cfg_valid_i",
    "cfg_batch_length_i",
    "cfg_req_valid_pct_i",
    "cfg_rsp_valid_pct_i",
    "cfg_host_d_ready_pct_i",
    "cfg_device_a_ready_pct_i",
    "cfg_put_full_pct_i",
    "cfg_put_partial_pct_i",
    "cfg_req_fill_target_i",
    "cfg_req_burst_len_max_i",
    "cfg_req_family_i",
    "cfg_req_address_mode_i",
    "cfg_req_data_mode_i",
    "cfg_req_data_hi_xor_i",
    "cfg_access_ack_data_pct_i",
    "cfg_rsp_error_pct_i",
    "cfg_rsp_fill_target_i",
    "cfg_rsp_delay_max_i",
    "cfg_rsp_family_i",
    "cfg_rsp_delay_mode_i",
    "cfg_rsp_data_mode_i",
    "cfg_rsp_data_hi_xor_i",
    "cfg_reset_cycles_i",
    "cfg_drain_cycles_i",
    "cfg_seed_i",
    "cfg_address_base_i",
    "cfg_address_mask_i",
    "cfg_source_mask_i",
]
REQUIRED_REAL_TOGGLE_OUTPUTS = [f"real_toggle_subset_word{i}_o" for i in range(18)]
REQUIRED_TOGGLE_BITMAP_OUTPUTS = [f"toggle_bitmap_word{i}_o" for i in range(3)]
REQUIRED_FOCUSED_WAVE_OUTPUTS = [f"focused_wave_word{i}_o" for i in range(8)]
REQUIRED_BASE_OUTPUTS = [
    "cfg_signature_o",
    "done_o",
    "host_req_accepted_o",
    "device_req_accepted_o",
    "device_rsp_accepted_o",
    "host_rsp_accepted_o",
    "rsp_queue_overflow_o",
    "progress_cycle_count_o",
    "progress_signature_o",
]
REQUIRED_OUTPUT_GROUPS = {
    "base": REQUIRED_BASE_OUTPUTS,
    "toggle_bitmap": REQUIRED_TOGGLE_BITMAP_OUTPUTS,
    "real_toggle_subset": REQUIRED_REAL_TOGGLE_OUTPUTS,
    "focused_wave": REQUIRED_FOCUSED_WAVE_OUTPUTS,
}
REQUIRED_OUTPUTS_FLAT = [
    name
    for group in REQUIRED_OUTPUT_GROUPS.values()
    for name in group
]
REQUIRED_SEMANTIC_OUTPUTS = [
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
SEMANTIC_CONTRACT_TARGET_SUFFIXES = (
    "tlul_sink",
    "edn_main_sm",
    "csrng_main_sm",
    "aes_cipher_control",
    "entropy_src_main_sm",
    "alert_handler_ping_timer",
    "pwrmgr_fsm",
)
EXPECTED_COVERAGE_DOMAIN = "toggle_real_subset_bitmap"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_sv_ports(tb_path: Path, direction: str) -> list[str]:
    text = tb_path.read_text(encoding="utf-8")
    return sorted(set(re.findall(
        rf"\b{direction}\s+logic(?:\s*\[[^\]]+\])?\s+([A-Za-z_][A-Za-z0-9_$]*)",
        text,
    )))


def parse_sv_input_ports(tb_path: Path) -> list[str]:
    return _parse_sv_ports(tb_path, "input")


def parse_sv_output_ports(tb_path: Path) -> list[str]:
    return _parse_sv_ports(tb_path, "output")


def _manifest_words(manifest: dict[str, Any]) -> list[str]:
    words: list[str] = []
    for region in list(manifest.get("regions") or []):
        for word in list(dict(region).get("words") or []):
            text = str(word)
            if text not in words:
                words.append(text)
    return words


def _semantic_contract_expected(*, target: str, manifest_payload: dict[str, Any]) -> bool:
    if any(target.endswith(suffix) for suffix in SEMANTIC_CONTRACT_TARGET_SUFFIXES):
        return True
    return bool(dict(manifest_payload.get("history_visibility_contract") or {}).get("kind"))


def validate_slice_contract(
    *,
    target: str,
    top_module: str,
    tb_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    issues: list[str] = []
    notes: list[str] = []
    inputs: list[str] = []
    outputs: list[str] = []
    manifest_payload: dict[str, Any] = {}
    manifest_words: list[str] = []

    if not tb_path.exists():
        issues.append(f"coverage_tb_missing:{tb_path}")
    else:
        inputs = parse_sv_input_ports(tb_path)
        outputs = parse_sv_output_ports(tb_path)

    if not manifest_path.exists():
        issues.append(f"coverage_manifest_missing:{manifest_path}")
    else:
        try:
            manifest_payload = _load_json(manifest_path)
            manifest_words = _manifest_words(manifest_payload)
        except Exception as exc:
            issues.append(f"coverage_manifest_invalid:{exc}")

    inputs_set = set(inputs)
    outputs_set = set(outputs)
    missing_inputs = [name for name in REQUIRED_CORE_INPUTS if name not in inputs_set]
    missing_by_group = {
        group: [name for name in names if name not in outputs_set]
        for group, names in REQUIRED_OUTPUT_GROUPS.items()
    }
    missing_outputs = [name for names in missing_by_group.values() for name in names]
    semantic_expected = _semantic_contract_expected(
        target=target,
        manifest_payload=manifest_payload,
    )
    semantic_missing_outputs = [
        name for name in REQUIRED_SEMANTIC_OUTPUTS
        if name not in outputs_set
    ]

    top_module_matches_tb = tb_path.stem == top_module if tb_path.exists() else False
    if tb_path.exists() and not top_module_matches_tb:
        issues.append(f"top_module_mismatch:{top_module}!={tb_path.stem}")

    manifest_target = str(manifest_payload.get("target") or "")
    manifest_target_matches = not manifest_payload or manifest_target == target
    if manifest_payload and not manifest_target_matches:
        issues.append(f"manifest_target_mismatch:{manifest_target}")

    coverage_domain = str(manifest_payload.get("coverage_domain") or "")
    coverage_domain_matches = not manifest_payload or coverage_domain == EXPECTED_COVERAGE_DOMAIN
    if manifest_payload and not coverage_domain_matches:
        issues.append(f"coverage_domain_mismatch:{coverage_domain}")

    missing_manifest_words = [name for name in REQUIRED_REAL_TOGGLE_OUTPUTS if name not in manifest_words]
    unexpected_manifest_words = [
        name for name in manifest_words
        if name not in REQUIRED_REAL_TOGGLE_OUTPUTS
    ]
    if missing_manifest_words:
        issues.append(f"manifest_missing_real_toggle_words:{len(missing_manifest_words)}")
    if unexpected_manifest_words:
        notes.append(f"manifest_extra_words:{len(unexpected_manifest_words)}")

    if missing_inputs:
        issues.append(f"tb_missing_required_inputs:{len(missing_inputs)}")
    if missing_outputs:
        issues.append(f"tb_missing_required_outputs:{len(missing_outputs)}")
    if semantic_expected and semantic_missing_outputs:
        issues.append(f"tb_missing_semantic_outputs:{len(semantic_missing_outputs)}")

    core_contract_status = "core_ready"
    if missing_inputs or missing_outputs or not top_module_matches_tb or not manifest_target_matches or not coverage_domain_matches or missing_manifest_words:
        core_contract_status = "core_needs_review"
    if not tb_path.exists() or not manifest_path.exists():
        core_contract_status = "core_missing_inputs"

    semantic_contract_status = "semantic_not_required"
    if semantic_expected:
        semantic_contract_status = "semantic_ready"
        if semantic_missing_outputs:
            semantic_contract_status = "semantic_needs_review"
        if not tb_path.exists():
            semantic_contract_status = "semantic_missing_inputs"

    status = "contract_ready"
    if issues:
        status = "contract_needs_review"
    if not tb_path.exists() or not manifest_path.exists():
        status = "contract_missing_inputs"

    return {
        "schema_version": "opentitan-tlul-slice-contract-v1",
        "status": status,
        "target": target,
        "top_module": top_module,
        "coverage_tb_path": str(tb_path),
        "coverage_manifest_path": str(manifest_path),
        "top_module_matches_tb": top_module_matches_tb,
        "tb_input_count": len(inputs),
        "required_input_count": len(REQUIRED_CORE_INPUTS),
        "missing_inputs": missing_inputs,
        "tb_output_count": len(outputs),
        "required_output_count": len(REQUIRED_OUTPUTS_FLAT),
        "missing_outputs": missing_outputs,
        "missing_outputs_by_group": missing_by_group,
        "core_contract_status": core_contract_status,
        "core_contract_ready": core_contract_status == "core_ready",
        "semantic_contract_expected": semantic_expected,
        "semantic_contract_status": semantic_contract_status,
        "semantic_contract_ready": semantic_contract_status == "semantic_ready",
        "semantic_required_output_count": len(REQUIRED_SEMANTIC_OUTPUTS),
        "semantic_missing_outputs": semantic_missing_outputs,
        "manifest_target": manifest_target,
        "manifest_target_matches": manifest_target_matches,
        "manifest_coverage_domain": coverage_domain,
        "manifest_coverage_domain_matches": coverage_domain_matches,
        "manifest_real_toggle_word_count": len(manifest_words),
        "manifest_missing_real_toggle_words": missing_manifest_words,
        "manifest_unexpected_words": unexpected_manifest_words,
        "issues": issues,
        "notes": notes,
    }
