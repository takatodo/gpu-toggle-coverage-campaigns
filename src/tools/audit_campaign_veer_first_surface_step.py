#!/usr/bin/env python3
"""
Summarize the current next step for the first VeeR fallback single-surface line.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_C910_RUNTIME_GATE_JSON = REPO_ROOT / "work" / "campaign_xuantie_c910_runtime_gate.json"
DEFAULT_VEER_FALLBACK_CANDIDATES_JSON = REPO_ROOT / "work" / "campaign_veer_fallback_candidates.json"
DEFAULT_DEFAULT_COMPARISON_JSON = REPO_ROOT / "output" / "validation" / "veer_eh1_time_to_threshold_comparison.json"
DEFAULT_THRESHOLD5_COMPARISON_JSON = (
    REPO_ROOT / "output" / "validation" / "veer_eh1_time_to_threshold_comparison_threshold5.json"
)
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_veer_first_surface_step.json"


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
        "path": str(Path(str(payload.get("runner_json") or ""))).strip() or None,
        "status": payload.get("status"),
        "comparison_ready": bool(payload.get("comparison_ready")),
        "winner": payload.get("winner"),
        "speedup_ratio": payload.get("speedup_ratio"),
        "threshold_value": threshold.get("value"),
    }


def build_status(
    *,
    c910_runtime_gate_payload: dict[str, Any] | None,
    veer_fallback_candidates_payload: dict[str, Any] | None,
    default_comparison_payload: dict[str, Any] | None,
    threshold5_comparison_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    gate_outcome = dict((c910_runtime_gate_payload or {}).get("outcome") or {})
    fallback_decision = dict((veer_fallback_candidates_payload or {}).get("decision") or {})
    active_runtime_profile = dict((c910_runtime_gate_payload or {}).get("selection") or {}).get("profile_name")
    selected_design = str(fallback_decision.get("recommended_first_design") or "")
    fallback_design = fallback_decision.get("fallback_design")

    default_summary = _comparison_summary(default_comparison_payload)
    threshold5_summary = _comparison_summary(threshold5_comparison_payload)
    if default_comparison_payload is not None:
        default_summary["path"] = str(DEFAULT_DEFAULT_COMPARISON_JSON.resolve())
    if threshold5_comparison_payload is not None:
        threshold5_summary["path"] = str(DEFAULT_THRESHOLD5_COMPARISON_JSON.resolve())

    runtime_status = str(gate_outcome.get("status") or "")
    if runtime_status != "open_fallback_family_ready":
        outcome = {
            "status": "blocked_veer_fallback_not_active",
            "reason": "the_current_checked_in_C910_runtime_branch_has_not_opened_the_VeeR_fallback_family",
            "next_action": gate_outcome.get("next_action") or "select_open_veer_fallback_family",
            "active_runtime_profile_name": active_runtime_profile,
        }
    elif selected_design != "VeeR-EH1":
        outcome = {
            "status": "blocked_unexpected_veer_first_design",
            "reason": "the_VeeR_fallback_candidates_artifact_does_not_currently_select_VeeR-EH1_as_the_first_surface",
            "next_action": fallback_decision.get("recommended_next_action")
            or "refresh_the_veer_fallback_candidate_inventory",
            "recommended_first_design": selected_design or None,
        }
    elif bool(default_summary["comparison_ready"]) and str(default_summary["winner"]) == "hybrid":
        outcome = {
            "status": "ready_to_accept_veer_eh1_default_gate",
            "reason": "VeeR-EH1 already has a checked-in default-gate hybrid win",
            "next_action": "accept_veer_eh1_as_the_first_fallback_surface",
            "selected_design": selected_design,
            "comparison_path": default_summary["path"],
            "speedup_ratio": default_summary["speedup_ratio"],
        }
    elif bool(threshold5_summary["comparison_ready"]) and str(threshold5_summary["winner"]) == "hybrid":
        outcome = {
            "status": "decide_veer_eh1_candidate_only_vs_new_default_gate",
            "reason": "VeeR-EH1 has a checked-in threshold=5 candidate-only hybrid win but the default gate line is unresolved",
            "next_action": "choose_between_accepting_the_threshold5_candidate_only_line_and_defining_a_new_default_gate",
            "selected_design": selected_design,
            "default_comparison_path": default_summary["path"],
            "candidate_comparison_path": threshold5_summary["path"],
            "candidate_threshold_value": threshold5_summary["threshold_value"],
            "speedup_ratio": threshold5_summary["speedup_ratio"],
        }
    elif default_comparison_payload is not None:
        outcome = {
            "status": "veer_eh1_default_gate_unresolved",
            "reason": "VeeR-EH1 comparison artifacts exist but the default gate line is not ready and no checked-in candidate-only win is available",
            "next_action": "define_a_new_default_gate_or_collect_candidate_only_evidence",
            "selected_design": selected_design,
            "default_comparison_path": default_summary["path"],
        }
    else:
        outcome = {
            "status": "run_veer_eh1_trio",
            "reason": "the_VeeR_fallback_family_is_active_but_VeeR-EH1_has_no_checked-in_comparison_artifact_yet",
            "next_action": "run_stock_hybrid_baseline_and_comparison_for_veer_eh1",
            "selected_design": selected_design,
        }

    return {
        "schema_version": 1,
        "scope": "campaign_veer_first_surface_step",
        "context": {
            "active_runtime_profile_name": active_runtime_profile,
            "active_runtime_status": runtime_status or None,
            "recommended_first_design": selected_design or None,
            "fallback_design": fallback_design,
        },
        "selected_design": {
            "design": selected_design or None,
            "default_comparison": default_summary,
            "threshold5_candidate": threshold5_summary,
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c910-runtime-gate-json", type=Path, default=DEFAULT_C910_RUNTIME_GATE_JSON)
    parser.add_argument("--veer-fallback-candidates-json", type=Path, default=DEFAULT_VEER_FALLBACK_CANDIDATES_JSON)
    parser.add_argument("--default-comparison-json", type=Path, default=DEFAULT_DEFAULT_COMPARISON_JSON)
    parser.add_argument("--threshold5-comparison-json", type=Path, default=DEFAULT_THRESHOLD5_COMPARISON_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_status(
        c910_runtime_gate_payload=_read_json(args.c910_runtime_gate_json.resolve()),
        veer_fallback_candidates_payload=_read_json(args.veer_fallback_candidates_json.resolve()),
        default_comparison_payload=_read_json(args.default_comparison_json.resolve()),
        threshold5_comparison_payload=_read_json(args.threshold5_comparison_json.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
