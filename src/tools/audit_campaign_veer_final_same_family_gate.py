#!/usr/bin/env python3
"""
Resolve the currently selected final VeeR same-family profile against the
current final same-family step summary.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_STEP_JSON = REPO_ROOT / "work" / "campaign_veer_final_same_family_step.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_veer_final_same_family" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_veer_final_same_family_gate.json"


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
        raise FileNotFoundError(f"campaign VeeR final same-family profile not found: {profile_path}")
    return normalized_name, profile_path, _read_json(profile_path)


def _build_outcome(*, profile_payload: dict[str, Any], step_payload: dict[str, Any]) -> dict[str, Any]:
    step_mode = str(profile_payload.get("step_mode") or "")
    selected_design = str(profile_payload.get("design") or "")
    candidate_threshold_value = profile_payload.get("candidate_threshold_value")
    step_outcome = dict(step_payload.get("outcome") or {})
    step_selected_design = dict(step_payload.get("selected_design") or {})
    step_status = str(step_outcome.get("status") or "")
    step_design = str(step_outcome.get("selected_design") or step_selected_design.get("design") or "")
    best_ready_threshold_value = step_outcome.get("candidate_threshold_value") or step_selected_design.get(
        "threshold6_candidate", {}
    ).get("threshold_value")

    if step_design and selected_design and step_design != selected_design:
        return {
            "status": "blocked_selected_design_mismatch",
            "reason": "selected_profile_targets_a_different_VeeR_design_than_the_current_final_same_family_step_artifact",
            "next_action": "recompute_veer_final_same_family_step_or_fix_profile",
            "selected_design": selected_design,
            "step_design": step_design,
        }

    if step_mode == "default_gate_hold":
        if step_status in {
            "decide_veer_el2_candidate_only_vs_new_default_gate",
            "veer_el2_default_gate_unresolved",
        }:
            return {
                "status": "default_gate_hold",
                "reason": "selected_profile_keeps_VeeR-EL2_on_the_current_unresolved_default_gate",
                "next_action": step_outcome.get("next_action") or "define_a_new_default_gate",
                "selected_design": step_design or selected_design or None,
                "default_comparison_path": step_outcome.get("default_comparison_path")
                or step_selected_design.get("default_comparison", {}).get("path"),
            }
        if step_status == "ready_to_accept_veer_el2_default_gate":
            return {
                "status": "default_gate_ready",
                "reason": "the_selected_final_VeeR_same-family_surface_already_has_a_ready_default_gate_line",
                "next_action": "accept_veer_el2_default_gate_line",
                "selected_design": step_design or selected_design or None,
                "comparison_path": step_outcome.get("comparison_path"),
                "speedup_ratio": step_outcome.get("speedup_ratio"),
            }
        return {
            "status": "default_gate_blocked",
            "reason": "selected_profile_requests_default_gate_progress_but_the_current_final_same_family_step_artifact_does_not_support_it",
            "next_action": step_outcome.get("next_action") or "repair_veer_el2_default_gate_line",
            "selected_design": step_design or selected_design or None,
        }

    if step_mode == "candidate_only_threshold":
        if step_status == "decide_veer_el2_candidate_only_vs_new_default_gate" and (
            best_ready_threshold_value == candidate_threshold_value
        ):
            return {
                "status": "candidate_only_ready",
                "reason": "selected_profile_accepts_the_checked_in_VeeR-EL2_candidate-only_hybrid_win",
                "next_action": "accept_veer_el2_candidate_only_step",
                "selected_design": step_design or selected_design or None,
                "comparison_path": step_outcome.get("candidate_comparison_path")
                or step_selected_design.get("threshold6_candidate", {}).get("path"),
                "speedup_ratio": step_outcome.get("speedup_ratio")
                or step_selected_design.get("threshold6_candidate", {}).get("speedup_ratio"),
                "candidate_threshold_value": candidate_threshold_value,
            }
        return {
            "status": "candidate_only_blocked",
            "reason": "selected_profile_requires_a_checked_in_VeeR-EL2_candidate-only_line_that_is_not_currently_available",
            "next_action": step_outcome.get("next_action") or "repair_veer_el2_candidate_only_line",
            "selected_design": step_design or selected_design or None,
            "candidate_threshold_value": candidate_threshold_value,
        }

    return {
        "status": "blocked_unknown_step_mode",
        "reason": f"unsupported step_mode: {step_mode}",
        "next_action": "fix_campaign_veer_final_same_family_profile",
    }


def build_gate(*, step_payload: dict[str, Any], selection_payload: dict[str, Any], selection_path: Path) -> dict[str, Any]:
    profile_name, profile_path, profile_payload = _resolve_profile_payload(
        selection_payload=selection_payload,
        selection_path=selection_path,
    )
    if profile_payload is None or profile_path is None:
        raise ValueError("selection.json must specify a valid profile_name")

    outcome = _build_outcome(profile_payload=profile_payload, step_payload=step_payload)
    step_context = dict(step_payload.get("context") or {})

    return {
        "schema_version": 1,
        "scope": "campaign_veer_final_same_family_gate",
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()),
            "step_mode": profile_payload.get("step_mode"),
            "design": profile_payload.get("design"),
            "candidate_threshold_value": profile_payload.get("candidate_threshold_value"),
            "notes": selection_payload.get("notes"),
        },
        "context": {
            "accepted_veer_same_family_status": step_context.get("accepted_veer_same_family_status"),
            "current_first_design": step_context.get("current_first_design"),
            "remaining_veer_designs": step_context.get("remaining_veer_designs"),
            "selected_design": step_context.get("selected_design"),
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step-json", type=Path, default=DEFAULT_STEP_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_gate(
        step_payload=_read_json(args.step_json.resolve()),
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
