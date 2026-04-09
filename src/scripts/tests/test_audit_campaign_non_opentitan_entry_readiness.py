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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_non_opentitan_entry_readiness.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignNonOpentitanEntryReadinessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_non_opentitan_entry_readiness_test", MODULE_PATH)

    def test_blocks_family_pilot_when_legacy_bench_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            legacy_output_dir = root / "legacy"
            legacy_output_dir.mkdir(parents=True)
            legacy_verilator = root / "verilator"
            legacy_verilator.write_text("", encoding="utf-8")
            rtlmeter_python = root / "python"
            rtlmeter_python.write_text("", encoding="utf-8")

            payload = self.module.build_entry_readiness(
                entry_payload={
                    "decision": {
                        "recommended_family": "XuanTie",
                        "recommended_entry_mode": "family_pilot",
                    }
                },
                legacy_output_dir=legacy_output_dir,
                legacy_bench_path=root / "missing_bench",
                legacy_verilator_path=legacy_verilator,
                rtlmeter_venv_python=rtlmeter_python,
                bootstrap_summary_dir=root / "bootstrap",
            )

            self.assertEqual(payload["decision"]["readiness"], "blocked_by_missing_legacy_bench")

    def test_reports_ready_when_all_family_pilot_prerequisites_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            legacy_output_dir = root / "legacy"
            legacy_output_dir.mkdir(parents=True)
            bench = root / "verilator_sim_accel_bench"
            bench.write_text("", encoding="utf-8")
            verilator = root / "verilator"
            verilator.write_text("", encoding="utf-8")
            python_bin = root / "python"
            python_bin.write_text("", encoding="utf-8")

            payload = self.module.build_entry_readiness(
                entry_payload={
                    "decision": {
                        "recommended_family": "XuanTie",
                        "recommended_entry_mode": "family_pilot",
                    }
                },
                legacy_output_dir=legacy_output_dir,
                legacy_bench_path=bench,
                legacy_verilator_path=verilator,
                rtlmeter_venv_python=python_bin,
                bootstrap_summary_dir=root / "bootstrap",
            )

            self.assertEqual(payload["decision"]["readiness"], "ready_to_run_family_pilot")

    def test_prefers_failed_legacy_artifact_over_naive_presence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            legacy_output_dir = root / "legacy"
            legacy_output_dir.mkdir(parents=True)
            bench = root / "verilator_sim_accel_bench"
            bench.write_text("", encoding="utf-8")
            verilator = root / "verilator"
            verilator.write_text("", encoding="utf-8")
            python_bin = root / "python"
            python_bin.write_text("", encoding="utf-8")
            (legacy_output_dir / "xuantie_family_gpu_toggle_validation.json").write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "execute_status": "failed",
                                "returncode": 1,
                                "stderr_tail": "FileNotFoundError: verilator_sim_accel_bench",
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_entry_readiness(
                entry_payload={
                    "decision": {
                        "recommended_family": "XuanTie",
                        "recommended_entry_mode": "family_pilot",
                    }
                },
                legacy_output_dir=legacy_output_dir,
                legacy_bench_path=bench,
                legacy_verilator_path=verilator,
                rtlmeter_venv_python=python_bin,
                bootstrap_summary_dir=root / "bootstrap",
            )

            self.assertEqual(payload["decision"]["readiness"], "legacy_family_pilot_failed")
            self.assertEqual(
                payload["decision"]["reason"],
                "legacy_family_pilot_artifact_records_missing_legacy_bench",
            )

    def test_reports_override_ready_when_family_pilot_failed_and_bootstrap_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            legacy_output_dir = root / "legacy"
            legacy_output_dir.mkdir(parents=True)
            bootstrap_dir = root / "bootstrap"
            bootstrap_dir.mkdir(parents=True)
            bench = root / "verilator_sim_accel_bench"
            bench.write_text("", encoding="utf-8")
            verilator = root / "verilator"
            verilator.write_text("", encoding="utf-8")
            python_bin = root / "python"
            python_bin.write_text("", encoding="utf-8")
            (legacy_output_dir / "xuantie_family_gpu_toggle_validation.json").write_text(
                json.dumps(
                    {
                        "results": [
                            {
                                "execute_status": "failed",
                                "returncode": 1,
                                "stderr_tail": "FileNotFoundError: verilator_sim_accel_bench",
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (bootstrap_dir / "xuantie_e902_gpu_cov_gate_stock_verilator_cc_bootstrap.json").write_text(
                json.dumps(
                    {
                        "design": "XuanTie-E902",
                        "config": "gpu_cov_gate",
                        "compile_case": "XuanTie-E902:gpu_cov_gate",
                        "status": "ok",
                        "returncode": 0,
                        "classes_mk": "/tmp/Vxuantie_e902_gpu_cov_tb_classes.mk",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_entry_readiness(
                entry_payload={
                    "decision": {
                        "recommended_family": "XuanTie",
                        "recommended_entry_mode": "family_pilot",
                    }
                },
                legacy_output_dir=legacy_output_dir,
                legacy_bench_path=bench,
                legacy_verilator_path=verilator,
                rtlmeter_venv_python=python_bin,
                bootstrap_summary_dir=bootstrap_dir,
            )

            self.assertEqual(
                payload["decision"]["readiness"],
                "legacy_family_pilot_failed_but_single_surface_override_ready",
            )
            self.assertEqual(payload["single_surface_bootstrap_summary"]["ready_count"], 1)
            self.assertEqual(payload["single_surface_bootstrap_summary"]["ready_designs"], ["XuanTie-E902"])

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            entry_path = root / "entry.json"
            bench = root / "bench"
            verilator = root / "verilator"
            python_bin = root / "python"
            legacy_dir = root / "legacy"
            bootstrap_dir = root / "bootstrap"
            json_out = root / "readiness.json"
            legacy_dir.mkdir(parents=True)
            bootstrap_dir.mkdir(parents=True)
            bench.write_text("", encoding="utf-8")
            verilator.write_text("", encoding="utf-8")
            python_bin.write_text("", encoding="utf-8")
            entry_path.write_text(
                json.dumps(
                    {
                        "decision": {
                            "recommended_family": "XuanTie",
                            "recommended_entry_mode": "family_pilot",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_non_opentitan_entry_readiness.py",
                "--entry-json",
                str(entry_path),
                "--legacy-output-dir",
                str(legacy_dir),
                "--legacy-bench",
                str(bench),
                "--legacy-verilator",
                str(verilator),
                "--rtlmeter-venv-python",
                str(python_bin),
                "--bootstrap-summary-dir",
                str(bootstrap_dir),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_non_opentitan_entry_readiness")


if __name__ == "__main__":
    unittest.main()
