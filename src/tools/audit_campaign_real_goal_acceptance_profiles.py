#!/usr/bin/env python3
"""
Evaluate named checkpoint/seed acceptance profiles independently of the current
checked-in selection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_campaign_real_goal_acceptance_gate import build_gate


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_CHECKPOINT_JSON = REPO_ROOT / "work" / "campaign_checkpoint_readiness.json"
DEFAULT_SEED_STATUS_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_seed_status.json"
DEFAULT_PROFILES_DIR = REPO_ROOT / "config" / "campaign_real_goal_acceptance" / "profiles"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_real_goal_acceptance" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_real_goal_acceptance_profiles.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_profiles_matrix(
    *,
    checkpoint_payload: dict[str, Any],
    seed_payload: dict[str, Any],
    profiles_dir: Path,
    current_selection_payload: dict[str, Any] | None,
    current_selection_path: Path | None,
) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    profile_selection_path = profiles_dir.resolve().parent / "_profile_selection.json"
    for profile_path in sorted(profiles_dir.glob("*.json")):
        profile_payload = _read_json(profile_path)
        gate = build_gate(
            checkpoint_payload=checkpoint_payload,
            seed_payload=seed_payload,
            selection_payload={
                "profile_name": profile_payload.get("name"),
                "notes": profile_payload.get("notes"),
            },
            selection_path=profile_selection_path,
        )
        profiles.append(
            {
                "profile_path": str(profile_path.resolve()),
                "selection": {
                    "name": profile_payload.get("name"),
                    "accept_checkpoint": bool(profile_payload.get("accept_checkpoint")),
                    "accept_selected_seed": bool(profile_payload.get("accept_selected_seed")),
                    "notes": profile_payload.get("notes"),
                },
                "gate": gate,
            }
        )

    accepted_profiles: list[str] = []
    partial_profiles: list[str] = []
    hold_profiles: list[str] = []
    blocked_profiles: list[str] = []
    for profile in profiles:
        selection = dict(profile.get("selection") or {})
        outcome = dict((profile.get("gate") or {}).get("outcome") or {})
        name = str(selection.get("name") or "")
        status = str(outcome.get("status") or "")
        if status == "accepted_checkpoint_and_seed":
            accepted_profiles.append(name)
        elif status == "checkpoint_accepted_seed_pending":
            partial_profiles.append(name)
        elif status == "hold_checkpoint_and_seed":
            hold_profiles.append(name)
        else:
            blocked_profiles.append(name)

    current_profile_name = None
    current_profile_classification = "unknown"
    if current_selection_payload is not None:
        raw_name = current_selection_payload.get("profile_name")
        if isinstance(raw_name, str) and raw_name.strip():
            current_profile_name = raw_name.strip()
            if current_profile_name in accepted_profiles:
                current_profile_classification = "accepted"
            elif current_profile_name in partial_profiles:
                current_profile_classification = "partial"
            elif current_profile_name in hold_profiles:
                current_profile_classification = "hold"
            elif current_profile_name in blocked_profiles:
                current_profile_classification = "blocked"

    if current_profile_classification == "accepted":
        recommended_profile_name = current_profile_name
        recommended_decision_axis = "advance_after_accepting_checkpoint_and_seed"
    elif accepted_profiles:
        recommended_profile_name = accepted_profiles[0]
        recommended_decision_axis = "choose_named_checkpoint_seed_acceptance_profile"
    elif partial_profiles:
        recommended_profile_name = partial_profiles[0]
        recommended_decision_axis = "accept_checkpoint_before_seed_or_keep_holding"
    else:
        recommended_profile_name = hold_profiles[0] if hold_profiles else None
        recommended_decision_axis = "repair_checkpoint_seed_acceptance_profiles"

    return {
        "schema_version": 1,
        "scope": "campaign_real_goal_acceptance_profiles",
        "profiles_dir": str(profiles_dir.resolve()),
        "current_selection_path": (
            str(current_selection_path.resolve()) if current_selection_path is not None else None
        ),
        "profiles": profiles,
        "summary": {
            "profile_count": len(profiles),
            "current_profile_name": current_profile_name,
            "current_profile_classification": current_profile_classification,
            "accepted_profiles": accepted_profiles,
            "partial_profiles": partial_profiles,
            "hold_profiles": hold_profiles,
            "blocked_profiles": blocked_profiles,
            "recommended_profile_name": recommended_profile_name,
            "recommended_decision_axis": recommended_decision_axis,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-json", type=Path, default=DEFAULT_CHECKPOINT_JSON)
    parser.add_argument("--seed-status-json", type=Path, default=DEFAULT_SEED_STATUS_JSON)
    parser.add_argument("--profiles-dir", type=Path, default=DEFAULT_PROFILES_DIR)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    selection_path = args.selection_config.resolve()
    payload = build_profiles_matrix(
        checkpoint_payload=_read_json(args.checkpoint_json.resolve()),
        seed_payload=_read_json(args.seed_status_json.resolve()),
        profiles_dir=args.profiles_dir.resolve(),
        current_selection_payload=_read_json(selection_path),
        current_selection_path=selection_path,
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
