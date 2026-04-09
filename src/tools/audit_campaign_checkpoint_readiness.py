#!/usr/bin/env python3
"""
Summarize whether the current active campaign line is enough to count as a first
campaign-goal checkpoint, and whether the remaining weakness is family breadth.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_ACTIVE_SCOREBOARD = REPO_ROOT / "work" / "campaign_speed_scoreboard_active.json"
DEFAULT_READY_SCOREBOARD = REPO_ROOT / "work" / "rtlmeter_ready_scoreboard.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_checkpoint_readiness.json"
DEFAULT_MIN_READY_SURFACES = 5
DEFAULT_MIN_STRONG_MARGIN = 2.0
DEFAULT_MIN_FAMILY_COUNT = 2


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _family_for_target(target: str) -> str:
    if target.startswith("tlul_"):
        return "OpenTitan.TLUL"
    if target.startswith("xbar_"):
        return "OpenTitan.XBAR"
    if "_" in target:
        return target.split("_", 1)[0]
    return target


def build_checkpoint_readiness(
    *,
    active_scoreboard: dict[str, Any],
    ready_scoreboard: dict[str, Any],
    minimum_ready_surfaces: int,
    minimum_strong_margin: float,
    minimum_family_count: int,
) -> dict[str, Any]:
    active_rows = list(active_scoreboard.get("rows") or [])
    ready_rows = list(ready_scoreboard.get("rows") or [])
    summary = dict(active_scoreboard.get("summary") or {})
    comparison_ready_count = int(summary.get("comparison_ready_count") or 0)
    hybrid_win_count = int(summary.get("hybrid_win_count") or 0)
    weakest = dict(summary.get("weakest_hybrid_win") or {})
    weakest_ratio_raw = weakest.get("speedup_ratio")
    weakest_ratio = float(weakest_ratio_raw) if isinstance(weakest_ratio_raw, (int, float)) else None

    families: dict[str, list[str]] = {}
    for row in active_rows:
        target = str(row.get("target") or "")
        if not target:
            continue
        family = _family_for_target(target)
        families.setdefault(family, []).append(target)
    family_counts = {family: len(targets) for family, targets in sorted(families.items())}
    family_diversity_count = len(family_counts)

    readiness = "not_ready"
    reason = "insufficient_active_surfaces"
    recommended_next_task = "add_next_comparison_surface"
    if comparison_ready_count >= minimum_ready_surfaces and hybrid_win_count == comparison_ready_count:
        if weakest_ratio is not None and weakest_ratio >= minimum_strong_margin:
            if family_diversity_count >= minimum_family_count:
                readiness = "cross_family_checkpoint_ready"
                reason = "active_line_has_enough_surface_count_margin_and_family_diversity"
                recommended_next_task = "choose_next_expansion_axis"
            else:
                readiness = "single_family_checkpoint_ready"
                reason = "active_line_has_enough_surface_count_and_margin_but_only_one_family"
                recommended_next_task = "decide_if_single_family_checkpoint_is_acceptable"
        else:
            readiness = "not_ready"
            reason = "weakest_hybrid_margin_below_threshold"
            recommended_next_task = "strengthen_existing_surfaces"
    elif comparison_ready_count >= minimum_ready_surfaces:
        readiness = "not_ready"
        reason = "not_all_active_surfaces_are_hybrid_wins"
        recommended_next_task = "repair_existing_surfaces"

    return {
        "schema_version": 1,
        "scope": "campaign_checkpoint_readiness",
        "selected_profile_name": active_scoreboard.get("selected_profile_name"),
        "selected_policy_mode": active_scoreboard.get("selected_policy_mode"),
        "selected_scenario_name": active_scoreboard.get("selected_scenario_name"),
        "policy_gate_status": active_scoreboard.get("policy_gate_status"),
        "policy": {
            "minimum_ready_surfaces": minimum_ready_surfaces,
            "minimum_strong_margin": minimum_strong_margin,
            "minimum_family_count": minimum_family_count,
        },
        "summary": {
            "active_surface_count": len(active_rows),
            "comparison_ready_count": comparison_ready_count,
            "hybrid_win_count": hybrid_win_count,
            "ready_pool_count": len(ready_rows),
            "active_fraction_of_ready_pool": (
                comparison_ready_count / len(ready_rows) if ready_rows else None
            ),
            "family_diversity_count": family_diversity_count,
            "family_counts": family_counts,
            "weakest_hybrid_win": weakest,
        },
        "decision": {
            "readiness": readiness,
            "reason": reason,
            "recommended_next_task": recommended_next_task,
        },
        "active_targets": [str(row.get("target")) for row in active_rows if row.get("target")],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-scoreboard-json", type=Path, default=DEFAULT_ACTIVE_SCOREBOARD)
    parser.add_argument("--ready-scoreboard-json", type=Path, default=DEFAULT_READY_SCOREBOARD)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--minimum-ready-surfaces", type=int, default=DEFAULT_MIN_READY_SURFACES)
    parser.add_argument("--minimum-strong-margin", type=float, default=DEFAULT_MIN_STRONG_MARGIN)
    parser.add_argument("--minimum-family-count", type=int, default=DEFAULT_MIN_FAMILY_COUNT)
    args = parser.parse_args()

    payload = build_checkpoint_readiness(
        active_scoreboard=_read_json(args.active_scoreboard_json.resolve()),
        ready_scoreboard=_read_json(args.ready_scoreboard_json.resolve()),
        minimum_ready_surfaces=args.minimum_ready_surfaces,
        minimum_strong_margin=args.minimum_strong_margin,
        minimum_family_count=args.minimum_family_count,
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
