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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_caliptra_first_surface_status.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignCaliptraFirstSurfaceStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_caliptra_first_surface_status_test", MODULE_PATH)

    def test_reports_tls_lowering_debug_vs_example_when_llc_crashes_on_verilated_tls(self) -> None:
        payload = self.module.build_status(
            axes_payload={
                "decision": {
                    "status": "decide_open_next_family_after_vortex_acceptance",
                    "recommended_family": "Caliptra",
                    "fallback_family": "Example",
                }
            },
            bootstrap_payload={"status": "ok", "cpp_source_count": 0, "cpp_include_count": 0},
            baseline_payload={
                "status": "ok",
                "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
                "campaign_measurement": {"bits_hit": 8, "threshold_satisfied": True},
            },
            hybrid_payload={"status": "error", "campaign_measurement": {"bits_hit": 0}},
            build_log_text="\n".join(
                [
                    "LLVM ERROR: Cannot select: i64 = GlobalTLSAddress<ptr addrspace(1) @_ZN9Verilated3t_sE>",
                    "In function: _Z54Vcaliptra_gpu_cov_tb___024root___act_sequent__TOP__290P30Vcaliptra_gpu_cov_tb___024root",
                    "  storage_size = 3128704 bytes",
                    "llc-18 -march=nvptx64 -mcpu=sm_89 /tmp/vl_batch_gpu_opt.ll -o /tmp/vl_batch_gpu.ptx",
                    "subprocess.CalledProcessError: Command ['llc-18', '-march=nvptx64'] died with <Signals.SIGABRT: 6>.",
                ]
            )
            + "\n",
        )

        self.assertEqual(
            payload["outcome"]["status"],
            "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
        )
        self.assertEqual(payload["gpu_build"]["status"], "llc_tls_global_blocked")
        self.assertEqual(payload["gpu_build"]["blocker_kind"], "nvptx_tls_lowering")
        self.assertTrue(payload["gpu_build"]["contains_verilated_tls"])
        self.assertEqual(payload["upstream_axes"]["fallback_family"], "Example")

    def test_prefers_ready_to_finish_trio_when_stock_hybrid_is_ok_even_if_old_failure_log_remains(self) -> None:
        payload = self.module.build_status(
            axes_payload={
                "decision": {
                    "status": "decide_open_next_family_after_vortex_acceptance",
                    "recommended_family": "Caliptra",
                    "fallback_family": "Example",
                }
            },
            bootstrap_payload={"status": "ok", "cpp_source_count": 0, "cpp_include_count": 0},
            baseline_payload={
                "status": "ok",
                "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
                "campaign_measurement": {"bits_hit": 8, "threshold_satisfied": True},
            },
            hybrid_payload={
                "status": "ok",
                "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
                "campaign_measurement": {"bits_hit": 8, "threshold_satisfied": True},
            },
            build_log_text="\n".join(
                [
                    "LLVM ERROR: Cannot select: i64 = GlobalTLSAddress<ptr addrspace(1) @_ZN9Verilated3t_sE>",
                    "In function: _Z54Vcaliptra_gpu_cov_tb___024root___act_sequent__TOP__290P30Vcaliptra_gpu_cov_tb___024root",
                    "llc-18 -march=nvptx64 -mcpu=sm_89 /tmp/vl_batch_gpu_opt.ll -o /tmp/vl_batch_gpu.ptx",
                ]
            )
            + "\n",
        )

        self.assertEqual(payload["outcome"]["status"], "ready_to_finish_caliptra_first_trio")
        self.assertEqual(payload["stock_hybrid"]["status"], "ok")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            axes_json = root / "axes.json"
            bootstrap_json = root / "bootstrap.json"
            baseline_json = root / "baseline.json"
            hybrid_json = root / "hybrid.json"
            build_log = root / "caliptra_build_vl_gpu.log"
            json_out = root / "status.json"

            axes_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "status": "decide_open_next_family_after_vortex_acceptance",
                            "recommended_family": "Caliptra",
                            "fallback_family": "Example",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            bootstrap_json.write_text(
                json.dumps({"status": "ok", "cpp_source_count": 0, "cpp_include_count": 0}) + "\n",
                encoding="utf-8",
            )
            baseline_json.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
                        "campaign_measurement": {"bits_hit": 8, "threshold_satisfied": True},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            hybrid_json.write_text(
                json.dumps({"status": "error", "campaign_measurement": {"bits_hit": 0}}) + "\n",
                encoding="utf-8",
            )
            build_log.write_text(
                "\n".join(
                    [
                        "LLVM ERROR: Cannot select: i64 = GlobalTLSAddress<ptr addrspace(1) @_ZN9Verilated3t_sE>",
                        "In function: _Z54Vcaliptra_gpu_cov_tb___024root___act_sequent__TOP__290P30Vcaliptra_gpu_cov_tb___024root",
                        "storage_size = 3128704 bytes",
                        "llc-18 -march=nvptx64 -mcpu=sm_89 /tmp/vl_batch_gpu_opt.ll -o /tmp/vl_batch_gpu.ptx",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_caliptra_first_surface_status.py",
                "--axes-json",
                str(axes_json),
                "--bootstrap-json",
                str(bootstrap_json),
                "--baseline-json",
                str(baseline_json),
                "--hybrid-json",
                str(hybrid_json),
                "--build-log",
                str(build_log),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_caliptra_first_surface_status")
            self.assertEqual(payload["gpu_build"]["storage_size_bytes"], 3128704)
            self.assertEqual(payload["gpu_build"]["status"], "llc_tls_global_blocked")
            self.assertEqual(
                payload["outcome"]["next_action"],
                "choose_between_offline_caliptra_tls_lowering_debug_and_opening_example_fallback_family",
            )


if __name__ == "__main__":
    unittest.main()
