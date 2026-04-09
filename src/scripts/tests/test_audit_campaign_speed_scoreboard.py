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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_speed_scoreboard.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _comparison_payload(*, target: str, winner: str, speedup_ratio: float | None, ready: bool = True):
    return {
        "schema_version": 1,
        "status": "ok" if winner != "reject" else "reject",
        "target": target,
        "campaign_threshold": {
            "kind": "toggle_bits_hit",
            "value": 3,
            "aggregation": "bitwise_or_across_trials",
        },
        "comparison_ready": ready,
        "winner": winner,
        "speedup_ratio": speedup_ratio,
        "reject_reason": None if winner != "reject" else "threshold_schema_mismatch",
        "baseline": {
            "campaign_measurement": {
                "wall_time_ms": 20.0,
            }
        },
        "hybrid": {
            "campaign_measurement": {
                "wall_time_ms": 10.0 if speedup_ratio is not None else None,
            }
        },
    }


class AuditCampaignSpeedScoreboardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_speed_scoreboard_test", MODULE_PATH)

    def test_build_scoreboard_summarizes_hybrid_wins(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            socket = root / "socket_m1_time_to_threshold_comparison.json"
            fifo = root / "tlul_fifo_sync_time_to_threshold_comparison.json"
            socket.write_text(
                json.dumps(_comparison_payload(target="tlul_socket_m1", winner="hybrid", speedup_ratio=15.0))
                + "\n",
                encoding="utf-8",
            )
            fifo.write_text(
                json.dumps(_comparison_payload(target="tlul_fifo_sync", winner="hybrid", speedup_ratio=1.16))
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_scoreboard([socket, fifo])
            self.assertEqual(payload["summary"]["total_comparisons"], 2)
            self.assertEqual(payload["summary"]["comparison_ready_count"], 2)
            self.assertEqual(payload["summary"]["hybrid_win_count"], 2)
            self.assertEqual(payload["summary"]["baseline_win_count"], 0)
            self.assertTrue(payload["summary"]["all_thresholds_match"])
            self.assertEqual(payload["summary"]["best_hybrid_win"]["target"], "tlul_socket_m1")
            self.assertEqual(payload["summary"]["weakest_hybrid_win"]["target"], "tlul_fifo_sync")

    def test_main_writes_json_with_mixed_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ready = root / "demo_time_to_threshold_comparison.json"
            reject = root / "broken_time_to_threshold_comparison.json"
            ready.write_text(
                json.dumps(_comparison_payload(target="demo", winner="baseline", speedup_ratio=0.5))
                + "\n",
                encoding="utf-8",
            )
            reject.write_text(
                json.dumps(_comparison_payload(target="broken", winner="reject", speedup_ratio=None, ready=False))
                + "\n",
                encoding="utf-8",
            )
            json_out = root / "scoreboard.json"

            argv = [
                "audit_campaign_speed_scoreboard.py",
                "--search-dir",
                str(root),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["total_comparisons"], 2)
            self.assertEqual(payload["summary"]["baseline_win_count"], 1)
            self.assertEqual(payload["summary"]["reject_count"], 1)
            self.assertEqual(payload["summary"]["comparison_ready_count"], 1)


if __name__ == "__main__":
    unittest.main()
