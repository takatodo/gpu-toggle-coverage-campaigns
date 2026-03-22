#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR / "report_opentitan_tlul_surface_results.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SurfaceToggleAggregationTest(unittest.TestCase):
    def setUp(self) -> None:
        if not MODULE_PATH.is_file():
            self.skipTest(f"Module not available: {MODULE_PATH.name}")
        self.module = _load_module("surface_toggle_aggregation_module", MODULE_PATH)

    def test_toggle_coverage_aggregate_sums_hits_regions_and_targets(self) -> None:
        rows = [
            {
                "slice_name": "a",
                "points_hit": 18,
                "points_total": 18,
                "dead_region_count": 0,
                "active_region_union_count": 5,
                "campaign_target_region_case_count": 5,
                "campaign_target_region_covered_count": 5,
                "campaign_target_region_activated_count": 5,
            },
            {
                "slice_name": "b",
                "points_hit": 15,
                "points_total": 18,
                "dead_region_count": 1,
                "active_region_union_count": 4,
                "campaign_target_region_case_count": 5,
                "campaign_target_region_covered_count": 4,
                "campaign_target_region_activated_count": 3,
            },
            {
                "slice_name": "c",
                "points_hit": None,
                "points_total": None,
                "dead_region_count": None,
                "active_region_union_count": None,
                "campaign_target_region_case_count": None,
                "campaign_target_region_covered_count": None,
                "campaign_target_region_activated_count": None,
            },
        ]
        aggregate = self.module._toggle_coverage_aggregate(rows)
        self.assertEqual(aggregate["toggle_rows_with_points"], 2)
        self.assertEqual(aggregate["toggle_points_hit_sum"], 33)
        self.assertEqual(aggregate["toggle_points_total_sum"], 36)
        self.assertAlmostEqual(aggregate["toggle_points_hit_fraction"], 33.0 / 36.0)
        self.assertEqual(aggregate["toggle_full_hit_slice_count"], 1)
        self.assertEqual(aggregate["toggle_full_region_slice_count"], 1)
        self.assertEqual(aggregate["active_region_union_count_sum"], 9)
        self.assertEqual(aggregate["campaign_target_region_case_count_sum"], 10)
        self.assertEqual(aggregate["campaign_target_region_covered_count_sum"], 9)
        self.assertEqual(aggregate["campaign_target_region_activated_count_sum"], 8)


if __name__ == "__main__":
    unittest.main()
