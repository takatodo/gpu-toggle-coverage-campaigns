#!/usr/bin/env python3
"""
Summarize the next breadth decision inside XuanTie after the OpenTitan
checkpoint and XuanTie-E902 seed have been accepted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_ACCEPTANCE_GATE_JSON = REPO_ROOT / "work" / "campaign_real_goal_acceptance_gate.json"
DEFAULT_ENTRY_READINESS_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_entry_readiness.json"
DEFAULT_OVERRIDE_CANDIDATES_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_override_candidates.json"
DEFAULT_E906_CASE_VARIANTS_JSON = REPO_ROOT / "work" / "xuantie_e906_case_variants.json"
DEFAULT_E906_THRESHOLD_OPTIONS_JSON = REPO_ROOT / "work" / "xuantie_e906_threshold_options.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xuantie_breadth_status.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_xuantie_breadth_status(
    *,
    acceptance_gate_payload: dict[str, Any],
    entry_readiness_payload: dict[str, Any],
    override_candidates_payload: dict[str, Any],
    e906_case_variants_payload: dict[str, Any],
    e906_threshold_options_payload: dict[str, Any],
) -> dict[str, Any]:
    acceptance_outcome = dict(acceptance_gate_payload.get("outcome") or {})
    readiness_decision = dict(entry_readiness_payload.get("decision") or {})
    override_decision = dict(override_candidates_payload.get("decision") or {})
    e906_decision = dict(e906_case_variants_payload.get("decision") or {})
    e906_summary = dict(e906_case_variants_payload.get("summary") or {})
    threshold2_candidate = dict(e906_case_variants_payload.get("threshold2_candidate") or {})
    threshold_options_decision = dict(e906_threshold_options_payload.get("decision") or {})
    strongest_ready_numeric_gate = dict(e906_threshold_options_payload.get("strongest_ready_numeric_gate") or {})

    acceptance_status = str(acceptance_outcome.get("status") or "")
    readiness = str(readiness_decision.get("readiness") or "")
    e906_status = str(e906_decision.get("status") or "")
    threshold2_ready = bool(threshold2_candidate.get("comparison_ready"))
    threshold2_hybrid_win = str(threshold2_candidate.get("winner") or "") == "hybrid"
    threshold_options_status = str(threshold_options_decision.get("status") or "")

    if acceptance_status != "accepted_checkpoint_and_seed":
        decision = {
            "status": "blocked_accept_checkpoint_and_seed_first",
            "reason": "the_project_has_not_yet_checked_in_the_current_checkpoint_and_selected_seed_as_the_baseline",
            "recommended_next_task": acceptance_outcome.get("next_action") or "accept_checkpoint_and_seed",
        }
    elif str(override_decision.get("recommended_design") or "") != "XuanTie-E902":
        decision = {
            "status": "blocked_unexpected_seed_order",
            "reason": "override_candidates_no_longer_rank_XuanTie_E902_as_the_accepted_seed",
            "recommended_next_task": "revalidate_xuantie_seed_order_before_breadth",
        }
    elif str(override_decision.get("fallback_design") or "") != "XuanTie-E906":
        decision = {
            "status": "blocked_unexpected_e906_fallback_order",
            "reason": "override_candidates_no_longer_rank_XuanTie_E906_as_the_next_breadth_candidate",
            "recommended_next_task": "recompute_xuantie_breadth_order",
        }
    elif (
        e906_status == "default_gate_blocked_across_known_case_pats"
        and threshold2_ready
        and threshold2_hybrid_win
        and threshold_options_status == "threshold2_is_strongest_ready_numeric_gate"
    ):
        if readiness == "legacy_family_pilot_failed_but_single_surface_override_ready":
            decision = {
                "status": "decide_threshold2_promotion_vs_non_cutoff_default_gate",
                "reason": "threshold2_is_the_strongest_ready_numeric_gate_for_E906_under_known_workloads_and_family_pilot_is_still_blocked",
                "recommended_next_task": "choose_between_promoting_threshold2_and_defining_a_non_cutoff_default_gate",
            }
        else:
            decision = {
                "status": "decide_threshold2_promotion_vs_non_cutoff_default_gate_or_family_pilot",
                "reason": "threshold2_is_the_strongest_ready_numeric_gate_for_E906_but_family_pilot_is_also_visible",
                "recommended_next_task": "choose_between_promoting_threshold2_defining_a_non_cutoff_default_gate_or_family_pilot",
            }
    elif e906_status == "default_gate_blocked_across_known_case_pats" and threshold2_ready and threshold2_hybrid_win:
        if readiness == "legacy_family_pilot_failed_but_single_surface_override_ready":
            decision = {
                "status": "decide_e906_candidate_only_vs_new_default_gate",
                "reason": "E906_default_gate_is_blocked_across_known_case_pats_but_a_candidate_only_threshold2_hybrid_win_exists_and_family_pilot_is_still_blocked",
                "recommended_next_task": "choose_between_candidate_only_e906_and_a_new_default_gate",
            }
        else:
            decision = {
                "status": "decide_e906_candidate_only_vs_new_default_gate_or_family_pilot",
                "reason": "E906_default_gate_is_blocked_but_candidate_only_and_family_pilot_branches_are_both_visible",
                "recommended_next_task": "choose_between_candidate_only_e906_new_default_gate_or_family_pilot",
            }
    elif e906_status == "default_gate_blocked_across_known_case_pats":
        decision = {
            "status": "define_new_e906_default_gate",
            "reason": "E906_default_gate_is_blocked_and_no_candidate_only_hybrid_win_is_available",
            "recommended_next_task": "define_new_e906_default_gate",
        }
    else:
        decision = {
            "status": "advance_e906_default_gate",
            "reason": "E906_is_not_blocked_under_the_current_default_gate",
            "recommended_next_task": "promote_E906_under_the_current_default_gate",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_xuantie_breadth_status",
        "accepted_seed": {
            "design": acceptance_outcome.get("selected_seed_design"),
            "profile_name": acceptance_outcome.get("selected_seed_profile_name"),
            "speedup_ratio": acceptance_outcome.get("selected_seed_speedup_ratio"),
        },
        "entry_context": {
            "entry_readiness": readiness or None,
            "recommended_design": override_decision.get("recommended_design"),
            "fallback_design": override_decision.get("fallback_design"),
        },
        "e906_default_gate": {
            "status": e906_status or None,
            "reason": e906_decision.get("reason"),
            "recommended_next_task": e906_decision.get("recommended_next_task"),
            "known_case_count": e906_summary.get("case_count"),
            "max_stock_hybrid_bits_hit": e906_summary.get("max_stock_hybrid_bits_hit"),
            "default_threshold_values": e906_summary.get("default_threshold_values"),
        },
        "e906_candidate_only_threshold2": {
            "comparison_ready": threshold2_candidate.get("comparison_ready"),
            "winner": threshold2_candidate.get("winner"),
            "speedup_ratio": threshold2_candidate.get("speedup_ratio"),
            "comparison_path": threshold2_candidate.get("comparison_path"),
        },
        "e906_threshold_options": {
            "decision_status": threshold_options_status or None,
            "strongest_ready_numeric_threshold": strongest_ready_numeric_gate.get("threshold_value"),
            "blocked_numeric_thresholds": e906_threshold_options_payload.get("blocked_numeric_thresholds"),
        },
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acceptance-gate-json", type=Path, default=DEFAULT_ACCEPTANCE_GATE_JSON)
    parser.add_argument("--entry-readiness-json", type=Path, default=DEFAULT_ENTRY_READINESS_JSON)
    parser.add_argument("--override-candidates-json", type=Path, default=DEFAULT_OVERRIDE_CANDIDATES_JSON)
    parser.add_argument("--e906-case-variants-json", type=Path, default=DEFAULT_E906_CASE_VARIANTS_JSON)
    parser.add_argument("--e906-threshold-options-json", type=Path, default=DEFAULT_E906_THRESHOLD_OPTIONS_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_xuantie_breadth_status(
        acceptance_gate_payload=_read_json(args.acceptance_gate_json.resolve()),
        entry_readiness_payload=_read_json(args.entry_readiness_json.resolve()),
        override_candidates_payload=_read_json(args.override_candidates_json.resolve()),
        e906_case_variants_payload=_read_json(args.e906_case_variants_json.resolve()),
        e906_threshold_options_payload=_read_json(args.e906_threshold_options_json.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
