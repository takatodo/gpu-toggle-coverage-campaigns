#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = SCRIPT_DIR.parents[1]
MANIFEST_PATH = ROOT_DIR / "work/source_stage/OpenTitan/tests/entropy_src_main_sm_coverage_regions.json"
TEMPLATE_PATH = ROOT_DIR / "config/slice_launch_templates/entropy_src_main_sm.json"
SCAFFOLD_PATH = ROOT_DIR / "work/slice_scaffolds/entropy_src_main_sm/campaign_request.json"
SCAFFOLD_TEMPLATE_PATH = ROOT_DIR / "work/slice_scaffolds/entropy_src_main_sm/coverage_regions.template.json"
TB_PATH = ROOT_DIR / "work/source_stage/OpenTitan/src/entropy_src_main_sm_gpu_cov_tb.sv"
BASELINE_PATH = SCRIPT_DIR.parent / "runners" / "run_opentitan_tlul_slice_gpu_baseline.py"
RTL_PATH = ROOT_DIR / "third_party/rtlmeter/designs/OpenTitan/src/entropy_src_main_sm.sv"
SEARCH_TUNING_PATH = SCRIPT_DIR / "opentitan_tlul_slice_search_tuning.py"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_baseline_module():
    spec = importlib.util.spec_from_file_location("entropy_src_slice_baseline", BASELINE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_search_tuning_module():
    spec = importlib.util.spec_from_file_location("entropy_src_slice_search_tuning", SEARCH_TUNING_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EntropySrcMainSmOnboardingArtifactsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not TB_PATH.is_file() or not MANIFEST_PATH.is_file():
            raise unittest.SkipTest(
                "Onboarding artifact data files not available (TB_PATH / MANIFEST_PATH missing)"
            )

    def test_files_exist(self) -> None:
        for path in [TB_PATH, MANIFEST_PATH, SCAFFOLD_PATH, SCAFFOLD_TEMPLATE_PATH]:
            self.assertTrue(path.exists(), f"missing {path}")

    def test_manifest_regions(self) -> None:
        payload = _load(MANIFEST_PATH)
        self.assertEqual(payload["target"], "OpenTitan.entropy_src_main_sm")
        self.assertEqual(len(payload["regions"]), 5)
        self.assertEqual(sum(len(region["words"]) for region in payload["regions"]), 18)
        self.assertEqual(
            [region["name"] for region in payload["regions"]],
            [
                "boot_bypass_progress",
                "startup_health_test_progress",
                "continuous_sha3_pipeline",
                "fw_override_insert_and_digest",
                "alert_or_error_terminal",
            ],
        )

    def test_scaffold_consistency(self) -> None:
        scaffold = _load(SCAFFOLD_PATH)
        template = _load(SCAFFOLD_TEMPLATE_PATH)
        self.assertEqual(scaffold["slice_name"], "entropy_src_main_sm")
        self.assertEqual(scaffold["target"], "OpenTitan.entropy_src_main_sm")
        self.assertEqual(template["target"], "OpenTitan.entropy_src_main_sm")
        self.assertEqual(len(template["regions"]), 5)
        self.assertEqual(scaffold["coverage_manifest_path"], str(MANIFEST_PATH))
        self.assertEqual(scaffold["coverage_tb_path"], str(TB_PATH))
        self.assertEqual(scaffold["baseline_knobs"]["variants_per_case"], 5)
        self.assertEqual(scaffold["external_actions_required"], [])

    def test_tb_exports_required_oracle_outputs(self) -> None:
        tb_text = TB_PATH.read_text(encoding="utf-8")
        for name in [
            "oracle_expected_ok_count_o",
            "oracle_expected_err_count_o",
            "oracle_observed_ok_count_o",
            "oracle_observed_err_count_o",
            "oracle_semantic_family_seen_o",
            "oracle_semantic_family_acked_o",
            "oracle_semantic_case_seen_o",
            "oracle_semantic_case_acked_o",
            "oracle_req_signature_o",
            "oracle_stalled_req_signature_o",
            "oracle_req_signature_delta_o",
            "oracle_req_stable_violation_o",
            "oracle_pre_handshake_traffic_cycles_o",
        ]:
            self.assertIn(name, tb_text)

    def test_baseline_runner_supports_entropy_src_slice(self) -> None:
        baseline = _load_baseline_module()
        sources = baseline._collect_compile_sources("entropy_src_main_sm", RTL_PATH, TB_PATH)
        self.assertIn(RTL_PATH, sources)
        self.assertIn(TB_PATH, sources)
        self.assertIn(baseline.OPENTITAN_SRC / "entropy_src_pkg.sv", sources)
        self.assertIn(baseline.OPENTITAN_SRC / "entropy_src_main_sm_pkg.sv", sources)
        self.assertIn(baseline.OPENTITAN_SRC / "prim_mubi_pkg.sv", sources)
        self.assertIn(baseline.OPENTITAN_SRC / "prim_sparse_fsm_flop.sv", sources)

    def test_search_tuning_is_entropy_src_specific(self) -> None:
        module = _load_search_tuning_module()
        tuning = module.resolve_slice_search_tuning(
            "entropy_src_main_sm",
            {
                "slice_name": "entropy_src_main_sm",
            },
        )
        self.assertEqual(
            tuning["trace_variants"],
            [
                "target-boot-bypass-progress",
                "target-startup-health-test-progress",
                "target-continuous-sha3-pipeline",
                "target-fw-override-insert-and-digest",
                "target-alert-or-error-terminal",
            ],
        )
        self.assertEqual(
            sorted(tuning["region_budget"].keys()),
            [
                "alert_or_error_terminal",
                "boot_bypass_progress",
                "continuous_sha3_pipeline",
                "fw_override_insert_and_digest",
                "startup_health_test_progress",
            ],
        )


if __name__ == "__main__":
    unittest.main()
