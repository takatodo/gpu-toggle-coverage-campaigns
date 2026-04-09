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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_checkpoint_readiness.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _active_row(target: str, ratio: float) -> dict[str, object]:
    return {
        "target": target,
        "comparison_ready": True,
        "winner": "hybrid",
        "speedup_ratio": ratio,
    }


def _active_scoreboard(*, rows: list[dict[str, object]], weakest_target: str, weakest_ratio: float) -> dict[str, object]:
    return {
        "selected_profile_name": "per_target_ready",
        "selected_policy_mode": "per_target",
        "selected_scenario_name": "candidate_design_specific_minimal_progress",
        "policy_gate_status": "promote_design_specific_v2",
        "rows": rows,
        "summary": {
            "comparison_ready_count": len(rows),
            "hybrid_win_count": len(rows),
            "weakest_hybrid_win": {
                "target": weakest_target,
                "speedup_ratio": weakest_ratio,
            },
        },
    }


class AuditCampaignCheckpointReadinessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_checkpoint_readiness_test", MODULE_PATH)

    def test_reports_single_family_checkpoint_ready(self) -> None:
        active = _active_scoreboard(
            rows=[
                _active_row("tlul_socket_m1", 22.5),
                _active_row("tlul_fifo_sync", 2.6),
                _active_row("tlul_request_loopback", 4.8),
                _active_row("tlul_err", 14.0),
                _active_row("tlul_sink", 10.4),
            ],
            weakest_target="tlul_fifo_sync",
            weakest_ratio=2.6,
        )
        ready = {"rows": [{"slice_name": name} for name in ("a", "b", "c", "d", "e", "f", "g", "h", "i")]}

        payload = self.module.build_checkpoint_readiness(
            active_scoreboard=active,
            ready_scoreboard=ready,
            minimum_ready_surfaces=5,
            minimum_strong_margin=2.0,
            minimum_family_count=2,
        )

        self.assertEqual(payload["decision"]["readiness"], "single_family_checkpoint_ready")
        self.assertEqual(
            payload["decision"]["recommended_next_task"],
            "decide_if_single_family_checkpoint_is_acceptable",
        )
        self.assertEqual(payload["summary"]["family_diversity_count"], 1)
        self.assertEqual(payload["summary"]["family_counts"], {"OpenTitan.TLUL": 5})

    def test_reports_cross_family_checkpoint_ready_when_diverse(self) -> None:
        active = _active_scoreboard(
            rows=[
                _active_row("tlul_socket_m1", 22.5),
                _active_row("xbar_main", 3.1),
                _active_row("demo_misc", 5.0),
                _active_row("tlul_err", 14.0),
                _active_row("tlul_sink", 10.4),
            ],
            weakest_target="xbar_main",
            weakest_ratio=3.1,
        )
        ready = {"rows": [{"slice_name": name} for name in ("a", "b", "c", "d", "e")]}

        payload = self.module.build_checkpoint_readiness(
            active_scoreboard=active,
            ready_scoreboard=ready,
            minimum_ready_surfaces=5,
            minimum_strong_margin=2.0,
            minimum_family_count=2,
        )

        self.assertEqual(payload["decision"]["readiness"], "cross_family_checkpoint_ready")
        self.assertEqual(payload["decision"]["recommended_next_task"], "choose_next_expansion_axis")
        self.assertGreaterEqual(payload["summary"]["family_diversity_count"], 2)

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            active_path = root / "active.json"
            ready_path = root / "ready.json"
            json_out = root / "checkpoint.json"
            active_path.write_text(
                json.dumps(
                    _active_scoreboard(
                        rows=[
                            _active_row("tlul_socket_m1", 22.5),
                            _active_row("tlul_fifo_sync", 2.6),
                            _active_row("tlul_request_loopback", 4.8),
                            _active_row("tlul_err", 14.0),
                            _active_row("tlul_sink", 10.4),
                        ],
                        weakest_target="tlul_fifo_sync",
                        weakest_ratio=2.6,
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            ready_path.write_text(
                json.dumps({"rows": [{"slice_name": name} for name in ("a", "b", "c", "d", "e", "f")]}) + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_checkpoint_readiness.py",
                "--active-scoreboard-json",
                str(active_path),
                "--ready-scoreboard-json",
                str(ready_path),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["decision"]["readiness"], "single_family_checkpoint_ready")


if __name__ == "__main__":
    unittest.main()
