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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_openpiton_first_surface_step.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignOpenPitonFirstSurfaceStepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_openpiton_first_surface_step_test", MODULE_PATH)

    def test_reports_ready_to_accept_when_default_gate_is_hybrid_win(self) -> None:
        payload = self.module.build_status(
            xiangshan_status_payload={
                "upstream_axes": {
                    "recommended_family": "XiangShan",
                    "fallback_family": "OpenPiton",
                },
                "outcome": {
                    "status": "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family",
                },
            },
            comparison_payload={
                "status": "ok",
                "comparison_ready": True,
                "winner": "hybrid",
                "speedup_ratio": 1.57,
                "campaign_threshold": {"value": 8},
            },
        )

        self.assertEqual(payload["outcome"]["status"], "ready_to_accept_openpiton_default_gate")
        self.assertEqual(payload["outcome"]["threshold_value"], 8)

    def test_reports_baseline_win_when_default_line_loses(self) -> None:
        payload = self.module.build_status(
            xiangshan_status_payload={
                "upstream_axes": {
                    "recommended_family": "XiangShan",
                    "fallback_family": "OpenPiton",
                },
                "outcome": {
                    "status": "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family",
                },
            },
            comparison_payload={
                "status": "ok",
                "comparison_ready": True,
                "winner": "baseline",
                "speedup_ratio": 0.48,
                "campaign_threshold": {"value": 8},
            },
        )

        self.assertEqual(payload["outcome"]["status"], "openpiton_default_gate_baseline_win")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xiangshan_json = root / "xiangshan.json"
            comparison_json = root / "comparison.json"
            json_out = root / "step.json"

            xiangshan_json.write_text(
                json.dumps(
                    {
                        "upstream_axes": {
                            "recommended_family": "XiangShan",
                            "fallback_family": "OpenPiton",
                        },
                        "outcome": {
                            "status": "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            comparison_json.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "comparison_ready": True,
                        "winner": "hybrid",
                        "speedup_ratio": 1.57,
                        "campaign_threshold": {"value": 8},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_openpiton_first_surface_step.py",
                "--xiangshan-status-json",
                str(xiangshan_json),
                "--comparison-json",
                str(comparison_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_openpiton_first_surface_step")
            self.assertEqual(payload["outcome"]["status"], "ready_to_accept_openpiton_default_gate")


if __name__ == "__main__":
    unittest.main()
