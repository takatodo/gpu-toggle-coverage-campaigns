#!/usr/bin/env python3
"""
Summarize the current next step for the first Vortex single-surface line.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_STATUS_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_status.json"
DEFAULT_DEFAULT_COMPARISON_JSON = REPO_ROOT / "output" / "validation" / "vortex_time_to_threshold_comparison.json"
DEFAULT_THRESHOLD4_COMPARISON_JSON = (
    REPO_ROOT / "output" / "validation" / "vortex_time_to_threshold_comparison_threshold4.json"
)
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_vortex_first_surface_step.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _comparison_summary(payload: dict[str, Any] | None, *, path: Path) -> dict[str, Any]:
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
        "path": str(path.resolve()),
        "status": payload.get("status"),
        "comparison_ready": bool(payload.get("comparison_ready")),
        "winner": payload.get("winner"),
        "speedup_ratio": payload.get("speedup_ratio"),
        "threshold_value": threshold.get("value"),
    }


def build_status(
    *,
    vortex_status_payload: dict[str, Any] | None,
    default_comparison_payload: dict[str, Any] | None,
    threshold4_comparison_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    vortex_outcome = dict((vortex_status_payload or {}).get("outcome") or {})
    vortex_status = str(vortex_outcome.get("status") or "")
    default_summary = _comparison_summary(
        default_comparison_payload,
        path=DEFAULT_DEFAULT_COMPARISON_JSON,
    )
    threshold4_summary = _comparison_summary(
        threshold4_comparison_payload,
        path=DEFAULT_THRESHOLD4_COMPARISON_JSON,
    )

    if vortex_status != "ready_to_finish_vortex_first_trio":
        outcome = {
            "status": "blocked_vortex_first_surface_not_ready",
            "reason": "the_current_checked-in_Vortex_branch_is_not_yet_ready_to_finish_the_first_trio",
            "next_action": vortex_outcome.get("next_action") or "continue_vortex_first_surface_recovery",
        }
    elif bool(default_summary["comparison_ready"]) and str(default_summary["winner"]) == "hybrid":
        outcome = {
            "status": "ready_to_accept_vortex_default_gate",
            "reason": "Vortex already has a checked-in default-gate hybrid win",
            "next_action": "accept_vortex_as_the_current_non_opentitan_surface",
            "comparison_path": default_summary["path"],
            "speedup_ratio": default_summary["speedup_ratio"],
            "selected_design": "Vortex",
        }
    elif bool(threshold4_summary["comparison_ready"]) and str(threshold4_summary["winner"]) == "hybrid":
        outcome = {
            "status": "decide_vortex_candidate_only_vs_new_default_gate",
            "reason": "Vortex has a checked-in threshold=4 candidate-only hybrid win but the default gate line is unresolved",
            "next_action": "choose_between_accepting_the_threshold4_candidate_only_line_and_defining_a_new_default_gate",
            "default_comparison_path": default_summary["path"],
            "candidate_comparison_path": threshold4_summary["path"],
            "candidate_threshold_value": threshold4_summary["threshold_value"],
            "speedup_ratio": threshold4_summary["speedup_ratio"],
            "selected_design": "Vortex",
        }
    elif default_comparison_payload is not None:
        outcome = {
            "status": "vortex_default_gate_unresolved",
            "reason": "Vortex comparison artifacts exist but the default gate line is not ready and no checked-in candidate-only win is available",
            "next_action": "define_a_new_default_gate_or_collect_candidate_only_evidence",
            "default_comparison_path": default_summary["path"],
            "selected_design": "Vortex",
        }
    else:
        outcome = {
            "status": "run_vortex_trio",
            "reason": "Vortex GPU recovery is ready but the comparison artifacts are not checked in yet",
            "next_action": "run_stock_hybrid_baseline_and_comparison_for_vortex",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_vortex_first_surface_step",
        "context": {
            "vortex_status": vortex_status or None,
            "next_action": vortex_outcome.get("next_action"),
        },
        "selected_design": {
            "design": "Vortex",
            "default_comparison": default_summary,
            "threshold4_candidate": threshold4_summary,
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-json", type=Path, default=DEFAULT_STATUS_JSON)
    parser.add_argument("--default-comparison-json", type=Path, default=DEFAULT_DEFAULT_COMPARISON_JSON)
    parser.add_argument("--threshold4-comparison-json", type=Path, default=DEFAULT_THRESHOLD4_COMPARISON_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_status(
        vortex_status_payload=_read_json(args.status_json.resolve()),
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
