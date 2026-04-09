#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "enrollment_common.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class EnrollmentCommonRuntimeInputsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("enrollment_common_runtime_inputs_test", MODULE_PATH)

    def test_load_enrollment_accepts_runtime_file(self) -> None:
        enrollment = self.module.load_enrollment(
            {
                "enrollment": {
                    "slug": "xiangshan",
                    "mdir_name": "xiangshan_gpu_cov_vl",
                    "runtime_input_type": "runtime_file",
                    "runtime_input_path": "tests/hello/program.bin",
                    "runtime_input_name": "program.bin",
                }
            }
        )
        self.assertEqual(enrollment["runtime_input_type"], "runtime_file")

    def test_load_enrollment_accepts_blackparrot_prog_mem(self) -> None:
        enrollment = self.module.load_enrollment(
            {
                "enrollment": {
                    "slug": "blackparrot",
                    "mdir_name": "blackparrot_gpu_cov_vl",
                    "runtime_input_type": "blackparrot_prog_mem",
                    "runtime_input_path": "tests/hello/prog.mem",
                    "runtime_input_target": {
                        "kind": "memory-array-preload-v1",
                        "target_path": "blackparrot_gpu_cov_tb.gpu_cov_program_words",
                        "word_bits": 64,
                        "depth": 32768,
                        "base_addr": 0,
                        "address_unit_bytes": 8,
                        "endianness": "little",
                    },
                }
            }
        )
        self.assertEqual(enrollment["runtime_input_type"], "blackparrot_prog_mem")

    def test_ensure_runtime_input_stages_runtime_file_into_mdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            source = root / "source.bin"
            source.write_bytes(b"\x11\x22\x33\x44")

            runtime_inputs, extra_defines = self.module.ensure_runtime_input(
                mdir=mdir,
                runtime_input_type="runtime_file",
                runtime_input_path=source,
                runtime_input_name="program.bin",
                top_module="xiangshan_gpu_cov_tb",
            )

            self.assertEqual(extra_defines, [])
            staged = mdir / "program.bin"
            self.assertEqual(runtime_inputs["runtime_file"], str(staged.resolve()))
            self.assertEqual(runtime_inputs["runtime_file_name"], "program.bin")
            self.assertEqual(staged.read_bytes(), b"\x11\x22\x33\x44")

    def test_ensure_runtime_input_stages_runtime_file_companions_into_mdir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            source = root / "init.bin"
            source.write_bytes(b"\x11\x22")
            post = root / "post.bin"
            post.write_bytes(b"\xaa\xbb")
            dcrs = root / "dcrs.bin"
            dcrs.write_bytes(b"\x01\x02\x03\x04")

            runtime_inputs, extra_defines = self.module.ensure_runtime_input(
                mdir=mdir,
                runtime_input_type="runtime_file",
                runtime_input_path=source,
                runtime_input_name="init.bin",
                runtime_input_companion_paths=[post, dcrs],
                top_module="vortex_gpu_cov_tb",
            )

            self.assertEqual(extra_defines, [])
            self.assertEqual((mdir / "init.bin").read_bytes(), b"\x11\x22")
            self.assertEqual((mdir / "post.bin").read_bytes(), b"\xaa\xbb")
            self.assertEqual((mdir / "dcrs.bin").read_bytes(), b"\x01\x02\x03\x04")
            self.assertEqual(
                runtime_inputs["runtime_file_companion_names"],
                ["post.bin", "dcrs.bin"],
            )
            self.assertEqual(
                runtime_inputs["runtime_file_companion_files"],
                [
                    str((mdir / "post.bin").resolve()),
                    str((mdir / "dcrs.bin").resolve()),
                ],
            )

    def test_ensure_runtime_input_rejects_runtime_file_name_with_path_separator(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            source = root / "source.bin"
            source.write_bytes(b"\x00")

            with self.assertRaisesRegex(ValueError, "plain filename"):
                self.module.ensure_runtime_input(
                    mdir=mdir,
                    runtime_input_type="runtime_file",
                    runtime_input_path=source,
                    runtime_input_name="nested/program.bin",
                    top_module="xiangshan_gpu_cov_tb",
                )

    def test_ensure_runtime_input_stages_memory_image_and_applies_patches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            source = root / "mem.bin"
            source.write_bytes(b"\x00" * 16)

            runtime_inputs, extra_defines = self.module.ensure_runtime_input(
                mdir=mdir,
                runtime_input_type="memory_image",
                runtime_input_path=source,
                top_module="openpiton_gpu_cov_tb",
                runtime_input_format="bin",
                runtime_input_target={
                    "kind": "memory-array-preload-v1",
                    "target_path": "openpiton_gpu_cov_tb.dut.visible_mem",
                    "word_bits": 64,
                    "depth": 2048,
                    "base_addr": 0,
                    "address_unit_bytes": 8,
                    "endianness": "little",
                },
                runtime_input_patch_bytes=[
                    {"offset": 0, "value": 1, "width_bytes": 8},
                    {"offset": 8, "value": 7, "width_bytes": 8},
                ],
            )

            self.assertEqual(extra_defines, [])
            staged = Path(runtime_inputs["memory_image"])
            self.assertEqual(staged.read_bytes(), (1).to_bytes(8, "little") + (7).to_bytes(8, "little"))
            descriptor = Path(runtime_inputs["memory_image_target"])
            self.assertTrue(descriptor.is_file())
            self.assertEqual(runtime_inputs["memory_image_format"], "bin")

    def test_ensure_runtime_input_materializes_blackparrot_prog_mem_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            source = root / "prog.mem"
            source.write_text("@00000000\n11 22 33 44 55 66 77 88\n99 aa bb cc\n", encoding="utf-8")

            runtime_inputs, extra_defines = self.module.ensure_runtime_input(
                mdir=mdir,
                runtime_input_type="blackparrot_prog_mem",
                runtime_input_path=source,
                top_module="blackparrot_gpu_cov_tb",
                runtime_input_target={
                    "kind": "memory-array-preload-v1",
                    "target_path": "blackparrot_gpu_cov_tb.gpu_cov_program_words",
                    "word_bits": 64,
                    "depth": 32768,
                    "base_addr": 0,
                    "address_unit_bytes": 8,
                    "endianness": "little",
                },
                runtime_input_patch_bytes=[
                    {"offset": 8, "value": 0xDEADBEEF, "width_bytes": 4, "endianness": "little"},
                ],
            )

            self.assertEqual(extra_defines, [])
            image_path = Path(runtime_inputs["memory_image"])
            self.assertEqual(
                image_path.read_bytes(),
                (
                    (2).to_bytes(8, "little")
                    + int.from_bytes(bytes.fromhex("1122334455667788"), "little").to_bytes(8, "little")
                    + int.from_bytes(b"\xef\xbe\xad\xde\x00\x00\x00\x00", "little").to_bytes(8, "little")
                ),
            )
            descriptor_path = Path(runtime_inputs["memory_image_target"])
            self.assertTrue(descriptor_path.is_file())
            self.assertEqual(runtime_inputs["memory_image_format"], "bin")


if __name__ == "__main__":
    unittest.main()
