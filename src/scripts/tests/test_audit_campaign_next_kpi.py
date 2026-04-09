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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_next_kpi.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _scoreboard_summary(
    *,
    comparison_ready_count: int,
    hybrid_win_count: int,
    all_thresholds_match: bool = True,
    weakest_ratio: float | None = None,
):
    summary = {
        "comparison_ready_count": comparison_ready_count,
        "hybrid_win_count": hybrid_win_count,
        "all_thresholds_match": all_thresholds_match,
    }
    if weakest_ratio is not None:
        summary["weakest_hybrid_win"] = {
            "target": "demo",
            "speedup_ratio": weakest_ratio,
        }
    return {
        "schema_version": 1,
        "scope": "campaign_speed_scoreboard",
        "summary": summary,
        "rows": [],
    }


class AuditCampaignNextKpiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_next_kpi_test", MODULE_PATH)

    def test_recommends_stronger_thresholds_when_margin_is_narrow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            scoreboard = Path(tmpdir) / "campaign_speed_scoreboard.json"
            scoreboard.write_text(
                json.dumps(
                    _scoreboard_summary(
                        comparison_ready_count=2,
                        hybrid_win_count=2,
                        weakest_ratio=1.16,
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_audit(scoreboard, minimum_ready_surfaces=2, minimum_strong_margin=2.0)
            self.assertEqual(payload["decision"]["recommended_next_kpi"], "stronger_thresholds")
            self.assertEqual(payload["decision"]["reason"], "weakest_hybrid_win_below_margin")

    def test_recommends_broader_design_count_when_margin_is_strong(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            scoreboard = Path(tmpdir) / "campaign_speed_scoreboard.json"
            scoreboard.write_text(
                json.dumps(
                    _scoreboard_summary(
                        comparison_ready_count=2,
                        hybrid_win_count=2,
                        weakest_ratio=3.5,
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_audit(scoreboard, minimum_ready_surfaces=2, minimum_strong_margin=2.0)
            self.assertEqual(payload["decision"]["recommended_next_kpi"], "broader_design_count")

    def test_main_writes_stabilize_decision_when_ready_count_is_too_low(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scoreboard = root / "campaign_speed_scoreboard.json"
            scoreboard.write_text(
                json.dumps(
                    _scoreboard_summary(
                        comparison_ready_count=1,
                        hybrid_win_count=1,
                        weakest_ratio=10.0,
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            json_out = root / "campaign_next_kpi_audit.json"
            argv = [
                "audit_campaign_next_kpi.py",
                "--scoreboard",
                str(scoreboard),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["decision"]["recommended_next_kpi"], "stabilize_existing_surfaces")
            self.assertEqual(payload["decision"]["reason"], "insufficient_ready_comparisons")

    def test_build_audit_can_relax_threshold_match_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            scoreboard = Path(tmpdir) / "campaign_speed_scoreboard.json"
            scoreboard.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "scope": "campaign_speed_scoreboard",
                        "summary": {
                            "comparison_ready_count": 2,
                            "hybrid_win_count": 2,
                            "all_thresholds_match": False,
                            "weakest_hybrid_win": {
                                "target": "demo",
                                "speedup_ratio": 2.64,
                            },
                        },
                        "rows": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.module.build_audit(
                scoreboard,
                minimum_ready_surfaces=2,
                minimum_strong_margin=2.0,
                require_matching_thresholds=False,
            )
            self.assertEqual(payload["decision"]["recommended_next_kpi"], "broader_design_count")
            self.assertFalse(payload["policy"]["require_matching_thresholds"])

    def test_main_accepts_policy_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            socket = root / "socket.json"
            fifo = root / "fifo.json"
            gate = root / "gate.json"
            socket.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "ok",
                        "target": "tlul_socket_m1",
                        "campaign_threshold": {
                            "kind": "toggle_bits_hit",
                            "value": 3,
                            "aggregation": "bitwise_or_across_trials",
                        },
                        "comparison_ready": True,
                        "winner": "hybrid",
                        "speedup_ratio": 15.0,
                        "reject_reason": None,
                        "baseline": {"campaign_measurement": {"wall_time_ms": 20.0}},
                        "hybrid": {"campaign_measurement": {"wall_time_ms": 10.0}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            fifo.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "ok",
                        "target": "tlul_fifo_sync",
                        "campaign_threshold": {
                            "kind": "toggle_bits_hit",
                            "value": 3,
                            "aggregation": "bitwise_or_across_trials",
                        },
                        "comparison_ready": True,
                        "winner": "hybrid",
                        "speedup_ratio": 1.16,
                        "reject_reason": None,
                        "baseline": {"campaign_measurement": {"wall_time_ms": 20.0}},
                        "hybrid": {"campaign_measurement": {"wall_time_ms": 10.0}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            gate.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "scope": "campaign_threshold_policy_gate",
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
                        "selection": {
                            "allow_per_target_thresholds": False,
                            "require_matching_thresholds": True,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            json_out = root / "campaign_next_kpi_audit.json"
            argv = [
                "audit_campaign_next_kpi.py",
                "--policy-gate",
                str(gate),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["policy_gate_status"], "hold_current_v1")
            self.assertEqual(payload["selected_scenario_name"], "checked_in_common_v1")
            self.assertEqual(payload["decision"]["recommended_next_kpi"], "stronger_thresholds")


if __name__ == "__main__":
    unittest.main()
