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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_socket_m1_stock_hybrid_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunSocketM1StockHybridValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_socket_m1_stock_hybrid_validation_test", MODULE_PATH)

    def test_runner_writes_stable_validation_json(self) -> None:
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
                self.assertIn("--json-out", argv)
                flow_json.write_text(
                    json.dumps(
                        {
                            "target": "tlul_socket_m1",
                            "clock_ownership": "tb_timed_coroutine",
                            "mdir": str(mdir),
                            "nstates": 32,
                            "steps": 2,
                            "block_size": 256,
                            "host_report": str(host_report),
                            "host_state": str(host_state),
                            "final_state": str(final_state),
                            "storage_size": 2112,
                            "done_o": 1,
                            "cfg_signature_o": 0x12345678,
                            "toggle_bitmap_word0_o": 11,
                            "toggle_bitmap_word1_o": 22,
                            "toggle_bitmap_word2_o": 33,
                            "patches": ["4:0xff"],
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                host_report.write_text(
                    json.dumps(
                        {
                            "constructor_ok": True,
                            "abi_ok": True,
                            "vl_symsp_bound": True,
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
                            "ok: steps=2 kernels_per_step=5 patches_per_step=1 grid=1 block=256 nstates=32 storage=2112 B",
                            "gpu_kernel_time_ms: total=4.000000  per_launch=2.000000  (CUDA events, kernels only; HtoD patches before launch excluded)",
                            "gpu_kernel_time: per_state=62.500 us  (per_launch / nstates)",
                            "wall_time_ms: 5.500  (host; one GPU sync unless RUN_VL_HYBRID_SYNC_EACH_STEP=1)",
                            '{"target":"tlul_socket_m1"}',
                        ]
                    )
                    + "\n",
                    stderr="",
                )

            argv = [
                "run_socket_m1_stock_hybrid_validation.py",
                "--mdir",
                str(mdir),
                "--nstates",
                "32",
                "--steps",
                "2",
                "--campaign-threshold-bits",
                "5",
                "--patch",
                "4:0xff",
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
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["target"], "tlul_socket_m1")
            self.assertEqual(payload["clock_ownership"], "tb_timed_coroutine")
            self.assertEqual(payload["acceptance_gate"], "phase_b_endpoint")
            self.assertEqual(payload["outputs"]["done_o"], 1)
            self.assertEqual(payload["outputs"]["cfg_signature_o"], 0x12345678)
            self.assertEqual(payload["toggle_coverage"]["bits_hit"], 8)
            self.assertTrue(payload["toggle_coverage"]["any_hit"])
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
            self.assertEqual(payload["campaign_measurement"]["wall_time_ms"], 5.5)
            self.assertEqual(payload["campaign_measurement"]["steps_executed"], 2)
            self.assertEqual(
                payload["artifacts"]["classifier_report"],
                str((mdir / "vl_classifier_report.json").resolve()),
            )
            self.assertEqual(payload["performance"]["device_name"], "Demo GPU")
            self.assertEqual(payload["performance"]["runner_shape"]["kernels_per_step"], 5)
            self.assertEqual(payload["performance"]["throughput"]["kernel_launches"], 10)
            self.assertIn("Phase B is complete at phase_b_endpoint", payload["caveats"][1])
            self.assertAlmostEqual(
                payload["performance"]["throughput"]["state_steps_per_second"],
                16000.0,
            )

    def test_runner_keeps_campaign_schema_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "validation.json"

            def _fake_run(cmd: list[str], **kwargs):
                return mock.Mock(
                    returncode=9,
                    stdout="device 0: Demo GPU\n",
                    stderr="fatal: simulated failure\n",
                )

            argv = [
                "run_socket_m1_stock_hybrid_validation.py",
                "--mdir",
                str(mdir),
                "--steps",
                "7",
                "--campaign-threshold-bits",
                "5",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    rc = self.module.main(sys.argv[1:])

            self.assertEqual(rc, 9)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(
                payload["campaign_threshold"],
                {
                    "kind": "toggle_bits_hit",
                    "value": 5,
                    "aggregation": "bitwise_or_across_trials",
                },
            )
            self.assertEqual(payload["campaign_measurement"]["bits_hit"], 0)
            self.assertFalse(payload["campaign_measurement"]["threshold_satisfied"])
            self.assertIsNone(payload["campaign_measurement"]["wall_time_ms"])
            self.assertEqual(payload["campaign_measurement"]["steps_executed"], 7)
            self.assertEqual(payload["toggle_coverage"]["bits_hit"], 0)
            self.assertEqual(payload["toggle_coverage"]["words_nonzero"], 0)
            self.assertIn("device 0: Demo GPU", payload["stdout_tail"])
            self.assertIn("simulated failure", payload["stderr_tail"])


if __name__ == "__main__":
    unittest.main()
