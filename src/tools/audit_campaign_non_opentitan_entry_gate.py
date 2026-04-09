#!/usr/bin/env python3
"""
Resolve the currently selected non-OpenTitan entry profile against the current
entry-readiness and single-surface override artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_ENTRY_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_entry.json"
DEFAULT_ENTRY_READINESS_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_entry_readiness.json"
DEFAULT_OVERRIDE_CANDIDATES_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_override_candidates.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_non_opentitan_entry" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_non_opentitan_entry_gate.json"


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
        raise FileNotFoundError(f"non-OpenTitan entry profile not found: {profile_path}")
    return normalized_name, profile_path, _read_json(profile_path)


def _candidate_by_design(override_payload: dict[str, Any], design: str) -> dict[str, Any] | None:
    for row in list(override_payload.get("ranked_candidates") or []):
        if str(row.get("design") or "") == design:
            return dict(row)
    return None


def _build_outcome(
    *,
    profile_payload: dict[str, Any],
    entry_payload: dict[str, Any],
    readiness_payload: dict[str, Any],
    override_payload: dict[str, Any],
) -> dict[str, Any]:
    family = str(profile_payload.get("family") or "")
    entry_mode = str(profile_payload.get("entry_mode") or "")
    readiness = str((readiness_payload.get("decision") or {}).get("readiness") or "")
    recommended_family = str((entry_payload.get("decision") or {}).get("recommended_family") or "")
    decision_reason = str((readiness_payload.get("decision") or {}).get("reason") or "")

    if family and recommended_family and family != recommended_family:
        return {
            "status": "blocked_wrong_family",
            "reason": "selected_profile_family_does_not_match_current_recommended_family",
            "next_action": "align_profile_family_with_current_non_opentitan_axis",
        }

    if entry_mode == "family_pilot":
        if readiness in {"ready_to_run_family_pilot", "pilot_artifact_already_present"}:
            return {
                "status": "family_pilot_ready",
                "reason": "selected_family_pilot_is_executable_in_current_workspace",
                "next_action": "run_xuantie_family_pilot",
            }
        return {
            "status": "family_pilot_blocked",
            "reason": decision_reason or "selected_family_pilot_is_not_executable",
            "next_action": "restore_legacy_bench_or_switch_profile",
        }

    if entry_mode == "single_surface":
        design = str(profile_payload.get("design") or "")
        fallback_design = str(profile_payload.get("fallback_design") or "")
        candidate = _candidate_by_design(override_payload, design)
        if candidate is not None and bool(candidate.get("hybrid_wins")):
            return {
                "status": "single_surface_trio_ready",
                "reason": "selected_single_surface_override_has_checked_in_campaign_trio_and_hybrid_win",
                "next_action": "accept_non_opentitan_campaign_trio",
                "design": design,
                "fallback_design": fallback_design or None,
                "bootstrap_path": candidate.get("path"),
                "comparison_path": candidate.get("comparison_path"),
                "speedup_ratio": candidate.get("speedup_ratio"),
            }
        if candidate is not None and bool(candidate.get("ready")):
            return {
                "status": "single_surface_ready",
                "reason": "selected_single_surface_override_has_ready_stock_verilator_bootstrap",
                "next_action": "implement_non_opentitan_campaign_trio",
                "design": design,
                "fallback_design": fallback_design or None,
                "bootstrap_path": candidate.get("path"),
            }
        return {
            "status": "single_surface_blocked",
            "reason": "selected_single_surface_override_design_is_not_ready",
            "next_action": "pick_ready_override_candidate_or_revert_profile",
            "design": design or None,
            "fallback_design": fallback_design or None,
        }

    return {
        "status": "blocked_unknown_entry_mode",
        "reason": f"unsupported entry_mode: {entry_mode}",
        "next_action": "fix_profile_definition",
    }


def build_gate(
    *,
    entry_payload: dict[str, Any],
    readiness_payload: dict[str, Any],
    override_payload: dict[str, Any],
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
        entry_payload=entry_payload,
        readiness_payload=readiness_payload,
        override_payload=override_payload,
    )
    return {
        "schema_version": 1,
        "scope": "campaign_non_opentitan_entry_gate",
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()),
            "notes": selection_payload.get("notes"),
        },
        "context": {
            "recommended_family": (entry_payload.get("decision") or {}).get("recommended_family"),
            "recommended_entry_mode": (entry_payload.get("decision") or {}).get("recommended_entry_mode"),
            "entry_readiness": (readiness_payload.get("decision") or {}).get("readiness"),
            "override_recommended_design": (override_payload.get("decision") or {}).get("recommended_design"),
            "override_fallback_design": (override_payload.get("decision") or {}).get("fallback_design"),
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry-json", type=Path, default=DEFAULT_ENTRY_JSON)
    parser.add_argument("--entry-readiness-json", type=Path, default=DEFAULT_ENTRY_READINESS_JSON)
    parser.add_argument("--override-candidates-json", type=Path, default=DEFAULT_OVERRIDE_CANDIDATES_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_gate(
        entry_payload=_read_json(args.entry_json.resolve()),
        readiness_payload=_read_json(args.entry_readiness_json.resolve()),
        override_payload=_read_json(args.override_candidates_json.resolve()),
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
