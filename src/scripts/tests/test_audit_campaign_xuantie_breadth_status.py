#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xuantie_breadth_status.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXuantieBreadthStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xuantie_breadth_status_test", MODULE_PATH)

    def test_reports_candidate_only_vs_new_default_gate_when_e906_plateaus(self) -> None:
        payload = self.module.build_xuantie_breadth_status(
            acceptance_gate_payload={
                "outcome": {
                    "status": "accepted_checkpoint_and_seed",
                    "selected_seed_design": "XuanTie-E902",
                    "selected_seed_profile_name": "xuantie_single_surface_e902",
                    "selected_seed_speedup_ratio": 16.7,
                }
            },
            entry_readiness_payload={
                "decision": {
                    "readiness": "legacy_family_pilot_failed_but_single_surface_override_ready",
                }
            },
            override_candidates_payload={
                "decision": {
                    "recommended_design": "XuanTie-E902",
                    "fallback_design": "XuanTie-E906",
                }
            },
            e906_case_variants_payload={
                "decision": {
                    "status": "default_gate_blocked_across_known_case_pats",
                    "reason": "plateau",
                    "recommended_next_task": "treat_xuantie_e906_as_candidate_only_or_define_a_new_default_gate",
                },
                "summary": {
                    "case_count": 3,
                    "max_stock_hybrid_bits_hit": 2,
                    "default_threshold_values": [8],
                },
                "threshold2_candidate": {
                    "comparison_ready": True,
                    "winner": "hybrid",
                    "speedup_ratio": 30.3,
                    "comparison_path": "/tmp/e906_threshold2.json",
                },
            },
            e906_threshold_options_payload={
                "decision": {
                    "status": "threshold2_is_strongest_ready_numeric_gate",
                    "recommended_next_task": "choose_between_promoting_threshold2_and_defining_a_non_cutoff_default_gate",
                },
                "strongest_ready_numeric_gate": {"threshold_value": 2},
                "blocked_numeric_thresholds": [3, 4, 5, 6, 7, 8],
            },
        )

        self.assertEqual(payload["decision"]["status"], "decide_threshold2_promotion_vs_non_cutoff_default_gate")
        self.assertEqual(
            payload["decision"]["recommended_next_task"],
            "choose_between_promoting_threshold2_and_defining_a_non_cutoff_default_gate",
        )


if __name__ == "__main__":
    unittest.main()
