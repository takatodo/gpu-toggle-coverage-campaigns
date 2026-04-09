#!/usr/bin/env python3
"""
Resolve the selected post-E906 non-OpenTitan breadth profile against the
current accepted XuanTie breadth baseline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_BREADTH_AXES_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_breadth_axes.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_non_opentitan_breadth" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_non_opentitan_breadth_gate.json"


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
        raise FileNotFoundError(f"campaign non-OpenTitan breadth profile not found: {profile_path}")
    return normalized_name, profile_path, _read_json(profile_path)


def _build_outcome(
    *,
    profile_payload: dict[str, Any],
    breadth_axes_payload: dict[str, Any],
) -> dict[str, Any]:
    branch_mode = str(profile_payload.get("branch_mode") or "")
    profile_family = str(profile_payload.get("family") or "")
    decision = dict(breadth_axes_payload.get("decision") or {})
    family_axis = dict(breadth_axes_payload.get("recommended_family_axis") or {})

    decision_status = str(decision.get("status") or "")
    recommended_family = str(family_axis.get("recommended_family") or "")
    fallback_family = str(family_axis.get("fallback_family") or "")
    remaining_same_family_designs = [
        str(design) for design in family_axis.get("remaining_same_family_designs") or [] if str(design)
    ]

    if branch_mode == "hold_post_e906_branch":
        return {
            "status": "hold_post_e906_branch",
            "reason": "selected_profile_keeps_the_post_E906_non_opentitan_branch_in_pre_selection_state",
            "next_action": decision.get("recommended_next_task") or "choose_post_e906_branch",
            "decision_status": decision_status or None,
        }

    if branch_mode == "continue_same_family":
        if (
            decision_status == "decide_continue_xuantie_breadth_vs_open_fallback_family"
            and profile_family == recommended_family
            and remaining_same_family_designs
        ):
            return {
                "status": "continue_same_family_ready",
                "reason": "selected_profile_accepts_the_current_same_family_breadth_branch_after_the_accepted_XuanTie_seed_and_E906_step",
                "next_action": "choose_the_next_same_family_design",
                "family": recommended_family,
                "remaining_same_family_designs": remaining_same_family_designs,
            }
        return {
            "status": "continue_same_family_blocked",
            "reason": "selected_profile_requests_same_family_breadth_but_the_current_axes_artifact_does_not_support_that_branch",
            "next_action": decision.get("recommended_next_task") or "recompute_post_e906_branch",
        }

    if branch_mode == "open_fallback_family":
        if (
            decision_status == "decide_continue_xuantie_breadth_vs_open_fallback_family"
            and profile_family
            and profile_family == fallback_family
        ):
            return {
                "status": "open_fallback_family_ready",
                "reason": "selected_profile_accepts_switching_to_the_current_fallback_non_opentitan_family",
                "next_action": "open_fallback_non_opentitan_family",
                "family": fallback_family,
            }
        return {
            "status": "open_fallback_family_blocked",
            "reason": "selected_profile_requests_a_fallback_family_that_is_not_currently_available",
            "next_action": decision.get("recommended_next_task") or "recompute_post_e906_branch",
        }

    return {
        "status": "blocked_unknown_branch_mode",
        "reason": f"unsupported branch_mode: {branch_mode}",
        "next_action": "fix_campaign_non_opentitan_breadth_profile",
    }


def build_gate(
    *,
    breadth_axes_payload: dict[str, Any],
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
        breadth_axes_payload=breadth_axes_payload,
    )
    accepted_baseline = dict(breadth_axes_payload.get("accepted_baseline") or {})
    decision = dict(breadth_axes_payload.get("decision") or {})

    return {
        "schema_version": 1,
        "scope": "campaign_non_opentitan_breadth_gate",
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()),
            "branch_mode": profile_payload.get("branch_mode"),
            "family": profile_payload.get("family"),
            "notes": selection_payload.get("notes"),
        },
        "context": {
            "selected_seed_design": accepted_baseline.get("selected_seed_design"),
            "selected_breadth_design": accepted_baseline.get("selected_breadth_design"),
            "selected_breadth_profile_name": accepted_baseline.get("selected_breadth_profile_name"),
            "decision_status": decision.get("status"),
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--breadth-axes-json", type=Path, default=DEFAULT_BREADTH_AXES_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_gate(
        breadth_axes_payload=_read_json(args.breadth_axes_json.resolve()),
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
