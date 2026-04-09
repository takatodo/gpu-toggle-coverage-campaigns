#!/usr/bin/env python3
"""
Summarize the current deeper Vortex debug line after XiangShan acceptance
reopens Vortex as the active next family.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_XIANGSHAN_ACCEPTANCE_JSON = (
    REPO_ROOT / "work" / "campaign_xiangshan_first_surface_acceptance_gate.json"
)
DEFAULT_VORTEX_STATUS_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_status.json"
DEFAULT_VORTEX_BYPASS_PTX = (
    REPO_ROOT / "work" / "vl_ir_exp" / "vortex_gpu_cov_vl" / "vl_batch_gpu_vortex_tls_bypass.ptx"
)
DEFAULT_VORTEX_CLASSIFIER_JSON = (
    REPO_ROOT / "work" / "vl_ir_exp" / "vortex_gpu_cov_vl" / "vl_classifier_report.json"
)
DEFAULT_VORTEX_PTXAS_LOG = REPO_ROOT / "work" / "vortex_tls_bypass_ptxas.log"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_vortex_deeper_debug_status.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text_if_exists(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _ptx_observations(ptx_text: str | None) -> dict[str, Any]:
    if not ptx_text:
        return {
            "ptx_exists": False,
            "kernel_entry_present": False,
            "dpi_wrapper_present": False,
            "wrapper_param3_is_b64": False,
        }
    return {
        "ptx_exists": True,
        "kernel_entry_present": ".visible .entry vl_eval_batch_gpu" in ptx_text,
        "dpi_wrapper_present": "__Vdpiimwrap_" in ptx_text and "mem_access" in ptx_text,
        "wrapper_param3_is_b64": "__param_3" in ptx_text and ".param .b64" in ptx_text,
    }


def _ptxas_observations(log_text: str | None) -> dict[str, Any]:
    if not log_text:
        return {
            "status": None,
            "failed_wrapper_name": None,
            "failed_param_name": None,
        }

    match = re.search(r"formal parameter '([^']+)'", log_text)
    failed_param_name = match.group(1) if match else None
    failed_wrapper_name = None
    if failed_param_name and "__param_" in failed_param_name:
        failed_wrapper_name = failed_param_name.rsplit("__param_", 1)[0]

    if "Type of argument does not match formal parameter" in log_text and failed_wrapper_name:
        status = "dpi_wrapper_abi_mismatch"
    elif "Type of argument does not match formal parameter" in log_text:
        status = "ptxas_formal_parameter_type_mismatch"
    elif "ptxas fatal" in log_text:
        status = "ptxas_failed"
    else:
        status = "unknown"

    return {
        "status": status,
        "failed_wrapper_name": failed_wrapper_name,
        "failed_param_name": failed_param_name,
    }


def _classifier_wrapper_details(
    classifier_payload: dict[str, Any] | None,
    wrapper_name: str | None,
) -> dict[str, Any]:
    functions = list((classifier_payload or {}).get("functions") or [])
    if not wrapper_name:
        return {"placement": None, "reason": None}
    for entry in functions:
        if not isinstance(entry, dict):
            continue
        entry_name = str(entry.get("name") or "")
        if (
            entry_name == wrapper_name
            or entry_name.rstrip("_") == wrapper_name.rstrip("_")
            or wrapper_name in entry_name
        ):
            return {
                "placement": entry.get("placement"),
                "reason": entry.get("reason"),
            }
    return {"placement": None, "reason": None}


def build_status(
    *,
    xiangshan_acceptance_payload: dict[str, Any],
    vortex_status_payload: dict[str, Any],
    vortex_bypass_ptx_text: str | None,
    vortex_ptxas_log_text: str | None,
    vortex_classifier_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    xiangshan_outcome = dict(xiangshan_acceptance_payload.get("outcome") or {})
    vortex_outcome = dict(vortex_status_payload.get("outcome") or {})
    vortex_build = dict(vortex_status_payload.get("gpu_build") or {})

    xiangshan_acceptance_status = str(xiangshan_outcome.get("status") or "")
    vortex_status = str(vortex_outcome.get("status") or "")
    baseline_gpu_build_status = str(vortex_build.get("status") or "")

    ptx_obs = _ptx_observations(vortex_bypass_ptx_text)
    ptxas_obs = _ptxas_observations(vortex_ptxas_log_text)
    classifier_obs = _classifier_wrapper_details(
        vortex_classifier_payload,
        str(ptxas_obs.get("failed_wrapper_name") or "") or None,
    )

    if xiangshan_acceptance_status != "accepted_selected_xiangshan_first_surface_step":
        decision = {
            "status": "accept_xiangshan_first_before_reopening_vortex",
            "reason": "the_current_Vortex_deeper_debug line assumes XiangShan has already been accepted",
            "recommended_next_tactic": "accept_selected_xiangshan_first_surface_step",
            "fallback_tactic": "deeper_xiangshan_executable_link_population_debug",
        }
    elif (
        vortex_status == "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback"
        and baseline_gpu_build_status == "llc_tls_global_blocked"
        and ptx_obs.get("ptx_exists")
        and ptx_obs.get("kernel_entry_present")
        and ptxas_obs.get("status") == "dpi_wrapper_abi_mismatch"
        and classifier_obs.get("placement") == "gpu"
    ):
        decision = {
            "status": "ready_for_vortex_dpi_wrapper_abi_debug",
            "reason": (
                "a_temporary_Verilated_TLS_slot_bypass_proves_llc_can_emit_a_gpu_kernel_but_ptxas_"
                "now_fails_on_a_gpu-reachable_mem_access_dpi_wrapper_formal-parameter_ABI_mismatch"
            ),
            "recommended_next_tactic": "deeper_vortex_dpi_wrapper_abi_debug",
            "fallback_tactic": "deeper_vortex_tls_lowering_debug",
        }
    elif (
        vortex_status == "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback"
        and baseline_gpu_build_status == "llc_tls_global_blocked"
        and ptx_obs.get("ptx_exists")
    ):
        decision = {
            "status": "continue_collecting_vortex_post_tls_codegen_evidence",
            "reason": (
                "the_temporary_TLS_bypass_produces_PTX_but_the_downstream_failure_is_not_yet_"
                "classified_as_the_expected_DPI-wrapper_ABI_mismatch"
            ),
            "recommended_next_tactic": "deeper_vortex_tls_lowering_debug",
            "fallback_tactic": "reinspect_vortex_tls_bypass_packaging_artifacts",
        }
    else:
        decision = {
            "status": "repair_vortex_or_xiangshan_branch_state_first",
            "reason": (
                "the_current_Vortex_and_XiangShan artifacts do_not_match_the_expected_"
                "post-acceptance_tls-bypass_debug_state"
            ),
            "recommended_next_tactic": vortex_outcome.get("next_action")
            or "repair_the_current_Vortex_branch_state",
            "fallback_tactic": "reopen_xiangshan_fallback_family",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_vortex_deeper_debug_status",
        "current_branch": {
            "xiangshan_acceptance_status": xiangshan_acceptance_status or None,
            "vortex_status": vortex_status or None,
            "baseline_gpu_build_status": baseline_gpu_build_status or None,
        },
        "observations": {
            "tls_bypass_ptx_exists": ptx_obs.get("ptx_exists"),
            "tls_bypass_kernel_entry_present": ptx_obs.get("kernel_entry_present"),
            "tls_bypass_dpi_wrapper_present": ptx_obs.get("dpi_wrapper_present"),
            "tls_bypass_wrapper_param3_is_b64": ptx_obs.get("wrapper_param3_is_b64"),
            "ptxas_status": ptxas_obs.get("status"),
            "ptxas_failed_wrapper_name": ptxas_obs.get("failed_wrapper_name"),
            "ptxas_failed_param_name": ptxas_obs.get("failed_param_name"),
            "classifier_wrapper_placement": classifier_obs.get("placement"),
            "classifier_wrapper_reason": classifier_obs.get("reason"),
            "high_level_vortex_blocker_kind": vortex_build.get("blocker_kind"),
            "high_level_vortex_failing_function": vortex_build.get("failing_function"),
        },
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xiangshan-acceptance-json", type=Path, default=DEFAULT_XIANGSHAN_ACCEPTANCE_JSON)
    parser.add_argument("--vortex-status-json", type=Path, default=DEFAULT_VORTEX_STATUS_JSON)
    parser.add_argument("--vortex-bypass-ptx", type=Path, default=DEFAULT_VORTEX_BYPASS_PTX)
    parser.add_argument("--vortex-ptxas-log", type=Path, default=DEFAULT_VORTEX_PTXAS_LOG)
    parser.add_argument("--vortex-classifier-json", type=Path, default=DEFAULT_VORTEX_CLASSIFIER_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    classifier_path = args.vortex_classifier_json.resolve()
    payload = build_status(
        xiangshan_acceptance_payload=_read_json(args.xiangshan_acceptance_json.resolve()),
        vortex_status_payload=_read_json(args.vortex_status_json.resolve()),
        vortex_bypass_ptx_text=_read_text_if_exists(args.vortex_bypass_ptx.resolve()),
        vortex_ptxas_log_text=_read_text_if_exists(args.vortex_ptxas_log.resolve()),
        vortex_classifier_payload=_read_json(classifier_path) if classifier_path.is_file() else None,
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
