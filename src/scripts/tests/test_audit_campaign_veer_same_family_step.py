#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_veer_same_family_step.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignVeerSameFamilyStepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_veer_same_family_step_test", MODULE_PATH)

    def test_reports_candidate_only_decision_for_eh2(self) -> None:
        payload = self.module.build_status(
            veer_next_axes_payload={
                "accepted_veer_first_surface_step": {
                    "status": "accepted_selected_veer_first_surface_step",
                },
                "decision": {
                    "status": "decide_continue_to_remaining_veer_design",
                    "recommended_next_design": "VeeR-EH2",
                },
                "next_same_family_axis": {
                    "current_first_design": "VeeR-EH1",
                    "remaining_veer_designs": ["VeeR-EH2", "VeeR-EL2"],
                },
            },
            default_comparison_payload={
                "status": "ok",
                "comparison_ready": False,
                "winner": "unresolved",
                "campaign_threshold": {"value": 8},
            },
            threshold4_comparison_payload={
                "status": "ok",
                "comparison_ready": True,
                "winner": "hybrid",
                "speedup_ratio": 2.97,
                "campaign_threshold": {"value": 4},
            },
        )

        self.assertEqual(payload["scope"], "campaign_veer_same_family_step")
        self.assertEqual(
            payload["outcome"]["status"],
            "decide_veer_eh2_candidate_only_vs_new_default_gate",
        )
        self.assertEqual(payload["outcome"]["selected_design"], "VeeR-EH2")
        self.assertEqual(payload["outcome"]["candidate_threshold_value"], 4)
        self.assertEqual(payload["context"]["fallback_design"], "VeeR-EL2")


if __name__ == "__main__":
    unittest.main()
