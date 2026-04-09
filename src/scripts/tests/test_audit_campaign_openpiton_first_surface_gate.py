#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_openpiton_first_surface_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignOpenPitonFirstSurfaceGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_openpiton_first_surface_gate_test", MODULE_PATH)

    def test_default_gate_profile_is_ready_when_step_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "openpiton_default_gate.json").write_text(
                (
                    '{"name":"openpiton_default_gate","step_mode":"default_gate",'
                    '"family":"OpenPiton","threshold_value":8}\n'
                ),
                encoding="utf-8",
            )
            payload = self.module.build_gate(
                step_payload={
                    "selected_family": {
                        "family": "OpenPiton",
                        "default_comparison": {"path": "/tmp/openpiton.json", "speedup_ratio": 1.56},
                    },
                    "outcome": {
                        "status": "ready_to_accept_openpiton_default_gate",
                        "comparison_path": "/tmp/openpiton.json",
                        "speedup_ratio": 1.56,
                    },
                },
                selection_payload={"profile_name": "openpiton_default_gate"},
                selection_path=root / "selection.json",
            )

            self.assertEqual(payload["outcome"]["status"], "default_gate_ready")
            self.assertEqual(payload["outcome"]["threshold_value"], 8)

    def test_hold_profile_reports_hold_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "openpiton_default_gate_hold.json").write_text(
                '{"name":"openpiton_default_gate_hold","step_mode":"default_gate_hold","family":"OpenPiton"}\n',
                encoding="utf-8",
            )
            payload = self.module.build_gate(
                step_payload={
                    "selected_family": {"family": "OpenPiton"},
                    "outcome": {"status": "ready_to_accept_openpiton_default_gate"},
                },
                selection_payload={"profile_name": "openpiton_default_gate_hold"},
                selection_path=root / "selection.json",
            )

            self.assertEqual(payload["outcome"]["status"], "default_gate_hold")


if __name__ == "__main__":
    unittest.main()
