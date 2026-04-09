#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = SCRIPT_DIR.parents[1]
CONTRACTS_PATH = SCRIPT_DIR / "opentitan_tlul_slice_contracts.py"
BASELINE_PATH = SCRIPT_DIR.parent / "runners" / "run_opentitan_tlul_slice_gpu_baseline.py"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_module(path: Path, name: str):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    scripts_dir = str(SCRIPT_DIR)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TlulErrAndSinkCampaignArtifactsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contracts = _load_module(CONTRACTS_PATH, "tlul_contracts_test")
        cls.baseline = _load_module(BASELINE_PATH, "tlul_baseline_test")

    def _validate(self, slice_name: str) -> dict:
        template_path = ROOT_DIR / "config" / "slice_launch_templates" / f"{slice_name}.json"
        template = _load_json(template_path)
        tb_path = ROOT_DIR / template["runner_args_template"]["coverage_tb_path"]
        manifest_path = ROOT_DIR / template["runner_args_template"]["coverage_manifest_path"]
        top_module = template["runner_args_template"]["top_module"]
        self.assertTrue(tb_path.exists(), tb_path)
        self.assertTrue(manifest_path.exists(), manifest_path)
        report = self.contracts.validate_slice_contract(
            target=template["target"],
            top_module=top_module,
            tb_path=tb_path,
            manifest_path=manifest_path,
        )
        self.assertEqual(report["status"], "contract_ready")
        return report

    def test_tlul_err_template_points_to_checked_in_artifacts(self) -> None:
        template = _load_json(ROOT_DIR / "config" / "slice_launch_templates" / "tlul_err.json")
        self.assertEqual(
            template["runner_args_template"]["coverage_tb_path"],
            "third_party/rtlmeter/designs/OpenTitan/src/tlul_err_gpu_cov_tb.sv",
        )
        self.assertEqual(
            template["runner_args_template"]["coverage_manifest_path"],
            "third_party/rtlmeter/designs/OpenTitan/tests/tlul_err_coverage_regions.json",
        )
        report = self._validate("tlul_err")
        self.assertEqual(report["core_contract_status"], "core_ready")
        self.assertEqual(report["semantic_contract_status"], "semantic_not_required")
        rtl_path = ROOT_DIR / "third_party/rtlmeter/designs/OpenTitan/src/tlul_err.sv"
        tb_path = ROOT_DIR / "third_party/rtlmeter/designs/OpenTitan/src/tlul_err_gpu_cov_tb.sv"
        sources = self.baseline._collect_compile_sources("tlul_err", rtl_path, tb_path)
        self.assertIn(rtl_path, sources)
        self.assertIn(tb_path, sources)

    def test_tlul_sink_template_points_to_checked_in_artifacts(self) -> None:
        template = _load_json(ROOT_DIR / "config" / "slice_launch_templates" / "tlul_sink.json")
        self.assertEqual(
            template["runner_args_template"]["coverage_tb_path"],
            "third_party/rtlmeter/designs/OpenTitan/src/tlul_sink_gpu_cov_tb.sv",
        )
        self.assertEqual(
            template["runner_args_template"]["coverage_manifest_path"],
            "third_party/rtlmeter/designs/OpenTitan/tests/tlul_sink_coverage_regions.json",
        )
        report = self._validate("tlul_sink")
        self.assertEqual(report["core_contract_status"], "core_ready")
        self.assertEqual(report["semantic_contract_status"], "semantic_ready")
        rtl_path = ROOT_DIR / "third_party/rtlmeter/designs/OpenTitan/src/tlul_sink.sv"
        tb_path = ROOT_DIR / "third_party/rtlmeter/designs/OpenTitan/src/tlul_sink_gpu_cov_tb.sv"
        sources = self.baseline._collect_compile_sources("tlul_sink", rtl_path, tb_path)
        self.assertIn(rtl_path, sources)
        self.assertIn(tb_path, sources)
        for path in [
            self.baseline.OPENTITAN_SRC / "tlul_err.sv",
            self.baseline.OPENTITAN_SRC / "tlul_rsp_intg_gen.sv",
        ]:
            self.assertIn(path, sources)


if __name__ == "__main__":
    unittest.main()
