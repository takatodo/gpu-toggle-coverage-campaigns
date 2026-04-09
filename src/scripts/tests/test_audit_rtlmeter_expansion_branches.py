#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_rtlmeter_expansion_branches.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditRtlmeterExpansionBranchesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_rtlmeter_expansion_branches_test", MODULE_PATH)

    def test_main_emits_objective_oriented_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scoreboard = root / "scoreboard.json"
            feasibility = root / "feasibility.json"
            out = root / "branch_audit.json"

            scoreboard.write_text(
                json.dumps(
                    {
                        "summary": {
                            "tier_counts": {
                                "Tier S": 1,
                                "Tier R": 1,
                                "Tier B": 2,
                                "Tier T": 3,
                                "Tier M": 2,
                            }
                        },
                        "rows": [
                            {"slice_name": "tlul_fifo_sync", "tier": "Tier B"},
                            {"slice_name": "tlul_err", "tier": "Tier M"},
                            {"slice_name": "tlul_sink", "tier": "Tier M"},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            feasibility.write_text(
                json.dumps(
                    {
                        "recommendation": {
                            "if_promote_thinner_host_driven_top": {
                                "recommended_seed": "tlul_fifo_sync",
                            },
                            "if_keep_current_tb_timed_model": {
                                "blocked_candidates": ["tlul_err", "tlul_sink"],
                            },
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                rc = self.module.main(
                    [
                        "--scoreboard",
                        str(scoreboard),
                        "--feasibility",
                        str(feasibility),
                        "--json-out",
                        str(out),
                    ]
                )

            self.assertEqual(rc, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            objectives = payload["objectives"]
            self.assertEqual(
                objectives["maximize_ready_tier_count_quickly"]["recommended_branch"],
                "current_tb_timed_coroutine_model",
            )
            self.assertEqual(
                objectives["maximize_second_r_or_s_candidate"]["recommended_branch"],
                "thinner_host_driven_top",
            )
            self.assertEqual(
                objectives["maximize_second_r_or_s_candidate"]["seed_candidate"],
                "tlul_fifo_sync",
            )
            self.assertEqual(
                objectives["minimize_delivery_risk"]["recommended_branch"],
                "defer_second_target",
            )

    def test_current_model_branch_switches_to_pilot_actions_after_source_restore(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scoreboard = root / "scoreboard.json"
            feasibility = root / "feasibility.json"
            out = root / "branch_audit.json"

            scoreboard.write_text(
                json.dumps(
                    {
                        "summary": {
                            "tier_counts": {
                                "Tier S": 1,
                                "Tier R": 1,
                                "Tier B": 4,
                                "Tier T": 3,
                                "Tier M": 0,
                            }
                        },
                        "rows": [
                            {"slice_name": "tlul_fifo_sync", "tier": "Tier B"},
                            {"slice_name": "tlul_err", "tier": "Tier B"},
                            {"slice_name": "tlul_sink", "tier": "Tier B"},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            feasibility.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {"slice_name": "tlul_err", "current_blocker": "ready_for_next_experiment"},
                            {"slice_name": "tlul_sink", "current_blocker": "ready_for_next_experiment"},
                        ],
                        "recommendation": {
                            "if_promote_thinner_host_driven_top": {
                                "recommended_seed": "tlul_fifo_sync",
                            },
                            "if_keep_current_tb_timed_model": {
                                "blocked_candidates": [],
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                rc = self.module.main(
                    [
                        "--scoreboard",
                        str(scoreboard),
                        "--feasibility",
                        str(feasibility),
                        "--json-out",
                        str(out),
                    ]
                )

            self.assertEqual(rc, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            current_model = payload["objectives"]["maximize_ready_tier_count_quickly"]
            self.assertEqual(current_model["recommended_branch"], "current_tb_timed_coroutine_model")
            self.assertEqual(
                current_model["first_actions"],
                [
                    "run_initial_host_gpu_flow_for_tlul_err",
                    "run_initial_host_gpu_flow_for_tlul_sink",
                ],
            )
            self.assertEqual(current_model["expected_near_term_tier_moves"], [])
            self.assertIn("first pilot on tlul_err, tlul_sink", current_model["reason"])

    def test_current_model_branch_defers_when_no_quick_gain_remains(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scoreboard = root / "scoreboard.json"
            feasibility = root / "feasibility.json"
            out = root / "branch_audit.json"

            scoreboard.write_text(
                json.dumps(
                    {
                        "summary": {
                            "tier_counts": {
                                "Tier S": 1,
                                "Tier R": 1,
                                "Tier B": 4,
                                "Tier T": 3,
                                "Tier M": 0,
                            }
                        },
                        "rows": [
                            {"slice_name": "tlul_fifo_sync", "tier": "Tier B"},
                            {"slice_name": "tlul_err", "tier": "Tier B"},
                            {"slice_name": "tlul_sink", "tier": "Tier B"},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            feasibility.write_text(
                json.dumps(
                    {
                        "candidates": [
                            {"slice_name": "tlul_err", "current_blocker": "no_gpu_driven_deltas_under_current_model"},
                            {"slice_name": "tlul_sink", "current_blocker": "no_gpu_driven_deltas_under_current_model"},
                        ],
                        "recommendation": {
                            "if_promote_thinner_host_driven_top": {
                                "recommended_seed": "tlul_fifo_sync",
                            },
                            "if_keep_current_tb_timed_model": {
                                "blocked_candidates": [],
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                rc = self.module.main(
                    [
                        "--scoreboard",
                        str(scoreboard),
                        "--feasibility",
                        str(feasibility),
                        "--json-out",
                        str(out),
                    ]
                )

            self.assertEqual(rc, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            current_model = payload["objectives"]["maximize_ready_tier_count_quickly"]
            self.assertEqual(current_model["recommended_branch"], "defer_second_target")
            self.assertEqual(current_model["first_actions"], [])
            self.assertEqual(current_model["expected_near_term_tier_moves"], [])
            self.assertIn("no near-term raw tier-count gain", current_model["reason"])

    def test_second_r_or_s_objective_defers_once_seed_is_already_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            scoreboard = root / "scoreboard.json"
            feasibility = root / "feasibility.json"
            out = root / "branch_audit.json"

            scoreboard.write_text(
                json.dumps(
                    {
                        "summary": {
                            "tier_counts": {
                                "Tier S": 1,
                                "Tier R": 2,
                                "Tier B": 3,
                                "Tier T": 3,
                                "Tier M": 0,
                            }
                        },
                        "rows": [
                            {"slice_name": "tlul_fifo_sync", "tier": "Tier R"},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            feasibility.write_text(
                json.dumps(
                    {
                        "recommendation": {
                            "if_promote_thinner_host_driven_top": {
                                "recommended_seed": "tlul_fifo_sync",
                            },
                            "if_keep_current_tb_timed_model": {
                                "blocked_candidates": [],
                            },
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                rc = self.module.main(
                    [
                        "--scoreboard",
                        str(scoreboard),
                        "--feasibility",
                        str(feasibility),
                        "--json-out",
                        str(out),
                    ]
                )

            self.assertEqual(rc, 0)
            payload = json.loads(out.read_text(encoding="utf-8"))
            second_target = payload["objectives"]["maximize_second_r_or_s_candidate"]
            self.assertEqual(second_target["recommended_branch"], "defer_second_target")
            self.assertEqual(second_target["first_actions"], [])
            self.assertTrue(second_target["objective_already_met"])
            self.assertIn("already Tier R", second_target["reason"])


if __name__ == "__main__":
    unittest.main()
