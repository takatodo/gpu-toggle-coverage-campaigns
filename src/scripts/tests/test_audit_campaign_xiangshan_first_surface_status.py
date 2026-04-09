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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xiangshan_first_surface_status.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXiangshanFirstSurfaceStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xiangshan_first_surface_status_test", MODULE_PATH)

    def test_reports_cubin_first_debug_vs_openpiton_when_trace_stalls_before_module_load(self) -> None:
        payload = self.module.build_status(
            axes_payload={
                "decision": {
                    "status": "decide_open_next_non_veer_family_after_veer_exhaustion",
                    "recommended_family": "XiangShan",
                    "fallback_family": "OpenPiton",
                }
            },
            vortex_gate_payload=None,
            bootstrap_payload={"status": "ok", "cpp_source_count": 5, "cpp_include_count": 1},
            baseline_payload={
                "status": "ok",
                "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
                "campaign_measurement": {"bits_hit": 2, "threshold_satisfied": False},
            },
            meta_payload={
                "cubin": "vl_batch_gpu.ptx",
                "cuda_module_format": "ptx",
                "storage_size": 1058880,
            },
            ptx_smoke_trace_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_cuInit",
                    "run_vl_hybrid: stage=after_cuCtxCreate",
                    "run_vl_hybrid: stage=before_cuModuleLoad",
                ]
            )
            + "\n",
            ptx_smoke_timeout_seconds=20,
        )

        self.assertEqual(
            payload["outcome"]["status"],
            "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family",
        )
        self.assertEqual(payload["ptx_smoke"]["status"], "stalled_before_cuModuleLoad")
        self.assertEqual(payload["upstream_axes"]["fallback_family"], "OpenPiton")

    def test_prefers_reopened_vortex_context_when_gate_selects_xiangshan_fallback(self) -> None:
        payload = self.module.build_status(
            axes_payload={
                "decision": {
                    "status": "decide_open_next_non_veer_family_after_veer_exhaustion",
                    "recommended_family": "XiangShan",
                    "fallback_family": "OpenPiton",
                }
            },
            vortex_gate_payload={
                "selection": {"profile_name": "reopen_xiangshan_fallback_family"},
                "outcome": {"status": "reopen_xiangshan_fallback_ready"},
            },
            bootstrap_payload={"status": "ok", "cpp_source_count": 5, "cpp_include_count": 1},
            baseline_payload={
                "status": "ok",
                "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
                "campaign_measurement": {"bits_hit": 2, "threshold_satisfied": False},
            },
            meta_payload={
                "cubin": "vl_batch_gpu.ptx",
                "cuda_module_format": "ptx",
                "storage_size": 1058880,
            },
            ptx_smoke_trace_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_cuInit",
                    "run_vl_hybrid: stage=after_cuCtxCreate",
                    "run_vl_hybrid: stage=before_cuModuleLoad",
                ]
            )
            + "\n",
            ptx_smoke_timeout_seconds=20,
        )

        self.assertEqual(
            payload["outcome"]["status"],
            "decide_xiangshan_cubin_first_debug_vs_reopen_vortex_tls_lowering_debug",
        )
        self.assertEqual(payload["current_branch"]["source_scope"], "campaign_vortex_first_surface_gate")
        self.assertEqual(payload["current_branch"]["fallback_branch"], "debug_vortex_tls_lowering")

    def test_reports_ready_to_finish_when_runtime_smoke_completes(self) -> None:
        payload = self.module.build_status(
            axes_payload={
                "decision": {
                    "status": "decide_open_next_non_veer_family_after_veer_exhaustion",
                    "recommended_family": "XiangShan",
                    "fallback_family": "OpenPiton",
                }
            },
            vortex_gate_payload={
                "selection": {"profile_name": "reopen_xiangshan_fallback_family"},
                "outcome": {"status": "reopen_xiangshan_fallback_ready"},
            },
            bootstrap_payload={"status": "ok", "cpp_source_count": 5, "cpp_include_count": 1},
            baseline_payload={
                "status": "ok",
                "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
                "campaign_measurement": {"bits_hit": 2, "threshold_satisfied": False},
            },
            meta_payload={
                "cubin": "vl_batch_gpu.cubin",
                "cuda_module_format": "cubin",
                "storage_size": 1058880,
            },
            ptx_smoke_trace_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_cuModuleLoad",
                    "run_vl_hybrid: stage=after_kernel_resolution",
                    "run_vl_hybrid: stage=after_cleanup",
                    "ok: steps=1 kernels_per_step=1",
                ]
            )
            + "\n",
            ptx_smoke_timeout_seconds=20,
        )

        self.assertEqual(payload["ptx_smoke"]["status"], "completed_smoke_run")
        self.assertEqual(payload["outcome"]["status"], "ready_to_finish_xiangshan_first_trio")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            axes_json = root / "axes.json"
            vortex_gate_json = root / "vortex_gate.json"
            bootstrap_json = root / "bootstrap.json"
            baseline_json = root / "baseline.json"
            meta_json = root / "meta.json"
            trace_log = root / "xiangshan_ptx_smoke_trace.log"
            json_out = root / "status.json"

            axes_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "status": "decide_open_next_non_veer_family_after_veer_exhaustion",
                            "recommended_family": "XiangShan",
                            "fallback_family": "OpenPiton",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            vortex_gate_json.write_text(
                json.dumps(
                    {
                        "selection": {"profile_name": "reopen_xiangshan_fallback_family"},
                        "outcome": {"status": "reopen_xiangshan_fallback_ready"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            bootstrap_json.write_text(
                json.dumps({"status": "ok", "cpp_source_count": 5, "cpp_include_count": 1}) + "\n",
                encoding="utf-8",
            )
            baseline_json.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
                        "campaign_measurement": {"bits_hit": 2, "threshold_satisfied": False},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            meta_json.write_text(
                json.dumps(
                    {
                        "cubin": "vl_batch_gpu.ptx",
                        "cuda_module_format": "ptx",
                        "storage_size": 1058880,
                        "incremental_mode": "reuse_ptx",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            trace_log.write_text(
                "\n".join(
                    [
                        "run_vl_hybrid: stage=before_cuInit",
                        "run_vl_hybrid: stage=after_cuCtxCreate",
                        "run_vl_hybrid: stage=before_cuModuleLoad",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_xiangshan_first_surface_status.py",
                "--axes-json",
                str(axes_json),
                "--vortex-gate-json",
                str(vortex_gate_json),
                "--bootstrap-json",
                str(bootstrap_json),
                "--baseline-json",
                str(baseline_json),
                "--meta-json",
                str(meta_json),
                "--ptx-smoke-trace-log",
                str(trace_log),
                "--ptx-smoke-timeout-seconds",
                "20",
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_xiangshan_first_surface_status")
            self.assertEqual(payload["ptx_smoke"]["timeout_seconds"], 20)
            self.assertEqual(payload["ptx_smoke"]["last_stage"], "before_cuModuleLoad")
            self.assertEqual(
                payload["outcome"]["next_action"],
                "choose_between_offline_xiangshan_cubin_first_debug_and_reopening_vortex_tls_lowering_debug",
            )


if __name__ == "__main__":
    unittest.main()
