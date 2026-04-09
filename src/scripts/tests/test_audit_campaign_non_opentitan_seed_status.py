#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_non_opentitan_seed_status.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignNonOpentitanSeedStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_non_opentitan_seed_status_test", MODULE_PATH)

    def test_reports_ready_to_accept_selected_seed(self) -> None:
        payload = self.module.build_seed_status(
            checkpoint_payload={
                "decision": {"readiness": "cross_family_checkpoint_ready", "reason": "ok"},
                "summary": {
                    "active_surface_count": 9,
                    "weakest_hybrid_win": {"target": "tlul_fifo_sync", "speedup_ratio": 2.63},
                },
            },
            post_checkpoint_payload={
                "decision": {
                    "recommended_next_axis": "broaden_non_opentitan_family",
                    "recommended_family": "XuanTie",
                },
                "current_active_line": {"repo_family_count": 1, "repo_families": ["OpenTitan"]},
            },
            entry_gate_payload={
                "selection": {
                    "profile_name": "xuantie_single_surface_e902",
                    "profile_path": "/tmp/profile.json",
                },
                "outcome": {
                    "status": "single_surface_trio_ready",
                    "design": "XuanTie-E902",
                    "fallback_design": "XuanTie-E906",
                    "comparison_path": "/tmp/comparison.json",
                    "speedup_ratio": 16.79,
                },
            },
        )

        self.assertEqual(payload["decision"]["status"], "ready_to_accept_selected_seed")
        self.assertEqual(payload["decision"]["recommended_next_task"], "accept_selected_non_opentitan_seed")
        self.assertEqual(payload["selected_entry"]["design"], "XuanTie-E902")

    def test_reports_blocked_when_checkpoint_is_not_ready(self) -> None:
        payload = self.module.build_seed_status(
            checkpoint_payload={"decision": {"readiness": "not_ready", "reason": "weak margin"}, "summary": {}},
            post_checkpoint_payload={
                "decision": {"recommended_next_axis": "broaden_non_opentitan_family"},
                "current_active_line": {"repo_family_count": 1, "repo_families": ["OpenTitan"]},
            },
            entry_gate_payload={
                "selection": {"profile_name": "xuantie_single_surface_e902"},
                "outcome": {"status": "single_surface_trio_ready"},
            },
        )

        self.assertEqual(payload["decision"]["status"], "blocked_checkpoint_not_ready")
        self.assertEqual(payload["decision"]["recommended_next_task"], "stabilize_current_checkpoint")


if __name__ == "__main__":
    unittest.main()
