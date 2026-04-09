#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xuantie_same_family_next_axes.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXuantieSameFamilyNextAxesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xuantie_same_family_next_axes_test", MODULE_PATH)

    def test_reports_c910_vs_veer_after_c906_is_accepted(self) -> None:
        payload = self.module.build_axes(
            branch_candidates_payload={
                "decision": {"fallback_profile_name": "open_veer_fallback_family"},
                "branch_candidates": [
                    {
                        "profile_name": "xuantie_continue_same_family",
                        "candidate_designs": ["XuanTie-C906", "XuanTie-C910"],
                    }
                ],
            },
            same_family_acceptance_payload={
                "outcome": {
                    "status": "accepted_selected_same_family_step",
                    "selected_design": "XuanTie-C906",
                    "selected_same_family_profile_name": "c906_candidate_only_threshold5",
                }
            },
        )

        self.assertEqual(
            payload["decision"]["status"],
            "decide_continue_to_remaining_same_family_design_vs_open_fallback_family",
        )
        self.assertEqual(payload["decision"]["recommended_same_family_design"], "XuanTie-C910")


if __name__ == "__main__":
    unittest.main()
