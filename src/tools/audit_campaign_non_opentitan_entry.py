#!/usr/bin/env python3
"""
Recommend the first non-OpenTitan family and entry shape after the current
cross-family checkpoint is accepted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_POST_CHECKPOINT_AXES_JSON = REPO_ROOT / "work" / "campaign_post_checkpoint_axes.json"
DEFAULT_RUNNERS_DIR = REPO_ROOT / "src" / "runners"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_non_opentitan_entry.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _slug(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch.isalnum())


def _runner_inventory_for_family(runners_dir: Path, family_name: str) -> dict[str, Any]:
    slug = _slug(family_name)
    family_runner = runners_dir / f"run_{slug}_family_gpu_toggle_validation.py"
    single_runners = sorted(
        path for path in runners_dir.glob(f"run_{slug}_*_gpu_toggle_validation.py") if path != family_runner
    )
    stock_hybrid_runners = sorted(runners_dir.glob(f"run_{slug}_*_stock_hybrid_validation.py"))
    cpu_baseline_runners = sorted(runners_dir.glob(f"run_{slug}_*_cpu_baseline_validation.py"))
    comparison_runners = sorted(runners_dir.glob(f"run_{slug}_*_time_to_threshold_comparison.py"))
    return {
        "family_runner_path": str(family_runner.resolve()) if family_runner.exists() else None,
        "single_runner_paths": [str(path.resolve()) for path in single_runners],
        "stock_hybrid_runner_paths": [str(path.resolve()) for path in stock_hybrid_runners],
        "cpu_baseline_runner_paths": [str(path.resolve()) for path in cpu_baseline_runners],
        "comparison_runner_paths": [str(path.resolve()) for path in comparison_runners],
    }


def _entry_mode_for_family(family_row: dict[str, Any], runner_inventory: dict[str, Any]) -> tuple[str, str]:
    design_count = int(family_row.get("design_count") or 0)
    has_family_runner = bool(runner_inventory.get("family_runner_path"))
    has_stock_hybrid = bool(runner_inventory.get("stock_hybrid_runner_paths"))
    single_runner_count = len(runner_inventory.get("single_runner_paths") or [])

    if has_family_runner and design_count >= 2 and not has_stock_hybrid:
        return (
            "family_pilot",
            "existing_runner_shape_is_family_level_legacy_validation_and_no_stock_hybrid_surface_exists_yet",
        )
    if single_runner_count > 0 and not has_stock_hybrid:
        return (
            "single_surface",
            "existing_runner_shape_is_design_specific_and_no_family_level_stock_hybrid_surface_exists_yet",
        )
    if has_stock_hybrid:
        return (
            "single_surface",
            "stock_hybrid_design_specific_runners_already_exist_for_this_family",
        )
    return (
        "family_pilot" if design_count >= 2 else "single_surface",
        "no_specialized_campaign_runner_exists_so_start_with_the_smallest_repeatable_entry_shape",
    )


def build_non_opentitan_entry(
    *,
    post_checkpoint_axes: dict[str, Any],
    runners_dir: Path,
) -> dict[str, Any]:
    decision = dict(post_checkpoint_axes.get("decision") or {})
    inventory_rows = list(post_checkpoint_axes.get("inventory_rows") or [])
    recommended_axis = str(decision.get("recommended_next_axis") or "")
    recommended_family = str(decision.get("recommended_family") or "")

    family_rows = [row for row in inventory_rows if not row.get("is_active_repo_family") and not row.get("is_opentitan")]
    enriched_rows: list[dict[str, Any]] = []
    for row in family_rows:
        family_name = str(row.get("repo_family") or "")
        runner_inventory = _runner_inventory_for_family(runners_dir, family_name)
        entry_mode, entry_reason = _entry_mode_for_family(row, runner_inventory)
        enriched_rows.append(
            {
                **row,
                "runner_inventory": runner_inventory,
                "recommended_entry_mode": entry_mode,
                "entry_mode_reason": entry_reason,
            }
        )

    top_row = next((row for row in enriched_rows if row.get("repo_family") == recommended_family), None)
    if top_row is None and enriched_rows:
        top_row = enriched_rows[0]
        recommended_family = str(top_row.get("repo_family") or "")

    if recommended_axis != "broaden_non_opentitan_family" or top_row is None:
        decision_payload = {
            "recommended_family": None,
            "recommended_entry_mode": None,
            "reason": "post_checkpoint_axis_not_ready_for_non_opentitan_entry",
            "recommended_next_tasks": [
                "Keep the current checkpoint baseline stable.",
                "Do not define a non-OpenTitan entry mode until the active post-checkpoint axis is broaden_non_opentitan_family.",
            ],
        }
    else:
        decision_payload = {
            "recommended_family": recommended_family,
            "recommended_entry_mode": top_row.get("recommended_entry_mode"),
            "reason": top_row.get("entry_mode_reason"),
            "recommended_next_tasks": [
                f"Start the first non-OpenTitan wave with `{recommended_family}`.",
                f"Use `{top_row.get('recommended_entry_mode')}` as the first deliverable shape.",
                "Only after that first entry lands should the project decide whether to widen inside the same family or promote one surface to the campaign line.",
            ],
        }

    return {
        "schema_version": 1,
        "scope": "campaign_non_opentitan_entry",
        "post_checkpoint_axis": recommended_axis,
        "current_checkpoint_ready": post_checkpoint_axes.get("checkpoint_summary"),
        "decision": decision_payload,
        "rows": enriched_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--post-checkpoint-axes-json", type=Path, default=DEFAULT_POST_CHECKPOINT_AXES_JSON)
    parser.add_argument("--runners-dir", type=Path, default=DEFAULT_RUNNERS_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_non_opentitan_entry(
        post_checkpoint_axes=_read_json(args.post_checkpoint_axes_json.resolve()),
        runners_dir=args.runners_dir.resolve(),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
