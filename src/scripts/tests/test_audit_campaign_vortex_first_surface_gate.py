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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_vortex_first_surface_gate.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignVortexFirstSurfaceGateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_vortex_first_surface_gate_test", MODULE_PATH)

    def test_debug_profile_is_ready_when_vortex_is_blocked_on_tls_lowering(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selection_dir = root / "selection"
            profiles_dir = selection_dir / "profiles"
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
            selection_path = selection_dir / "selection.json"
            selection_path.write_text(
                json.dumps({"profile_name": "debug_vortex_tls_lowering", "notes": "debug"}) + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_gate(
                vortex_status_payload={
                    "outcome": {
                        "status": "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback",
                        "reason": "vortex_gpu_codegen_fails_on_verilated_tls",
                        "next_action": "choose_between_offline_vortex_tls_lowering_debug_and_reopening_xiangshan_fallback_family",
                    },
                    "gpu_build": {
                        "status": "llc_tls_global_blocked",
                        "blocker_kind": "nvptx_tls_lowering",
                        "failing_function": "demo",
                    },
                },
                post_blackparrot_axes_payload={
                    "decision": {
                        "status": "decide_open_next_family_after_blackparrot_baseline_loss",
                        "recommended_family": "Vortex",
                        "fallback_family": "XiangShan",
                    }
                },
                xiangshan_status_payload={
                    "outcome": {
                        "status": "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family",
                    }
                },
                selection_payload={
                    "profile_name": "debug_vortex_tls_lowering",
                    "notes": "debug",
                },
                selection_path=selection_path,
            )

            self.assertEqual(payload["outcome"]["status"], "debug_vortex_tls_lowering_ready")
            self.assertEqual(payload["context"]["recommended_family"], "Vortex")
            self.assertEqual(payload["outcome"]["gpu_blocker_kind"], "nvptx_tls_lowering")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            selection_dir = root / "selection"
            profiles_dir = selection_dir / "profiles"
            profiles_dir.mkdir(parents=True)
            (profiles_dir / "hold_vortex_first_surface_branch.json").write_text(
                json.dumps(
                    {
                        "name": "hold_vortex_first_surface_branch",
                        "branch_mode": "hold_vortex_first_surface_branch",
                        "notes": "hold",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            selection_json = selection_dir / "selection.json"
            selection_json.write_text(
                json.dumps({"profile_name": "hold_vortex_first_surface_branch", "notes": "hold"}) + "\n",
                encoding="utf-8",
            )
            vortex_json = root / "vortex.json"
            vortex_json.write_text(
                json.dumps({"outcome": {"status": "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback"}})
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
                json.dumps({"outcome": {"status": "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family"}})
                + "\n",
                encoding="utf-8",
            )
            json_out = root / "gate.json"

            argv = [
                "audit_campaign_vortex_first_surface_gate.py",
                "--vortex-status-json",
                str(vortex_json),
                "--post-blackparrot-axes-json",
                str(axes_json),
                "--xiangshan-status-json",
                str(xiangshan_json),
                "--selection-config",
                str(selection_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_vortex_first_surface_gate")
            self.assertEqual(payload["outcome"]["status"], "hold_vortex_first_surface_branch")


if __name__ == "__main__":
    unittest.main()
