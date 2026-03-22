#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _pilot_rollout_metrics(row: dict) -> dict:
    pilot_root = Path(row["pilot_root_dir"])
    campaign_summary = pilot_root / "campaign" / "summary.json"
    sweep_summary = pilot_root / "sweep" / "summary.json"

    source_path = campaign_summary if campaign_summary.exists() else sweep_summary
    data = json.loads(source_path.read_text(encoding="utf-8"))
    best_case = data["best_case"]
    best_by_target = data.get("best_by_target_region", {})

    covered_count = sum(
        1 for v in best_by_target.values() if not v.get("target_region_still_dead", 0)
    )
    activated_count = sum(
        1 for v in best_by_target.values() if v.get("target_region_activated", 0)
    )

    return {
        "result_source_path": str(source_path.resolve()),
        "points_hit": best_case.get("real_subset_points_hit"),
        "active_region_union_count": best_case.get("active_region_count"),
        "campaign_target_region_case_count": len(best_by_target),
        "campaign_target_region_covered_count": covered_count,
        "campaign_target_region_activated_count": activated_count,
    }


def _toggle_coverage_aggregate(rows: list[dict]) -> dict:
    with_points = [r for r in rows if r.get("points_hit") is not None]
    hit_sum = sum(r["points_hit"] for r in with_points)
    total_sum = sum(r["points_total"] for r in with_points)
    return {
        "toggle_rows_with_points": len(with_points),
        "toggle_points_hit_sum": hit_sum,
        "toggle_points_total_sum": total_sum,
        "toggle_points_hit_fraction": hit_sum / total_sum if total_sum else 0.0,
        "toggle_full_hit_slice_count": sum(
            1 for r in with_points if r["points_hit"] == r["points_total"]
        ),
        "toggle_full_region_slice_count": sum(
            1 for r in rows if r.get("dead_region_count") == 0
        ),
        "active_region_union_count_sum": sum(
            r["active_region_union_count"]
            for r in rows
            if r.get("active_region_union_count") is not None
        ),
        "campaign_target_region_case_count_sum": sum(
            r["campaign_target_region_case_count"]
            for r in rows
            if r.get("campaign_target_region_case_count") is not None
        ),
        "campaign_target_region_covered_count_sum": sum(
            r["campaign_target_region_covered_count"]
            for r in rows
            if r.get("campaign_target_region_covered_count") is not None
        ),
        "campaign_target_region_activated_count_sum": sum(
            r["campaign_target_region_activated_count"]
            for r in rows
            if r.get("campaign_target_region_activated_count") is not None
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Report surface toggle coverage results")
    parser.add_argument("--rollout-json", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    args = parser.parse_args(argv)

    rollout = json.loads(Path(args.rollout_json).read_text(encoding="utf-8"))
    rows = [_pilot_rollout_metrics(r) for r in rollout.get("rows", [])]
    aggregate = _toggle_coverage_aggregate(rows)

    out = {"rows": rows, "aggregate": aggregate, "schema_version": "opentitan-tlul-surface-results-v1"}
    Path(args.json_out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    Path(args.md_out).write_text("# Surface Toggle Coverage Results\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
