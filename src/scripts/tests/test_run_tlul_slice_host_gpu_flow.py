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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "run_tlul_slice_host_gpu_flow.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunTlulSliceHostGpuFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_tlul_slice_host_gpu_flow_test", MODULE_PATH)

    def test_run_gpu_once_forwards_sanitize_flag(self) -> None:
        seen: dict[str, object] = {}

        def _fake_run(cmd: list[str], **kwargs):
            seen["cmd"] = list(cmd)
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
            self.module._run_gpu_once(
                mdir=Path("/tmp/mdir"),
                nstates=1,
                steps=1,
                block_size=1,
                init_state=Path("/tmp/init.bin"),
                dump_state=Path("/tmp/out.bin"),
                patches=[],
                sanitize_host_only_internals=True,
            )

        cmd = seen["cmd"]
        assert isinstance(cmd, list)
        self.assertIn("--sanitize-host-only-internals", cmd)

    def test_flow_forwards_memory_image_arguments_to_host_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "summary.json"
            memory_image = root / "program.bin"
            memory_image.write_bytes(b"\x01\x02\x03\x04")
            memory_target = root / "target.json"
            memory_target.write_text(
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
                if argv[1].endswith("run_tlul_slice_host_probe.py"):
                    self.assertIn("--memory-image", argv)
                    self.assertIn(str(memory_image), argv)
                    self.assertIn("--memory-image-target", argv)
                    self.assertIn(str(memory_target), argv)
                    host_report = Path(argv[argv.index("--json-out") + 1])
                    host_state = Path(argv[argv.index("--state-out") + 1])
                    host_report.write_text(
                        json.dumps(
                            {
                                "target": "xiangshan",
                                "root_size": 64,
                                "field_offsets": {
                                    "done_o": 0,
                                    "progress_cycle_count_o": 4,
                                },
                                "field_sizes": {
                                    "done_o": 1,
                                    "progress_cycle_count_o": 4,
                                },
                                "watch_field_names": [],
                                "configured_inputs": {"cfg_valid_i": 1},
                                "host_clock_control": False,
                                "host_reset_control": False,
                            }
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    host_state.write_bytes(bytes(64))
                    return None
                final_state = Path(argv[argv.index("--dump-state") + 1])
                final_blob = bytearray(64)
                final_blob[4:8] = (3).to_bytes(4, "little")
                final_state.write_bytes(final_blob)
                return mock.Mock(returncode=0, stdout="", stderr="")

            argv = [
                "run_tlul_slice_host_gpu_flow.py",
                "--mdir",
                str(mdir),
                "--target",
                "xiangshan",
                "--support-tier",
                "candidate_non_opentitan_single_surface",
                "--nstates",
                "8",
                "--steps",
                "56",
                "--memory-image",
                str(memory_image),
                "--memory-image-target",
                str(memory_target),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    self.module.main()

            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["memory_image"], str(memory_image.resolve()))
            self.assertEqual(payload["memory_image_target"], str(memory_target.resolve()))
            self.assertTrue(calls[0][1].endswith("run_tlul_slice_host_probe.py"))
            self.assertTrue(calls[1][1].endswith("run_vl_hybrid.py"))

    def test_flow_reports_changed_watch_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "summary.json"
            program_entries = root / "program_entries.bin"
            program_entries.write_bytes(b"\x01\x00\x00\x00\x00\x00\x00\x00")
            calls: list[list[str]] = []

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                if argv[1].endswith("run_tlul_slice_host_probe.py"):
                    host_report = Path(argv[argv.index("--json-out") + 1])
                    host_state = Path(argv[argv.index("--state-out") + 1])
                    host_report.write_text(
                        json.dumps(
                            {
                                "target": "tlul_socket_1n",
                                "root_size": 64,
                                "field_offsets": {
                                    "done_o": 0,
                                    "progress_cycle_count_o": 4,
                                    "tlul_socket_1n_gpu_cov_tb__DOT__dut__DOT__fifo_h__DOT____Vcellout__reqfifo__rvalid_o": 8,
                                    "tlul_socket_1n_gpu_cov_tb__DOT__tl_h_o": 12,
                                },
                                "field_sizes": {
                                    "done_o": 1,
                                    "progress_cycle_count_o": 4,
                                    "tlul_socket_1n_gpu_cov_tb__DOT__dut__DOT__fifo_h__DOT____Vcellout__reqfifo__rvalid_o": 1,
                                    "tlul_socket_1n_gpu_cov_tb__DOT__tl_h_o": 12,
                                },
                                "watch_field_names": [
                                    "tlul_socket_1n_gpu_cov_tb__DOT__dut__DOT__fifo_h__DOT____Vcellout__reqfifo__rvalid_o",
                                    "tlul_socket_1n_gpu_cov_tb__DOT__tl_h_o",
                                ],
                                "configured_inputs": {"cfg_valid_i": 1},
                            }
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    host_blob = bytearray(64)
                    host_blob[4:8] = (2).to_bytes(4, "little")
                    host_blob[8] = 0
                    host_blob[12:24] = bytes.fromhex("0102030405060708090a0b0c")
                    host_state.write_bytes(host_blob)
                    return None
                final_state = Path(argv[argv.index("--dump-state") + 1])
                final_blob = bytearray(64)
                final_blob[4:8] = (2).to_bytes(4, "little")
                final_blob[8] = 1
                final_blob[12:24] = bytes.fromhex("0102030405060708090a0bff")
                final_state.write_bytes(final_blob)
                return mock.Mock(
                    returncode=0,
                    stdout="\n".join(
                        [
                            "device 0: Demo GPU",
                            "ok: steps=56 kernels_per_step=1 patches_per_step=0 grid=1 block=256 nstates=32 storage=64 B",
                            "gpu_kernel_time_ms: total=1.250000  per_launch=1.250000  (CUDA events, kernels only; HtoD patches before launch excluded)",
                            "gpu_kernel_time: per_state=39.062 us  (per_launch / nstates)",
                            "wall_time_ms: 1.500  (host; one GPU sync unless RUN_VL_HYBRID_SYNC_EACH_STEP=1)",
                        ]
                    )
                    + "\n",
                    stderr="",
                )

            argv = [
                "run_tlul_slice_host_gpu_flow.py",
                "--mdir",
                str(mdir),
                "--target",
                "tlul_socket_1n",
                "--support-tier",
                "candidate_second_supported_target",
                "--nstates",
                "32",
                "--steps",
                "56",
                "--host-watch-field",
                "tlul_socket_1n_gpu_cov_tb__DOT__dut__DOT__fifo_h__DOT____Vcellout__reqfifo__rvalid_o",
                "--host-probe-extra-define=-DPROGRAM_ENTRIES_ARRAY=demo__DOT__gpu_cov_program_entries",
                "--program-entries-bin",
                str(program_entries),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(self.module.cmp, "probe_root_layout", return_value=[]):
                    with mock.patch.object(
                        self.module.cmp,
                        "annotate_state_offset",
                        side_effect=lambda _layout, offset: (
                            {
                                "field_name": "tlul_fifo_sync_gpu_cov_host_tb__DOT__core__DOT__watch_q",
                                "field_offset": 12,
                                "field_size": 1,
                                "field_byte_offset": 0,
                            }
                            if offset == 12
                            else None
                        ),
                    ):
                        with mock.patch.object(sys, "argv", argv):
                            self.module.main()

            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["target"], "tlul_socket_1n")
            self.assertEqual(payload["support_tier"], "candidate_second_supported_target")
            self.assertEqual(payload["outputs"]["progress_cycle_count_o"], 2)
            self.assertEqual(payload["changed_watch_field_count"], 2)
            self.assertEqual(payload["state_delta"]["changed_byte_count"], 2)
            self.assertEqual(payload["state_delta"]["changed_known_field_count"], 2)
            self.assertEqual(payload["campaign_timing"]["run_count"], 1)
            self.assertTrue(payload["campaign_timing"]["timing_complete"])
            self.assertEqual(payload["campaign_timing"]["wall_time_ms"], 1.5)
            self.assertEqual(payload["gpu_runs"][0]["performance"]["wall_time_ms"], 1.5)
            reqfifo = payload["watched_fields"][
                "tlul_socket_1n_gpu_cov_tb__DOT__dut__DOT__fifo_h__DOT____Vcellout__reqfifo__rvalid_o"
            ]
            self.assertTrue(reqfifo["changed"])
            self.assertEqual(reqfifo["host_probe_hex"], "0x00")
            self.assertEqual(reqfifo["gpu_final_hex"], "0x01")
            tlh = payload["watched_fields"]["tlul_socket_1n_gpu_cov_tb__DOT__tl_h_o"]
            self.assertTrue(tlh["changed"])
            self.assertEqual(
                payload["gpu_runs"][0]["delta_from_host_probe"]["first_changed_known_fields"],
                [
                    "tlul_socket_1n_gpu_cov_tb__DOT__dut__DOT__fifo_h__DOT____Vcellout__reqfifo__rvalid_o",
                    "tlul_socket_1n_gpu_cov_tb__DOT__tl_h_o",
                ],
            )
            self.assertTrue(calls[0][1].endswith("run_tlul_slice_host_probe.py"))
            self.assertIn("--watch-field", calls[0])
            self.assertIn(
                "--extra-define=-DPROGRAM_ENTRIES_ARRAY=demo__DOT__gpu_cov_program_entries",
                calls[0],
            )
            self.assertIn("--program-entries-bin", calls[0])
            self.assertIn(str(program_entries), calls[0])
            self.assertTrue(calls[1][1].endswith("run_vl_hybrid.py"))

    def test_host_owned_clock_sequence_runs_multiple_gpu_invocations(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "summary.json"
            calls: list[list[str]] = []
            edge_dir = mdir / "host_edge_trace"

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                calls.append(argv)
                if argv[1].endswith("run_tlul_slice_host_probe.py"):
                    host_report = Path(argv[argv.index("--json-out") + 1])
                    payload = {
                        "target": "tlul_fifo_sync",
                        "root_size": 64,
                        "host_clock_control": True,
                        "host_reset_control": True,
                        "reset_field_name": "rst_ni",
                        "reset_deasserted_value": 1,
                        "field_offsets": {
                            "clk_i": 0,
                            "rst_ni": 1,
                            "done_o": 4,
                            "progress_cycle_count_o": 8,
                            "tlul_fifo_sync_gpu_cov_host_tb__DOT__core__DOT__watch_q": 12,
                        },
                        "field_sizes": {
                            "clk_i": 1,
                            "rst_ni": 1,
                            "done_o": 1,
                            "progress_cycle_count_o": 4,
                            "tlul_fifo_sync_gpu_cov_host_tb__DOT__core__DOT__watch_q": 1,
                        },
                        "watch_field_names": [
                            "tlul_fifo_sync_gpu_cov_host_tb__DOT__core__DOT__watch_q"
                        ],
                        "configured_inputs": {"cfg_valid_i": 1},
                    }
                    if "--clock-sequence" in argv:
                        edge_dir.mkdir(parents=True, exist_ok=True)
                        edge1 = edge_dir / "edge_1.bin"
                        edge2 = edge_dir / "edge_2.bin"
                        host1 = bytearray(64)
                        host1[0] = 1
                        host1[1] = 1
                        host1[8:12] = (6).to_bytes(4, "little")
                        host1[12] = 0
                        edge1.write_bytes(host1)
                        host2 = bytearray(64)
                        host2[1] = 1
                        host2[8:12] = (7).to_bytes(4, "little")
                        host2[12] = 0
                        edge2.write_bytes(host2)
                        payload["edge_runs"] = [
                            {
                                "index": 1,
                                "clock_level": 1,
                                "dump_state": str(edge1),
                                "progress_cycle_count_o": 6,
                                "progress_signature_o": 0,
                                "done_o": 0,
                                "toggle_bitmap_word0_o": 0,
                                "toggle_bitmap_word1_o": 0,
                                "toggle_bitmap_word2_o": 0,
                            },
                            {
                                "index": 2,
                                "clock_level": 0,
                                "dump_state": str(edge2),
                                "progress_cycle_count_o": 7,
                                "progress_signature_o": 0,
                                "done_o": 0,
                                "toggle_bitmap_word0_o": 0,
                                "toggle_bitmap_word1_o": 0,
                                "toggle_bitmap_word2_o": 0,
                            },
                        ]
                    else:
                        host_state = Path(argv[argv.index("--state-out") + 1])
                        host_blob = bytearray(64)
                        host_blob[1] = 1
                        host_blob[8:12] = (6).to_bytes(4, "little")
                        host_blob[12] = 0
                        host_state.write_bytes(host_blob)
                    host_report.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                    return None

                dump_state = Path(argv[argv.index("--dump-state") + 1])
                patch_values = [argv[i + 1] for i, token in enumerate(argv) if token == "--patch"]
                if len(calls) == 3:
                    self.assertEqual(patch_values, ["0:0x01", "1:0x01"])
                    blob = bytearray(64)
                    blob[0] = 1
                    blob[1] = 1
                    blob[8:12] = (6).to_bytes(4, "little")
                    blob[12] = 0
                    dump_state.write_bytes(blob)
                    return mock.Mock(
                        returncode=0,
                        stdout="\n".join(
                            [
                                "device 0: Demo GPU",
                                "ok: steps=1 kernels_per_step=1 patches_per_step=2 grid=1 block=256 nstates=1 storage=64 B",
                                "gpu_kernel_time_ms: total=0.500000  per_launch=0.500000  (CUDA events, kernels only; HtoD patches before launch excluded)",
                                "gpu_kernel_time: per_state=500.000 us  (per_launch / nstates)",
                                "wall_time_ms: 1.250  (host; one GPU sync unless RUN_VL_HYBRID_SYNC_EACH_STEP=1)",
                            ]
                        )
                        + "\n",
                        stderr="",
                    )

                self.assertEqual(patch_values, ["0:0x00", "1:0x01"])
                blob = bytearray(64)
                blob[1] = 1
                blob[8:12] = (7).to_bytes(4, "little")
                blob[12] = 1
                dump_state.write_bytes(blob)
                return mock.Mock(
                    returncode=0,
                    stdout="\n".join(
                        [
                            "device 0: Demo GPU",
                            "ok: steps=1 kernels_per_step=1 patches_per_step=2 grid=1 block=256 nstates=1 storage=64 B",
                            "gpu_kernel_time_ms: total=0.750000  per_launch=0.750000  (CUDA events, kernels only; HtoD patches before launch excluded)",
                            "gpu_kernel_time: per_state=750.000 us  (per_launch / nstates)",
                            "wall_time_ms: 1.750  (host; one GPU sync unless RUN_VL_HYBRID_SYNC_EACH_STEP=1)",
                        ]
                    )
                    + "\n",
                    stderr="",
                )

            argv = [
                "run_tlul_slice_host_gpu_flow.py",
                "--mdir",
                str(mdir),
                "--target",
                "tlul_fifo_sync",
                "--support-tier",
                "thin_top_seed",
                "--nstates",
                "1",
                "--steps",
                "99",
                "--host-clock-sequence",
                "1,0",
                "--host-clock-sequence-steps",
                "1",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(self.module.cmp, "probe_root_layout", return_value=[]):
                    with mock.patch.object(
                        self.module.cmp,
                        "annotate_state_offset",
                        side_effect=lambda _layout, offset: (
                            {
                                "field_name": "tlul_fifo_sync_gpu_cov_host_tb__DOT__core__DOT__watch_q",
                                "field_offset": 12,
                                "field_size": 1,
                                "field_byte_offset": 0,
                            }
                            if offset == 12
                            else None
                        ),
                    ):
                        with mock.patch.object(sys, "argv", argv):
                            self.module.main()

            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["clock_ownership"], "host_direct_ports")
            self.assertEqual(payload["host_clock_sequence"], [1, 0])
            self.assertEqual(len(payload["gpu_runs"]), 2)
            self.assertEqual(len(payload["host_edge_runs"]), 2)
            self.assertEqual(payload["outputs"]["progress_cycle_count_o"], 7)
            self.assertEqual(payload["changed_watch_field_count"], 1)
            self.assertEqual(payload["state_delta"]["changed_byte_count"], 2)
            self.assertEqual(payload["host_edge_trace_report"], str(mdir / "mdir_host_edge_trace.json"))
            self.assertEqual(payload["edge_parity"]["compared_edge_count"], 2)
            self.assertEqual(payload["edge_parity"]["role_summary"], {"design_state": 1})
            self.assertFalse(payload["edge_parity"]["all_edges_internal_only"])
            self.assertEqual(payload["campaign_timing"]["run_count"], 2)
            self.assertTrue(payload["campaign_timing"]["timing_complete"])
            self.assertEqual(payload["campaign_timing"]["per_run_wall_time_ms"], [1.25, 1.75])
            self.assertEqual(payload["campaign_timing"]["wall_time_ms"], 3.0)
            self.assertEqual(payload["gpu_runs"][0]["performance"]["wall_time_ms"], 1.25)
            self.assertEqual(payload["gpu_runs"][1]["performance"]["wall_time_ms"], 1.75)
            self.assertEqual(
                payload["gpu_runs"][0]["delta_from_host_probe"]["first_changed_known_fields"],
                ["clk_i"],
            )
            self.assertEqual(
                payload["gpu_runs"][1]["delta_from_host_probe"]["first_changed_known_fields"],
                [
                    "progress_cycle_count_o",
                    "tlul_fifo_sync_gpu_cov_host_tb__DOT__core__DOT__watch_q",
                ],
            )
            self.assertEqual(
                payload["edge_parity"]["edges"][1]["parity"]["first_changed_known_fields"],
                ["tlul_fifo_sync_gpu_cov_host_tb__DOT__core__DOT__watch_q"],
            )
            self.assertTrue(
                payload["watched_fields"][
                    "tlul_fifo_sync_gpu_cov_host_tb__DOT__core__DOT__watch_q"
                ]["changed"]
            )


if __name__ == "__main__":
    unittest.main()
