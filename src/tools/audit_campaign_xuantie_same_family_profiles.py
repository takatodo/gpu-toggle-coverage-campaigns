#!/usr/bin/env python3
"""
Evaluate named XuanTie same-family profiles independently of the current
checked-in selection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_campaign_xuantie_same_family_gate import build_gate


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_STEP_JSON = REPO_ROOT / "work" / "campaign_xuantie_same_family_step.json"
DEFAULT_PROFILES_DIR = REPO_ROOT / "config" / "campaign_xuantie_same_family" / "profiles"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_xuantie_same_family" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xuantie_same_family_profiles.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_profiles_matrix(
    *,
    step_payload: dict[str, Any],
    profiles_dir: Path,
    current_selection_payload: dict[str, Any] | None,
    current_selection_path: Path | None,
) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    for profile_path in sorted(profiles_dir.glob("*.json")):
        profile_payload = _read_json(profile_path)
        gate = build_gate(
            step_payload=step_payload,
            selection_payload={
                "profile_name": profile_payload.get("name"),
                "notes": profile_payload.get("notes"),
            },
            selection_path=current_selection_path if current_selection_path is not None else profile_path,
        )
        profiles.append(
            {
                "profile_path": str(profile_path.resolve()),
                "selection": {
                    "name": profile_payload.get("name"),
                    "step_mode": profile_payload.get("step_mode"),
                    "design": profile_payload.get("design"),
                    "candidate_threshold_value": profile_payload.get("candidate_threshold_value"),
                    "notes": profile_payload.get("notes"),
                },
                "gate": gate,
            }
        )

    ready_profiles: list[str] = []
    hold_profiles: list[str] = []
    blocked_profiles: list[str] = []
    recommended_profile_name = None
    current_profile_name = None
    current_profile_classification = "unknown"
    for profile in profiles:
        selection = dict(profile.get("selection") or {})
        outcome = dict((profile.get("gate") or {}).get("outcome") or {})
        name = str(selection.get("name") or "")
        status = str(outcome.get("status") or "")
        if status in {"candidate_only_ready", "default_gate_ready"}:
            ready_profiles.append(name)
            if recommended_profile_name is None:
                recommended_profile_name = name
        elif status == "default_gate_hold":
            hold_profiles.append(name)
            if recommended_profile_name is None:
                recommended_profile_name = name
        else:
            blocked_profiles.append(name)
        if current_selection_payload is not None:
            raw_name = current_selection_payload.get("profile_name")
            if isinstance(raw_name, str) and raw_name.strip() == name:
                current_profile_name = name
                if name in ready_profiles:
                    current_profile_classification = "ready"
                elif name in hold_profiles:
                    current_profile_classification = "hold"
                else:
                    current_profile_classification = "blocked"

    recommended_decision_axis = "repair_xuantie_same_family_profiles"
    if recommended_profile_name is not None:
        if current_profile_classification == "ready" and current_profile_name == recommended_profile_name:
            recommended_decision_axis = "accept_current_xuantie_same_family_profile"
        else:
            recommended_decision_axis = "choose_named_xuantie_same_family_profile"

    return {
        "schema_version": 1,
        "scope": "campaign_xuantie_same_family_profiles",
        "profiles_dir": str(profiles_dir.resolve()),
        "current_selection_path": (
            str(current_selection_path.resolve()) if current_selection_path is not None else None
        ),
        "profiles": profiles,
        "summary": {
            "profile_count": len(profiles),
            "current_profile_name": current_profile_name,
            "current_profile_classification": current_profile_classification,
            "ready_profiles": ready_profiles,
            "hold_profiles": hold_profiles,
            "blocked_profiles": blocked_profiles,
            "recommended_profile_name": recommended_profile_name,
            "recommended_decision_axis": recommended_decision_axis,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step-json", type=Path, default=DEFAULT_STEP_JSON)
    parser.add_argument("--profiles-dir", type=Path, default=DEFAULT_PROFILES_DIR)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    selection_path = args.selection_config.resolve()
    payload = build_profiles_matrix(
        step_payload=_read_json(args.step_json.resolve()),
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
