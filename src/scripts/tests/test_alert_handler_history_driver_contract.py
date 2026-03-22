#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
BASELINE_MODULE_PATH = SCRIPT_DIR / "run_opentitan_tlul_slice_gpu_baseline.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AlertHandlerHistoryDriverContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("slice_baseline_alert_driver_contract", BASELINE_MODULE_PATH)
        self.manifest = {
            "history_visibility_contract": {
                "kind": "alert_handler_ping_timer_semantic_seen",
            }
        }

    def test_skip_family_driver_activates_skip_words_under_mixed_visibility(self) -> None:
        active_words = self.module._augment_active_words_for_history_visibility(
            manifest=self.manifest,
            active_words=[
                "real_toggle_subset_word0_o",
                "real_toggle_subset_word1_o",
                "real_toggle_subset_word2_o",
                "real_toggle_subset_word3_o",
                "real_toggle_subset_word4_o",
                "real_toggle_subset_word5_o",
                "real_toggle_subset_word6_o",
                "real_toggle_subset_word7_o",
                "real_toggle_subset_word11_o",
                "real_toggle_subset_word12_o",
                "real_toggle_subset_word13_o",
                "real_toggle_subset_word14_o",
                "real_toggle_subset_word15_o",
                "real_toggle_subset_word16_o",
                "real_toggle_subset_word17_o",
            ],
            traffic_values={"host_req_accepted_o": 1},
            execution_values={"progress_cycle_count_o": 1, "debug_phase_o": 0, "debug_cycle_count_o": 0},
            internal_probe_values={
                "alert_handler_ping_timer_gpu_cov_tb__DOT__phase_q": 0,
                "alert_handler_ping_timer_gpu_cov_tb__DOT__cycle_count_q": 0,
                "alert_handler_ping_timer_gpu_cov_tb__DOT__oracle_semantic_family_seen_q": 23,
                "alert_handler_ping_timer_gpu_cov_tb__DOT__oracle_semantic_case_seen_q": 73,
                "alert_handler_ping_timer_gpu_cov_tb__DOT__non_init_seen_q": 1,
                "alert_handler_ping_timer_gpu_cov_tb__DOT__activity_seen_q": 0,
            },
            driver_values={"req_family": 4},
        )
        self.assertIn("real_toggle_subset_word8_o", active_words)
        self.assertIn("real_toggle_subset_word9_o", active_words)
        self.assertIn("real_toggle_subset_word10_o", active_words)

    def test_non_skip_driver_does_not_force_skip_words(self) -> None:
        active_words = self.module._augment_active_words_for_history_visibility(
            manifest=self.manifest,
            active_words=[
                "real_toggle_subset_word0_o",
                "real_toggle_subset_word1_o",
                "real_toggle_subset_word2_o",
                "real_toggle_subset_word3_o",
                "real_toggle_subset_word4_o",
                "real_toggle_subset_word5_o",
                "real_toggle_subset_word6_o",
                "real_toggle_subset_word7_o",
                "real_toggle_subset_word11_o",
                "real_toggle_subset_word12_o",
                "real_toggle_subset_word13_o",
                "real_toggle_subset_word14_o",
                "real_toggle_subset_word15_o",
                "real_toggle_subset_word16_o",
                "real_toggle_subset_word17_o",
            ],
            traffic_values={"host_req_accepted_o": 1},
            execution_values={"progress_cycle_count_o": 1, "debug_phase_o": 0, "debug_cycle_count_o": 0},
            internal_probe_values={
                "alert_handler_ping_timer_gpu_cov_tb__DOT__phase_q": 0,
                "alert_handler_ping_timer_gpu_cov_tb__DOT__cycle_count_q": 0,
                "alert_handler_ping_timer_gpu_cov_tb__DOT__oracle_semantic_family_seen_q": 23,
                "alert_handler_ping_timer_gpu_cov_tb__DOT__oracle_semantic_case_seen_q": 73,
                "alert_handler_ping_timer_gpu_cov_tb__DOT__non_init_seen_q": 1,
                "alert_handler_ping_timer_gpu_cov_tb__DOT__activity_seen_q": 0,
            },
            driver_values={"req_family": 2},
        )
        self.assertNotIn("real_toggle_subset_word8_o", active_words)
        self.assertNotIn("real_toggle_subset_word9_o", active_words)
        self.assertNotIn("real_toggle_subset_word10_o", active_words)


if __name__ == "__main__":
    unittest.main()
