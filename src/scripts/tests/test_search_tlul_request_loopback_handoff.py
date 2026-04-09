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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "search_tlul_request_loopback_handoff.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_validation_json(
    path: Path,
    *,
    host_done_o: int,
    host_progress_cycle_count_o: int,
    final_done_o: int,
    final_progress_cycle_count_o: int,
    rsp_queue_overflow_o: int,
    promotion_gate_passed: bool,
    promotion_gate_blocked_by: list[str],
    handoff_gate_passed: bool,
    handoff_gate_blocked_by: list[str],
    promotion_assessment_decision: str,
) -> None:
    path.write_text(
        json.dumps(
            {
                "host_probe": {
                    "done_o": host_done_o,
                    "progress_cycle_count_o": host_progress_cycle_count_o,
                },
                "outputs": {
                    "done_o": final_done_o,
                    "progress_cycle_count_o": final_progress_cycle_count_o,
                    "rsp_queue_overflow_o": rsp_queue_overflow_o,
                },
                "promotion_gate": {
                    "passed": promotion_gate_passed,
                    "blocked_by": promotion_gate_blocked_by,
                },
                "handoff_gate": {
                    "passed": handoff_gate_passed,
                    "blocked_by": handoff_gate_blocked_by,
                },
                "promotion_assessment": {
                    "decision": promotion_assessment_decision,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


class SearchTlulRequestLoopbackHandoffTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("search_tlul_request_loopback_handoff_test", MODULE_PATH)

    def test_search_assessment_reports_handoff_case_when_present(self) -> None:
        assessment = self.module._search_assessment(
            [
                {
                    "handoff_gate_passed": True,
                    "promotion_gate_passed": True,
                    "host_done_o": 0,
                    "final_done_o": 1,
                }
            ]
        )

        self.assertEqual(assessment["decision"], "handoff_case_found")

    def test_search_assessment_reports_completion_without_handoff(self) -> None:
        assessment = self.module._search_assessment(
            [
                {
                    "handoff_gate_passed": False,
                    "promotion_gate_passed": False,
                    "host_done_o": 0,
                    "final_done_o": 1,
                }
            ]
        )

        self.assertEqual(assessment["decision"], "completion_without_handoff_gate")

    def test_main_writes_summary_for_terminal_state_only_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            output_dir = root / "handoff_search"
            json_out = root / "summary.json"
            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                validation_json = Path(argv[argv.index("--json-out") + 1])
                req_valid_pct = int(argv[argv.index("--host-set") + 1].split("=", 1)[1])
                host_post_reset_cycles = int(argv[argv.index("--host-post-reset-cycles") + 1])
                steps = int(argv[argv.index("--steps") + 1])
                self.assertEqual(host_post_reset_cycles, 96)
                self.assertEqual(steps, 56)

                if req_valid_pct == 92:
                    _write_validation_json(
                        validation_json,
                        host_done_o=1,
                        host_progress_cycle_count_o=120,
                        final_done_o=1,
                        final_progress_cycle_count_o=120,
                        rsp_queue_overflow_o=0,
                        promotion_gate_passed=True,
                        promotion_gate_blocked_by=[],
                        handoff_gate_passed=False,
                        handoff_gate_blocked_by=[
                            "host_probe_not_already_done",
                            "gpu_replay_made_progress",
                        ],
                        promotion_assessment_decision="promotion_gate_only_not_handoff_proven",
                    )
                else:
                    _write_validation_json(
                        validation_json,
                        host_done_o=0,
                        host_progress_cycle_count_o=5,
                        final_done_o=0,
                        final_progress_cycle_count_o=5,
                        rsp_queue_overflow_o=0,
                        promotion_gate_passed=False,
                        promotion_gate_blocked_by=["done_o"],
                        handoff_gate_passed=False,
                        handoff_gate_blocked_by=["gpu_replay_made_progress"],
                        promotion_assessment_decision="freeze_at_phase_b_reference_design",
                    )
                return mock.Mock(returncode=0, stdout="", stderr="")

            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                rc = self.module.main(
                    [
                        "--mdir",
                        str(mdir),
                        "--req-valid-values",
                        "80,92",
                        "--host-post-reset-values",
                        "96",
                        "--steps-values",
                        "56",
                        "--output-dir",
                        str(output_dir),
                        "--json-out",
                        str(json_out),
                    ]
                )

            self.assertEqual(rc, 0)
            summary = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(summary["total_cases"], 2)
            self.assertEqual(summary["completed_cases"], 2)
            self.assertEqual(summary["failed_cases"], [])
            self.assertEqual(summary["search_assessment"]["decision"], "terminal_state_only_candidates_found")
            self.assertEqual(len(summary["handoff_passes"]), 0)
            self.assertEqual(len(summary["promotion_only"]), 1)
            self.assertEqual(len(summary["host_incomplete_then_final_done"]), 0)
            self.assertEqual(
                summary["promotion_only"][0]["promotion_assessment_decision"],
                "promotion_gate_only_not_handoff_proven",
            )
            self.assertEqual(summary["cases"][0]["req_valid_pct"], 80)
            self.assertEqual(summary["cases"][1]["req_valid_pct"], 92)
            self.assertEqual(len(calls), 2)
            self.assertIn("--host-post-reset-cycles", calls[0])
            self.assertIn("--host-set", calls[0])

    def test_main_records_failed_cases_and_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "summary.json"

            def _fake_run(cmd: list[str], **kwargs):
                return mock.Mock(returncode=2, stdout="runner failed\n", stderr="bad config\n")

            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                rc = self.module.main(
                    [
                        "--mdir",
                        str(mdir),
                        "--req-valid-values",
                        "92",
                        "--host-post-reset-values",
                        "120",
                        "--steps-values",
                        "56",
                        "--json-out",
                        str(json_out),
                    ]
                )

            self.assertEqual(rc, 1)
            summary = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(summary["completed_cases"], 0)
            self.assertEqual(len(summary["failed_cases"]), 1)
            self.assertEqual(summary["failed_cases"][0]["runner_returncode"], 2)
            self.assertEqual(summary["search_assessment"]["decision"], "no_handoff_case_found_in_search_space")


if __name__ == "__main__":
    unittest.main()
