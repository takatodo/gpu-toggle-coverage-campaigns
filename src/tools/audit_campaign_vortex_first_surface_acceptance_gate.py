#!/usr/bin/env python3
"""
Resolve the selected Vortex first-surface acceptance profile against the
active Vortex branch gate and the active Vortex policy gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_VORTEX_BRANCH_GATE_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_gate.json"
DEFAULT_VORTEX_POLICY_GATE_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_policy_gate.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_vortex_first_surface_acceptance" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_vortex_first_surface_acceptance_gate.json"


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
        raise FileNotFoundError(f"campaign Vortex first-surface acceptance profile not found: {profile_path}")
    return normalized_name, profile_path, _read_json(profile_path)


def _build_outcome(
    *,
    profile_payload: dict[str, Any],
    vortex_branch_gate_payload: dict[str, Any],
    vortex_policy_gate_payload: dict[str, Any],
) -> dict[str, Any]:
    accept_selected_step = bool(profile_payload.get("accept_selected_vortex_first_surface_step"))
    branch_outcome = dict(vortex_branch_gate_payload.get("outcome") or {})
    branch_selection = dict(vortex_branch_gate_payload.get("selection") or {})
    policy_outcome = dict(vortex_policy_gate_payload.get("outcome") or {})
    policy_selection = dict(vortex_policy_gate_payload.get("selection") or {})

    branch_status = str(branch_outcome.get("status") or "")
    policy_status = str(policy_outcome.get("status") or "")

    if accept_selected_step and policy_status in {"candidate_only_ready", "default_gate_ready"} and branch_status == "vortex_gpu_build_recovered_ready_to_finish_trio":
        return {
            "status": "accepted_selected_vortex_first_surface_step",
            "reason": "the_selected_Vortex_first_surface_step_is_ready_and_now_checked-in_as_non_opentitan_breadth_evidence",
            "next_action": "decide_post_vortex_family_axes_after_accepting_vortex",
            "selected_vortex_branch_profile_name": branch_selection.get("profile_name"),
            "selected_vortex_policy_profile_name": policy_selection.get("profile_name"),
            "selected_design": policy_outcome.get("selected_design"),
            "selected_vortex_policy_status": policy_status,
            "comparison_path": policy_outcome.get("comparison_path"),
            "speedup_ratio": policy_outcome.get("speedup_ratio"),
            "candidate_threshold_value": policy_outcome.get("candidate_threshold_value"),
        }

    if branch_status != "vortex_gpu_build_recovered_ready_to_finish_trio":
        return {
            "status": "blocked_vortex_branch_not_ready_for_acceptance",
            "reason": "Vortex first-surface acceptance requires the checked-in Vortex branch to be past GPU-build recovery and ready to finish the trio",
            "next_action": branch_outcome.get("next_action") or "finish_the_Vortex_first_campaign_trio",
            "selected_vortex_branch_status": branch_status or None,
        }

    if not accept_selected_step:
        return {
            "status": "hold_selected_vortex_first_surface_step",
            "reason": "selected_profile_keeps_the_current_Vortex_first-surface_step_in_pre-acceptance_state",
            "next_action": policy_outcome.get("next_action") or "accept_selected_vortex_first_surface_step",
            "selected_vortex_policy_status": policy_status or None,
        }

    return {
        "status": "blocked_selected_vortex_first_surface_step_not_ready",
        "reason": policy_outcome.get("reason") or "selected_vortex_first_surface_step_is_not_ready_for_acceptance",
        "next_action": policy_outcome.get("next_action") or "repair_selected_vortex_first_surface_step",
        "selected_vortex_policy_status": policy_status or None,
    }


def build_gate(
    *,
    vortex_branch_gate_payload: dict[str, Any],
    vortex_policy_gate_payload: dict[str, Any],
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
        vortex_branch_gate_payload=vortex_branch_gate_payload,
        vortex_policy_gate_payload=vortex_policy_gate_payload,
    )
    branch_selection = dict(vortex_branch_gate_payload.get("selection") or {})
    branch_outcome = dict(vortex_branch_gate_payload.get("outcome") or {})
    policy_selection = dict(vortex_policy_gate_payload.get("selection") or {})
    policy_outcome = dict(vortex_policy_gate_payload.get("outcome") or {})

    return {
        "schema_version": 1,
        "scope": "campaign_vortex_first_surface_acceptance_gate",
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()),
            "notes": selection_payload.get("notes"),
        },
        "context": {
            "selected_vortex_branch_profile_name": branch_selection.get("profile_name"),
            "selected_vortex_branch_status": branch_outcome.get("status"),
            "selected_vortex_policy_profile_name": policy_selection.get("profile_name"),
            "selected_vortex_policy_status": policy_outcome.get("status"),
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vortex-branch-gate-json", type=Path, default=DEFAULT_VORTEX_BRANCH_GATE_JSON)
    parser.add_argument("--vortex-policy-gate-json", type=Path, default=DEFAULT_VORTEX_POLICY_GATE_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_gate(
        vortex_branch_gate_payload=_read_json(args.vortex_branch_gate_json.resolve()),
        vortex_policy_gate_payload=_read_json(args.vortex_policy_gate_json.resolve()),
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
