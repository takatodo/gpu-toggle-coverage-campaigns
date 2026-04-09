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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "run_tlul_fifo_sync_cpu_replay_host_probe.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunTlulFifoSyncCpuReplayHostProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_tlul_fifo_sync_cpu_replay_host_probe_test", MODULE_PATH)

    def test_runner_builds_binary_applies_template_defaults_and_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            (mdir / "Vtlul_fifo_sync_gpu_cov_cpu_replay_tb.mk").write_text("# fake mk\n", encoding="utf-8")
            template = root / "template.json"
            template.write_text(
                json.dumps(
                    {
                        "runner_args_template": {
                            "batch_length": 12,
                            "driver_defaults": {
                                "req_valid_pct": 92,
                                "source_mask": "0x3f",
                            },
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            binary_out = root / "probe.bin"
            json_out = root / "probe.json"
            state_out = root / "state.bin"
            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                if argv[0] == "make":
                    (mdir / "libVtlul_fifo_sync_gpu_cov_cpu_replay_tb.a").write_bytes(b"fake-top")
                    (mdir / "libverilated.a").write_bytes(b"fake-verilated")
                    return None
                if argv[0] == "g++":
                    Path(argv[argv.index("-o") + 1]).write_bytes(b"fake-probe")
                    return None
                self.assertEqual(argv[0], str(binary_out))
                return mock.Mock(
                    stdout=json.dumps(
                        {
                            "target": "tlul_fifo_sync_cpu_replay",
                            "wrapper_top": "tlul_fifo_sync_gpu_cov_cpu_replay_tb",
                            "constructor_ok": True,
                            "field_offsets": {"done_o": 4},
                            "field_sizes": {"done_o": 1},
                            "watch_field_names": ["direct_req_done_q"],
                            "root_size": 1024,
                            "done_o": 0,
                        }
                    )
                    + "\n"
                )

            argv = [
                "run_tlul_fifo_sync_cpu_replay_host_probe.py",
                "--mdir",
                str(mdir),
                "--template",
                str(template),
                "--binary-out",
                str(binary_out),
                "--json-out",
                str(json_out),
                "--state-out",
                str(state_out),
                "--clock-cycles",
                "8",
                "--set",
                "cfg_seed=7",
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    self.module.main()

            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["target"], "tlul_fifo_sync_cpu_replay")
            self.assertEqual(payload["clock_ownership"], "tb_timed_coroutine")
            self.assertEqual(payload["probe_kind"], "no_port_cpu_replay_wrapper")
            self.assertEqual(payload["configured_inputs"]["cfg_valid"], 1)
            self.assertEqual(payload["configured_inputs"]["cfg_batch_length"], 12)
            self.assertEqual(payload["configured_inputs"]["cfg_req_valid_pct"], 92)
            self.assertEqual(payload["configured_inputs"]["cfg_source_mask"], 0x3F)
            self.assertEqual(payload["configured_inputs"]["cfg_seed"], 7)
            self.assertEqual(calls[0][0], "make")
            self.assertEqual(calls[1][0], "g++")
            self.assertEqual(calls[2][0], str(binary_out))
            self.assertIn("--clock-cycles", calls[2])
            self.assertIn("--state-out", calls[2])
            self.assertIn("--set", calls[2])


if __name__ == "__main__":
    unittest.main()
