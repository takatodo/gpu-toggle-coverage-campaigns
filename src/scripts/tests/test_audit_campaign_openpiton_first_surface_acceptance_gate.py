#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_openpiton_first_surface_acceptance_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignOpenPitonFirstSurfaceAcceptanceGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module(
            "audit_campaign_openpiton_first_surface_acceptance_gate_test",
            MODULE_PATH,
        )

    def test_accept_profile_accepts_ready_openpiton_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "accept_selected_openpiton_first_surface_step.json").write_text(
                (
                    '{"name":"accept_selected_openpiton_first_surface_step",'
                    '"accept_selected_openpiton_first_surface_step":true}\n'
                ),
                encoding="utf-8",
            )
            payload = self.module.build_gate(
                xiangshan_status_payload={
                    "outcome": {
                        "status": "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family"
                    }
                },
                openpiton_gate_payload={
                    "selection": {"profile_name": "openpiton_default_gate"},
                    "outcome": {
                        "status": "default_gate_ready",
                        "selected_family": "OpenPiton",
                        "comparison_path": "/tmp/openpiton.json",
                        "speedup_ratio": 1.56,
                        "threshold_value": 8,
                    },
                },
                selection_payload={"profile_name": "accept_selected_openpiton_first_surface_step"},
                selection_path=root / "selection.json",
            )

            self.assertEqual(payload["outcome"]["status"], "accepted_selected_openpiton_first_surface_step")
            self.assertEqual(payload["outcome"]["selected_family"], "OpenPiton")

    def test_hold_profile_reports_hold_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "hold_selected_openpiton_first_surface_step.json").write_text(
                (
                    '{"name":"hold_selected_openpiton_first_surface_step",'
                    '"accept_selected_openpiton_first_surface_step":false}\n'
                ),
                encoding="utf-8",
            )
            payload = self.module.build_gate(
                xiangshan_status_payload={
                    "outcome": {
                        "status": "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family"
                    }
                },
                openpiton_gate_payload={"outcome": {"status": "default_gate_ready"}},
                selection_payload={"profile_name": "hold_selected_openpiton_first_surface_step"},
                selection_path=root / "selection.json",
            )

            self.assertEqual(payload["outcome"]["status"], "hold_selected_openpiton_first_surface_step")

    def test_accept_profile_remains_accepted_after_xiangshan_branch_advances(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "accept_selected_openpiton_first_surface_step.json").write_text(
                (
                    '{"name":"accept_selected_openpiton_first_surface_step",'
                    '"accept_selected_openpiton_first_surface_step":true}\n'
                ),
                encoding="utf-8",
            )
            payload = self.module.build_gate(
                xiangshan_status_payload={
                    "outcome": {
                        "status": "decide_xiangshan_cubin_first_debug_vs_reopen_vortex_tls_lowering_debug"
                    }
                },
                openpiton_gate_payload={
                    "selection": {"profile_name": "openpiton_default_gate"},
                    "outcome": {
                        "status": "default_gate_ready",
                        "selected_family": "OpenPiton",
                        "comparison_path": "/tmp/openpiton.json",
                        "speedup_ratio": 1.56,
                        "threshold_value": 8,
                    },
                },
                selection_payload={"profile_name": "accept_selected_openpiton_first_surface_step"},
                selection_path=root / "selection.json",
            )

            self.assertEqual(payload["outcome"]["status"], "accepted_selected_openpiton_first_surface_step")


if __name__ == "__main__":
    unittest.main()
