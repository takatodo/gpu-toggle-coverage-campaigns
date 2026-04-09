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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_veer_eh1_cpu_baseline_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunVeeREH1CpuBaselineValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_veer_eh1_cpu_baseline_validation_test", MODULE_PATH)

    def test_runner_writes_cpu_baseline_validation_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            template = root / "template.json"
            template.write_text(
                json.dumps({"runner_args_template": {"driver_defaults": {}}}) + "\n",
                encoding="utf-8",
            )
            json_out = root / "baseline.json"
            host_report_out = root / "host_report.json"
            binary_out = root / "probe.bin"
            program_hex = root / "program.hex"
            program_hex.write_text("@00000000\nAA\n", encoding="utf-8")

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                if "--build-only" in argv:
                    self.assertIn(
                        "--extra-define=-DPROGRAM_ENTRIES_ARRAY=veer_eh1_gpu_cov_tb__DOT__dut__DOT__gpu_cov_program_entries",
                        argv,
                    )
                    return mock.Mock(returncode=0, stdout=str(binary_out) + "\n", stderr="")
                self.assertEqual(argv[0], str(binary_out))
                self.assertEqual(kwargs.get("cwd"), binary_out.parent)
                self.assertIn("--set", argv)
                self.assertIn("cfg_valid_i=1", argv)
                self.assertIn("--program-entries-bin", argv)
                return mock.Mock(
                    returncode=0,
                    stdout=(
                        "******START TO LOAD PROGRAM******\n"
                        + json.dumps(
                            {
                                "constructor_ok": True,
                                "clock_ownership": "tb_timed_coroutine",
                                "drained_events": 136,
                                "done_o": 1,
                                "cfg_signature_o": 17,
                                "host_req_accepted_o": 3,
                                "device_req_accepted_o": 2,
                                "device_rsp_accepted_o": 2,
                                "host_rsp_accepted_o": 4,
                                "rsp_queue_overflow_o": 0,
                                "progress_cycle_count_o": 21,
                                "progress_signature_o": 91,
                                "toggle_bitmap_word0_o": 0x3F,
                                "toggle_bitmap_word1_o": 0x03,
                                "toggle_bitmap_word2_o": 0x00,
                            }
                        )
                        + "\n"
                    ),
                    stderr="",
                )

            argv = [
                "run_veer_eh1_cpu_baseline_validation.py",
                "--mdir",
                str(mdir),
                "--template",
                str(template),
                "--program-hex",
                str(program_hex),
                "--json-out",
                str(json_out),
                "--host-report-out",
                str(host_report_out),
                "--binary-out",
                str(binary_out),
                "--host-reset-cycles",
                "4",
                "--host-post-reset-cycles",
                "64",
                "--campaign-threshold-bits",
                "8",
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(self.module.time, "perf_counter", side_effect=[10.0, 10.2]):
                    with mock.patch.object(sys, "argv", argv):
                        rc = self.module.main(sys.argv[1:])

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["target"], "veer_eh1")
            self.assertEqual(payload["backend"], "stock_verilator_cpu_baseline")
            self.assertEqual(payload["clock_ownership"], "tb_timed_coroutine")
            self.assertEqual(payload["support_tier"], "candidate_non_opentitan_single_surface")
            self.assertEqual(payload["coverage"]["bits_hit"], 8)
            self.assertTrue(payload["campaign_measurement"]["threshold_satisfied"])
            self.assertAlmostEqual(payload["campaign_measurement"]["wall_time_ms"], 200.0)
            self.assertEqual(payload["campaign_measurement"]["steps_executed"], 136)
            self.assertEqual(
                payload["inputs"]["host_probe_extra_defines"],
                ["-DPROGRAM_ENTRIES_ARRAY=veer_eh1_gpu_cov_tb__DOT__dut__DOT__gpu_cov_program_entries"],
            )
            program_entries_bin = Path(payload["artifacts"]["runtime_program_entries_bin"])
            self.assertTrue(program_entries_bin.is_file())


if __name__ == "__main__":
    unittest.main()
