#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xuantie_same_family_acceptance_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXuantieSameFamilyAcceptanceGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xuantie_same_family_acceptance_gate_test", MODULE_PATH)

    def test_accept_profile_accepts_ready_same_family_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "accept_selected_same_family_step.json").write_text(
                '{"name":"accept_selected_same_family_step","accept_selected_same_family_step":true}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            payload = self.module.build_gate(
                branch_gate_payload={"outcome": {"status": "continue_same_family_ready"}},
                same_family_gate_payload={
                    "selection": {"profile_name": "c906_candidate_only_threshold5"},
                    "outcome": {
                        "status": "candidate_only_ready",
                        "selected_design": "XuanTie-C906",
                        "candidate_threshold_value": 5,
                        "comparison_path": "/tmp/c906.json",
                        "speedup_ratio": 9.59,
                    },
                },
                selection_payload={"profile_name": "accept_selected_same_family_step"},
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "accepted_selected_same_family_step")
            self.assertEqual(payload["outcome"]["selected_design"], "XuanTie-C906")

    def test_hold_profile_reports_hold_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "hold_selected_same_family_step.json").write_text(
                '{"name":"hold_selected_same_family_step","accept_selected_same_family_step":false}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            payload = self.module.build_gate(
                branch_gate_payload={"outcome": {"status": "continue_same_family_ready"}},
                same_family_gate_payload={"outcome": {"status": "candidate_only_ready"}},
                selection_payload={"profile_name": "hold_selected_same_family_step"},
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "hold_selected_same_family_step")


if __name__ == "__main__":
    unittest.main()
