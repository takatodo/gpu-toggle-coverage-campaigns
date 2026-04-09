#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xuantie_breadth_profiles.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXuantieBreadthProfilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xuantie_breadth_profiles_test", MODULE_PATH)

    def test_reports_ready_candidate_only_alternative_against_hold_current_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "e906_default_gate_hold.json").write_text(
                '{"name":"e906_default_gate_hold","breadth_mode":"default_gate_hold","design":"XuanTie-E906"}\n',
                encoding="utf-8",
            )
            (profiles_dir / "e906_candidate_only_threshold2.json").write_text(
                (
                    '{"name":"e906_candidate_only_threshold2","breadth_mode":"candidate_only_threshold",'
                    '"design":"XuanTie-E906","candidate_threshold_value":2}\n'
                ),
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            selection_path.write_text('{"profile_name":"e906_default_gate_hold"}\n', encoding="utf-8")

            payload = self.module.build_profiles_matrix(
                breadth_status_payload={
                    "decision": {"status": "decide_e906_candidate_only_vs_new_default_gate"},
                    "accepted_seed": {"design": "XuanTie-E902"},
                    "entry_context": {"entry_readiness": "legacy_family_pilot_failed_but_single_surface_override_ready"},
                    "e906_default_gate": {"status": "default_gate_blocked_across_known_case_pats"},
                    "e906_candidate_only_threshold2": {"comparison_ready": True, "winner": "hybrid"},
                },
                profiles_dir=profiles_dir,
                current_selection_payload={"profile_name": "e906_default_gate_hold"},
                current_selection_path=selection_path,
            )

            self.assertEqual(payload["summary"]["current_profile_classification"], "hold")
            self.assertEqual(payload["summary"]["recommended_profile_name"], "e906_candidate_only_threshold2")


if __name__ == "__main__":
    unittest.main()
