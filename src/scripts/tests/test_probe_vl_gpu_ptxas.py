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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "probe_vl_gpu_ptxas.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ProbeVlGpuPtxasTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("probe_vl_gpu_ptxas_test", MODULE_PATH)

    def test_main_writes_timeout_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ptx = root / "demo.ptx"
            cubin = root / "demo.cubin"
            json_out = root / "probe.json"
            ptx.write_text("// ptx\n", encoding="utf-8")

            def _fake_run(*args, **kwargs):
                raise subprocess.TimeoutExpired(
                    cmd=kwargs.get("args", args[0] if args else ["ptxas"]),
                    timeout=90,
                    output="partial stdout\n",
                    stderr="partial stderr\n",
                )

            import subprocess

            argv = [
                "probe_vl_gpu_ptxas.py",
                "--ptx",
                str(ptx),
                "--cubin-out",
                str(cubin),
                "--opt-level",
                "1",
                "--timeout-seconds",
                "90",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "probe_vl_gpu_ptxas")
            self.assertEqual(payload["status"], "timed_out")
            self.assertEqual(payload["opt_level"], 1)
            self.assertEqual(payload["timeout_seconds"], 90)
            self.assertFalse(payload["cubin_exists"])
            self.assertFalse(payload["compile_only"])

    def test_main_writes_compile_only_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ptx = root / "demo.ptx"
            obj = root / "demo.o"
            json_out = root / "probe.json"
            ptx.write_text("// ptx\n", encoding="utf-8")

            import subprocess

            def _fake_run(*args, **kwargs):
                output_path = Path(args[0][-1])
                output_path.write_bytes(b"\x7fELF")
                return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

            argv = [
                "probe_vl_gpu_ptxas.py",
                "--ptx",
                str(ptx),
                "--cubin-out",
                str(obj),
                "--opt-level",
                "0",
                "--compile-only",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "probe_vl_gpu_ptxas")
            self.assertEqual(payload["status"], "ok")
            self.assertTrue(payload["compile_only"])
            self.assertEqual(payload["output_kind"], "relocatable_object")
            self.assertTrue(payload["output_exists"])


if __name__ == "__main__":
    unittest.main()
