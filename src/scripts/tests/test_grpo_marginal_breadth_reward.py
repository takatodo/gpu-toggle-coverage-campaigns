#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
GRPO_COMMON_PATH = SCRIPT_DIR / "grpo_coverage_common.py"
DATASET_BUILDER_PATH = SCRIPT_DIR.parent / "grpo/build_grpo_offline_dataset.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class MarginalBreadthRewardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.common = _load_module("grpo_common_marginal_breadth_test", GRPO_COMMON_PATH)
        if DATASET_BUILDER_PATH.is_file():
            self.dataset_builder = _load_module("grpo_dataset_builder_marginal_breadth_test", DATASET_BUILDER_PATH)
        else:
            self.dataset_builder = None

    def test_marginal_breadth_prefers_multi_region_case(self) -> None:
        narrow_terms = self.common.reward_terms_from_case(
            {
                "real_subset_points_hit": 8,
                "real_subset_points_total": 18,
                "dead_region_count": 2,
                "dead_output_word_count": 5,
                "target_region_activated": 1,
                "target_region_still_dead": 0,
                "real_subset_coverage_per_second": 12.0,
                "active_region_count": 1,
                "region_count": 5,
                "accepted_traffic_sum": 4,
                "progress_cycle_count_o": 5,
            },
            reward_profile="marginal_breadth",
        )
        wide_terms = self.common.reward_terms_from_case(
            {
                "real_subset_points_hit": 8,
                "real_subset_points_total": 18,
                "dead_region_count": 0,
                "dead_output_word_count": 1,
                "target_region_activated": 1,
                "target_region_still_dead": 0,
                "real_subset_coverage_per_second": 12.0,
                "active_region_count": 3,
                "region_count": 5,
                "accepted_traffic_sum": 4,
                "progress_cycle_count_o": 5,
            },
            reward_profile="marginal_breadth",
        )
        self.assertGreater(wide_terms["reward"], narrow_terms["reward"])
        self.assertGreater(wide_terms["multi_region_bonus"], narrow_terms["multi_region_bonus"])
        self.assertGreater(narrow_terms["target_isolation_penalty"], wide_terms["target_isolation_penalty"])

    def test_dataset_shaping_rewards_rare_target_regions(self) -> None:
        if self.dataset_builder is None:
            self.skipTest("build_grpo_offline_dataset not available in this repo")
        records = [
            {
                "slice_context_key": "tlul_socket_m1::*::mixed",
                "frontier": {"target_region": "r0"},
                "reward_terms": {"reward": 1.0, "target_region_rarity_bonus": 0.0},
                "reward": 1.0,
            },
            {
                "slice_context_key": "tlul_socket_m1::*::mixed",
                "frontier": {"target_region": "r0"},
                "reward_terms": {"reward": 1.0, "target_region_rarity_bonus": 0.0},
                "reward": 1.0,
            },
            {
                "slice_context_key": "tlul_socket_m1::*::mixed",
                "frontier": {"target_region": "r1"},
                "reward_terms": {
                    "reward": 1.0,
                    "target_region_rarity_bonus": 0.0,
                    "target_region_rarity_weight": 0.25,
                },
                "reward": 1.0,
            },
        ]
        for record in records[:2]:
            record["reward_terms"]["target_region_rarity_weight"] = 0.25
        self.dataset_builder._apply_marginal_breadth_reward_shaping(records)
        self.assertLess(
            records[0]["reward_terms"]["target_region_rarity_bonus"],
            records[2]["reward_terms"]["target_region_rarity_bonus"],
        )
        self.assertLess(records[0]["reward"], records[2]["reward"])

    def test_closure_profile_prefers_activation_with_multi_region_progress(self) -> None:
        isolated_terms = self.common.reward_terms_from_case(
            {
                "real_subset_points_hit": 10,
                "real_subset_points_total": 18,
                "dead_region_count": 1,
                "dead_output_word_count": 4,
                "target_region_activated": 1,
                "target_region_still_dead": 0,
                "real_subset_coverage_per_second": 10.0,
                "active_region_count": 1,
                "region_count": 5,
                "accepted_traffic_sum": 5,
                "progress_cycle_count_o": 6,
            },
            reward_profile="closure",
        )
        closure_terms = self.common.reward_terms_from_case(
            {
                "real_subset_points_hit": 10,
                "real_subset_points_total": 18,
                "dead_region_count": 0,
                "dead_output_word_count": 1,
                "target_region_activated": 1,
                "target_region_still_dead": 0,
                "real_subset_coverage_per_second": 10.0,
                "active_region_count": 4,
                "region_count": 5,
                "accepted_traffic_sum": 5,
                "progress_cycle_count_o": 6,
            },
            reward_profile="closure",
        )
        self.assertGreater(closure_terms["closure_progress_bonus"], isolated_terms["closure_progress_bonus"])
        self.assertGreater(closure_terms["activation_novelty_bonus"], isolated_terms["activation_novelty_bonus"])
        self.assertGreater(closure_terms["reward"], isolated_terms["reward"])


if __name__ == "__main__":
    unittest.main()
