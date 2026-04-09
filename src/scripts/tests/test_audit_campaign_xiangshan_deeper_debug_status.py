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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xiangshan_deeper_debug_status.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXiangshanDeeperDebugStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module(
            "audit_campaign_xiangshan_deeper_debug_status_test",
            MODULE_PATH,
        )

    def test_prefers_finish_trio_after_nvcc_device_link_success(self) -> None:
        payload = self.module.build_status(
            branch_resolution_payload={
                "decision": {
                    "status": "avoid_xiangshan_vortex_reopen_loop_keep_current_xiangshan_branch",
                    "recommended_profile_name": "reopen_xiangshan_fallback_family",
                    "recommended_next_tactic": "deeper_xiangshan_cubin_first_debug",
                    "fallback_tactic": "deeper_vortex_tls_lowering_debug",
                }
            },
            ptxas_probe_payload={"status": "timed_out"},
            compile_only_probe_payload={"status": "ok", "output_exists": True},
            nvcc_device_link_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {
                    "object_exists": True,
                    "object_size": 17_432_512,
                    "object_kernel_symbol_present": True,
                    "linked_exists": True,
                    "linked_size": 18_923_520,
                    "linked_kernel_symbol_present": True,
                },
            },
            compile_only_kernel_symbol_present=True,
            nvlink_kernel_symbol_present=False,
            nvcc_dlink_kernel_symbol_present=False,
            fatbinary_device_c_kernel_symbol_present=True,
            fatbinary_device_c_link_kernel_symbol_present=True,
            compile_only_object_size_bytes=99_229_952,
            nvlink_cubin_size_bytes=760,
            nvcc_dlink_fatbin_size_bytes=840,
            fatbinary_device_c_fatbin_size_bytes=7_986_712,
            fatbinary_device_c_link_fatbin_size_bytes=7_986_712,
            ptx_fatbin_size_bytes=11_793_512,
            compile_only_smoke_payload={"status": "device_kernel_image_invalid", "last_stage": "after_cuModuleLoad"},
            nvlink_smoke_payload={"status": "named_symbol_not_found", "last_stage": "after_cuModuleLoad"},
            fatbin_smoke_payload={"status": "device_kernel_image_invalid", "last_stage": "after_cuModuleLoad"},
            nvcc_dlink_smoke_payload={"status": "named_symbol_not_found", "last_stage": "after_cuModuleLoad"},
            fatbinary_device_c_smoke_payload={
                "status": "device_kernel_image_invalid",
                "last_stage": "after_cuModuleLoad",
            },
            fatbinary_device_c_link_smoke_payload={
                "status": "device_kernel_image_invalid",
                "last_stage": "after_cuModuleLoad",
            },
            ptx_fatbin_smoke_payload={
                "status": "stalled_before_cuModuleLoad",
                "last_stage": "before_cuModuleLoad",
            },
            nvcc_device_link_smoke_payload={"status": "ok", "last_stage": "after_cleanup"},
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_to_finish_xiangshan_first_trio",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "finish_xiangshan_stock_hybrid_validation_and_compare_gate_policy",
        )

    def test_prefers_executable_link_population_debug_without_official_link_success(self) -> None:
        payload = self.module.build_status(
            branch_resolution_payload={
                "decision": {
                    "status": "avoid_xiangshan_vortex_reopen_loop_keep_current_xiangshan_branch",
                    "recommended_profile_name": "reopen_xiangshan_fallback_family",
                    "recommended_next_tactic": "deeper_xiangshan_cubin_first_debug",
                    "fallback_tactic": "deeper_vortex_tls_lowering_debug",
                }
            },
            ptxas_probe_payload={"status": "timed_out"},
            compile_only_probe_payload={"status": "ok", "output_exists": True},
            nvcc_device_link_probe_payload=None,
            compile_only_kernel_symbol_present=True,
            nvlink_kernel_symbol_present=False,
            nvcc_dlink_kernel_symbol_present=False,
            fatbinary_device_c_kernel_symbol_present=True,
            fatbinary_device_c_link_kernel_symbol_present=True,
            compile_only_object_size_bytes=99_229_952,
            nvlink_cubin_size_bytes=760,
            nvcc_dlink_fatbin_size_bytes=840,
            fatbinary_device_c_fatbin_size_bytes=7_986_712,
            fatbinary_device_c_link_fatbin_size_bytes=7_986_712,
            ptx_fatbin_size_bytes=11_793_512,
            compile_only_smoke_payload={"status": "device_kernel_image_invalid", "last_stage": "after_cuModuleLoad"},
            nvlink_smoke_payload={"status": "named_symbol_not_found", "last_stage": "after_cuModuleLoad"},
            fatbin_smoke_payload={"status": "device_kernel_image_invalid", "last_stage": "after_cuModuleLoad"},
            nvcc_dlink_smoke_payload={"status": "named_symbol_not_found", "last_stage": "after_cuModuleLoad"},
            fatbinary_device_c_smoke_payload={
                "status": "device_kernel_image_invalid",
                "last_stage": "after_cuModuleLoad",
            },
            fatbinary_device_c_link_smoke_payload={
                "status": "device_kernel_image_invalid",
                "last_stage": "after_cuModuleLoad",
            },
            ptx_fatbin_smoke_payload={
                "status": "stalled_before_cuModuleLoad",
                "last_stage": "before_cuModuleLoad",
            },
            nvcc_device_link_smoke_payload={"status": None, "last_stage": None},
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_xiangshan_executable_link_population_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_xiangshan_executable_link_population_debug",
        )

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            branch_resolution_json = root / "resolution.json"
            ptxas_probe_json = root / "ptxas.json"
            compile_only_probe_json = root / "compile_only.json"
            nvcc_device_link_probe_json = root / "nvcc_device_link.json"
            compile_only_object = root / "probe.o"
            nvlink_cubin = root / "probe.cubin"
            nvcc_dlink_fatbin = root / "probe.fatbin"
            fatbinary_device_c_fatbin = root / "device_c.fatbin"
            fatbinary_device_c_link_fatbin = root / "device_c_link.fatbin"
            ptx_fatbin = root / "ptx.fatbin"
            nvcc_device_link_smoke_log = root / "nvcc_device_link_smoke.log"
            compile_only_log = root / "compile_only.log"
            nvlink_log = root / "nvlink.log"
            fatbin_log = root / "fatbin.log"
            nvcc_dlink_log = root / "nvcc.log"
            fatbinary_device_c_log = root / "device_c.log"
            fatbinary_device_c_link_log = root / "device_c_link.log"
            ptx_fatbin_log = root / "ptx.log"
            json_out = root / "status.json"

            branch_resolution_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "status": "avoid_xiangshan_vortex_reopen_loop_keep_current_xiangshan_branch",
                            "recommended_profile_name": "reopen_xiangshan_fallback_family",
                            "recommended_next_tactic": "deeper_xiangshan_cubin_first_debug",
                            "fallback_tactic": "deeper_vortex_tls_lowering_debug",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            ptxas_probe_json.write_text(json.dumps({"status": "timed_out"}) + "\n", encoding="utf-8")
            compile_only_probe_json.write_text(
                json.dumps({"status": "ok", "output_exists": True}) + "\n",
                encoding="utf-8",
            )
            nvcc_device_link_probe_json.write_text(
                json.dumps(
                    {
                        "compile": {"status": "ok"},
                        "link": {"status": "ok"},
                        "observations": {
                            "object_exists": True,
                            "object_size": 17432512,
                            "object_kernel_symbol_present": True,
                            "linked_exists": True,
                            "linked_size": 18923520,
                            "linked_kernel_symbol_present": True,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            compile_only_object.write_text("obj\n", encoding="utf-8")
            nvlink_cubin.write_text("cubin\n", encoding="utf-8")
            nvcc_dlink_fatbin.write_text("fatbin\n", encoding="utf-8")
            fatbinary_device_c_fatbin.write_text("fatbin\n", encoding="utf-8")
            fatbinary_device_c_link_fatbin.write_text("fatbin\n", encoding="utf-8")
            ptx_fatbin.write_text("ptxfatbin\n", encoding="utf-8")
            nvcc_device_link_smoke_log.write_text(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
                encoding="utf-8",
            )
            compile_only_log.write_text(
                "run_vl_hybrid: stage=after_cuModuleLoad\nrun_vl_hybrid.c:239 CUDA error 200: device kernel image is invalid\n",
                encoding="utf-8",
            )
            nvlink_log.write_text(
                "run_vl_hybrid: stage=after_cuModuleLoad\nrun_vl_hybrid.c:239 CUDA error 500: named symbol not found\n",
                encoding="utf-8",
            )
            fatbin_log.write_text(
                "run_vl_hybrid: stage=after_cuModuleLoad\nrun_vl_hybrid.c:239 CUDA error 200: device kernel image is invalid\n",
                encoding="utf-8",
            )
            nvcc_dlink_log.write_text(
                "run_vl_hybrid: stage=after_cuModuleLoad\nrun_vl_hybrid.c:239 CUDA error 500: named symbol not found\n",
                encoding="utf-8",
            )
            fatbinary_device_c_log.write_text(
                "run_vl_hybrid: stage=after_cuModuleLoad\nrun_vl_hybrid.c:239 CUDA error 200: device kernel image is invalid\n",
                encoding="utf-8",
            )
            fatbinary_device_c_link_log.write_text(
                "run_vl_hybrid: stage=after_cuModuleLoad\nrun_vl_hybrid.c:239 CUDA error 200: device kernel image is invalid\n",
                encoding="utf-8",
            )
            ptx_fatbin_log.write_text(
                "run_vl_hybrid: stage=before_cuModuleLoad\n",
                encoding="utf-8",
            )

            def _fake_run(cmd, check, capture_output, text):
                path = Path(cmd[-1])
                if path in {compile_only_object, fatbinary_device_c_fatbin, fatbinary_device_c_link_fatbin}:
                    stdout = "symbols:\nSTT_FUNC STB_GLOBAL STO_ENTRY      vl_eval_batch_gpu\n"
                else:
                    stdout = "symbols:\n"
                return mock.Mock(returncode=0, stdout=stdout, stderr="")

            argv = [
                "audit_campaign_xiangshan_deeper_debug_status.py",
                "--branch-resolution-json",
                str(branch_resolution_json),
                "--ptxas-probe-json",
                str(ptxas_probe_json),
                "--compile-only-probe-json",
                str(compile_only_probe_json),
                "--nvcc-device-link-probe-json",
                str(nvcc_device_link_probe_json),
                "--compile-only-object",
                str(compile_only_object),
                "--nvlink-cubin",
                str(nvlink_cubin),
                "--nvcc-dlink-fatbin",
                str(nvcc_dlink_fatbin),
                "--fatbinary-device-c-fatbin",
                str(fatbinary_device_c_fatbin),
                "--fatbinary-device-c-link-fatbin",
                str(fatbinary_device_c_link_fatbin),
                "--ptx-fatbin",
                str(ptx_fatbin),
                "--compile-only-smoke-log",
                str(compile_only_log),
                "--nvlink-smoke-log",
                str(nvlink_log),
                "--fatbin-smoke-log",
                str(fatbin_log),
                "--nvcc-dlink-smoke-log",
                str(nvcc_dlink_log),
                "--fatbinary-device-c-smoke-log",
                str(fatbinary_device_c_log),
                "--fatbinary-device-c-link-smoke-log",
                str(fatbinary_device_c_link_log),
                "--ptx-fatbin-smoke-log",
                str(ptx_fatbin_log),
                "--nvcc-device-link-smoke-log",
                str(nvcc_device_link_smoke_log),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(self.module.subprocess, "run", side_effect=_fake_run):
                with mock.patch.object(sys, "argv", argv):
                    rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_xiangshan_deeper_debug_status")
            self.assertEqual(
                payload["decision"]["recommended_next_tactic"],
                "finish_xiangshan_stock_hybrid_validation_and_compare_gate_policy",
            )


if __name__ == "__main__":
    unittest.main()
