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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_non_opentitan_entry.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignNonOpentitanEntryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_non_opentitan_entry_test", MODULE_PATH)

    def test_recommends_xuantie_family_pilot_when_family_runner_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runners_dir = root / "runners"
            runners_dir.mkdir(parents=True)
            (runners_dir / "run_xuantie_family_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            (runners_dir / "run_xuantie_c906_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            (runners_dir / "run_xuantie_c910_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            (runners_dir / "run_veer_family_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")

            payload = self.module.build_non_opentitan_entry(
                post_checkpoint_axes={
                    "decision": {
                        "recommended_next_axis": "broaden_non_opentitan_family",
                        "recommended_family": "XuanTie",
                    },
                    "checkpoint_summary": {"active_surface_count": 9},
                    "inventory_rows": [
                        {
                            "repo_family": "XuanTie",
                            "design_count": 4,
                            "is_active_repo_family": False,
                            "is_opentitan": False,
                        },
                        {
                            "repo_family": "VeeR",
                            "design_count": 3,
                            "is_active_repo_family": False,
                            "is_opentitan": False,
                        },
                    ],
                },
                runners_dir=runners_dir,
            )

            self.assertEqual(payload["decision"]["recommended_family"], "XuanTie")
            self.assertEqual(payload["decision"]["recommended_entry_mode"], "family_pilot")
            self.assertEqual(payload["rows"][0]["recommended_entry_mode"], "family_pilot")

    def test_recommends_single_surface_for_single_runner_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            runners_dir = root / "runners"
            runners_dir.mkdir(parents=True)
            (runners_dir / "run_openpiton_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")

            payload = self.module.build_non_opentitan_entry(
                post_checkpoint_axes={
                    "decision": {
                        "recommended_next_axis": "broaden_non_opentitan_family",
                        "recommended_family": "OpenPiton",
                    },
                    "checkpoint_summary": {"active_surface_count": 9},
                    "inventory_rows": [
                        {
                            "repo_family": "OpenPiton",
                            "design_count": 1,
                            "is_active_repo_family": False,
                            "is_opentitan": False,
                        }
                    ],
                },
                runners_dir=runners_dir,
            )

            self.assertEqual(payload["decision"]["recommended_entry_mode"], "single_surface")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            post_axes_path = root / "post_axes.json"
            runners_dir = root / "runners"
            json_out = root / "entry.json"
            runners_dir.mkdir(parents=True)
            (runners_dir / "run_xuantie_family_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")

            post_axes_path.write_text(
                json.dumps(
                    {
                        "decision": {
                            "recommended_next_axis": "broaden_non_opentitan_family",
                            "recommended_family": "XuanTie",
                        },
                        "checkpoint_summary": {"active_surface_count": 9},
                        "inventory_rows": [
                            {
                                "repo_family": "XuanTie",
                                "design_count": 4,
                                "is_active_repo_family": False,
                                "is_opentitan": False,
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_non_opentitan_entry.py",
                "--post-checkpoint-axes-json",
                str(post_axes_path),
                "--runners-dir",
                str(runners_dir),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_non_opentitan_entry")
            self.assertEqual(payload["decision"]["recommended_family"], "XuanTie")


if __name__ == "__main__":
    unittest.main()
