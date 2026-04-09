#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_non_opentitan_breadth_axes.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignNonOpentitanBreadthAxesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_non_opentitan_breadth_axes_test", MODULE_PATH)

    def test_reports_xuantie_vs_fallback_decision_after_e906_acceptance(self) -> None:
        payload = self.module.build_axes(
            real_goal_acceptance_payload={
                "outcome": {
                    "status": "accepted_checkpoint_and_seed",
                    "selected_seed_design": "XuanTie-E902",
                }
            },
            xuantie_breadth_acceptance_payload={
                "outcome": {
                    "status": "accepted_selected_xuantie_breadth",
                    "selected_breadth_design": "XuanTie-E906",
                    "selected_breadth_profile_name": "e906_candidate_only_threshold2",
                    "comparison_path": "/tmp/e906.json",
                    "speedup_ratio": 30.3,
                }
            },
            post_checkpoint_axes_payload={
                "decision": {"recommended_family": "XuanTie"},
                "inventory_rows": [
                    {
                        "repo_family": "XuanTie",
                        "design_count": 4,
                        "raw_family_dirs": [
                            "XuanTie-C906",
                            "XuanTie-C910",
                            "XuanTie-E902",
                            "XuanTie-E906",
                        ],
                        "is_active_repo_family": False,
                        "is_opentitan": False,
                    },
                    {
                        "repo_family": "VeeR",
                        "design_count": 3,
                        "raw_family_dirs": ["VeeR-EH1", "VeeR-EH2", "VeeR-EL2"],
                        "is_active_repo_family": False,
                        "is_opentitan": False,
                    },
                ],
            },
        )

        self.assertEqual(
            payload["decision"]["status"],
            "decide_continue_xuantie_breadth_vs_open_fallback_family",
        )
        self.assertEqual(
            payload["recommended_family_axis"]["remaining_same_family_designs"],
            ["XuanTie-C906", "XuanTie-C910"],
        )


if __name__ == "__main__":
    unittest.main()
