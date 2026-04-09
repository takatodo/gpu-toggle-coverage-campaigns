#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xiangshan_first_surface_acceptance_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXiangshanFirstSurfaceAcceptanceGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module(
            "audit_campaign_xiangshan_first_surface_acceptance_gate_test",
            MODULE_PATH,
        )

    def test_accept_profile_accepts_ready_xiangshan_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "accept_selected_xiangshan_first_surface_step.json").write_text(
                (
                    '{"name":"accept_selected_xiangshan_first_surface_step",'
                    '"accept_selected_xiangshan_first_surface_step":true}\n'
                ),
                encoding="utf-8",
            )
            payload = self.module.build_gate(
                vortex_gate_payload={
                    "selection": {"profile_name": "reopen_xiangshan_fallback_family"},
                    "outcome": {"status": "reopen_xiangshan_fallback_ready"},
                },
                xiangshan_gate_payload={
                    "selection": {"profile_name": "xiangshan_candidate_only_threshold2"},
                    "outcome": {
                        "status": "candidate_only_ready",
                        "selected_design": "XiangShan",
                        "comparison_path": "/tmp/xiangshan_threshold2.json",
                        "speedup_ratio": 3.13,
                        "candidate_threshold_value": 2,
                    },
                },
                selection_payload={"profile_name": "accept_selected_xiangshan_first_surface_step"},
                selection_path=root / "selection.json",
            )

            self.assertEqual(payload["outcome"]["status"], "accepted_selected_xiangshan_first_surface_step")
            self.assertEqual(payload["outcome"]["selected_design"], "XiangShan")

    def test_hold_profile_reports_hold_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "hold_selected_xiangshan_first_surface_step.json").write_text(
                (
                    '{"name":"hold_selected_xiangshan_first_surface_step",'
                    '"accept_selected_xiangshan_first_surface_step":false}\n'
                ),
                encoding="utf-8",
            )
            payload = self.module.build_gate(
                vortex_gate_payload={"outcome": {"status": "reopen_xiangshan_fallback_ready"}},
                xiangshan_gate_payload={"outcome": {"status": "candidate_only_ready"}},
                selection_payload={"profile_name": "hold_selected_xiangshan_first_surface_step"},
                selection_path=root / "selection.json",
            )

            self.assertEqual(payload["outcome"]["status"], "hold_selected_xiangshan_first_surface_step")


if __name__ == "__main__":
    unittest.main()
