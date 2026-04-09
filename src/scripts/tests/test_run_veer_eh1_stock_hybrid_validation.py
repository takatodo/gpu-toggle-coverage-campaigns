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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_veer_eh1_stock_hybrid_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunVeeREH1StockHybridValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_veer_eh1_stock_hybrid_validation_test", MODULE_PATH)

    def test_runner_writes_candidate_single_surface_validation_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "validation.json"
            flow_json = root / "flow.json"
            host_report = root / "host.json"
            host_state = root / "host.bin"
            final_state = root / "final.bin"
            program_hex = root / "program.hex"
            program_hex.write_text("@00000000\nAA\n", encoding="utf-8")

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                self.assertIn("--sanitize-host-only-internals", argv)
                self.assertIn("--program-entries-bin", argv)
                self.assertIn(
                    "--host-probe-extra-define=-DPROGRAM_ENTRIES_ARRAY=veer_eh1_gpu_cov_tb__DOT__dut__DOT__gpu_cov_program_entries",
                    argv,
                )
                flow_json.write_text(
                    json.dumps(
                        {
                            "target": "veer_eh1",
                            "clock_ownership": "tb_timed_coroutine",
                            "support_tier": "candidate_non_opentitan_single_surface",
                            "mdir": str(mdir),
                            "nstates": 8,
                            "steps": 56,
                            "block_size": 256,
                            "sanitize_host_only_internals": True,
                            "host_report": str(host_report),
                            "host_state": str(host_state),
                            "final_state": str(final_state),
                            "storage_size": 4096,
                            "outputs": {
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
                            },
                            "changed_watch_field_count": 0,
                            "state_delta": {
                                "changed_byte_count": 12,
                                "changed_known_field_count": 0,
                                "first_changed_offsets": [128],
                                "first_changed_known_fields": [],
                            },
                            "campaign_timing": {
                                "run_count": 1,
                                "timing_complete": True,
                                "wall_time_ms": 1.75,
                                "per_run_wall_time_ms": [1.75],
                                "gpu_kernel_time_complete": True,
                                "gpu_kernel_time_ms_total": 1.6,
                                "per_run_gpu_kernel_time_ms": [1.6],
                            },
                            "gpu_runs": [
                                {
                                    "index": 1,
                                    "steps": 56,
                                    "performance": {
                                        "wall_time_ms": 1.75,
                                        "gpu_kernel_time_ms": {
                                            "total": 1.6,
                                            "per_launch": 0.02857,
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
                    + "\n",
                    encoding="utf-8",
                )
                return mock.Mock(
                    returncode=0,
                    stdout="\n".join(
                        [
                            "device 0: Demo GPU",
                            "ok: steps=56 kernels_per_step=1 patches_per_step=0 grid=1 block=256 nstates=8 storage=4096 B",
                            "gpu_kernel_time_ms: total=1.600000  per_launch=0.028570  (CUDA events, kernels only; HtoD patches before launch excluded)",
                            "gpu_kernel_time: per_state=3.571 us  (per_launch / nstates)",
                            "wall_time_ms: 1.750  (host; one GPU sync unless RUN_VL_HYBRID_SYNC_EACH_STEP=1)",
                        ]
                    )
                    + "\n",
                    stderr="",
                )

            argv = [
                "run_veer_eh1_stock_hybrid_validation.py",
                "--mdir",
                str(mdir),
                "--program-hex",
                str(program_hex),
                "--campaign-threshold-bits",
                "8",
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
            self.assertEqual(payload["target"], "veer_eh1")
            self.assertTrue(payload["reference_gate"]["passed"])
            self.assertEqual(payload["toggle_coverage"]["bits_hit"], 8)
            self.assertTrue(payload["campaign_measurement"]["threshold_satisfied"])
            self.assertEqual(payload["campaign_measurement"]["wall_time_ms"], 1.75)
            self.assertTrue(payload["inputs"]["sanitize_host_only_internals"])
            self.assertEqual(
                payload["inputs"]["host_probe_extra_defines"],
                ["-DPROGRAM_ENTRIES_ARRAY=veer_eh1_gpu_cov_tb__DOT__dut__DOT__gpu_cov_program_entries"],
            )
            program_entries_bin = Path(payload["artifacts"]["runtime_program_entries_bin"])
            self.assertTrue(program_entries_bin.is_file())


if __name__ == "__main__":
    unittest.main()
