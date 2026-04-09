#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_real_goal_acceptance_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignRealGoalAcceptanceGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_real_goal_acceptance_gate_test", MODULE_PATH)

    def test_accept_profile_promotes_ready_checkpoint_and_seed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "accept_checkpoint_and_seed.json").write_text(
                '{"name":"accept_checkpoint_and_seed","accept_checkpoint":true,"accept_selected_seed":true}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            selection_payload = {"profile_name": "accept_checkpoint_and_seed"}

            payload = self.module.build_gate(
                checkpoint_payload={
                    "decision": {"readiness": "cross_family_checkpoint_ready"},
                    "summary": {"active_surface_count": 9},
                },
                seed_payload={
                    "decision": {"status": "ready_to_accept_selected_seed"},
                    "selected_entry": {
                        "design": "XuanTie-E902",
                        "profile_name": "xuantie_single_surface_e902",
                        "comparison_path": "/tmp/e902_cmp.json",
                        "speedup_ratio": 16.7,
                    },
                },
                selection_payload=selection_payload,
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "accepted_checkpoint_and_seed")
            self.assertEqual(payload["outcome"]["selected_seed_design"], "XuanTie-E902")

    def test_checkpoint_only_profile_keeps_seed_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "accept_checkpoint_only.json").write_text(
                '{"name":"accept_checkpoint_only","accept_checkpoint":true,"accept_selected_seed":false}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            selection_payload = {"profile_name": "accept_checkpoint_only"}

            payload = self.module.build_gate(
                checkpoint_payload={"decision": {"readiness": "cross_family_checkpoint_ready"}},
                seed_payload={"decision": {"status": "ready_to_accept_selected_seed"}},
                selection_payload=selection_payload,
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "checkpoint_accepted_seed_pending")
            self.assertEqual(payload["outcome"]["next_action"], "accept_selected_non_opentitan_seed")


if __name__ == "__main__":
    unittest.main()
