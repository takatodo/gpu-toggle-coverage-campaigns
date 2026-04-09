#!/usr/bin/env python3
"""
Evaluate named Vortex first-surface branch profiles independently of the current
checked-in selection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_campaign_vortex_first_surface_gate import build_gate


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_VORTEX_STATUS_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_status.json"
DEFAULT_POST_BLACKPARROT_AXES_JSON = REPO_ROOT / "work" / "campaign_post_blackparrot_axes.json"
DEFAULT_XIANGSHAN_STATUS_JSON = REPO_ROOT / "work" / "campaign_xiangshan_first_surface_status.json"
DEFAULT_DEBUG_TACTICS_JSON = REPO_ROOT / "work" / "campaign_vortex_debug_tactics.json"
DEFAULT_PROFILES_DIR = REPO_ROOT / "config" / "campaign_vortex_first_surface" / "profiles"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_vortex_first_surface" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_vortex_first_surface_profiles.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_profiles_matrix(
    *,
    vortex_status_payload: dict[str, Any],
    post_blackparrot_axes_payload: dict[str, Any],
    xiangshan_status_payload: dict[str, Any] | None,
    debug_tactics_payload: dict[str, Any] | None,
    profiles_dir: Path,
    current_selection_payload: dict[str, Any] | None,
    current_selection_path: Path | None,
) -> dict[str, Any]:
    profiles: list[dict[str, Any]] = []
    for profile_path in sorted(profiles_dir.glob("*.json")):
        profile_payload = _read_json(profile_path)
        gate = build_gate(
            vortex_status_payload=vortex_status_payload,
            post_blackparrot_axes_payload=post_blackparrot_axes_payload,
            xiangshan_status_payload=xiangshan_status_payload,
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
                    "branch_mode": profile_payload.get("branch_mode"),
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
        if status in {
            "debug_vortex_tls_lowering_ready",
            "reopen_xiangshan_fallback_ready",
            "vortex_gpu_build_recovered_ready_to_finish_trio",
        }:
            ready_profiles.append(name)
        elif status == "hold_vortex_first_surface_branch":
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

    vortex_outcome = dict(vortex_status_payload.get("outcome") or {})
    vortex_status = str(vortex_outcome.get("status") or "")
    debug_decision = dict((debug_tactics_payload or {}).get("decision") or {})
    debug_recommended_tactic = str(debug_decision.get("recommended_next_tactic") or "")

    recommended_profile_name = None
    if (
        debug_recommended_tactic == "reopen_xiangshan_fallback_family"
        and "reopen_xiangshan_fallback_family" in ready_profiles
    ):
        recommended_profile_name = "reopen_xiangshan_fallback_family"
    elif vortex_status == "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback":
        if "debug_vortex_tls_lowering" in ready_profiles:
            recommended_profile_name = "debug_vortex_tls_lowering"
        elif "reopen_xiangshan_fallback_family" in ready_profiles:
            recommended_profile_name = "reopen_xiangshan_fallback_family"
    elif vortex_status == "ready_to_finish_vortex_first_trio" and "debug_vortex_tls_lowering" in ready_profiles:
        recommended_profile_name = "debug_vortex_tls_lowering"
    elif ready_profiles:
        recommended_profile_name = ready_profiles[0]

    recommended_decision_axis = "repair_vortex_first_surface_profiles"
    if recommended_profile_name is not None:
        if current_profile_classification == "ready" and current_profile_name == recommended_profile_name:
            recommended_decision_axis = "accept_current_vortex_first_surface_profile"
        else:
            recommended_decision_axis = "choose_named_vortex_first_surface_profile"

    return {
        "schema_version": 1,
        "scope": "campaign_vortex_first_surface_profiles",
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
            "vortex_status": vortex_status or None,
            "debug_tactic_recommended_next_tactic": debug_recommended_tactic or None,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vortex-status-json", type=Path, default=DEFAULT_VORTEX_STATUS_JSON)
    parser.add_argument("--post-blackparrot-axes-json", type=Path, default=DEFAULT_POST_BLACKPARROT_AXES_JSON)
    parser.add_argument("--xiangshan-status-json", type=Path, default=DEFAULT_XIANGSHAN_STATUS_JSON)
    parser.add_argument("--debug-tactics-json", type=Path, default=DEFAULT_DEBUG_TACTICS_JSON)
    parser.add_argument("--profiles-dir", type=Path, default=DEFAULT_PROFILES_DIR)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    selection_path = args.selection_config.resolve()
    xiangshan_path = args.xiangshan_status_json.resolve()
    payload = build_profiles_matrix(
        vortex_status_payload=_read_json(args.vortex_status_json.resolve()),
        post_blackparrot_axes_payload=_read_json(args.post_blackparrot_axes_json.resolve()),
        xiangshan_status_payload=_read_json(xiangshan_path) if xiangshan_path.is_file() else None,
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
