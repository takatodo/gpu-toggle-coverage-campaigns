#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_pilot_campaign_quality(root_dir: str) -> dict:
    summary_path = Path(root_dir) / "campaign" / "summary.json"
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    best_case = data["best_case"]
    best_by_target = data.get("best_by_target_region", {})

    covered_count = sum(
        1 for v in best_by_target.values() if not v.get("target_region_still_dead", 0)
    )
    activated_count = sum(
        1 for v in best_by_target.values() if v.get("target_region_activated", 0)
    )
    case_count = len(best_by_target)

    if case_count > 0 and activated_count == case_count:
        status = "fully_activated"
    elif activated_count > 0 or covered_count > 0:
        status = "positive_or_partial"
    else:
        status = "no_activation"

    return {
        "best_case_points_hit": best_case.get("real_subset_points_hit"),
        "best_case_active_region_count": best_case.get("active_region_count"),
        "target_region_case_count": case_count,
        "target_region_covered_count": covered_count,
        "target_region_activated_count": activated_count,
        "status": status,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Report OpenTitan TLUL slice rollout status")
    parser.add_argument("--rollout-json", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    args = parser.parse_args(argv)

    rollout = json.loads(Path(args.rollout_json).read_text(encoding="utf-8"))
    rows = []
    for entry in rollout.get("rows", []):
        quality = _load_pilot_campaign_quality(entry["pilot_root_dir"])
        rows.append({"slice_name": entry.get("slice_name"), **quality})

    out = {"rows": rows, "schema_version": "opentitan-tlul-slice-rollout-status-v1"}
    Path(args.json_out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    Path(args.md_out).write_text("# Rollout Status\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
