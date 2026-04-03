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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "run_vl_hybrid.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunVlHybridContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_vl_hybrid_contract_test", MODULE_PATH)

    def test_mdir_launch_sequence_is_forwarded_to_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            (mdir / "vl_batch_gpu.cubin").write_bytes(b"fake-cubin")
            (mdir / "vl_batch_gpu.meta.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "cubin": "vl_batch_gpu.cubin",
                        "storage_size": 2112,
                        "launch_sequence": [
                            "vl_nba_seg0_batch_gpu",
                            "vl_nba_seg1_batch_gpu",
                            "vl_nba_seg3_batch_gpu",
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            hybrid_bin = root / "run_vl_hybrid"
            hybrid_bin.write_text("#!/bin/sh\n", encoding="utf-8")

            seen: dict[str, object] = {}

            def _fake_run(cmd: list[str], check: bool, env: dict[str, str]) -> None:
                seen["cmd"] = list(cmd)
                seen["check"] = check
                seen["env"] = dict(env)

            argv = [
                "run_vl_hybrid.py",
                "--mdir",
                str(mdir),
                "--nstates",
                "128",
                "--steps",
                "3",
                "--init-state",
                str(root / "init.bin"),
                "--dump-state",
                str(root / "state.bin"),
                "--patch",
                "4:0xff",
            ]
            with mock.patch.object(self.module, "HYBRID_BIN", hybrid_bin):
                with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                    with mock.patch.object(sys, "argv", argv):
                        self.module.main()

            self.assertEqual(
                seen["cmd"],
                [
                    str(hybrid_bin),
                    str((mdir / "vl_batch_gpu.cubin").resolve()),
                    "2112",
                    "128",
                    "256",
                    "3",
                    "4:0xff",
                ],
            )
            self.assertTrue(seen["check"])
            env = seen["env"]
            assert isinstance(env, dict)
            self.assertEqual(
                env["RUN_VL_HYBRID_KERNELS"],
                "vl_nba_seg0_batch_gpu,vl_nba_seg1_batch_gpu,vl_nba_seg3_batch_gpu",
            )
            self.assertEqual(env["RUN_VL_HYBRID_INIT_STATE"], str((root / "init.bin").resolve()))
            self.assertEqual(env["RUN_VL_HYBRID_DUMP_STATE"], str((root / "state.bin").resolve()))

    def test_kernel_override_takes_precedence_over_meta_launch_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            (mdir / "vl_batch_gpu.cubin").write_bytes(b"fake-cubin")
            (mdir / "vl_batch_gpu.meta.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "cubin": "vl_batch_gpu.cubin",
                        "storage_size": 2112,
                        "launch_sequence": ["vl_meta_only_gpu"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            hybrid_bin = root / "run_vl_hybrid"
            hybrid_bin.write_text("#!/bin/sh\n", encoding="utf-8")

            seen: dict[str, object] = {}

            def _fake_run(cmd: list[str], check: bool, env: dict[str, str]) -> None:
                seen["env"] = dict(env)

            argv = [
                "run_vl_hybrid.py",
                "--mdir",
                str(mdir),
                "--kernels",
                "vl_ico_batch_gpu,vl_nba_comb_batch_gpu",
            ]
            with mock.patch.object(self.module, "HYBRID_BIN", hybrid_bin):
                with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                    with mock.patch.object(sys, "argv", argv):
                        self.module.main()

            env = seen["env"]
            assert isinstance(env, dict)
            self.assertEqual(env["RUN_VL_HYBRID_KERNELS"], "vl_ico_batch_gpu,vl_nba_comb_batch_gpu")


if __name__ == "__main__":
    unittest.main()
