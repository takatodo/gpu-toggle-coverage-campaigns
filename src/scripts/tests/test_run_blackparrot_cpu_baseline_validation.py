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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_blackparrot_cpu_baseline_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunBlackParrotCpuBaselineValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_blackparrot_cpu_baseline_validation_test", MODULE_PATH)

    def test_runner_delegates_to_enrollment_common(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            template = root / "template.json"
            prog_mem = root / "prog.mem"
            json_out = root / "baseline.json"
            template.write_text(
                json.dumps(
                    {
                        "status": "candidate_non_opentitan_single_surface",
                        "enrollment": {
                            "slug": "blackparrot",
                            "mdir_name": "blackparrot_gpu_cov_vl",
                            "runtime_input_type": "blackparrot_prog_mem",
                            "runtime_input_path": "unused",
                            "runtime_input_target": {
                                "kind": "memory-array-preload-v1",
                                "target_path": "blackparrot_gpu_cov_tb.gpu_cov_program_words",
                                "word_bits": 64,
                                "depth": 32768,
                                "base_addr": 0,
                                "address_unit_bytes": 8,
                                "endianness": "little"
                            }
                        },
                        "runner_args_template": {
                            "top_module": "blackparrot_gpu_cov_tb"
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            prog_mem.write_text("@00000000\n11 22 33 44\n", encoding="utf-8")

            with mock.patch.object(
                self.module,
                "ensure_runtime_input",
                return_value=({"memory_image": str(prog_mem), "memory_image_target": str(template)}, []),
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
                        "--prog-mem",
                        str(prog_mem),
                        "--json-out",
                        str(json_out),
                    ]
                )

            self.assertEqual(rc, 0)
            ensure_mock.assert_called_once()
            self.assertEqual(ensure_mock.call_args.kwargs["runtime_input_type"], "blackparrot_prog_mem")
            self.assertEqual(ensure_mock.call_args.kwargs["runtime_input_path"], prog_mem.resolve())
            run_mock.assert_called_once()
            self.assertEqual(run_mock.call_args.kwargs["slug"], "blackparrot")
            self.assertEqual(run_mock.call_args.kwargs["json_out"], json_out.resolve())


if __name__ == "__main__":
    unittest.main()
