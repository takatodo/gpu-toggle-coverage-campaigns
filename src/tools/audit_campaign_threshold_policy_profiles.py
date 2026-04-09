#!/usr/bin/env python3
"""
Evaluate named campaign-threshold policy profiles independently of the current
checked-in selection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_campaign_active_scoreboard import build_active_scoreboard_from_gate_payload
from audit_campaign_next_kpi import build_audit_from_scoreboard_payload
from audit_campaign_threshold_policy_gate import build_gate


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_OPTIONS_JSON = REPO_ROOT / "work" / "campaign_threshold_policy_options.json"
DEFAULT_PROFILES_DIR = REPO_ROOT / "config" / "campaign_threshold_policies" / "profiles"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_threshold_policies" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_threshold_policy_profiles.json"
DEFAULT_MIN_READY_SURFACES = 2
DEFAULT_MIN_STRONG_MARGIN = 2.0


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _profile_payload(
    *,
    profile_payload: dict[str, Any],
    options_payload: dict[str, Any],
    options_path: Path,
    profile_path: Path,
    minimum_ready_surfaces: int,
    minimum_strong_margin: float,
) -> dict[str, Any]:
    gate = build_gate(
        options_payload=options_payload,
        selection_payload=profile_payload,
        options_path=options_path,
        selection_path=profile_path,
    )
    scoreboard = build_active_scoreboard_from_gate_payload(gate, policy_gate_path=profile_path)
    next_kpi = build_audit_from_scoreboard_payload(
        scoreboard,
        minimum_ready_surfaces=minimum_ready_surfaces,
        minimum_strong_margin=minimum_strong_margin,
        require_matching_thresholds=bool(profile_payload.get("require_matching_thresholds", True)),
        scoreboard_path=None,
        policy_gate_path=profile_path,
    )
    return {
        "profile_path": str(profile_path.resolve()),
        "selection": {
            "name": profile_payload.get("name"),
            "allow_per_target_thresholds": bool(profile_payload.get("allow_per_target_thresholds")),
            "require_matching_thresholds": bool(profile_payload.get("require_matching_thresholds", True)),
            "notes": profile_payload.get("notes"),
        },
        "gate": gate,
        "active_scoreboard": scoreboard,
        "active_next_kpi": next_kpi,
    }


def build_profiles_matrix(
    *,
    options_payload: dict[str, Any],
    options_path: Path,
    profiles_dir: Path,
    current_selection_payload: dict[str, Any] | None,
    current_selection_path: Path | None,
    minimum_ready_surfaces: int,
    minimum_strong_margin: float,
) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    for profile_path in sorted(profiles_dir.glob("*.json")):
        profile_payload = _read_json(profile_path)
        profiles.append(
            _profile_payload(
                profile_payload=profile_payload,
                options_payload=options_payload,
                options_path=options_path,
                profile_path=profile_path,
                minimum_ready_surfaces=minimum_ready_surfaces,
                minimum_strong_margin=minimum_strong_margin,
            )
        )

    ready_profiles = []
    blocked_profiles = []
    active_like_profiles = []
    for profile in profiles:
        selection = dict(profile.get("selection") or {})
        next_kpi = dict((profile.get("active_next_kpi") or {}).get("decision") or {})
        gate_outcome = dict((profile.get("gate") or {}).get("outcome") or {})
        name = str(selection.get("name") or "")
        status = str(gate_outcome.get("status") or "")
        recommended_next_kpi = str(next_kpi.get("recommended_next_kpi") or "")
        if recommended_next_kpi == "broader_design_count":
            ready_profiles.append(name)
        elif recommended_next_kpi == "stabilize_existing_surfaces":
            blocked_profiles.append(name)
        elif status == "hold_current_v1":
            active_like_profiles.append(name)

    current_profile_name = None
    current_profile_classification = "unknown"
    if current_selection_payload is not None:
        raw_name = current_selection_payload.get("profile_name")
        if isinstance(raw_name, str) and raw_name.strip():
            current_profile_name = raw_name.strip()
            if current_profile_name in ready_profiles:
                current_profile_classification = "ready"
            elif current_profile_name in blocked_profiles:
                current_profile_classification = "blocked"
            elif current_profile_name in active_like_profiles:
                current_profile_classification = "active_like"

    return {
        "schema_version": 1,
        "scope": "campaign_threshold_policy_profiles",
        "options_path": str(options_path.resolve()),
        "profiles_dir": str(profiles_dir.resolve()),
        "current_selection_path": (
            str(current_selection_path.resolve()) if current_selection_path is not None else None
        ),
        "policy": {
            "minimum_ready_surfaces": minimum_ready_surfaces,
            "minimum_strong_margin": minimum_strong_margin,
        },
        "profiles": profiles,
        "summary": {
            "profile_count": len(profiles),
            "current_profile_name": current_profile_name,
            "current_profile_classification": current_profile_classification,
            "ready_profiles": ready_profiles,
            "blocked_profiles": blocked_profiles,
            "active_like_profiles": active_like_profiles,
            "recommended_decision_axis": "choose_named_policy_profile_before_editing_selection",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-options-json", type=Path, default=DEFAULT_OPTIONS_JSON)
    parser.add_argument("--profiles-dir", type=Path, default=DEFAULT_PROFILES_DIR)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--minimum-ready-surfaces", type=int, default=DEFAULT_MIN_READY_SURFACES)
    parser.add_argument("--minimum-strong-margin", type=float, default=DEFAULT_MIN_STRONG_MARGIN)
    args = parser.parse_args()

    options_path = args.policy_options_json.resolve()
    profiles_dir = args.profiles_dir.resolve()
    selection_path = args.selection_config.resolve()
    payload = build_profiles_matrix(
        options_payload=_read_json(options_path),
        options_path=options_path,
        profiles_dir=profiles_dir,
        current_selection_payload=_read_json(selection_path),
        current_selection_path=selection_path,
        minimum_ready_surfaces=args.minimum_ready_surfaces,
        minimum_strong_margin=args.minimum_strong_margin,
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
