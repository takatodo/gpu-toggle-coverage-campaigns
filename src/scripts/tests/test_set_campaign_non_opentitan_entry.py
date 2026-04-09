#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "set_campaign_non_opentitan_entry.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SetCampaignNonOpentitanEntryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("set_campaign_non_opentitan_entry_test", MODULE_PATH)

    def test_apply_profile_writes_selection_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "xuantie_single_surface_e902.json").write_text(
                (
                    '{"name":"xuantie_single_surface_e902","family":"XuanTie","entry_mode":"single_surface",'
                    '"design":"XuanTie-E902","fallback_design":"XuanTie-E906","notes":"demo"}\n'
                ),
                encoding="utf-8",
            )
            entry_json = root / "entry.json"
            readiness_json = root / "readiness.json"
            override_json = root / "override.json"
            selection_json = root / "selection.json"
            gate_json = root / "gate.json"
            entry_json.write_text(
                '{"decision":{"recommended_family":"XuanTie","recommended_entry_mode":"family_pilot"}}\n',
                encoding="utf-8",
            )
            readiness_json.write_text(
                '{"decision":{"readiness":"legacy_family_pilot_failed_but_single_surface_override_ready"}}\n',
                encoding="utf-8",
            )
            override_json.write_text(
                '{"decision":{"recommended_design":"XuanTie-E902","fallback_design":"XuanTie-E906"},"ranked_candidates":[{"design":"XuanTie-E902","ready":true,"path":"/tmp/e902.json"}]}\n',
                encoding="utf-8",
            )

            payload = self.module.apply_profile(
                profile_name="xuantie_single_surface_e902",
                profiles_dir=profiles_dir,
                entry_json=entry_json,
                entry_readiness_json=readiness_json,
                override_candidates_json=override_json,
                selection_path=selection_json,
                gate_json_path=gate_json,
            )

            self.assertEqual(payload["outcome_status"], "single_surface_ready")
            self.assertEqual(json.loads(selection_json.read_text(encoding="utf-8"))["profile_name"], "xuantie_single_surface_e902")


if __name__ == "__main__":
    unittest.main()
