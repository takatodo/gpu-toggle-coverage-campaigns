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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "probe_vl_hybrid_stack_limit.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ProbeVlHybridStackLimitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("probe_vl_hybrid_stack_limit_test", MODULE_PATH)

    def test_parse_trace_detects_updated_and_failed_limits(self) -> None:
        updated = self.module._parse_trace(
            "\n".join(
                [
                    "run_vl_hybrid: stage=after_cuModuleLoad",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=523712",
                    "run_vl_hybrid: ctx_limit STACK_SIZE updated=523712",
                ]
            )
        )
        failed = self.module._parse_trace(
            "\n".join(
                [
                    "run_vl_hybrid: stage=after_cuModuleLoad",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument",
                ]
            )
        )

        self.assertEqual(updated["status"], "stack_limit_updated")
        self.assertEqual(updated["updated_limit"], 523712)
        self.assertEqual(failed["status"], "stack_limit_invalid_argument")
        self.assertEqual(failed["set_failed_target"], 564320)

    def test_build_payload_summarizes_ceiling_and_launch_result(self) -> None:
        payload = self.module.build_payload(
            hybrid_bin=Path("/tmp/run_vl_hybrid"),
            cubin=Path("/tmp/vl_batch_gpu.cubin"),
            storage_bytes=3128704,
            nstates=1,
            block_size=32,
            steps=1,
            candidate_results=[
                {
                    "probe_only": True,
                    "returncode": 0,
                    "updated_limit": 523712,
                    "stack_limit_override": 523712,
                    "status": "stack_limit_updated",
                },
                {
                    "probe_only": True,
                    "returncode": 1,
                    "updated_limit": None,
                    "stack_limit_override": 564320,
                    "status": "stack_limit_invalid_argument",
                },
            ],
            launch_at_max={
                "probe_only": False,
                "returncode": 1,
                "status": "invalid_argument",
                "last_stage": "before_first_kernel_launch",
                "updated_limit": 523712,
                "stack_limit_override": 523712,
            },
        )

        self.assertEqual(payload["max_accepted_stack_limit"], 523712)
        self.assertEqual(payload["min_rejected_stack_limit_target"], 564320)
        self.assertEqual(payload["launch_at_max_result"]["status"], "invalid_argument")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            hybrid_bin = root / "run_vl_hybrid"
            cubin = root / "vl_batch_gpu.cubin"
            json_out = root / "probe.json"
            hybrid_bin.write_text("", encoding="utf-8")
            cubin.write_text("", encoding="utf-8")

            results = [
                subprocess_completed(stdout="run_vl_hybrid: ctx_limit STACK_SIZE updated=523712\n", returncode=0),
                subprocess_completed(
                    stdout="run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument\n",
                    returncode=1,
                ),
                subprocess_completed(
                    stdout="\n".join(
                        [
                            "run_vl_hybrid: ctx_limit STACK_SIZE updated=523712",
                            "run_vl_hybrid: stage=before_first_kernel_launch",
                            "run_vl_hybrid.c:555 CUDA error 1: invalid argument",
                        ]
                    )
                    + "\n",
                    returncode=1,
                ),
            ]

            argv = [
                "probe_vl_hybrid_stack_limit.py",
                "--hybrid-bin",
                str(hybrid_bin),
                "--cubin",
                str(cubin),
                "--storage-bytes",
                "3128704",
                "--candidates",
                "523712,564320",
                "--launch-at-max",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=results):
                with mock.patch.object(sys, "argv", argv):
                    rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["max_accepted_stack_limit"], 523712)
            self.assertEqual(payload["min_rejected_stack_limit_target"], 564320)
            self.assertEqual(payload["launch_at_max_result"]["last_stage"], "before_first_kernel_launch")


def subprocess_completed(*, stdout: str, returncode: int):
    cp = mock.Mock()
    cp.stdout = stdout
    cp.stderr = ""
    cp.returncode = returncode
    return cp


if __name__ == "__main__":
    unittest.main()
