#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "set_campaign_veer_same_family_acceptance.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SetCampaignVeerSameFamilyAcceptanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("set_campaign_veer_same_family_acceptance_test", MODULE_PATH)

    def test_apply_profile_writes_selection_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "accept_selected_veer_same_family_step.json").write_text(
                '{"name":"accept_selected_veer_same_family_step","accept_selected_veer_same_family_step":true,"notes":"demo"}\n',
                encoding="utf-8",
            )
            first_surface_acceptance_json = root / "first_surface_acceptance.json"
            same_family_gate_json = root / "same_family_gate.json"
            selection_path = root / "selection.json"
            gate_json_path = root / "gate.json"
            first_surface_acceptance_json.write_text(
                json.dumps({"outcome": {"status": "accepted_selected_veer_first_surface_step"}}) + "\n",
                encoding="utf-8",
            )
            same_family_gate_json.write_text(
                json.dumps(
                    {
                        "selection": {"profile_name": "veer_eh2_candidate_only_threshold4"},
                        "outcome": {
                            "status": "candidate_only_ready",
                            "selected_design": "VeeR-EH2",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.apply_profile(
                profile_name="accept_selected_veer_same_family_step",
                profiles_dir=profiles_dir,
                veer_first_surface_acceptance_json=first_surface_acceptance_json,
                veer_same_family_gate_json=same_family_gate_json,
                selection_path=selection_path,
                gate_json_path=gate_json_path,
            )

            self.assertEqual(payload["outcome_status"], "accepted_selected_veer_same_family_step")
            self.assertEqual(
                json.loads(selection_path.read_text(encoding="utf-8"))["profile_name"],
                "accept_selected_veer_same_family_step",
            )


if __name__ == "__main__":
    unittest.main()
