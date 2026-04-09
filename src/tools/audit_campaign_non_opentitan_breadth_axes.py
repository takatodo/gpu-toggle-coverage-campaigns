#!/usr/bin/env python3
"""
Summarize the next branch after the accepted OpenTitan checkpoint, accepted
XuanTie-E902 seed, and accepted XuanTie-E906 breadth step.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_REAL_GOAL_ACCEPTANCE_JSON = REPO_ROOT / "work" / "campaign_real_goal_acceptance_gate.json"
DEFAULT_XUANTIE_BREADTH_ACCEPTANCE_JSON = REPO_ROOT / "work" / "campaign_xuantie_breadth_acceptance_gate.json"
DEFAULT_POST_CHECKPOINT_AXES_JSON = REPO_ROOT / "work" / "campaign_post_checkpoint_axes.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_non_opentitan_breadth_axes.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_axes(
    *,
    real_goal_acceptance_payload: dict[str, Any],
    xuantie_breadth_acceptance_payload: dict[str, Any],
    post_checkpoint_axes_payload: dict[str, Any],
) -> dict[str, Any]:
    real_goal_outcome = dict(real_goal_acceptance_payload.get("outcome") or {})
    breadth_outcome = dict(xuantie_breadth_acceptance_payload.get("outcome") or {})
    axes_decision = dict(post_checkpoint_axes_payload.get("decision") or {})
    inventory_rows = list(post_checkpoint_axes_payload.get("inventory_rows") or [])

    real_goal_status = str(real_goal_outcome.get("status") or "")
    breadth_status = str(breadth_outcome.get("status") or "")
    recommended_family = str(axes_decision.get("recommended_family") or "")
    fallback_family = ""

    accepted_seed_design = str(real_goal_outcome.get("selected_seed_design") or "")
    accepted_breadth_design = str(breadth_outcome.get("selected_breadth_design") or "")

    accepted_designs = [design for design in (accepted_seed_design, accepted_breadth_design) if design]
    family_member_designs: list[str] = []
    family_gpu_cov_tb_count = None
    non_opentitan_rows = [
        row for row in inventory_rows if not bool(row.get("is_active_repo_family")) and not bool(row.get("is_opentitan"))
    ]
    for index, family in enumerate(non_opentitan_rows):
        if str(family.get("repo_family") or "") == recommended_family:
            family_member_designs = [str(name) for name in family.get("raw_family_dirs") or [] if str(name)]
            family_gpu_cov_tb_count = family.get("design_count")
            if index + 1 < len(non_opentitan_rows):
                fallback_family = str(non_opentitan_rows[index + 1].get("repo_family") or "")
            break
    remaining_same_family_designs = [
        design for design in family_member_designs if design not in set(accepted_designs)
    ]

    if real_goal_status != "accepted_checkpoint_and_seed":
        decision = {
            "status": "blocked_checkpoint_seed_not_accepted",
            "reason": "the_OpenTitan_checkpoint_and_first_non_OpenTitan_seed_must_be_accepted_before_branching_further",
            "recommended_next_task": real_goal_outcome.get("next_action") or "accept_checkpoint_and_seed_baseline",
        }
    elif breadth_status != "accepted_selected_xuantie_breadth":
        decision = {
            "status": "blocked_selected_xuantie_breadth_not_accepted",
            "reason": "the_selected_XuanTie_breadth_step_has_not_been_accepted_as_the_current_non_OpenTitan_breadth_baseline",
            "recommended_next_task": breadth_outcome.get("next_action") or "accept_selected_xuantie_breadth",
        }
    elif recommended_family != "XuanTie":
        decision = {
            "status": "blocked_unexpected_recommended_family",
            "reason": "post_checkpoint_axes_no_longer_recommend_XuanTie_as_the_active_non_OpenTitan_family",
            "recommended_next_task": "recompute_non_opentitan_family_axis",
        }
    elif remaining_same_family_designs:
        decision = {
            "status": "decide_continue_xuantie_breadth_vs_open_fallback_family",
            "reason": "the_project_now_has_an_accepted_XuanTie_seed_and_an_accepted_XuanTie_breadth_step_so_the_next_question_is_same_family_breadth_vs_next_repo_family",
            "recommended_next_task": "choose_between_opening_another_XuanTie_single_surface_and_switching_to_the_fallback_family",
            "recommended_same_family_designs": remaining_same_family_designs,
        }
    else:
        decision = {
            "status": "decide_move_to_fallback_family",
            "reason": "the_known_XuanTie_member_designs_from_post_checkpoint_axes_are_exhausted_under_the_current_acceptance_line",
            "recommended_next_task": "open_the_fallback_non_opentitan_family",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_non_opentitan_breadth_axes",
        "accepted_baseline": {
            "real_goal_acceptance_status": real_goal_status,
            "selected_seed_design": accepted_seed_design or None,
            "xuantie_breadth_acceptance_status": breadth_status,
            "selected_breadth_design": accepted_breadth_design or None,
            "selected_breadth_profile_name": breadth_outcome.get("selected_breadth_profile_name"),
            "selected_breadth_comparison_path": breadth_outcome.get("comparison_path"),
            "selected_breadth_speedup_ratio": breadth_outcome.get("speedup_ratio"),
        },
        "recommended_family_axis": {
            "recommended_family": recommended_family or None,
            "fallback_family": fallback_family or None,
            "family_gpu_cov_tb_count": family_gpu_cov_tb_count,
            "family_member_designs": family_member_designs,
            "accepted_designs": accepted_designs,
            "remaining_same_family_designs": remaining_same_family_designs,
        },
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-goal-acceptance-json", type=Path, default=DEFAULT_REAL_GOAL_ACCEPTANCE_JSON)
    parser.add_argument(
        "--xuantie-breadth-acceptance-json",
        type=Path,
        default=DEFAULT_XUANTIE_BREADTH_ACCEPTANCE_JSON,
    )
    parser.add_argument("--post-checkpoint-axes-json", type=Path, default=DEFAULT_POST_CHECKPOINT_AXES_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_axes(
        real_goal_acceptance_payload=_read_json(args.real_goal_acceptance_json.resolve()),
        xuantie_breadth_acceptance_payload=_read_json(args.xuantie_breadth_acceptance_json.resolve()),
        post_checkpoint_axes_payload=_read_json(args.post_checkpoint_axes_json.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
