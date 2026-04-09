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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_openpiton_cpu_baseline_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunOpenPitonCpuBaselineValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_openpiton_cpu_baseline_validation_test", MODULE_PATH)

    def test_runner_delegates_to_enrollment_common(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            template = root / "template.json"
            mem_bin = root / "mem.bin"
            json_out = root / "baseline.json"
            template.write_text(
                json.dumps(
                    {
                        "status": "candidate_non_opentitan_single_surface",
                        "enrollment": {
                            "slug": "openpiton",
                            "mdir_name": "openpiton_gpu_cov_vl",
                            "runtime_input_type": "memory_image",
                            "runtime_input_path": "unused",
                            "runtime_input_format": "bin",
                            "runtime_input_target": {
                                "kind": "memory-array-preload-v1",
                                "target_path": "openpiton_gpu_cov_tb.dut.visible_mem",
                                "word_bits": 64,
                                "depth": 2048,
                                "base_addr": 0,
                                "address_unit_bytes": 8,
                                "endianness": "little",
                            },
                            "runtime_input_patch_bytes": [
                                {"offset": 1664, "value": 1, "width_bytes": 8}
                            ],
                        },
                        "runner_args_template": {
                            "top_module": "openpiton_gpu_cov_tb",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            mem_bin.write_bytes(b"\x00" * 16)

            with mock.patch.object(
                self.module,
                "ensure_runtime_input",
                return_value=({"memory_image": str(mem_bin), "memory_image_target": str(template)}, []),
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
                        "--mem-bin",
                        str(mem_bin),
                        "--json-out",
                        str(json_out),
                    ]
                )

            self.assertEqual(rc, 0)
            ensure_mock.assert_called_once()
            self.assertEqual(ensure_mock.call_args.kwargs["runtime_input_type"], "memory_image")
            self.assertEqual(ensure_mock.call_args.kwargs["runtime_input_path"], mem_bin.resolve())
            self.assertEqual(ensure_mock.call_args.kwargs["runtime_input_patch_bytes"][0]["value"], 1)
            run_mock.assert_called_once()
            self.assertEqual(run_mock.call_args.kwargs["slug"], "openpiton")
            self.assertEqual(run_mock.call_args.kwargs["json_out"], json_out.resolve())


if __name__ == "__main__":
    unittest.main()
