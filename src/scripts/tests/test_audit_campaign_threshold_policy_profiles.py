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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_threshold_policy_profiles.py"


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


def _scenario(*, name: str, policy_mode: str, threshold_values: list[int], weakest_ratio: float, paths: list[str]) -> dict:
    threshold_keys = [f"toggle_bits_hit:{value}:bitwise_or_across_trials" for value in threshold_values]
    return {
        "name": name,
        "policy_mode": policy_mode,
        "paths": paths,
        "scoreboard_summary": {
            "comparison_ready_count": 2,
            "hybrid_win_count": 2,
            "threshold_keys": threshold_keys,
            "weakest_hybrid_win": {"target": "tlul_fifo_sync", "speedup_ratio": weakest_ratio},
        },
    }


class AuditCampaignThresholdPolicyProfilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_threshold_policy_profiles_test", MODULE_PATH)

    def test_build_profiles_matrix_classifies_named_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            socket_v1 = root / "socket_v1.json"
            fifo_v1 = root / "fifo_v1.json"
            socket_v5 = root / "socket_v5.json"
            fifo_seq1 = root / "fifo_seq1.json"
            socket_v1.write_text(json.dumps(_comparison_payload(target="tlul_socket_m1", value=3, ratio=15.0)) + "\n", encoding="utf-8")
            fifo_v1.write_text(json.dumps(_comparison_payload(target="tlul_fifo_sync", value=3, ratio=1.16)) + "\n", encoding="utf-8")
            socket_v5.write_text(json.dumps(_comparison_payload(target="tlul_socket_m1", value=5, ratio=22.5)) + "\n", encoding="utf-8")
            fifo_seq1.write_text(json.dumps(_comparison_payload(target="tlul_fifo_sync", value=24, ratio=2.64)) + "\n", encoding="utf-8")
            (profiles_dir / "common_v1_hold.json").write_text(
                json.dumps(
                    {
                        "name": "common_v1_hold",
                        "allow_per_target_thresholds": False,
                        "require_matching_thresholds": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (profiles_dir / "per_target_blocked.json").write_text(
                json.dumps(
                    {
                        "name": "per_target_blocked",
                        "allow_per_target_thresholds": True,
                        "require_matching_thresholds": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (profiles_dir / "per_target_ready.json").write_text(
                json.dumps(
                    {
                        "name": "per_target_ready",
                        "allow_per_target_thresholds": True,
                        "require_matching_thresholds": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            options = {
                "policy": {"minimum_strong_margin": 2.0},
                "decision": {
                    "recommended_policy": "decide_if_design_specific_thresholds_are_allowed",
                    "reason": "design_specific_candidate_is_strong_but_common_candidate_is_not",
                },
                "scenarios": [
                    _scenario(
                        name="checked_in_common_v1",
                        policy_mode="common",
                        threshold_values=[3],
                        weakest_ratio=1.16,
                        paths=[str(socket_v1), str(fifo_v1)],
                    ),
                    _scenario(
                        name="candidate_common_threshold5",
                        policy_mode="common",
                        threshold_values=[5],
                        weakest_ratio=1.20,
                        paths=[str(socket_v5), str(fifo_seq1)],
                    ),
                    _scenario(
                        name="candidate_design_specific_minimal_progress",
                        policy_mode="per_target",
                        threshold_values=[5, 24],
                        weakest_ratio=2.64,
                        paths=[str(socket_v5), str(fifo_seq1)],
                    ),
                ],
            }

            payload = self.module.build_profiles_matrix(
                options_payload=options,
                options_path=root / "options.json",
                profiles_dir=profiles_dir,
                current_selection_payload={"profile_name": "common_v1_hold"},
                current_selection_path=root / "selection.json",
                minimum_ready_surfaces=2,
                minimum_strong_margin=2.0,
            )
            self.assertEqual(payload["scope"], "campaign_threshold_policy_profiles")
            self.assertEqual(payload["summary"]["current_profile_name"], "common_v1_hold")
            self.assertEqual(payload["summary"]["current_profile_classification"], "active_like")
            self.assertIn("common_v1_hold", payload["summary"]["active_like_profiles"])
            self.assertIn("per_target_blocked", payload["summary"]["blocked_profiles"])
            self.assertIn("per_target_ready", payload["summary"]["ready_profiles"])

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            socket_v1 = root / "socket_v1.json"
            fifo_v1 = root / "fifo_v1.json"
            socket_v5 = root / "socket_v5.json"
            fifo_seq1 = root / "fifo_seq1.json"
            socket_v1.write_text(json.dumps(_comparison_payload(target="tlul_socket_m1", value=3, ratio=15.0)) + "\n", encoding="utf-8")
            fifo_v1.write_text(json.dumps(_comparison_payload(target="tlul_fifo_sync", value=3, ratio=1.16)) + "\n", encoding="utf-8")
            socket_v5.write_text(json.dumps(_comparison_payload(target="tlul_socket_m1", value=5, ratio=22.5)) + "\n", encoding="utf-8")
            fifo_seq1.write_text(json.dumps(_comparison_payload(target="tlul_fifo_sync", value=24, ratio=2.64)) + "\n", encoding="utf-8")
            (profiles_dir / "common_v1_hold.json").write_text(
                json.dumps(
                    {
                        "name": "common_v1_hold",
                        "allow_per_target_thresholds": False,
                        "require_matching_thresholds": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (profiles_dir / "per_target_ready.json").write_text(
                json.dumps(
                    {
                        "name": "per_target_ready",
                        "allow_per_target_thresholds": True,
                        "require_matching_thresholds": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            options = root / "options.json"
            options.write_text(
                json.dumps(
                    {
                        "policy": {"minimum_strong_margin": 2.0},
                        "decision": {
                            "recommended_policy": "decide_if_design_specific_thresholds_are_allowed",
                            "reason": "design_specific_candidate_is_strong_but_common_candidate_is_not",
                        },
                        "scenarios": [
                            _scenario(
                                name="checked_in_common_v1",
                                policy_mode="common",
                                threshold_values=[3],
                                weakest_ratio=1.16,
                                paths=[str(socket_v1), str(fifo_v1)],
                            ),
                            _scenario(
                                name="candidate_design_specific_minimal_progress",
                                policy_mode="per_target",
                                threshold_values=[5, 24],
                                weakest_ratio=2.64,
                                paths=[str(socket_v5), str(fifo_seq1)],
                            ),
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            json_out = root / "profiles.json"
            selection = root / "selection.json"
            selection.write_text(json.dumps({"profile_name": "per_target_ready"}) + "\n", encoding="utf-8")
            argv = [
                "audit_campaign_threshold_policy_profiles.py",
                "--policy-options-json",
                str(options),
                "--profiles-dir",
                str(profiles_dir),
                "--selection-config",
                str(selection),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_threshold_policy_profiles")
            self.assertEqual(payload["summary"]["profile_count"], 2)
            self.assertEqual(payload["summary"]["current_profile_name"], "per_target_ready")


if __name__ == "__main__":
    unittest.main()
