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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xuantie_same_family_step.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXuantieSameFamilyStepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xuantie_same_family_step_test", MODULE_PATH)

    def test_blocks_when_same_family_branch_is_not_active(self) -> None:
        payload = self.module.build_status(
            branch_gate_payload={
                "selection": {"profile_name": "hold_post_e906_branch"},
                "context": {
                    "selected_seed_design": "XuanTie-E902",
                    "selected_breadth_design": "XuanTie-E906",
                },
                "outcome": {
                    "status": "hold_post_e906_branch",
                    "next_action": "choose_post_e906_branch",
                },
            },
            branch_candidates_payload={"decision": {}},
        )

        self.assertEqual(payload["outcome"]["status"], "blocked_same_family_branch_not_active")

    def test_reports_candidate_only_vs_default_gate_for_c906(self) -> None:
        payload = self.module.build_status(
            branch_gate_payload={
                "selection": {"profile_name": "xuantie_continue_same_family"},
                "context": {
                    "selected_seed_design": "XuanTie-E902",
                    "selected_breadth_design": "XuanTie-E906",
                },
                "outcome": {"status": "continue_same_family_ready"},
            },
            branch_candidates_payload={
                "decision": {
                    "recommended_profile_name": "xuantie_continue_same_family",
                    "recommended_first_design": "XuanTie-C906",
                },
                "branch_candidates": [
                    {
                        "profile_name": "xuantie_continue_same_family",
                        "design_rows": [
                            {
                                "design": "XuanTie-C906",
                                "validated_line_kind": "candidate_only_hybrid_win",
                                "default_comparison_path": "/tmp/default.json",
                                "default_comparison_ready": False,
                                "default_winner": "unresolved",
                                "best_ready_comparison_path": "/tmp/threshold5.json",
                                "best_ready_threshold_value": 5,
                                "best_ready_speedup_ratio": 9.59,
                            }
                        ],
                    }
                ],
            },
        )

        self.assertEqual(
            payload["outcome"]["status"],
            "decide_selected_same_family_design_candidate_only_vs_new_default_gate",
        )
        self.assertEqual(payload["outcome"]["selected_design"], "XuanTie-C906")
        self.assertEqual(payload["outcome"]["candidate_threshold_value"], 5)

    def test_reports_ready_to_accept_when_default_gate_is_ready(self) -> None:
        payload = self.module.build_status(
            branch_gate_payload={
                "selection": {"profile_name": "xuantie_continue_same_family"},
                "context": {
                    "selected_seed_design": "XuanTie-E902",
                    "selected_breadth_design": "XuanTie-E906",
                },
                "outcome": {"status": "continue_same_family_ready"},
            },
            branch_candidates_payload={
                "decision": {
                    "recommended_profile_name": "xuantie_continue_same_family",
                    "recommended_first_design": "XuanTie-C906",
                },
                "branch_candidates": [
                    {
                        "profile_name": "xuantie_continue_same_family",
                        "design_rows": [
                            {
                                "design": "XuanTie-C906",
                                "validated_line_kind": "default_gate_hybrid_win",
                                "best_ready_comparison_path": "/tmp/default.json",
                                "best_ready_speedup_ratio": 4.2,
                            }
                        ],
                    }
                ],
            },
        )

        self.assertEqual(payload["outcome"]["status"], "ready_to_accept_selected_same_family_design")
        self.assertEqual(payload["outcome"]["selected_design"], "XuanTie-C906")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gate_json = root / "gate.json"
            candidates_json = root / "candidates.json"
            json_out = root / "status.json"

            gate_json.write_text(
                json.dumps(
                    {
                        "selection": {"profile_name": "xuantie_continue_same_family"},
                        "context": {
                            "selected_seed_design": "XuanTie-E902",
                            "selected_breadth_design": "XuanTie-E906",
                        },
                        "outcome": {"status": "continue_same_family_ready"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            candidates_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "recommended_profile_name": "xuantie_continue_same_family",
                            "recommended_first_design": "XuanTie-C906",
                        },
                        "branch_candidates": [
                            {
                                "profile_name": "xuantie_continue_same_family",
                                "design_rows": [
                                    {
                                        "design": "XuanTie-C906",
                                        "validated_line_kind": "candidate_only_hybrid_win",
                                        "default_comparison_path": "/tmp/default.json",
                                        "default_comparison_ready": False,
                                        "default_winner": "unresolved",
                                        "best_ready_comparison_path": "/tmp/threshold5.json",
                                        "best_ready_threshold_value": 5,
                                        "best_ready_speedup_ratio": 9.59,
                                    }
                                ],
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_xuantie_same_family_step.py",
                "--breadth-gate-json",
                str(gate_json),
                "--branch-candidates-json",
                str(candidates_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_xuantie_same_family_step")
            self.assertEqual(
                payload["outcome"]["status"],
                "decide_selected_same_family_design_candidate_only_vs_new_default_gate",
            )


if __name__ == "__main__":
    unittest.main()
