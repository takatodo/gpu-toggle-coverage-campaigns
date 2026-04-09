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

    def _make_fake_vortex_mdir(self, tmpdir: str) -> Path:
        return self._make_fake_verilated_tls_bypass_target_mdir(tmpdir, "Vvortex_gpu_cov_tb")

    def _make_fake_caliptra_mdir(self, tmpdir: str) -> Path:
        return self._make_fake_verilated_tls_bypass_target_mdir(tmpdir, "Vcaliptra_gpu_cov_tb")

    def _make_fake_verilated_tls_bypass_target_mdir(self, tmpdir: str, prefix: str) -> Path:
        mdir = Path(tmpdir)
        (mdir / f"{prefix}_classes.mk").write_text(
            f"VM_CLASSES_FAST += {prefix}\n",
            encoding="utf-8",
        )
        (mdir / f"{prefix}.cpp").write_text("// fake cpp\n", encoding="utf-8")
        patched_ir = "\n".join(
            [
                '@_ZN9Verilated3t_sE = external thread_local global %"struct.Verilated::ThreadLocal", align 8',
                'declare nonnull ptr @llvm.threadlocal.address.p0(ptr nonnull)',
                'define void @vl_eval_batch_gpu() {',
                '657:',
                '  %658 = tail call noundef align 8 ptr @llvm.threadlocal.address.p0(ptr align 8 @_ZN9Verilated3t_sE)',
                '  %659 = load ptr, ptr %658, align 8',
                '732:',
                '  %733 = call noundef align 8 ptr @llvm.threadlocal.address.p0(ptr align 8 @_ZN9Verilated3t_sE)',
                '  %734 = load ptr, ptr %733, align 8',
                '12418:',
                '  %12419 = call noundef align 8 ptr @llvm.threadlocal.address.p0(ptr align 8 @_ZN9Verilated3t_sE)',
                '  %12420 = load ptr, ptr %12419, align 8',
                '  ret void',
                '}',
                '',
            ]
        )
        (mdir / "vl_batch_gpu_patched.ll").write_text(patched_ir, encoding="utf-8")
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

                if item.startswith("--classifier-report-out="):
                    report_path = Path(item.split("=", 1)[1])
                    report_path.write_text(
                        json.dumps(
                            {
                                "schema_version": 1,
                                "eval_function": "_Zfake_eval",
                                "decl_runtime_merge_enabled": True,
                                "vl_symsp_offset": 2000,
                                "counts": {"reachable": 4, "gpu": 3, "runtime": 1},
                                "functions": [
                                    {
                                        "name": "_Zfake___ico_sequent",
                                        "placement": "gpu",
                                        "reason": "force_include",
                                        "detail": "___ico_sequent",
                                    },
                                    {
                                        "name": "_ZN9Verilated15commandArgsEv",
                                        "placement": "runtime",
                                        "reason": "runtime_prefix",
                                        "detail": "_ZN9Verilated",
                                    },
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
            self.assertEqual(meta["classifier_report"], "vl_classifier_report.json")
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
                any(arg.startswith("--classifier-report-out=") for arg in vg_calls[0]),
            )
            self.assertTrue(
                any(arg.startswith("--kernel-manifest-out=") for arg in vg_calls[0]),
            )

    def test_ptxas_opt_level_forwards_into_command_and_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = self._make_fake_mdir(tmpdir)
            calls: list[list[str]] = []
            with mock.patch.object(self.module, "detect_storage_size", return_value=4096):
                with mock.patch.object(self.module, "run", side_effect=self._fake_run(calls)):
                    cubin, storage_size = self.module.build_vl_gpu(
                        mdir,
                        ptxas_opt_level=0,
                    )

            self.assertEqual(storage_size, 4096)
            self.assertTrue(cubin.is_file())
            meta = json.loads((mdir / "vl_batch_gpu.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["ptxas_opt_level"], 0)
            ptxas_calls = [argv for argv in calls if argv and argv[0] == self.module.PTXAS]
            self.assertEqual(len(ptxas_calls), 1)
            self.assertIn("--opt-level", ptxas_calls[0])
            self.assertIn("0", ptxas_calls[0])

    def test_emit_ptx_module_skips_ptxas_and_writes_ptx_meta(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = self._make_fake_mdir(tmpdir)
            calls: list[list[str]] = []
            with mock.patch.object(self.module, "detect_storage_size", return_value=1024):
                with mock.patch.object(self.module, "run", side_effect=self._fake_run(calls)):
                    module_path, storage_size = self.module.build_vl_gpu(
                        mdir,
                        emit_ptx_module=True,
                    )

            self.assertEqual(storage_size, 1024)
            self.assertEqual(module_path.name, "vl_batch_gpu.ptx")
            self.assertTrue(module_path.is_file())
            meta = json.loads((mdir / "vl_batch_gpu.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["cubin"], "vl_batch_gpu.ptx")
            self.assertEqual(meta["cuda_module_format"], "ptx")
            ptxas_calls = [argv for argv in calls if argv and argv[0] == self.module.PTXAS]
            self.assertEqual(ptxas_calls, [])

    def test_reuse_gpu_patched_ll_skips_vlgpugen_and_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = self._make_fake_mdir(tmpdir)
            (mdir / "vl_batch_gpu_patched.ll").write_text("; patched gpu ll\n", encoding="utf-8")
            (mdir / "existing_classifier.json").write_text("{}\n", encoding="utf-8")
            (mdir / "vl_batch_gpu.meta.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "cubin": "vl_batch_gpu.ptx",
                        "storage_size": 3072,
                        "sm": "sm_89",
                        "kernel": "vl_eval_batch_gpu",
                        "classifier_report": "existing_classifier.json",
                        "clang_opt": "Oz",
                        "gpu_opt_level": "O2",
                        "cuda_module_format": "ptx",
                        "launch_sequence": ["k0", "k1"],
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            calls: list[list[str]] = []
            with mock.patch.object(self.module, "detect_storage_size") as probe_mock:
                with mock.patch.object(self.module, "run", side_effect=self._fake_run(calls)):
                    cubin, storage_size = self.module.build_vl_gpu(
                        mdir,
                        reuse_gpu_patched_ll=True,
                        gpu_opt_level="O0",
                    )

            probe_mock.assert_not_called()
            self.assertEqual(storage_size, 3072)
            self.assertTrue(cubin.is_file())
            meta = json.loads((mdir / "vl_batch_gpu.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["incremental_mode"], "reuse_gpu_patched_ll")
            self.assertEqual(meta["gpu_opt_level"], "O0")
            self.assertEqual(meta["launch_sequence"], ["k0", "k1"])
            self.assertEqual(meta["classifier_report"], "existing_classifier.json")
            self.assertFalse(any(arg.startswith("--out=") for argv in calls for arg in argv))
            self.assertFalse(
                any(any(arg.startswith("--load-pass-plugin=") for arg in argv) for argv in calls)
            )
            llc_calls = [argv for argv in calls if argv and argv[0] == self.module.LLC]
            self.assertEqual(len(llc_calls), 1)

    def test_reuse_ptx_rebuilds_cubin_without_llc_or_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = self._make_fake_mdir(tmpdir)
            (mdir / "vl_batch_gpu.ptx").write_text("// fake ptx\n", encoding="utf-8")
            (mdir / "existing_classifier.json").write_text("{}\n", encoding="utf-8")
            (mdir / "vl_batch_gpu.meta.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "cubin": "vl_batch_gpu.ptx",
                        "storage_size": 5120,
                        "sm": "sm_89",
                        "kernel": "vl_eval_batch_gpu",
                        "classifier_report": "existing_classifier.json",
                        "clang_opt": "Os",
                        "gpu_opt_level": "O2",
                        "cuda_module_format": "ptx",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            calls: list[list[str]] = []
            with mock.patch.object(self.module, "detect_storage_size") as probe_mock:
                with mock.patch.object(self.module, "run", side_effect=self._fake_run(calls)):
                    cubin, storage_size = self.module.build_vl_gpu(
                        mdir,
                        reuse_ptx=True,
                        ptxas_opt_level=0,
                    )

            probe_mock.assert_not_called()
            self.assertEqual(storage_size, 5120)
            self.assertTrue(cubin.is_file())
            meta = json.loads((mdir / "vl_batch_gpu.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["incremental_mode"], "reuse_ptx")
            self.assertEqual(meta["clang_opt"], "Os")
            self.assertEqual(meta["gpu_opt_level"], "O2")
            self.assertEqual(meta["ptxas_opt_level"], 0)
            self.assertFalse(any(argv and argv[0] == self.module.LLC for argv in calls))
            self.assertFalse(any(arg.startswith("--out=") for argv in calls for arg in argv))
            ptxas_calls = [argv for argv in calls if argv and argv[0] == self.module.PTXAS]
            self.assertEqual(len(ptxas_calls), 1)
            self.assertIn(str(mdir / "vl_batch_gpu.ptx"), ptxas_calls[0])

    def test_compile_ll_adds_vltstd_include_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            cpp = mdir / "demo.cpp"
            out_ll = mdir / "demo.ll"
            cpp.write_text("// fake cpp\n", encoding="utf-8")
            vl_inc = root / "verilator" / "include"
            (vl_inc / "vltstd").mkdir(parents=True)

            calls: list[list[str]] = []

            def _fake_run(cmd: list, **kwargs) -> None:
                calls.append([str(item) for item in cmd])

            with mock.patch.object(self.module, "run", side_effect=_fake_run):
                with mock.patch.object(self.module, "verilator_include_dir", return_value=vl_inc):
                    self.module.compile_ll(cpp, mdir, out_ll)

            self.assertEqual(len(calls), 1)
            self.assertIn(f"-I{vl_inc}", calls[0])
            self.assertIn(f"-I{vl_inc / 'vltstd'}", calls[0])

    def test_jobs_parallelizes_cpp_to_ll_emission(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = self._make_fake_mdir(tmpdir)
            for ll_path in mdir.glob("*.ll"):
                ll_path.unlink()
            merged_ll = mdir / "merged.ll"
            if merged_ll.exists():
                merged_ll.unlink()

            calls: list[list[str]] = []
            compile_calls: list[tuple[str, str]] = []

            def _fake_compile_ll(cpp_path: Path, _mdir: Path, out_ll: Path, *, clang_opt: str = "O1") -> None:
                compile_calls.append((cpp_path.name, clang_opt))
                out_ll.write_text(f"; rebuilt {cpp_path.stem}\n", encoding="utf-8")

            with mock.patch.object(self.module, "detect_storage_size", return_value=4096):
                with mock.patch.object(self.module, "compile_ll", side_effect=_fake_compile_ll):
                    with mock.patch.object(self.module, "run", side_effect=self._fake_run(calls)):
                        cubin, storage_size = self.module.build_vl_gpu(
                            mdir,
                            jobs=2,
                        )

            self.assertEqual(storage_size, 4096)
            self.assertTrue(cubin.is_file())
            self.assertCountEqual(
                compile_calls,
                [
                    ("Vfake.cpp", "O1"),
                    ("Vfake___024root__0.cpp", "O1"),
                    ("Vfake___024root__Slow.cpp", "O1"),
                ],
            )
            self.assertTrue((mdir / "merged.ll").is_file())
            self.assertTrue((mdir / "vl_batch_gpu.meta.json").is_file())

    def test_apply_vortex_tls_slot_bypass_text_rewrites_all_tls_slot_uses(self) -> None:
        ir = "\n".join(
            [
                '@_ZN9Verilated3t_sE = external thread_local global %"struct.Verilated::ThreadLocal", align 8',
                'declare nonnull ptr @llvm.threadlocal.address.p0(ptr nonnull)',
                '  %658 = tail call noundef align 8 ptr @llvm.threadlocal.address.p0(ptr align 8 @_ZN9Verilated3t_sE)',
                '  %733 = call noundef align 8 ptr @llvm.threadlocal.address.p0(ptr align 8 @_ZN9Verilated3t_sE)',
                '  %12419 = call noundef align 8 ptr @llvm.threadlocal.address.p0(ptr align 8 @_ZN9Verilated3t_sE)',
                '',
            ]
        )

        rewritten, replacements = self.module.apply_vortex_tls_slot_bypass_text(ir)

        self.assertEqual(replacements, 3)
        self.assertIn("@vl_gpu_fake_verilated_t_contextp = internal global ptr null, align 8", rewritten)
        self.assertEqual(rewritten.count("@llvm.threadlocal.address.p0(ptr align 8 @_ZN9Verilated3t_sE)"), 0)
        self.assertEqual(rewritten.count("@vl_gpu_fake_verilated_t_contextp"), 4)
        self.assertIn("%658 = getelementptr inbounds ptr, ptr @vl_gpu_fake_verilated_t_contextp, i64 0", rewritten)
        self.assertIn("%733 = getelementptr inbounds ptr, ptr @vl_gpu_fake_verilated_t_contextp, i64 0", rewritten)
        self.assertIn("%12419 = getelementptr inbounds ptr, ptr @vl_gpu_fake_verilated_t_contextp, i64 0", rewritten)

    def test_reuse_gpu_patched_ll_applies_vortex_tls_slot_bypass_before_opt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = self._make_fake_vortex_mdir(tmpdir)
            (mdir / "vl_batch_gpu.meta.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "cubin": "vl_batch_gpu.ptx",
                        "storage_size": 6144,
                        "sm": "sm_89",
                        "kernel": "vl_eval_batch_gpu",
                        "classifier_report": "vl_classifier_report.json",
                        "clang_opt": "O1",
                        "gpu_opt_level": "O3",
                        "cuda_module_format": "ptx",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            calls: list[list[str]] = []
            with mock.patch.object(self.module, "detect_storage_size") as probe_mock:
                with mock.patch.object(self.module, "run", side_effect=self._fake_run(calls)):
                    cubin, storage_size = self.module.build_vl_gpu(
                        mdir,
                        reuse_gpu_patched_ll=True,
                    )

            probe_mock.assert_not_called()
            self.assertEqual(storage_size, 6144)
            self.assertTrue(cubin.is_file())
            bypass_path = mdir / "vl_batch_gpu_vortex_tls_bypass.ll"
            self.assertTrue(bypass_path.is_file())
            rewritten = bypass_path.read_text(encoding="utf-8")
            self.assertIn("@vl_gpu_fake_verilated_t_contextp = internal global ptr null, align 8", rewritten)
            self.assertEqual(rewritten.count("@vl_gpu_fake_verilated_t_contextp"), 4)
            self.assertEqual(rewritten.count("@llvm.threadlocal.address.p0(ptr align 8 @_ZN9Verilated3t_sE)"), 0)
            meta = json.loads((mdir / "vl_batch_gpu.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(
                meta["gpu_ir_workarounds"],
                ["vortex_verilated_tls_slot_bypass:3"],
            )
            opt_calls = [argv for argv in calls if argv and argv[0] == self.module.OPT and "-O3" in argv]
            self.assertEqual(len(opt_calls), 1)
            self.assertIn(str(bypass_path), opt_calls[0])

    def test_reuse_gpu_patched_ll_applies_caliptra_tls_slot_bypass_before_opt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = self._make_fake_caliptra_mdir(tmpdir)
            (mdir / "vl_batch_gpu.meta.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "cubin": "vl_batch_gpu.ptx",
                        "storage_size": 3128704,
                        "sm": "sm_89",
                        "kernel": "vl_eval_batch_gpu",
                        "classifier_report": "vl_classifier_report.json",
                        "clang_opt": "O1",
                        "gpu_opt_level": "O3",
                        "cuda_module_format": "ptx",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            calls: list[list[str]] = []
            with mock.patch.object(self.module, "detect_storage_size") as probe_mock:
                with mock.patch.object(self.module, "run", side_effect=self._fake_run(calls)):
                    cubin, storage_size = self.module.build_vl_gpu(
                        mdir,
                        reuse_gpu_patched_ll=True,
                    )

            probe_mock.assert_not_called()
            self.assertEqual(storage_size, 3128704)
            self.assertTrue(cubin.is_file())
            bypass_path = mdir / "vl_batch_gpu_caliptra_tls_bypass.ll"
            self.assertTrue(bypass_path.is_file())
            rewritten = bypass_path.read_text(encoding="utf-8")
            self.assertIn("@vl_gpu_fake_verilated_t_contextp = internal global ptr null, align 8", rewritten)
            self.assertEqual(rewritten.count("@vl_gpu_fake_verilated_t_contextp"), 4)
            self.assertEqual(rewritten.count("@llvm.threadlocal.address.p0(ptr align 8 @_ZN9Verilated3t_sE)"), 0)
            meta = json.loads((mdir / "vl_batch_gpu.meta.json").read_text(encoding="utf-8"))
            self.assertEqual(
                meta["gpu_ir_workarounds"],
                ["caliptra_verilated_tls_slot_bypass:3"],
            )
            opt_calls = [argv for argv in calls if argv and argv[0] == self.module.OPT and "-O3" in argv]
            self.assertEqual(len(opt_calls), 1)
            self.assertIn(str(bypass_path), opt_calls[0])


if __name__ == "__main__":
    unittest.main()
