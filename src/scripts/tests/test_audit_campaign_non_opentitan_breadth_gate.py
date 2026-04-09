#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_non_opentitan_breadth_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignNonOpentitanBreadthGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_non_opentitan_breadth_gate_test", MODULE_PATH)

    def test_continue_same_family_profile_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "xuantie_continue_same_family.json").write_text(
                '{"name":"xuantie_continue_same_family","branch_mode":"continue_same_family","family":"XuanTie"}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"

            payload = self.module.build_gate(
                breadth_axes_payload={
                    "accepted_baseline": {
                        "selected_seed_design": "XuanTie-E902",
                        "selected_breadth_design": "XuanTie-E906",
                        "selected_breadth_profile_name": "e906_candidate_only_threshold2",
                    },
                    "decision": {
                        "status": "decide_continue_xuantie_breadth_vs_open_fallback_family",
                    },
                    "recommended_family_axis": {
                        "recommended_family": "XuanTie",
                        "fallback_family": "VeeR",
                        "remaining_same_family_designs": ["XuanTie-C906", "XuanTie-C910"],
                    },
                },
                selection_payload={"profile_name": "xuantie_continue_same_family"},
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "continue_same_family_ready")
            self.assertEqual(
                payload["outcome"]["remaining_same_family_designs"],
                ["XuanTie-C906", "XuanTie-C910"],
            )

    def test_fallback_family_profile_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "open_veer_fallback_family.json").write_text(
                '{"name":"open_veer_fallback_family","branch_mode":"open_fallback_family","family":"VeeR"}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"

            payload = self.module.build_gate(
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
                selection_payload={"profile_name": "open_veer_fallback_family"},
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "open_fallback_family_ready")


if __name__ == "__main__":
    unittest.main()
