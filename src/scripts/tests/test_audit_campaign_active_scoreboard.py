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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_active_scoreboard.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _comparison_payload(*, target: str, value: int, ratio: float) -> dict:
    return {
        "schema_version": 1,
        "status": "ok",
        "target": target,
        "campaign_threshold": {
            "kind": "toggle_bits_hit",
            "value": value,
            "aggregation": "bitwise_or_across_trials",
        },
        "comparison_ready": True,
        "winner": "hybrid",
        "speedup_ratio": ratio,
        "reject_reason": None,
        "baseline": {"campaign_measurement": {"wall_time_ms": 20.0}},
        "hybrid": {"campaign_measurement": {"wall_time_ms": 10.0}},
    }


class AuditCampaignActiveScoreboardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_active_scoreboard_test", MODULE_PATH)

    def test_build_active_scoreboard_uses_policy_gate_selected_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            socket = root / "socket.json"
            fifo = root / "fifo.json"
            socket.write_text(
                json.dumps(_comparison_payload(target="tlul_socket_m1", value=5, ratio=22.5)) + "\n",
                encoding="utf-8",
            )
            fifo.write_text(
                json.dumps(_comparison_payload(target="tlul_fifo_sync", value=24, ratio=2.64)) + "\n",
                encoding="utf-8",
            )
            gate = root / "gate.json"
            gate.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "scope": "campaign_threshold_policy_gate",
                        "selection": {"profile_name": "per_target_ready"},
                        "outcome": {
                            "status": "promote_design_specific_v2",
                            "selected_policy_mode": "per_target",
                            "selected_scenario_name": "candidate_design_specific_minimal_progress",
                            "selected_thresholds": [
                                {
                                    "kind": "toggle_bits_hit",
                                    "value": 5,
                                    "aggregation": "bitwise_or_across_trials",
                                },
                                {
                                    "kind": "toggle_bits_hit",
                                    "value": 24,
                                    "aggregation": "bitwise_or_across_trials",
                                },
                            ],
                            "selected_paths": [str(socket), str(fifo)],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_active_scoreboard(policy_gate_path=gate)
            self.assertEqual(payload["scope"], "campaign_speed_scoreboard_active")
            self.assertEqual(payload["policy_gate_status"], "promote_design_specific_v2")
            self.assertEqual(payload["selected_profile_name"], "per_target_ready")
            self.assertEqual(payload["selected_policy_mode"], "per_target")
            self.assertEqual(payload["summary"]["comparison_ready_count"], 2)
            self.assertEqual(payload["summary"]["hybrid_win_count"], 2)

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            socket = root / "socket.json"
            fifo = root / "fifo.json"
            gate = root / "gate.json"
            json_out = root / "active.json"
            socket.write_text(
                json.dumps(_comparison_payload(target="tlul_socket_m1", value=3, ratio=15.0)) + "\n",
                encoding="utf-8",
            )
            fifo.write_text(
                json.dumps(_comparison_payload(target="tlul_fifo_sync", value=3, ratio=1.16)) + "\n",
                encoding="utf-8",
            )
            gate.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "scope": "campaign_threshold_policy_gate",
                        "selection": {"profile_name": "common_v1_hold"},
                        "outcome": {
                            "status": "hold_current_v1",
                            "selected_policy_mode": "common",
                            "selected_scenario_name": "checked_in_common_v1",
                            "selected_thresholds": [
                                {
                                    "kind": "toggle_bits_hit",
                                    "value": 3,
                                    "aggregation": "bitwise_or_across_trials",
                                }
                            ],
                            "selected_paths": [str(socket), str(fifo)],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            argv = [
                "audit_campaign_active_scoreboard.py",
                "--policy-gate",
                str(gate),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_speed_scoreboard_active")
            self.assertEqual(payload["selected_profile_name"], "common_v1_hold")
            self.assertEqual(payload["selected_scenario_name"], "checked_in_common_v1")


if __name__ == "__main__":
    unittest.main()
