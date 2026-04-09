#!/usr/bin/env python3
"""
Summarize the next concrete debug tactic for the accepted XuanTie-C910 runtime
debug branch.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_RUNTIME_STATUS_JSON = REPO_ROOT / "work" / "campaign_xuantie_c910_runtime_status.json"
DEFAULT_RUNTIME_GATE_JSON = REPO_ROOT / "work" / "campaign_xuantie_c910_runtime_gate.json"
DEFAULT_SPLIT_PHASE_TRIAL_JSON = REPO_ROOT / "work" / "campaign_xuantie_c910_split_phase_trial.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xuantie_c910_debug_tactics.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_tactics(
    *,
    runtime_status_payload: dict[str, Any],
    runtime_gate_payload: dict[str, Any],
    split_phase_trial_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    gate_outcome = dict(runtime_gate_payload.get("outcome") or {})
    gate_selection = dict(runtime_gate_payload.get("selection") or {})
    runtime_outcome = dict(runtime_status_payload.get("outcome") or {})
    low_opt = dict(runtime_status_payload.get("low_opt_runtime_debug") or {})
    o1_trace = dict(low_opt.get("o1_trace") or {})
    cubin_probe = dict(low_opt.get("cubin_probe") or {})
    split_runtime = dict((split_phase_trial_payload or {}).get("split_phase_runtime") or {})
    split_decision = dict((split_phase_trial_payload or {}).get("decision") or {})

    selected_profile_name = str(gate_selection.get("profile_name") or "")
    gate_status = str(gate_outcome.get("status") or "")
    runtime_status = str(runtime_outcome.get("status") or "")
    o1_trace_status = str(o1_trace.get("status") or "")
    cubin_probe_status = str(cubin_probe.get("status") or "")
    split_decision_status = str(split_decision.get("status") or "")

    if selected_profile_name != "debug_c910_hybrid_runtime":
        decision = {
            "status": "select_debug_or_fallback_runtime_branch_first",
            "reason": "the_current_checked_in_runtime_profile_is_not_the_same_family_debug_branch",
            "recommended_next_tactic": "choose_named_c910_runtime_profile",
            "fallback_tactic": "open_veer_fallback_family",
        }
    elif gate_status != "debug_c910_hybrid_runtime_ready":
        decision = {
            "status": "repair_c910_runtime_branch_state",
            "reason": gate_outcome.get("reason")
            or "the_selected_c910_debug_branch_is_not_in_a_ready_debug_state",
            "recommended_next_tactic": gate_outcome.get("next_action")
            or "repair_the_selected_c910_runtime_branch",
            "fallback_tactic": "open_veer_fallback_family",
        }
    elif (
        runtime_status == "decide_hybrid_runtime_debug_vs_open_veer_fallback_family"
        and o1_trace_status == "stalled_before_cuModuleLoad"
        and cubin_probe_status in {"timed_out", "killed"}
    ):
        if split_decision_status == "timed_out_before_cuModuleLoad":
            decision = {
                "status": "prefer_fallback_family_after_split_phase_trial_failed",
                "reason": (
                    "the_split_phase_ptx_module_first_trial_also_timed_out_before_"
                    "cuModuleLoad_so_the_lowest_cost_c910_size_reduction_tactic_is_exhausted"
                ),
                "recommended_next_tactic": "open_veer_fallback_family",
                "fallback_tactic": "deeper_c910_cubin_debug",
            }
        else:
            decision = {
                "status": "try_kernel_split_phases_before_opening_fallback_family",
                "reason": (
                    "the_monolithic_o1_ptx_path_stalls_before_cuModuleLoad_and_the_current_"
                    "offline_cubin_probe_is_not_finishing"
                ),
                "recommended_next_tactic": "kernel_split_phases_ptx_module_first",
                "fallback_tactic": "open_veer_fallback_family",
            }
    elif runtime_status == "ready_to_compare_c910_gate_policy":
        decision = {
            "status": "ready_to_compare_c910_gate_policy",
            "reason": "the_c910_runtime_blocker_is_no_longer_active",
            "recommended_next_tactic": "compare_candidate_only_vs_new_default_gate_for_c910",
            "fallback_tactic": None,
        }
    else:
        decision = {
            "status": "deeper_cubin_debug_or_fallback_family",
            "reason": runtime_outcome.get("reason")
            or "the_current_c910_runtime_state_does_not_match_a_more_specific_debug_tactic",
            "recommended_next_tactic": "deeper_c910_cubin_debug",
            "fallback_tactic": "open_veer_fallback_family",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_xuantie_c910_debug_tactics",
        "current_branch": {
            "selected_profile_name": selected_profile_name or None,
            "gate_status": gate_status or None,
            "runtime_status": runtime_status or None,
        },
        "observations": {
            "o1_trace_status": o1_trace.get("status"),
            "o1_trace_last_stage": o1_trace.get("last_stage"),
            "cubin_probe_status": cubin_probe.get("status"),
            "cubin_probe_timeout_seconds": cubin_probe.get("timeout_seconds"),
            "cubin_probe_exists": cubin_probe.get("cubin_exists"),
            "split_phase_trial_status": split_decision.get("status"),
            "split_phase_runtime_status": split_runtime.get("status"),
            "split_phase_last_stage": split_runtime.get("last_stage"),
            "split_phase_returncode": split_runtime.get("returncode"),
        },
        "capabilities": {
            "build_vl_gpu_supports_kernel_split_phases": True,
            "run_vl_hybrid_supports_launch_sequence": True,
            "fallback_family_ready": True,
            "fallback_family_name": "VeeR",
        },
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-status-json", type=Path, default=DEFAULT_RUNTIME_STATUS_JSON)
    parser.add_argument("--runtime-gate-json", type=Path, default=DEFAULT_RUNTIME_GATE_JSON)
    parser.add_argument("--split-phase-trial-json", type=Path, default=DEFAULT_SPLIT_PHASE_TRIAL_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_tactics(
        runtime_status_payload=_read_json(args.runtime_status_json.resolve()),
        runtime_gate_payload=_read_json(args.runtime_gate_json.resolve()),
        split_phase_trial_payload=(
            _read_json(args.split_phase_trial_json.resolve())
            if args.split_phase_trial_json.resolve().is_file()
            else None
        ),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
