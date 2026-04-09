#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_vortex_first_surface_policy_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignVortexFirstSurfacePolicyGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_vortex_first_surface_policy_gate_test", MODULE_PATH)

    def test_candidate_only_profile_is_ready_when_threshold4_win_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "vortex_candidate_only_threshold4.json").write_text(
                (
                    '{"name":"vortex_candidate_only_threshold4","step_mode":"candidate_only_threshold",'
                    '"design":"Vortex","candidate_threshold_value":4}\n'
                ),
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            payload = self.module.build_gate(
                step_payload={
                    "selected_design": {
                        "design": "Vortex",
                        "threshold4_candidate": {"threshold_value": 4},
                    },
                    "outcome": {
                        "status": "decide_vortex_candidate_only_vs_new_default_gate",
                        "selected_design": "Vortex",
                        "candidate_comparison_path": "/tmp/vortex_threshold4.json",
                        "speedup_ratio": 1.07,
                        "candidate_threshold_value": 4,
                    },
                },
                selection_payload={"profile_name": "vortex_candidate_only_threshold4"},
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "candidate_only_ready")
            self.assertEqual(payload["outcome"]["candidate_threshold_value"], 4)

    def test_default_gate_hold_reports_hold_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "vortex_default_gate_hold.json").write_text(
                '{"name":"vortex_default_gate_hold","step_mode":"default_gate_hold","design":"Vortex"}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            payload = self.module.build_gate(
                step_payload={
                    "selected_design": {
                        "design": "Vortex",
                        "default_comparison": {"path": "/tmp/default.json"},
                    },
                    "outcome": {
                        "status": "decide_vortex_candidate_only_vs_new_default_gate",
                        "selected_design": "Vortex",
                    },
                },
                selection_payload={"profile_name": "vortex_default_gate_hold"},
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "default_gate_hold")


if __name__ == "__main__":
    unittest.main()
