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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_threshold_policy_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _scenario(*, name: str, policy_mode: str, threshold_values: list[int], weakest_ratio: float) -> dict:
    threshold_keys = [f"toggle_bits_hit:{value}:bitwise_or_across_trials" for value in threshold_values]
    return {
        "name": name,
        "policy_mode": policy_mode,
        "paths": [f"/tmp/{name}.json"],
        "scoreboard_summary": {
            "comparison_ready_count": 2,
            "hybrid_win_count": 2,
            "threshold_keys": threshold_keys,
            "weakest_hybrid_win": {
                "target": "tlul_fifo_sync",
                "speedup_ratio": weakest_ratio,
            },
        },
    }


class AuditCampaignThresholdPolicyGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_threshold_policy_gate_test", MODULE_PATH)

    def test_holds_common_v1_when_per_target_is_disallowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "profiles").mkdir()
            (root / "profiles" / "common_v1_hold.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "common_v1_hold",
                        "allow_per_target_thresholds": False,
                        "require_matching_thresholds": True,
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
                    _scenario(name="checked_in_common_v1", policy_mode="common", threshold_values=[3], weakest_ratio=1.16),
                    _scenario(name="candidate_common_threshold5", policy_mode="common", threshold_values=[5], weakest_ratio=1.20),
                    _scenario(
                        name="candidate_design_specific_minimal_progress",
                        policy_mode="per_target",
                        threshold_values=[5, 24],
                        weakest_ratio=2.64,
                    ),
                ],
            }
            selection = {
                "profile_name": "common_v1_hold",
                "allow_per_target_thresholds": False,
                "require_matching_thresholds": True,
            }
            payload = self.module.build_gate(
                options_payload=options,
                selection_payload=selection,
                options_path=root / "options.json",
                selection_path=root / "selection.json",
            )
            self.assertEqual(payload["outcome"]["status"], "hold_current_v1")
            self.assertEqual(payload["outcome"]["reason"], "per_target_thresholds_not_allowed")
            self.assertEqual(payload["outcome"]["selected_scenario_name"], "checked_in_common_v1")
            self.assertEqual(payload["selection"]["profile_name"], "common_v1_hold")

    def test_promotes_design_specific_v2_when_per_target_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "profiles").mkdir()
            (root / "profiles" / "per_target_blocked.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "per_target_blocked",
                        "allow_per_target_thresholds": True,
                        "require_matching_thresholds": True,
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
                    _scenario(name="checked_in_common_v1", policy_mode="common", threshold_values=[3], weakest_ratio=1.16),
                    _scenario(name="candidate_common_threshold5", policy_mode="common", threshold_values=[5], weakest_ratio=1.20),
                    _scenario(
                        name="candidate_design_specific_minimal_progress",
                        policy_mode="per_target",
                        threshold_values=[5, 24],
                        weakest_ratio=2.64,
                    ),
                ],
            }
            selection = {
                "profile_name": "per_target_blocked",
                "allow_per_target_thresholds": True,
                "require_matching_thresholds": True,
            }
            payload = self.module.build_gate(
                options_payload=options,
                selection_payload=selection,
                options_path=root / "options.json",
                selection_path=root / "selection.json",
            )
            self.assertEqual(payload["outcome"]["status"], "promote_design_specific_v2")
            self.assertEqual(
                payload["outcome"]["selected_scenario_name"],
                "candidate_design_specific_minimal_progress",
            )
            self.assertEqual(payload["outcome"]["selected_policy_mode"], "per_target")
            self.assertEqual(payload["selection"]["profile_name"], "per_target_blocked")

    def test_promotes_common_v2_when_policy_options_already_choose_common_candidate(self) -> None:
        options = {
            "policy": {"minimum_strong_margin": 2.0},
            "decision": {
                "recommended_policy": "promote_common_threshold_v2",
                "reason": "common_candidate_is_strong_and_ready",
            },
            "scenarios": [
                _scenario(name="checked_in_common_v1", policy_mode="common", threshold_values=[3], weakest_ratio=1.16),
                _scenario(name="candidate_common_threshold5", policy_mode="common", threshold_values=[5], weakest_ratio=2.20),
                _scenario(
                    name="candidate_design_specific_minimal_progress",
                    policy_mode="per_target",
                    threshold_values=[5, 24],
                    weakest_ratio=2.64,
                ),
            ],
        }
        selection = {"allow_per_target_thresholds": False, "require_matching_thresholds": True}
        payload = self.module.build_gate(
            options_payload=options,
            selection_payload=selection,
            options_path=Path("/tmp/options.json"),
            selection_path=Path("/tmp/selection.json"),
        )
        self.assertEqual(payload["outcome"]["status"], "promote_common_v2")
        self.assertEqual(payload["outcome"]["selected_scenario_name"], "candidate_common_threshold5")

    def test_build_gate_merges_extra_comparison_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "profiles").mkdir()
            (root / "profiles" / "per_target_ready.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "per_target_ready",
                        "allow_per_target_thresholds": True,
                        "require_matching_thresholds": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            extra = root / "loopback.json"
            options = {
                "policy": {"minimum_strong_margin": 2.0},
                "decision": {
                    "recommended_policy": "decide_if_design_specific_thresholds_are_allowed",
                    "reason": "design_specific_candidate_is_strong_but_common_candidate_is_not",
                },
                "scenarios": [
                    _scenario(name="checked_in_common_v1", policy_mode="common", threshold_values=[3], weakest_ratio=1.16),
                    _scenario(name="candidate_common_threshold5", policy_mode="common", threshold_values=[5], weakest_ratio=1.20),
                    _scenario(
                        name="candidate_design_specific_minimal_progress",
                        policy_mode="per_target",
                        threshold_values=[5, 24],
                        weakest_ratio=2.64,
                    ),
                ],
            }
            selection = {
                "profile_name": "per_target_ready",
                "allow_per_target_thresholds": True,
                "require_matching_thresholds": False,
                "extra_comparison_paths": [str(extra)],
            }
            payload = self.module.build_gate(
                options_payload=options,
                selection_payload=selection,
                options_path=root / "options.json",
                selection_path=root / "selection.json",
            )
            self.assertEqual(payload["selection"]["extra_comparison_paths"], [str(extra.resolve())])
            self.assertEqual(payload["outcome"]["extra_selected_paths"], [str(extra.resolve())])
            self.assertIn(str(extra.resolve()), payload["outcome"]["selected_paths"])

    def test_rejects_selection_when_profile_and_booleans_disagree(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "profiles").mkdir()
            profile_path = root / "profiles" / "common_v1_hold.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "common_v1_hold",
                        "allow_per_target_thresholds": False,
                        "require_matching_thresholds": True,
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
                    _scenario(name="checked_in_common_v1", policy_mode="common", threshold_values=[3], weakest_ratio=1.16),
                ],
            }
            with self.assertRaisesRegex(ValueError, "selection.json disagrees with profile"):
                self.module.build_gate(
                    options_payload=options,
                    selection_payload={
                        "profile_name": "common_v1_hold",
                        "allow_per_target_thresholds": True,
                        "require_matching_thresholds": True,
                    },
                    options_path=root / "options.json",
                    selection_path=root / "selection.json",
                )

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            options = root / "options.json"
            selection = root / "selection.json"
            json_out = root / "gate.json"
            options.write_text(
                json.dumps(
                    {
                        "policy": {"minimum_strong_margin": 2.0},
                        "decision": {
                            "recommended_policy": "decide_if_design_specific_thresholds_are_allowed",
                            "reason": "design_specific_candidate_is_strong_but_common_candidate_is_not",
                        },
                        "scenarios": [
                            _scenario(name="checked_in_common_v1", policy_mode="common", threshold_values=[3], weakest_ratio=1.16),
                            _scenario(name="candidate_common_threshold5", policy_mode="common", threshold_values=[5], weakest_ratio=1.20),
                            _scenario(
                                name="candidate_design_specific_minimal_progress",
                                policy_mode="per_target",
                                threshold_values=[5, 24],
                                weakest_ratio=2.64,
                            ),
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            selection.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profile_name": "per_target_blocked",
                        "allow_per_target_thresholds": True,
                        "require_matching_thresholds": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "profiles").mkdir()
            (root / "profiles" / "per_target_blocked.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "per_target_blocked",
                        "allow_per_target_thresholds": True,
                        "require_matching_thresholds": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            argv = [
                "audit_campaign_threshold_policy_gate.py",
                "--policy-options-json",
                str(options),
                "--selection-config",
                str(selection),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_threshold_policy_gate")
            self.assertEqual(payload["outcome"]["status"], "promote_design_specific_v2")


if __name__ == "__main__":
    unittest.main()
