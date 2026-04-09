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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_veer_eh2_cpu_baseline_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunVeeREH2CpuBaselineValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_veer_eh2_cpu_baseline_validation_test", MODULE_PATH)

    def test_runner_delegates_to_enrollment_common(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            template = root / "template.json"
            program_hex = root / "program.hex"
            json_out = root / "baseline.json"
            template.write_text(
                json.dumps(
                    {
                        "status": "candidate_non_opentitan_single_surface",
                        "enrollment": {
                            "slug": "veer_eh2",
                            "mdir_name": "veer_eh2_gpu_cov_vl",
                            "runtime_input_type": "program_hex",
                            "runtime_input_path": "unused",
                        },
                        "runner_args_template": {
                            "top_module": "veer_eh2_gpu_cov_tb",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            program_hex.write_text("@00000000\nAA\n", encoding="utf-8")

            with mock.patch.object(
                self.module,
                "ensure_runtime_input",
                return_value=({"program_entries_bin": str(root / "program_entries.bin")}, ["-DTEST=1"]),
            ) as ensure_mock, mock.patch.object(
                self.module,
                "run_cpu_baseline_validation",
                return_value={"status": "ok"},
            ) as run_mock:
                rc = self.module.main(
                    [
                        "--mdir",
                        str(mdir),
                        "--template",
                        str(template),
                        "--program-hex",
                        str(program_hex),
                        "--json-out",
                        str(json_out),
                    ]
                )

            self.assertEqual(rc, 0)
            ensure_mock.assert_called_once()
            self.assertEqual(ensure_mock.call_args.kwargs["runtime_input_type"], "program_hex")
            self.assertEqual(ensure_mock.call_args.kwargs["runtime_input_path"], program_hex.resolve())
            run_mock.assert_called_once()
            self.assertEqual(run_mock.call_args.kwargs["slug"], "veer_eh2")
            self.assertEqual(run_mock.call_args.kwargs["json_out"], json_out.resolve())


if __name__ == "__main__":
    unittest.main()
