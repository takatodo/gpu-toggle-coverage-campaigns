#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_veer_same_family_next_axes.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignVeerSameFamilyNextAxesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_veer_same_family_next_axes_test", MODULE_PATH)

    def test_reports_el2_after_eh2_is_accepted(self) -> None:
        payload = self.module.build_axes(
            veer_fallback_candidates_payload={
                "decision": {
                    "recommended_first_design": "VeeR-EH1",
                    "fallback_design": "VeeR-EH2",
                },
                "ready_candidates": ["VeeR-EH1", "VeeR-EH2", "VeeR-EL2"],
            },
            veer_same_family_acceptance_payload={
                "outcome": {
                    "status": "accepted_selected_veer_same_family_step",
                    "selected_design": "VeeR-EH2",
                    "selected_veer_same_family_profile_name": "veer_eh2_candidate_only_threshold4",
                }
            },
        )

        self.assertEqual(payload["decision"]["status"], "decide_continue_to_remaining_veer_design")
        self.assertEqual(payload["decision"]["recommended_next_design"], "VeeR-EL2")


if __name__ == "__main__":
    unittest.main()
