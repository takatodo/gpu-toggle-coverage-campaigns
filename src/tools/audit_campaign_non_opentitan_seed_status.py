#!/usr/bin/env python3
"""
Summarize whether the selected non-OpenTitan entry profile is ready to be
accepted as the first seed beyond the OpenTitan checkpoint baseline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_CHECKPOINT_JSON = REPO_ROOT / "work" / "campaign_checkpoint_readiness.json"
DEFAULT_POST_CHECKPOINT_AXES_JSON = REPO_ROOT / "work" / "campaign_post_checkpoint_axes.json"
DEFAULT_ENTRY_GATE_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_entry_gate.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_non_opentitan_seed_status.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_seed_status(
    *,
    checkpoint_payload: dict[str, Any],
    post_checkpoint_payload: dict[str, Any],
    entry_gate_payload: dict[str, Any],
) -> dict[str, Any]:
    checkpoint_decision = dict(checkpoint_payload.get("decision") or {})
    checkpoint_summary = dict(checkpoint_payload.get("summary") or {})
    axes_decision = dict(post_checkpoint_payload.get("decision") or {})
    active_line = dict(post_checkpoint_payload.get("current_active_line") or {})
    gate_selection = dict(entry_gate_payload.get("selection") or {})
    gate_outcome = dict(entry_gate_payload.get("outcome") or {})

    checkpoint_status = str(checkpoint_decision.get("readiness") or "")
    recommended_axis = str(axes_decision.get("recommended_next_axis") or "")
    entry_status = str(gate_outcome.get("status") or "")

    decision: dict[str, Any]
    if checkpoint_status != "cross_family_checkpoint_ready":
        decision = {
            "status": "blocked_checkpoint_not_ready",
            "reason": "current_opentitan_checkpoint_has_not_reached_cross_family_checkpoint_ready",
            "recommended_next_task": "stabilize_current_checkpoint",
        }
    elif recommended_axis != "broaden_non_opentitan_family":
        decision = {
            "status": "blocked_wrong_expansion_axis",
            "reason": "post_checkpoint_axis_is_not_currently_broaden_non_opentitan_family",
            "recommended_next_task": "follow_post_checkpoint_axis_before_opening_non_opentitan_seed",
        }
    elif entry_status == "single_surface_trio_ready":
        decision = {
            "status": "ready_to_accept_selected_seed",
            "reason": "selected_non_opentitan_profile_already_has_checked_in_campaign_trio_and_hybrid_win",
            "recommended_next_task": "accept_selected_non_opentitan_seed",
        }
    elif entry_status == "single_surface_ready":
        decision = {
            "status": "ready_to_implement_selected_seed_trio",
            "reason": "selected_non_opentitan_profile_is_bootstrap_ready_but_missing_campaign_trio",
            "recommended_next_task": "implement_selected_non_opentitan_campaign_trio",
        }
    elif entry_status == "family_pilot_ready":
        decision = {
            "status": "ready_to_run_selected_family_pilot",
            "reason": "selected_non_opentitan_family_pilot_is_executable",
            "recommended_next_task": "run_selected_family_pilot",
        }
    else:
        decision = {
            "status": "blocked_on_selected_entry_profile",
            "reason": entry_status or "selected_non_opentitan_entry_profile_is_not_ready",
            "recommended_next_task": gate_outcome.get("next_action") or "repair_selected_entry_profile",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_non_opentitan_seed_status",
        "checkpoint": {
            "status": checkpoint_status,
            "reason": checkpoint_decision.get("reason"),
            "active_surface_count": checkpoint_summary.get("active_surface_count"),
            "weakest_hybrid_win": checkpoint_summary.get("weakest_hybrid_win"),
        },
        "post_checkpoint_axis": {
            "recommended_next_axis": recommended_axis,
            "recommended_family": axes_decision.get("recommended_family"),
            "repo_family_count": active_line.get("repo_family_count"),
            "repo_families": active_line.get("repo_families"),
        },
        "selected_entry": {
            "profile_name": gate_selection.get("profile_name"),
            "profile_path": gate_selection.get("profile_path"),
            "status": entry_status,
            "design": gate_outcome.get("design"),
            "fallback_design": gate_outcome.get("fallback_design"),
            "comparison_path": gate_outcome.get("comparison_path"),
            "speedup_ratio": gate_outcome.get("speedup_ratio"),
        },
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-json", type=Path, default=DEFAULT_CHECKPOINT_JSON)
    parser.add_argument("--post-checkpoint-axes-json", type=Path, default=DEFAULT_POST_CHECKPOINT_AXES_JSON)
    parser.add_argument("--entry-gate-json", type=Path, default=DEFAULT_ENTRY_GATE_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_seed_status(
        checkpoint_payload=_read_json(args.checkpoint_json.resolve()),
        post_checkpoint_payload=_read_json(args.post_checkpoint_axes_json.resolve()),
        entry_gate_payload=_read_json(args.entry_gate_json.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
