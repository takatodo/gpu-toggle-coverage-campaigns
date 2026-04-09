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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xiangshan_first_surface_step.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXiangshanFirstSurfaceStepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xiangshan_first_surface_step_test", MODULE_PATH)

    def test_blocks_when_runtime_is_not_ready(self) -> None:
        payload = self.module.build_status(
            deeper_status_payload={
                "decision": {
                    "status": "ready_for_xiangshan_executable_link_population_debug",
                    "recommended_next_tactic": "deeper_xiangshan_executable_link_population_debug",
                }
            },
            default_comparison_payload=None,
            threshold2_comparison_payload=None,
        )

        self.assertEqual(payload["outcome"]["status"], "blocked_xiangshan_runtime_not_ready")

    def test_reports_candidate_only_vs_new_default_gate(self) -> None:
        payload = self.module.build_status(
            deeper_status_payload={
                "decision": {
                    "status": "ready_to_finish_xiangshan_first_trio",
                    "recommended_next_tactic": "finish_xiangshan_stock_hybrid_validation_and_compare_gate_policy",
                    "fallback_tactic": "deeper_vortex_tls_lowering_debug",
                }
            },
            default_comparison_payload={
                "status": "ok",
                "comparison_ready": False,
                "winner": "unresolved",
                "campaign_threshold": {"value": 8},
            },
            threshold2_comparison_payload={
                "status": "ok",
                "comparison_ready": True,
                "winner": "hybrid",
                "speedup_ratio": 3.12,
                "campaign_threshold": {"value": 2},
            },
        )

        self.assertEqual(
            payload["outcome"]["status"],
            "decide_xiangshan_candidate_only_vs_new_default_gate",
        )
        self.assertEqual(payload["outcome"]["candidate_threshold_value"], 2)

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            deeper_json = root / "deeper.json"
            default_json = root / "default.json"
            threshold2_json = root / "threshold2.json"
            json_out = root / "step.json"

            deeper_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "status": "ready_to_finish_xiangshan_first_trio",
                            "recommended_next_tactic": "finish_xiangshan_stock_hybrid_validation_and_compare_gate_policy",
                            "fallback_tactic": "deeper_vortex_tls_lowering_debug",
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
            threshold2_json.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "comparison_ready": True,
                        "winner": "hybrid",
                        "speedup_ratio": 3.12,
                        "campaign_threshold": {"value": 2},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_xiangshan_first_surface_step.py",
                "--deeper-status-json",
                str(deeper_json),
                "--default-comparison-json",
                str(default_json),
                "--threshold2-comparison-json",
                str(threshold2_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_xiangshan_first_surface_step")
            self.assertEqual(
                payload["outcome"]["status"],
                "decide_xiangshan_candidate_only_vs_new_default_gate",
            )


if __name__ == "__main__":
    unittest.main()
