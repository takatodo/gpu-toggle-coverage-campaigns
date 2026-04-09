#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xuantie_breadth_acceptance_profiles.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXuantieBreadthAcceptanceProfilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xuantie_breadth_acceptance_profiles_test", MODULE_PATH)

    def test_reports_ready_profile_when_selected_breadth_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "hold_selected_xuantie_breadth.json").write_text(
                '{"name":"hold_selected_xuantie_breadth","accept_selected_breadth":false}\n',
                encoding="utf-8",
            )
            (profiles_dir / "accept_selected_xuantie_breadth.json").write_text(
                '{"name":"accept_selected_xuantie_breadth","accept_selected_breadth":true}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            selection_path.write_text(
                '{"profile_name":"hold_selected_xuantie_breadth"}\n',
                encoding="utf-8",
            )

            payload = self.module.build_profiles_matrix(
                real_goal_acceptance_payload={"outcome": {"status": "accepted_checkpoint_and_seed"}},
                breadth_gate_payload={"outcome": {"status": "candidate_only_ready"}},
                profiles_dir=profiles_dir,
                current_selection_payload={"profile_name": "hold_selected_xuantie_breadth"},
                current_selection_path=selection_path,
            )

            self.assertEqual(
                payload["summary"]["recommended_profile_name"],
                "accept_selected_xuantie_breadth",
            )
            self.assertEqual(payload["summary"]["current_profile_classification"], "hold")


if __name__ == "__main__":
    unittest.main()
