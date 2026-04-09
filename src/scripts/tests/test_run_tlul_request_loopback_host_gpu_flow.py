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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "run_tlul_request_loopback_host_gpu_flow.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunTlulRequestLoopbackHostGpuFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_tlul_request_loopback_host_gpu_flow_test", MODULE_PATH)

    def test_flow_runs_probe_then_gpu_and_summarizes_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "summary.json"
            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                if argv[1].endswith("run_tlul_slice_host_probe.py"):
                    host_report = Path(argv[argv.index("--json-out") + 1])
                    host_state = Path(argv[argv.index("--state-out") + 1])
                    host_report.write_text(
                        json.dumps(
                            {
                                "root_size": 896,
                                "field_offsets": {
                                    "done_o": 1,
                                    "cfg_signature_o": 188,
                                    "host_req_accepted_o": 192,
                                    "device_req_accepted_o": 196,
                                    "device_rsp_accepted_o": 200,
                                    "host_rsp_accepted_o": 204,
                                    "rsp_queue_overflow_o": 208,
                                    "progress_cycle_count_o": 212,
                                    "progress_signature_o": 216,
                                    "toggle_bitmap_word0_o": 220,
                                    "toggle_bitmap_word1_o": 224,
                                    "toggle_bitmap_word2_o": 228,
                                },
                                "field_sizes": {
                                    "done_o": 1,
                                    "cfg_signature_o": 4,
                                    "host_req_accepted_o": 4,
                                    "device_req_accepted_o": 4,
                                    "device_rsp_accepted_o": 4,
                                    "host_rsp_accepted_o": 4,
                                    "rsp_queue_overflow_o": 4,
                                    "progress_cycle_count_o": 4,
                                    "progress_signature_o": 4,
                                    "toggle_bitmap_word0_o": 4,
                                    "toggle_bitmap_word1_o": 4,
                                    "toggle_bitmap_word2_o": 4,
                                },
                                "configured_inputs": {"cfg_valid_i": 1},
                            }
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    host_state.write_bytes(b"\x00" * 896)
                    return None
                final_state = Path(argv[argv.index("--dump-state") + 1])
                blob = bytearray(896)
                blob[1] = 1
                blob[188:192] = (0x12345678).to_bytes(4, "little")
                blob[192:196] = (7).to_bytes(4, "little")
                blob[196:200] = (8).to_bytes(4, "little")
                blob[200:204] = (9).to_bytes(4, "little")
                blob[204:208] = (10).to_bytes(4, "little")
                blob[212:216] = (56).to_bytes(4, "little")
                blob[216:220] = (0xABCDEF01).to_bytes(4, "little")
                blob[220:224] = (11).to_bytes(4, "little")
                blob[224:228] = (22).to_bytes(4, "little")
                blob[228:232] = (33).to_bytes(4, "little")
                final_state.write_bytes(blob)
                return None

            argv = [
                "run_tlul_request_loopback_host_gpu_flow.py",
                "--mdir",
                str(mdir),
                "--nstates",
                "32",
                "--steps",
                "56",
                "--host-post-reset-cycles",
                "120",
                "--host-set",
                "cfg_req_valid_pct_i=92",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    self.module.main()

            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["target"], "tlul_request_loopback")
            self.assertEqual(payload["support_tier"], "phase_b_reference_design")
            self.assertEqual(payload["nstates"], 32)
            self.assertEqual(payload["steps"], 56)
            self.assertEqual(payload["host_post_reset_cycles"], 120)
            self.assertEqual(payload["host_overrides"], ["cfg_req_valid_pct_i=92"])
            self.assertEqual(payload["done_o"], 1)
            self.assertEqual(payload["cfg_signature_o"], 0x12345678)
            self.assertEqual(payload["host_req_accepted_o"], 7)
            self.assertEqual(payload["device_req_accepted_o"], 8)
            self.assertEqual(payload["device_rsp_accepted_o"], 9)
            self.assertEqual(payload["host_rsp_accepted_o"], 10)
            self.assertEqual(payload["progress_cycle_count_o"], 56)
            self.assertEqual(payload["progress_signature_o"], 0xABCDEF01)
            self.assertEqual(payload["toggle_bitmap_word0_o"], 11)
            self.assertEqual(payload["toggle_bitmap_word1_o"], 22)
            self.assertEqual(payload["toggle_bitmap_word2_o"], 33)
            self.assertTrue(calls[0][1].endswith("run_tlul_slice_host_probe.py"))
            self.assertIn("--post-reset-cycles", calls[0])
            self.assertIn("120", calls[0])
            self.assertIn("cfg_req_valid_pct_i=92", calls[0])
            self.assertTrue(calls[1][1].endswith("run_vl_hybrid.py"))


if __name__ == "__main__":
    unittest.main()
