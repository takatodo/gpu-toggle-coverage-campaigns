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
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_xuantie_c906_stock_hybrid_validation.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RunXuanTieC906StockHybridValidationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_xuantie_c906_stock_hybrid_validation_test", MODULE_PATH)

    def test_runner_writes_candidate_single_surface_validation_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mdir = root / "mdir"
            mdir.mkdir()
            json_out = root / "validation.json"
            flow_json = root / "flow.json"
            host_report = root / "host.json"
            host_state = root / "host.bin"
            final_state = root / "final.bin"
            inst_pat_source = root / "inst_source.pat"
            data_pat_source = root / "data_source.pat"
            inst_pat_source.write_text("deadbeef\n", encoding="utf-8")
            data_pat_source.write_text("cafebabe\n", encoding="utf-8")

            def _fake_run(cmd: list[str], **kwargs):
                argv = [str(item) for item in cmd]
                self.assertIn("--sanitize-host-only-internals", argv)
                self.assertIn("--host-post-reset-cycles", argv)
                self.assertIn("64", argv)
                flow_json.write_text(
                    json.dumps(
                        {
                            "target": "xuantie_c906",
                            "clock_ownership": "tb_timed_coroutine",
                            "support_tier": "candidate_non_opentitan_single_surface",
                            "mdir": str(mdir),
                            "nstates": 8,
                            "steps": 56,
                            "block_size": 256,
                            "sanitize_host_only_internals": True,
                            "host_report": str(host_report),
                            "host_state": str(host_state),
                            "final_state": str(final_state),
                            "storage_size": 1318912,
                            "outputs": {
                                "done_o": 0,
                                "cfg_signature_o": 3615,
                                "host_req_accepted_o": 3,
                                "device_req_accepted_o": 0,
                                "device_rsp_accepted_o": 3,
                                "host_rsp_accepted_o": 23,
                                "rsp_queue_overflow_o": 0,
                                "progress_cycle_count_o": 35,
                                "progress_signature_o": 76292,
                                "toggle_bitmap_word0_o": 47,
                                "toggle_bitmap_word1_o": 16,
                                "toggle_bitmap_word2_o": 18,
                            },
                            "changed_watch_field_count": 0,
                            "state_delta": {
                                "changed_byte_count": 32,
                                "changed_known_field_count": 0,
                                "first_changed_offsets": [2100],
                                "first_changed_known_fields": [],
                            },
                            "campaign_timing": {
                                "run_count": 1,
                                "timing_complete": True,
                                "wall_time_ms": 1.444,
                                "per_run_wall_time_ms": [1.444],
                                "gpu_kernel_time_complete": True,
                                "gpu_kernel_time_ms_total": 1.40144,
                                "per_run_gpu_kernel_time_ms": [1.40144],
                            },
                            "gpu_runs": [
                                {
                                    "index": 1,
                                    "steps": 56,
                                    "performance": {
                                        "wall_time_ms": 1.444,
                                        "gpu_kernel_time_ms": {
                                            "total": 1.40144,
                                            "per_launch": 0.025026,
                                        },
                                    },
                                }
                            ],
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                host_report.write_text(
                    json.dumps(
                        {
                            "constructor_ok": True,
                            "clock_ownership": "tb_timed_coroutine",
                            "done_o": 0,
                            "cfg_signature_o": 3615,
                            "host_req_accepted_o": 3,
                            "device_req_accepted_o": 0,
                            "device_rsp_accepted_o": 3,
                            "host_rsp_accepted_o": 23,
                            "rsp_queue_overflow_o": 0,
                            "progress_cycle_count_o": 35,
                            "progress_signature_o": 76292,
                            "toggle_bitmap_word0_o": 47,
                            "toggle_bitmap_word1_o": 16,
                            "toggle_bitmap_word2_o": 18,
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                return mock.Mock(
                    returncode=0,
                    stdout="\n".join(
                        [
                            "device 0: Demo GPU",
                            "ok: steps=56 kernels_per_step=1 patches_per_step=0 grid=1 block=256 nstates=8 storage=1318912 B",
                            "gpu_kernel_time_ms: total=1.401440  per_launch=0.025026  (CUDA events, kernels only; HtoD patches before launch excluded)",
                            "gpu_kernel_time: per_state=3.128 us  (per_launch / nstates)",
                            "wall_time_ms: 1.444  (host; one GPU sync unless RUN_VL_HYBRID_SYNC_EACH_STEP=1)",
                            '{"target":"xuantie_c906"}',
                        ]
                    )
                    + "\n",
                    stderr="",
                )

            argv = [
                "run_xuantie_c906_stock_hybrid_validation.py",
                "--mdir",
                str(mdir),
                "--campaign-threshold-bits",
                "8",
                "--inst-pat",
                str(inst_pat_source),
                "--data-pat",
                str(data_pat_source),
                "--json-out",
                str(json_out),
                "--flow-json-out",
                str(flow_json),
                "--host-report-out",
                str(host_report),
                "--host-state-out",
                str(host_state),
                "--final-state-out",
                str(final_state),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    rc = self.module.main(sys.argv[1:])

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["target"], "xuantie_c906")
            self.assertEqual(payload["support_tier"], "candidate_non_opentitan_single_surface")
            self.assertEqual(payload["acceptance_gate"], "candidate_non_opentitan_single_surface_v1")
            self.assertTrue(payload["reference_gate"]["passed"])
            self.assertEqual(payload["toggle_coverage"]["bits_hit"], 8)
            self.assertTrue(payload["campaign_measurement"]["threshold_satisfied"])
            self.assertEqual(payload["campaign_measurement"]["wall_time_ms"], 1.444)
            self.assertEqual(payload["inputs"]["sanitize_host_only_internals"], True)
            self.assertEqual(payload["inputs"]["inst_pat"], str(inst_pat_source.resolve()))
            self.assertEqual(payload["inputs"]["data_pat"], str(data_pat_source.resolve()))
            self.assertTrue((mdir / "inst.pat").is_symlink())
            self.assertTrue((mdir / "data.pat").is_symlink())


if __name__ == "__main__":
    unittest.main()
