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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_vortex_deeper_debug_status.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignVortexDeeperDebugStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_vortex_deeper_debug_status_test", MODULE_PATH)

    def test_ready_for_dpi_wrapper_abi_debug_after_tls_bypass_proves_llc_recovery(self) -> None:
        ptx_text = "\n".join(
            [
                ".visible .func _Z81Vvortex_gpu_cov_tb___024root____Vdpiimwrap_vortex_gpu_cov_tb__DOT__mem_access_TOPhmm6VlWideILm16EERS0_(",
                ".param .b64 _Z81Vvortex_gpu_cov_tb___024root____Vdpiimwrap_vortex_gpu_cov_tb__DOT__mem_access_TOPhmm6VlWideILm16EERS0__param_3,",
                ".visible .entry vl_eval_batch_gpu(",
            ]
        ) + "\n"
        log_text = (
            "ptxas /tmp/vl_batch_gpu_vortex_tls_bypass.ptx, line 71019; error   : "
            "Type of argument does not match formal parameter "
            "'_Z81Vvortex_gpu_cov_tb___024root____Vdpiimwrap_vortex_gpu_cov_tb__DOT__"
            "mem_access_TOPhmm6VlWideILm16EERS0__param_3'\n"
            "ptxas fatal   : Ptx assembly aborted due to errors\n"
        )
        payload = self.module.build_status(
            xiangshan_acceptance_payload={
                "outcome": {"status": "accepted_selected_xiangshan_first_surface_step"}
            },
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
            vortex_bypass_ptx_text=ptx_text,
            vortex_ptxas_log_text=log_text,
            vortex_classifier_payload={
                "functions": [
                    {
                        "name": "_Z81Vvortex_gpu_cov_tb___024root____Vdpiimwrap_vortex_gpu_cov_tb__DOT__mem_access_TOPhmm6VlWideILm16EERS0_",
                        "placement": "gpu",
                        "reason": "gpu_reachable",
                    }
                ]
            },
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_vortex_dpi_wrapper_abi_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_vortex_dpi_wrapper_abi_debug",
        )
        self.assertEqual(payload["observations"]["ptxas_status"], "dpi_wrapper_abi_mismatch")
        self.assertEqual(payload["observations"]["classifier_wrapper_placement"], "gpu")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            xiangshan_json = root / "xiangshan.json"
            vortex_json = root / "vortex.json"
            ptx_path = root / "bypass.ptx"
            ptxas_log = root / "ptxas.log"
            classifier_json = root / "classifier.json"
            json_out = root / "status.json"

            xiangshan_json.write_text(
                json.dumps({"outcome": {"status": "accepted_selected_xiangshan_first_surface_step"}})
                + "\n",
                encoding="utf-8",
            )
            vortex_json.write_text(
                json.dumps(
                    {
                        "outcome": {
                            "status": "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback",
                        },
                        "gpu_build": {"status": "llc_tls_global_blocked"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            ptx_path.write_text(
                ".visible .func _Z81Vvortex_gpu_cov_tb___024root____Vdpiimwrap_vortex_gpu_cov_tb__DOT__mem_access_TOPhmm6VlWideILm16EERS0_(\n"
                ".param .b64 _Z81Vvortex_gpu_cov_tb___024root____Vdpiimwrap_vortex_gpu_cov_tb__DOT__mem_access_TOPhmm6VlWideILm16EERS0__param_3,\n"
                ".visible .entry vl_eval_batch_gpu(\n",
                encoding="utf-8",
            )
            ptxas_log.write_text(
                "Type of argument does not match formal parameter "
                "'_Z81Vvortex_gpu_cov_tb___024root____Vdpiimwrap_vortex_gpu_cov_tb__DOT__"
                "mem_access_TOPhmm6VlWideILm16EERS0__param_3'\n",
                encoding="utf-8",
            )
            classifier_json.write_text(
                json.dumps(
                    {
                        "functions": [
                            {
                                "name": "_Z81Vvortex_gpu_cov_tb___024root____Vdpiimwrap_vortex_gpu_cov_tb__DOT__mem_access_TOPhmm6VlWideILm16EERS0_",
                                "placement": "gpu",
                                "reason": "gpu_reachable",
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_vortex_deeper_debug_status.py",
                "--xiangshan-acceptance-json",
                str(xiangshan_json),
                "--vortex-status-json",
                str(vortex_json),
                "--vortex-bypass-ptx",
                str(ptx_path),
                "--vortex-ptxas-log",
                str(ptxas_log),
                "--vortex-classifier-json",
                str(classifier_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_vortex_deeper_debug_status")
            self.assertEqual(
                payload["decision"]["recommended_next_tactic"],
                "deeper_vortex_dpi_wrapper_abi_debug",
            )


if __name__ == "__main__":
    unittest.main()
