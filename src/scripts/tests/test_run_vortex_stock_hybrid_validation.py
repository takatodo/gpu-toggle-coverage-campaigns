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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_vortex_stock_hybrid_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunVortexStockHybridValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_vortex_stock_hybrid_validation_test", MODULE_PATH)

    def test_runner_delegates_to_enrollment_common(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            template = root / "template.json"
            init_bin = root / "init.bin"
            post_bin = root / "post.bin"
            dcrs_bin = root / "dcrs.bin"
            json_out = root / "validation.json"
            template.write_text(
                json.dumps(
                    {
                        "status": "candidate_non_opentitan_single_surface",
                        "enrollment": {
                            "slug": "vortex",
                            "mdir_name": "vortex_gpu_cov_vl",
                            "runtime_input_type": "runtime_file",
                            "runtime_input_path": "unused",
                            "runtime_input_name": "init.bin",
                        },
                        "runner_args_template": {
                            "gpu_nstates": 12,
                            "gpu_sequential_steps": 88,
                            "top_module": "vortex_gpu_cov_tb",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            init_bin.write_bytes(b"\x11\x22")
            post_bin.write_bytes(b"\x33\x44")
            dcrs_bin.write_bytes(b"\x55\x66")

            with mock.patch.object(
                self.module,
                "ensure_runtime_input",
                return_value=({"runtime_file": str(init_bin), "runtime_file_name": "init.bin"}, []),
            ) as ensure_mock, mock.patch.object(
                self.module,
                "run_hybrid_validation",
                return_value={"status": "ok"},
            ) as run_mock:
                rc = self.module.main(
                    [
                        "--mdir",
                        str(mdir),
                        "--template",
                        str(template),
                        "--init-bin",
                        str(init_bin),
                        "--post-bin",
                        str(post_bin),
                        "--dcrs-bin",
                        str(dcrs_bin),
                        "--json-out",
                        str(json_out),
                    ]
                )

            self.assertEqual(rc, 0)
            ensure_mock.assert_called_once()
            self.assertEqual(ensure_mock.call_args.kwargs["runtime_input_type"], "runtime_file")
            self.assertEqual(ensure_mock.call_args.kwargs["runtime_input_path"], init_bin.resolve())
            self.assertEqual(
                ensure_mock.call_args.kwargs["runtime_input_companion_paths"],
                [post_bin.resolve(), dcrs_bin.resolve()],
            )
            run_mock.assert_called_once()
            self.assertEqual(run_mock.call_args.kwargs["slug"], "vortex")
            self.assertEqual(run_mock.call_args.kwargs["nstates"], 12)
            self.assertEqual(run_mock.call_args.kwargs["steps"], 88)
            self.assertEqual(run_mock.call_args.kwargs["json_out"], json_out.resolve())


if __name__ == "__main__":
    unittest.main()
