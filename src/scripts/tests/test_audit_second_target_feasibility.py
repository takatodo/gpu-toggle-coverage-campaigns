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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_second_target_feasibility.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditSecondTargetFeasibilityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_second_target_feasibility_test", MODULE_PATH)

    def test_main_reports_second_target_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_dir = root / "config" / "slice_launch_templates"
            work_dir = root / "work" / "vl_ir_exp"
            src_dir = root / "third_party" / "rtlmeter" / "designs" / "OpenTitan" / "src"
            config_dir.mkdir(parents=True)
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
                                "can_prepare_launch": True,
                                "can_run_pilot": True,
                                "launch_template_path": "config/slice_launch_templates/tlul_fifo_sync.json",
                            },
                            {
                                "slice_name": "tlul_socket_1n",
                                "status": "ready_for_campaign",
                                "can_prepare_launch": True,
                                "can_run_pilot": True,
                                "launch_template_path": "config/slice_launch_templates/tlul_socket_1n.json",
                            },
                            {
                                "slice_name": "tlul_err",
                                "status": "ready_for_campaign",
                                "can_prepare_launch": True,
                                "can_run_pilot": True,
                                "launch_template_path": "config/slice_launch_templates/tlul_err.json",
                            },
                            {
                                "slice_name": "tlul_sink",
                                "status": "ready_for_campaign",
                                "can_prepare_launch": True,
                                "can_run_pilot": True,
                                "launch_template_path": "config/slice_launch_templates/tlul_sink.json",
                            },
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            for name in ("tlul_fifo_sync", "tlul_socket_1n", "tlul_err", "tlul_sink"):
                template_path = config_dir / f"{name}.json"
                template_path.write_text(
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

            for name in ("tlul_fifo_sync", "tlul_socket_1n"):
                (src_dir / f"{name}_gpu_cov_tb.sv").write_text(
                    f"module {name}_gpu_cov_tb; endmodule\n",
                    encoding="utf-8",
                )

            (src_dir / "tlul_fifo_sync_gpu_cov_cpu_replay_tb.sv").write_text(
                "module tlul_fifo_sync_gpu_cov_cpu_replay_tb; endmodule\n",
                encoding="utf-8",
            )

            for name in ("tlul_fifo_sync", "tlul_socket_1n"):
                mdir = work_dir / f"{name}_vl"
                mdir.mkdir(parents=True)
                (mdir / "vl_batch_gpu.cubin").write_bytes(b"cubin")
                (mdir / "vl_batch_gpu.meta.json").write_text("{}\n", encoding="utf-8")
                (mdir / "vl_classifier_report.json").write_text("{}\n", encoding="utf-8")
                (mdir / f"{name}_host_probe_report.json").write_text("{}\n", encoding="utf-8")
                (mdir / f"{name}_host_gpu_flow_watch_summary.json").write_text(
                    json.dumps({"changed_watch_field_count": 0}) + "\n",
                    encoding="utf-8",
                )

            search_dir = work_dir / "tlul_socket_1n_vl" / "watch_handoff_search"
            search_dir.mkdir(parents=True)
            (search_dir / "summary.json").write_text(
                json.dumps({"search_assessment": {"decision": "no_handoff_case_found_in_search_space"}}) + "\n",
                encoding="utf-8",
            )

            json_out = root / "audit.json"

            with mock.patch.object(self.module, "REPO_ROOT", root):
                with contextlib.redirect_stdout(io.StringIO()):
                    rc = self.module.main(["--index", str(index_path), "--json-out", str(json_out)])

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            rows = {row["slice_name"]: row for row in payload["candidates"]}

            self.assertEqual(
                rows["tlul_fifo_sync"]["current_blocker"],
                "no_gpu_driven_deltas_under_current_model",
            )
            self.assertTrue(rows["tlul_fifo_sync"]["cpu_replay_wrapper_exists"])
            self.assertEqual(
                rows["tlul_socket_1n"]["current_blocker"],
                "no_gpu_driven_deltas_under_current_model",
            )
            self.assertEqual(rows["tlul_socket_1n"]["watch_search_decision"], "no_handoff_case_found_in_search_space")
            self.assertEqual(rows["tlul_err"]["current_blocker"], "missing_coverage_tb_source")
            self.assertEqual(rows["tlul_sink"]["current_blocker"], "missing_coverage_tb_source")

            recommendation = payload["recommendation"]
            self.assertEqual(
                recommendation["if_promote_thinner_host_driven_top"]["recommended_seed"],
                "tlul_fifo_sync",
            )
            self.assertEqual(
                recommendation["if_keep_current_tb_timed_model"]["recommended_action"],
                "restore_or_generate_tier2_coverage_tb_sources",
            )
            self.assertEqual(
                recommendation["if_keep_current_tb_timed_model"]["blocked_candidates"],
                ["tlul_err", "tlul_sink"],
            )


if __name__ == "__main__":
    unittest.main()
