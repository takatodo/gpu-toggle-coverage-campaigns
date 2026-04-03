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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "run_socket_m1_host_gpu_flow.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunSocketM1HostGpuFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_socket_m1_host_gpu_flow_test", MODULE_PATH)

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
                if argv[1].endswith("run_socket_m1_host_probe.py"):
                    host_report = Path(argv[argv.index("--json-out") + 1])
                    host_state = Path(argv[argv.index("--state-out") + 1])
                    host_report.write_text("{\"abi_ok\": true}\n", encoding="utf-8")
                    host_state.write_bytes(b"\x00" * 2112)
                    return None
                final_state = Path(argv[argv.index("--dump-state") + 1])
                blob = bytearray(2112)
                blob[1] = 1
                blob[196:200] = (0x12345678).to_bytes(4, "little")
                blob[296:300] = (11).to_bytes(4, "little")
                blob[300:304] = (22).to_bytes(4, "little")
                blob[304:308] = (33).to_bytes(4, "little")
                final_state.write_bytes(blob)
                return None

            argv = [
                "run_socket_m1_host_gpu_flow.py",
                "--mdir",
                str(mdir),
                "--nstates",
                "32",
                "--steps",
                "2",
                "--patch",
                "4:0xff",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    self.module.main()

            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["target"], "tlul_socket_m1")
            self.assertEqual(payload["clock_ownership"], "tb_timed_coroutine")
            self.assertEqual(payload["nstates"], 32)
            self.assertEqual(payload["steps"], 2)
            self.assertEqual(payload["done_o"], 1)
            self.assertEqual(payload["cfg_signature_o"], 0x12345678)
            self.assertEqual(payload["toggle_bitmap_word0_o"], 11)
            self.assertEqual(payload["toggle_bitmap_word1_o"], 22)
            self.assertEqual(payload["toggle_bitmap_word2_o"], 33)
            self.assertEqual(payload["patches"], ["4:0xff"])
            self.assertTrue(calls[0][1].endswith("run_socket_m1_host_probe.py"))
            self.assertIn("--state-out", calls[0])
            self.assertTrue(calls[1][1].endswith("run_vl_hybrid.py"))
            self.assertIn("--init-state", calls[1])
            self.assertIn("--dump-state", calls[1])


if __name__ == "__main__":
    unittest.main()
