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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "run_tlul_slice_handoff_parity_probe.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunTlulSliceHandoffParityProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_tlul_slice_handoff_parity_probe_test", MODULE_PATH)

    def test_main_builds_parity_probe_and_annotates_edge_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            template = root / "template.json"
            template.write_text(
                json.dumps(
                    {
                        "runner_args_template": {"driver_defaults": {"seed": 7}},
                        "debug_internal_output_names": ["demo__DOT__phase_q"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            binary_out = root / "probe.bin"
            json_out = root / "probe.json"
            host_dir = root / "host_eval"
            root_dir = root / "root_eval"
            fake_dir = root / "fake_syms_eval"
            raw_import_dir = root / "raw_import_eval"
            host_dir.mkdir()
            root_dir.mkdir()
            fake_dir.mkdir()
            raw_import_dir.mkdir()
            (host_dir / "edge_1.bin").write_bytes(b"\x00\x01\x02\x03")
            (root_dir / "edge_1.bin").write_bytes(b"\x00\x09\x02\x03")
            (fake_dir / "edge_1.bin").write_bytes(b"\x00\x08\x02\x03")
            (raw_import_dir / "edge_1.bin").write_bytes(b"\x00\x01\x02\x03")

            parity_stdout = json.dumps(
                {
                    "target": "tlul_fifo_sync",
                    "constructor_ok": True,
                    "field_offsets": {"clk_i": 0, "progress_cycle_count_o": 1},
                    "field_sizes": {"clk_i": 1, "progress_cycle_count_o": 1},
                    "watch_field_names": ["demo__DOT__phase_q"],
                    "host_clock_control": True,
                    "host_reset_control": True,
                    "root_size": 4,
                    "edge_runs": [
                        {
                            "index": 1,
                            "clock_level": 1,
                            "host_eval": {
                                "dump_state": str(host_dir / "edge_1.bin"),
                                "done_o": 0,
                                "progress_cycle_count_o": 7,
                                "progress_signature_o": 1,
                                "sim_time": 11,
                                "toggle_bitmap_word0_o": 2,
                                "toggle_bitmap_word1_o": 3,
                                "toggle_bitmap_word2_o": 4,
                            },
                            "root_eval": {
                                "dump_state": str(root_dir / "edge_1.bin"),
                                "done_o": 0,
                                "progress_cycle_count_o": 6,
                                "progress_signature_o": 0,
                                "sim_time": 11,
                                "toggle_bitmap_word0_o": 0,
                                "toggle_bitmap_word1_o": 0,
                                "toggle_bitmap_word2_o": 0,
                            },
                            "fake_syms_eval": {
                                "dump_state": str(fake_dir / "edge_1.bin"),
                                "done_o": 0,
                                "progress_cycle_count_o": 6,
                                "progress_signature_o": 0,
                                "sim_time": 11,
                                "toggle_bitmap_word0_o": 0,
                                "toggle_bitmap_word1_o": 0,
                                "toggle_bitmap_word2_o": 0,
                            },
                            "raw_import_eval": {
                                "dump_state": str(raw_import_dir / "edge_1.bin"),
                                "done_o": 0,
                                "progress_cycle_count_o": 7,
                                "progress_signature_o": 1,
                                "sim_time": 11,
                                "toggle_bitmap_word0_o": 2,
                                "toggle_bitmap_word1_o": 3,
                                "toggle_bitmap_word2_o": 4,
                            },
                        }
                    ],
                }
            )

            with mock.patch.object(
                self.module.host_probe,
                "find_prefix",
                return_value="Vtlul_fifo_sync_gpu_cov_host_tb",
            ), mock.patch.object(
                self.module.host_probe,
                "_derive_target",
                return_value="tlul_fifo_sync",
            ), mock.patch.object(
                self.module.host_probe,
                "_load_template_watch_fields",
                return_value=["demo__DOT__phase_q"],
            ), mock.patch.object(
                self.module.host_probe,
                "_rewrite_top_module_watch_fields",
                side_effect=lambda prefix, target, items: items,
            ), mock.patch.object(
                self.module.host_probe,
                "_load_template_settings",
                return_value={"cfg_seed_i": 7},
            ), mock.patch.object(
                self.module.host_probe,
                "_apply_overrides",
                side_effect=lambda settings, overrides: dict(settings, cfg_req_valid_pct_i=92),
            ), mock.patch.object(
                self.module.host_probe,
                "build_probe_binary",
                return_value=(
                    binary_out,
                    "Vtlul_fifo_sync_gpu_cov_host_tb",
                    "tlul_fifo_sync",
                    {
                        "clock_field_name": "clk_i",
                        "reset_report_name": "rst_ni",
                        "host_clock_control": True,
                        "host_reset_control": True,
                    },
                ),
            ) as build_probe_binary, mock.patch.object(
                self.module.host_probe,
                "_write_json",
            ) as write_json, mock.patch.object(
                self.module.subprocess,
                "run",
                return_value=mock.Mock(stdout=parity_stdout),
            ) as run_cmd, mock.patch.object(
                self.module.cmp,
                "probe_root_layout",
                return_value=[
                    {"name": "clk_i", "offset": 0, "size": 1},
                    {"name": "progress_cycle_count_o", "offset": 1, "size": 1},
                ],
            ), mock.patch.object(
                self.module.cmp,
                "annotate_state_offset",
                side_effect=lambda layout, offset: (
                    {"field_name": "progress_cycle_count_o", "field_offset": 1, "field_size": 1, "field_byte_offset": 0}
                    if offset == 1
                    else {"field_name": "clk_i", "field_offset": 0, "field_size": 1, "field_byte_offset": 0}
                    if offset == 0
                    else None
                ),
            ):
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "run_tlul_slice_handoff_parity_probe.py",
                        "--mdir",
                        str(mdir),
                        "--template",
                        str(template),
                        "--binary-out",
                        str(binary_out),
                        "--json-out",
                        str(json_out),
                        "--clock-sequence",
                        "1,0",
                    ],
                ):
                    self.module.main()

            build_kwargs = build_probe_binary.call_args.kwargs
            self.assertEqual(build_kwargs["probe_source"], self.module.PARITY_SOURCE)
            self.assertIn(
                "-DROOT_EVAL_FN=Vtlul_fifo_sync_gpu_cov_host_tb___024root___eval",
                build_kwargs["extra_defines"],
            )
            run_argv = [str(item) for item in run_cmd.call_args.args[0]]
            self.assertIn("--clock-sequence", run_argv)
            self.assertIn("1,0", run_argv)
            self.assertIn("--host-edge-state-dir", run_argv)
            self.assertIn("--root-eval-edge-state-dir", run_argv)
            payload = write_json.call_args.args[1]
            self.assertEqual(payload["configured_inputs"]["cfg_seed_i"], 7)
            self.assertEqual(payload["configured_inputs"]["cfg_req_valid_pct_i"], 92)
            self.assertEqual(payload["edge_parity"]["compared_edge_count"], 1)
            self.assertFalse(payload["edge_parity"]["all_edges_match_exact"])
            self.assertEqual(payload["edge_parity"]["role_summary"]["top_level_io"], 1)
            edge = payload["edge_parity"]["edges"][0]
            self.assertEqual(edge["parity"]["changed_byte_count"], 1)
            self.assertEqual(edge["parity"]["first_changed_known_fields"], ["progress_cycle_count_o"])
            self.assertEqual(payload["fake_syms_edge_parity"]["compared_edge_count"], 1)
            self.assertEqual(payload["raw_import_edge_parity"]["compared_edge_count"], 1)
            self.assertTrue(payload["raw_import_edge_parity"]["all_edges_match_exact"])


if __name__ == "__main__":
    unittest.main()
