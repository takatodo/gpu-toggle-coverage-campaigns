#!/usr/bin/env python3
"""
Evaluate named non-OpenTitan entry profiles independently of the current
checked-in selection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_campaign_non_opentitan_entry_gate import build_gate


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_ENTRY_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_entry.json"
DEFAULT_ENTRY_READINESS_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_entry_readiness.json"
DEFAULT_OVERRIDE_CANDIDATES_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_override_candidates.json"
DEFAULT_PROFILES_DIR = REPO_ROOT / "config" / "campaign_non_opentitan_entry" / "profiles"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_non_opentitan_entry" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_non_opentitan_entry_profiles.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_profiles_matrix(
    *,
    entry_payload: dict[str, Any],
    readiness_payload: dict[str, Any],
    override_payload: dict[str, Any],
    profiles_dir: Path,
    current_selection_payload: dict[str, Any] | None,
    current_selection_path: Path | None,
) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    for profile_path in sorted(profiles_dir.glob("*.json")):
        profile_payload = _read_json(profile_path)
        gate = build_gate(
            entry_payload=entry_payload,
            readiness_payload=readiness_payload,
            override_payload=override_payload,
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
                    "family": profile_payload.get("family"),
                    "entry_mode": profile_payload.get("entry_mode"),
                    "design": profile_payload.get("design"),
                    "fallback_design": profile_payload.get("fallback_design"),
                    "notes": profile_payload.get("notes"),
                },
                "gate": gate,
            }
        )

    ready_profiles: list[str] = []
    blocked_profiles: list[str] = []
    current_profile_name = None
    current_profile_classification = "unknown"
    recommended_profile_name = None
    for profile in profiles:
        selection = dict(profile.get("selection") or {})
        outcome = dict((profile.get("gate") or {}).get("outcome") or {})
        name = str(selection.get("name") or "")
        status = str(outcome.get("status") or "")
        if status in {"single_surface_ready", "single_surface_trio_ready", "family_pilot_ready"}:
            ready_profiles.append(name)
            if recommended_profile_name is None:
                recommended_profile_name = name
        else:
            blocked_profiles.append(name)
        if current_selection_payload is not None:
            raw_name = current_selection_payload.get("profile_name")
            if isinstance(raw_name, str) and raw_name.strip() == name:
                current_profile_name = name
                current_profile_classification = "ready" if name in ready_profiles else "blocked"

    recommended_decision_axis = "repair_non_opentitan_entry_profiles"
    if recommended_profile_name is not None:
        if current_profile_classification == "ready" and current_profile_name == recommended_profile_name:
            recommended_decision_axis = "accept_current_profile_seed_or_add_gate"
        else:
            recommended_decision_axis = "choose_named_non_opentitan_entry_profile_before_implementation"

    return {
        "schema_version": 1,
        "scope": "campaign_non_opentitan_entry_profiles",
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
            "blocked_profiles": blocked_profiles,
            "recommended_profile_name": recommended_profile_name,
            "recommended_decision_axis": recommended_decision_axis,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry-json", type=Path, default=DEFAULT_ENTRY_JSON)
    parser.add_argument("--entry-readiness-json", type=Path, default=DEFAULT_ENTRY_READINESS_JSON)
    parser.add_argument("--override-candidates-json", type=Path, default=DEFAULT_OVERRIDE_CANDIDATES_JSON)
    parser.add_argument("--profiles-dir", type=Path, default=DEFAULT_PROFILES_DIR)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_profiles_matrix(
        entry_payload=_read_json(args.entry_json.resolve()),
        readiness_payload=_read_json(args.entry_readiness_json.resolve()),
        override_payload=_read_json(args.override_candidates_json.resolve()),
        profiles_dir=args.profiles_dir.resolve(),
        current_selection_payload=_read_json(args.selection_config.resolve()),
        current_selection_path=args.selection_config.resolve(),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
