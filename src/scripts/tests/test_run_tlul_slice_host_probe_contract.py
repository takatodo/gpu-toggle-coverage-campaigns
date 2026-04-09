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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "run_tlul_slice_host_probe.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunTlulSliceHostProbeContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_tlul_slice_host_probe_contract_test", MODULE_PATH)

    def test_derive_target_accepts_gpu_cov_and_cov_tb_prefixes(self) -> None:
        self.assertEqual(
            self.module._derive_target("Vtlul_socket_1n_gpu_cov_tb"),
            "tlul_socket_1n",
        )
        self.assertEqual(
            self.module._derive_target("Vtlul_fifo_async_cov_tb"),
            "tlul_fifo_async",
        )

    def test_select_control_fields_handle_direct_and_nested_layouts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()

            prefix = "Vtlul_fifo_sync_gpu_cov_tb"
            root_header = mdir / f"{prefix}___024root.h"
            root_header.write_text(
                "class demo {\n"
                "  CData clk_i;\n"
                "  CData rst_ni;\n"
                "};\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module._select_clock_field(mdir, prefix),
                ("clk_i", "clk_i", True),
            )
            self.assertEqual(
                self.module._select_reset_field(mdir, prefix),
                ("rst_ni", "rst_ni", 0, 1, True),
            )

            root_header.write_text(
                "class demo {\n"
                "  CData tlul_fifo_sync_gpu_cov_tb__DOT__clk_i;\n"
                "  CData tlul_fifo_sync_gpu_cov_tb__DOT__reset_like_w;\n"
                "};\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module._select_clock_field(mdir, prefix),
                (
                    "tlul_fifo_sync_gpu_cov_tb__DOT__clk_i",
                    "clk_i",
                    False,
                ),
            )
            self.assertEqual(
                self.module._select_reset_field(mdir, prefix),
                (
                    "tlul_fifo_sync_gpu_cov_tb__DOT__reset_like_w",
                    "reset_like_w",
                    1,
                    0,
                    False,
                ),
            )

            root_header.write_text(
                "class demo {\n"
                "  CData tlul_fifo_sync_gpu_cov_tb__DOT__clk_i;\n"
                "  CData tlul_fifo_sync_gpu_cov_tb__DOT__rst_ni;\n"
                "  CData tlul_fifo_sync_gpu_cov_tb__DOT__reset_like_w;\n"
                "};\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module._select_reset_field(mdir, prefix),
                (
                    "tlul_fifo_sync_gpu_cov_tb__DOT__rst_ni",
                    "rst_ni",
                    0,
                    1,
                    False,
                ),
            )

    def test_select_control_fields_handle_multiclock_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()

            prefix = "Vxbar_main_gpu_cov_tb"
            root_header = mdir / f"{prefix}___024root.h"
            root_header.write_text(
                "class demo {\n"
                "  CData xbar_main_gpu_cov_tb__DOT__clk_main_i;\n"
                "  CData xbar_main_gpu_cov_tb__DOT__clk_fixed_i;\n"
                "  CData xbar_main_gpu_cov_tb__DOT__rst_main_ni;\n"
                "};\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module._select_clock_field(mdir, prefix),
                (
                    "xbar_main_gpu_cov_tb__DOT__clk_main_i",
                    "clk_main_i",
                    False,
                ),
            )
            self.assertEqual(
                self.module._select_reset_field(mdir, prefix),
                (
                    "xbar_main_gpu_cov_tb__DOT__rst_main_ni",
                    "rst_main_ni",
                    0,
                    1,
                    False,
                ),
            )

    def test_select_control_fields_handle_xuantie_nested_clk_and_reset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()

            prefix = "Vxuantie_e902_gpu_cov_tb"
            root_header = mdir / f"{prefix}___024root.h"
            root_header.write_text(
                "class demo {\n"
                "  CData xuantie_e902_gpu_cov_tb__DOT__dut__DOT__clk;\n"
                "  CData xuantie_e902_gpu_cov_tb__DOT__dut__DOT__rst_b;\n"
                "};\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module._select_clock_field(mdir, prefix),
                (
                    "xuantie_e902_gpu_cov_tb__DOT__dut__DOT__clk",
                    "dut__DOT__clk",
                    False,
                ),
            )
            self.assertEqual(
                self.module._select_reset_field(mdir, prefix),
                (
                    "xuantie_e902_gpu_cov_tb__DOT__dut__DOT__rst_b",
                    "dut__DOT__rst_b",
                    0,
                    1,
                    False,
                ),
            )

    def test_select_control_fields_handle_xuantie_c906_simaccel_clock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()

            prefix = "Vxuantie_c906_gpu_cov_tb"
            root_header = mdir / f"{prefix}___024root.h"
            root_header.write_text(
                "class demo {\n"
                "  CData xuantie_c906_gpu_cov_tb__DOT__simaccel_main_clk;\n"
                "  CData xuantie_c906_gpu_cov_tb__DOT__x_soc__DOT__pad_cpu_rst_b;\n"
                "};\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module._select_clock_field(mdir, prefix),
                (
                    "xuantie_c906_gpu_cov_tb__DOT__simaccel_main_clk",
                    "simaccel_main_clk",
                    True,
                ),
            )
            self.assertEqual(
                self.module._select_reset_field(mdir, prefix),
                (
                    "xuantie_c906_gpu_cov_tb__DOT__x_soc__DOT__pad_cpu_rst_b",
                    "x_soc__DOT__pad_cpu_rst_b",
                    0,
                    1,
                    False,
                ),
            )

    def test_select_control_fields_handle_xuantie_c910_deep_reset_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()

            prefix = "Vxuantie_c910_gpu_cov_tb"
            root_header = mdir / f"{prefix}___024root.h"
            root_header.write_text(
                "class demo {\n"
                "  CData xuantie_c910_gpu_cov_tb__DOT__simaccel_main_clk;\n"
                "  CData xuantie_c910_gpu_cov_tb__DOT__x_soc__DOT__x_cpu_sub_system_axi__DOT__x_rv_integration_platform__DOT__x_cpu_top__DOT__x_ct_mp_rst_top__DOT__async_core0_rst_b;\n"
                "};\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module._select_clock_field(mdir, prefix),
                (
                    "xuantie_c910_gpu_cov_tb__DOT__simaccel_main_clk",
                    "simaccel_main_clk",
                    True,
                ),
            )
            self.assertEqual(
                self.module._select_reset_field(mdir, prefix),
                (
                    "xuantie_c910_gpu_cov_tb__DOT__x_soc__DOT__x_cpu_sub_system_axi__DOT__x_rv_integration_platform__DOT__x_cpu_top__DOT__x_ct_mp_rst_top__DOT__async_core0_rst_b",
                    "x_soc__DOT__x_cpu_sub_system_axi__DOT__x_rv_integration_platform__DOT__x_cpu_top__DOT__x_ct_mp_rst_top__DOT__async_core0_rst_b",
                    0,
                    1,
                    False,
                ),
            )

    def test_select_control_fields_handle_openpiton_core_ref_clk_and_sys_rst_n(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()

            prefix = "Vopenpiton_gpu_cov_tb"
            root_header = mdir / f"{prefix}___024root.h"
            root_header.write_text(
                "class demo {\n"
                "  CData openpiton_gpu_cov_tb__DOT__dut__DOT__core_ref_clk;\n"
                "  CData openpiton_gpu_cov_tb__DOT__dut__DOT__sys_rst_n;\n"
                "};\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module._select_clock_field(mdir, prefix),
                (
                    "openpiton_gpu_cov_tb__DOT__dut__DOT__core_ref_clk",
                    "dut__DOT__core_ref_clk",
                    True,
                ),
            )
            self.assertEqual(
                self.module._select_reset_field(mdir, prefix),
                (
                    "openpiton_gpu_cov_tb__DOT__dut__DOT__sys_rst_n",
                    "dut__DOT__sys_rst_n",
                    0,
                    1,
                    False,
                ),
            )

    def test_select_control_fields_handle_xiangshan_nested_clock_and_reset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()

            prefix = "Vxiangshan_gpu_cov_tb"
            root_header = mdir / f"{prefix}___024root.h"
            root_header.write_text(
                "class demo {\n"
                "  CData xiangshan_gpu_cov_tb__DOT__dut__DOT__clock;\n"
                "  CData xiangshan_gpu_cov_tb__DOT__dut__DOT__reset;\n"
                "};\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module._select_clock_field(mdir, prefix),
                (
                    "xiangshan_gpu_cov_tb__DOT__dut__DOT__clock",
                    "dut__DOT__clock",
                    False,
                ),
            )
            self.assertEqual(
                self.module._select_reset_field(mdir, prefix),
                (
                    "xiangshan_gpu_cov_tb__DOT__dut__DOT__reset",
                    "dut__DOT__reset",
                    1,
                    0,
                    False,
                ),
            )

    def test_select_control_fields_handle_veer_nested_core_clk_and_reset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()

            prefix = "Vveer_eh1_gpu_cov_tb"
            root_header = mdir / f"{prefix}___024root.h"
            root_header.write_text(
                "class demo {\n"
                "  CData veer_eh1_gpu_cov_tb__DOT__dut__DOT__core_clk;\n"
                "  CData veer_eh1_gpu_cov_tb__DOT__dut__DOT__gpu_cov_rst_l_w;\n"
                "};\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module._select_clock_field(mdir, prefix),
                (
                    "veer_eh1_gpu_cov_tb__DOT__dut__DOT__core_clk",
                    "dut__DOT__core_clk",
                    False,
                ),
            )
            self.assertEqual(
                self.module._select_reset_field(mdir, prefix),
                (
                    "veer_eh1_gpu_cov_tb__DOT__dut__DOT__gpu_cov_rst_l_w",
                    "dut__DOT__gpu_cov_rst_l_w",
                    0,
                    1,
                    False,
                ),
            )

    def test_select_control_fields_handle_caliptra_core_clk_and_cptra_rst_b(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()

            prefix = "Vcaliptra_gpu_cov_tb"
            root_header = mdir / f"{prefix}___024root.h"
            root_header.write_text(
                "class demo {\n"
                "  CData caliptra_gpu_cov_tb__DOT__dut__DOT__core_clk;\n"
                "  CData caliptra_gpu_cov_tb__DOT__dut__DOT__cptra_rst_b;\n"
                "};\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module._select_clock_field(mdir, prefix),
                (
                    "caliptra_gpu_cov_tb__DOT__dut__DOT__core_clk",
                    "dut__DOT__core_clk",
                    False,
                ),
            )
            self.assertEqual(
                self.module._select_reset_field(mdir, prefix),
                (
                    "caliptra_gpu_cov_tb__DOT__dut__DOT__cptra_rst_b",
                    "dut__DOT__cptra_rst_b",
                    0,
                    1,
                    False,
                ),
            )

    def test_select_control_fields_handle_blackparrot_dut_clk_and_reset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()

            prefix = "Vblackparrot_gpu_cov_tb"
            root_header = mdir / f"{prefix}___024root.h"
            root_header.write_text(
                "class demo {\n"
                "  CData blackparrot_gpu_cov_tb__DOT__dut__DOT__dut_clk;\n"
                "  CData blackparrot_gpu_cov_tb__DOT__dut__DOT__dut_reset;\n"
                "};\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module._select_clock_field(mdir, prefix),
                (
                    "blackparrot_gpu_cov_tb__DOT__dut__DOT__dut_clk",
                    "dut__DOT__dut_clk",
                    False,
                ),
            )
            self.assertEqual(
                self.module._select_reset_field(mdir, prefix),
                (
                    "blackparrot_gpu_cov_tb__DOT__dut__DOT__dut_reset",
                    "dut__DOT__dut_reset",
                    1,
                    0,
                    False,
                ),
            )

    def test_build_model_archive_retries_without_pch_after_make_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            mk_path = mdir / "Vxbar_main_gpu_cov_tb.mk"
            mk_path.write_text("# fake mk\n", encoding="utf-8")
            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                if len(calls) == 1:
                    raise self.module.subprocess.CalledProcessError(returncode=2, cmd=argv)
                return None

            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                mode = self.module._build_model_archive(
                    mdir,
                    mk_path,
                    "Vxbar_main_gpu_cov_tb",
                    {"VERILATOR_ROOT": "/tmp/verilator"},
                )

            self.assertEqual(mode, "no_pch_fallback")
            self.assertEqual(
                calls[0],
                ["make", "-C", str(mdir), "-f", mk_path.name, "libVxbar_main_gpu_cov_tb"],
            )
            self.assertEqual(
                calls[1],
                [
                    "make",
                    "-C",
                    str(mdir),
                    "-f",
                    mk_path.name,
                    "libVxbar_main_gpu_cov_tb",
                    "VK_PCH_I_FAST=",
                    "VK_PCH_I_SLOW=",
                ],
            )

    def test_build_model_archive_forwards_opt_overrides_as_make_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            mk_path = mdir / "Vxbar_main_gpu_cov_tb.mk"
            mk_path.write_text("# fake mk\n", encoding="utf-8")
            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                calls.append([str(item) for item in cmd])
                return None

            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                mode = self.module._build_model_archive(
                    mdir,
                    mk_path,
                    "Vxbar_main_gpu_cov_tb",
                    {
                        "VERILATOR_ROOT": "/tmp/verilator",
                        "OPT_FAST": "-O0",
                        "OPT_SLOW": "-O0",
                        "OPT_GLOBAL": "-O0",
                    },
                )

            self.assertEqual(mode, "default_pch")
            self.assertEqual(
                calls[0],
                [
                    "make",
                    "-C",
                    str(mdir),
                    "-f",
                    mk_path.name,
                    "libVxbar_main_gpu_cov_tb",
                    "OPT_FAST=-O0",
                    "OPT_SLOW=-O0",
                    "OPT_GLOBAL=-O0",
                ],
            )

    def test_build_model_archive_forwards_parallel_make_jobs_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            mdir = Path(tmpdir)
            mk_path = mdir / "Vxbar_main_gpu_cov_tb.mk"
            mk_path.write_text("# fake mk\n", encoding="utf-8")
            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                calls.append([str(item) for item in cmd])
                return None

            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                mode = self.module._build_model_archive(
                    mdir,
                    mk_path,
                    "Vxbar_main_gpu_cov_tb",
                    {
                        "VERILATOR_ROOT": "/tmp/verilator",
                        "HOST_PROBE_MAKE_JOBS": "4",
                    },
                )

            self.assertEqual(mode, "default_pch")
            self.assertEqual(
                calls[0],
                [
                    "make",
                    "-j4",
                    "-C",
                    str(mdir),
                    "-f",
                    mk_path.name,
                    "libVxbar_main_gpu_cov_tb",
                ],
            )

    def test_template_watch_fields_are_loaded_and_written_to_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            template = root / "template.json"
            template.write_text(
                json.dumps(
                    {
                        "debug_internal_output_names": ["demo__DOT__phase_q"],
                        "runner_args_template": {
                            "debug_internal_output_names": ["debug_phase_o", "demo__DOT__phase_q"]
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                self.module._load_template_watch_fields(template),
                ["demo__DOT__phase_q", "debug_phase_o"],
            )

            mdir = root / "mdir"
            mdir.mkdir()
            prefix = "Vdemo_gpu_cov_tb"
            (mdir / f"{prefix}___024root.h").write_text(
                "class demo {\n"
                "  CData demo__DOT__phase_q;\n"
                "  CData debug_phase_o;\n"
                "};\n",
                encoding="utf-8",
            )
            resolved = self.module._resolve_watch_fields(
                mdir, prefix, ["demo__DOT__phase_q", "debug_phase_o", "done_o"]
            )
            self.assertEqual(resolved, ["demo__DOT__phase_q", "debug_phase_o"])
            header = self.module._write_watch_fields_header(mdir, resolved)
            text = header.read_text(encoding="utf-8")
            self.assertIn('X("demo__DOT__phase_q", demo__DOT__phase_q)', text)
            self.assertIn('X("debug_phase_o", debug_phase_o)', text)

    def test_parse_probe_stdout_skips_banner_prefix(self) -> None:
        payload = self.module._parse_probe_stdout(
            "******START TO LOAD PROGRAM******\n{\n  \"target\": \"xuantie_e902\"\n}\n"
        )
        self.assertEqual(payload["target"], "xuantie_e902")

    def test_memory_image_extra_defines_accept_descriptor_backed_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            prefix = "Vxiangshan_gpu_cov_tb"
            (mdir / f"{prefix}___024root.h").write_text(
                "class demo {\n"
                "  VlUnpacked<QData/*63:0*/, 131072> xiangshan_gpu_cov_tb__DOT__dut__DOT__top__DOT__memory__DOT__ram__DOT__rdata_mem__DOT__ram;\n"
                "};\n",
                encoding="utf-8",
            )
            descriptor = root / "target.json"
            descriptor.write_text(
                json.dumps(
                    {
                        "kind": "memory-array-preload-v1",
                        "target_path": "xiangshan_gpu_cov_tb.dut.top.memory.ram.rdata_mem.ram",
                        "word_bits": 64,
                        "depth": 131072,
                        "base_addr": 0,
                        "address_unit_bytes": 8,
                        "endianness": "little",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            defines = self.module._memory_image_extra_defines(
                mdir,
                prefix,
                descriptor,
            )

            self.assertEqual(
                defines,
                [
                    "-DMEMORY_IMAGE_ARRAY=xiangshan_gpu_cov_tb__DOT__dut__DOT__top__DOT__memory__DOT__ram__DOT__rdata_mem__DOT__ram",
                    "-DMEMORY_IMAGE_WORD_BITS=64",
                    "-DMEMORY_IMAGE_EXPECTED_DEPTH=131072",
                ],
            )

    def test_build_and_run_forwards_memory_image_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            (mdir / "Vxiangshan_gpu_cov_tb.mk").write_text("# fake mk\n", encoding="utf-8")
            (mdir / "Vxiangshan_gpu_cov_tb___024root.h").write_text(
                "class demo {\n"
                "  CData xiangshan_gpu_cov_tb__DOT__dut__DOT__clock;\n"
                "  CData xiangshan_gpu_cov_tb__DOT__dut__DOT__reset;\n"
                "  VlUnpacked<QData/*63:0*/, 131072> xiangshan_gpu_cov_tb__DOT__dut__DOT__top__DOT__memory__DOT__ram__DOT__rdata_mem__DOT__ram;\n"
                "};\n",
                encoding="utf-8",
            )
            template = root / "template.json"
            template.write_text(json.dumps({"runner_args_template": {"driver_defaults": {}}}) + "\n", encoding="utf-8")
            binary_out = root / "probe.bin"
            json_out = root / "probe.json"
            memory_image = root / "program.bin"
            memory_image.write_bytes(b"\x01\x02\x03\x04")
            descriptor = root / "target.json"
            descriptor.write_text(
                json.dumps(
                    {
                        "kind": "memory-array-preload-v1",
                        "target_path": "xiangshan_gpu_cov_tb.dut.top.memory.ram.rdata_mem.ram",
                        "word_bits": 64,
                        "depth": 131072,
                        "base_addr": 0,
                        "address_unit_bytes": 8,
                        "endianness": "little",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                if argv[0] == "make":
                    (mdir / "libVxiangshan_gpu_cov_tb.a").write_bytes(b"fake-top")
                    (mdir / "libverilated.a").write_bytes(b"fake-verilated")
                    return None
                if argv[0] == "g++":
                    out_path = Path(argv[argv.index("-o") + 1])
                    out_path.write_bytes(b"fake-probe")
                    self.assertIn(
                        "-DMEMORY_IMAGE_ARRAY=xiangshan_gpu_cov_tb__DOT__dut__DOT__top__DOT__memory__DOT__ram__DOT__rdata_mem__DOT__ram",
                        argv,
                    )
                    self.assertIn("-DMEMORY_IMAGE_WORD_BITS=64", argv)
                    self.assertIn("-DMEMORY_IMAGE_EXPECTED_DEPTH=131072", argv)
                    return None
                self.assertEqual(argv[0], str(binary_out))
                self.assertIn("--memory-image", argv)
                self.assertIn(str(memory_image), argv)
                return mock.Mock(
                    stdout=json.dumps(
                        {
                            "target": "xiangshan",
                            "constructor_ok": True,
                            "field_offsets": {"done_o": 0},
                            "field_sizes": {"done_o": 1},
                            "watch_field_names": [],
                            "host_clock_control": False,
                            "host_reset_control": False,
                            "root_size": 896,
                        }
                    )
                    + "\n"
                )

            with mock.patch.object(self.module, "find_prefix", return_value="Vxiangshan_gpu_cov_tb"):
                with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                    with mock.patch.object(
                        sys,
                        "argv",
                        [
                            "run_tlul_slice_host_probe.py",
                            "--mdir",
                            str(mdir),
                            "--template",
                            str(template),
                            "--binary-out",
                            str(binary_out),
                            "--json-out",
                            str(json_out),
                            "--memory-image",
                            str(memory_image),
                            "--memory-image-target",
                            str(descriptor),
                        ],
                    ):
                        self.module.main()

            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["memory_image"], str(memory_image.resolve()))
            self.assertEqual(payload["memory_image_target"], str(descriptor.resolve()))
            self.assertIn("-DMEMORY_IMAGE_WORD_BITS=64", payload["extra_defines"])

    def test_build_and_run_uses_template_defaults_and_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            (mdir / "Vtlul_request_loopback_gpu_cov_tb.mk").write_text("# fake mk\n", encoding="utf-8")
            (
                mdir / "Vtlul_request_loopback_gpu_cov_tb___024root.h"
            ).write_text(
                "class demo {\n"
                "  CData tlul_request_loopback_gpu_cov_tb__DOT__clk_i;\n"
                "  CData tlul_request_loopback_gpu_cov_tb__DOT__rst_ni;\n"
                "  CData tlul_request_loopback_gpu_cov_tb__DOT__debug_seen_q;\n"
                "};\n",
                encoding="utf-8",
            )
            template = root / "template.json"
            template.write_text(
                json.dumps(
                    {
                        "runner_args_template": {
                            "driver_defaults": {
                                "batch_length": 48,
                                "seed": 123,
                                "req_valid_pct": 96,
                            },
                            "debug_internal_output_names": [
                                "tlul_request_loopback_gpu_cov_tb__DOT__debug_seen_q"
                            ],
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            binary_out = root / "probe.bin"
            json_out = root / "probe.json"
            program_entries = root / "program_entries.bin"
            program_entries.write_bytes(b"\x01\x00\x00\x00\x00\x00\x00\x00")
            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                if argv[0] == "make":
                    (mdir / "libVtlul_request_loopback_gpu_cov_tb.a").write_bytes(b"fake-top")
                    (mdir / "libverilated.a").write_bytes(b"fake-verilated")
                    return None
                if argv[0] == "g++":
                    out_path = Path(argv[argv.index("-o") + 1])
                    out_path.write_bytes(b"fake-probe")
                    return None
                self.assertEqual(argv[0], str(binary_out))
                return mock.Mock(
                    stdout=json.dumps(
                            {
                                "target": "tlul_request_loopback",
                                "constructor_ok": True,
                                "field_offsets": {
                                    "done_o": 1,
                                    "tlul_request_loopback_gpu_cov_tb__DOT__debug_seen_q": 7,
                                },
                                "field_sizes": {
                                    "done_o": 1,
                                    "tlul_request_loopback_gpu_cov_tb__DOT__debug_seen_q": 1,
                                },
                                "watch_field_names": [
                                    "tlul_request_loopback_gpu_cov_tb__DOT__debug_seen_q"
                                ],
                                "host_clock_control": False,
                                "host_reset_control": False,
                                "root_size": 896,
                            }
                        )
                    + "\n"
                )

            with mock.patch.object(self.module, "find_prefix", return_value="Vtlul_request_loopback_gpu_cov_tb"):
                with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                    with mock.patch.object(
                        sys,
                        "argv",
                        [
                            "run_tlul_slice_host_probe.py",
                            "--mdir",
                            str(mdir),
                            "--template",
                            str(template),
                            "--binary-out",
                            str(binary_out),
                            "--json-out",
                            str(json_out),
                            "--state-out",
                            str(root / "state.bin"),
                            "--clock-sequence",
                            "1,0",
                            "--edge-state-dir",
                            str(root / "edge_trace"),
                "--extra-define=-DPROGRAM_ENTRIES_ARRAY=demo__DOT__gpu_cov_program_entries",
                            "--program-entries-bin",
                            str(program_entries),
                            "--set",
                            "cfg_source_mask_i=0x3f",
                        ],
                    ):
                        self.module.main()

            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["target"], "tlul_request_loopback")
            self.assertEqual(payload["configured_inputs"]["cfg_valid_i"], 1)
            self.assertEqual(payload["configured_inputs"]["cfg_batch_length_i"], 48)
            self.assertEqual(payload["configured_inputs"]["cfg_seed_i"], 123)
            self.assertEqual(payload["configured_inputs"]["cfg_req_valid_pct_i"], 96)
            self.assertEqual(payload["configured_inputs"]["cfg_source_mask_i"], 0x3F)
            self.assertEqual(
                payload["watch_field_names"],
                ["tlul_request_loopback_gpu_cov_tb__DOT__debug_seen_q"],
            )
            self.assertEqual(payload["model_build_mode"], "default_pch")
            self.assertEqual(
                payload["extra_defines"],
                ["-DPROGRAM_ENTRIES_ARRAY=demo__DOT__gpu_cov_program_entries"],
            )
            self.assertEqual(payload["program_entries_bin"], str(program_entries.resolve()))
            self.assertEqual(calls[0][0], "make")
            self.assertEqual(calls[1][0], "g++")
            self.assertIn('-DTARGET_NAME="tlul_request_loopback"', calls[1])
            self.assertIn("-DPROGRAM_ENTRIES_ARRAY=demo__DOT__gpu_cov_program_entries", calls[1])
            self.assertIn("-DHOST_CLOCK_CONTROL=0", calls[1])
            self.assertIn("-DHOST_RESET_CONTROL=0", calls[1])
            self.assertIn("-DROOT_RST_FIELD=tlul_request_loopback_gpu_cov_tb__DOT__rst_ni", calls[1])
            self.assertIn('-DEXTRA_WATCH_FIELDS_HEADER="tlul_slice_host_probe_watch_fields.h"', calls[1])
            self.assertIn("--state-out", calls[2])
            self.assertIn("--program-entries-bin", calls[2])
            self.assertIn(str(program_entries), calls[2])
            self.assertIn("--clock-sequence", calls[2])
            self.assertIn("1,0", calls[2])
            self.assertIn("--edge-state-dir", calls[2])
            self.assertIn("--set", calls[2])


if __name__ == "__main__":
    unittest.main()
