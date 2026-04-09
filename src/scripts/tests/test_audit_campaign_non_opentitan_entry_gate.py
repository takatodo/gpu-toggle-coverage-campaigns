#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_non_opentitan_entry_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignNonOpentitanEntryGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_non_opentitan_entry_gate_test", MODULE_PATH)

    def test_reports_blocked_family_pilot_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles = root / "profiles"
            profiles.mkdir()
            (profiles / "xuantie_family_pilot_hold.json").write_text(
                '{"name":"xuantie_family_pilot_hold","family":"XuanTie","entry_mode":"family_pilot"}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            selection_path.write_text('{"profile_name":"xuantie_family_pilot_hold"}\n', encoding="utf-8")

            payload = self.module.build_gate(
                entry_payload={"decision": {"recommended_family": "XuanTie", "recommended_entry_mode": "family_pilot"}},
                readiness_payload={"decision": {"readiness": "legacy_family_pilot_failed", "reason": "missing bench"}},
                override_payload={"decision": {"recommended_design": "XuanTie-E902"}},
                selection_payload={"profile_name": "xuantie_family_pilot_hold"},
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "family_pilot_blocked")

    def test_reports_ready_single_surface_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles = root / "profiles"
            profiles.mkdir()
            (profiles / "xuantie_single_surface_e902.json").write_text(
                (
                    '{"name":"xuantie_single_surface_e902","family":"XuanTie","entry_mode":"single_surface",'
                    '"design":"XuanTie-E902","fallback_design":"XuanTie-E906"}\n'
                ),
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            selection_path.write_text('{"profile_name":"xuantie_single_surface_e902"}\n', encoding="utf-8")

            payload = self.module.build_gate(
                entry_payload={"decision": {"recommended_family": "XuanTie", "recommended_entry_mode": "family_pilot"}},
                readiness_payload={"decision": {"readiness": "legacy_family_pilot_failed_but_single_surface_override_ready"}},
                override_payload={
                    "decision": {"recommended_design": "XuanTie-E902", "fallback_design": "XuanTie-E906"},
                    "ranked_candidates": [
                        {"design": "XuanTie-E902", "ready": True, "path": "/tmp/e902.json"},
                        {"design": "XuanTie-E906", "ready": True, "path": "/tmp/e906.json"},
                    ],
                },
                selection_payload={"profile_name": "xuantie_single_surface_e902"},
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "single_surface_ready")
            self.assertEqual(payload["outcome"]["design"], "XuanTie-E902")

    def test_reports_trio_ready_single_surface_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles = root / "profiles"
            profiles.mkdir()
            (profiles / "xuantie_single_surface_e902.json").write_text(
                (
                    '{"name":"xuantie_single_surface_e902","family":"XuanTie","entry_mode":"single_surface",'
                    '"design":"XuanTie-E902","fallback_design":"XuanTie-E906"}\n'
                ),
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            selection_path.write_text('{"profile_name":"xuantie_single_surface_e902"}\n', encoding="utf-8")

            payload = self.module.build_gate(
                entry_payload={"decision": {"recommended_family": "XuanTie", "recommended_entry_mode": "family_pilot"}},
                readiness_payload={"decision": {"readiness": "legacy_family_pilot_failed_but_single_surface_override_ready"}},
                override_payload={
                    "decision": {"recommended_design": "XuanTie-E902", "fallback_design": "XuanTie-E906"},
                    "ranked_candidates": [
                        {
                            "design": "XuanTie-E902",
                            "ready": True,
                            "hybrid_wins": True,
                            "comparison_path": "/tmp/e902_cmp.json",
                            "speedup_ratio": 16.7,
                            "path": "/tmp/e902.json",
                        },
                    ],
                },
                selection_payload={"profile_name": "xuantie_single_surface_e902"},
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "single_surface_trio_ready")
            self.assertEqual(payload["outcome"]["next_action"], "accept_non_opentitan_campaign_trio")


if __name__ == "__main__":
    unittest.main()
