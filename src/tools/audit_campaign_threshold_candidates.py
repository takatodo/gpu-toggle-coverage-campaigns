#!/usr/bin/env python3
"""
Compare checked-in and candidate campaign-threshold scoreboards and recommend
whether any candidate is strong enough to replace the current checked-in line.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_SCOREBOARDS = [
    REPO_ROOT / "work" / "campaign_speed_scoreboard.json",
    REPO_ROOT / "work" / "campaign_speed_scoreboard_threshold5.json",
]
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_threshold_candidate_matrix.json"
DEFAULT_MIN_READY_SURFACES = 2
DEFAULT_MIN_STRONG_MARGIN = 2.0


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _label_for_path(path: Path, *, index: int) -> str:
    stem = path.stem
    if index == 0:
        return "checked_in_v1"
    prefix = "campaign_speed_scoreboard_"
    if stem.startswith(prefix):
        return stem.removeprefix(prefix)
    return stem


def _parse_threshold_key(key: str | None) -> dict[str, Any] | None:
    if key is None:
        return None
    parts = key.split(":", 2)
    if len(parts) != 3:
        return None
    kind, raw_value, aggregation = parts
    try:
        value: int | str = int(raw_value)
    except ValueError:
        value = raw_value
    return {
        "kind": kind,
        "value": value,
        "aggregation": aggregation,
    }


def _row_from_scoreboard(
    scoreboard_path: Path,
    *,
    index: int,
    minimum_ready_surfaces: int,
    minimum_strong_margin: float,
) -> dict[str, Any]:
    payload = _read_json(scoreboard_path)
    summary = dict(payload.get("summary") or {})
    threshold_keys = list(summary.get("threshold_keys") or [])
    threshold_key = threshold_keys[0] if len(threshold_keys) == 1 else None
    threshold = _parse_threshold_key(threshold_key)
    ready = int(summary.get("comparison_ready_count") or 0)
    wins = int(summary.get("hybrid_win_count") or 0)
    all_thresholds_match = bool(summary.get("all_thresholds_match"))
    weakest = dict(summary.get("weakest_hybrid_win") or {})
    weakest_ratio_raw = weakest.get("speedup_ratio")
    weakest_ratio = float(weakest_ratio_raw) if isinstance(weakest_ratio_raw, (int, float)) else None
    eligible = ready >= minimum_ready_surfaces and all_thresholds_match and wins == ready and weakest_ratio is not None
    promotable = bool(eligible and weakest_ratio is not None and weakest_ratio >= minimum_strong_margin)
    if index == 0:
        candidate_status = "checked_in"
    elif promotable:
        candidate_status = "promotable_v2"
    elif eligible:
        candidate_status = "candidate_only"
    else:
        candidate_status = "invalid_candidate"
    return {
        "label": _label_for_path(scoreboard_path, index=index),
        "scoreboard_path": str(scoreboard_path.resolve()),
        "threshold_key": threshold_key,
        "threshold": threshold,
        "comparison_ready_count": ready,
        "hybrid_win_count": wins,
        "total_comparisons": int(summary.get("total_comparisons") or 0),
        "all_thresholds_match": all_thresholds_match,
        "weakest_hybrid_win": weakest or None,
        "candidate_status": candidate_status,
        "eligible_for_promotion": eligible,
        "promotable_v2": promotable,
    }


def build_matrix(
    scoreboard_paths: list[Path],
    *,
    minimum_ready_surfaces: int,
    minimum_strong_margin: float,
) -> dict[str, Any]:
    rows = [
        _row_from_scoreboard(
            path.resolve(),
            index=index,
            minimum_ready_surfaces=minimum_ready_surfaces,
            minimum_strong_margin=minimum_strong_margin,
        )
        for index, path in enumerate(scoreboard_paths)
    ]
    checked_in = rows[0] if rows else None
    candidates = rows[1:]
    promotable = [row for row in candidates if row["promotable_v2"]]
    promotable.sort(
        key=lambda row: (
            float((row.get("threshold") or {}).get("value", 0))
            if isinstance((row.get("threshold") or {}).get("value"), (int, float))
            else 0.0,
            float((row.get("weakest_hybrid_win") or {}).get("speedup_ratio", 0.0)),
        ),
        reverse=True,
    )

    summary: dict[str, Any] = {
        "checked_in_label": checked_in["label"] if checked_in else None,
        "checked_in_threshold": checked_in.get("threshold") if checked_in else None,
        "candidate_count": len(candidates),
        "promotable_candidate_count": len(promotable),
        "best_promotable_candidate": promotable[0] if promotable else None,
    }
    if promotable:
        summary["recommended_action"] = "promote_best_candidate"
        summary["reason"] = "candidate_meets_minimum_strong_margin"
    else:
        summary["recommended_action"] = "keep_current_threshold_and_define_stronger_candidate"
        summary["reason"] = "no_candidate_meets_minimum_strong_margin"
    return {
        "schema_version": 1,
        "scope": "campaign_threshold_candidate_matrix",
        "policy": {
            "minimum_ready_surfaces": minimum_ready_surfaces,
            "minimum_strong_margin": minimum_strong_margin,
        },
        "rows": rows,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scoreboard",
        action="append",
        type=Path,
        default=None,
        help="Scoreboard path(s); first one is treated as the checked-in baseline.",
    )
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--minimum-ready-surfaces", type=int, default=DEFAULT_MIN_READY_SURFACES)
    parser.add_argument("--minimum-strong-margin", type=float, default=DEFAULT_MIN_STRONG_MARGIN)
    args = parser.parse_args()

    scoreboard_paths = list(args.scoreboard or DEFAULT_SCOREBOARDS)
    payload = build_matrix(
        scoreboard_paths,
        minimum_ready_surfaces=args.minimum_ready_surfaces,
        minimum_strong_margin=args.minimum_strong_margin,
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
