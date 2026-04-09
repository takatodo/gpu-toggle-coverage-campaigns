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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_tlul_fifo_sync_stock_hybrid_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunTlulFifoSyncStockHybridValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_tlul_fifo_sync_stock_hybrid_validation_test", MODULE_PATH)

    def test_runner_writes_thin_top_reference_validation_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "validation.json"
            flow_json = root / "flow.json"
            parity_json = root / "parity.json"
            host_report = root / "host.json"
            host_state = root / "host.bin"
            final_state = root / "final.bin"
            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                if argv[1].endswith("run_tlul_slice_host_gpu_flow.py"):
                    flow_json.write_text(
                        json.dumps(
                            {
                                "target": "tlul_fifo_sync",
                                "clock_ownership": "host_direct_ports",
                                "support_tier": "thin_top_reference_design",
                                "mdir": str(mdir),
                                "nstates": 32,
                                "steps": 56,
                                "block_size": 256,
                                "host_report": str(host_report),
                                "host_state": str(host_state),
                                "final_state": str(final_state),
                                "storage_size": 5952,
                                "outputs": {
                                    "done_o": 0,
                                    "progress_cycle_count_o": 7,
                                    "progress_signature_o": 0x9E3779B2,
                                    "toggle_bitmap_word0_o": 11,
                                    "toggle_bitmap_word1_o": 22,
                                    "toggle_bitmap_word2_o": 33,
                                },
                                "host_edge_runs": [
                                    {
                                        "index": 1,
                                        "clock_level": 1,
                                        "done_o": 0,
                                        "progress_cycle_count_o": 7,
                                        "progress_signature_o": 0x9E3779B2,
                                        "toggle_bitmap_word0_o": 11,
                                        "toggle_bitmap_word1_o": 22,
                                        "toggle_bitmap_word2_o": 33,
                                    },
                                    {
                                        "index": 2,
                                        "clock_level": 0,
                                        "done_o": 0,
                                        "progress_cycle_count_o": 7,
                                        "progress_signature_o": 0x9E3779B2,
                                        "toggle_bitmap_word0_o": 11,
                                        "toggle_bitmap_word1_o": 22,
                                        "toggle_bitmap_word2_o": 33,
                                    },
                                ],
                                "edge_parity": {
                                    "compared_edge_count": 2,
                                    "all_edges_internal_only": True,
                                    "role_summary": {"verilator_internal": 22},
                                },
                                "campaign_timing": {
                                    "run_count": 2,
                                    "timing_complete": True,
                                    "wall_time_ms": 7.0,
                                    "per_run_wall_time_ms": [3.0, 4.0],
                                    "gpu_kernel_time_complete": True,
                                    "gpu_kernel_time_ms_total": 6.0,
                                    "per_run_gpu_kernel_time_ms": [2.5, 3.5],
                                },
                            }
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    host_report.write_text(
                        json.dumps(
                            {
                                "constructor_ok": True,
                                "clock_ownership": "host_direct_ports",
                                "host_clock_control": True,
                                "host_reset_control": True,
                                "progress_cycle_count_o": 6,
                                "progress_signature_o": 0,
                                "toggle_bitmap_word0_o": 0,
                                "toggle_bitmap_word1_o": 0,
                                "toggle_bitmap_word2_o": 0,
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
                                "ok: steps=56 kernels_per_step=2 patches_per_step=2 grid=1 block=256 nstates=32 storage=5952 B",
                                "gpu_kernel_time_ms: total=2.000000  per_launch=1.000000  (CUDA events, kernels only; HtoD patches before launch excluded)",
                                "gpu_kernel_time: per_state=31.250 us  (per_launch / nstates)",
                                "wall_time_ms: 3.500  (host; one GPU sync unless RUN_VL_HYBRID_SYNC_EACH_STEP=1)",
                            ]
                        )
                        + "\n",
                        stderr="",
                    )
                parity_json.write_text(
                    json.dumps(
                        {
                            "target": "tlul_fifo_sync",
                            "clock_ownership": "host_direct_ports",
                            "edge_parity": {
                                "compared_edge_count": 2,
                                "all_edges_internal_only": True,
                                "role_summary": {"verilator_internal": 6},
                            },
                            "fake_syms_edge_parity": {
                                "compared_edge_count": 2,
                                "all_edges_internal_only": True,
                                "role_summary": {"verilator_internal": 16},
                            },
                            "raw_import_edge_parity": {
                                "compared_edge_count": 2,
                                "all_edges_internal_only": True,
                                "role_summary": {"verilator_internal": 12},
                            },
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return mock.Mock(returncode=0, stdout='{"target":"tlul_fifo_sync"}\n', stderr="")

            argv = [
                "run_tlul_fifo_sync_stock_hybrid_validation.py",
                "--mdir",
                str(mdir),
                "--campaign-threshold-bits",
                "5",
                "--json-out",
                str(json_out),
                "--flow-json-out",
                str(flow_json),
                "--parity-json-out",
                str(parity_json),
                "--host-report-out",
                str(host_report),
                "--host-state-out",
                str(host_state),
                "--final-state-out",
                str(final_state),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(self.module.time, "perf_counter", side_effect=[20.0, 20.25]):
                    with mock.patch.object(sys, "argv", argv):
                        rc = self.module.main(sys.argv[1:])

            self.assertEqual(rc, 0)
            self.assertEqual(len(calls), 2)
            self.assertTrue(calls[0][1].endswith("run_tlul_slice_host_gpu_flow.py"))
            self.assertTrue(calls[1][1].endswith("run_tlul_slice_handoff_parity_probe.py"))
            self.assertIn("--host-clock-sequence", calls[0])
            self.assertIn("1,0", calls[0])
            self.assertIn("--clock-sequence", calls[1])
            self.assertIn("1,0", calls[1])

            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["target"], "tlul_fifo_sync")
            self.assertEqual(payload["support_tier"], "thin_top_reference_design")
            self.assertEqual(payload["clock_ownership"], "host_direct_ports")
            self.assertEqual(payload["acceptance_gate"], "thin_top_edge_parity_v1")
            self.assertTrue(payload["edge_parity_gate"]["passed"])
            self.assertEqual(payload["edge_parity_gate"]["blocked_by"], [])
            self.assertEqual(payload["edge_parity_gate"]["target_support_tier"], "thin_top_reference_design")
            self.assertEqual(payload["outputs"]["progress_cycle_count_o"], 7)
            self.assertEqual(payload["outputs"]["progress_signature_o"], 0x9E3779B2)
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
            self.assertEqual(payload["campaign_measurement"]["steps_executed"], 2)
            self.assertEqual(payload["campaign_measurement"]["wall_time_ms"], 7.0)
            self.assertEqual(payload["performance"]["device_name"], "Demo GPU")
            self.assertEqual(payload["performance"]["campaign_wall_time_ms"], 7.0)
            self.assertEqual(payload["performance"]["flow_wall_time_ms"], 250.0)
            self.assertEqual(payload["performance"]["campaign_timing"]["per_run_wall_time_ms"], [3.0, 4.0])
            self.assertEqual(payload["performance"]["runner_shape"]["kernels_per_step"], 2)
            self.assertEqual(payload["performance"]["throughput"]["kernel_launches"], 112)
            self.assertEqual(
                payload["artifacts"]["classifier_report"],
                str((mdir / "vl_classifier_report.json").resolve()),
            )
            self.assertTrue(payload["edge_parity_gate"]["observed"]["final_outputs"] == payload["edge_parity_gate"]["observed"]["last_host_edge_outputs"])
            self.assertIn("per-run run_vl_hybrid host wall times", payload["caveats"][2])


if __name__ == "__main__":
    unittest.main()
