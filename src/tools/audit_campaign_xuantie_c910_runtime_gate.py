#!/usr/bin/env python3
"""
Resolve the selected XuanTie-C910 runtime profile against the accepted same-family
branch and the current C910 runtime status.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_RUNTIME_STATUS_JSON = REPO_ROOT / "work" / "campaign_xuantie_c910_runtime_status.json"
DEFAULT_SAME_FAMILY_NEXT_AXES_JSON = REPO_ROOT / "work" / "campaign_xuantie_same_family_next_axes.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_xuantie_c910_runtime" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xuantie_c910_runtime_gate.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_profile_payload(
    *,
    selection_payload: dict[str, Any],
    selection_path: Path,
) -> tuple[str | None, Path | None, dict[str, Any] | None]:
    profile_name = selection_payload.get("profile_name")
    if not isinstance(profile_name, str) or not profile_name.strip():
        return None, None, None
    normalized_name = profile_name.strip()
    profile_path = selection_path.resolve().parent / "profiles" / f"{normalized_name}.json"
    if not profile_path.is_file():
        raise FileNotFoundError(f"campaign XuanTie-C910 runtime profile not found: {profile_path}")
    return normalized_name, profile_path, _read_json(profile_path)


def _build_outcome(
    *,
    profile_payload: dict[str, Any],
    runtime_status_payload: dict[str, Any],
    same_family_next_axes_payload: dict[str, Any],
) -> dict[str, Any]:
    runtime_mode = str(profile_payload.get("runtime_mode") or "")
    runtime_outcome = dict(runtime_status_payload.get("outcome") or {})
    runtime_smoke = dict(runtime_status_payload.get("runtime_smoke") or {})
    hybrid_payload = dict(runtime_status_payload.get("hybrid") or {})
    baseline_payload = dict(runtime_status_payload.get("cpu_baseline") or {})
    low_opt_debug = dict(runtime_status_payload.get("low_opt_runtime_debug") or {})
    cubin_probe = dict(low_opt_debug.get("cubin_probe") or {})
    o1_trace = dict(low_opt_debug.get("o1_trace") or {})
    next_axes_decision = dict(same_family_next_axes_payload.get("decision") or {})
    next_axes_context = dict(same_family_next_axes_payload.get("next_family_axis") or {})

    next_axes_status = str(next_axes_decision.get("status") or "")
    selected_design = str(next_axes_decision.get("recommended_same_family_design") or "")
    fallback_profile_name = str(next_axes_context.get("fallback_profile_name") or "")
    fallback_family = str(next_axes_context.get("fallback_family") or "")
    runtime_status = str(runtime_outcome.get("status") or "")

    if next_axes_status != "decide_continue_to_remaining_same_family_design_vs_open_fallback_family":
        return {
            "status": "blocked_c910_runtime_branch_not_active",
            "reason": "the_C910_runtime decision only applies after the accepted same-family step points at the remaining same-family design",
            "next_action": next_axes_decision.get("recommended_next_task") or "refresh_same_family_next_axes",
        }

    if selected_design != "XuanTie-C910":
        return {
            "status": "blocked_selected_same_family_design_is_not_c910",
            "reason": "the_current_same_family_next_axes artifact does not point at XuanTie-C910",
            "next_action": "refresh_the_same_family_next_axes_artifact_before_selecting_a_C910_runtime_profile",
        }

    if runtime_mode == "hold_c910_runtime_branch":
        return {
            "status": "hold_c910_runtime_branch",
            "reason": "the_selected_profile_keeps_the_C910_runtime_branch_in_pre_selection_state",
            "next_action": runtime_outcome.get("next_action") or "choose_between_debugging_C910_and_opening_VeeR",
            "runtime_status": runtime_status or None,
        }

    if runtime_mode == "debug_c910_hybrid_runtime":
        if runtime_status == "decide_hybrid_runtime_debug_vs_open_veer_fallback_family":
            return {
                "status": "debug_c910_hybrid_runtime_ready",
                "reason": runtime_outcome.get("reason")
                or "C910_cpu_baseline_is_ok_but_the_hybrid_runtime_is_still_killed_even_at_minimal_shapes",
                "next_action": runtime_outcome.get("next_action")
                or "debug_the_C910_hybrid_runtime_until_a_ready_comparison_line_exists",
                "selected_design": "XuanTie-C910",
                "runtime_smoke_status": runtime_smoke.get("status"),
                "baseline_status": baseline_payload.get("status"),
                "hybrid_status": hybrid_payload.get("status"),
                "o1_trace_status": o1_trace.get("status"),
                "cubin_probe_status": cubin_probe.get("status"),
            }
        if runtime_status == "ready_to_compare_c910_gate_policy":
            return {
                "status": "c910_runtime_recovered_ready_to_compare_gate_policy",
                "reason": "the_hybrid_runtime_is_no_longer_the_blocker_for_C910",
                "next_action": "decide_candidate_only_vs_new_default_gate_for_C910",
                "selected_design": "XuanTie-C910",
            }
        return {
            "status": "blocked_c910_runtime_debug_not_ready",
            "reason": runtime_outcome.get("reason") or "the_current_C910_runtime_state_does_not_support_runtime-debug selection",
            "next_action": runtime_outcome.get("next_action") or "repair_the_C910_runtime_prerequisites",
        }

    if runtime_mode == "open_fallback_family":
        if fallback_profile_name == "open_veer_fallback_family" and fallback_family == "VeeR":
            return {
                "status": "open_fallback_family_ready",
                "reason": "the_current_same-family-next-axes artifact already exposes VeeR as the fallback family after C906 acceptance",
                "next_action": "open_the_VeeR_fallback_family",
                "fallback_profile_name": fallback_profile_name,
                "fallback_family": fallback_family,
            }
        return {
            "status": "blocked_fallback_family_not_ready",
            "reason": "the_current_same-family-next-axes artifact does not expose the expected VeeR fallback family",
            "next_action": "refresh_the_same_family_next_axes_artifact_before_switching_to_the_fallback_family",
        }

    return {
        "status": "blocked_unknown_c910_runtime_mode",
        "reason": f"unknown XuanTie-C910 runtime mode: {runtime_mode}",
        "next_action": "repair_the_C910_runtime_profile_selection",
    }


def build_gate(
    *,
    runtime_status_payload: dict[str, Any],
    same_family_next_axes_payload: dict[str, Any],
    selection_payload: dict[str, Any],
    selection_path: Path,
) -> dict[str, Any]:
    profile_name, profile_path, profile_payload = _resolve_profile_payload(
        selection_payload=selection_payload,
        selection_path=selection_path,
    )
    if profile_payload is None or profile_path is None:
        raise ValueError("selection.json must specify a valid profile_name")

    outcome = _build_outcome(
        profile_payload=profile_payload,
        runtime_status_payload=runtime_status_payload,
        same_family_next_axes_payload=same_family_next_axes_payload,
    )
    next_axes_decision = dict(same_family_next_axes_payload.get("decision") or {})
    next_axes_context = dict(same_family_next_axes_payload.get("next_family_axis") or {})
    runtime_outcome = dict(runtime_status_payload.get("outcome") or {})

    return {
        "schema_version": 1,
        "scope": "campaign_xuantie_c910_runtime_gate",
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()),
            "notes": selection_payload.get("notes"),
        },
        "context": {
            "selected_same_family_design": next_axes_decision.get("recommended_same_family_design"),
            "fallback_family": next_axes_context.get("fallback_family"),
            "same_family_next_axes_status": next_axes_decision.get("status"),
            "runtime_status": runtime_outcome.get("status"),
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-status-json", type=Path, default=DEFAULT_RUNTIME_STATUS_JSON)
    parser.add_argument("--same-family-next-axes-json", type=Path, default=DEFAULT_SAME_FAMILY_NEXT_AXES_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_gate(
        runtime_status_payload=_read_json(args.runtime_status_json.resolve()),
        same_family_next_axes_payload=_read_json(args.same_family_next_axes_json.resolve()),
        selection_payload=_read_json(args.selection_config.resolve()),
        selection_path=args.selection_config.resolve(),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
