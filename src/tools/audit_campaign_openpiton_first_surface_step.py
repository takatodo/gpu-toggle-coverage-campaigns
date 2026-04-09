#!/usr/bin/env python3
"""
Summarize the current next step for the first OpenPiton fallback single-surface line.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_XIANGSHAN_STATUS_JSON = REPO_ROOT / "work" / "campaign_xiangshan_first_surface_status.json"
DEFAULT_COMPARISON_JSON = REPO_ROOT / "output" / "validation" / "openpiton_time_to_threshold_comparison.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_openpiton_first_surface_step.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def build_status(
    *,
    xiangshan_status_payload: dict[str, Any] | None,
    comparison_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    upstream = dict((xiangshan_status_payload or {}).get("outcome") or {})
    upstream_axes = dict((xiangshan_status_payload or {}).get("upstream_axes") or {})
    fallback_family = upstream_axes.get("fallback_family")

    comparison_summary = {
        "path": str(DEFAULT_COMPARISON_JSON.resolve()) if comparison_payload is not None else None,
        "status": (comparison_payload or {}).get("status"),
        "comparison_ready": bool((comparison_payload or {}).get("comparison_ready")),
        "winner": (comparison_payload or {}).get("winner"),
        "speedup_ratio": (comparison_payload or {}).get("speedup_ratio"),
        "threshold_value": dict((comparison_payload or {}).get("campaign_threshold") or {}).get("value"),
    }

    if fallback_family != "OpenPiton":
        outcome = {
            "status": "blocked_openpiton_not_current_fallback_family",
            "reason": "the_upstream_non_veer_axes_do_not_currently_point_to_OpenPiton_as_the_active_fallback_family",
            "next_action": upstream.get("next_action") or "refresh_the_post_veer_family_axes",
        }
    elif comparison_payload is None:
        outcome = {
            "status": "run_openpiton_trio",
            "reason": "OpenPiton is the active fallback family but no checked-in comparison artifact exists yet",
            "next_action": "run_stock_hybrid_baseline_and_comparison_for_openpiton",
        }
    elif bool(comparison_summary["comparison_ready"]) and str(comparison_summary["winner"]) == "hybrid":
        outcome = {
            "status": "ready_to_accept_openpiton_default_gate",
            "reason": "OpenPiton now has a checked-in default-gate hybrid win on the first fallback surface",
            "next_action": "accept_openpiton_as_the_next_non_veer_family_surface",
            "comparison_path": comparison_summary["path"],
            "speedup_ratio": comparison_summary["speedup_ratio"],
            "threshold_value": comparison_summary["threshold_value"],
        }
    elif bool(comparison_summary["comparison_ready"]) and str(comparison_summary["winner"]) == "baseline":
        outcome = {
            "status": "openpiton_default_gate_baseline_win",
            "reason": "OpenPiton default-gate artifacts exist but the current checked-in hybrid shape still loses to the CPU baseline",
            "next_action": "retune_the_openpiton_hybrid_shape_or_hold_openpiton_out_of_breadth_evidence",
            "comparison_path": comparison_summary["path"],
            "speedup_ratio": comparison_summary["speedup_ratio"],
        }
    else:
        outcome = {
            "status": "openpiton_default_gate_unresolved",
            "reason": "OpenPiton comparison artifacts exist but the default gate line is not comparison-ready yet",
            "next_action": "define_a_candidate_only_line_or_adjust_the_default_gate",
            "comparison_path": comparison_summary["path"],
        }

    return {
        "schema_version": 1,
        "scope": "campaign_openpiton_first_surface_step",
        "context": {
            "upstream_status": upstream.get("status"),
            "fallback_family": fallback_family,
            "recommended_family": upstream_axes.get("recommended_family"),
        },
        "selected_family": {
            "family": "OpenPiton",
            "default_comparison": comparison_summary,
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xiangshan-status-json", type=Path, default=DEFAULT_XIANGSHAN_STATUS_JSON)
    parser.add_argument("--comparison-json", type=Path, default=DEFAULT_COMPARISON_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_status(
        xiangshan_status_payload=_read_json(args.xiangshan_status_json.resolve()),
        comparison_payload=_read_json(args.comparison_json.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
