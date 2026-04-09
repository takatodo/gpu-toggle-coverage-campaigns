#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "set_campaign_vortex_first_surface.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SetCampaignVortexFirstSurfaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("set_campaign_vortex_first_surface_test", MODULE_PATH)

    def test_apply_profile_writes_selection_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir(parents=True)
            (profiles_dir / "debug_vortex_tls_lowering.json").write_text(
                json.dumps(
                    {
                        "name": "debug_vortex_tls_lowering",
                        "branch_mode": "debug_vortex_tls_lowering",
                        "notes": "debug",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            vortex_json = root / "vortex.json"
            vortex_json.write_text(
                json.dumps(
                    {
                        "outcome": {
                            "status": "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback",
                            "next_action": "choose_between_offline_vortex_tls_lowering_debug_and_reopening_xiangshan_fallback_family",
                        },
                        "gpu_build": {"status": "llc_tls_global_blocked", "blocker_kind": "nvptx_tls_lowering"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            axes_json = root / "axes.json"
            axes_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "status": "decide_open_next_family_after_blackparrot_baseline_loss",
                            "recommended_family": "Vortex",
                            "fallback_family": "XiangShan",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            xiangshan_json = root / "xiangshan.json"
            xiangshan_json.write_text(
                json.dumps(
                    {
                        "outcome": {
                            "status": "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            selection_json = root / "selection.json"
            gate_json = root / "gate.json"

            payload = self.module.apply_profile(
                profile_name="debug_vortex_tls_lowering",
                profiles_dir=profiles_dir,
                vortex_status_json=vortex_json,
                post_blackparrot_axes_json=axes_json,
                xiangshan_status_json=xiangshan_json,
                selection_path=selection_json,
                gate_json_path=gate_json,
            )

            self.assertEqual(payload["outcome_status"], "debug_vortex_tls_lowering_ready")
            selection = json.loads(selection_json.read_text(encoding="utf-8"))
            self.assertEqual(selection["profile_name"], "debug_vortex_tls_lowering")
            gate = json.loads(gate_json.read_text(encoding="utf-8"))
            self.assertEqual(gate["outcome"]["status"], "debug_vortex_tls_lowering_ready")


if __name__ == "__main__":
    unittest.main()
