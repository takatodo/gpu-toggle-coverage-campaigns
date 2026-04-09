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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xuantie_c910_debug_tactics.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXuantieC910DebugTacticsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xuantie_c910_debug_tactics_test", MODULE_PATH)

    def test_recommends_kernel_split_when_split_trial_is_not_available_yet(self) -> None:
        payload = self.module.build_tactics(
            runtime_status_payload={
                "outcome": {
                    "status": "decide_hybrid_runtime_debug_vs_open_veer_fallback_family",
                },
                "low_opt_runtime_debug": {
                    "o1_trace": {
                        "status": "stalled_before_cuModuleLoad",
                        "last_stage": "before_cuModuleLoad",
                    },
                    "cubin_probe": {
                        "status": "timed_out",
                        "timeout_seconds": 180,
                        "cubin_exists": False,
                    },
                },
            },
            runtime_gate_payload={
                "selection": {"profile_name": "debug_c910_hybrid_runtime"},
                "outcome": {"status": "debug_c910_hybrid_runtime_ready"},
            },
            split_phase_trial_payload=None,
        )

        self.assertEqual(
            payload["decision"]["status"],
            "try_kernel_split_phases_before_opening_fallback_family",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "kernel_split_phases_ptx_module_first",
        )

    def test_recommends_fallback_after_split_trial_also_times_out(self) -> None:
        payload = self.module.build_tactics(
            runtime_status_payload={
                "outcome": {
                    "status": "decide_hybrid_runtime_debug_vs_open_veer_fallback_family",
                },
                "low_opt_runtime_debug": {
                    "o1_trace": {
                        "status": "stalled_before_cuModuleLoad",
                        "last_stage": "before_cuModuleLoad",
                    },
                    "cubin_probe": {
                        "status": "timed_out",
                        "timeout_seconds": 180,
                        "cubin_exists": False,
                    },
                },
            },
            runtime_gate_payload={
                "selection": {"profile_name": "debug_c910_hybrid_runtime"},
                "outcome": {"status": "debug_c910_hybrid_runtime_ready"},
            },
            split_phase_trial_payload={
                "split_phase_runtime": {
                    "status": "timed_out",
                    "last_stage": "before_cuModuleLoad",
                    "returncode": 137,
                },
                "decision": {
                    "status": "timed_out_before_cuModuleLoad",
                },
            },
        )

        self.assertEqual(
            payload["decision"]["status"],
            "prefer_fallback_family_after_split_phase_trial_failed",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "open_veer_fallback_family",
        )
        self.assertEqual(
            payload["decision"]["fallback_tactic"],
            "deeper_c910_cubin_debug",
        )

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runtime_json = root / "runtime.json"
            gate_json = root / "gate.json"
            split_trial_json = root / "split_trial.json"
            json_out = root / "tactics.json"
            runtime_json.write_text(
                json.dumps(
                    {
                        "outcome": {
                            "status": "decide_hybrid_runtime_debug_vs_open_veer_fallback_family",
                        },
                        "low_opt_runtime_debug": {
                            "o1_trace": {
                                "status": "stalled_before_cuModuleLoad",
                                "last_stage": "before_cuModuleLoad",
                            },
                            "cubin_probe": {
                                "status": "timed_out",
                                "timeout_seconds": 180,
                                "cubin_exists": False,
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            gate_json.write_text(
                json.dumps(
                    {
                        "selection": {"profile_name": "debug_c910_hybrid_runtime"},
                        "outcome": {"status": "debug_c910_hybrid_runtime_ready"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            split_trial_json.write_text(
                json.dumps(
                    {
                        "split_phase_runtime": {
                            "status": "timed_out",
                            "last_stage": "before_cuModuleLoad",
                            "returncode": 137,
                        },
                        "decision": {
                            "status": "timed_out_before_cuModuleLoad",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_xuantie_c910_debug_tactics.py",
                "--runtime-status-json",
                str(runtime_json),
                "--runtime-gate-json",
                str(gate_json),
                "--split-phase-trial-json",
                str(split_trial_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_xuantie_c910_debug_tactics")
            self.assertEqual(
                payload["decision"]["recommended_next_tactic"],
                "open_veer_fallback_family",
            )


if __name__ == "__main__":
    unittest.main()
