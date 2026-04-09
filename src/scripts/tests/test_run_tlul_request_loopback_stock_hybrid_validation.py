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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_tlul_request_loopback_stock_hybrid_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunTlulRequestLoopbackStockHybridValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_tlul_request_loopback_stock_hybrid_validation_test", MODULE_PATH)

    def test_runner_writes_reference_design_validation_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "validation.json"
            flow_json = root / "flow.json"
            host_report = root / "host.json"
            host_state = root / "host.bin"
            final_state = root / "final.bin"

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                flow_json.write_text(
                    json.dumps(
                        {
                            "target": "tlul_request_loopback",
                            "clock_ownership": "tb_timed_coroutine",
                            "support_tier": "phase_b_reference_design",
                            "mdir": str(mdir),
                            "nstates": 32,
                            "steps": 56,
                            "block_size": 256,
                            "host_report": str(host_report),
                            "host_state": str(host_state),
                            "final_state": str(final_state),
                            "storage_size": 896,
                            "done_o": 1,
                            "cfg_signature_o": 0x12345678,
                            "rsp_queue_overflow_o": 0,
                            "progress_cycle_count_o": 56,
                            "progress_signature_o": 0xABCDEF01,
                            "toggle_bitmap_word0_o": 11,
                            "toggle_bitmap_word1_o": 22,
                            "toggle_bitmap_word2_o": 33,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                host_report.write_text(
                    json.dumps(
                        {
                            "constructor_ok": True,
                            "clock_ownership": "tb_timed_coroutine",
                            "done_o": 0,
                            "progress_cycle_count_o": 4,
                            "progress_signature_o": 0,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return mock.Mock(
                    returncode=0,
                    stdout="\n".join(
                        [
                            "device 0: Demo GPU",
                            "ok: steps=56 kernels_per_step=5 patches_per_step=0 grid=1 block=256 nstates=32 storage=896 B",
                            "gpu_kernel_time_ms: total=3.500000  per_launch=0.062500  (CUDA events, kernels only; HtoD patches before launch excluded)",
                            "gpu_kernel_time: per_state=1.953 us  (per_launch / nstates)",
                            "wall_time_ms: 4.000  (host; one GPU sync unless RUN_VL_HYBRID_SYNC_EACH_STEP=1)",
                            '{"target":"tlul_request_loopback"}',
                        ]
                    )
                    + "\n",
                    stderr="",
                )

            argv = [
                "run_tlul_request_loopback_stock_hybrid_validation.py",
                "--mdir",
                str(mdir),
                "--nstates",
                "32",
                "--steps",
                "56",
                "--campaign-threshold-bits",
                "5",
                "--host-post-reset-cycles",
                "120",
                "--host-set",
                "cfg_req_valid_pct_i=92",
                "--json-out",
                str(json_out),
                "--flow-json-out",
                str(flow_json),
                "--host-report-out",
                str(host_report),
                "--host-state-out",
                str(host_state),
                "--final-state-out",
                str(final_state),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    rc = self.module.main(sys.argv[1:])

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["target"], "tlul_request_loopback")
            self.assertEqual(payload["support_tier"], "phase_b_reference_design")
            self.assertEqual(payload["acceptance_gate"], "phase_b_endpoint")
            self.assertEqual(payload["inputs"]["host_post_reset_cycles"], 120)
            self.assertEqual(payload["inputs"]["host_overrides"], ["cfg_req_valid_pct_i=92"])
            self.assertEqual(payload["outputs"]["done_o"], 1)
            self.assertEqual(payload["outputs"]["cfg_signature_o"], 0x12345678)
            self.assertEqual(payload["outputs"]["rsp_queue_overflow_o"], 0)
            self.assertEqual(payload["outputs"]["progress_cycle_count_o"], 56)
            self.assertEqual(payload["outputs"]["progress_signature_o"], 0xABCDEF01)
            self.assertEqual(payload["toggle_coverage"]["bits_hit"], 8)
            self.assertEqual(
                payload["campaign_threshold"],
                {
                    "kind": "toggle_bits_hit",
                    "value": 5,
                    "aggregation": "bitwise_or_across_trials",
                },
            )
            self.assertEqual(payload["campaign_measurement"]["bits_hit"], 8)
            self.assertTrue(payload["campaign_measurement"]["threshold_satisfied"])
            self.assertEqual(payload["campaign_measurement"]["wall_time_ms"], 4.0)
            self.assertEqual(payload["campaign_measurement"]["steps_executed"], 56)
            self.assertTrue(payload["promotion_gate"]["passed"])
            self.assertEqual(payload["promotion_gate"]["blocked_by"], [])
            self.assertEqual(payload["promotion_gate"]["target_support_tier"], "first_supported_target")
            self.assertTrue(payload["promotion_gate"]["observed"]["progress_advanced_since_host_probe"])
            self.assertTrue(payload["handoff_gate"]["passed"])
            self.assertEqual(payload["handoff_gate"]["blocked_by"], [])
            self.assertEqual(
                payload["promotion_assessment"]["decision"],
                "eligible_for_first_supported_target",
            )
            self.assertIsNone(payload["promotion_assessment"]["next_requirement"])
            self.assertEqual(
                payload["artifacts"]["classifier_report"],
                str((mdir / "vl_classifier_report.json").resolve()),
            )
            self.assertEqual(payload["performance"]["device_name"], "Demo GPU")
            self.assertEqual(payload["performance"]["runner_shape"]["kernels_per_step"], 5)
            self.assertEqual(payload["performance"]["throughput"]["kernel_launches"], 280)

    def test_runner_reports_promotion_blocker_when_done_stays_low(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "validation.json"
            flow_json = root / "flow.json"
            host_report = root / "host.json"
            host_state = root / "host.bin"
            final_state = root / "final.bin"

            def _fake_run(cmd: list[str], **kwargs):
                flow_json.write_text(
                    json.dumps(
                        {
                            "target": "tlul_request_loopback",
                            "clock_ownership": "tb_timed_coroutine",
                            "support_tier": "phase_b_reference_design",
                            "mdir": str(mdir),
                            "nstates": 32,
                            "steps": 56,
                            "block_size": 256,
                            "host_report": str(host_report),
                            "host_state": str(host_state),
                            "final_state": str(final_state),
                            "storage_size": 896,
                            "done_o": 0,
                            "cfg_signature_o": 0x12345678,
                            "rsp_queue_overflow_o": 0,
                            "progress_cycle_count_o": 5,
                            "progress_signature_o": 0,
                            "toggle_bitmap_word0_o": 0,
                            "toggle_bitmap_word1_o": 0,
                            "toggle_bitmap_word2_o": 1,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                host_report.write_text(
                    json.dumps(
                        {
                            "constructor_ok": True,
                            "clock_ownership": "tb_timed_coroutine",
                            "done_o": 0,
                            "progress_cycle_count_o": 5,
                            "progress_signature_o": 0,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return mock.Mock(
                    returncode=0,
                    stdout="device 0: Demo GPU\n"
                    "ok: steps=56 kernels_per_step=5 patches_per_step=0 grid=1 block=256 nstates=32 storage=896 B\n",
                    stderr="",
                )

            argv = [
                "run_tlul_request_loopback_stock_hybrid_validation.py",
                "--mdir",
                str(mdir),
                "--campaign-threshold-bits",
                "1",
                "--host-post-reset-cycles",
                "120",
                "--host-set",
                "cfg_req_valid_pct_i=92",
                "--json-out",
                str(json_out),
                "--flow-json-out",
                str(flow_json),
                "--host-report-out",
                str(host_report),
                "--host-state-out",
                str(host_state),
                "--final-state-out",
                str(final_state),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    rc = self.module.main(sys.argv[1:])

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertFalse(payload["promotion_gate"]["passed"])
            self.assertEqual(payload["promotion_gate"]["blocked_by"], ["done_o"])
            self.assertEqual(payload["campaign_measurement"]["bits_hit"], 1)
            self.assertTrue(payload["campaign_measurement"]["threshold_satisfied"])
            self.assertEqual(payload["inputs"]["host_post_reset_cycles"], 120)
            self.assertEqual(payload["inputs"]["host_overrides"], ["cfg_req_valid_pct_i=92"])
            self.assertFalse(payload["handoff_gate"]["passed"])
            self.assertEqual(payload["handoff_gate"]["blocked_by"], ["gpu_replay_made_progress"])
            self.assertFalse(payload["promotion_gate"]["alternative_progress_contract_defined"])
            self.assertFalse(payload["promotion_gate"]["observed"]["progress_advanced_since_host_probe"])
            self.assertEqual(
                payload["promotion_assessment"]["decision"],
                "freeze_at_phase_b_reference_design",
            )
            self.assertEqual(
                payload["promotion_assessment"]["next_requirement"],
                "change_clock_or_step_ownership_or_define_alternative_progress_contract",
            )
            self.assertTrue(
                any(
                    "progress_cycle_count_o did not advance beyond the host-probe baseline" in caveat
                    for caveat in payload["caveats"]
                )
            )

    def test_runner_marks_host_completed_candidate_as_handoff_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "validation.json"
            flow_json = root / "flow.json"
            host_report = root / "host.json"
            host_state = root / "host.bin"
            final_state = root / "final.bin"

            def _fake_run(cmd: list[str], **kwargs):
                flow_json.write_text(
                    json.dumps(
                        {
                            "target": "tlul_request_loopback",
                            "clock_ownership": "tb_timed_coroutine",
                            "support_tier": "phase_b_reference_design",
                            "mdir": str(mdir),
                            "nstates": 32,
                            "steps": 56,
                            "block_size": 256,
                            "host_report": str(host_report),
                            "host_state": str(host_state),
                            "final_state": str(final_state),
                            "storage_size": 896,
                            "done_o": 1,
                            "cfg_signature_o": 0x12345678,
                            "rsp_queue_overflow_o": 0,
                            "progress_cycle_count_o": 123,
                            "progress_signature_o": 0x140F0E03,
                            "toggle_bitmap_word0_o": 0x3FFFF,
                            "toggle_bitmap_word1_o": 0x140F0E03,
                            "toggle_bitmap_word2_o": 0x2000C,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                host_report.write_text(
                    json.dumps(
                        {
                            "constructor_ok": True,
                            "clock_ownership": "tb_timed_coroutine",
                            "done_o": 1,
                            "progress_cycle_count_o": 123,
                            "progress_signature_o": 0x140F0E03,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return mock.Mock(
                    returncode=0,
                    stdout="device 0: Demo GPU\n"
                    "ok: steps=56 kernels_per_step=5 patches_per_step=0 grid=1 block=256 nstates=32 storage=896 B\n",
                    stderr="",
                )

            argv = [
                "run_tlul_request_loopback_stock_hybrid_validation.py",
                "--mdir",
                str(mdir),
                "--campaign-threshold-bits",
                "1",
                "--host-post-reset-cycles",
                "120",
                "--host-set",
                "cfg_req_valid_pct_i=92",
                "--json-out",
                str(json_out),
                "--flow-json-out",
                str(flow_json),
                "--host-report-out",
                str(host_report),
                "--host-state-out",
                str(host_state),
                "--final-state-out",
                str(final_state),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    rc = self.module.main(sys.argv[1:])

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertTrue(payload["promotion_gate"]["passed"])
            self.assertFalse(payload["handoff_gate"]["passed"])
            self.assertEqual(
                payload["handoff_gate"]["blocked_by"],
                ["host_probe_not_already_done", "gpu_replay_made_progress"],
            )
            self.assertEqual(
                payload["promotion_assessment"]["decision"],
                "promotion_gate_only_not_handoff_proven",
            )
            self.assertEqual(
                payload["promotion_assessment"]["next_requirement"],
                "prove_gpu_driven_handoff",
            )
            self.assertTrue(
                any(
                    "host probe already reached done_o before GPU replay" in caveat
                    for caveat in payload["caveats"]
                )
            )


if __name__ == "__main__":
    unittest.main()
