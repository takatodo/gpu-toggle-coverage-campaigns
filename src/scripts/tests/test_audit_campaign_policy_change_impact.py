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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_policy_change_impact.py"


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
    scenario: str,
    mode: str,
    status: str,
    thresholds: list[dict],
    paths: list[str],
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
                "selected_scenario_name": scenario,
                "selected_policy_mode": mode,
                "status": status,
                "selected_thresholds": thresholds,
                "selected_paths": paths,
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
            }
        },
    }


class AuditCampaignPolicyChangeImpactTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_policy_change_impact_test", MODULE_PATH)

    def test_build_impact_summarizes_current_to_flip_both(self) -> None:
        preview = {
            "variants": {
                "current_selection": _variant(
                    allow_per_target=False,
                    require_matching=True,
                    scenario="checked_in_common_v1",
                    mode="common",
                    status="hold_current_v1",
                    thresholds=[{"kind": "toggle_bits_hit", "value": 3, "aggregation": "bitwise_or_across_trials"}],
                    paths=["/tmp/socket_v1.json", "/tmp/fifo_v1.json"],
                    all_thresholds_match=True,
                    ratio=1.16,
                    next_kpi="stronger_thresholds",
                    reason="weakest_hybrid_win_below_margin",
                ),
                "flip_both": _variant(
                    allow_per_target=True,
                    require_matching=False,
                    scenario="candidate_design_specific_minimal_progress",
                    mode="per_target",
                    status="promote_design_specific_v2",
                    thresholds=[
                        {"kind": "toggle_bits_hit", "value": 5, "aggregation": "bitwise_or_across_trials"},
                        {"kind": "toggle_bits_hit", "value": 24, "aggregation": "bitwise_or_across_trials"},
                    ],
                    paths=["/tmp/socket_v5.json", "/tmp/fifo_seq1.json"],
                    all_thresholds_match=False,
                    ratio=2.64,
                    next_kpi="broader_design_count",
                    reason="current_surfaces_have_strong_hybrid_margin",
                ),
            }
        }

        payload = self.module.build_impact(
            preview_payload=preview,
            preview_path=Path("/tmp/preview.json"),
            from_variant="current_selection",
            to_variant="flip_both",
        )

        self.assertEqual(payload["scope"], "campaign_policy_change_impact")
        self.assertTrue(payload["delta"]["selected_scenario_changed"])
        self.assertTrue(payload["delta"]["recommended_next_kpi_changed"])
        self.assertEqual(payload["policy_changes"]["allow_per_target_thresholds"]["from"], False)
        self.assertEqual(payload["policy_changes"]["allow_per_target_thresholds"]["to"], True)
        self.assertEqual(payload["impact_assessment"]["decision_type"], "policy_switch_enables_broader_design_count")

    def test_build_impact_detects_policy_reversion(self) -> None:
        preview = {
            "variants": {
                "current_selection": _variant(
                    allow_per_target=True,
                    require_matching=False,
                    scenario="candidate_design_specific_minimal_progress",
                    mode="per_target",
                    status="promote_design_specific_v2",
                    thresholds=[
                        {"kind": "toggle_bits_hit", "value": 5, "aggregation": "bitwise_or_across_trials"},
                        {"kind": "toggle_bits_hit", "value": 24, "aggregation": "bitwise_or_across_trials"},
                    ],
                    paths=["/tmp/socket_v5.json", "/tmp/fifo_seq1.json"],
                    all_thresholds_match=False,
                    ratio=2.64,
                    next_kpi="broader_design_count",
                    reason="current_surfaces_have_strong_hybrid_margin",
                ),
                "flip_both": _variant(
                    allow_per_target=False,
                    require_matching=True,
                    scenario="checked_in_common_v1",
                    mode="common",
                    status="hold_current_v1",
                    thresholds=[{"kind": "toggle_bits_hit", "value": 3, "aggregation": "bitwise_or_across_trials"}],
                    paths=["/tmp/socket_v1.json", "/tmp/fifo_v1.json"],
                    all_thresholds_match=True,
                    ratio=1.16,
                    next_kpi="stronger_thresholds",
                    reason="weakest_hybrid_win_below_margin",
                ),
            }
        }

        payload = self.module.build_impact(
            preview_payload=preview,
            preview_path=Path("/tmp/preview.json"),
            from_variant="current_selection",
            to_variant="flip_both",
        )

        self.assertEqual(payload["impact_assessment"]["decision_type"], "policy_reversion_reduces_design_count")

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
                                scenario="checked_in_common_v1",
                                mode="common",
                                status="hold_current_v1",
                                thresholds=[
                                    {
                                        "kind": "toggle_bits_hit",
                                        "value": 3,
                                        "aggregation": "bitwise_or_across_trials",
                                    }
                                ],
                                paths=["/tmp/socket_v1.json", "/tmp/fifo_v1.json"],
                                all_thresholds_match=True,
                                ratio=1.16,
                                next_kpi="stronger_thresholds",
                                reason="weakest_hybrid_win_below_margin",
                            ),
                            "flip_both": _variant(
                                allow_per_target=True,
                                require_matching=False,
                                scenario="candidate_design_specific_minimal_progress",
                                mode="per_target",
                                status="promote_design_specific_v2",
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
                                paths=["/tmp/socket_v5.json", "/tmp/fifo_seq1.json"],
                                all_thresholds_match=False,
                                ratio=2.64,
                                next_kpi="broader_design_count",
                                reason="current_surfaces_have_strong_hybrid_margin",
                            ),
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            json_out = root / "impact.json"
            argv = [
                "audit_campaign_policy_change_impact.py",
                "--preview-json",
                str(preview_path),
                "--from-variant",
                "current_selection",
                "--to-variant",
                "flip_both",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_policy_change_impact")
            self.assertEqual(payload["from_variant"], "current_selection")
            self.assertEqual(payload["to_variant"], "flip_both")


if __name__ == "__main__":
    unittest.main()
