#!/usr/bin/env python3
"""
Summarize which campaign-threshold policy branches are active, blocked, or ready.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_PREVIEW_JSON = REPO_ROOT / "work" / "campaign_threshold_policy_preview.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_policy_decision_readiness.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _variant_branch(
    *,
    branch_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    gate = dict(payload.get("gate") or {})
    outcome = dict(gate.get("outcome") or {})
    scoreboard = dict(payload.get("active_scoreboard") or {})
    scoreboard_summary = dict(scoreboard.get("summary") or {})
    next_kpi = dict(payload.get("active_next_kpi") or {})
    decision = dict(next_kpi.get("decision") or {})
    recommendation = str(decision.get("recommended_next_kpi") or "")
    reason = str(decision.get("reason") or "")

    blockers: list[str] = []
    status = "informational"
    readiness = "unknown"

    if branch_name == "current_selection":
        status = "active"
        readiness = "checked_in_current_line"
        if recommendation == "stronger_thresholds":
            blockers.append("need_stronger_threshold_v2")
    elif recommendation == "stabilize_existing_surfaces" and reason == "threshold_schema_mismatch":
        status = "blocked"
        readiness = "blocked_by_threshold_schema_mismatch"
        blockers.append("threshold_schema_mismatch")
    elif recommendation == "broader_design_count":
        status = "ready"
        readiness = "ready_if_policy_is_checked_in"
    elif recommendation == "stronger_thresholds":
        status = "candidate"
        readiness = "needs_stronger_semantics"
        blockers.append("need_stronger_threshold_v2")
    else:
        status = "candidate"
        readiness = "needs_manual_review"

    return {
        "name": branch_name,
        "policy": {
            "allow_per_target_thresholds": bool(payload.get("allow_per_target_thresholds")),
            "require_matching_thresholds": bool(payload.get("require_matching_thresholds")),
        },
        "status": status,
        "readiness": readiness,
        "blockers": blockers,
        "selected_scenario_name": outcome.get("selected_scenario_name"),
        "selected_policy_mode": outcome.get("selected_policy_mode"),
        "selected_thresholds": list(outcome.get("selected_thresholds") or []),
        "comparison_ready_count": int(scoreboard_summary.get("comparison_ready_count") or 0),
        "hybrid_win_count": int(scoreboard_summary.get("hybrid_win_count") or 0),
        "all_thresholds_match": bool(scoreboard_summary.get("all_thresholds_match")),
        "weakest_hybrid_win": dict(scoreboard_summary.get("weakest_hybrid_win") or {}),
        "recommended_next_kpi": recommendation,
        "decision_reason": reason,
        "recommended_next_tasks": list(decision.get("recommended_next_tasks") or []),
    }


def build_readiness(*, preview_payload: dict[str, Any], preview_path: Path) -> dict[str, Any]:
    variants = dict(preview_payload.get("variants") or {})
    current = _variant_branch(branch_name="current_selection", payload=dict(variants.get("current_selection") or {}))
    flip_allow = _variant_branch(
        branch_name="flip_allow_per_target",
        payload=dict(variants.get("flip_allow_per_target") or {}),
    )
    flip_both = _variant_branch(branch_name="flip_both", payload=dict(variants.get("flip_both") or {}))

    decisive_question = "decide_if_campaign_v2_allows_threshold_schema_mismatch"
    recommended_active_task = "define_new_common_stronger_threshold_semantics"
    recommended_next_tasks = [
        "Decide whether campaign v2 allows threshold-schema mismatch across targets.",
        "If yes, check in the design-specific v2 policy and regenerate the active campaign artifacts.",
        "If no, keep common v1 active and define a new common stronger-threshold semantics.",
    ]
    if current.get("recommended_next_kpi") == "broader_design_count":
        decisive_question = "policy_already_checked_in"
        recommended_active_task = "add_next_comparison_surface"
        recommended_next_tasks = [
            "Keep the current policy-aware active campaign line stable.",
            "Choose and add the next comparison surface under the active policy.",
            "Only revisit stronger common semantics after the next surface is checked in.",
        ]
    elif (
        flip_allow.get("readiness") == "blocked_by_threshold_schema_mismatch"
        and flip_both.get("readiness") == "ready_if_policy_is_checked_in"
    ):
        decisive_question = "decide_if_campaign_v2_allows_threshold_schema_mismatch"
    elif flip_both.get("readiness") == "ready_if_policy_is_checked_in":
        decisive_question = "decide_if_campaign_v2_checks_in_design_specific_thresholds"
    else:
        decisive_question = "define_new_common_stronger_threshold_semantics"
        recommended_active_task = "define_new_common_stronger_threshold_semantics"

    return {
        "schema_version": 1,
        "scope": "campaign_policy_decision_readiness",
        "preview_path": str(preview_path.resolve()),
        "summary": {
            "current_line": current.get("selected_scenario_name"),
            "current_status": current.get("status"),
            "current_next_kpi": current.get("recommended_next_kpi"),
            "decisive_policy_question": decisive_question,
            "flip_allow_blocked_by_threshold_schema_mismatch": (
                flip_allow.get("readiness") == "blocked_by_threshold_schema_mismatch"
            ),
            "flip_both_ready_for_checkin": flip_both.get("readiness") == "ready_if_policy_is_checked_in",
            "recommended_active_task": (
                recommended_active_task
                if current.get("recommended_next_kpi") == "broader_design_count"
                else (
                    "decide_policy_before_defining_new_v2_threshold"
                    if flip_both.get("readiness") == "ready_if_policy_is_checked_in"
                    else "define_new_common_stronger_threshold_semantics"
                )
            ),
        },
        "branches": [
            current,
            flip_allow,
            flip_both,
        ],
        "recommended_next_tasks": recommended_next_tasks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview-json", type=Path, default=DEFAULT_PREVIEW_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    preview_path = args.preview_json.resolve()
    payload = build_readiness(preview_payload=_read_json(preview_path), preview_path=preview_path)
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
