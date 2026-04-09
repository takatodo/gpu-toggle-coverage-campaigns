#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "set_campaign_xuantie_c910_runtime.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SetCampaignXuantieC910RuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("set_campaign_xuantie_c910_runtime_test", MODULE_PATH)

    def test_apply_profile_writes_selection_and_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir(parents=True)
            (profiles_dir / "debug_c910_hybrid_runtime.json").write_text(
                json.dumps(
                    {
                        "name": "debug_c910_hybrid_runtime",
                        "runtime_mode": "debug_c910_hybrid_runtime",
                        "notes": "debug",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            runtime_json = root / "runtime.json"
            runtime_json.write_text(
                json.dumps(
                    {
                        "outcome": {
                            "status": "decide_hybrid_runtime_debug_vs_open_veer_fallback_family",
                        },
                        "runtime_smoke": {"status": "hybrid_runtime_killed_even_at_minimal_shapes"},
                        "hybrid": {"status": "error"},
                        "cpu_baseline": {"status": "ok"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            next_axes_json = root / "next_axes.json"
            next_axes_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "status": "decide_continue_to_remaining_same_family_design_vs_open_fallback_family",
                            "recommended_same_family_design": "XuanTie-C910",
                        },
                        "next_family_axis": {
                            "fallback_profile_name": "open_veer_fallback_family",
                            "fallback_family": "VeeR",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            selection_json = root / "selection.json"
            gate_json = root / "gate.json"

            payload = self.module.apply_profile(
                profile_name="debug_c910_hybrid_runtime",
                profiles_dir=profiles_dir,
                runtime_status_json=runtime_json,
                same_family_next_axes_json=next_axes_json,
                selection_path=selection_json,
                gate_json_path=gate_json,
            )

            self.assertEqual(payload["outcome_status"], "debug_c910_hybrid_runtime_ready")
            selection = json.loads(selection_json.read_text(encoding="utf-8"))
            self.assertEqual(selection["profile_name"], "debug_c910_hybrid_runtime")
            gate = json.loads(gate_json.read_text(encoding="utf-8"))
            self.assertEqual(gate["outcome"]["status"], "debug_c910_hybrid_runtime_ready")


if __name__ == "__main__":
    unittest.main()
