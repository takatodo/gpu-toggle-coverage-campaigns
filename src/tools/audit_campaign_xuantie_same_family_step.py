#!/usr/bin/env python3
"""
Summarize the current next step after the project chooses the
`xuantie_continue_same_family` post-E906 breadth branch.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_BREADTH_GATE_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_breadth_gate.json"
DEFAULT_BRANCH_CANDIDATES_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_breadth_branch_candidates.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xuantie_same_family_step.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_same_family_branch(payload: dict[str, Any]) -> dict[str, Any] | None:
    for row in payload.get("branch_candidates") or []:
        if str(row.get("profile_name") or "") == "xuantie_continue_same_family":
            return dict(row)
    return None


def _find_design_row(candidate: dict[str, Any], design: str | None) -> dict[str, Any] | None:
    if not design:
        return None
    for row in candidate.get("design_rows") or []:
        if str(row.get("design") or "") == design:
            return dict(row)
    return None


def _build_outcome(*, branch_gate_payload: dict[str, Any], branch_candidates_payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    gate_outcome = dict(branch_gate_payload.get("outcome") or {})
    gate_selection = dict(branch_gate_payload.get("selection") or {})
    decision = dict(branch_candidates_payload.get("decision") or {})
    same_family_candidate = _find_same_family_branch(branch_candidates_payload)

    branch_status = str(gate_outcome.get("status") or "")
    if branch_status != "continue_same_family_ready":
        return (
            {
                "status": "blocked_same_family_branch_not_active",
                "reason": "the_current_checked_in_post_E906_branch_is_not_the_same_family_branch",
                "next_action": gate_outcome.get("next_action") or "select_xuantie_continue_same_family",
                "active_branch_profile_name": gate_selection.get("profile_name"),
            },
            None,
        )

    recommended_profile_name = str(decision.get("recommended_profile_name") or "")
    if recommended_profile_name != "xuantie_continue_same_family" or same_family_candidate is None:
        return (
            {
                "status": "blocked_same_family_candidate_summary_missing",
                "reason": "the_branch_candidates_artifact_does_not_currently_support_the_selected_same_family_branch",
                "next_action": "recompute_same_family_branch_candidates",
                "recommended_profile_name": decision.get("recommended_profile_name"),
            },
            None,
        )

    selected_design = str(
        same_family_candidate.get("recommended_first_design")
        or decision.get("recommended_first_design")
        or ""
    )
    if not selected_design:
        return (
            {
                "status": "blocked_no_selected_same_family_design",
                "reason": "the_same_family_branch_is_active_but_no_first_design_is_recommended",
                "next_action": "choose_the_next_same_family_design",
            },
            same_family_candidate,
        )

    design_row = _find_design_row(same_family_candidate, selected_design)
    if design_row is None:
        return (
            {
                "status": "blocked_selected_same_family_design_missing",
                "reason": "the_selected_same_family_design_is_not_present_in_the_branch_candidates_artifact",
                "next_action": "repair_same_family_branch_candidate_inventory",
                "selected_design": selected_design,
            },
            same_family_candidate,
        )

    validated_line_kind = str(design_row.get("validated_line_kind") or "")
    best_ready_path = design_row.get("best_ready_comparison_path")
    best_ready_threshold_value = design_row.get("best_ready_threshold_value")
    best_ready_speedup_ratio = design_row.get("best_ready_speedup_ratio")

    if validated_line_kind == "default_gate_hybrid_win":
        return (
            {
                "status": "ready_to_accept_selected_same_family_design",
                "reason": "the_selected_same_family_design_already_has_a_default_gate_hybrid_win",
                "next_action": "accept_selected_same_family_design",
                "selected_design": selected_design,
                "comparison_path": best_ready_path,
                "speedup_ratio": best_ready_speedup_ratio,
            },
            design_row,
        )

    if validated_line_kind == "candidate_only_hybrid_win":
        return (
            {
                "status": "decide_selected_same_family_design_candidate_only_vs_new_default_gate",
                "reason": "the_selected_same_family_design_has_a_ready_candidate_only_hybrid_win_but_the_default_gate_line_is_not_ready",
                "next_action": "choose_between_accepting_the_candidate_only_line_and_defining_a_new_default_gate",
                "selected_design": selected_design,
                "comparison_path": best_ready_path,
                "candidate_threshold_value": best_ready_threshold_value,
                "speedup_ratio": best_ready_speedup_ratio,
            },
            design_row,
        )

    if validated_line_kind == "comparison_exists_but_not_ready":
        return (
            {
                "status": "selected_same_family_design_default_gate_unresolved",
                "reason": "comparison_artifacts_exist_but_the_selected_same_family_design_does_not_yet_have_a_ready_hybrid_win",
                "next_action": "define_a_new_default_gate_or_expand_the_known_workload_set",
                "selected_design": selected_design,
                "default_comparison_path": design_row.get("default_comparison_path"),
            },
            design_row,
        )

    if all(
        bool(design_row.get(field))
        for field in (
            "stock_hybrid_runner_exists",
            "cpu_baseline_runner_exists",
            "comparison_runner_exists",
        )
    ):
        return (
            {
                "status": "run_selected_same_family_design_trio",
                "reason": "the_selected_same_family_design_has_the_runner_trio_but_no_checked_in_comparison_artifact",
                "next_action": "run_stock_hybrid_baseline_and_comparison_for_the_selected_same_family_design",
                "selected_design": selected_design,
            },
            design_row,
        )

    return (
        {
            "status": "bootstrap_selected_same_family_design",
            "reason": "the_selected_same_family_design_still_lacks_the_full_single_surface_runner_trio",
            "next_action": "bootstrap_the_selected_same_family_design_into_a_stock_hybrid_trio",
            "selected_design": selected_design,
        },
        design_row,
    )


def build_status(*, branch_gate_payload: dict[str, Any], branch_candidates_payload: dict[str, Any]) -> dict[str, Any]:
    outcome, selected_design_row = _build_outcome(
        branch_gate_payload=branch_gate_payload,
        branch_candidates_payload=branch_candidates_payload,
    )
    gate_selection = dict(branch_gate_payload.get("selection") or {})
    gate_context = dict(branch_gate_payload.get("context") or {})
    decision = dict(branch_candidates_payload.get("decision") or {})

    return {
        "schema_version": 1,
        "scope": "campaign_xuantie_same_family_step",
        "context": {
            "active_branch_profile_name": gate_selection.get("profile_name"),
            "active_branch_status": dict(branch_gate_payload.get("outcome") or {}).get("status"),
            "selected_seed_design": gate_context.get("selected_seed_design"),
            "selected_breadth_design": gate_context.get("selected_breadth_design"),
            "branch_recommended_first_design": decision.get("recommended_first_design"),
        },
        "selected_design": {
            "design": selected_design_row.get("design") if selected_design_row else None,
            "validated_line_kind": selected_design_row.get("validated_line_kind") if selected_design_row else None,
            "default_comparison_path": selected_design_row.get("default_comparison_path") if selected_design_row else None,
            "default_comparison_ready": selected_design_row.get("default_comparison_ready") if selected_design_row else None,
            "default_winner": selected_design_row.get("default_winner") if selected_design_row else None,
            "best_ready_comparison_path": selected_design_row.get("best_ready_comparison_path") if selected_design_row else None,
            "best_ready_threshold_value": selected_design_row.get("best_ready_threshold_value") if selected_design_row else None,
            "best_ready_speedup_ratio": selected_design_row.get("best_ready_speedup_ratio") if selected_design_row else None,
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--breadth-gate-json", type=Path, default=DEFAULT_BREADTH_GATE_JSON)
    parser.add_argument("--branch-candidates-json", type=Path, default=DEFAULT_BRANCH_CANDIDATES_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_status(
        branch_gate_payload=_read_json(args.breadth_gate_json.resolve()),
        branch_candidates_payload=_read_json(args.branch_candidates_json.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
