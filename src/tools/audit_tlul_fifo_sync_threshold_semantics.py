#!/usr/bin/env python3
"""
Summarize tlul_fifo_sync threshold-semantics candidates from checked-in comparison artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_SEQ1 = REPO_ROOT / "output" / "validation" / "tlul_fifo_sync_time_to_threshold_comparison_seq1_threshold24.json"
DEFAULT_SEQ10 = REPO_ROOT / "output" / "validation" / "tlul_fifo_sync_time_to_threshold_comparison_threshold24.json"
DEFAULT_SEQ101 = REPO_ROOT / "output" / "validation" / "tlul_fifo_sync_time_to_threshold_comparison_seq101_threshold24.json"
DEFAULT_SEQ1010 = REPO_ROOT / "output" / "validation" / "tlul_fifo_sync_time_to_threshold_comparison_seq1010_threshold24.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "tlul_fifo_sync_threshold_semantics_audit.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _case_summary(*, label: str, clock_sequence: list[int], path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    hybrid = dict(payload.get("hybrid") or {})
    baseline = dict(payload.get("baseline") or {})
    hybrid_measurement = dict(hybrid.get("campaign_measurement") or {})
    baseline_measurement = dict(baseline.get("campaign_measurement") or {})
    return {
        "label": label,
        "clock_sequence": list(clock_sequence),
        "comparison_path": str(path.resolve()),
        "campaign_threshold": dict(payload.get("campaign_threshold") or {}),
        "comparison_ready": bool(payload.get("comparison_ready")),
        "winner": payload.get("winner"),
        "speedup_ratio": payload.get("speedup_ratio"),
        "hybrid_measurement": hybrid_measurement,
        "baseline_measurement": baseline_measurement,
    }


def build_audit(
    *,
    seq1_path: Path,
    seq10_path: Path,
    seq101_path: Path,
    seq1010_path: Path,
) -> dict[str, Any]:
    seq1 = _case_summary(label="seq1_threshold24", clock_sequence=[1], path=seq1_path)
    seq10 = _case_summary(label="seq10_threshold24", clock_sequence=[1, 0], path=seq10_path)
    seq101 = _case_summary(label="seq101_threshold24", clock_sequence=[1, 0, 1], path=seq101_path)
    seq1010 = _case_summary(label="seq1010_threshold24", clock_sequence=[1, 0, 1, 0], path=seq1010_path)
    cases = [seq1, seq10, seq101, seq1010]

    first_flip_case = None
    for case in cases[1:]:
        if case["comparison_ready"] and case["winner"] == "baseline":
            first_flip_case = {
                "label": case["label"],
                "clock_sequence": list(case["clock_sequence"]),
                "speedup_ratio": case["speedup_ratio"],
            }
            break

    recommended_action = "collect_more_sequence_cases"
    reason = "no_sequence_extension_flip_observed"
    recommended_next_tasks = [
        "Add more tlul_fifo_sync sequence candidates before changing the threshold semantics decision.",
    ]

    strongest_positive_case = None
    for case in cases:
        if case["comparison_ready"] and case["winner"] == "hybrid":
            if strongest_positive_case is None or float(case["speedup_ratio"]) > float(strongest_positive_case["speedup_ratio"]):
                strongest_positive_case = {
                    "label": case["label"],
                    "clock_sequence": list(case["clock_sequence"]),
                    "speedup_ratio": case["speedup_ratio"],
                }

    if seq10["comparison_ready"] and seq10["winner"] == "hybrid" and first_flip_case is not None:
        recommended_action = "evaluate_minimal_progress_sequence_semantics"
        reason = "longer_sequence_flips_winner_to_baseline_while_shorter_sequence_strengthens_hybrid"
        recommended_next_tasks = [
            "Do not use longer host-clock sequences as the stronger threshold semantics for tlul_fifo_sync.",
            "Treat the shortest progress-enabling sequence as the next design-specific candidate semantics to evaluate.",
            "Define a stronger threshold semantics that is not equivalent to extending the checked-in 1,0 replay depth.",
            "Keep tlul_fifo_sync on the current checked-in comparison surface until that new semantics exists.",
        ]

    return {
        "schema_version": 1,
        "scope": "tlul_fifo_sync_threshold_semantics_audit",
        "target": "tlul_fifo_sync",
        "cases": cases,
        "summary": {
            "strongest_positive_case": strongest_positive_case,
            "positive_reference_case": {
                "label": seq10["label"],
                "clock_sequence": list(seq10["clock_sequence"]),
                "winner": seq10["winner"],
                "speedup_ratio": seq10["speedup_ratio"],
            },
            "first_sequence_extension_flip": first_flip_case,
            "recommended_action": recommended_action,
            "reason": reason,
            "recommended_next_tasks": recommended_next_tasks,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seq1", type=Path, default=DEFAULT_SEQ1)
    parser.add_argument("--seq10", type=Path, default=DEFAULT_SEQ10)
    parser.add_argument("--seq101", type=Path, default=DEFAULT_SEQ101)
    parser.add_argument("--seq1010", type=Path, default=DEFAULT_SEQ1010)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_audit(
        seq1_path=args.seq1.resolve(),
        seq10_path=args.seq10.resolve(),
        seq101_path=args.seq101.resolve(),
        seq1010_path=args.seq1010.resolve(),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
