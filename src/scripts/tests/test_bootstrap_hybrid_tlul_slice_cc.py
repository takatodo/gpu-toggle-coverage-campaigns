#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "bootstrap_hybrid_tlul_slice_cc.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class BootstrapHybridTlulSliceCcTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("bootstrap_hybrid_tlul_slice_cc_test", MODULE_PATH)

    def test_tb_override_adds_wrapper_source_and_top_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            out_dir = root / "out"
            verilator = root / "verilator"
            verilator.write_text("#!/bin/sh\n", encoding="utf-8")
            verilator.chmod(0o755)

            rtl = root / "tlul_fifo_sync.sv"
            default_tb = root / "tlul_fifo_sync_gpu_cov_tb.sv"
            replay_tb = root / "tlul_fifo_sync_gpu_cov_cpu_replay_tb.sv"
            extra_sv = root / "helper.sv"
            for path in (rtl, default_tb, replay_tb, extra_sv):
                path.write_text(f"module {path.stem}; endmodule\n", encoding="utf-8")

            baseline = types.SimpleNamespace(
                OPENTITAN_SRC=root,
                SLICE_EXTRA_SOURCES={"tlul_fifo_sync": []},
                _dedupe_paths=lambda paths: list(dict.fromkeys(Path(p).resolve() for p in paths)),
                _collect_compile_sources=lambda slice_name, rtl_path, tb_path: [
                    Path(rtl_path).resolve(),
                    Path(tb_path).resolve(),
                ],
            )

            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "Vtlul_fifo_sync_gpu_cov_cpu_replay_tb_classes.mk").write_text(
                    "# fake mk\n",
                    encoding="utf-8",
                )
                return mock.Mock(returncode=0)

            with mock.patch.object(self.module, "_load_baseline", return_value=baseline):
                with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                    rc = self.module.main(
                        [
                            "--slice-name",
                            "tlul_fifo_sync",
                            "--out-dir",
                            str(out_dir),
                            "--verilator",
                            str(verilator),
                            "--tb-path",
                            str(replay_tb),
                            "--top-module",
                            "tlul_fifo_sync_gpu_cov_cpu_replay_tb",
                            "--extra-source",
                            str(extra_sv),
                        ]
                    )

            self.assertEqual(rc, 0)
            self.assertEqual(len(calls), 1)
            cmd = calls[0]
            self.assertIn("--top-module", cmd)
            self.assertIn("tlul_fifo_sync_gpu_cov_cpu_replay_tb", cmd)
            self.assertIn(str(default_tb.resolve()), cmd)
            self.assertIn(str(replay_tb.resolve()), cmd)
            self.assertIn(str(extra_sv.resolve()), cmd)

    def test_cov_tb_fallback_works_when_gpu_cov_name_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            out_dir = root / "out"
            verilator = root / "verilator"
            verilator.write_text("#!/bin/sh\n", encoding="utf-8")
            verilator.chmod(0o755)

            rtl = root / "tlul_fifo_async.sv"
            cov_tb = root / "tlul_fifo_async_cov_tb.sv"
            for path in (rtl, cov_tb):
                path.write_text(f"module {path.stem}; endmodule\n", encoding="utf-8")

            baseline = types.SimpleNamespace(
                OPENTITAN_SRC=root,
                SLICE_EXTRA_SOURCES={"tlul_fifo_async": []},
                _dedupe_paths=lambda paths: list(dict.fromkeys(Path(p).resolve() for p in paths)),
                _collect_compile_sources=lambda slice_name, rtl_path, tb_path: [
                    Path(rtl_path).resolve(),
                    Path(tb_path).resolve(),
                ],
            )

            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                out_dir.mkdir(parents=True, exist_ok=True)
                (out_dir / "Vtlul_fifo_async_cov_tb_classes.mk").write_text("# fake mk\n", encoding="utf-8")
                return mock.Mock(returncode=0)

            with mock.patch.object(self.module, "_load_baseline", return_value=baseline):
                with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                    rc = self.module.main(
                        [
                            "--slice-name",
                            "tlul_fifo_async",
                            "--out-dir",
                            str(out_dir),
                            "--verilator",
                            str(verilator),
                        ]
                    )

            self.assertEqual(rc, 0)
            self.assertEqual(len(calls), 1)
            cmd = calls[0]
            self.assertIn("--top-module", cmd)
            self.assertIn("tlul_fifo_async_cov_tb", cmd)
            self.assertIn(str(cov_tb.resolve()), cmd)


if __name__ == "__main__":
    unittest.main()
