#!/usr/bin/env python3
"""
Summarize the next concrete debug tactic for the checked-in Vortex first-surface
debug branch.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_campaign_vortex_first_surface_status import _summarize_build_log


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_VORTEX_STATUS_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_status.json"
DEFAULT_VORTEX_GATE_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_gate.json"
DEFAULT_VORTEX_ACCEPTANCE_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_acceptance_gate.json"
DEFAULT_DEEPER_STATUS_JSON = REPO_ROOT / "work" / "campaign_vortex_deeper_debug_status.json"
DEFAULT_BUILD_O0_LOG = REPO_ROOT / "work" / "vortex_build_o0.log"
DEFAULT_BUILD_O1_LOG = REPO_ROOT / "work" / "vortex_build_o1.log"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_vortex_debug_tactics.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text_if_exists(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def build_tactics(
    *,
    vortex_status_payload: dict[str, Any],
    vortex_gate_payload: dict[str, Any],
    vortex_acceptance_payload: dict[str, Any] | None,
    deeper_status_payload: dict[str, Any] | None,
    low_opt_o0_log_text: str | None,
    low_opt_o1_log_text: str | None,
) -> dict[str, Any]:
    gate_outcome = dict(vortex_gate_payload.get("outcome") or {})
    gate_selection = dict(vortex_gate_payload.get("selection") or {})
    acceptance_outcome = dict((vortex_acceptance_payload or {}).get("outcome") or {})
    vortex_outcome = dict(vortex_status_payload.get("outcome") or {})
    vortex_build = dict(vortex_status_payload.get("gpu_build") or {})
    low_opt_o0 = _summarize_build_log(low_opt_o0_log_text)
    low_opt_o1 = _summarize_build_log(low_opt_o1_log_text)
    deeper_decision = dict((deeper_status_payload or {}).get("decision") or {})
    deeper_observations = dict((deeper_status_payload or {}).get("observations") or {})

    selected_profile_name = str(gate_selection.get("profile_name") or "")
    gate_status = str(gate_outcome.get("status") or "")
    acceptance_status = str(acceptance_outcome.get("status") or "")
    vortex_status = str(vortex_outcome.get("status") or "")
    deeper_status = str(deeper_decision.get("status") or "")
    baseline_blocker = str(vortex_build.get("status") or "")
    o0_status = str(low_opt_o0.get("status") or "")
    o1_status = str(low_opt_o1.get("status") or "")

    if acceptance_status == "accepted_selected_vortex_first_surface_step":
        decision = {
            "status": "vortex_first_surface_already_accepted",
            "reason": "the_selected_Vortex_first_surface_step_is_already_accepted",
            "recommended_next_tactic": acceptance_outcome.get("next_action")
            or "decide_post_vortex_family_axes_after_accepting_vortex",
            "fallback_tactic": None,
        }
    elif selected_profile_name != "debug_vortex_tls_lowering":
        decision = {
            "status": "select_vortex_debug_or_fallback_branch_first",
            "reason": "the_current_checked_in_Vortex_profile_is_not_the_TLS-lowering_debug_branch",
            "recommended_next_tactic": "choose_named_vortex_first_surface_profile",
            "fallback_tactic": "reopen_xiangshan_fallback_family",
        }
    elif (
        gate_status == "vortex_gpu_build_recovered_ready_to_finish_trio"
        and vortex_status == "ready_to_finish_vortex_first_trio"
    ):
        decision = {
            "status": "ready_to_finish_vortex_first_trio",
            "reason": "the_Vortex_gpu_build_blocker_is_no_longer_active",
            "recommended_next_tactic": "finish_the_Vortex_first_campaign_trio",
            "fallback_tactic": None,
        }
    elif gate_status != "debug_vortex_tls_lowering_ready":
        decision = {
            "status": "repair_vortex_branch_state",
            "reason": gate_outcome.get("reason")
            or "the_selected_Vortex_debug_branch_is_not_in_a_ready_debug_state",
            "recommended_next_tactic": gate_outcome.get("next_action")
            or "repair_the_selected_Vortex_branch",
            "fallback_tactic": "reopen_xiangshan_fallback_family",
        }
    elif deeper_status == "ready_for_vortex_dpi_wrapper_abi_debug":
        decision = {
            "status": "continue_vortex_with_dpi_wrapper_abi_debug",
            "reason": deeper_decision.get("reason")
            or "a_tls_bypass_proves_llc_recovery_but_ptxas_now_fails_on_a_gpu-reachable_DPI_wrapper_ABI_mismatch",
            "recommended_next_tactic": deeper_decision.get("recommended_next_tactic")
            or "deeper_vortex_dpi_wrapper_abi_debug",
            "fallback_tactic": deeper_decision.get("fallback_tactic")
            or "deeper_vortex_tls_lowering_debug",
        }
    elif (
        vortex_status == "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback"
        and baseline_blocker == "llc_tls_global_blocked"
        and o0_status == "llc_tls_global_blocked"
        and o1_status == "llc_tls_global_blocked"
    ):
        decision = {
            "status": "prefer_reopen_xiangshan_after_low_opt_vortex_trials_failed",
            "reason": (
                "the_default_O3_path_and_the_generic_O0_O1_reuse_gpu_patched_ll_trials_all_fail_"
                "at_the_same_llc_TLS_lowering_step"
            ),
            "recommended_next_tactic": "reopen_xiangshan_fallback_family",
            "fallback_tactic": "deeper_vortex_tls_lowering_debug",
        }
    else:
        decision = {
            "status": "deeper_vortex_tls_debug_or_reopen_xiangshan",
            "reason": vortex_outcome.get("reason")
            or "the_current_Vortex_state_does_not_match_a_more_specific_debug_tactic",
            "recommended_next_tactic": "deeper_vortex_tls_lowering_debug",
            "fallback_tactic": "reopen_xiangshan_fallback_family",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_vortex_debug_tactics",
        "current_branch": {
            "selected_profile_name": selected_profile_name or None,
            "gate_status": gate_status or None,
            "acceptance_status": acceptance_status or None,
            "vortex_status": vortex_status or None,
        },
        "observations": {
            "baseline_gpu_build_status": vortex_build.get("status"),
            "baseline_gpu_blocker_kind": vortex_build.get("blocker_kind"),
            "baseline_failing_function": vortex_build.get("failing_function"),
            "low_opt_o0_status": low_opt_o0.get("status"),
            "low_opt_o0_blocker_kind": low_opt_o0.get("blocker_kind"),
            "low_opt_o1_status": low_opt_o1.get("status"),
            "low_opt_o1_blocker_kind": low_opt_o1.get("blocker_kind"),
            "low_opt_o0_contains_verilated_tls": low_opt_o0.get("contains_verilated_tls"),
            "low_opt_o1_contains_verilated_tls": low_opt_o1.get("contains_verilated_tls"),
            "deeper_status": deeper_status or None,
            "deeper_ptxas_status": deeper_observations.get("ptxas_status"),
            "deeper_failed_wrapper_name": deeper_observations.get("ptxas_failed_wrapper_name"),
            "deeper_classifier_wrapper_placement": deeper_observations.get(
                "classifier_wrapper_placement"
            ),
        },
        "capabilities": {
            "build_vl_gpu_supports_gpu_opt_level": True,
            "build_vl_gpu_supports_reuse_gpu_patched_ll": True,
            "fallback_family_ready": True,
            "fallback_family_name": "XiangShan",
            "tls_bypass_recovery_path_present": deeper_status == "ready_for_vortex_dpi_wrapper_abi_debug",
        },
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vortex-status-json", type=Path, default=DEFAULT_VORTEX_STATUS_JSON)
    parser.add_argument("--vortex-gate-json", type=Path, default=DEFAULT_VORTEX_GATE_JSON)
    parser.add_argument("--vortex-acceptance-json", type=Path, default=DEFAULT_VORTEX_ACCEPTANCE_JSON)
    parser.add_argument("--deeper-status-json", type=Path, default=DEFAULT_DEEPER_STATUS_JSON)
    parser.add_argument("--build-o0-log", type=Path, default=DEFAULT_BUILD_O0_LOG)
    parser.add_argument("--build-o1-log", type=Path, default=DEFAULT_BUILD_O1_LOG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    deeper_status_path = args.deeper_status_json.resolve()
    acceptance_path = args.vortex_acceptance_json.resolve()
    payload = build_tactics(
        vortex_status_payload=_read_json(args.vortex_status_json.resolve()),
        vortex_gate_payload=_read_json(args.vortex_gate_json.resolve()),
        vortex_acceptance_payload=_read_json(acceptance_path) if acceptance_path.is_file() else None,
        deeper_status_payload=_read_json(deeper_status_path) if deeper_status_path.is_file() else None,
        low_opt_o0_log_text=_read_text_if_exists(args.build_o0_log.resolve()),
        low_opt_o1_log_text=_read_text_if_exists(args.build_o1_log.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
