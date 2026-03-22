#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
BASELINE_MODULE_PATH = SCRIPT_DIR / "run_opentitan_tlul_slice_gpu_baseline.py"
PRODUCTION_DEFAULTS_MODULE_PATH = SCRIPT_DIR / "freeze_opentitan_tlul_slice_production_defaults.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class CirctBackendPolicyFlowTest(unittest.TestCase):
    def test_edn_auto_backend_uses_frozen_single_step_policy(self) -> None:
        if not BASELINE_MODULE_PATH.is_file():
            self.skipTest(f"Module not available: {BASELINE_MODULE_PATH.name}")
        module = _load_module("slice_baseline_policy", BASELINE_MODULE_PATH)
        template = {
            "launch_backend_policy": {
                "single_step": "source",
                "multi_step": "source",
                "sweep": "source",
                "campaign": "source",
            }
        }
        ns = type("Ns", (), {"launch_backend": "auto", "phase": "auto"})()
        self.assertEqual(module._effective_launch_backend(template, ns, 1), "source")
        self.assertEqual(module._effective_launch_backend(template, ns, 8), "source")

    def test_production_defaults_preserve_canonical_execution_profile_keys(self) -> None:
        if not PRODUCTION_DEFAULTS_MODULE_PATH.is_file():
            self.skipTest(f"Module not available: {PRODUCTION_DEFAULTS_MODULE_PATH.name}")
        module = _load_module("production_defaults_policy", PRODUCTION_DEFAULTS_MODULE_PATH)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            profiles_json = root / "profiles.json"
            convergence_json = root / "convergence.json"
            campaign_json = root / "campaign.json"
            out_json = root / "defaults.json"
            out_md = root / "defaults.md"

            profiles_json.write_text(
                json.dumps(
                    {
                        "slices": [
                            {
                                "slice_name": "edn_main_sm",
                                "launch_backend_policy": {
                                    "single_step": "source",
                                    "multi_step": "source",
                                    "sweep": "source",
                                    "campaign": "source",
                                },
                                "profiles": {
                                    "single_step": {
                                        "status": "frozen",
                                        "scenario": "single_step_small",
                                        "nstates": 16,
                                        "gpu_reps": 5,
                                    },
                                    "multi_step": {
                                        "status": "frozen",
                                        "scenario": "multi_step_medium",
                                        "nstates": 32,
                                        "gpu_reps": 5,
                                    },
                                },
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            convergence_json.write_text(
                json.dumps(
                    {
                        "slices": [
                            {
                                "slice_name": "edn_main_sm",
                                "recommended_campaign_candidate_count": 180,
                                "recommended_campaign_shard_count": 2,
                                "recommended_stop": True,
                                "recommended_stop_at_shard": 3,
                                "plateau_after_shard": 1,
                                "recommended_convergence_thresholds": {"min_new_regions_per_1k": 0.05},
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            campaign_json.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "slice_name": "edn_main_sm",
                                "status": "completed",
                                "best_case_hit": 7,
                                "best_case_gpu_cps": 2600.0,
                                "hit_per_wall_s": 0.4,
                                "wall_clock_s": 120.0,
                                "summary_json": "/tmp/edn-summary.json",
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            rc = module.main(
                [
                    "--profiles-json",
                    str(profiles_json),
                    "--convergence-json",
                    str(convergence_json),
                    "--campaign-efficiency-json",
                    str(campaign_json),
                    "--json-out",
                    str(out_json),
                    "--md-out",
                    str(out_md),
                ]
            )
            self.assertEqual(rc, 0)
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            row = payload["rows"][0]
            self.assertEqual(row["single_step_backend"], "source")
            self.assertEqual(row["single_step_profile"]["scenario"], "single_step_small")
            self.assertEqual(row["single_step_profile"]["nstates"], 16)
            self.assertEqual(row["multi_step_profile"]["scenario"], "multi_step_medium")
            self.assertEqual(row["multi_step_profile"]["nstates"], 32)


if __name__ == "__main__":
    unittest.main()
