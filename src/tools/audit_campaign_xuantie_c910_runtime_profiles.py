#!/usr/bin/env python3
"""
Evaluate named XuanTie-C910 runtime profiles independently of the current
checked-in selection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_campaign_xuantie_c910_runtime_gate import build_gate


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_RUNTIME_STATUS_JSON = REPO_ROOT / "work" / "campaign_xuantie_c910_runtime_status.json"
DEFAULT_SAME_FAMILY_NEXT_AXES_JSON = REPO_ROOT / "work" / "campaign_xuantie_same_family_next_axes.json"
DEFAULT_DEBUG_TACTICS_JSON = REPO_ROOT / "work" / "campaign_xuantie_c910_debug_tactics.json"
DEFAULT_PROFILES_DIR = REPO_ROOT / "config" / "campaign_xuantie_c910_runtime" / "profiles"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_xuantie_c910_runtime" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xuantie_c910_runtime_profiles.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_profiles_matrix(
    *,
    runtime_status_payload: dict[str, Any],
    same_family_next_axes_payload: dict[str, Any],
    debug_tactics_payload: dict[str, Any] | None,
    profiles_dir: Path,
    current_selection_payload: dict[str, Any] | None,
    current_selection_path: Path | None,
) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    for profile_path in sorted(profiles_dir.glob("*.json")):
        profile_payload = _read_json(profile_path)
        gate = build_gate(
            runtime_status_payload=runtime_status_payload,
            same_family_next_axes_payload=same_family_next_axes_payload,
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
                    "runtime_mode": profile_payload.get("runtime_mode"),
                    "design": profile_payload.get("design"),
                    "family": profile_payload.get("family"),
                    "notes": profile_payload.get("notes"),
                },
                "gate": gate,
            }
        )

    ready_profiles: list[str] = []
    hold_profiles: list[str] = []
    blocked_profiles: list[str] = []
    current_profile_name = None
    current_profile_classification = "unknown"
    for profile in profiles:
        selection = dict(profile.get("selection") or {})
        outcome = dict((profile.get("gate") or {}).get("outcome") or {})
        name = str(selection.get("name") or "")
        status = str(outcome.get("status") or "")
        if status in {"debug_c910_hybrid_runtime_ready", "open_fallback_family_ready", "c910_runtime_recovered_ready_to_compare_gate_policy"}:
            ready_profiles.append(name)
        elif status == "hold_c910_runtime_branch":
            hold_profiles.append(name)
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

    debug_decision = dict((debug_tactics_payload or {}).get("decision") or {})
    debug_recommended_tactic = str(debug_decision.get("recommended_next_tactic") or "")

    recommended_profile_name = None
    if (
        debug_recommended_tactic == "open_veer_fallback_family"
        and "open_veer_fallback_family" in ready_profiles
    ):
        recommended_profile_name = "open_veer_fallback_family"
    elif "debug_c910_hybrid_runtime" in ready_profiles:
        recommended_profile_name = "debug_c910_hybrid_runtime"
    elif "open_veer_fallback_family" in ready_profiles:
        recommended_profile_name = "open_veer_fallback_family"
    elif ready_profiles:
        recommended_profile_name = ready_profiles[0]

    recommended_decision_axis = "repair_c910_runtime_profiles"
    if recommended_profile_name is not None:
        if current_profile_classification == "ready" and current_profile_name == recommended_profile_name:
            recommended_decision_axis = "accept_current_c910_runtime_profile"
        else:
            recommended_decision_axis = "choose_named_c910_runtime_profile"

    return {
        "schema_version": 1,
        "scope": "campaign_xuantie_c910_runtime_profiles",
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
            "debug_tactic_recommended_next_tactic": debug_recommended_tactic or None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-status-json", type=Path, default=DEFAULT_RUNTIME_STATUS_JSON)
    parser.add_argument("--same-family-next-axes-json", type=Path, default=DEFAULT_SAME_FAMILY_NEXT_AXES_JSON)
    parser.add_argument("--debug-tactics-json", type=Path, default=DEFAULT_DEBUG_TACTICS_JSON)
    parser.add_argument("--profiles-dir", type=Path, default=DEFAULT_PROFILES_DIR)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    selection_path = args.selection_config.resolve()
    payload = build_profiles_matrix(
        runtime_status_payload=_read_json(args.runtime_status_json.resolve()),
        same_family_next_axes_payload=_read_json(args.same_family_next_axes_json.resolve()),
        debug_tactics_payload=(
            _read_json(args.debug_tactics_json.resolve())
            if args.debug_tactics_json.resolve().is_file()
            else None
        ),
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
