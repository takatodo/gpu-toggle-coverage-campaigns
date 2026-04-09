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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "set_campaign_threshold_policy.py"


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


def _options_payload(socket_v1: Path, fifo_v1: Path, socket_v5: Path, fifo_seq1: Path) -> dict:
    return {
        "policy": {"minimum_strong_margin": 2.0},
        "decision": {
            "recommended_policy": "decide_if_design_specific_thresholds_are_allowed",
            "reason": "design_specific_candidate_is_strong_but_common_candidate_is_not",
        },
        "scenarios": [
            {
                "name": "checked_in_common_v1",
                "policy_mode": "common",
                "paths": [str(socket_v1), str(fifo_v1)],
                "scoreboard_summary": {
                    "comparison_ready_count": 2,
                    "hybrid_win_count": 2,
                    "threshold_keys": ["toggle_bits_hit:3:bitwise_or_across_trials"],
                    "weakest_hybrid_win": {"target": "tlul_fifo_sync", "speedup_ratio": 1.16},
                },
            },
            {
                "name": "candidate_design_specific_minimal_progress",
                "policy_mode": "per_target",
                "paths": [str(socket_v5), str(fifo_seq1)],
                "scoreboard_summary": {
                    "comparison_ready_count": 2,
                    "hybrid_win_count": 2,
                    "threshold_keys": [
                        "toggle_bits_hit:5:bitwise_or_across_trials",
                        "toggle_bits_hit:24:bitwise_or_across_trials",
                    ],
                    "weakest_hybrid_win": {"target": "tlul_fifo_sync", "speedup_ratio": 2.64},
                },
            },
        ],
    }


class SetCampaignThresholdPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("set_campaign_threshold_policy_test", MODULE_PATH)

    def test_apply_policy_profile_writes_selection_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "per_target_ready.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "per_target_ready",
                        "allow_per_target_thresholds": True,
                        "require_matching_thresholds": False,
                        "notes": "ready profile",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            socket_v1 = root / "socket_v1.json"
            fifo_v1 = root / "fifo_v1.json"
            socket_v5 = root / "socket_v5.json"
            fifo_seq1 = root / "fifo_seq1.json"
            socket_v1.write_text(json.dumps(_comparison_payload(target="tlul_socket_m1", value=3, ratio=15.0)) + "\n", encoding="utf-8")
            fifo_v1.write_text(json.dumps(_comparison_payload(target="tlul_fifo_sync", value=3, ratio=1.16)) + "\n", encoding="utf-8")
            socket_v5.write_text(json.dumps(_comparison_payload(target="tlul_socket_m1", value=5, ratio=22.5)) + "\n", encoding="utf-8")
            fifo_seq1.write_text(json.dumps(_comparison_payload(target="tlul_fifo_sync", value=24, ratio=2.64)) + "\n", encoding="utf-8")
            options = root / "options.json"
            options.write_text(json.dumps(_options_payload(socket_v1, fifo_v1, socket_v5, fifo_seq1)) + "\n", encoding="utf-8")

            selection = root / "selection.json"
            gate_json = root / "gate.json"
            scoreboard_json = root / "active.json"
            next_kpi_json = root / "next.json"
            selection.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profile_name": "common_v1_hold",
                        "allow_per_target_thresholds": False,
                        "require_matching_thresholds": True,
                        "extra_comparison_paths": ["output/validation/tlul_request_loopback_time_to_threshold_comparison.json"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            payload = self.module.apply_policy_profile(
                profile_name="per_target_ready",
                profiles_dir=profiles_dir,
                options_path=options,
                selection_path=selection,
                gate_json_path=gate_json,
                scoreboard_json_path=scoreboard_json,
                next_kpi_json_path=next_kpi_json,
                minimum_ready_surfaces=2,
                minimum_strong_margin=2.0,
            )

            self.assertEqual(payload["applied_profile_name"], "per_target_ready")
            self.assertEqual(payload["policy_gate_status"], "promote_design_specific_v2")
            self.assertEqual(payload["recommended_next_kpi"], "broader_design_count")
            selection_payload = json.loads(selection.read_text(encoding="utf-8"))
            self.assertEqual(selection_payload["profile_name"], "per_target_ready")
            self.assertEqual(
                selection_payload["extra_comparison_paths"],
                ["output/validation/tlul_request_loopback_time_to_threshold_comparison.json"],
            )
            scoreboard_payload = json.loads(scoreboard_json.read_text(encoding="utf-8"))
            self.assertEqual(scoreboard_payload["selected_profile_name"], "per_target_ready")

    def test_main_writes_summary_json_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "common_v1_hold.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "common_v1_hold",
                        "allow_per_target_thresholds": False,
                        "require_matching_thresholds": True,
                        "notes": "common profile",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            socket_v1 = root / "socket_v1.json"
            fifo_v1 = root / "fifo_v1.json"
            socket_v5 = root / "socket_v5.json"
            fifo_seq1 = root / "fifo_seq1.json"
            socket_v1.write_text(json.dumps(_comparison_payload(target="tlul_socket_m1", value=3, ratio=15.0)) + "\n", encoding="utf-8")
            fifo_v1.write_text(json.dumps(_comparison_payload(target="tlul_fifo_sync", value=3, ratio=1.16)) + "\n", encoding="utf-8")
            socket_v5.write_text(json.dumps(_comparison_payload(target="tlul_socket_m1", value=5, ratio=22.5)) + "\n", encoding="utf-8")
            fifo_seq1.write_text(json.dumps(_comparison_payload(target="tlul_fifo_sync", value=24, ratio=2.64)) + "\n", encoding="utf-8")
            options = root / "options.json"
            options.write_text(json.dumps(_options_payload(socket_v1, fifo_v1, socket_v5, fifo_seq1)) + "\n", encoding="utf-8")
            selection = root / "selection.json"
            gate_json = root / "gate.json"
            scoreboard_json = root / "active.json"
            next_kpi_json = root / "next.json"

            argv = [
                "set_campaign_threshold_policy.py",
                "--profile-name",
                "common_v1_hold",
                "--profiles-dir",
                str(profiles_dir),
                "--policy-options-json",
                str(options),
                "--selection-config",
                str(selection),
                "--gate-json-out",
                str(gate_json),
                "--scoreboard-json-out",
                str(scoreboard_json),
                "--next-kpi-json-out",
                str(next_kpi_json),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            next_payload = json.loads(next_kpi_json.read_text(encoding="utf-8"))
            self.assertEqual(next_payload["selected_scenario_name"], "checked_in_common_v1")


if __name__ == "__main__":
    unittest.main()
