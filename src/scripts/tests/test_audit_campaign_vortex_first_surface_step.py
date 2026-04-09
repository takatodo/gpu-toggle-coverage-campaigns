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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_vortex_first_surface_step.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignVortexFirstSurfaceStepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_vortex_first_surface_step_test", MODULE_PATH)

    def test_reports_candidate_only_decision_when_threshold4_line_is_ready(self) -> None:
        payload = self.module.build_status(
            vortex_status_payload={
                "outcome": {
                    "status": "ready_to_finish_vortex_first_trio",
                    "next_action": "finish_vortex_stock_hybrid_validation_and_compare_gate_policy",
                }
            },
            default_comparison_payload={
                "status": "ok",
                "comparison_ready": False,
                "winner": "unresolved",
                "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
            },
            threshold4_comparison_payload={
                "status": "ok",
                "comparison_ready": True,
                "winner": "hybrid",
                "speedup_ratio": 1.071,
                "campaign_threshold": {"kind": "toggle_bits_hit", "value": 4},
            },
        )

        self.assertEqual(
            payload["outcome"]["status"],
            "decide_vortex_candidate_only_vs_new_default_gate",
        )
        self.assertEqual(payload["outcome"]["candidate_threshold_value"], 4)
        self.assertEqual(payload["selected_design"]["threshold4_candidate"]["winner"], "hybrid")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            status_json = root / "status.json"
            default_json = root / "default.json"
            threshold4_json = root / "threshold4.json"
            json_out = root / "step.json"

            status_json.write_text(
                json.dumps({"outcome": {"status": "ready_to_finish_vortex_first_trio"}}) + "\n",
                encoding="utf-8",
            )
            default_json.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "comparison_ready": False,
                        "winner": "unresolved",
                        "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            threshold4_json.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "comparison_ready": True,
                        "winner": "hybrid",
                        "speedup_ratio": 1.071,
                        "campaign_threshold": {"kind": "toggle_bits_hit", "value": 4},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_vortex_first_surface_step.py",
                "--status-json",
                str(status_json),
                "--default-comparison-json",
                str(default_json),
                "--threshold4-comparison-json",
                str(threshold4_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_vortex_first_surface_step")
            self.assertEqual(
                payload["outcome"]["status"],
                "decide_vortex_candidate_only_vs_new_default_gate",
            )


if __name__ == "__main__":
    unittest.main()
