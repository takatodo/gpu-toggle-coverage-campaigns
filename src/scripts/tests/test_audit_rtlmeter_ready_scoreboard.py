#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_rtlmeter_ready_scoreboard.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditReadyScoreboardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_rtlmeter_ready_scoreboard_test", MODULE_PATH)

    def test_main_emits_tiered_ready_scoreboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_dir = root / "config" / "slice_launch_templates"
            validation_dir = root / "output" / "validation"
            work_dir = root / "work" / "vl_ir_exp"
            src_dir = root / "third_party" / "rtlmeter" / "designs" / "OpenTitan" / "src"
            config_dir.mkdir(parents=True)
            validation_dir.mkdir(parents=True)
            work_dir.mkdir(parents=True)
            src_dir.mkdir(parents=True)

            ready_names = [
                "tlul_socket_m1",
                "tlul_request_loopback",
                "tlul_fifo_sync",
                "tlul_socket_1n",
                "xbar_main",
                "tlul_err",
            ]
            index_path = config_dir / "index.json"
            index_path.write_text(
                json.dumps(
                    {
                        "index": [
                            {
                                "slice_name": name,
                                "status": "ready_for_campaign",
                                "launch_template_path": f"config/slice_launch_templates/{name}.json",
                            }
                            for name in ready_names
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            for name in ready_names:
                (config_dir / f"{name}.json").write_text(
                    json.dumps(
                        {
                            "runner_args_template": {
                                "coverage_tb_path": f"third_party/rtlmeter/designs/OpenTitan/src/{name}_gpu_cov_tb.sv",
                                "rtl_path": f"third_party/rtlmeter/designs/OpenTitan/src/{name}.sv",
                            }
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                (src_dir / f"{name}.sv").write_text(f"module {name}; endmodule\n", encoding="utf-8")

            for name in ["tlul_socket_m1", "tlul_request_loopback", "tlul_fifo_sync", "tlul_socket_1n", "xbar_main"]:
                (src_dir / f"{name}_gpu_cov_tb.sv").write_text(
                    f"module {name}_gpu_cov_tb; endmodule\n",
                    encoding="utf-8",
                )

            (validation_dir / "socket_m1_stock_hybrid_validation.json").write_text(
                json.dumps({"target": "tlul_socket_m1", "support_tier": "first_supported_target", "status": "ok"})
                + "\n",
                encoding="utf-8",
            )
            (validation_dir / "tlul_request_loopback_stock_hybrid_validation.json").write_text(
                json.dumps(
                    {
                        "target": "tlul_request_loopback",
                        "support_tier": "phase_b_reference_design",
                        "status": "ok",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            for name in ["tlul_fifo_sync", "tlul_socket_1n"]:
                mdir = work_dir / f"{name}_vl"
                mdir.mkdir(parents=True)
                (mdir / "vl_batch_gpu.cubin").write_bytes(b"cubin")
                (mdir / "vl_batch_gpu.meta.json").write_text("{}\n", encoding="utf-8")
                (mdir / "vl_classifier_report.json").write_text("{}\n", encoding="utf-8")
                (mdir / f"{name}_host_probe_report.json").write_text("{}\n", encoding="utf-8")

            json_out = root / "scoreboard.json"

            with mock.patch.object(self.module, "REPO_ROOT", root):
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = self.module.main(
                        [
                            "--index",
                            str(index_path),
                            "--validation-dir",
                            str(validation_dir),
                            "--json-out",
                            str(json_out),
                        ]
                    )

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            rows = {row["slice_name"]: row for row in payload["rows"]}
            self.assertEqual(payload["summary"]["ready_count"], 6)
            self.assertEqual(payload["summary"]["tier_counts"]["Tier S"], 1)
            self.assertEqual(payload["summary"]["tier_counts"]["Tier R"], 1)
            self.assertEqual(payload["summary"]["tier_counts"]["Tier B"], 2)
            self.assertEqual(payload["summary"]["tier_counts"]["Tier T"], 1)
            self.assertEqual(payload["summary"]["tier_counts"]["Tier M"], 1)
            self.assertEqual(rows["tlul_socket_m1"]["tier"], "Tier S")
            self.assertEqual(rows["tlul_request_loopback"]["tier"], "Tier R")
            self.assertEqual(rows["tlul_fifo_sync"]["tier"], "Tier B")
            self.assertEqual(rows["tlul_socket_1n"]["tier"], "Tier B")
            self.assertEqual(rows["xbar_main"]["tier"], "Tier T")
            self.assertEqual(rows["tlul_err"]["tier"], "Tier M")

    def test_reference_support_tier_and_host_mdir_are_preferred(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_dir = root / "config" / "slice_launch_templates"
            validation_dir = root / "output" / "validation"
            work_dir = root / "work" / "vl_ir_exp"
            src_dir = root / "third_party" / "rtlmeter" / "designs" / "OpenTitan" / "src"
            config_dir.mkdir(parents=True)
            validation_dir.mkdir(parents=True)
            work_dir.mkdir(parents=True)
            src_dir.mkdir(parents=True)

            index_path = config_dir / "index.json"
            index_path.write_text(
                json.dumps(
                    {
                        "index": [
                            {
                                "slice_name": "tlul_fifo_sync",
                                "status": "ready_for_campaign",
                                "launch_template_path": "config/slice_launch_templates/tlul_fifo_sync.json",
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (config_dir / "tlul_fifo_sync.json").write_text(
                json.dumps(
                    {
                        "runner_args_template": {
                            "coverage_tb_path": "third_party/rtlmeter/designs/OpenTitan/src/tlul_fifo_sync_gpu_cov_tb.sv",
                            "rtl_path": "third_party/rtlmeter/designs/OpenTitan/src/tlul_fifo_sync.sv",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (src_dir / "tlul_fifo_sync.sv").write_text("module tlul_fifo_sync; endmodule\n", encoding="utf-8")
            (src_dir / "tlul_fifo_sync_gpu_cov_tb.sv").write_text(
                "module tlul_fifo_sync_gpu_cov_tb; endmodule\n",
                encoding="utf-8",
            )
            (validation_dir / "tlul_fifo_sync_stock_hybrid_validation.json").write_text(
                json.dumps(
                    {
                        "target": "tlul_fifo_sync",
                        "support_tier": "thin_top_reference_design",
                        "status": "ok",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            host_mdir = work_dir / "tlul_fifo_sync_host_vl"
            host_mdir.mkdir(parents=True)
            (host_mdir / "vl_batch_gpu.cubin").write_bytes(b"cubin")
            (host_mdir / "tlul_fifo_sync_host_probe_report.json").write_text("{}\n", encoding="utf-8")

            json_out = root / "scoreboard.json"
            with mock.patch.object(self.module, "REPO_ROOT", root):
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = self.module.main(
                        [
                            "--index",
                            str(index_path),
                            "--validation-dir",
                            str(validation_dir),
                            "--json-out",
                            str(json_out),
                        ]
                    )

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            row = payload["rows"][0]
            self.assertEqual(row["tier"], "Tier R")
            self.assertEqual(row["tier_basis"], "stable_validation_reference")
            self.assertEqual(row["mdir"], str(host_mdir.resolve()))
            self.assertTrue(row["host_probe_exists"])


if __name__ == "__main__":
    unittest.main()
