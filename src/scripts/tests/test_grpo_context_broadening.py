#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
GRPO_COMMON_PATH = SCRIPT_DIR / "grpo_coverage_common.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _candidate(action_key: str) -> dict[str, object]:
    return {
        "action_key": action_key,
        "action_patch": {"action": action_key},
    }


class ContextBroadeningTest(unittest.TestCase):
    def setUp(self) -> None:
        self.common = _load_module("grpo_common_context_broadening_test", GRPO_COMMON_PATH)

    def test_slice_mode_backfills_missing_then_exact(self) -> None:
        selected, meta = self.common.select_policy_candidates(
            exact_candidates=[_candidate("e1"), _candidate("e2")],
            missing_candidates=[_candidate("m1")],
            slice_candidates=[_candidate("s1")],
            limit=4,
            selection_mode="slice",
        )
        self.assertEqual([item["action_key"] for item in selected], ["s1", "m1", "e1", "e2"])
        self.assertEqual(meta["selection_source"], "slice_context")
        self.assertEqual(meta["selected_from_counts"], {"exact": 2, "missing": 1, "slice": 1})

    def test_missing_mode_backfills_slice_then_exact(self) -> None:
        selected, meta = self.common.select_policy_candidates(
            exact_candidates=[_candidate("e1"), _candidate("e2")],
            missing_candidates=[_candidate("m1")],
            slice_candidates=[_candidate("s1")],
            limit=4,
            selection_mode="missing",
        )
        self.assertEqual([item["action_key"] for item in selected], ["m1", "s1", "e1", "e2"])
        self.assertEqual(meta["selection_source"], "missing_region_context")
        self.assertEqual(meta["selected_from_counts"], {"exact": 2, "missing": 1, "slice": 1})

    def test_closure_mode_prefers_missing_and_slice_before_exact(self) -> None:
        selected, meta = self.common.select_policy_candidates(
            exact_candidates=[_candidate("e1"), _candidate("e2"), _candidate("e3")],
            missing_candidates=[_candidate("m1")],
            slice_candidates=[_candidate("s1"), _candidate("s2")],
            limit=4,
            selection_mode="closure",
        )
        self.assertEqual([item["action_key"] for item in selected], ["m1", "s1", "s2", "e1"])
        self.assertEqual(meta["selection_source"], "closure_missing_slice_blend")
        self.assertEqual(meta["selected_from_counts"], {"exact": 1, "missing": 1, "slice": 2})

    def test_closure_prefers_new_target_family_across_sources(self) -> None:
        selected, meta = self.common.select_policy_candidates(
            exact_candidates=[],
            missing_candidates=[
                {
                    "action_key": "m_reqfifo",
                    "action_patch": {"v": "m_reqfifo"},
                    "target_regions": ["reqfifo_storage_upper"],
                }
            ],
            slice_candidates=[
                {
                    "action_key": "s_reqfifo",
                    "action_patch": {"v": "s_reqfifo"},
                    "target_regions": ["reqfifo_storage_upper"],
                },
                {
                    "action_key": "s_rspfifo",
                    "action_patch": {"v": "s_rspfifo"},
                    "target_regions": ["rspfifo_storage_upper"],
                },
            ],
            limit=2,
            selection_mode="closure",
        )
        self.assertEqual([item["action_key"] for item in selected], ["m_reqfifo", "s_rspfifo"])
        self.assertEqual(meta["selected_from_counts"], {"exact": 0, "missing": 1, "slice": 1})

    def test_hard_slices_default_to_closure_selection(self) -> None:
        self.assertEqual(self.common.recommended_grpo_selection_mode("tlul_socket_m1"), "closure")
        self.assertEqual(self.common.recommended_grpo_selection_mode("alert_handler_ping_timer"), "closure")


if __name__ == "__main__":
    unittest.main()
