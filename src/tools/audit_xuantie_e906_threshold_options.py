#!/usr/bin/env python3
"""
Summarize which numeric toggle_bits_hit thresholds remain viable for the checked
XuanTie-E906 workloads.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_CASE_VARIANTS_JSON = REPO_ROOT / "work" / "xuantie_e906_case_variants.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "xuantie_e906_threshold_options.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_threshold_options(*, case_variants_payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(case_variants_payload.get("summary") or {})
    threshold2_candidate = dict(case_variants_payload.get("threshold2_candidate") or {})
    current_default_thresholds = list(summary.get("default_threshold_values") or [])
    default_threshold = None
    if current_default_thresholds:
        raw_default = current_default_thresholds[0]
        if isinstance(raw_default, (int, float)) and not isinstance(raw_default, bool):
            default_threshold = int(raw_default)

    max_bits_hit = summary.get("max_stock_hybrid_bits_hit")
    if isinstance(max_bits_hit, bool) or not isinstance(max_bits_hit, (int, float)):
        max_bits_hit = None
    else:
        max_bits_hit = int(max_bits_hit)

    candidate_threshold_value = 2
    threshold2_ready = bool(threshold2_candidate.get("comparison_ready"))
    threshold2_hybrid_win = str(threshold2_candidate.get("winner") or "") == "hybrid"

    strongest_ready_numeric_threshold = None
    if threshold2_ready and threshold2_hybrid_win:
        strongest_ready_numeric_threshold = candidate_threshold_value

    blocked_numeric_thresholds: list[int] = []
    if isinstance(default_threshold, int) and isinstance(max_bits_hit, int):
        for threshold in range(max_bits_hit + 1, default_threshold + 1):
            blocked_numeric_thresholds.append(threshold)

    if strongest_ready_numeric_threshold is not None and blocked_numeric_thresholds:
        decision = {
            "status": "threshold2_is_strongest_ready_numeric_gate",
            "reason": "known_E906_workloads_plateau_at_bits_hit_2_so_any_numeric_gate_above_2_is_blocked",
            "recommended_next_task": "choose_between_promoting_threshold2_and_defining_a_non_cutoff_default_gate",
        }
    elif strongest_ready_numeric_threshold is not None:
        decision = {
            "status": "threshold2_ready_but_no_higher_numeric_gate_observed",
            "reason": "threshold2_is_ready_and_no_higher_numeric_cutoff_has_evidence",
            "recommended_next_task": "choose_between_promoting_threshold2_and_collecting_more_gate_evidence",
        }
    else:
        decision = {
            "status": "no_ready_numeric_gate",
            "reason": "no_checked_in_numeric_gate currently produces a comparison-ready hybrid win",
            "recommended_next_task": "define_a_new_default_gate_or_collect_more_E906_evidence",
        }

    return {
        "schema_version": 1,
        "scope": "xuantie_e906_threshold_options",
        "current_default_gate": {
            "threshold_value": default_threshold,
            "known_case_count": summary.get("case_count"),
            "max_bits_hit": max_bits_hit,
            "all_default_blocked": summary.get("all_default_blocked"),
        },
        "strongest_ready_numeric_gate": {
            "threshold_value": strongest_ready_numeric_threshold,
            "comparison_ready": threshold2_candidate.get("comparison_ready"),
            "winner": threshold2_candidate.get("winner"),
            "speedup_ratio": threshold2_candidate.get("speedup_ratio"),
            "comparison_path": threshold2_candidate.get("comparison_path"),
        },
        "blocked_numeric_thresholds": blocked_numeric_thresholds,
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-variants-json", type=Path, default=DEFAULT_CASE_VARIANTS_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_threshold_options(case_variants_payload=_read_json(args.case_variants_json.resolve()))
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
