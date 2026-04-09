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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_tlul_socket_1n_stock_hybrid_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunTlulSocket1NStockHybridValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_tlul_socket_1n_stock_hybrid_validation_test", MODULE_PATH)

    def test_runner_writes_campaign_reference_validation_json(self) -> None:
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
                            "target": "tlul_socket_1n",
                            "clock_ownership": "tb_timed_coroutine",
                            "support_tier": "campaign_reference_surface",
                            "mdir": str(mdir),
                            "nstates": 32,
                            "steps": 56,
                            "block_size": 256,
                            "host_report": str(host_report),
                            "host_state": str(host_state),
                            "final_state": str(final_state),
                            "storage_size": 2240,
                            "outputs": {
                                "done_o": 0,
                                "cfg_signature_o": 4294963363,
                                "host_req_accepted_o": 0,
                                "device_req_accepted_o": 0,
                                "device_rsp_accepted_o": 0,
                                "host_rsp_accepted_o": 0,
                                "rsp_queue_overflow_o": 0,
                                "progress_cycle_count_o": 8,
                                "progress_signature_o": 9,
                                "toggle_bitmap_word0_o": 521217097,
                                "toggle_bitmap_word1_o": 1062228096,
                                "toggle_bitmap_word2_o": 3221241856,
                            },
                            "changed_watch_field_count": 0,
                            "state_delta": {
                                "changed_byte_count": 8,
                                "changed_known_field_count": 0,
                                "first_changed_offsets": [84, 1968],
                                "first_changed_known_fields": [],
                            },
                            "campaign_timing": {
                                "run_count": 1,
                                "timing_complete": True,
                                "wall_time_ms": 1.866,
                                "per_run_wall_time_ms": [1.866],
                                "gpu_kernel_time_complete": True,
                                "gpu_kernel_time_ms_total": 1.82272,
                                "per_run_gpu_kernel_time_ms": [1.82272],
                            },
                            "gpu_runs": [
                                {
                                    "index": 1,
                                    "steps": 56,
                                    "performance": {
                                        "wall_time_ms": 1.866,
                                        "gpu_kernel_time_ms": {
                                            "total": 1.82272,
                                            "per_launch": 0.032549,
                                        },
                                    },
                                }
                            ],
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
                            "cfg_signature_o": 4294963363,
                            "host_req_accepted_o": 0,
                            "device_req_accepted_o": 0,
                            "device_rsp_accepted_o": 0,
                            "host_rsp_accepted_o": 0,
                            "rsp_queue_overflow_o": 0,
                            "progress_cycle_count_o": 8,
                            "progress_signature_o": 9,
                            "toggle_bitmap_word0_o": 521217097,
                            "toggle_bitmap_word1_o": 1062228096,
                            "toggle_bitmap_word2_o": 3221241856,
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
                            "ok: steps=56 kernels_per_step=1 patches_per_step=0 grid=1 block=256 nstates=32 storage=2240 B",
                            "gpu_kernel_time_ms: total=1.822720  per_launch=0.032549  (CUDA events, kernels only; HtoD patches before launch excluded)",
                            "gpu_kernel_time: per_state=1.017 us  (per_launch / nstates)",
                            "wall_time_ms: 1.866  (host; one GPU sync unless RUN_VL_HYBRID_SYNC_EACH_STEP=1)",
                            '{"target":"tlul_socket_1n"}',
                        ]
                    )
                    + "\n",
                    stderr="",
                )

            argv = [
                "run_tlul_socket_1n_stock_hybrid_validation.py",
                "--mdir",
                str(mdir),
                "--campaign-threshold-bits",
                "26",
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
            self.assertEqual(payload["target"], "tlul_socket_1n")
            self.assertEqual(payload["support_tier"], "campaign_reference_surface")
            self.assertEqual(payload["acceptance_gate"], "campaign_reference_surface_v1")
            self.assertTrue(payload["reference_gate"]["passed"])
            self.assertEqual(payload["toggle_coverage"]["bits_hit"], 26)
            self.assertEqual(payload["campaign_threshold"]["value"], 26)
            self.assertTrue(payload["campaign_measurement"]["threshold_satisfied"])
            self.assertEqual(payload["campaign_measurement"]["wall_time_ms"], 1.866)
            self.assertEqual(payload["campaign_measurement"]["steps_executed"], 56)
            self.assertEqual(payload["performance"]["device_name"], "Demo GPU")

    def test_runner_reports_reference_gate_blocker_when_outputs_diverge(self) -> None:
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
                            "target": "tlul_socket_1n",
                            "clock_ownership": "tb_timed_coroutine",
                            "outputs": {
                                "done_o": 0,
                                "cfg_signature_o": 4294963363,
                                "host_req_accepted_o": 0,
                                "device_req_accepted_o": 0,
                                "device_rsp_accepted_o": 0,
                                "host_rsp_accepted_o": 0,
                                "rsp_queue_overflow_o": 0,
                                "progress_cycle_count_o": 8,
                                "progress_signature_o": 7,
                                "toggle_bitmap_word0_o": 521217097,
                                "toggle_bitmap_word1_o": 1062228096,
                                "toggle_bitmap_word2_o": 3221241856,
                            },
                            "changed_watch_field_count": 0,
                            "campaign_timing": {"wall_time_ms": 1.866},
                            "gpu_runs": [{"index": 1, "steps": 56, "performance": {"wall_time_ms": 1.866}}],
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                host_report.write_text(
                    json.dumps(
                        {
                            "clock_ownership": "tb_timed_coroutine",
                            "done_o": 0,
                            "cfg_signature_o": 4294963363,
                            "host_req_accepted_o": 0,
                            "device_req_accepted_o": 0,
                            "device_rsp_accepted_o": 0,
                            "host_rsp_accepted_o": 0,
                            "rsp_queue_overflow_o": 0,
                            "progress_cycle_count_o": 8,
                            "progress_signature_o": 9,
                            "toggle_bitmap_word0_o": 521217097,
                            "toggle_bitmap_word1_o": 1062228096,
                            "toggle_bitmap_word2_o": 3221241856,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return mock.Mock(returncode=0, stdout="", stderr="")

            argv = [
                "run_tlul_socket_1n_stock_hybrid_validation.py",
                "--mdir",
                str(mdir),
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
            self.assertFalse(payload["reference_gate"]["passed"])
            self.assertEqual(payload["reference_gate"]["blocked_by"], ["outputs_match_host_probe"])
            self.assertFalse(payload["campaign_measurement"]["threshold_satisfied"])


if __name__ == "__main__":
    unittest.main()
