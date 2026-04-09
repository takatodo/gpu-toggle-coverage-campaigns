#!/usr/bin/env python3
"""
Summarize the next breadth axis after the selected XuanTie same-family step has
been accepted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_BRANCH_CANDIDATES_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_breadth_branch_candidates.json"
DEFAULT_SAME_FAMILY_ACCEPTANCE_JSON = REPO_ROOT / "work" / "campaign_xuantie_same_family_acceptance_gate.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xuantie_same_family_next_axes.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_same_family_branch(payload: dict[str, Any]) -> dict[str, Any] | None:
    for row in payload.get("branch_candidates") or []:
        if str(row.get("profile_name") or "") == "xuantie_continue_same_family":
            return dict(row)
    return None


def build_axes(*, branch_candidates_payload: dict[str, Any], same_family_acceptance_payload: dict[str, Any]) -> dict[str, Any]:
    acceptance_outcome = dict(same_family_acceptance_payload.get("outcome") or {})
    decision = dict(branch_candidates_payload.get("decision") or {})
    same_family_branch = _find_same_family_branch(branch_candidates_payload) or {}
    accepted_design = str(acceptance_outcome.get("selected_design") or "")
    candidate_designs = [str(name) for name in same_family_branch.get("candidate_designs") or [] if str(name)]
    remaining_same_family_designs = [design for design in candidate_designs if design != accepted_design]

    if str(acceptance_outcome.get("status") or "") != "accepted_selected_same_family_step":
        decision_payload = {
            "status": "blocked_selected_same_family_step_not_accepted",
            "reason": "the_next_same_family_vs_fallback decision requires the selected same-family step to be accepted first",
            "recommended_next_task": acceptance_outcome.get("next_action") or "accept_selected_same_family_step",
        }
    elif remaining_same_family_designs:
        decision_payload = {
            "status": "decide_continue_to_remaining_same_family_design_vs_open_fallback_family",
            "reason": "the_selected_same_family_step_is_accepted_so_the_next_question_is_the_last_remaining_XuanTie_design_vs_the_fallback_family",
            "recommended_next_task": "choose_between_opening_the_next_same_family_design_and_switching_to_the_fallback_family",
            "recommended_same_family_design": remaining_same_family_designs[0],
        }
    else:
        decision_payload = {
            "status": "decide_move_to_fallback_family_after_same_family_exhaustion",
            "reason": "the_known_same_family_designs_are_exhausted_under_the_current_accepted_line",
            "recommended_next_task": "open_the_fallback_non_opentitan_family",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_xuantie_same_family_next_axes",
        "accepted_same_family_step": {
            "status": acceptance_outcome.get("status"),
            "selected_design": accepted_design or None,
            "selected_same_family_profile_name": acceptance_outcome.get("selected_same_family_profile_name"),
            "comparison_path": acceptance_outcome.get("comparison_path"),
            "speedup_ratio": acceptance_outcome.get("speedup_ratio"),
            "candidate_threshold_value": acceptance_outcome.get("candidate_threshold_value"),
        },
        "next_family_axis": {
            "remaining_same_family_designs": remaining_same_family_designs,
            "fallback_profile_name": decision.get("fallback_profile_name"),
            "fallback_family": "VeeR" if decision.get("fallback_profile_name") == "open_veer_fallback_family" else None,
        },
        "decision": decision_payload,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch-candidates-json", type=Path, default=DEFAULT_BRANCH_CANDIDATES_JSON)
    parser.add_argument("--same-family-acceptance-json", type=Path, default=DEFAULT_SAME_FAMILY_ACCEPTANCE_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_axes(
        branch_candidates_payload=_read_json(args.branch_candidates_json.resolve()),
        same_family_acceptance_payload=_read_json(args.same_family_acceptance_json.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
