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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_tlul_fifo_async_stock_hybrid_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunTlulFifoAsyncStockHybridValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_tlul_fifo_async_stock_hybrid_validation_test", MODULE_PATH)

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
                argv = [str(item) for item in cmd]
                self.assertIn("--sanitize-host-only-internals", argv)
                flow_json.write_text(
                    json.dumps(
                        {
                            "target": "tlul_fifo_async",
                            "clock_ownership": "tb_timed_coroutine",
                            "support_tier": "campaign_reference_surface",
                            "mdir": str(mdir),
                            "nstates": 32,
                            "steps": 56,
                            "block_size": 256,
                            "sanitize_host_only_internals": True,
                            "host_report": str(host_report),
                            "host_state": str(host_state),
                            "final_state": str(final_state),
                            "storage_size": 3136,
                            "outputs": {
                                "done_o": 0,
                                "cfg_signature_o": 14602,
                                "host_req_accepted_o": 5,
                                "device_req_accepted_o": 4,
                                "device_rsp_accepted_o": 3,
                                "host_rsp_accepted_o": 1,
                                "rsp_queue_overflow_o": 0,
                                "progress_cycle_count_o": 14,
                                "progress_signature_o": 84148993,
                                "toggle_bitmap_word0_o": 1573632,
                                "toggle_bitmap_word1_o": 1263550790,
                                "toggle_bitmap_word2_o": 957016063,
                            },
                            "changed_watch_field_count": 0,
                            "state_delta": {
                                "changed_byte_count": 33,
                                "changed_known_field_count": 0,
                                "first_changed_offsets": [2976],
                                "first_changed_known_fields": [],
                            },
                            "campaign_timing": {
                                "run_count": 1,
                                "timing_complete": True,
                                "wall_time_ms": 1.088,
                                "per_run_wall_time_ms": [1.088],
                                "gpu_kernel_time_complete": True,
                                "gpu_kernel_time_ms_total": 0.900096,
                                "per_run_gpu_kernel_time_ms": [0.900096],
                            },
                            "gpu_runs": [
                                {
                                    "index": 1,
                                    "steps": 56,
                                    "performance": {
                                        "wall_time_ms": 1.088,
                                        "gpu_kernel_time_ms": {
                                            "total": 0.900096,
                                            "per_launch": 0.016073,
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
                            "cfg_signature_o": 14602,
                            "host_req_accepted_o": 5,
                            "device_req_accepted_o": 4,
                            "device_rsp_accepted_o": 3,
                            "host_rsp_accepted_o": 1,
                            "rsp_queue_overflow_o": 0,
                            "progress_cycle_count_o": 14,
                            "progress_signature_o": 84148993,
                            "toggle_bitmap_word0_o": 1573632,
                            "toggle_bitmap_word1_o": 1263550790,
                            "toggle_bitmap_word2_o": 957016063,
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
                            "ok: steps=56 kernels_per_step=1 patches_per_step=0 grid=1 block=256 nstates=32 storage=3136 B",
                            "gpu_kernel_time_ms: total=0.900096  per_launch=0.016073  (CUDA events, kernels only; HtoD patches before launch excluded)",
                            "gpu_kernel_time: per_state=0.502 us  (per_launch / nstates)",
                            "wall_time_ms: 1.088  (host; one GPU sync unless RUN_VL_HYBRID_SYNC_EACH_STEP=1)",
                            '{"target":"tlul_fifo_async"}',
                        ]
                    )
                    + "\n",
                    stderr="",
                )

            argv = [
                "run_tlul_fifo_async_stock_hybrid_validation.py",
                "--mdir",
                str(mdir),
                "--campaign-threshold-bits",
                "35",
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
            self.assertEqual(payload["target"], "tlul_fifo_async")
            self.assertEqual(payload["support_tier"], "campaign_reference_surface")
            self.assertEqual(payload["acceptance_gate"], "campaign_reference_surface_v1")
            self.assertTrue(payload["reference_gate"]["passed"])
            self.assertEqual(payload["reference_gate"]["blocked_by"], [])
            self.assertEqual(payload["outputs"]["cfg_signature_o"], 14602)
            self.assertEqual(payload["toggle_coverage"]["bits_hit"], 35)
            self.assertTrue(payload["campaign_measurement"]["threshold_satisfied"])
            self.assertEqual(payload["campaign_measurement"]["wall_time_ms"], 1.088)
            self.assertEqual(payload["inputs"]["sanitize_host_only_internals"], True)
            self.assertIn("sanitize", payload["caveats"][3])


if __name__ == "__main__":
    unittest.main()
