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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_tlul_socket_1n_cpu_baseline_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunTlulSocket1NCpuBaselineValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_tlul_socket_1n_cpu_baseline_validation_test", MODULE_PATH)

    def test_runner_writes_cpu_baseline_validation_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            template = root / "template.json"
            template.write_text(
                json.dumps({"runner_args_template": {"driver_defaults": {"req_valid_pct": 92}}}) + "\n",
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
                self.assertIn("cfg_req_valid_pct_i=92", argv)
                self.assertIn("cfg_valid_i=1", argv)
                return mock.Mock(
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "constructor_ok": True,
                            "clock_ownership": "tb_timed_coroutine",
                            "drained_events": 24,
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
                    stderr="",
                )

            argv = [
                "run_tlul_socket_1n_cpu_baseline_validation.py",
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
                "8",
                "--campaign-threshold-bits",
                "26",
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(self.module.time, "perf_counter", side_effect=[10.0, 10.25]):
                    with mock.patch.object(sys, "argv", argv):
                        rc = self.module.main(sys.argv[1:])

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["target"], "tlul_socket_1n")
            self.assertEqual(payload["backend"], "stock_verilator_cpu_baseline")
            self.assertEqual(payload["support_tier"], "campaign_reference_surface")
            self.assertEqual(payload["coverage"]["bits_hit"], 26)
            self.assertEqual(payload["campaign_threshold"]["value"], 26)
            self.assertTrue(payload["campaign_measurement"]["threshold_satisfied"])
            self.assertEqual(payload["campaign_measurement"]["wall_time_ms"], 250.0)
            self.assertEqual(payload["campaign_measurement"]["steps_executed"], 24)
            self.assertEqual(payload["inputs"]["configured_inputs"]["cfg_req_valid_pct_i"], 92)

    def test_runner_keeps_schema_when_build_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "baseline.json"

            def _fake_run(cmd: list[str], **kwargs):
                return mock.Mock(returncode=2, stdout="", stderr="build failed\n")

            argv = [
                "run_tlul_socket_1n_cpu_baseline_validation.py",
                "--mdir",
                str(mdir),
                "--campaign-threshold-bits",
                "26",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    rc = self.module.main(sys.argv[1:])

            self.assertEqual(rc, 1)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["coverage"]["bits_hit"], 0)
            self.assertFalse(payload["campaign_measurement"]["threshold_satisfied"])
            self.assertEqual(payload["build_returncode"], 2)


if __name__ == "__main__":
    unittest.main()
