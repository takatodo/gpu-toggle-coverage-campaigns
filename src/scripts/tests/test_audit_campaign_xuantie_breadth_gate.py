#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xuantie_breadth_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXuantieBreadthGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xuantie_breadth_gate_test", MODULE_PATH)

    def test_candidate_only_profile_is_ready_when_threshold2_win_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "e906_candidate_only_threshold2.json").write_text(
                (
                    '{"name":"e906_candidate_only_threshold2","breadth_mode":"candidate_only_threshold",'
                    '"design":"XuanTie-E906","candidate_threshold_value":2}\n'
                ),
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            payload = self.module.build_gate(
                breadth_status_payload={
                    "decision": {"status": "decide_e906_candidate_only_vs_new_default_gate"},
                    "accepted_seed": {"design": "XuanTie-E902", "profile_name": "xuantie_single_surface_e902"},
                    "entry_context": {"entry_readiness": "legacy_family_pilot_failed_but_single_surface_override_ready"},
                    "e906_candidate_only_threshold2": {
                        "comparison_ready": True,
                        "winner": "hybrid",
                        "comparison_path": "/tmp/e906_cmp.json",
                        "speedup_ratio": 30.3,
                    },
                },
                selection_payload={"profile_name": "e906_candidate_only_threshold2"},
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "candidate_only_ready")
            self.assertEqual(payload["outcome"]["candidate_threshold_value"], 2)

    def test_default_gate_hold_reports_hold_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "e906_default_gate_hold.json").write_text(
                '{"name":"e906_default_gate_hold","breadth_mode":"default_gate_hold","design":"XuanTie-E906"}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            payload = self.module.build_gate(
                breadth_status_payload={
                    "accepted_seed": {"design": "XuanTie-E902"},
                    "e906_default_gate": {
                        "status": "default_gate_blocked_across_known_case_pats",
                        "known_case_count": 3,
                        "default_threshold_values": [8],
                    },
                },
                selection_payload={"profile_name": "e906_default_gate_hold"},
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "default_gate_hold")


if __name__ == "__main__":
    unittest.main()
