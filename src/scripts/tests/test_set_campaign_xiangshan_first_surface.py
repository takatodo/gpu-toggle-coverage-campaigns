#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "set_campaign_xiangshan_first_surface.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SetCampaignXiangshanFirstSurfaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("set_campaign_xiangshan_first_surface_test", MODULE_PATH)

    def test_apply_profile_writes_selection_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "xiangshan_candidate_only_threshold2.json").write_text(
                '{"name":"xiangshan_candidate_only_threshold2","step_mode":"candidate_only_threshold","design":"XiangShan","candidate_threshold_value":2,"notes":"demo"}\n',
                encoding="utf-8",
            )
            step_json = root / "step.json"
            selection_path = root / "selection.json"
            gate_json_path = root / "gate.json"
            step_json.write_text(
                json.dumps(
                    {
                        "selected_design": {
                            "design": "XiangShan",
                            "threshold2_candidate": {"threshold_value": 2},
                        },
                        "outcome": {
                            "status": "decide_xiangshan_candidate_only_vs_new_default_gate",
                            "selected_design": "XiangShan",
                            "candidate_threshold_value": 2,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.apply_profile(
                profile_name="xiangshan_candidate_only_threshold2",
                profiles_dir=profiles_dir,
                step_json=step_json,
                selection_path=selection_path,
                gate_json_path=gate_json_path,
            )

            self.assertEqual(payload["outcome_status"], "candidate_only_ready")
            self.assertEqual(
                json.loads(selection_path.read_text(encoding="utf-8"))["profile_name"],
                "xiangshan_candidate_only_threshold2",
            )


if __name__ == "__main__":
    unittest.main()
