#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xuantie_breadth_acceptance_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXuantieBreadthAcceptanceGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xuantie_breadth_acceptance_gate_test", MODULE_PATH)

    def test_accept_profile_promotes_ready_selected_breadth(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "accept_selected_xuantie_breadth.json").write_text(
                '{"name":"accept_selected_xuantie_breadth","accept_selected_breadth":true}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"

            payload = self.module.build_gate(
                real_goal_acceptance_payload={
                    "outcome": {"status": "accepted_checkpoint_and_seed"},
                },
                breadth_gate_payload={
                    "selection": {"profile_name": "e906_candidate_only_threshold2"},
                    "outcome": {
                        "status": "candidate_only_ready",
                        "comparison_path": "/tmp/e906.json",
                        "speedup_ratio": 30.3,
                        "candidate_threshold_value": 2,
                    },
                },
                selection_payload={"profile_name": "accept_selected_xuantie_breadth"},
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "accepted_selected_xuantie_breadth")
            self.assertEqual(payload["outcome"]["candidate_threshold_value"], 2)

    def test_hold_profile_keeps_breadth_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "hold_selected_xuantie_breadth.json").write_text(
                '{"name":"hold_selected_xuantie_breadth","accept_selected_breadth":false}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"

            payload = self.module.build_gate(
                real_goal_acceptance_payload={"outcome": {"status": "accepted_checkpoint_and_seed"}},
                breadth_gate_payload={"outcome": {"status": "candidate_only_ready"}},
                selection_payload={"profile_name": "hold_selected_xuantie_breadth"},
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "hold_selected_xuantie_breadth")


if __name__ == "__main__":
    unittest.main()
