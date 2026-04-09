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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_post_blackparrot_axes.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignPostBlackParrotAxesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_post_blackparrot_axes_test", MODULE_PATH)

    def test_prefers_vortex_and_uses_xiangshan_as_blocked_fallback(self) -> None:
        payload = self.module.build_status(
            blackparrot_step_payload={
                "outcome": {
                    "status": "blackparrot_candidate_only_baseline_win",
                    "next_action": "open_the_next_family_after_blackparrot_baseline_loss",
                    "fallback_family": "XiangShan",
                }
            }
        )

        self.assertEqual(
            payload["decision"]["status"],
            "decide_open_next_family_after_blackparrot_baseline_loss",
        )
        self.assertEqual(payload["decision"]["recommended_family"], "Vortex")
        self.assertEqual(payload["decision"]["fallback_family"], "XiangShan")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            step_json = root / "step.json"
            json_out = root / "axes.json"
            step_json.write_text(
                json.dumps(
                    {
                        "outcome": {
                            "status": "blackparrot_candidate_only_baseline_win",
                            "next_action": "open_the_next_family_after_blackparrot_baseline_loss",
                            "fallback_family": "XiangShan",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_post_blackparrot_axes.py",
                "--blackparrot-step-json",
                str(step_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_post_blackparrot_axes")
            self.assertEqual(payload["decision"]["recommended_family"], "Vortex")


if __name__ == "__main__":
    unittest.main()
