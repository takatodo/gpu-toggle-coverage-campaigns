#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "set_campaign_vortex_first_surface_acceptance.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SetCampaignVortexFirstSurfaceAcceptanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("set_campaign_vortex_first_surface_acceptance_test", MODULE_PATH)

    def test_apply_profile_writes_selection_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir()
            (profiles_dir / "accept_selected_vortex_first_surface_step.json").write_text(
                '{"name":"accept_selected_vortex_first_surface_step","accept_selected_vortex_first_surface_step":true,"notes":"demo"}\n',
                encoding="utf-8",
            )
            branch_gate_json = root / "branch_gate.json"
            policy_gate_json = root / "policy_gate.json"
            selection_path = root / "selection.json"
            gate_json_path = root / "gate.json"
            branch_gate_json.write_text(
                json.dumps({"outcome": {"status": "vortex_gpu_build_recovered_ready_to_finish_trio"}}) + "\n",
                encoding="utf-8",
            )
            policy_gate_json.write_text(
                json.dumps(
                    {
                        "selection": {"profile_name": "vortex_candidate_only_threshold4"},
                        "outcome": {
                            "status": "candidate_only_ready",
                            "selected_design": "Vortex",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.apply_profile(
                profile_name="accept_selected_vortex_first_surface_step",
                profiles_dir=profiles_dir,
                vortex_branch_gate_json=branch_gate_json,
                vortex_policy_gate_json=policy_gate_json,
                selection_path=selection_path,
                gate_json_path=gate_json_path,
            )

            self.assertEqual(payload["outcome_status"], "accepted_selected_vortex_first_surface_step")
            self.assertEqual(
                json.loads(selection_path.read_text(encoding="utf-8"))["profile_name"],
                "accept_selected_vortex_first_surface_step",
            )


if __name__ == "__main__":
    unittest.main()
