#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "set_campaign_xiangshan_first_surface_acceptance.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SetCampaignXiangshanFirstSurfaceAcceptanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("set_campaign_xiangshan_first_surface_acceptance_test", MODULE_PATH)

    def test_apply_profile_writes_selection_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "accept_selected_xiangshan_first_surface_step.json").write_text(
                '{"name":"accept_selected_xiangshan_first_surface_step","accept_selected_xiangshan_first_surface_step":true,"notes":"demo"}\n',
                encoding="utf-8",
            )
            vortex_gate_json = root / "vortex_gate.json"
            xiangshan_gate_json = root / "xiangshan_gate.json"
            selection_path = root / "selection.json"
            gate_json_path = root / "gate.json"
            vortex_gate_json.write_text(
                json.dumps({"outcome": {"status": "reopen_xiangshan_fallback_ready"}}) + "\n",
                encoding="utf-8",
            )
            xiangshan_gate_json.write_text(
                json.dumps(
                    {
                        "selection": {"profile_name": "xiangshan_candidate_only_threshold2"},
                        "outcome": {
                            "status": "candidate_only_ready",
                            "selected_design": "XiangShan",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.apply_profile(
                profile_name="accept_selected_xiangshan_first_surface_step",
                profiles_dir=profiles_dir,
                vortex_gate_json=vortex_gate_json,
                xiangshan_gate_json=xiangshan_gate_json,
                selection_path=selection_path,
                gate_json_path=gate_json_path,
            )

            self.assertEqual(payload["outcome_status"], "accepted_selected_xiangshan_first_surface_step")
            self.assertEqual(
                json.loads(selection_path.read_text(encoding="utf-8"))["profile_name"],
                "accept_selected_xiangshan_first_surface_step",
            )


if __name__ == "__main__":
    unittest.main()
