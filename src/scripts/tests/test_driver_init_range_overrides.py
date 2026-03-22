#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
BASELINE_MODULE_PATH = SCRIPT_DIR / "run_opentitan_tlul_slice_gpu_baseline.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class DriverInitRangeOverridesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("slice_baseline_driver_range_overrides", BASELINE_MODULE_PATH)

    def test_uniform_states_emit_range_overrides_for_all_driver_keys(self) -> None:
        driver = dict(self.module.DRIVER_DEFAULTS)
        driver["req_family"] = 4
        driver["batch_length"] = 64
        with tempfile.TemporaryDirectory() as tmpdir:
            init_path = Path(tmpdir) / "gpu_driver.init"
            self.module._write_init_file(
                init_path,
                driver,
                nstates=8,
                uniform_states=True,
            )
            text = init_path.read_text(encoding="utf-8")
        self.assertIn("cfg_batch_length_i 0+8 64", text)
        self.assertIn("cfg_req_family_i 0+8 4", text)
        self.assertIn("cfg_seed_i 0+8 0x00000001", text)

    def test_nonuniform_states_emit_base_range_and_seed_overrides(self) -> None:
        driver = dict(self.module.DRIVER_DEFAULTS)
        driver["seed"] = 0x123
        with tempfile.TemporaryDirectory() as tmpdir:
            init_path = Path(tmpdir) / "gpu_driver.init"
            self.module._write_init_file(
                init_path,
                driver,
                nstates=4,
                uniform_states=False,
            )
            text = init_path.read_text(encoding="utf-8")
        self.assertIn("cfg_req_family_i 0+4 0", text)
        self.assertIn("cfg_seed_i 0+4 0x00000123", text)
        self.assertIn("cfg_seed_i 1 0x00000184", text)


if __name__ == "__main__":
    unittest.main()
