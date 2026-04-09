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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_xbar_main_cpu_baseline_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunXbarMainCpuBaselineValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_xbar_main_cpu_baseline_validation_test", MODULE_PATH)

    def test_runner_writes_cpu_baseline_validation_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            template = root / "template.json"
            template.write_text(
                json.dumps(
                    {
                        "runner_args_template": {
                            "driver_defaults": {
                                "access_ack_data_pct": 100,
                            }
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            json_out = root / "baseline.json"
            host_report_out = root / "host_report.json"
            binary_out = root / "probe.bin"

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                if "--build-only" in argv:
                    return mock.Mock(returncode=0, stdout=str(binary_out) + "\n", stderr="")
                self.assertEqual(argv[0], str(binary_out))
                self.assertIn("--set", argv)
                self.assertIn("cfg_valid_i=1", argv)
                self.assertIn("cfg_access_ack_data_pct_i=100", argv)
                self.assertNotIn("access_ack_data_pct=100", argv)
                return mock.Mock(
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "constructor_ok": True,
                            "clock_ownership": "tb_timed_coroutine",
                            "drained_events": 200,
                            "done_o": 0,
                            "cfg_signature_o": 987108,
                            "host_req_accepted_o": 26,
                            "device_req_accepted_o": 12,
                            "device_rsp_accepted_o": 12,
                            "host_rsp_accepted_o": 23,
                            "rsp_queue_overflow_o": 0,
                            "progress_cycle_count_o": 37,
                            "progress_signature_o": 4094362513,
                            "toggle_bitmap_word0_o": 1623617039,
                            "toggle_bitmap_word1_o": 4234200684,
                            "toggle_bitmap_word2_o": 2249006069,
                        }
                    )
                    + "\n",
                    stderr="",
                )

            argv = [
                "run_xbar_main_cpu_baseline_validation.py",
                "--mdir",
                str(mdir),
                "--template",
                str(template),
                "--json-out",
                str(json_out),
                "--host-report-out",
                str(host_report_out),
                "--binary-out",
                str(binary_out),
                "--host-reset-cycles",
                "4",
                "--host-post-reset-cycles",
                "96",
                "--campaign-threshold-bits",
                "47",
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(self.module.time, "perf_counter", side_effect=[10.0, 10.5]):
                    with mock.patch.object(sys, "argv", argv):
                        rc = self.module.main(sys.argv[1:])

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["target"], "xbar_main")
            self.assertEqual(payload["backend"], "stock_verilator_cpu_baseline")
            self.assertEqual(payload["clock_ownership"], "tb_timed_coroutine")
            self.assertEqual(payload["support_tier"], "campaign_reference_surface")
            self.assertEqual(payload["coverage"]["bits_hit"], 47)
            self.assertEqual(
                payload["campaign_threshold"],
                {
                    "kind": "toggle_bits_hit",
                    "value": 47,
                    "aggregation": "bitwise_or_across_trials",
                },
            )
            self.assertEqual(payload["campaign_measurement"]["bits_hit"], 47)
            self.assertTrue(payload["campaign_measurement"]["threshold_satisfied"])
            self.assertEqual(payload["campaign_measurement"]["wall_time_ms"], 500.0)
            self.assertEqual(payload["campaign_measurement"]["steps_executed"], 200)


if __name__ == "__main__":
    unittest.main()
