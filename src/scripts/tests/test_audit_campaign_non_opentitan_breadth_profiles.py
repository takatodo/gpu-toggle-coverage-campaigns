#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_non_opentitan_breadth_profiles.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignNonOpentitanBreadthProfilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_non_opentitan_breadth_profiles_test", MODULE_PATH)

    def test_reports_multiple_ready_profiles_without_forcing_one_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "hold_post_e906_branch.json").write_text(
                '{"name":"hold_post_e906_branch","branch_mode":"hold_post_e906_branch"}\n',
                encoding="utf-8",
            )
            (profiles_dir / "xuantie_continue_same_family.json").write_text(
                '{"name":"xuantie_continue_same_family","branch_mode":"continue_same_family","family":"XuanTie"}\n',
                encoding="utf-8",
            )
            (profiles_dir / "open_veer_fallback_family.json").write_text(
                '{"name":"open_veer_fallback_family","branch_mode":"open_fallback_family","family":"VeeR"}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            selection_path.write_text('{"profile_name":"hold_post_e906_branch"}\n', encoding="utf-8")

            payload = self.module.build_profiles_matrix(
                breadth_axes_payload={
                    "accepted_baseline": {},
                    "decision": {
                        "status": "decide_continue_xuantie_breadth_vs_open_fallback_family",
                    },
                    "recommended_family_axis": {
                    "recommended_family": "XuanTie",
                    "fallback_family": "VeeR",
                    "remaining_same_family_designs": ["XuanTie-C906", "XuanTie-C910"],
                },
            },
                profiles_dir=profiles_dir,
                current_selection_payload={"profile_name": "hold_post_e906_branch"},
                current_selection_path=selection_path,
            )

            self.assertIsNone(payload["summary"]["recommended_profile_name"])
            self.assertEqual(
                payload["summary"]["ready_profile_names"],
                ["open_veer_fallback_family", "xuantie_continue_same_family"],
            )
            self.assertEqual(payload["summary"]["current_profile_classification"], "hold")


if __name__ == "__main__":
    unittest.main()
