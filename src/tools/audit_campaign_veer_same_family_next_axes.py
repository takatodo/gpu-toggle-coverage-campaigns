#!/usr/bin/env python3
"""
Summarize the next same-family breadth axis after the selected VeeR same-family
step has been accepted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_VEER_FALLBACK_CANDIDATES_JSON = REPO_ROOT / "work" / "campaign_veer_fallback_candidates.json"
DEFAULT_VEER_SAME_FAMILY_ACCEPTANCE_JSON = REPO_ROOT / "work" / "campaign_veer_same_family_acceptance_gate.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_veer_same_family_next_axes.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_axes(*, veer_fallback_candidates_payload: dict[str, Any], veer_same_family_acceptance_payload: dict[str, Any]) -> dict[str, Any]:
    acceptance_outcome = dict(veer_same_family_acceptance_payload.get("outcome") or {})
    decision = dict(veer_fallback_candidates_payload.get("decision") or {})
    accepted_design = str(acceptance_outcome.get("selected_design") or "")
    ready_candidates = [str(name) for name in veer_fallback_candidates_payload.get("ready_candidates") or [] if str(name)]
    remaining_veer_designs = [design for design in ready_candidates if design not in {"VeeR-EH1", accepted_design}]

    if str(acceptance_outcome.get("status") or "") != "accepted_selected_veer_same_family_step":
        decision_payload = {
            "status": "blocked_selected_veer_same_family_step_not_accepted",
            "reason": "the_next_VeeR_same-family decision requires the selected VeeR same-family step to be accepted first",
            "recommended_next_task": acceptance_outcome.get("next_action") or "accept_selected_veer_same_family_step",
        }
    elif remaining_veer_designs:
        decision_payload = {
            "status": "decide_continue_to_remaining_veer_design",
            "reason": "the_selected_VeeR_same-family_step_is_accepted_so_the_next_question_is_the_next_remaining_VeeR_design",
            "recommended_next_task": "open_the_next_remaining_veer_design",
            "recommended_next_design": remaining_veer_designs[0],
        }
    else:
        decision_payload = {
            "status": "decide_leave_veer_family_after_exhaustion",
            "reason": "the_known_VeeR_ready_candidates_are_exhausted_under_the_current_accepted_line",
            "recommended_next_task": "open_a_new_non_opentitan_family_or_revisit_deeper_debug_branches",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_veer_same_family_next_axes",
        "accepted_veer_same_family_step": {
            "status": acceptance_outcome.get("status"),
            "selected_design": accepted_design or None,
            "selected_veer_same_family_profile_name": acceptance_outcome.get("selected_veer_same_family_profile_name"),
            "comparison_path": acceptance_outcome.get("comparison_path"),
            "speedup_ratio": acceptance_outcome.get("speedup_ratio"),
            "candidate_threshold_value": acceptance_outcome.get("candidate_threshold_value"),
        },
        "next_same_family_axis": {
            "remaining_veer_designs": remaining_veer_designs,
            "current_first_design": decision.get("recommended_first_design"),
            "current_fallback_design": decision.get("fallback_design"),
        },
        "decision": decision_payload,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--veer-fallback-candidates-json", type=Path, default=DEFAULT_VEER_FALLBACK_CANDIDATES_JSON)
    parser.add_argument("--veer-same-family-acceptance-json", type=Path, default=DEFAULT_VEER_SAME_FAMILY_ACCEPTANCE_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_axes(
        veer_fallback_candidates_payload=_read_json(args.veer_fallback_candidates_json.resolve()),
        veer_same_family_acceptance_payload=_read_json(args.veer_same_family_acceptance_json.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
