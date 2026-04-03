#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "run_socket_m1_host_probe.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunSocketM1HostProbeContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_socket_m1_host_probe_contract_test", MODULE_PATH)

    def test_build_and_run_writes_json_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            mk = mdir / "Vtlul_socket_m1_gpu_cov_tb.mk"
            mk.write_text("# fake mk\n", encoding="utf-8")
            binary_out = mdir / "probe.bin"
            json_out = mdir / "probe.json"

            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                if argv[0] == "make":
                    (mdir / "libVtlul_socket_m1_gpu_cov_tb.a").write_bytes(b"fake-top")
                    (mdir / "libverilated.a").write_bytes(b"fake-verilated")
                    return None
                if argv[0] == "g++":
                    out_path = Path(argv[argv.index("-o") + 1])
                    out_path.write_bytes(b"fake-probe")
                    return None
                self.assertEqual(argv[0], str(binary_out))
                return mock.Mock(stdout="{\"abi_ok\": true}\n")

            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "run_socket_m1_host_probe.py",
                        "--mdir",
                        str(mdir),
                        "--binary-out",
                        str(binary_out),
                        "--json-out",
                        str(json_out),
                        "--state-out",
                        str(mdir / "state.bin"),
                        "--reset-cycles",
                        "7",
                        "--post-reset-cycles",
                        "3",
                        "--batch-length",
                        "2",
                        "--seed",
                        "9",
                    ],
                ):
                    self.module.main()

            self.assertTrue(binary_out.is_file())
            self.assertEqual(json_out.read_text(encoding="utf-8"), "{\"abi_ok\": true}\n")
            self.assertEqual(calls[0][:4], ["make", "-C", str(mdir), "-f"])
            self.assertIn("libVtlul_socket_m1_gpu_cov_tb", calls[0])
            self.assertEqual(calls[1][0], "g++")
            self.assertIn(str(self.module.PROBE_SOURCE), calls[1])
            self.assertEqual(
                calls[2],
                [
                    str(binary_out),
                    "--reset-cycles",
                    "7",
                    "--post-reset-cycles",
                    "3",
                    "--batch-length",
                    "2",
                    "--seed",
                    "9",
                    "--cfg-valid",
                    "1",
                    "--state-out",
                    str((mdir / "state.bin").resolve()),
                ],
            )

    def test_build_only_skips_probe_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            mk = mdir / "Vtlul_socket_m1_gpu_cov_tb.mk"
            mk.write_text("# fake mk\n", encoding="utf-8")
            binary_out = mdir / "probe.bin"
            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                if argv[0] == "make":
                    (mdir / "libVtlul_socket_m1_gpu_cov_tb.a").write_bytes(b"fake-top")
                    (mdir / "libverilated.a").write_bytes(b"fake-verilated")
                    return None
                out_path = Path(argv[argv.index("-o") + 1])
                out_path.write_bytes(b"fake-probe")
                return None

            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "run_socket_m1_host_probe.py",
                        "--mdir",
                        str(mdir),
                        "--binary-out",
                        str(binary_out),
                        "--build-only",
                    ],
                ):
                    self.module.main()

            self.assertTrue(binary_out.is_file())
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][0], "make")
            self.assertEqual(calls[1][0], "g++")


if __name__ == "__main__":
    unittest.main()
