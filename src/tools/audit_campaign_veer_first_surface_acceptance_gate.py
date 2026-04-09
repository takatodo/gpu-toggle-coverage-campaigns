#!/usr/bin/env python3
"""
Resolve the selected VeeR first-surface acceptance profile against the active
C910 runtime gate and the active VeeR first-surface gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_RUNTIME_GATE_JSON = REPO_ROOT / "work" / "campaign_xuantie_c910_runtime_gate.json"
DEFAULT_VEER_GATE_JSON = REPO_ROOT / "work" / "campaign_veer_first_surface_gate.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_veer_first_surface_acceptance" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_veer_first_surface_acceptance_gate.json"


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
        raise FileNotFoundError(f"campaign VeeR first-surface acceptance profile not found: {profile_path}")
    return normalized_name, profile_path, _read_json(profile_path)


def _build_outcome(
    *,
    profile_payload: dict[str, Any],
    runtime_gate_payload: dict[str, Any],
    veer_gate_payload: dict[str, Any],
) -> dict[str, Any]:
    accept_selected_step = bool(profile_payload.get("accept_selected_veer_first_surface_step"))
    runtime_outcome = dict(runtime_gate_payload.get("outcome") or {})
    veer_outcome = dict(veer_gate_payload.get("outcome") or {})
    veer_selection = dict(veer_gate_payload.get("selection") or {})

    runtime_status = str(runtime_outcome.get("status") or "")
    veer_status = str(veer_outcome.get("status") or "")

    if runtime_status != "open_fallback_family_ready":
        return {
            "status": "blocked_veer_fallback_not_active",
            "reason": "VeeR first-surface acceptance requires the open_veer_fallback_family branch to be active first",
            "next_action": runtime_outcome.get("next_action") or "select_open_veer_fallback_family",
        }

    if not accept_selected_step:
        return {
            "status": "hold_selected_veer_first_surface_step",
            "reason": "selected_profile_keeps_the_current_VeeR_first_surface_step_in_pre_acceptance_state",
            "next_action": veer_outcome.get("next_action") or "accept_selected_veer_first_surface_step",
            "selected_veer_status": veer_status or None,
        }

    if veer_status not in {"candidate_only_ready", "default_gate_ready"}:
        return {
            "status": "blocked_selected_veer_first_surface_step_not_ready",
            "reason": veer_outcome.get("reason") or "selected_veer_first_surface_step_is_not_ready_for_acceptance",
            "next_action": veer_outcome.get("next_action") or "repair_selected_veer_first_surface_step",
            "selected_veer_status": veer_status or None,
        }

    return {
        "status": "accepted_selected_veer_first_surface_step",
        "reason": "the_selected_VeeR_first_surface_step_is_ready_and_now_checked_in_as_the_next_fallback_family_evidence",
        "next_action": "decide_next_veer_same_family_surface",
        "selected_veer_profile_name": veer_selection.get("profile_name"),
        "selected_design": veer_outcome.get("selected_design"),
        "selected_veer_status": veer_status,
        "comparison_path": veer_outcome.get("comparison_path"),
        "speedup_ratio": veer_outcome.get("speedup_ratio"),
        "candidate_threshold_value": veer_outcome.get("candidate_threshold_value"),
    }


def build_gate(
    *,
    runtime_gate_payload: dict[str, Any],
    veer_gate_payload: dict[str, Any],
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
        runtime_gate_payload=runtime_gate_payload,
        veer_gate_payload=veer_gate_payload,
    )
    runtime_context = dict(runtime_gate_payload.get("context") or {})
    veer_selection = dict(veer_gate_payload.get("selection") or {})
    veer_outcome = dict(veer_gate_payload.get("outcome") or {})

    return {
        "schema_version": 1,
        "scope": "campaign_veer_first_surface_acceptance_gate",
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()),
            "notes": selection_payload.get("notes"),
        },
        "context": {
            "active_runtime_profile_name": runtime_context.get("profile_name") or runtime_gate_payload.get("selection", {}).get("profile_name"),
            "active_runtime_status": dict(runtime_gate_payload.get("outcome") or {}).get("status"),
            "selected_veer_profile_name": veer_selection.get("profile_name"),
            "selected_veer_status": veer_outcome.get("status"),
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-gate-json", type=Path, default=DEFAULT_RUNTIME_GATE_JSON)
    parser.add_argument("--veer-gate-json", type=Path, default=DEFAULT_VEER_GATE_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_gate(
        runtime_gate_payload=_read_json(args.runtime_gate_json.resolve()),
        veer_gate_payload=_read_json(args.veer_gate_json.resolve()),
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
