#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "set_campaign_xuantie_breadth.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SetCampaignXuantieBreadthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("set_campaign_xuantie_breadth_test", MODULE_PATH)

    def test_apply_profile_writes_selection_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "e906_candidate_only_threshold2.json").write_text(
                (
                    '{"name":"e906_candidate_only_threshold2","breadth_mode":"candidate_only_threshold",'
                    '"design":"XuanTie-E906","candidate_threshold_value":2,"notes":"demo"}\n'
                ),
                encoding="utf-8",
            )
            breadth_status_json = root / "breadth_status.json"
            selection_json = root / "selection.json"
            gate_json = root / "gate.json"
            breadth_status_json.write_text(
                (
                    '{"decision":{"status":"decide_e906_candidate_only_vs_new_default_gate"},'
                    '"accepted_seed":{"design":"XuanTie-E902"},'
                    '"entry_context":{"entry_readiness":"legacy_family_pilot_failed_but_single_surface_override_ready"},'
                    '"e906_candidate_only_threshold2":{"comparison_ready":true,"winner":"hybrid"}}\n'
                ),
                encoding="utf-8",
            )

            payload = self.module.apply_profile(
                profile_name="e906_candidate_only_threshold2",
                profiles_dir=profiles_dir,
                breadth_status_json=breadth_status_json,
                selection_path=selection_json,
                gate_json_path=gate_json,
            )

            self.assertEqual(payload["outcome_status"], "candidate_only_ready")
            self.assertEqual(
                json.loads(selection_json.read_text(encoding="utf-8"))["profile_name"],
                "e906_candidate_only_threshold2",
            )


if __name__ == "__main__":
    unittest.main()
