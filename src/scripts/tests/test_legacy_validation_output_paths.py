#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent.parent
VEER_MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_veer_family_gpu_toggle_validation.py"
XUANTIE_MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_xuantie_family_gpu_toggle_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class LegacyValidationOutputPathsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.veer = _load_module("veer_validation_test", VEER_MODULE_PATH)
        self.xuantie = _load_module("xuantie_validation_test", XUANTIE_MODULE_PATH)

    def test_veer_defaults_to_output_legacy_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir) / "work"
            seen: dict[str, Path] = {}

            def _fake_run(*args, **kwargs):
                return mock.Mock(returncode=0, stderr="", stdout="")

            def _fake_write_json(path: Path, payload: dict):
                seen["path"] = path
                seen["payload"] = payload

            with mock.patch.object(self.veer, "_run", side_effect=_fake_run):
                with mock.patch.object(self.veer, "_write_json", side_effect=_fake_write_json):
                    rc = self.veer.main(["--work-dir", str(work_dir), "--design", "VeeR-EL2"])

            self.assertEqual(rc, 0)
            self.assertEqual(
                seen["path"],
                (self.veer.DEFAULT_STATUS_DIR / "veer_family_gpu_toggle_validation.json").resolve(),
            )
            self.assertEqual(seen["payload"]["status_surface"], "legacy_sim_accel")

    def test_xuantie_defaults_to_output_legacy_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            work_dir = Path(tmpdir) / "work"
            seen: dict[str, Path] = {}

            def _fake_run(*args, **kwargs):
                return mock.Mock(returncode=0, stderr="", stdout="")

            def _fake_write_json(path: Path, payload: dict):
                seen["path"] = path
                seen["payload"] = payload

            with mock.patch.object(self.xuantie, "_run", side_effect=_fake_run):
                with mock.patch.object(self.xuantie, "_write_json", side_effect=_fake_write_json):
                    rc = self.xuantie.main(["--work-dir", str(work_dir), "--design", "XuanTie-E902"])

            self.assertEqual(rc, 0)
            self.assertEqual(
                seen["path"],
                (
                    self.xuantie.DEFAULT_STATUS_DIR / "xuantie_family_gpu_toggle_validation.json"
                ).resolve(),
            )
            self.assertEqual(seen["payload"]["status_surface"], "legacy_sim_accel")

    def test_write_json_creates_parent_directory_for_veer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "nested" / "veer.json"
            self.veer._write_json(json_path, {"ok": True})
            self.assertTrue(json_path.is_file())

    def test_write_json_creates_parent_directory_for_xuantie(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "nested" / "xuantie.json"
            self.xuantie._write_json(json_path, {"ok": True})
            self.assertTrue(json_path.is_file())


if __name__ == "__main__":
    unittest.main()
