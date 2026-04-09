#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "bootstrap_hybrid_rtlmeter_design_cc.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class BootstrapHybridRtlmeterDesignCcTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("bootstrap_hybrid_rtlmeter_design_cc_test", MODULE_PATH)

    def test_builds_verilator_command_from_compile_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            out_dir = root / "out"
            json_out = root / "bootstrap.json"
            verilator = root / "verilator"
            verilator.write_text("#!/bin/sh\n", encoding="utf-8")
            verilator.chmod(0o755)

            src_dir = root / "src"
            inc_dir = root / "inc"
            src_dir.mkdir()
            inc_dir.mkdir()
            (src_dir / "tb.sv").write_text("module demo_tb; endmodule\n", encoding="utf-8")
            (src_dir / "helper.sv").write_text("module helper; endmodule\n", encoding="utf-8")
            (inc_dir / "defs.svh").write_text("`define FOO 1\n", encoding="utf-8")
            (src_dir / "helper.cpp").write_text('#include "helper.h"\nint helper() { return DEMO_CPP; }\n', encoding="utf-8")
            (inc_dir / "helper.h").write_text("#pragma once\n", encoding="utf-8")

            compile_desc = types.SimpleNamespace(
                design="XuanTie-E902",
                config="gpu_cov_gate",
                topModule="demo_tb",
                verilatorArgs=["--timing", "--autoflush"],
                verilogSourceFiles=[str(src_dir / "tb.sv"), str(src_dir / "helper.sv")],
                verilogIncludeFiles=[str(inc_dir / "defs.svh")],
                verilogDefines={"DEMO": 1},
                cppSourceFiles=[str(src_dir / "helper.cpp")],
                cppIncludeFiles=[str(inc_dir / "helper.h")],
                cppDefines={"DEMO_CPP": 7},
            )

            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "Vdemo_tb_classes.mk").write_text("# fake mk\n", encoding="utf-8")
                return mock.Mock(returncode=0, stdout="", stderr="")

            with mock.patch.object(self.module, "_load_compile_descriptor", return_value=compile_desc):
                with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                    rc = self.module.main(
                        [
                            "--compile-case",
                            "XuanTie-E902:gpu_cov_gate",
                            "--out-dir",
                            str(out_dir),
                            "--json-out",
                            str(json_out),
                            "--verilator",
                            str(verilator),
                        ]
                    )

            self.assertEqual(rc, 0)
            self.assertEqual(len(calls), 1)
            cmd = calls[0]
            self.assertIn("--cc", cmd)
            self.assertIn("--top-module", cmd)
            self.assertIn("demo_tb", cmd)
            self.assertIn("+define+DEMO=1", cmd)
            self.assertTrue(any(arg.startswith("+incdir+") for arg in cmd))
            self.assertIn("-f", cmd)
            self.assertIn(str((src_dir / "helper.cpp").resolve()), cmd)
            self.assertIn("-CFLAGS", cmd)
            self.assertIn(f"-I{src_dir.resolve()}", cmd)
            self.assertIn(f"-I{inc_dir.resolve()}", cmd)
            self.assertIn("-DDEMO_CPP=7", cmd)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["design"], "XuanTie-E902")
            self.assertEqual(payload["cpp_source_count"], 1)
            self.assertEqual(payload["cpp_include_count"], 1)

    def test_reports_descriptor_load_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            json_out = root / "bootstrap.json"
            verilator = root / "verilator"
            verilator.write_text("#!/bin/sh\n", encoding="utf-8")
            verilator.chmod(0o755)

            with mock.patch.object(self.module, "_load_compile_descriptor", side_effect=RuntimeError("bad descriptor")):
                rc = self.module.main(
                    [
                        "--compile-case",
                        "XuanTie-E902:gpu_cov_gate",
                        "--json-out",
                        str(json_out),
                        "--verilator",
                        str(verilator),
                    ]
                )

            self.assertEqual(rc, 1)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "error")
            self.assertIn("failed to load compile descriptor", payload["error"])


if __name__ == "__main__":
    unittest.main()
