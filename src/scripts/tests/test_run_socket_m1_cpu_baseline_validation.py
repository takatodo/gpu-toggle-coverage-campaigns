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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_socket_m1_cpu_baseline_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunSocketM1CpuBaselineValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_socket_m1_cpu_baseline_validation_test", MODULE_PATH)

    def test_runner_writes_cpu_baseline_validation_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "baseline.json"
            host_report_out = root / "host_report.json"
            binary_out = root / "probe.bin"

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                if "--build-only" in argv:
                    return mock.Mock(returncode=0, stdout=str(binary_out) + "\n", stderr="")
                self.assertEqual(argv[0], str(binary_out))
                return mock.Mock(
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "constructor_ok": True,
                            "abi_ok": True,
                            "vl_symsp_bound": True,
                            "drained_events": 12,
                            "cfg_signature_o": 0x12345678,
                            "toggle_bitmap_word0_o": 11,
                            "toggle_bitmap_word1_o": 22,
                            "toggle_bitmap_word2_o": 33,
                            "done_o": 1,
                        }
                    )
                    + "\n",
                    stderr="",
                )

            argv = [
                "run_socket_m1_cpu_baseline_validation.py",
                "--mdir",
                str(mdir),
                "--json-out",
                str(json_out),
                "--host-report-out",
                str(host_report_out),
                "--binary-out",
                str(binary_out),
                "--reset-cycles",
                "4",
                "--post-reset-cycles",
                "2",
                "--campaign-threshold-bits",
                "5",
                "--batch-length",
                "1",
                "--seed",
                "9",
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(self.module.time, "perf_counter", side_effect=[10.0, 10.25]):
                    with mock.patch.object(sys, "argv", argv):
                        rc = self.module.main(sys.argv[1:])

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["target"], "tlul_socket_m1")
            self.assertEqual(payload["backend"], "stock_verilator_cpu_baseline")
            self.assertEqual(payload["coverage"]["bits_hit"], 8)
            self.assertTrue(payload["coverage"]["any_hit"])
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
            self.assertEqual(payload["campaign_measurement"]["wall_time_ms"], 250.0)
            self.assertEqual(payload["campaign_measurement"]["steps_executed"], 12)
            self.assertEqual(payload["performance"]["wall_time_ms"], 250.0)
            self.assertEqual(payload["performance"]["steps_executed"], 12)
            self.assertEqual(payload["outputs"]["done_o"], 1)
            self.assertEqual(payload["outputs"]["cfg_signature_o"], 0x12345678)
            self.assertEqual(payload["artifacts"]["probe_binary"], str(binary_out.resolve()))
            self.assertEqual(payload["host_probe"]["drained_events"], 12)
            self.assertIn("compile time is excluded", payload["caveats"][0])

    def test_runner_keeps_schema_when_build_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "baseline.json"

            def _fake_run(cmd: list[str], **kwargs):
                return mock.Mock(returncode=2, stdout="", stderr="build failed\n")

            argv = [
                "run_socket_m1_cpu_baseline_validation.py",
                "--mdir",
                str(mdir),
                "--json-out",
                str(json_out),
                "--steps",
                "ignored",
            ]
            # argv above intentionally not parsed; keep minimal valid args only.
            argv = [
                "run_socket_m1_cpu_baseline_validation.py",
                "--mdir",
                str(mdir),
                "--campaign-threshold-bits",
                "5",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    rc = self.module.main(sys.argv[1:])

            self.assertEqual(rc, 1)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["coverage"]["bits_hit"], 0)
            self.assertEqual(payload["campaign_measurement"]["bits_hit"], 0)
            self.assertFalse(payload["campaign_measurement"]["threshold_satisfied"])
            self.assertEqual(payload["campaign_measurement"]["steps_executed"], 6)
            self.assertEqual(payload["build_returncode"], 2)
            self.assertEqual(payload["flow_returncode"], 1)
            self.assertIn("build failed", payload["build_stderr_tail"])


if __name__ == "__main__":
    unittest.main()
