#!/usr/bin/env python3
"""
Summarize the current next step after VeeR-EH1 is accepted as the first fallback-family surface.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_VEER_NEXT_AXES_JSON = REPO_ROOT / "work" / "campaign_veer_next_axes.json"
DEFAULT_DEFAULT_COMPARISON_JSON = REPO_ROOT / "output" / "validation" / "veer_eh2_time_to_threshold_comparison.json"
DEFAULT_THRESHOLD4_COMPARISON_JSON = (
    REPO_ROOT / "output" / "validation" / "veer_eh2_time_to_threshold_comparison_threshold4.json"
)
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_veer_same_family_step.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _comparison_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {
            "path": None,
            "status": None,
            "comparison_ready": False,
            "winner": None,
            "speedup_ratio": None,
            "threshold_value": None,
        }
    threshold = dict(payload.get("campaign_threshold") or {})
    return {
        "path": None,
        "status": payload.get("status"),
        "comparison_ready": bool(payload.get("comparison_ready")),
        "winner": payload.get("winner"),
        "speedup_ratio": payload.get("speedup_ratio"),
        "threshold_value": threshold.get("value"),
    }


def build_status(
    *,
    veer_next_axes_payload: dict[str, Any] | None,
    default_comparison_payload: dict[str, Any] | None,
    threshold4_comparison_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    accepted = dict((veer_next_axes_payload or {}).get("accepted_veer_first_surface_step") or {})
    decision = dict((veer_next_axes_payload or {}).get("decision") or {})
    next_axis = dict((veer_next_axes_payload or {}).get("next_same_family_axis") or {})

    selected_design = str(decision.get("recommended_next_design") or "")
    remaining_designs = list(next_axis.get("remaining_veer_designs") or [])
    fallback_design = remaining_designs[1] if len(remaining_designs) > 1 else None

    default_summary = _comparison_summary(default_comparison_payload)
    threshold4_summary = _comparison_summary(threshold4_comparison_payload)
    if default_comparison_payload is not None:
        default_summary["path"] = str(DEFAULT_DEFAULT_COMPARISON_JSON.resolve())
    if threshold4_comparison_payload is not None:
        threshold4_summary["path"] = str(DEFAULT_THRESHOLD4_COMPARISON_JSON.resolve())

    accepted_status = str(accepted.get("status") or "")
    decision_status = str(decision.get("status") or "")
    if accepted_status != "accepted_selected_veer_first_surface_step":
        outcome = {
            "status": "blocked_veer_first_surface_not_accepted",
            "reason": "the_first_VeeR_fallback_surface_has_not_been_checked_in_as_accepted_breadth_evidence",
            "next_action": "accept_veer_eh1_first_surface_step",
            "accepted_veer_first_surface_status": accepted_status or None,
        }
    elif decision_status != "decide_continue_to_remaining_veer_design":
        outcome = {
            "status": "blocked_veer_next_axes_not_ready",
            "reason": "the_veer_next_axes_artifact_is_not_ready_to_select_the_next_remaining_design",
            "next_action": decision.get("recommended_next_task") or "recompute_veer_next_axes",
            "veer_next_axes_status": decision_status or None,
        }
    elif selected_design != "VeeR-EH2":
        outcome = {
            "status": "blocked_unexpected_veer_same_family_design",
            "reason": "the_current_veer_next_axes_artifact_does_not_select_VeeR-EH2_as_the_next_same_family_surface",
            "next_action": "refresh_veer_next_axes",
            "recommended_next_design": selected_design or None,
        }
    elif bool(default_summary["comparison_ready"]) and str(default_summary["winner"]) == "hybrid":
        outcome = {
            "status": "ready_to_accept_veer_eh2_default_gate",
            "reason": "VeeR-EH2 already has a checked-in default-gate hybrid win",
            "next_action": "accept_veer_eh2_as_the_next_same_family_surface",
            "selected_design": selected_design,
            "comparison_path": default_summary["path"],
            "speedup_ratio": default_summary["speedup_ratio"],
        }
    elif bool(threshold4_summary["comparison_ready"]) and str(threshold4_summary["winner"]) == "hybrid":
        outcome = {
            "status": "decide_veer_eh2_candidate_only_vs_new_default_gate",
            "reason": "VeeR-EH2 has a checked-in threshold=4 candidate-only hybrid win but the default gate line is unresolved",
            "next_action": "choose_between_accepting_the_threshold4_candidate_only_line_and_defining_a_new_default_gate",
            "selected_design": selected_design,
            "default_comparison_path": default_summary["path"],
            "candidate_comparison_path": threshold4_summary["path"],
            "candidate_threshold_value": threshold4_summary["threshold_value"],
            "speedup_ratio": threshold4_summary["speedup_ratio"],
        }
    elif default_comparison_payload is not None:
        outcome = {
            "status": "veer_eh2_default_gate_unresolved",
            "reason": "VeeR-EH2 comparison artifacts exist but the default gate line is not ready and no checked-in candidate-only win is available",
            "next_action": "define_a_new_default_gate_or_collect_candidate_only_evidence",
            "selected_design": selected_design,
            "default_comparison_path": default_summary["path"],
        }
    else:
        outcome = {
            "status": "run_veer_eh2_trio",
            "reason": "the_next_remaining_VeeR_design_is_selected_but_its_checked-in_trio_is_missing",
            "next_action": "run_stock_hybrid_baseline_and_comparison_for_veer_eh2",
            "selected_design": selected_design,
        }

    return {
        "schema_version": 1,
        "scope": "campaign_veer_same_family_step",
        "context": {
            "accepted_veer_first_surface_status": accepted_status or None,
            "current_first_design": next_axis.get("current_first_design"),
            "selected_design": selected_design or None,
            "fallback_design": fallback_design,
        },
        "selected_design": {
            "design": selected_design or None,
            "default_comparison": default_summary,
            "threshold4_candidate": threshold4_summary,
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--veer-next-axes-json", type=Path, default=DEFAULT_VEER_NEXT_AXES_JSON)
    parser.add_argument("--default-comparison-json", type=Path, default=DEFAULT_DEFAULT_COMPARISON_JSON)
    parser.add_argument("--threshold4-comparison-json", type=Path, default=DEFAULT_THRESHOLD4_COMPARISON_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_status(
        veer_next_axes_payload=_read_json(args.veer_next_axes_json.resolve()),
        default_comparison_payload=_read_json(args.default_comparison_json.resolve()),
        threshold4_comparison_payload=_read_json(args.threshold4_comparison_json.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
