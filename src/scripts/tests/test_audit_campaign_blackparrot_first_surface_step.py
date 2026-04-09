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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_blackparrot_first_surface_step.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignBlackParrotFirstSurfaceStepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_blackparrot_first_surface_step_test", MODULE_PATH)

    def test_reports_candidate_only_baseline_win(self) -> None:
        payload = self.module.build_status(
            post_openpiton_axes_payload={
                "decision": {
                    "status": "decide_open_next_family_after_openpiton_acceptance",
                    "recommended_family": "BlackParrot",
                    "fallback_family": "XiangShan",
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
                "winner": "baseline",
                "speedup_ratio": 0.19,
                "campaign_threshold": {"value": 5},
            },
        )

        self.assertEqual(payload["outcome"]["status"], "blackparrot_candidate_only_baseline_win")
        self.assertEqual(payload["outcome"]["fallback_family"], "XiangShan")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            axes_json = root / "axes.json"
            default_json = root / "default.json"
            threshold_json = root / "threshold5.json"
            json_out = root / "step.json"

            axes_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "status": "decide_open_next_family_after_openpiton_acceptance",
                            "recommended_family": "BlackParrot",
                            "fallback_family": "XiangShan",
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
            threshold_json.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "comparison_ready": True,
                        "winner": "baseline",
                        "speedup_ratio": 0.19,
                        "campaign_threshold": {"value": 5},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_blackparrot_first_surface_step.py",
                "--post-openpiton-axes-json",
                str(axes_json),
                "--default-comparison-json",
                str(default_json),
                "--threshold5-comparison-json",
                str(threshold_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_blackparrot_first_surface_step")
            self.assertEqual(payload["outcome"]["status"], "blackparrot_candidate_only_baseline_win")


if __name__ == "__main__":
    unittest.main()
