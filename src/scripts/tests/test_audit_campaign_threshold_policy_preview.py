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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_threshold_policy_preview.py"


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


class AuditCampaignThresholdPolicyPreviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_threshold_policy_preview_test", MODULE_PATH)

    def test_preview_shows_allow_only_is_insufficient_but_flip_both_unblocks_broader_design_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            socket_v1 = root / "socket_v1.json"
            fifo_v1 = root / "fifo_v1.json"
            socket_v5 = root / "socket_v5.json"
            fifo_v5 = root / "fifo_v5.json"
            fifo_seq1 = root / "fifo_seq1.json"
            socket_v1.write_text(json.dumps(_comparison_payload(target="tlul_socket_m1", value=3, ratio=15.0)) + "\n", encoding="utf-8")
            fifo_v1.write_text(json.dumps(_comparison_payload(target="tlul_fifo_sync", value=3, ratio=1.16)) + "\n", encoding="utf-8")
            socket_v5.write_text(json.dumps(_comparison_payload(target="tlul_socket_m1", value=5, ratio=22.5)) + "\n", encoding="utf-8")
            fifo_v5.write_text(json.dumps(_comparison_payload(target="tlul_fifo_sync", value=5, ratio=1.20)) + "\n", encoding="utf-8")
            fifo_seq1.write_text(json.dumps(_comparison_payload(target="tlul_fifo_sync", value=24, ratio=2.64)) + "\n", encoding="utf-8")

            options = {
                "policy": {"minimum_strong_margin": 2.0},
                "decision": {
                    "recommended_policy": "decide_if_design_specific_thresholds_are_allowed",
                    "reason": "design_specific_candidate_is_strong_but_common_candidate_is_not",
                },
                "scenarios": [
                    {
                        "name": "checked_in_common_v1",
                        "label": "checked-in common threshold v1",
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
                        "name": "candidate_common_threshold5",
                        "label": "common threshold5",
                        "policy_mode": "common",
                        "paths": [str(socket_v5), str(fifo_v5)],
                        "scoreboard_summary": {
                            "comparison_ready_count": 2,
                            "hybrid_win_count": 2,
                            "threshold_keys": ["toggle_bits_hit:5:bitwise_or_across_trials"],
                            "weakest_hybrid_win": {"target": "tlul_fifo_sync", "speedup_ratio": 1.20},
                        },
                    },
                    {
                        "name": "candidate_design_specific_minimal_progress",
                        "label": "design-specific",
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
            selection = {"allow_per_target_thresholds": False, "require_matching_thresholds": True}

            payload = self.module.build_preview(
                options_payload=options,
                selection_payload=selection,
                options_path=root / "options.json",
                selection_path=root / "selection.json",
                minimum_ready_surfaces=2,
                minimum_strong_margin=2.0,
            )
            self.assertEqual(payload["variants"]["current_selection"]["gate"]["outcome"]["status"], "hold_current_v1")
            self.assertEqual(payload["variants"]["flip_allow_per_target"]["gate"]["outcome"]["status"], "promote_design_specific_v2")
            self.assertEqual(payload["variants"]["flip_both"]["gate"]["outcome"]["status"], "promote_design_specific_v2")
            self.assertEqual(
                payload["variants"]["current_selection"]["active_next_kpi"]["decision"]["recommended_next_kpi"],
                "stronger_thresholds",
            )
            self.assertEqual(
                payload["variants"]["flip_allow_per_target"]["active_next_kpi"]["decision"]["recommended_next_kpi"],
                "stabilize_existing_surfaces",
            )
            self.assertEqual(
                payload["variants"]["flip_both"]["active_next_kpi"]["decision"]["recommended_next_kpi"],
                "broader_design_count",
            )
            self.assertTrue(payload["summary"]["flip_allow_changes_active_line"])
            self.assertTrue(payload["summary"]["flip_allow_changes_next_kpi"])
            self.assertTrue(payload["summary"]["flip_allow_triggers_threshold_schema_mismatch"])
            self.assertTrue(payload["summary"]["flip_both_unlocks_broader_design_count"])

    def test_preview_allows_hypothetical_flips_when_selection_is_profile_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            socket_v1 = root / "socket_v1.json"
            fifo_v1 = root / "fifo_v1.json"
            socket_v5 = root / "socket_v5.json"
            fifo_seq1 = root / "fifo_seq1.json"
            for path, payload in (
                (socket_v1, _comparison_payload(target="tlul_socket_m1", value=3, ratio=15.0)),
                (fifo_v1, _comparison_payload(target="tlul_fifo_sync", value=3, ratio=1.16)),
                (socket_v5, _comparison_payload(target="tlul_socket_m1", value=5, ratio=22.5)),
                (fifo_seq1, _comparison_payload(target="tlul_fifo_sync", value=24, ratio=2.64)),
            ):
                path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

            options = {
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
            selection = {
                "schema_version": 1,
                "profile_name": "per_target_ready",
                "allow_per_target_thresholds": True,
                "require_matching_thresholds": False,
            }

            payload = self.module.build_preview(
                options_payload=options,
                selection_payload=selection,
                options_path=root / "options.json",
                selection_path=root / "selection.json",
                minimum_ready_surfaces=2,
                minimum_strong_margin=2.0,
            )
            self.assertEqual(
                payload["variants"]["current_selection"]["gate"]["outcome"]["status"],
                "promote_design_specific_v2",
            )
            self.assertEqual(
                payload["variants"]["flip_allow_per_target"]["gate"]["outcome"]["status"],
                "hold_current_v1",
            )
            self.assertIsNone(
                payload["variants"]["flip_allow_per_target"]["gate"]["selection"]["profile_name"]
            )

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            socket_v1 = root / "socket_v1.json"
            fifo_v1 = root / "fifo_v1.json"
            socket_v5 = root / "socket_v5.json"
            fifo_v5 = root / "fifo_v5.json"
            fifo_seq1 = root / "fifo_seq1.json"
            for path, payload in (
                (socket_v1, _comparison_payload(target="tlul_socket_m1", value=3, ratio=15.0)),
                (fifo_v1, _comparison_payload(target="tlul_fifo_sync", value=3, ratio=1.16)),
                (socket_v5, _comparison_payload(target="tlul_socket_m1", value=5, ratio=22.5)),
                (fifo_v5, _comparison_payload(target="tlul_fifo_sync", value=5, ratio=1.20)),
                (fifo_seq1, _comparison_payload(target="tlul_fifo_sync", value=24, ratio=2.64)),
            ):
                path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

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
                            {
                                "name": "checked_in_common_v1",
                                "label": "checked-in common threshold v1",
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
                                "name": "candidate_common_threshold5",
                                "label": "common threshold5",
                                "policy_mode": "common",
                                "paths": [str(socket_v5), str(fifo_v5)],
                                "scoreboard_summary": {
                                    "comparison_ready_count": 2,
                                    "hybrid_win_count": 2,
                                    "threshold_keys": ["toggle_bits_hit:5:bitwise_or_across_trials"],
                                    "weakest_hybrid_win": {"target": "tlul_fifo_sync", "speedup_ratio": 1.20},
                                },
                            },
                            {
                                "name": "candidate_design_specific_minimal_progress",
                                "label": "design-specific",
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
                )
                + "\n",
                encoding="utf-8",
            )
            selection = root / "selection.json"
            selection.write_text(json.dumps({"schema_version": 1, "allow_per_target_thresholds": False, "require_matching_thresholds": True}) + "\n", encoding="utf-8")
            json_out = root / "preview.json"
            argv = [
                "audit_campaign_threshold_policy_preview.py",
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
            self.assertEqual(payload["scope"], "campaign_threshold_policy_preview")
            self.assertFalse(payload["current_selection"]["allow_per_target_thresholds"])
            self.assertTrue(payload["current_selection"]["require_matching_thresholds"])


if __name__ == "__main__":
    unittest.main()
