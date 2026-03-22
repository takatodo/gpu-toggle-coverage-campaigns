#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Freeze production defaults from execution profiles and convergence data"
    )
    parser.add_argument("--profiles-json", required=True)
    parser.add_argument("--convergence-json", required=True)
    parser.add_argument("--campaign-efficiency-json", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    args = parser.parse_args(argv)

    profiles_data = json.loads(Path(args.profiles_json).read_text(encoding="utf-8"))
    convergence_data = json.loads(Path(args.convergence_json).read_text(encoding="utf-8"))

    convergence_by_slice = {
        s["slice_name"]: s for s in convergence_data.get("slices", [])
    }

    rows = []
    for entry in profiles_data.get("slices", []):
        slice_name = entry["slice_name"]
        row: dict = {"slice_name": slice_name}

        policy = entry.get("launch_backend_policy", {})
        for phase in ("single_step", "multi_step", "sweep", "campaign"):
            if phase in policy:
                row[f"{phase}_backend"] = policy[phase]

        profiles = entry.get("profiles", {})
        for phase in ("single_step", "multi_step"):
            if phase in profiles:
                row[f"{phase}_profile"] = profiles[phase]

        conv = convergence_by_slice.get(slice_name, {})
        for key in (
            "recommended_campaign_candidate_count",
            "recommended_campaign_shard_count",
            "recommended_stop",
            "recommended_stop_at_shard",
            "plateau_after_shard",
            "recommended_convergence_thresholds",
        ):
            if key in conv:
                row[key] = conv[key]

        rows.append(row)

    out = {"rows": rows, "schema_version": "opentitan-tlul-slice-production-defaults-v1"}
    Path(args.json_out).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    Path(args.md_out).write_text("# Production Defaults\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
