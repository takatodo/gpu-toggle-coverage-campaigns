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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_policy_decision_readiness.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _variant(
    *,
    allow_per_target: bool,
    require_matching: bool,
    selected_scenario_name: str,
    selected_policy_mode: str,
    thresholds: list[dict],
    all_thresholds_match: bool,
    ratio: float,
    next_kpi: str,
    reason: str,
) -> dict:
    return {
        "allow_per_target_thresholds": allow_per_target,
        "require_matching_thresholds": require_matching,
        "gate": {
            "outcome": {
                "selected_scenario_name": selected_scenario_name,
                "selected_policy_mode": selected_policy_mode,
                "selected_thresholds": thresholds,
            }
        },
        "active_scoreboard": {
            "summary": {
                "comparison_ready_count": 2,
                "hybrid_win_count": 2,
                "all_thresholds_match": all_thresholds_match,
                "weakest_hybrid_win": {
                    "target": "tlul_fifo_sync",
                    "speedup_ratio": ratio,
                },
            }
        },
        "active_next_kpi": {
            "decision": {
                "recommended_next_kpi": next_kpi,
                "reason": reason,
                "recommended_next_tasks": ["stub task"],
            }
        },
    }


class AuditCampaignPolicyDecisionReadinessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_policy_decision_readiness_test", MODULE_PATH)

    def test_build_readiness_identifies_decisive_threshold_mismatch_question(self) -> None:
        preview = {
            "variants": {
                "current_selection": _variant(
                    allow_per_target=False,
                    require_matching=True,
                    selected_scenario_name="checked_in_common_v1",
                    selected_policy_mode="common",
                    thresholds=[{"kind": "toggle_bits_hit", "value": 3, "aggregation": "bitwise_or_across_trials"}],
                    all_thresholds_match=True,
                    ratio=1.16,
                    next_kpi="stronger_thresholds",
                    reason="weakest_hybrid_win_below_margin",
                ),
                "flip_allow_per_target": _variant(
                    allow_per_target=True,
                    require_matching=True,
                    selected_scenario_name="candidate_design_specific_minimal_progress",
                    selected_policy_mode="per_target",
                    thresholds=[
                        {"kind": "toggle_bits_hit", "value": 5, "aggregation": "bitwise_or_across_trials"},
                        {"kind": "toggle_bits_hit", "value": 24, "aggregation": "bitwise_or_across_trials"},
                    ],
                    all_thresholds_match=False,
                    ratio=2.64,
                    next_kpi="stabilize_existing_surfaces",
                    reason="threshold_schema_mismatch",
                ),
                "flip_both": _variant(
                    allow_per_target=True,
                    require_matching=False,
                    selected_scenario_name="candidate_design_specific_minimal_progress",
                    selected_policy_mode="per_target",
                    thresholds=[
                        {"kind": "toggle_bits_hit", "value": 5, "aggregation": "bitwise_or_across_trials"},
                        {"kind": "toggle_bits_hit", "value": 24, "aggregation": "bitwise_or_across_trials"},
                    ],
                    all_thresholds_match=False,
                    ratio=2.64,
                    next_kpi="broader_design_count",
                    reason="enough_ready_surfaces_and_margin",
                ),
            }
        }

        payload = self.module.build_readiness(
            preview_payload=preview,
            preview_path=Path("/tmp/preview.json"),
        )

        self.assertEqual(payload["scope"], "campaign_policy_decision_readiness")
        self.assertEqual(
            payload["summary"]["decisive_policy_question"],
            "decide_if_campaign_v2_allows_threshold_schema_mismatch",
        )
        self.assertTrue(payload["summary"]["flip_allow_blocked_by_threshold_schema_mismatch"])
        self.assertTrue(payload["summary"]["flip_both_ready_for_checkin"])
        self.assertEqual(payload["summary"]["recommended_active_task"], "decide_policy_before_defining_new_v2_threshold")

    def test_build_readiness_switches_to_next_surface_task_when_current_policy_is_ready(self) -> None:
        preview = {
            "variants": {
                "current_selection": _variant(
                    allow_per_target=True,
                    require_matching=False,
                    selected_scenario_name="candidate_design_specific_minimal_progress",
                    selected_policy_mode="per_target",
                    thresholds=[
                        {"kind": "toggle_bits_hit", "value": 5, "aggregation": "bitwise_or_across_trials"},
                        {"kind": "toggle_bits_hit", "value": 24, "aggregation": "bitwise_or_across_trials"},
                    ],
                    all_thresholds_match=False,
                    ratio=2.64,
                    next_kpi="broader_design_count",
                    reason="current_surfaces_have_strong_hybrid_margin",
                ),
                "flip_allow_per_target": _variant(
                    allow_per_target=False,
                    require_matching=False,
                    selected_scenario_name="checked_in_common_v1",
                    selected_policy_mode="common",
                    thresholds=[{"kind": "toggle_bits_hit", "value": 3, "aggregation": "bitwise_or_across_trials"}],
                    all_thresholds_match=True,
                    ratio=1.16,
                    next_kpi="stronger_thresholds",
                    reason="weakest_hybrid_win_below_margin",
                ),
                "flip_both": _variant(
                    allow_per_target=False,
                    require_matching=True,
                    selected_scenario_name="checked_in_common_v1",
                    selected_policy_mode="common",
                    thresholds=[{"kind": "toggle_bits_hit", "value": 3, "aggregation": "bitwise_or_across_trials"}],
                    all_thresholds_match=True,
                    ratio=1.16,
                    next_kpi="stronger_thresholds",
                    reason="weakest_hybrid_win_below_margin",
                ),
            }
        }

        payload = self.module.build_readiness(
            preview_payload=preview,
            preview_path=Path("/tmp/preview.json"),
        )

        self.assertEqual(payload["summary"]["decisive_policy_question"], "policy_already_checked_in")
        self.assertEqual(payload["summary"]["recommended_active_task"], "add_next_comparison_surface")
        self.assertEqual(payload["recommended_next_tasks"][1], "Choose and add the next comparison surface under the active policy.")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            preview_path = root / "preview.json"
            preview_path.write_text(
                json.dumps(
                    {
                        "variants": {
                            "current_selection": _variant(
                                allow_per_target=False,
                                require_matching=True,
                                selected_scenario_name="checked_in_common_v1",
                                selected_policy_mode="common",
                                thresholds=[
                                    {
                                        "kind": "toggle_bits_hit",
                                        "value": 3,
                                        "aggregation": "bitwise_or_across_trials",
                                    }
                                ],
                                all_thresholds_match=True,
                                ratio=1.16,
                                next_kpi="stronger_thresholds",
                                reason="weakest_hybrid_win_below_margin",
                            ),
                            "flip_allow_per_target": _variant(
                                allow_per_target=True,
                                require_matching=True,
                                selected_scenario_name="candidate_design_specific_minimal_progress",
                                selected_policy_mode="per_target",
                                thresholds=[
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
                                all_thresholds_match=False,
                                ratio=2.64,
                                next_kpi="stabilize_existing_surfaces",
                                reason="threshold_schema_mismatch",
                            ),
                            "flip_both": _variant(
                                allow_per_target=True,
                                require_matching=False,
                                selected_scenario_name="candidate_design_specific_minimal_progress",
                                selected_policy_mode="per_target",
                                thresholds=[
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
                                all_thresholds_match=False,
                                ratio=2.64,
                                next_kpi="broader_design_count",
                                reason="enough_ready_surfaces_and_margin",
                            ),
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            json_out = root / "readiness.json"

            argv = [
                "audit_campaign_policy_decision_readiness.py",
                "--preview-json",
                str(preview_path),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_policy_decision_readiness")
            self.assertEqual(payload["summary"]["current_line"], "checked_in_common_v1")


if __name__ == "__main__":
    unittest.main()
