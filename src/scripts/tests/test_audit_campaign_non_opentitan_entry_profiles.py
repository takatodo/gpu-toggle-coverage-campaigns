#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_non_opentitan_entry_profiles.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignNonOpentitanEntryProfilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_non_opentitan_entry_profiles_test", MODULE_PATH)

    def test_reports_ready_override_profile_against_blocked_current_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "xuantie_family_pilot_hold.json").write_text(
                '{"name":"xuantie_family_pilot_hold","family":"XuanTie","entry_mode":"family_pilot"}\n',
                encoding="utf-8",
            )
            (profiles_dir / "xuantie_single_surface_e902.json").write_text(
                (
                    '{"name":"xuantie_single_surface_e902","family":"XuanTie","entry_mode":"single_surface",'
                    '"design":"XuanTie-E902","fallback_design":"XuanTie-E906"}\n'
                ),
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            selection_path.write_text('{"profile_name":"xuantie_family_pilot_hold"}\n', encoding="utf-8")

            payload = self.module.build_profiles_matrix(
                entry_payload={"decision": {"recommended_family": "XuanTie", "recommended_entry_mode": "family_pilot"}},
                readiness_payload={"decision": {"readiness": "legacy_family_pilot_failed_but_single_surface_override_ready", "reason": "override exists"}},
                override_payload={
                    "decision": {"recommended_design": "XuanTie-E902", "fallback_design": "XuanTie-E906"},
                    "ranked_candidates": [{"design": "XuanTie-E902", "ready": True, "path": "/tmp/e902.json"}],
                },
                profiles_dir=profiles_dir,
                current_selection_payload={"profile_name": "xuantie_family_pilot_hold"},
                current_selection_path=selection_path,
            )

            self.assertEqual(payload["summary"]["current_profile_name"], "xuantie_family_pilot_hold")
            self.assertEqual(payload["summary"]["current_profile_classification"], "blocked")
            self.assertEqual(payload["summary"]["recommended_profile_name"], "xuantie_single_surface_e902")
            self.assertEqual(
                payload["summary"]["recommended_decision_axis"],
                "choose_named_non_opentitan_entry_profile_before_implementation",
            )

    def test_reports_accept_axis_when_current_profile_is_already_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "xuantie_family_pilot_hold.json").write_text(
                '{"name":"xuantie_family_pilot_hold","family":"XuanTie","entry_mode":"family_pilot"}\n',
                encoding="utf-8",
            )
            (profiles_dir / "xuantie_single_surface_e902.json").write_text(
                (
                    '{"name":"xuantie_single_surface_e902","family":"XuanTie","entry_mode":"single_surface",'
                    '"design":"XuanTie-E902","fallback_design":"XuanTie-E906"}\n'
                ),
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            selection_path.write_text('{"profile_name":"xuantie_single_surface_e902"}\n', encoding="utf-8")

            payload = self.module.build_profiles_matrix(
                entry_payload={"decision": {"recommended_family": "XuanTie", "recommended_entry_mode": "family_pilot"}},
                readiness_payload={"decision": {"readiness": "legacy_family_pilot_failed_but_single_surface_override_ready", "reason": "override exists"}},
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
                        }
                    ],
                },
                profiles_dir=profiles_dir,
                current_selection_payload={"profile_name": "xuantie_single_surface_e902"},
                current_selection_path=selection_path,
            )

            self.assertEqual(payload["summary"]["current_profile_name"], "xuantie_single_surface_e902")
            self.assertEqual(payload["summary"]["current_profile_classification"], "ready")
            self.assertEqual(payload["summary"]["recommended_profile_name"], "xuantie_single_surface_e902")
            self.assertEqual(
                payload["summary"]["recommended_decision_axis"],
                "accept_current_profile_seed_or_add_gate",
            )


if __name__ == "__main__":
    unittest.main()
