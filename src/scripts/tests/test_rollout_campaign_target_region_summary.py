#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
ROLLOUT_STATUS_PATH = SCRIPT_DIR.parent / "tools" / "report_opentitan_tlul_slice_rollout_status.py"
SURFACE_RESULTS_PATH = SCRIPT_DIR.parent / "tools" / "report_opentitan_tlul_surface_results.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RolloutCampaignTargetRegionSummaryTest(unittest.TestCase):
    def test_load_pilot_campaign_quality_counts_target_region_coverage(self) -> None:
        if not ROLLOUT_STATUS_PATH.is_file():
            self.skipTest(f"Module not available: {ROLLOUT_STATUS_PATH.name}")
        module = _load_module(ROLLOUT_STATUS_PATH, "rollout_status_campaign_quality")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            campaign_dir = root / "campaign"
            campaign_dir.mkdir(parents=True)
            summary_path = campaign_dir / "summary.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "best_case": {
                            "real_subset_points_hit": 11,
                            "active_region_count": 3,
                            "dead_region_count": 2,
                            "accepted_traffic_sum": 4,
                        },
                        "best_by_target_region": {
                            "alpha": {
                                "target_region_activated": 1,
                                "target_region_still_dead": 0,
                            },
                            "beta": {
                                "target_region_activated": 0,
                                "target_region_still_dead": 0,
                            },
                            "gamma": {
                                "target_region_activated": 0,
                                "target_region_still_dead": 1,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            quality = module._load_pilot_campaign_quality(str(root))
        self.assertEqual(quality["best_case_points_hit"], 11)
        self.assertEqual(quality["best_case_active_region_count"], 3)
        self.assertEqual(quality["target_region_case_count"], 3)
        self.assertEqual(quality["target_region_covered_count"], 2)
        self.assertEqual(quality["target_region_activated_count"], 1)
        self.assertEqual(quality["status"], "positive_or_partial")

    def test_pilot_rollout_metrics_prefers_campaign_summary_and_preserves_target_counts(self) -> None:
        if not SURFACE_RESULTS_PATH.is_file():
            self.skipTest(f"Module not available: {SURFACE_RESULTS_PATH.name}")
        module = _load_module(SURFACE_RESULTS_PATH, "surface_results_campaign_quality")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sweep_dir = root / "sweep"
            campaign_dir = root / "campaign"
            sweep_dir.mkdir(parents=True)
            campaign_dir.mkdir(parents=True)
            (sweep_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "best_case": {
                            "real_subset_points_hit": 7,
                            "active_region_count": 2,
                        }
                    }
                ),
                encoding="utf-8",
            )
            campaign_summary = campaign_dir / "summary.json"
            campaign_summary.write_text(
                json.dumps(
                    {
                        "best_case": {
                            "real_subset_points_hit": 11,
                            "active_region_count": 3,
                            "accepted_traffic_sum": 4,
                        },
                        "best_by_target_region": {
                            "alpha": {
                                "target_region_activated": 1,
                                "target_region_still_dead": 0,
                            },
                            "beta": {
                                "target_region_activated": 0,
                                "target_region_still_dead": 0,
                            },
                            "gamma": {
                                "target_region_activated": 0,
                                "target_region_still_dead": 1,
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            metrics = module._pilot_rollout_metrics({"pilot_root_dir": str(root)})
        self.assertEqual(metrics["result_source_path"], str(campaign_summary.resolve()))
        self.assertEqual(metrics["points_hit"], 11)
        self.assertEqual(metrics["active_region_union_count"], 3)
        self.assertEqual(metrics["campaign_target_region_case_count"], 3)
        self.assertEqual(metrics["campaign_target_region_covered_count"], 2)
        self.assertEqual(metrics["campaign_target_region_activated_count"], 1)


if __name__ == "__main__":
    unittest.main()
