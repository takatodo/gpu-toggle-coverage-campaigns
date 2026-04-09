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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xiangshan_vortex_branch_resolution.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXiangshanVortexBranchResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module(
            "audit_campaign_xiangshan_vortex_branch_resolution_test",
            MODULE_PATH,
        )

    def test_avoids_reopen_loop_by_keeping_current_xiangshan_branch(self) -> None:
        payload = self.module.build_resolution(
            vortex_gate_payload={
                "selection": {"profile_name": "reopen_xiangshan_fallback_family"},
                "outcome": {"status": "reopen_xiangshan_fallback_ready"},
            },
            vortex_acceptance_payload=None,
            post_vortex_axes_payload=None,
            xiangshan_status_payload={
                "outcome": {
                    "status": "decide_xiangshan_cubin_first_debug_vs_reopen_vortex_tls_lowering_debug",
                }
            },
            xiangshan_tactics_payload={
                "decision": {
                    "recommended_next_tactic": "reopen_vortex_tls_lowering_debug",
                    "fallback_tactic": "deeper_xiangshan_cubin_first_debug",
                }
            },
            vortex_tactics_payload={
                "decision": {
                    "recommended_next_tactic": "reopen_xiangshan_fallback_family",
                    "fallback_tactic": "deeper_vortex_tls_lowering_debug",
                }
            },
        )

        self.assertEqual(
            payload["decision"]["status"],
            "avoid_xiangshan_vortex_reopen_loop_keep_current_xiangshan_branch",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_xiangshan_cubin_first_debug",
        )
        self.assertEqual(
            payload["decision"]["fallback_tactic"],
            "deeper_vortex_tls_lowering_debug",
        )
        self.assertTrue(payload["observations"]["oscillation_detected"])

    def test_follows_post_vortex_axes_after_vortex_acceptance(self) -> None:
        payload = self.module.build_resolution(
            vortex_gate_payload={
                "selection": {"profile_name": "debug_vortex_tls_lowering"},
                "outcome": {"status": "vortex_gpu_build_recovered_ready_to_finish_trio"},
            },
            vortex_acceptance_payload={
                "outcome": {"status": "accepted_selected_vortex_first_surface_step"}
            },
            post_vortex_axes_payload={
                "decision": {
                    "status": "decide_open_next_family_after_vortex_acceptance",
                    "recommended_next_task": "open_the_next_post_vortex_family",
                }
            },
            xiangshan_status_payload={"outcome": {"status": "ready_to_finish_xiangshan_first_trio"}},
            xiangshan_tactics_payload={"decision": {}},
            vortex_tactics_payload={"decision": {"recommended_next_tactic": "finish_the_Vortex_first_campaign_trio"}},
        )

        self.assertEqual(payload["decision"]["status"], "follow_post_vortex_axes_after_accepting_vortex")
        self.assertEqual(payload["decision"]["recommended_next_tactic"], "open_the_next_post_vortex_family")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vortex_gate_json = root / "vortex_gate.json"
            vortex_acceptance_json = root / "vortex_acceptance.json"
            post_vortex_axes_json = root / "post_vortex_axes.json"
            xiangshan_status_json = root / "xiangshan_status.json"
            xiangshan_tactics_json = root / "xiangshan_tactics.json"
            vortex_tactics_json = root / "vortex_tactics.json"
            json_out = root / "resolution.json"

            vortex_gate_json.write_text(
                json.dumps(
                    {
                        "selection": {"profile_name": "reopen_xiangshan_fallback_family"},
                        "outcome": {"status": "reopen_xiangshan_fallback_ready"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            vortex_acceptance_json.write_text(
                json.dumps({"outcome": {"status": "accepted_selected_vortex_first_surface_step"}}) + "\n",
                encoding="utf-8",
            )
            post_vortex_axes_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "recommended_next_task": "open_the_next_post_vortex_family",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            xiangshan_status_json.write_text(
                json.dumps(
                    {
                        "outcome": {
                            "status": "decide_xiangshan_cubin_first_debug_vs_reopen_vortex_tls_lowering_debug",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            xiangshan_tactics_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "recommended_next_tactic": "reopen_vortex_tls_lowering_debug",
                            "fallback_tactic": "deeper_xiangshan_cubin_first_debug",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            vortex_tactics_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "recommended_next_tactic": "reopen_xiangshan_fallback_family",
                            "fallback_tactic": "deeper_vortex_tls_lowering_debug",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_xiangshan_vortex_branch_resolution.py",
                "--vortex-gate-json",
                str(vortex_gate_json),
                "--vortex-acceptance-json",
                str(vortex_acceptance_json),
                "--post-vortex-axes-json",
                str(post_vortex_axes_json),
                "--xiangshan-status-json",
                str(xiangshan_status_json),
                "--xiangshan-tactics-json",
                str(xiangshan_tactics_json),
                "--vortex-tactics-json",
                str(vortex_tactics_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_xiangshan_vortex_branch_resolution")
            self.assertEqual(
                payload["decision"]["recommended_next_tactic"],
                "open_the_next_post_vortex_family",
            )


if __name__ == "__main__":
    unittest.main()
