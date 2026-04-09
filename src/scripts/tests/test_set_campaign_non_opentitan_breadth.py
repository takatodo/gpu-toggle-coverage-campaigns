#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "set_campaign_non_opentitan_breadth.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SetCampaignNonOpentitanBreadthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("set_campaign_non_opentitan_breadth_test", MODULE_PATH)

    def test_apply_profile_writes_selection_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "open_veer_fallback_family.json").write_text(
                '{"name":"open_veer_fallback_family","branch_mode":"open_fallback_family","family":"VeeR","notes":"demo"}\n',
                encoding="utf-8",
            )
            breadth_axes_json = root / "axes.json"
            selection_path = root / "selection.json"
            gate_json_path = root / "gate.json"
            breadth_axes_json.write_text(
                json.dumps(
                    {
                        "accepted_baseline": {},
                        "decision": {"status": "decide_continue_xuantie_breadth_vs_open_fallback_family"},
                        "recommended_family_axis": {
                            "recommended_family": "XuanTie",
                            "fallback_family": "VeeR",
                            "remaining_same_family_designs": ["XuanTie-C906", "XuanTie-C910"],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.apply_profile(
                profile_name="open_veer_fallback_family",
                profiles_dir=profiles_dir,
                breadth_axes_json=breadth_axes_json,
                selection_path=selection_path,
                gate_json_path=gate_json_path,
            )

            self.assertEqual(payload["outcome_status"], "open_fallback_family_ready")
            self.assertEqual(
                json.loads(selection_path.read_text(encoding="utf-8"))["profile_name"],
                "open_veer_fallback_family",
            )


if __name__ == "__main__":
    unittest.main()
