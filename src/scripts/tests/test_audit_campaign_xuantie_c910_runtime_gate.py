#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xuantie_c910_runtime_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXuantieC910RuntimeGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xuantie_c910_runtime_gate_test", MODULE_PATH)

    def test_debug_profile_is_ready_when_runtime_is_sigkilled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selection_dir = root / "selection"
            profiles_dir = selection_dir / "profiles"
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
            selection_path = selection_dir / "selection.json"
            selection_path.write_text(
                json.dumps({"profile_name": "debug_c910_hybrid_runtime", "notes": "debug"}) + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_gate(
                runtime_status_payload={
                    "outcome": {
                        "status": "decide_hybrid_runtime_debug_vs_open_veer_fallback_family",
                        "reason": "c910_runtime_and_offline_cubin_are_both_unready",
                        "next_action": "choose_between_deeper_c910_cubin_debug_and_opening_the_veer_fallback_family",
                    },
                    "runtime_smoke": {"status": "hybrid_runtime_killed_even_at_minimal_shapes"},
                    "hybrid": {"status": "error"},
                    "cpu_baseline": {"status": "ok"},
                    "low_opt_runtime_debug": {
                        "o1_trace": {"status": "stalled_before_cuModuleLoad"},
                        "cubin_probe": {"status": "timed_out"},
                    },
                },
                same_family_next_axes_payload={
                    "decision": {
                        "status": "decide_continue_to_remaining_same_family_design_vs_open_fallback_family",
                        "recommended_same_family_design": "XuanTie-C910",
                    },
                    "next_family_axis": {
                        "fallback_profile_name": "open_veer_fallback_family",
                        "fallback_family": "VeeR",
                    },
                },
                selection_payload={
                    "profile_name": "debug_c910_hybrid_runtime",
                    "notes": "debug",
                },
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "debug_c910_hybrid_runtime_ready")
            self.assertEqual(payload["context"]["selected_same_family_design"], "XuanTie-C910")
            self.assertEqual(
                payload["outcome"]["next_action"],
                "choose_between_deeper_c910_cubin_debug_and_opening_the_veer_fallback_family",
            )
            self.assertEqual(payload["outcome"]["o1_trace_status"], "stalled_before_cuModuleLoad")
            self.assertEqual(payload["outcome"]["cubin_probe_status"], "timed_out")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selection_dir = root / "selection"
            profiles_dir = selection_dir / "profiles"
            profiles_dir.mkdir(parents=True)
            (profiles_dir / "hold_c910_runtime_branch.json").write_text(
                json.dumps(
                    {
                        "name": "hold_c910_runtime_branch",
                        "runtime_mode": "hold_c910_runtime_branch",
                        "notes": "hold",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            selection_json = selection_dir / "selection.json"
            selection_json.write_text(
                json.dumps({"profile_name": "hold_c910_runtime_branch", "notes": "hold"}) + "\n",
                encoding="utf-8",
            )
            runtime_json = root / "runtime.json"
            runtime_json.write_text(
                json.dumps({"outcome": {"status": "decide_hybrid_runtime_debug_vs_open_veer_fallback_family"}})
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
            json_out = root / "gate.json"

            argv = [
                "audit_campaign_xuantie_c910_runtime_gate.py",
                "--runtime-status-json",
                str(runtime_json),
                "--same-family-next-axes-json",
                str(next_axes_json),
                "--selection-config",
                str(selection_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_xuantie_c910_runtime_gate")
            self.assertEqual(payload["outcome"]["status"], "hold_c910_runtime_branch")


if __name__ == "__main__":
    unittest.main()
