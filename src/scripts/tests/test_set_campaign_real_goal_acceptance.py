#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "set_campaign_real_goal_acceptance.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SetCampaignRealGoalAcceptanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("set_campaign_real_goal_acceptance_test", MODULE_PATH)

    def test_apply_profile_writes_selection_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "accept_checkpoint_and_seed.json").write_text(
                (
                    '{"name":"accept_checkpoint_and_seed","accept_checkpoint":true,'
                    '"accept_selected_seed":true,"notes":"demo"}\n'
                ),
                encoding="utf-8",
            )
            checkpoint_json = root / "checkpoint.json"
            seed_json = root / "seed.json"
            selection_json = root / "selection.json"
            gate_json = root / "gate.json"
            checkpoint_json.write_text(
                '{"decision":{"readiness":"cross_family_checkpoint_ready"},"summary":{"active_surface_count":9}}\n',
                encoding="utf-8",
            )
            seed_json.write_text(
                (
                    '{"decision":{"status":"ready_to_accept_selected_seed"},'
                    '"selected_entry":{"design":"XuanTie-E902","profile_name":"xuantie_single_surface_e902"}}\n'
                ),
                encoding="utf-8",
            )

            payload = self.module.apply_profile(
                profile_name="accept_checkpoint_and_seed",
                profiles_dir=profiles_dir,
                checkpoint_json=checkpoint_json,
                seed_status_json=seed_json,
                selection_path=selection_json,
                gate_json_path=gate_json,
            )

            self.assertEqual(payload["outcome_status"], "accepted_checkpoint_and_seed")
            self.assertEqual(
                json.loads(selection_json.read_text(encoding="utf-8"))["profile_name"],
                "accept_checkpoint_and_seed",
            )


if __name__ == "__main__":
    unittest.main()
