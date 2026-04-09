#!/usr/bin/env python3
"""
Resolve the currently selected XuanTie breadth profile against the accepted
checkpoint/seed baseline and the current E906 evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_BREADTH_STATUS_JSON = REPO_ROOT / "work" / "campaign_xuantie_breadth_status.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_xuantie_breadth" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xuantie_breadth_gate.json"


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
        raise FileNotFoundError(f"campaign XuanTie breadth profile not found: {profile_path}")
    return normalized_name, profile_path, _read_json(profile_path)


def _build_outcome(
    *,
    profile_payload: dict[str, Any],
    breadth_status_payload: dict[str, Any],
) -> dict[str, Any]:
    breadth_mode = str(profile_payload.get("breadth_mode") or "")
    decision = dict(breadth_status_payload.get("decision") or {})
    e906_default_gate = dict(breadth_status_payload.get("e906_default_gate") or {})
    threshold2_candidate = dict(breadth_status_payload.get("e906_candidate_only_threshold2") or {})
    entry_context = dict(breadth_status_payload.get("entry_context") or {})

    decision_status = str(decision.get("status") or "")
    default_gate_status = str(e906_default_gate.get("status") or "")
    entry_readiness = str(entry_context.get("entry_readiness") or "")
    threshold2_ready = bool(threshold2_candidate.get("comparison_ready"))
    threshold2_hybrid_win = str(threshold2_candidate.get("winner") or "") == "hybrid"
    threshold2_value = profile_payload.get("candidate_threshold_value")

    if breadth_mode == "default_gate_hold":
        if default_gate_status == "default_gate_blocked_across_known_case_pats":
            return {
                "status": "default_gate_hold",
                "reason": "selected_profile_keeps_E906_on_the_current_blocked_default_gate",
                "next_action": "choose_candidate_only_or_define_new_default_gate",
                "default_threshold_values": e906_default_gate.get("default_threshold_values"),
                "known_case_count": e906_default_gate.get("known_case_count"),
            }
        return {
            "status": "default_gate_ready",
            "reason": "E906_is_no_longer_blocked_under_the_current_default_gate",
            "next_action": "promote_E906_under_the_current_default_gate",
        }

    if breadth_mode == "candidate_only_threshold":
        if decision_status in {
            "decide_e906_candidate_only_vs_new_default_gate",
            "decide_e906_candidate_only_vs_new_default_gate_or_family_pilot",
            "decide_threshold2_promotion_vs_non_cutoff_default_gate",
            "decide_threshold2_promotion_vs_non_cutoff_default_gate_or_family_pilot",
        } and threshold2_ready and threshold2_hybrid_win:
            return {
                "status": "candidate_only_ready",
                "reason": "selected_profile_accepts_the_checked_in_E906_threshold2_hybrid_win_as_the_next_breadth_step",
                "next_action": "accept_e906_candidate_only_breadth_step",
                "comparison_path": threshold2_candidate.get("comparison_path"),
                "speedup_ratio": threshold2_candidate.get("speedup_ratio"),
                "candidate_threshold_value": threshold2_value,
            }
        return {
            "status": "candidate_only_blocked",
            "reason": "selected_profile_requires_a_checked_in_E906_candidate_only_hybrid_win_that_is_not_currently_available",
            "next_action": decision.get("recommended_next_task") or "repair_E906_candidate_only_line",
        }

    if breadth_mode == "family_pilot_recovery":
        if entry_readiness == "ready_to_run_family_pilot":
            return {
                "status": "family_pilot_ready",
                "reason": "selected_profile_returns_to_a_now-executable_XuanTie_family_pilot",
                "next_action": "run_xuantie_family_pilot",
            }
        return {
            "status": "family_pilot_blocked",
            "reason": "selected_profile_returns_to_XuanTie_family_pilot_but_the_legacy_bench_path_is_still_blocked",
            "next_action": "restore_legacy_bench_before_returning_to_family_pilot",
        }

    return {
        "status": "blocked_unknown_breadth_mode",
        "reason": f"unsupported breadth_mode: {breadth_mode}",
        "next_action": "fix_campaign_xuantie_breadth_profile",
    }


def build_gate(
    *,
    breadth_status_payload: dict[str, Any],
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
        breadth_status_payload=breadth_status_payload,
    )
    accepted_seed = dict(breadth_status_payload.get("accepted_seed") or {})
    return {
        "schema_version": 1,
        "scope": "campaign_xuantie_breadth_gate",
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()),
            "breadth_mode": profile_payload.get("breadth_mode"),
            "design": profile_payload.get("design"),
            "family": profile_payload.get("family"),
            "notes": selection_payload.get("notes"),
        },
        "context": {
            "accepted_seed_design": accepted_seed.get("design"),
            "accepted_seed_profile_name": accepted_seed.get("profile_name"),
            "breadth_decision_status": (breadth_status_payload.get("decision") or {}).get("status"),
            "entry_readiness": (breadth_status_payload.get("entry_context") or {}).get("entry_readiness"),
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--breadth-status-json", type=Path, default=DEFAULT_BREADTH_STATUS_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_gate(
        breadth_status_payload=_read_json(args.breadth_status_json.resolve()),
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
