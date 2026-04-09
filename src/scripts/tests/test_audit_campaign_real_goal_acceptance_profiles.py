#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_real_goal_acceptance_profiles.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignRealGoalAcceptanceProfilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_real_goal_acceptance_profiles_test", MODULE_PATH)

    def test_reports_accepted_profile_when_current_selection_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "hold_checkpoint_and_seed.json").write_text(
                '{"name":"hold_checkpoint_and_seed","accept_checkpoint":false,"accept_selected_seed":false}\n',
                encoding="utf-8",
            )
            (profiles_dir / "accept_checkpoint_and_seed.json").write_text(
                '{"name":"accept_checkpoint_and_seed","accept_checkpoint":true,"accept_selected_seed":true}\n',
                encoding="utf-8",
            )
            selection_path = root / "selection.json"
            selection_path.write_text('{"profile_name":"accept_checkpoint_and_seed"}\n', encoding="utf-8")

            payload = self.module.build_profiles_matrix(
                checkpoint_payload={"decision": {"readiness": "cross_family_checkpoint_ready"}},
                seed_payload={
                    "decision": {"status": "ready_to_accept_selected_seed"},
                    "selected_entry": {"design": "XuanTie-E902"},
                },
                profiles_dir=profiles_dir,
                current_selection_payload={"profile_name": "accept_checkpoint_and_seed"},
                current_selection_path=selection_path,
            )

            self.assertEqual(payload["summary"]["current_profile_classification"], "accepted")
            self.assertEqual(payload["summary"]["recommended_profile_name"], "accept_checkpoint_and_seed")


if __name__ == "__main__":
    unittest.main()
