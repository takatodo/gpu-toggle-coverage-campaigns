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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "probe_vl_gpu_nvcc_device_link.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ProbeVlGpuNvccDeviceLinkTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("probe_vl_gpu_nvcc_device_link_test", MODULE_PATH)

    def test_main_writes_compile_timeout_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ptx = root / "demo.ptx"
            object_out = root / "demo.o"
            linked_out = root / "demo.cubin"
            json_out = root / "probe.json"
            ptx.write_text("// ptx\n", encoding="utf-8")

            import subprocess

            def _fake_run(*args, **kwargs):
                cmd = kwargs.get("args", args[0] if args else [])
                if cmd and cmd[0] == "nvcc":
                    raise subprocess.TimeoutExpired(
                        cmd=cmd,
                        timeout=120,
                        output="partial stdout\n",
                        stderr="partial stderr\n",
                    )
                self.fail(f"unexpected subprocess invocation: {cmd}")

            argv = [
                "probe_vl_gpu_nvcc_device_link.py",
                "--ptx",
                str(ptx),
                "--object-out",
                str(object_out),
                "--linked-out",
                str(linked_out),
                "--compile-timeout-seconds",
                "120",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "probe_vl_gpu_nvcc_device_link")
            self.assertEqual(payload["compile"]["status"], "timed_out")
            self.assertEqual(payload["link"]["status"], "skipped")
            self.assertFalse(payload["observations"]["object_exists"])

    def test_main_writes_success_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ptx = root / "demo.ptx"
            object_out = root / "demo.o"
            linked_out = root / "demo.cubin"
            json_out = root / "probe.json"
            ptx.write_text("// ptx\n", encoding="utf-8")

            import subprocess

            def _fake_run(*args, **kwargs):
                cmd = kwargs.get("args", args[0] if args else [])
                if cmd[:2] == ["cuobjdump", "--dump-elf-symbols"]:
                    return subprocess.CompletedProcess(
                        args=cmd,
                        returncode=0,
                        stdout="symbols:\nSTT_FUNC STB_GLOBAL STO_ENTRY      vl_eval_batch_gpu\n",
                        stderr="",
                    )
                if cmd and cmd[0] == "nvcc" and "--device-c" in cmd:
                    object_out.write_bytes(b"\x7fELF")
                    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
                if cmd and cmd[0] == "nvcc" and "--device-link" in cmd:
                    linked_out.write_bytes(b"\x7fELFlinked")
                    return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
                self.fail(f"unexpected subprocess invocation: {cmd}")

            argv = [
                "probe_vl_gpu_nvcc_device_link.py",
                "--ptx",
                str(ptx),
                "--object-out",
                str(object_out),
                "--linked-out",
                str(linked_out),
                "--linked-kind",
                "cubin",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["compile"]["status"], "ok")
            self.assertEqual(payload["link"]["status"], "ok")
            self.assertTrue(payload["observations"]["object_exists"])
            self.assertTrue(payload["observations"]["linked_exists"])
            self.assertTrue(payload["observations"]["linked_kernel_symbol_present"])


if __name__ == "__main__":
    unittest.main()
