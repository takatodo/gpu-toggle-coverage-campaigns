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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xiangshan_debug_tactics.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXiangshanDebugTacticsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xiangshan_debug_tactics_test", MODULE_PATH)

    def test_prefers_reopen_vortex_when_ptxas_probe_fails(self) -> None:
        payload = self.module.build_tactics(
            xiangshan_status_payload={
                "current_branch": {
                    "source_scope": "campaign_vortex_first_surface_gate",
                    "selected_profile_name": "reopen_xiangshan_fallback_family",
                    "fallback_branch": "debug_vortex_tls_lowering",
                },
                "outcome": {
                    "status": "decide_xiangshan_cubin_first_debug_vs_reopen_vortex_tls_lowering_debug",
                },
                "ptx_smoke": {
                    "status": "stalled_before_cuModuleLoad",
                    "last_stage": "before_cuModuleLoad",
                },
                "gpu_module": {
                    "module_format": "ptx",
                    "module_path": "vl_batch_gpu.ptx",
                },
            },
            vortex_profiles_payload={
                "summary": {
                    "ready_profiles": [
                        "debug_vortex_tls_lowering",
                        "reopen_xiangshan_fallback_family",
                    ]
                }
            },
            ptxas_probe_payload={
                "status": "timed_out",
                "elapsed_ms": 180000,
                "cubin_exists": False,
            },
        )

        self.assertEqual(
            payload["decision"]["status"],
            "prefer_reopen_vortex_after_xiangshan_ptxas_probe_failed",
        )
        self.assertEqual(payload["decision"]["recommended_next_tactic"], "reopen_vortex_tls_lowering_debug")
        self.assertTrue(payload["current_branch"]["fallback_branch_ready"])

    def test_continues_xiangshan_when_probe_is_absent(self) -> None:
        payload = self.module.build_tactics(
            xiangshan_status_payload={
                "current_branch": {
                    "source_scope": "campaign_vortex_first_surface_gate",
                    "selected_profile_name": "reopen_xiangshan_fallback_family",
                    "fallback_branch": "debug_vortex_tls_lowering",
                },
                "outcome": {
                    "status": "decide_xiangshan_cubin_first_debug_vs_reopen_vortex_tls_lowering_debug",
                },
                "ptx_smoke": {
                    "status": "stalled_before_cuModuleLoad",
                    "last_stage": "before_cuModuleLoad",
                },
                "gpu_module": {
                    "module_format": "ptx",
                    "module_path": "vl_batch_gpu.ptx",
                },
            },
            vortex_profiles_payload={"summary": {"ready_profiles": ["debug_vortex_tls_lowering"]}},
            ptxas_probe_payload=None,
        )

        self.assertEqual(payload["decision"]["status"], "continue_xiangshan_cubin_first_debug")
        self.assertEqual(payload["decision"]["recommended_next_tactic"], "offline_xiangshan_cubin_first_debug")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xiangshan_json = root / "xiangshan.json"
            vortex_profiles_json = root / "vortex_profiles.json"
            probe_json = root / "probe.json"
            json_out = root / "tactics.json"

            xiangshan_json.write_text(
                json.dumps(
                    {
                        "current_branch": {
                            "source_scope": "campaign_vortex_first_surface_gate",
                            "selected_profile_name": "reopen_xiangshan_fallback_family",
                            "fallback_branch": "debug_vortex_tls_lowering",
                        },
                        "outcome": {
                            "status": "decide_xiangshan_cubin_first_debug_vs_reopen_vortex_tls_lowering_debug",
                        },
                        "ptx_smoke": {
                            "status": "stalled_before_cuModuleLoad",
                            "last_stage": "before_cuModuleLoad",
                        },
                        "gpu_module": {
                            "module_format": "ptx",
                            "module_path": "vl_batch_gpu.ptx",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            vortex_profiles_json.write_text(
                json.dumps(
                    {
                        "summary": {
                            "ready_profiles": [
                                "debug_vortex_tls_lowering",
                                "reopen_xiangshan_fallback_family",
                            ]
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            probe_json.write_text(
                json.dumps(
                    {
                        "status": "timed_out",
                        "elapsed_ms": 180000,
                        "cubin_exists": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_xiangshan_debug_tactics.py",
                "--xiangshan-status-json",
                str(xiangshan_json),
                "--vortex-profiles-json",
                str(vortex_profiles_json),
                "--ptxas-probe-json",
                str(probe_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_xiangshan_debug_tactics")
            self.assertEqual(
                payload["decision"]["recommended_next_tactic"],
                "reopen_vortex_tls_lowering_debug",
            )


if __name__ == "__main__":
    unittest.main()
