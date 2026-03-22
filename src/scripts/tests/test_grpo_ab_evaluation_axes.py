#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
AXES_MODULE_PATH = SCRIPT_DIR.parent / "grpo/report_grpo_ab_evaluation_axes.py"
COMMON_MODULE_PATH = SCRIPT_DIR / "grpo_coverage_common.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class GrpoAbEvaluationAxesTest(unittest.TestCase):
    def setUp(self) -> None:
        if not AXES_MODULE_PATH.is_file():
            self.skipTest(f"Module not available: {AXES_MODULE_PATH.name}")
        self.axes = _load_module("grpo_ab_axes_test_module", AXES_MODULE_PATH)
        self.common = _load_module("grpo_common_test_module", COMMON_MODULE_PATH)

    def test_diversity_collapse_is_not_frontier_gain(self) -> None:
        plain = {
            "best_hit_fraction": 1.0,
            "campaign_active_region_union_count": 5,
            "best_target_region_activated": 1,
            "frontier_mean_hit_fraction": 0.94,
            "frontier_mean_active_region_count": 4.6,
            "frontier_target_activation_rate": 1.0,
            "frontier_unique_target_region_count": 5,
            "frontier_unique_variant_count": 5,
            "wall_clock_s": 13.4,
            "candidates_per_second": 95.4,
            "total_candidate_space": 1280,
            "evaluated_case_count": 1280,
        }
        grpo = {
            "best_hit_fraction": 1.0,
            "campaign_active_region_union_count": 5,
            "best_target_region_activated": 1,
            "frontier_mean_hit_fraction": 0.98,
            "frontier_mean_active_region_count": 4.8,
            "frontier_target_activation_rate": 1.0,
            "frontier_unique_target_region_count": 2,
            "frontier_unique_variant_count": 2,
            "wall_clock_s": 12.7,
            "candidates_per_second": 100.1,
            "total_candidate_space": 1280,
            "evaluated_case_count": 1280,
        }
        verdict = self.axes._verdict(plain, grpo, {})
        self.assertFalse(verdict["ceiling_gain"])
        self.assertFalse(verdict["frontier_gain"])
        self.assertTrue(verdict["efficiency_gain"])
        self.assertTrue(verdict["throughput_only_gain"])
        self.assertTrue(verdict["target_focus_without_breadth"])
        self.assertEqual(verdict["classification"], "throughput_only_gain")

    def test_frontier_gain_requires_non_regressing_diversity(self) -> None:
        plain = {
            "best_hit_fraction": 1.0,
            "campaign_active_region_union_count": 5,
            "best_target_region_activated": 1,
            "frontier_mean_hit_fraction": 0.90,
            "frontier_mean_active_region_count": 4.0,
            "frontier_target_activation_rate": 0.8,
            "frontier_unique_target_region_count": 4,
            "frontier_unique_variant_count": 4,
            "wall_clock_s": 10.0,
            "candidates_per_second": 128.0,
            "total_candidate_space": 1280,
            "evaluated_case_count": 1280,
        }
        grpo = {
            "best_hit_fraction": 1.0,
            "campaign_active_region_union_count": 5,
            "best_target_region_activated": 1,
            "frontier_mean_hit_fraction": 0.95,
            "frontier_mean_active_region_count": 4.5,
            "frontier_target_activation_rate": 0.9,
            "frontier_unique_target_region_count": 4,
            "frontier_unique_variant_count": 4,
            "wall_clock_s": 9.8,
            "candidates_per_second": 130.0,
            "total_candidate_space": 1280,
            "evaluated_case_count": 1280,
        }
        verdict = self.axes._verdict(plain, grpo, {})
        self.assertFalse(verdict["ceiling_gain"])
        self.assertTrue(verdict["frontier_gain"])
        self.assertTrue(verdict["efficiency_gain"])
        self.assertFalse(verdict["throughput_only_gain"])
        self.assertEqual(verdict["classification"], "frontier_quality_gain")

    def test_alert_handler_has_canonical_grpo_hints(self) -> None:
        self.assertEqual(
            self.common.recommended_grpo_target_region("alert_handler_ping_timer"),
            "id_skip_and_rotation",
        )
        self.assertEqual(
            self.common.recommended_grpo_selection_mode("alert_handler_ping_timer"),
            "closure",
        )
        self.assertEqual(
            self.common.recommended_grpo_policy_profile("alert_handler_ping_timer"),
            "diversity",
        )
        self.assertEqual(
            self.common.recommended_grpo_reward_profile("alert_handler_ping_timer"),
            "closure",
        )


if __name__ == "__main__":
    unittest.main()
