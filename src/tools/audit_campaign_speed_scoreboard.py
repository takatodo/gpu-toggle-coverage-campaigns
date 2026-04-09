#!/usr/bin/env python3
"""
Summarize checked-in time-to-threshold comparison artifacts into one campaign scoreboard.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_GLOB = "*_time_to_threshold_comparison.json"
DEFAULT_SEARCH_DIR = REPO_ROOT / "output" / "validation"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_speed_scoreboard.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _threshold_key(payload: dict[str, Any]) -> str | None:
    threshold = dict(payload.get("campaign_threshold") or {})
    kind = threshold.get("kind")
    value = threshold.get("value")
    aggregation = threshold.get("aggregation")
    if kind is None or value is None or aggregation is None:
        return None
    return f"{kind}:{value}:{aggregation}"


def _measurement_wall_time_ms(section: dict[str, Any]) -> float | None:
    measurement = dict(section.get("campaign_measurement") or {})
    value = measurement.get("wall_time_ms")
    return float(value) if isinstance(value, (int, float)) else None


def build_scoreboard(paths: list[Path]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    threshold_keys: set[str] = set()
    hybrid_win_ratios: list[tuple[str, float]] = []
    for path in sorted(paths):
        payload = _read_json(path)
        target = str(payload.get("target") or path.stem.removesuffix("_time_to_threshold_comparison"))
        threshold_key = _threshold_key(payload)
        if threshold_key is not None:
            threshold_keys.add(threshold_key)
        winner = payload.get("winner")
        comparison_ready = bool(payload.get("comparison_ready"))
        speedup_ratio = payload.get("speedup_ratio")
        speedup_ratio_f = float(speedup_ratio) if isinstance(speedup_ratio, (int, float)) else None
        if comparison_ready and winner == "hybrid" and speedup_ratio_f is not None:
            hybrid_win_ratios.append((target, speedup_ratio_f))
        rows.append(
            {
                "target": target,
                "path": str(path.resolve()),
                "status": payload.get("status"),
                "comparison_ready": comparison_ready,
                "winner": winner,
                "speedup_ratio": speedup_ratio_f,
                "campaign_threshold": dict(payload.get("campaign_threshold") or {}),
                "reject_reason": payload.get("reject_reason"),
                "baseline_wall_time_ms": _measurement_wall_time_ms(dict(payload.get("baseline") or {})),
                "hybrid_wall_time_ms": _measurement_wall_time_ms(dict(payload.get("hybrid") or {})),
            }
        )

    comparison_ready_count = sum(1 for row in rows if row["comparison_ready"])
    hybrid_win_count = sum(1 for row in rows if row["winner"] == "hybrid")
    baseline_win_count = sum(1 for row in rows if row["winner"] == "baseline")
    unresolved_count = sum(1 for row in rows if row["winner"] == "unresolved")
    reject_count = sum(1 for row in rows if row["status"] == "reject")
    summary: dict[str, Any] = {
        "total_comparisons": len(rows),
        "comparison_ready_count": comparison_ready_count,
        "hybrid_win_count": hybrid_win_count,
        "baseline_win_count": baseline_win_count,
        "unresolved_count": unresolved_count,
        "reject_count": reject_count,
        "all_thresholds_match": len(threshold_keys) <= 1,
        "threshold_keys": sorted(threshold_keys),
        "hybrid_win_ratio": (
            hybrid_win_count / comparison_ready_count if comparison_ready_count > 0 else None
        ),
    }
    if hybrid_win_ratios:
        best_target, best_ratio = max(hybrid_win_ratios, key=lambda item: item[1])
        weakest_target, weakest_ratio = min(hybrid_win_ratios, key=lambda item: item[1])
        summary["best_hybrid_win"] = {"target": best_target, "speedup_ratio": best_ratio}
        summary["weakest_hybrid_win"] = {"target": weakest_target, "speedup_ratio": weakest_ratio}
    return {
        "schema_version": 1,
        "scope": "campaign_speed_scoreboard",
        "search_dir": str(DEFAULT_SEARCH_DIR.resolve()),
        "rows": rows,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-dir", type=Path, default=DEFAULT_SEARCH_DIR)
    parser.add_argument("--glob", default=DEFAULT_GLOB)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    search_dir = args.search_dir.resolve()
    paths = sorted(search_dir.glob(args.glob))
    payload = build_scoreboard(paths)
    payload["search_dir"] = str(search_dir)
    args.json_out = args.json_out.resolve()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
