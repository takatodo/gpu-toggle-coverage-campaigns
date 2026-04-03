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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "build_vl_gpu.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class BuildVlGpuContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("build_vl_gpu_contract_test", MODULE_PATH)

    def _make_fake_mdir(self, tmpdir: str) -> Path:
        mdir = Path(tmpdir)
        prefix = "Vfake"
        (mdir / f"{prefix}_classes.mk").write_text(
            "\n".join(
                [
                    "VM_CLASSES_FAST += Vfake \\",
                    "  Vfake___024root__0",
                    "VM_CLASSES_SLOW += Vfake___024root__Slow",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        for stem in ("Vfake", "Vfake___024root__0", "Vfake___024root__Slow"):
            (mdir / f"{stem}.cpp").write_text("// fake cpp\n", encoding="utf-8")
            (mdir / f"{stem}.ll").write_text(f"; fake ll for {stem}\n", encoding="utf-8")
        (mdir / "merged.ll").write_text("; linked fake module\n", encoding="utf-8")
        return mdir

    def _fake_run(self, calls: list[list[str]]):
        def _impl(cmd: list, **kwargs) -> None:
            argv = [str(item) for item in cmd]
            calls.append(argv)

            for item in argv:
                if item.startswith("--analyze-phases-json="):
                    phase_json = Path(item.split("=", 1)[1])
                    phase_json.write_text(
                        json.dumps(
                            {
                                "schema_version": 1,
                                "eval_function": "_Zfake_eval",
                                "phases": {
                                    "ico_sequent": {
                                        "any_defined_in_module": True,
                                        "any_reachable_from_eval": True,
                                        "functions": [
                                            {"name": "_Zfake_ico", "reachable": True},
                                        ],
                                    },
                                    "nba_comb": {
                                        "any_defined_in_module": True,
                                        "any_reachable_from_eval": True,
                                        "functions": [
                                            {"name": "_Zfake_nba_comb", "reachable": True},
                                        ],
                                    },
                                    "nba_sequent": {
                                        "any_defined_in_module": True,
                                        "any_reachable_from_eval": True,
                                        "functions": [
                                            {"name": "_Zfake_nba_seq", "reachable": True},
                                        ],
                                    },
                                },
                            },
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )

                if item.startswith("--kernel-manifest-out="):
                    manifest_path = Path(item.split("=", 1)[1])
                    manifest_path.write_text(
                        json.dumps(
                            {
                                "schema_version": 1,
                                "kernel_split": "phases",
                                "kernels": [
                                    {"name": "vl_nba_seg0_batch_gpu", "selector": "__seg0"},
                                    {"name": "vl_nba_seg1_batch_gpu", "selector": "__seg1"},
                                    {"name": "vl_nba_seg2_batch_gpu", "selector": "__seg2"},
                                    {"name": "vl_nba_seg3_batch_gpu", "selector": "__seg3"},
                                ],
                                "launch_sequence": [
                                    "vl_nba_seg0_batch_gpu",
                                    "vl_nba_seg1_batch_gpu",
                                    "vl_nba_seg2_batch_gpu",
                                    "vl_nba_seg3_batch_gpu",
                                ],
                            },
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )

                if item.startswith("--out="):
                    Path(item.split("=", 1)[1]).write_text("; generated gpu ll\n", encoding="utf-8")

            if "-o" in argv:
                out_path = Path(argv[argv.index("-o") + 1])
                payload = b"fake-cubin" if out_path.suffix == ".cubin" else b"; fake artifact\n"
                out_path.write_bytes(payload)

        return _impl

    def test_analyze_phases_writes_json_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = self._make_fake_mdir(tmpdir)
            calls: list[list[str]] = []
            with mock.patch.object(self.module, "detect_storage_size", return_value=2112):
                with mock.patch.object(self.module, "run", side_effect=self._fake_run(calls)):
                    cubin, storage_size = self.module.build_vl_gpu(mdir, analyze_phases=True)

            self.assertEqual(storage_size, 2112)
            self.assertTrue(cubin.is_file())
            phase_json = mdir / "vl_phase_analysis.json"
            self.assertTrue(phase_json.is_file())

            payload = json.loads(phase_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertIn("eval_function", payload)
            self.assertEqual(
                sorted(payload["phases"].keys()),
                ["ico_sequent", "nba_comb", "nba_sequent"],
            )
            self.assertTrue(payload["phases"]["ico_sequent"]["any_reachable_from_eval"])

            analyze_calls = [argv for argv in calls if "--analyze-phases" in argv]
            self.assertEqual(len(analyze_calls), 1)
            self.assertTrue(
                any(arg.startswith("--analyze-phases-json=") for arg in analyze_calls[0]),
            )

    def test_kernel_split_copies_manifest_launch_sequence_into_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = self._make_fake_mdir(tmpdir)
            calls: list[list[str]] = []
            with mock.patch.object(self.module, "detect_storage_size", return_value=2112):
                with mock.patch.object(self.module, "run", side_effect=self._fake_run(calls)):
                    cubin, storage_size = self.module.build_vl_gpu(mdir, kernel_split_phases=True)

            self.assertEqual(storage_size, 2112)
            self.assertTrue(cubin.is_file())

            meta_path = mdir / "vl_batch_gpu.meta.json"
            self.assertTrue(meta_path.is_file())
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(meta["storage_size"], 2112)
            self.assertEqual(
                meta["launch_sequence"],
                [
                    "vl_nba_seg0_batch_gpu",
                    "vl_nba_seg1_batch_gpu",
                    "vl_nba_seg2_batch_gpu",
                    "vl_nba_seg3_batch_gpu",
                ],
            )
            self.assertEqual((mdir / ".vl_gpu_kernel_split").read_text(encoding="utf-8"), "phases")

            vg_calls = [argv for argv in calls if any(arg.startswith("--out=") for arg in argv)]
            self.assertEqual(len(vg_calls), 1)
            self.assertIn("--kernel-split=phases", vg_calls[0])
            self.assertTrue(
                any(arg.startswith("--kernel-manifest-out=") for arg in vg_calls[0]),
            )


if __name__ == "__main__":
    unittest.main()
