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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_veer_first_surface_step.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignVeerFirstSurfaceStepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_veer_first_surface_step_test", MODULE_PATH)

    def test_blocks_when_veer_fallback_is_not_active(self) -> None:
        payload = self.module.build_status(
            c910_runtime_gate_payload={
                "selection": {"profile_name": "debug_c910_hybrid_runtime"},
                "outcome": {"status": "debug_c910_hybrid_runtime_ready", "next_action": "continue_c910_debug"},
            },
            veer_fallback_candidates_payload={"decision": {"recommended_first_design": "VeeR-EH1"}},
            default_comparison_payload=None,
            threshold5_comparison_payload=None,
        )

        self.assertEqual(payload["outcome"]["status"], "blocked_veer_fallback_not_active")

    def test_reports_candidate_only_vs_new_default_gate_for_veer_eh1(self) -> None:
        payload = self.module.build_status(
            c910_runtime_gate_payload={
                "selection": {"profile_name": "open_veer_fallback_family"},
                "outcome": {"status": "open_fallback_family_ready"},
            },
            veer_fallback_candidates_payload={
                "decision": {
                    "recommended_first_design": "VeeR-EH1",
                    "fallback_design": "VeeR-EH2",
                }
            },
            default_comparison_payload={
                "status": "ok",
                "comparison_ready": False,
                "winner": "unresolved",
                "campaign_threshold": {"value": 8},
            },
            threshold5_comparison_payload={
                "status": "ok",
                "comparison_ready": True,
                "winner": "hybrid",
                "speedup_ratio": 3.37,
                "campaign_threshold": {"value": 5},
            },
        )

        self.assertEqual(
            payload["outcome"]["status"],
            "decide_veer_eh1_candidate_only_vs_new_default_gate",
        )
        self.assertEqual(payload["outcome"]["selected_design"], "VeeR-EH1")
        self.assertEqual(payload["outcome"]["candidate_threshold_value"], 5)

    def test_reports_ready_to_accept_when_default_gate_is_ready(self) -> None:
        payload = self.module.build_status(
            c910_runtime_gate_payload={
                "selection": {"profile_name": "open_veer_fallback_family"},
                "outcome": {"status": "open_fallback_family_ready"},
            },
            veer_fallback_candidates_payload={
                "decision": {
                    "recommended_first_design": "VeeR-EH1",
                    "fallback_design": "VeeR-EH2",
                }
            },
            default_comparison_payload={
                "status": "ok",
                "comparison_ready": True,
                "winner": "hybrid",
                "speedup_ratio": 4.2,
                "campaign_threshold": {"value": 8},
            },
            threshold5_comparison_payload=None,
        )

        self.assertEqual(payload["outcome"]["status"], "ready_to_accept_veer_eh1_default_gate")
        self.assertEqual(payload["outcome"]["selected_design"], "VeeR-EH1")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gate_json = root / "gate.json"
            candidates_json = root / "candidates.json"
            default_json = root / "default.json"
            threshold5_json = root / "threshold5.json"
            json_out = root / "step.json"

            gate_json.write_text(
                json.dumps(
                    {
                        "selection": {"profile_name": "open_veer_fallback_family"},
                        "outcome": {"status": "open_fallback_family_ready"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            candidates_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "recommended_first_design": "VeeR-EH1",
                            "fallback_design": "VeeR-EH2",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            default_json.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "comparison_ready": False,
                        "winner": "unresolved",
                        "campaign_threshold": {"value": 8},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            threshold5_json.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "comparison_ready": True,
                        "winner": "hybrid",
                        "speedup_ratio": 3.37,
                        "campaign_threshold": {"value": 5},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_veer_first_surface_step.py",
                "--c910-runtime-gate-json",
                str(gate_json),
                "--veer-fallback-candidates-json",
                str(candidates_json),
                "--default-comparison-json",
                str(default_json),
                "--threshold5-comparison-json",
                str(threshold5_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_veer_first_surface_step")
            self.assertEqual(
                payload["outcome"]["status"],
                "decide_veer_eh1_candidate_only_vs_new_default_gate",
            )


if __name__ == "__main__":
    unittest.main()
