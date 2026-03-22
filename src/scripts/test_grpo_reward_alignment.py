#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
REPORT_PATH = SCRIPT_DIR.parent / "grpo/report_grpo_reward_alignment.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _row(reward: float, *, hit: float, active: float, target: float, dead: float) -> dict[str, object]:
    return {
        "reward": reward,
        "case_summary": {
            "points_hit": hit,
            "active_region_count": active,
            "target_region_activated": target,
            "dead_region_count": dead,
        },
    }


class RewardAlignmentReportTest(unittest.TestCase):
    def setUp(self) -> None:
        if not REPORT_PATH.is_file():
            self.skipTest(f"Module not available: {REPORT_PATH.name}")
        self.report = _load_module("grpo_reward_alignment_test_module", REPORT_PATH)

    def _write_dataset(self, rows: list[dict[str, object]]) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        path = Path(tmpdir.name) / "dataset.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_breadth_aligned_dataset_is_classified(self) -> None:
        dataset = self._write_dataset(
            [
                _row(0.1, hit=8, active=1, target=0, dead=4),
                _row(0.2, hit=10, active=2, target=0, dead=3),
                _row(0.3, hit=12, active=3, target=1, dead=2),
                _row(0.4, hit=14, active=4, target=1, dead=1),
            ]
        )
        payload = self.report._dataset_payload("breadth_case", dataset)
        self.assertEqual(payload["alignment_classification"], "breadth_aligned")
        self.assertGreater(payload["correlations"]["reward_vs_points_hit"], 0.9)
        self.assertLess(payload["correlations"]["reward_vs_dead_region_count"], -0.9)

    def test_target_only_alignment_is_separated(self) -> None:
        dataset = self._write_dataset(
            [
                _row(0.1, hit=10, active=1, target=0, dead=2),
                _row(0.2, hit=10, active=1, target=0, dead=2),
                _row(0.3, hit=10, active=1, target=1, dead=2),
                _row(0.4, hit=10, active=1, target=1, dead=2),
            ]
        )
        payload = self.report._dataset_payload("target_case", dataset)
        self.assertEqual(payload["alignment_classification"], "target_only_aligned")
        self.assertIsNone(payload["correlations"]["reward_vs_points_hit"])
        self.assertGreater(payload["correlations"]["reward_vs_target_region_activated"], 0.7)

    def test_saturated_dataset_is_not_over_interpreted(self) -> None:
        dataset = self._write_dataset(
            [
                _row(0.1, hit=18, active=6, target=1, dead=0),
                _row(0.2, hit=18, active=6, target=1, dead=0),
                _row(0.3, hit=18, active=6, target=1, dead=0),
                _row(0.4, hit=18, active=6, target=1, dead=0),
            ]
        )
        payload = self.report._dataset_payload("saturated_case", dataset)
        self.assertEqual(payload["alignment_classification"], "saturated_or_constant_dataset")
        self.assertIsNone(payload["correlations"]["reward_vs_points_hit"])
        self.assertIsNone(payload["correlations"]["reward_vs_active_region_count"])


if __name__ == "__main__":
    unittest.main()
