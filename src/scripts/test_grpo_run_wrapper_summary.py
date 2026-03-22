#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER_PATH = SCRIPT_DIR.parent / "grpo/run_gpro_coverage_improvement.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class WrapperSummaryTest(unittest.TestCase):
    def setUp(self) -> None:
        if not RUNNER_PATH.is_file():
            self.skipTest(f"Module not available: {RUNNER_PATH.name}")
        self.runner = _load_module("grpo_run_wrapper_summary_test", RUNNER_PATH)

    def test_resolve_wrapper_json_out_avoids_overwriting_runner_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            resolved = self.runner._resolve_wrapper_json_out(
                work_dir=work_dir,
                requested=str(work_dir / "summary.json"),
            )
            self.assertEqual(resolved, work_dir / "gpro_run.json")

    def test_build_wrapper_payload_hoists_runner_and_merge_view_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            (work_dir / "summary.json").write_text(
                json.dumps(
                    {
                        "slice_name": "pwrmgr_fsm",
                        "execution": {"wall_clock_s": 6.5, "launch_count": 10},
                        "best_case": {
                            "real_subset_points_hit": 18,
                            "real_subset_points_total": 18,
                            "active_region_count": 5,
                            "dead_region_count": 0,
                            "target_region_activated": 1,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (work_dir / "summary.campaign_merge_view.json").write_text(
                json.dumps(
                    {
                        "total_candidate_space": 1280,
                        "evaluated_case_count": 1280,
                        "active_region_union": ["a", "b", "c", "d", "e"],
                        "cases": [
                            {
                                "target_region": "rom_check_and_fetch_enable_path",
                                "real_subset_points_hit": 18,
                                "active_region_count": 5,
                                "dead_region_count": 0,
                                "target_region_activated": 1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            ns = types.SimpleNamespace(
                slice="pwrmgr_fsm",
                phase="campaign",
                execution_engine="gpu",
                launch_backend="source",
                search_scope_policy="off",
                static_prior_mode="off",
            )
            payload = self.runner._build_wrapper_payload(
                ns=ns,
                defaults={"profile_family": "mixed"},
                static_feature_adjustments={"applied": False},
                grpo_defaults={},
                work_dir=work_dir,
                cmd=["python3", "dummy.py"],
            )
            self.assertEqual(payload["summary_json"], str(work_dir / "summary.json"))
            self.assertEqual(payload["campaign_merge_view_json"], str(work_dir / "summary.campaign_merge_view.json"))
            self.assertEqual(payload["total_candidate_space"], 1280)
            self.assertEqual(payload["evaluated_case_count"], 1280)
            self.assertEqual(payload["execution"]["wall_clock_s"], 6.5)
            self.assertEqual(payload["best_case"]["real_subset_points_hit"], 18)
            self.assertEqual(len(payload["cases"]), 1)


if __name__ == "__main__":
    unittest.main()
