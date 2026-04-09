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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_vortex_debug_tactics.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignVortexDebugTacticsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_vortex_debug_tactics_test", MODULE_PATH)

    def test_prefers_xiangshan_reopen_after_o0_and_o1_repeat_same_tls_crash(self) -> None:
        log_text = "\n".join(
            [
                "LLVM ERROR: Cannot select: i64 = GlobalTLSAddress<ptr addrspace(1) @_ZN9Verilated3t_sE>",
                "In function: _Z50Vvortex_gpu_cov_tb___024root___nba_sequent__TOP__0P28Vvortex_gpu_cov_tb___024root",
                "llc-18 -march=nvptx64 -mcpu=sm_89 /tmp/vl_batch_gpu_opt.ll -o /tmp/vl_batch_gpu.ptx",
            ]
        ) + "\n"
        payload = self.module.build_tactics(
            vortex_status_payload={
                "outcome": {
                    "status": "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                    "failing_function": "demo",
                },
            },
            vortex_gate_payload={
                "selection": {"profile_name": "debug_vortex_tls_lowering"},
                "outcome": {"status": "debug_vortex_tls_lowering_ready"},
            },
            vortex_acceptance_payload=None,
            deeper_status_payload=None,
            low_opt_o0_log_text=log_text,
            low_opt_o1_log_text=log_text,
        )

        self.assertEqual(
            payload["decision"]["status"],
            "prefer_reopen_xiangshan_after_low_opt_vortex_trials_failed",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "reopen_xiangshan_fallback_family",
        )
        self.assertEqual(payload["observations"]["low_opt_o0_status"], "llc_tls_global_blocked")
        self.assertEqual(payload["observations"]["low_opt_o1_status"], "llc_tls_global_blocked")

    def test_prefers_deeper_vortex_dpi_wrapper_debug_after_tls_bypass(self) -> None:
        log_text = "\n".join(
            [
                "LLVM ERROR: Cannot select: i64 = GlobalTLSAddress<ptr addrspace(1) @_ZN9Verilated3t_sE>",
                "In function: _Z50Vvortex_gpu_cov_tb___024root___nba_sequent__TOP__0P28Vvortex_gpu_cov_tb___024root",
                "llc-18 -march=nvptx64 -mcpu=sm_89 /tmp/vl_batch_gpu_opt.ll -o /tmp/vl_batch_gpu.ptx",
            ]
        ) + "\n"
        payload = self.module.build_tactics(
            vortex_status_payload={
                "outcome": {
                    "status": "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                    "failing_function": "demo",
                },
            },
            vortex_gate_payload={
                "selection": {"profile_name": "debug_vortex_tls_lowering"},
                "outcome": {"status": "debug_vortex_tls_lowering_ready"},
            },
            vortex_acceptance_payload=None,
            deeper_status_payload={
                "decision": {
                    "status": "ready_for_vortex_dpi_wrapper_abi_debug",
                    "reason": "tls_bypass_proves_llc_recovery",
                    "recommended_next_tactic": "deeper_vortex_dpi_wrapper_abi_debug",
                    "fallback_tactic": "deeper_vortex_tls_lowering_debug",
                },
                "observations": {
                    "ptxas_status": "dpi_wrapper_abi_mismatch",
                    "ptxas_failed_wrapper_name": "demo_wrapper",
                    "classifier_wrapper_placement": "gpu",
                },
            },
            low_opt_o0_log_text=log_text,
            low_opt_o1_log_text=log_text,
        )

        self.assertEqual(
            payload["decision"]["status"],
            "continue_vortex_with_dpi_wrapper_abi_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_vortex_dpi_wrapper_abi_debug",
        )
        self.assertTrue(payload["capabilities"]["tls_bypass_recovery_path_present"])
        self.assertEqual(payload["observations"]["deeper_ptxas_status"], "dpi_wrapper_abi_mismatch")

    def test_reports_ready_to_finish_trio_after_gpu_build_recovery(self) -> None:
        payload = self.module.build_tactics(
            vortex_status_payload={
                "outcome": {
                    "status": "ready_to_finish_vortex_first_trio",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                    "failing_function": "demo",
                },
            },
            vortex_gate_payload={
                "selection": {"profile_name": "debug_vortex_tls_lowering"},
                "outcome": {"status": "vortex_gpu_build_recovered_ready_to_finish_trio"},
            },
            vortex_acceptance_payload=None,
            deeper_status_payload=None,
            low_opt_o0_log_text=None,
            low_opt_o1_log_text=None,
        )

        self.assertEqual(payload["decision"]["status"], "ready_to_finish_vortex_first_trio")
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "finish_the_Vortex_first_campaign_trio",
        )

    def test_reports_post_vortex_axes_after_acceptance(self) -> None:
        payload = self.module.build_tactics(
            vortex_status_payload={
                "outcome": {
                    "status": "ready_to_finish_vortex_first_trio",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                },
            },
            vortex_gate_payload={
                "selection": {"profile_name": "debug_vortex_tls_lowering"},
                "outcome": {"status": "vortex_gpu_build_recovered_ready_to_finish_trio"},
            },
            vortex_acceptance_payload={
                "outcome": {
                    "status": "accepted_selected_vortex_first_surface_step",
                    "next_action": "decide_post_vortex_family_axes_after_accepting_vortex",
                }
            },
            deeper_status_payload=None,
            low_opt_o0_log_text=None,
            low_opt_o1_log_text=None,
        )

        self.assertEqual(payload["decision"]["status"], "vortex_first_surface_already_accepted")
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "decide_post_vortex_family_axes_after_accepting_vortex",
        )

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vortex_json = root / "vortex.json"
            gate_json = root / "gate.json"
            deeper_json = root / "deeper.json"
            o0_log = root / "o0.log"
            o1_log = root / "o1.log"
            json_out = root / "tactics.json"

            vortex_json.write_text(
                json.dumps(
                    {
                        "outcome": {
                            "status": "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback",
                        },
                        "gpu_build": {
                            "status": "llc_tls_global_blocked",
                            "blocker_kind": "nvptx_tls_lowering",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            gate_json.write_text(
                json.dumps(
                    {
                        "selection": {"profile_name": "debug_vortex_tls_lowering"},
                        "outcome": {"status": "debug_vortex_tls_lowering_ready"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            deeper_json.write_text(
                json.dumps({"decision": {"status": "continue_collecting_vortex_post_tls_codegen_evidence"}})
                + "\n",
                encoding="utf-8",
            )
            log_text = "\n".join(
                [
                    "LLVM ERROR: Cannot select: i64 = GlobalTLSAddress<ptr addrspace(1) @_ZN9Verilated3t_sE>",
                    "In function: _Z50Vvortex_gpu_cov_tb___024root___nba_sequent__TOP__0P28Vvortex_gpu_cov_tb___024root",
                    "llc-18 -march=nvptx64 -mcpu=sm_89 /tmp/vl_batch_gpu_opt.ll -o /tmp/vl_batch_gpu.ptx",
                ]
            ) + "\n"
            o0_log.write_text(log_text, encoding="utf-8")
            o1_log.write_text(log_text, encoding="utf-8")

            argv = [
                "audit_campaign_vortex_debug_tactics.py",
                "--vortex-status-json",
                str(vortex_json),
                "--vortex-gate-json",
                str(gate_json),
                "--vortex-acceptance-json",
                str(root / "missing_acceptance.json"),
                "--deeper-status-json",
                str(deeper_json),
                "--build-o0-log",
                str(o0_log),
                "--build-o1-log",
                str(o1_log),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_vortex_debug_tactics")
            self.assertEqual(
                payload["decision"]["recommended_next_tactic"],
                "reopen_xiangshan_fallback_family",
            )


if __name__ == "__main__":
    unittest.main()
