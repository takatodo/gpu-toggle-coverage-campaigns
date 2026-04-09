#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_vortex_first_surface_acceptance_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignVortexFirstSurfaceAcceptanceGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module(
            "audit_campaign_vortex_first_surface_acceptance_gate_test",
            MODULE_PATH,
        )

    def test_accept_profile_accepts_ready_vortex_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "accept_selected_vortex_first_surface_step.json").write_text(
                (
                    '{"name":"accept_selected_vortex_first_surface_step",'
                    '"accept_selected_vortex_first_surface_step":true}\n'
                ),
                encoding="utf-8",
            )
            payload = self.module.build_gate(
                vortex_branch_gate_payload={
                    "selection": {"profile_name": "debug_vortex_tls_lowering"},
                    "outcome": {"status": "vortex_gpu_build_recovered_ready_to_finish_trio"},
                },
                vortex_policy_gate_payload={
                    "selection": {"profile_name": "vortex_candidate_only_threshold4"},
                    "outcome": {
                        "status": "candidate_only_ready",
                        "selected_design": "Vortex",
                        "comparison_path": "/tmp/vortex_threshold4.json",
                        "speedup_ratio": 1.07,
                        "candidate_threshold_value": 4,
                    },
                },
                selection_payload={"profile_name": "accept_selected_vortex_first_surface_step"},
                selection_path=root / "selection.json",
            )

            self.assertEqual(payload["outcome"]["status"], "accepted_selected_vortex_first_surface_step")
            self.assertEqual(payload["outcome"]["selected_design"], "Vortex")

    def test_hold_profile_reports_hold_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "hold_selected_vortex_first_surface_step.json").write_text(
                (
                    '{"name":"hold_selected_vortex_first_surface_step",'
                    '"accept_selected_vortex_first_surface_step":false}\n'
                ),
                encoding="utf-8",
            )
            payload = self.module.build_gate(
                vortex_branch_gate_payload={"outcome": {"status": "vortex_gpu_build_recovered_ready_to_finish_trio"}},
                vortex_policy_gate_payload={"outcome": {"status": "candidate_only_ready"}},
                selection_payload={"profile_name": "hold_selected_vortex_first_surface_step"},
                selection_path=root / "selection.json",
            )

            self.assertEqual(payload["outcome"]["status"], "hold_selected_vortex_first_surface_step")


if __name__ == "__main__":
    unittest.main()
