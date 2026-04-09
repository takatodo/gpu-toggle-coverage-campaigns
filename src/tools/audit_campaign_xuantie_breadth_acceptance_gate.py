#!/usr/bin/env python3
"""
Resolve the selected XuanTie breadth acceptance profile against the accepted
checkpoint/seed baseline and the active XuanTie breadth gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_REAL_GOAL_ACCEPTANCE_JSON = REPO_ROOT / "work" / "campaign_real_goal_acceptance_gate.json"
DEFAULT_BREADTH_GATE_JSON = REPO_ROOT / "work" / "campaign_xuantie_breadth_gate.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_xuantie_breadth_acceptance" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xuantie_breadth_acceptance_gate.json"


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
        raise FileNotFoundError(f"campaign XuanTie breadth acceptance profile not found: {profile_path}")
    return normalized_name, profile_path, _read_json(profile_path)


def _build_outcome(
    *,
    profile_payload: dict[str, Any],
    real_goal_acceptance_payload: dict[str, Any],
    breadth_gate_payload: dict[str, Any],
) -> dict[str, Any]:
    accept_selected_breadth = bool(profile_payload.get("accept_selected_breadth"))
    acceptance_outcome = dict(real_goal_acceptance_payload.get("outcome") or {})
    breadth_outcome = dict(breadth_gate_payload.get("outcome") or {})
    breadth_selection = dict(breadth_gate_payload.get("selection") or {})

    real_goal_status = str(acceptance_outcome.get("status") or "")
    breadth_status = str(breadth_outcome.get("status") or "")

    if real_goal_status != "accepted_checkpoint_and_seed":
        return {
            "status": "blocked_checkpoint_seed_not_accepted",
            "reason": "XuanTie breadth acceptance requires the checkpoint and first non-OpenTitan seed to be accepted first",
            "next_action": acceptance_outcome.get("next_action") or "accept_checkpoint_and_seed_baseline",
        }

    if not accept_selected_breadth:
        return {
            "status": "hold_selected_xuantie_breadth",
            "reason": "selected_profile_keeps_the_current_XuanTie_breadth_step_in_pre_acceptance_state",
            "next_action": breadth_outcome.get("next_action") or "accept_selected_xuantie_breadth_step",
            "selected_breadth_status": breadth_status or None,
        }

    if breadth_status not in {"candidate_only_ready", "default_gate_ready", "family_pilot_ready"}:
        return {
            "status": "blocked_selected_xuantie_breadth_not_ready",
            "reason": breadth_outcome.get("reason")
            or "selected_XuanTie_breadth_step_is_not_ready_for_acceptance",
            "next_action": breadth_outcome.get("next_action") or "repair_selected_xuantie_breadth_step",
            "selected_breadth_status": breadth_status or None,
        }

    return {
        "status": "accepted_selected_xuantie_breadth",
        "reason": "the_selected_XuanTie_breadth_step_is_ready_and_now_checked_in_as_the_next_non_OpenTitan_breadth_baseline",
        "next_action": "decide_next_non_opentitan_breadth_step",
        "selected_breadth_profile_name": breadth_selection.get("profile_name"),
        "selected_breadth_design": breadth_selection.get("design"),
        "selected_breadth_family": breadth_selection.get("family"),
        "selected_breadth_status": breadth_status,
        "comparison_path": breadth_outcome.get("comparison_path"),
        "speedup_ratio": breadth_outcome.get("speedup_ratio"),
        "candidate_threshold_value": breadth_outcome.get("candidate_threshold_value"),
    }


def build_gate(
    *,
    real_goal_acceptance_payload: dict[str, Any],
    breadth_gate_payload: dict[str, Any],
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
        real_goal_acceptance_payload=real_goal_acceptance_payload,
        breadth_gate_payload=breadth_gate_payload,
    )
    acceptance_outcome = dict(real_goal_acceptance_payload.get("outcome") or {})
    breadth_selection = dict(breadth_gate_payload.get("selection") or {})
    breadth_outcome = dict(breadth_gate_payload.get("outcome") or {})

    return {
        "schema_version": 1,
        "scope": "campaign_xuantie_breadth_acceptance_gate",
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()),
            "notes": selection_payload.get("notes"),
        },
        "context": {
            "real_goal_acceptance_status": acceptance_outcome.get("status"),
            "selected_breadth_profile_name": breadth_selection.get("profile_name"),
            "selected_breadth_design": breadth_selection.get("design"),
            "selected_breadth_status": breadth_outcome.get("status"),
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-goal-acceptance-json", type=Path, default=DEFAULT_REAL_GOAL_ACCEPTANCE_JSON)
    parser.add_argument("--breadth-gate-json", type=Path, default=DEFAULT_BREADTH_GATE_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_gate(
        real_goal_acceptance_payload=_read_json(args.real_goal_acceptance_json.resolve()),
        breadth_gate_payload=_read_json(args.breadth_gate_json.resolve()),
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
