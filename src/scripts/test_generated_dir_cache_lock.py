#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path("/home/takatodo/GEM_try/out/opentitan_tlul_fifo_sync_trace_gpu_campaign_100k")
BASELINE_MODULE_PATH = ROOT / "opentitan_support" / "run_opentitan_tlul_slice_gpu_baseline.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class GeneratedDirCacheLockTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("slice_baseline_cache_lock", BASELINE_MODULE_PATH)

    def test_generated_dir_lock_path_is_slice_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = Path(tmpdir)
            lock_path = self.module._generated_dir_lock_path(cache_root, "edn_main_sm")
            self.assertEqual(lock_path, cache_root / ".edn_main_sm.generated_dir.lock")

    def test_ensure_generated_dir_uses_exclusive_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_root = Path(tmpdir)
            slice_root = cache_root / "edn_main_sm"
            fused_dir = slice_root / "fused"
            fused_dir.mkdir(parents=True)
            required_names = [
                "kernel_generated.api.h",
                "kernel_generated.link.cu",
                "kernel_generated.full_all.cu",
                "kernel_generated.part0.cu",
                "kernel_generated.cluster0.cu",
                "kernel_generated.full_all.circt_driver.cpp",
                "kernel_generated.full_all.circt.cubin",
            ]
            for name in required_names:
                (fused_dir / name).write_text("// ready\n", encoding="utf-8")
            (slice_root / self.module.GENERATED_DIR_CACHE_ABI_MARKER).write_text(
                "abi\n",
                encoding="utf-8",
            )

            with mock.patch.object(self.module.fcntl, "flock") as flock_mock:
                result = self.module._ensure_generated_dir(
                    slice_name="edn_main_sm",
                    cache_root=cache_root,
                    rebuild=False,
                    emit_hsaco=False,
                    gfx_arch="gfx1201",
                )

            self.assertEqual(result, fused_dir)
            self.assertTrue(flock_mock.called)
            self.assertEqual(flock_mock.call_args_list[0].args[1], self.module.fcntl.LOCK_EX)
            self.assertEqual(flock_mock.call_args_list[-1].args[1], self.module.fcntl.LOCK_UN)


if __name__ == "__main__":
    unittest.main()
