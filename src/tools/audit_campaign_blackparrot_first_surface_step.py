#!/usr/bin/env python3
"""
Summarize the current next step for the first BlackParrot post-OpenPiton surface.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_POST_OPENPITON_AXES_JSON = REPO_ROOT / "work" / "campaign_post_openpiton_axes.json"
DEFAULT_DEFAULT_COMPARISON_JSON = REPO_ROOT / "output" / "validation" / "blackparrot_time_to_threshold_comparison.json"
DEFAULT_THRESHOLD5_COMPARISON_JSON = (
    REPO_ROOT / "output" / "validation" / "blackparrot_time_to_threshold_comparison_threshold5.json"
)
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_blackparrot_first_surface_step.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _comparison_summary(path: Path, payload: dict[str, Any] | None) -> dict[str, Any]:
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
    post_openpiton_axes_payload: dict[str, Any] | None,
    default_comparison_payload: dict[str, Any] | None,
    threshold5_comparison_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    decision = dict((post_openpiton_axes_payload or {}).get("decision") or {})
    recommended_family = str(decision.get("recommended_family") or "")
    fallback_family = decision.get("fallback_family")

    default_summary = _comparison_summary(DEFAULT_DEFAULT_COMPARISON_JSON, default_comparison_payload)
    threshold5_summary = _comparison_summary(
        DEFAULT_THRESHOLD5_COMPARISON_JSON,
        threshold5_comparison_payload,
    )

    if recommended_family != "BlackParrot":
        outcome = {
            "status": "blocked_blackparrot_not_current_post_openpiton_family",
            "reason": "the_current_post_openpiton_axes_do_not_select_BlackParrot_as_the_active_family",
            "next_action": decision.get("recommended_next_task") or "refresh_post_openpiton_axes",
        }
    elif default_comparison_payload is None:
        outcome = {
            "status": "run_blackparrot_trio",
            "reason": "BlackParrot is the active post-OpenPiton family but no checked-in comparison exists yet",
            "next_action": "run_stock_hybrid_baseline_and_comparison_for_blackparrot",
        }
    elif bool(default_summary["comparison_ready"]) and str(default_summary["winner"]) == "hybrid":
        outcome = {
            "status": "ready_to_accept_blackparrot_default_gate",
            "reason": "BlackParrot now has a checked-in default-gate hybrid win",
            "next_action": "accept_blackparrot_as_the_next_post_openpiton_family_surface",
            "comparison_path": default_summary["path"],
            "speedup_ratio": default_summary["speedup_ratio"],
            "threshold_value": default_summary["threshold_value"],
        }
    elif bool(threshold5_summary["comparison_ready"]) and str(threshold5_summary["winner"]) == "hybrid":
        outcome = {
            "status": "decide_blackparrot_candidate_only_vs_new_default_gate",
            "reason": "BlackParrot has a checked-in threshold=5 candidate-only hybrid win but the default gate line is unresolved",
            "next_action": "choose_between_accepting_the_threshold5_candidate_only_line_and_defining_a_new_default_gate",
            "default_comparison_path": default_summary["path"],
            "candidate_comparison_path": threshold5_summary["path"],
            "candidate_threshold_value": threshold5_summary["threshold_value"],
            "speedup_ratio": threshold5_summary["speedup_ratio"],
        }
    elif bool(threshold5_summary["comparison_ready"]) and str(threshold5_summary["winner"]) == "baseline":
        outcome = {
            "status": "blackparrot_candidate_only_baseline_win",
            "reason": "BlackParrot reaches threshold=5 on both sides, but the checked-in candidate-only line still loses to the CPU baseline",
            "next_action": "open_the_next_family_after_blackparrot_baseline_loss",
            "default_comparison_path": default_summary["path"],
            "candidate_comparison_path": threshold5_summary["path"],
            "candidate_threshold_value": threshold5_summary["threshold_value"],
            "speedup_ratio": threshold5_summary["speedup_ratio"],
            "fallback_family": fallback_family,
        }
    elif bool(default_summary["comparison_ready"]) and str(default_summary["winner"]) == "baseline":
        outcome = {
            "status": "blackparrot_default_gate_baseline_win",
            "reason": "BlackParrot has a checked-in default-gate comparison and the current hybrid line loses to the CPU baseline",
            "next_action": "open_the_next_family_after_blackparrot_baseline_loss",
            "comparison_path": default_summary["path"],
            "speedup_ratio": default_summary["speedup_ratio"],
            "fallback_family": fallback_family,
        }
    else:
        outcome = {
            "status": "blackparrot_default_gate_unresolved",
            "reason": "BlackParrot comparison artifacts exist but the default gate line is not comparison-ready and no checked-in hybrid-winning candidate line exists",
            "next_action": "retune_blackparrot_or_open_the_next_family",
            "default_comparison_path": default_summary["path"],
            "candidate_comparison_path": threshold5_summary["path"],
        }

    return {
        "schema_version": 1,
        "scope": "campaign_blackparrot_first_surface_step",
        "context": {
            "recommended_family": recommended_family or None,
            "fallback_family": fallback_family,
            "upstream_status": decision.get("status"),
        },
        "selected_family": {
            "family": "BlackParrot",
            "default_comparison": default_summary,
            "threshold5_candidate": threshold5_summary,
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--post-openpiton-axes-json", type=Path, default=DEFAULT_POST_OPENPITON_AXES_JSON)
    parser.add_argument("--default-comparison-json", type=Path, default=DEFAULT_DEFAULT_COMPARISON_JSON)
    parser.add_argument("--threshold5-comparison-json", type=Path, default=DEFAULT_THRESHOLD5_COMPARISON_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_status(
        post_openpiton_axes_payload=_read_json(args.post_openpiton_axes_json.resolve()),
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
