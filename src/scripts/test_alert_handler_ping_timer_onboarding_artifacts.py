#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path("/home/takatodo/GEM_try/out/opentitan_tlul_fifo_sync_trace_gpu_campaign_100k")
MANIFEST_PATH = ROOT / "source_stage" / "OpenTitan" / "tests" / "alert_handler_ping_timer_coverage_regions.json"
TEMPLATE_PATH = ROOT / "slice_launch_templates" / "alert_handler_ping_timer.json"
SCAFFOLD_PATH = ROOT / "slice_scaffolds" / "alert_handler_ping_timer" / "campaign_request.json"
TB_PATH = ROOT / "source_stage" / "OpenTitan" / "src" / "alert_handler_ping_timer_gpu_cov_tb.sv"
BASELINE_PATH = ROOT / "opentitan_support" / "run_opentitan_tlul_slice_gpu_baseline.py"
RTL_PATH = Path("/home/takatodo/GEM_try/rtlmeter/designs/OpenTitan/src/alert_handler_ping_timer.sv")
SEARCH_TUNING_PATH = ROOT / "archive" / "opentitan_tlul_slice_search_tuning.py"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_baseline_module():
    spec = importlib.util.spec_from_file_location("alert_handler_slice_baseline", BASELINE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_search_tuning_module():
    spec = importlib.util.spec_from_file_location("alert_handler_slice_search_tuning", SEARCH_TUNING_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AlertHandlerPingTimerOnboardingArtifactsTest(unittest.TestCase):
    def test_files_exist(self) -> None:
        for path in [TB_PATH, MANIFEST_PATH, TEMPLATE_PATH, SCAFFOLD_PATH]:
            self.assertTrue(path.exists(), f"missing {path}")

    def test_manifest_regions(self) -> None:
        payload = _load(MANIFEST_PATH)
        self.assertEqual(payload["target"], "OpenTitan.alert_handler_ping_timer")
        self.assertEqual(
            payload["history_visibility_contract"]["kind"],
            "alert_handler_ping_timer_semantic_seen",
        )
        self.assertEqual(len(payload["regions"]), 5)
        self.assertEqual(sum(len(region["words"]) for region in payload["regions"]), 18)
        self.assertEqual(
            [region["name"] for region in payload["regions"]],
            [
                "edn_reseed_and_entropy",
                "alert_wait_issue_ack",
                "esc_wait_issue_ack",
                "id_skip_and_rotation",
                "fail_or_spurious_terminal",
            ],
        )

    def test_template_consistency(self) -> None:
        payload = _load(TEMPLATE_PATH)
        self.assertEqual(payload["slice_name"], "alert_handler_ping_timer")
        self.assertEqual(payload["target"], "OpenTitan.alert_handler_ping_timer")
        self.assertTrue(payload["launch_gate"]["can_prepare_launch"])
        self.assertFalse(payload["launch_gate"]["can_run_pilot"])
        self.assertNotIn("baseline_compile_support_pending", payload["launch_gate"]["blocked_by"])
        self.assertEqual(
            payload["runner_args_template"]["coverage_tb_path"],
            str(TB_PATH),
        )
        self.assertEqual(
            payload["runner_args_template"]["coverage_manifest_path"],
            str(MANIFEST_PATH),
        )
        self.assertEqual(
            payload["runner_args_template"]["top_module"],
            "alert_handler_ping_timer_gpu_cov_tb",
        )
        self.assertEqual(payload["runner_args_template"]["variants_per_case"], 5)
        debug_names = payload["runner_args_template"]["debug_internal_output_names"]
        for name in [
            "alert_handler_ping_timer_gpu_cov_tb__DOT__phase_q",
            "alert_handler_ping_timer_gpu_cov_tb__DOT__oracle_semantic_family_seen_q",
            "alert_handler_ping_timer_gpu_cov_tb__DOT__edn_ack_seen_q",
            "alert_handler_ping_timer_gpu_cov_tb__DOT__alert_wait_seen_q",
            "alert_handler_ping_timer_gpu_cov_tb__DOT__esc_wait_seen_q",
            "alert_handler_ping_timer_gpu_cov_tb__DOT__activity_seen_q",
            "debug_state_o",
            "debug_selected_family_o",
            "debug_skip_seen_o",
            "debug_spurious_seen_o",
        ]:
            self.assertIn(name, debug_names)

    def test_scaffold_consistency(self) -> None:
        scaffold = _load(SCAFFOLD_PATH)
        self.assertEqual(scaffold["slice_name"], "alert_handler_ping_timer")
        self.assertEqual(scaffold["target"], "OpenTitan.alert_handler_ping_timer")
        self.assertEqual(scaffold["coverage_manifest_path"], str(MANIFEST_PATH))
        self.assertEqual(scaffold["coverage_tb_path"], str(TB_PATH))
        self.assertEqual(scaffold["baseline_knobs"]["variants_per_case"], 5)
        self.assertEqual(scaffold["external_actions_required"], [])
        self.assertIn("invalid-ID progression", " ".join(scaffold["candidate_generation_hints"]["notes"]))

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

    def test_baseline_runner_supports_alert_handler_slice(self) -> None:
        baseline = _load_baseline_module()
        sources = baseline._collect_compile_sources("alert_handler_ping_timer", RTL_PATH, TB_PATH)
        self.assertIn(RTL_PATH, sources)
        self.assertIn(TB_PATH, sources)
        for path in [
            baseline.OPENTITAN_SRC / "alert_handler_reg_pkg.sv",
            baseline.OPENTITAN_SRC / "alert_handler_pkg.sv",
            baseline.OPENTITAN_SRC / "prim_buf.sv",
            baseline.OPENTITAN_SRC / "prim_cipher_pkg.sv",
            baseline.OPENTITAN_SRC / "prim_lfsr.sv",
            baseline.OPENTITAN_SRC / "prim_double_lfsr.sv",
            baseline.OPENTITAN_SRC / "prim_sparse_fsm_flop.sv",
        ]:
            self.assertIn(path, sources)

    def test_search_tuning_is_alert_handler_specific(self) -> None:
        module = _load_search_tuning_module()
        tuning = module.resolve_slice_search_tuning("alert_handler_ping_timer", _load(TEMPLATE_PATH)["runner_args_template"])
        self.assertEqual(
            tuning["trace_variants"],
            [
                "target-edn-reseed-and-entropy",
                "target-alert-wait-issue-ack",
                "target-esc-wait-issue-ack",
                "target-id-skip-and-rotation",
                "target-fail-or-spurious-terminal",
            ],
        )
        self.assertEqual(
            sorted(tuning["region_budget"].keys()),
            [
                "alert_wait_issue_ack",
                "edn_reseed_and_entropy",
                "esc_wait_issue_ack",
                "fail_or_spurious_terminal",
                "id_skip_and_rotation",
            ],
        )


if __name__ == "__main__":
    unittest.main()
