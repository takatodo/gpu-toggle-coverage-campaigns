#!/usr/bin/env python3
"""
Resolve the selected VeeR same-family acceptance profile against the accepted
first VeeR surface and the active VeeR same-family gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_VEER_FIRST_SURFACE_ACCEPTANCE_JSON = REPO_ROOT / "work" / "campaign_veer_first_surface_acceptance_gate.json"
DEFAULT_VEER_SAME_FAMILY_GATE_JSON = REPO_ROOT / "work" / "campaign_veer_same_family_gate.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_veer_same_family_acceptance" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_veer_same_family_acceptance_gate.json"


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
        raise FileNotFoundError(f"campaign VeeR same-family acceptance profile not found: {profile_path}")
    return normalized_name, profile_path, _read_json(profile_path)


def _build_outcome(
    *,
    profile_payload: dict[str, Any],
    veer_first_surface_acceptance_payload: dict[str, Any],
    veer_same_family_gate_payload: dict[str, Any],
) -> dict[str, Any]:
    accept_selected_step = bool(profile_payload.get("accept_selected_veer_same_family_step"))
    first_surface_outcome = dict(veer_first_surface_acceptance_payload.get("outcome") or {})
    same_family_outcome = dict(veer_same_family_gate_payload.get("outcome") or {})
    same_family_selection = dict(veer_same_family_gate_payload.get("selection") or {})

    first_surface_status = str(first_surface_outcome.get("status") or "")
    same_family_status = str(same_family_outcome.get("status") or "")

    if first_surface_status != "accepted_selected_veer_first_surface_step":
        return {
            "status": "blocked_veer_first_surface_not_accepted",
            "reason": "VeeR same-family acceptance requires the first VeeR surface to be accepted first",
            "next_action": first_surface_outcome.get("next_action") or "accept_selected_veer_first_surface_step",
        }

    if not accept_selected_step:
        return {
            "status": "hold_selected_veer_same_family_step",
            "reason": "selected_profile_keeps_the_current_VeeR_same_family_step_in_pre_acceptance_state",
            "next_action": same_family_outcome.get("next_action") or "accept_selected_veer_same_family_step",
            "selected_veer_same_family_status": same_family_status or None,
        }

    if same_family_status not in {"candidate_only_ready", "default_gate_ready"}:
        return {
            "status": "blocked_selected_veer_same_family_step_not_ready",
            "reason": same_family_outcome.get("reason") or "selected_VeeR_same_family_step_is_not_ready_for_acceptance",
            "next_action": same_family_outcome.get("next_action") or "repair_selected_veer_same_family_step",
            "selected_veer_same_family_status": same_family_status or None,
        }

    return {
        "status": "accepted_selected_veer_same_family_step",
        "reason": "the_selected_VeeR_same_family_step_is_ready_and_now_checked_in_as_the_next_same_family_breadth_evidence",
        "next_action": "decide_next_veer_same_family_surface",
        "selected_veer_same_family_profile_name": same_family_selection.get("profile_name"),
        "selected_design": same_family_outcome.get("selected_design"),
        "selected_veer_same_family_status": same_family_status,
        "comparison_path": same_family_outcome.get("comparison_path"),
        "speedup_ratio": same_family_outcome.get("speedup_ratio"),
        "candidate_threshold_value": same_family_outcome.get("candidate_threshold_value"),
    }


def build_gate(
    *,
    veer_first_surface_acceptance_payload: dict[str, Any],
    veer_same_family_gate_payload: dict[str, Any],
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
        veer_first_surface_acceptance_payload=veer_first_surface_acceptance_payload,
        veer_same_family_gate_payload=veer_same_family_gate_payload,
    )
    first_surface_context = dict(veer_first_surface_acceptance_payload.get("context") or {})
    same_family_selection = dict(veer_same_family_gate_payload.get("selection") or {})
    same_family_outcome = dict(veer_same_family_gate_payload.get("outcome") or {})

    return {
        "schema_version": 1,
        "scope": "campaign_veer_same_family_acceptance_gate",
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()),
            "notes": selection_payload.get("notes"),
        },
        "context": {
            "selected_veer_first_surface_profile_name": first_surface_context.get("selected_veer_profile_name"),
            "selected_veer_first_surface_status": dict(veer_first_surface_acceptance_payload.get("outcome") or {}).get(
                "status"
            ),
            "selected_veer_same_family_profile_name": same_family_selection.get("profile_name"),
            "selected_veer_same_family_status": same_family_outcome.get("status"),
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--veer-first-surface-acceptance-json",
        type=Path,
        default=DEFAULT_VEER_FIRST_SURFACE_ACCEPTANCE_JSON,
    )
    parser.add_argument("--veer-same-family-gate-json", type=Path, default=DEFAULT_VEER_SAME_FAMILY_GATE_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_gate(
        veer_first_surface_acceptance_payload=_read_json(args.veer_first_surface_acceptance_json.resolve()),
        veer_same_family_gate_payload=_read_json(args.veer_same_family_gate_json.resolve()),
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
