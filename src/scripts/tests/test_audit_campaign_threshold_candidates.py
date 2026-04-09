#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_threshold_candidates.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _scoreboard(*, threshold_value: int, weakest_ratio: float, ready: int = 2, wins: int = 2):
    return {
        "schema_version": 1,
        "scope": "campaign_speed_scoreboard",
        "summary": {
            "comparison_ready_count": ready,
            "hybrid_win_count": wins,
            "total_comparisons": ready,
            "all_thresholds_match": True,
            "threshold_keys": [f"toggle_bits_hit:{threshold_value}:bitwise_or_across_trials"],
            "weakest_hybrid_win": {
                "target": "demo",
                "speedup_ratio": weakest_ratio,
            },
        },
        "rows": [],
    }


class AuditCampaignThresholdCandidatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_threshold_candidates_test", MODULE_PATH)

    def test_keeps_current_threshold_when_candidate_margin_is_too_weak(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            current = root / "campaign_speed_scoreboard.json"
            candidate = root / "campaign_speed_scoreboard_threshold5.json"
            current.write_text(json.dumps(_scoreboard(threshold_value=3, weakest_ratio=1.16)) + "\n", encoding="utf-8")
            candidate.write_text(json.dumps(_scoreboard(threshold_value=5, weakest_ratio=1.20)) + "\n", encoding="utf-8")

            payload = self.module.build_matrix([current, candidate], minimum_ready_surfaces=2, minimum_strong_margin=2.0)
            self.assertEqual(payload["summary"]["recommended_action"], "keep_current_threshold_and_define_stronger_candidate")
            self.assertEqual(payload["summary"]["reason"], "no_candidate_meets_minimum_strong_margin")
            self.assertEqual(payload["rows"][0]["candidate_status"], "checked_in")
            self.assertEqual(payload["rows"][1]["candidate_status"], "candidate_only")

    def test_promotes_best_candidate_when_margin_is_strong_enough(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            current = root / "campaign_speed_scoreboard.json"
            candidate = root / "campaign_speed_scoreboard_threshold7.json"
            current.write_text(json.dumps(_scoreboard(threshold_value=3, weakest_ratio=1.16)) + "\n", encoding="utf-8")
            candidate.write_text(json.dumps(_scoreboard(threshold_value=7, weakest_ratio=2.50)) + "\n", encoding="utf-8")

            payload = self.module.build_matrix([current, candidate], minimum_ready_surfaces=2, minimum_strong_margin=2.0)
            self.assertEqual(payload["summary"]["recommended_action"], "promote_best_candidate")
            self.assertEqual(payload["summary"]["best_promotable_candidate"]["label"], "threshold7")
            self.assertEqual(payload["rows"][1]["candidate_status"], "promotable_v2")

    def test_main_writes_default_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            current = root / "campaign_speed_scoreboard.json"
            candidate = root / "campaign_speed_scoreboard_threshold5.json"
            json_out = root / "campaign_threshold_candidate_matrix.json"
            current.write_text(json.dumps(_scoreboard(threshold_value=3, weakest_ratio=1.16)) + "\n", encoding="utf-8")
            candidate.write_text(json.dumps(_scoreboard(threshold_value=5, weakest_ratio=1.20)) + "\n", encoding="utf-8")

            argv = [
                "audit_campaign_threshold_candidates.py",
                "--scoreboard",
                str(current),
                "--scoreboard",
                str(candidate),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_threshold_candidate_matrix")
            self.assertEqual(payload["summary"]["checked_in_threshold"]["value"], 3)


if __name__ == "__main__":
    unittest.main()
