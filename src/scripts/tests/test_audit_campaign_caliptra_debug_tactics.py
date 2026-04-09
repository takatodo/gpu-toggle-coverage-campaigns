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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_caliptra_debug_tactics.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignCaliptraDebugTacticsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_caliptra_debug_tactics_test", MODULE_PATH)

    def test_prefers_ptxas_cubin_debug_after_tls_bypass_recovers_ptx(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=False,
            compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 121416128,
            },
            full_cubin_probe_payload={
                "status": "timed_out",
                "output_exists": False,
                "output_size": None,
            },
            nvcc_device_link_cubin_probe_payload=None,
            nvcc_device_link_fatbin_probe_payload=None,
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text=None,
            stack_limit_probe_payload=None,
            trial_ptx_exists=True,
            trial_ptxas_log_text="\n".join(
                [
                    "ptxas warning : Unresolved extern variable '__libc_single_threaded' in whole program compilation, ignoring extern qualifier",
                    "ptxas warning : Unresolved extern variable '_ZN9Verilated3t_sE' in whole program compilation, ignoring extern qualifier",
                ]
            )
            + "\n",
            split_kernel_manifest_payload=None,
            split_compile_only_probe_payload=None,
            split_smoke_log_text=None,
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_full_cubin_completion_debug",
        )
        self.assertEqual(payload["decision"]["recommended_next_tactic"], "deeper_caliptra_full_cubin_completion_debug")
        self.assertTrue(payload["observations"]["trial_ptxas_warning_only"])
        self.assertEqual(payload["observations"]["compile_only_probe_status"], "ok")
        self.assertEqual(payload["observations"]["full_cubin_probe_status"], "timed_out")

    def test_finishes_trio_once_official_cubin_exists(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload=None,
            full_cubin_probe_payload=None,
            nvcc_device_link_cubin_probe_payload=None,
            nvcc_device_link_fatbin_probe_payload=None,
            compile_only_kernel_symbol_present=None,
            cubin_smoke_log_text="run_vl_hybrid: stage=before_first_kernel_launch\nok: steps=56 kernels_per_step=1\n",
            stack_limit_probe_payload=None,
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload=None,
            split_compile_only_probe_payload=None,
            split_smoke_log_text=None,
        )

        self.assertEqual(payload["decision"]["status"], "ready_to_finish_caliptra_first_trio")

    def test_prefers_launch_shape_runtime_debug_when_cubin_loads_but_first_launch_fails(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 121416128,
            },
            full_cubin_probe_payload={
                "status": "timed_out",
                "output_exists": False,
                "output_size": None,
            },
            nvcc_device_link_cubin_probe_payload=None,
            nvcc_device_link_fatbin_probe_payload=None,
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_cuModuleLoad",
                    "run_vl_hybrid: stage=before_first_kernel_launch",
                    "run_vl_hybrid.c:387 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload=None,
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload=None,
            split_compile_only_probe_payload=None,
            split_smoke_log_text=None,
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_launch_shape_runtime_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_launch_shape_runtime_debug",
        )
        self.assertEqual(payload["observations"]["cubin_smoke_status"], "invalid_argument")
        self.assertEqual(payload["observations"]["cubin_smoke_last_stage"], "before_first_kernel_launch")

    def test_prefers_stack_limit_ceiling_debug_when_ctx_set_limit_itself_is_rejected(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 121416128,
            },
            full_cubin_probe_payload={
                "status": "timed_out",
                "output_exists": False,
                "output_size": None,
            },
            nvcc_device_link_cubin_probe_payload=None,
            nvcc_device_link_fatbin_probe_payload=None,
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320",
                    "run_vl_hybrid.c:212 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload=None,
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload=None,
            split_compile_only_probe_payload=None,
            split_smoke_log_text=None,
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_stack_limit_ceiling_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_stack_limit_ceiling_debug",
        )
        self.assertEqual(payload["observations"]["cubin_smoke_status"], "stack_limit_invalid_argument")
        self.assertEqual(payload["observations"]["cubin_smoke_stack_limit_current"], 1024)
        self.assertEqual(payload["observations"]["cubin_smoke_stack_limit_required"], 564320)

    def test_prefers_stack_footprint_reduction_debug_when_launch_still_fails_at_max_accepted_limit(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 121416128,
            },
            full_cubin_probe_payload={
                "status": "timed_out",
                "output_exists": False,
                "output_size": None,
            },
            nvcc_device_link_cubin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            nvcc_device_link_fatbin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument",
                    "run_vl_hybrid.c:212 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload={
                "max_accepted_stack_limit": 523712,
                "min_rejected_stack_limit_target": 523744,
                "launch_at_max_result": {
                    "status": "invalid_argument",
                    "last_stage": "before_first_kernel_launch",
                },
            },
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload=None,
            split_compile_only_probe_payload=None,
            split_smoke_log_text=None,
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_kernel_stack_footprint_reduction_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_kernel_stack_footprint_reduction_debug",
        )
        self.assertEqual(payload["observations"]["stack_limit_probe_max_accepted_stack_limit"], 523712)
        self.assertEqual(payload["observations"]["stack_limit_probe_min_rejected_stack_limit_target"], 523744)
        self.assertEqual(payload["observations"]["stack_limit_probe_launch_at_max_status"], "invalid_argument")
        self.assertEqual(payload["observations"]["nvcc_device_link_cubin_probe_status"], "timed_out")
        self.assertEqual(payload["observations"]["nvcc_device_link_fatbin_probe_status"], "timed_out")

    def test_prefers_split_kernel_executable_path_when_split_compile_only_recovers_zero_stack_kernels(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 121416128,
            },
            full_cubin_probe_payload={
                "status": "timed_out",
                "output_exists": False,
                "output_size": None,
            },
            nvcc_device_link_cubin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            nvcc_device_link_fatbin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument",
                    "run_vl_hybrid.c:212 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload={
                "max_accepted_stack_limit": 523712,
                "min_rejected_stack_limit_target": 523744,
                "launch_at_max_result": {
                    "status": "invalid_argument",
                    "last_stage": "before_first_kernel_launch",
                },
            },
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload={
                "kernels": [
                    {"name": "vl_ico_batch_gpu"},
                    {"name": "vl_nba_comb_batch_gpu"},
                    {"name": "vl_nba_sequent_batch_gpu"},
                ],
                "launch_sequence": [
                    "vl_ico_batch_gpu",
                    "vl_nba_comb_batch_gpu",
                    "vl_nba_sequent_batch_gpu",
                ],
            },
            split_compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 122127168,
                "stderr_tail": "\n".join(
                    [
                        "ptxas info    : Function properties for vl_ico_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_comb_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_sequent_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                    ]
                ),
            },
            split_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_cuInit",
                    "run_vl_hybrid: stage=after_cuCtxCreate",
                    "run_vl_hybrid: stage=before_cuModuleLoad",
                ]
            )
            + "\n",
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_split_kernel_executable_path_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_split_kernel_executable_path_debug",
        )
        self.assertTrue(payload["observations"]["split_kernel_manifest_exists"])
        self.assertTrue(payload["observations"]["split_compile_only_zero_stack"])
        self.assertEqual(payload["observations"]["split_smoke_last_stage"], "before_cuModuleLoad")

    def test_prefers_split_runtime_illegal_access_debug_after_split_linked_cubin_reaches_first_launch(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 121416128,
            },
            full_cubin_probe_payload={
                "status": "timed_out",
                "output_exists": False,
                "output_size": None,
            },
            nvcc_device_link_cubin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            nvcc_device_link_fatbin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument",
                    "run_vl_hybrid.c:212 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload={
                "max_accepted_stack_limit": 523712,
                "min_rejected_stack_limit_target": 523744,
                "launch_at_max_result": {
                    "status": "invalid_argument",
                    "last_stage": "before_first_kernel_launch",
                },
            },
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload={
                "kernels": [
                    {"name": "vl_ico_batch_gpu"},
                    {"name": "vl_nba_comb_batch_gpu"},
                    {"name": "vl_nba_sequent_batch_gpu"},
                ],
                "launch_sequence": [
                    "vl_ico_batch_gpu",
                    "vl_nba_comb_batch_gpu",
                    "vl_nba_sequent_batch_gpu",
                ],
            },
            split_compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 122127168,
                "stderr_tail": "\n".join(
                    [
                        "ptxas info    : Function properties for vl_ico_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_comb_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_sequent_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                    ]
                ),
            },
            split_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_cuModuleLoad",
                ]
            )
            + "\n",
            split_nvcc_device_link_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {
                    "linked_exists": True,
                    "linked_size": 26861344,
                    "linked_kernel_symbol_present": True,
                },
            },
            split_cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_cuModuleLoad",
                    "run_vl_hybrid: stage=after_kernel_resolution",
                    "run_vl_hybrid: stage=before_first_kernel_launch",
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_split_runtime_illegal_access_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_split_runtime_illegal_access_debug",
        )
        self.assertEqual(payload["observations"]["split_nvcc_device_link_compile_status"], "ok")
        self.assertEqual(payload["observations"]["split_nvcc_device_link_link_status"], "ok")
        self.assertEqual(payload["observations"]["split_cubin_smoke_status"], "illegal_memory_access")
        self.assertEqual(payload["observations"]["split_cubin_smoke_last_stage"], "after_first_kernel_launch")

    def test_prefers_split_nba_comb_illegal_access_debug_when_other_split_kernels_pass(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 121416128,
            },
            full_cubin_probe_payload={
                "status": "timed_out",
                "output_exists": False,
                "output_size": None,
            },
            nvcc_device_link_cubin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            nvcc_device_link_fatbin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument",
                    "run_vl_hybrid.c:212 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload={
                "max_accepted_stack_limit": 523712,
                "min_rejected_stack_limit_target": 523744,
                "launch_at_max_result": {
                    "status": "invalid_argument",
                    "last_stage": "before_first_kernel_launch",
                },
            },
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload={
                "kernels": [
                    {"name": "vl_ico_batch_gpu"},
                    {"name": "vl_nba_comb_batch_gpu"},
                    {"name": "vl_nba_sequent_batch_gpu"},
                ],
                "launch_sequence": [
                    "vl_ico_batch_gpu",
                    "vl_nba_comb_batch_gpu",
                    "vl_nba_sequent_batch_gpu",
                ],
            },
            split_compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 122127168,
                "stderr_tail": "\n".join(
                    [
                        "ptxas info    : Function properties for vl_ico_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_comb_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_sequent_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                    ]
                ),
            },
            split_smoke_log_text="run_vl_hybrid: stage=before_cuModuleLoad\n",
            split_nvcc_device_link_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {
                    "linked_exists": True,
                    "linked_size": 26861344,
                    "linked_kernel_symbol_present": True,
                },
            },
            split_cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_ico_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block1_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 719: unspecified launch failure",
                ]
            )
            + "\n",
            split_nba_comb_block8_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_sequent_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_split_nba_comb_illegal_access_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_split_nba_comb_illegal_access_debug",
        )
        self.assertEqual(payload["observations"]["split_ico_smoke_status"], "ok")
        self.assertEqual(payload["observations"]["split_nba_sequent_smoke_status"], "ok")
        self.assertEqual(payload["observations"]["split_nba_comb_smoke_status"], "illegal_memory_access")
        self.assertEqual(
            payload["observations"]["split_nba_comb_block1_smoke_status"],
            "unspecified_launch_failure",
        )

    def test_prefers_split_m_axi_if0_debug_when_zero_call_prefix_passes_but_prefix331_fails(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={"status": "ok", "output_exists": True, "output_size": 121416128},
            full_cubin_probe_payload={"status": "timed_out", "output_exists": False, "output_size": None},
            nvcc_device_link_cubin_probe_payload={"compile": {"status": "timed_out"}, "link": {"status": "skipped"}},
            nvcc_device_link_fatbin_probe_payload={"compile": {"status": "timed_out"}, "link": {"status": "skipped"}},
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument",
                    "run_vl_hybrid.c:212 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload={
                "max_accepted_stack_limit": 523712,
                "min_rejected_stack_limit_target": 523744,
                "launch_at_max_result": {"status": "invalid_argument", "last_stage": "before_first_kernel_launch"},
            },
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload={
                "kernels": [
                    {"name": "vl_ico_batch_gpu"},
                    {"name": "vl_nba_comb_batch_gpu"},
                    {"name": "vl_nba_sequent_batch_gpu"},
                ],
                "launch_sequence": [
                    "vl_ico_batch_gpu",
                    "vl_nba_comb_batch_gpu",
                    "vl_nba_sequent_batch_gpu",
                ],
            },
            split_compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 122127168,
                "stderr_tail": "\n".join(
                    [
                        "ptxas info    : Function properties for vl_ico_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_comb_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_sequent_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                    ]
                ),
            },
            split_smoke_log_text="run_vl_hybrid: stage=before_cuModuleLoad\n",
            split_nvcc_device_link_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True, "linked_kernel_symbol_present": True},
            },
            split_cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_ico_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block1_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 719: unspecified launch failure",
                ]
            )
            + "\n",
            split_nba_comb_block8_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_sequent_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix330_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix330_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix331_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_split_m_axi_if0_illegal_access_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_split_m_axi_if0_illegal_access_debug",
        )
        self.assertEqual(payload["observations"]["split_nba_comb_prefix330_smoke_status"], "ok")
        self.assertEqual(payload["observations"]["split_nba_comb_prefix331_smoke_status"], "illegal_memory_access")

    def test_prefers_split_m_axi_if0_first_half_core_debug_when_high_offset_bypass_still_fails(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={"status": "ok", "output_exists": True, "output_size": 121416128},
            full_cubin_probe_payload={"status": "timed_out", "output_exists": False, "output_size": None},
            nvcc_device_link_cubin_probe_payload={"compile": {"status": "timed_out"}, "link": {"status": "skipped"}},
            nvcc_device_link_fatbin_probe_payload={"compile": {"status": "timed_out"}, "link": {"status": "skipped"}},
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument",
                    "run_vl_hybrid.c:212 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload={
                "max_accepted_stack_limit": 523712,
                "min_rejected_stack_limit_target": 523744,
                "launch_at_max_result": {"status": "invalid_argument", "last_stage": "before_first_kernel_launch"},
            },
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload={
                "kernels": [
                    {"name": "vl_ico_batch_gpu"},
                    {"name": "vl_nba_comb_batch_gpu"},
                    {"name": "vl_nba_sequent_batch_gpu"},
                ],
                "launch_sequence": [
                    "vl_ico_batch_gpu",
                    "vl_nba_comb_batch_gpu",
                    "vl_nba_sequent_batch_gpu",
                ],
            },
            split_compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 122127168,
                "stderr_tail": "\n".join(
                    [
                        "ptxas info    : Function properties for vl_ico_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_comb_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_sequent_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                    ]
                ),
            },
            split_smoke_log_text="run_vl_hybrid: stage=before_cuModuleLoad\n",
            split_nvcc_device_link_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True, "linked_kernel_symbol_present": True},
            },
            split_cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_ico_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block1_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 719: unspecified launch failure",
                ]
            )
            + "\n",
            split_nba_comb_block8_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_sequent_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix330_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix330_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix331_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_ret_after_first_store_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_split_m_axi_if0_first_half_core_illegal_access_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_split_m_axi_if0_first_half_core_illegal_access_debug",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_zero_high_offsets_smoke_status"],
            "illegal_memory_access",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_ret_after_first_store_smoke_status"],
            "illegal_memory_access",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_status"],
            "illegal_memory_access",
        )

    def test_prefers_split_m_axi_if0_b64_arg_call_entry_abi_debug_when_noarg_call_passes(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={"status": "ok", "output_exists": True, "output_size": 121416128},
            full_cubin_probe_payload={"status": "timed_out", "output_exists": False, "output_size": None},
            nvcc_device_link_cubin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            nvcc_device_link_fatbin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument",
                    "run_vl_hybrid.c:212 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload={
                "max_accepted_stack_limit": 523712,
                "min_rejected_stack_limit_target": 523744,
                "launch_at_max_result": {
                    "status": "invalid_argument",
                    "last_stage": "before_first_kernel_launch",
                },
            },
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload={
                "launch_sequence": [
                    "vl_ico_batch_gpu",
                    "vl_nba_comb_batch_gpu",
                    "vl_nba_sequent_batch_gpu",
                ]
            },
            split_compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 122127168,
                "stderr_tail": "\n".join(
                    [
                        "ptxas info    : Function properties for vl_ico_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_comb_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_sequent_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                    ]
                ),
            },
            split_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_cuModuleLoad",
                    "run_vl_hybrid.c:259 CUDA error 200: device kernel image is invalid",
                ]
            )
            + "\n",
            split_nvcc_device_link_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_ico_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block1_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block8_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_sequent_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix330_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix330_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix331_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_ret_after_first_store_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_min_store_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_min_store_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_noarg_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_noarg_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_prefix331_param_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_param_only_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_split_m_axi_if0_b64_arg_call_entry_abi_illegal_access_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_split_m_axi_if0_b64_arg_call_entry_abi_illegal_access_debug",
        )
        self.assertEqual(payload["observations"]["split_nba_comb_prefix330_smoke_status"], "ok")
        self.assertEqual(payload["observations"]["split_nba_comb_prefix331_smoke_status"], "illegal_memory_access")
        self.assertEqual(payload["observations"]["split_nba_comb_prefix331_param_only_smoke_status"], "ok")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_noarg_ret_only_smoke_status"], "ok")
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_min_store_only_smoke_status"],
            "illegal_memory_access",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_ret_only_smoke_status"],
            "illegal_memory_access",
        )

    def test_prefers_split_m_axi_if0_live_b64_arg_handoff_debug_when_b64_zero_call_passes(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={"status": "ok", "output_exists": True, "output_size": 121416128},
            full_cubin_probe_payload={"status": "timed_out", "output_exists": False, "output_size": None},
            nvcc_device_link_cubin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            nvcc_device_link_fatbin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument",
                    "run_vl_hybrid.c:212 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload={
                "max_accepted_stack_limit": 523712,
                "min_rejected_stack_limit_target": 523744,
                "launch_at_max_result": {
                    "status": "invalid_argument",
                    "last_stage": "before_first_kernel_launch",
                },
            },
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload={
                "launch_sequence": [
                    "vl_ico_batch_gpu",
                    "vl_nba_comb_batch_gpu",
                    "vl_nba_sequent_batch_gpu",
                ]
            },
            split_compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 122127168,
                "stderr_tail": "\n".join(
                    [
                        "ptxas info    : Function properties for vl_ico_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_comb_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_sequent_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                    ]
                ),
            },
            split_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_cuModuleLoad",
                    "run_vl_hybrid.c:259 CUDA error 200: device kernel image is invalid",
                ]
            )
            + "\n",
            split_nvcc_device_link_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_ico_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block1_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block8_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_sequent_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix330_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix330_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix331_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_ret_after_first_store_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_min_store_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_min_store_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_noarg_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_noarg_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_b64_zero_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_prefix331_param_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_param_only_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_split_m_axi_if0_live_b64_arg_handoff_illegal_access_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_split_m_axi_if0_live_b64_arg_handoff_illegal_access_debug",
        )
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_noarg_ret_only_smoke_status"], "ok")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_status"], "ok")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_ret_only_smoke_status"], "illegal_memory_access")

    def test_prefers_split_m_axi_if0_live_pointer_like_b64_handoff_debug_when_rd4_variant_also_fails(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={"status": "ok", "output_exists": True, "output_size": 121416128},
            full_cubin_probe_payload={"status": "timed_out", "output_exists": False, "output_size": None},
            nvcc_device_link_cubin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            nvcc_device_link_fatbin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument",
                    "run_vl_hybrid.c:212 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload={
                "max_accepted_stack_limit": 523712,
                "min_rejected_stack_limit_target": 523744,
                "launch_at_max_result": {
                    "status": "invalid_argument",
                    "last_stage": "before_first_kernel_launch",
                },
            },
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload={
                "launch_sequence": [
                    "vl_ico_batch_gpu",
                    "vl_nba_comb_batch_gpu",
                    "vl_nba_sequent_batch_gpu",
                ]
            },
            split_compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 122127168,
                "stderr_tail": "\n".join(
                    [
                        "ptxas info    : Function properties for vl_ico_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_comb_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_sequent_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                    ]
                ),
            },
            split_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_cuModuleLoad",
                    "run_vl_hybrid.c:259 CUDA error 200: device kernel image is invalid",
                ]
            )
            + "\n",
            split_nvcc_device_link_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_ico_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block1_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block8_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_sequent_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix330_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix330_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix331_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_ret_after_first_store_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_min_store_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_min_store_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_noarg_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_noarg_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_b64_zero_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_b64_one_ret_only_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_rd4_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_rd4_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_prefix331_param_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_param_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_split_m_axi_if0_live_b64_arg_handoff_illegal_access_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_split_m_axi_if0_live_b64_arg_handoff_illegal_access_debug",
        )
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_status"], "ok")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_rd4_ret_only_smoke_status"], "illegal_memory_access")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_b64_one_ret_only_compile_status"], "timed_out")

    def test_prefers_split_m_axi_if0_live_nonzero_pointer_like_b64_handoff_debug_when_rd7_variant_also_fails(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={"status": "ok", "output_exists": True, "output_size": 121416128},
            full_cubin_probe_payload={"status": "timed_out", "output_exists": False, "output_size": None},
            nvcc_device_link_cubin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            nvcc_device_link_fatbin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument",
                    "run_vl_hybrid.c:212 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload={
                "max_accepted_stack_limit": 523712,
                "min_rejected_stack_limit_target": 523744,
                "launch_at_max_result": {
                    "status": "invalid_argument",
                    "last_stage": "before_first_kernel_launch",
                },
            },
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload={
                "launch_sequence": [
                    "vl_ico_batch_gpu",
                    "vl_nba_comb_batch_gpu",
                    "vl_nba_sequent_batch_gpu",
                ]
            },
            split_compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 122127168,
                "stderr_tail": "\n".join(
                    [
                        "ptxas info    : Function properties for vl_ico_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_comb_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_sequent_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                    ]
                ),
            },
            split_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_cuModuleLoad",
                    "run_vl_hybrid.c:259 CUDA error 200: device kernel image is invalid",
                ]
            )
            + "\n",
            split_nvcc_device_link_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_ico_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block1_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block8_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_sequent_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix330_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix330_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix331_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_ret_after_first_store_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_min_store_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_min_store_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_noarg_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_noarg_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_b64_zero_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_b64_one_ret_only_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_rd4_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_rd4_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_rd1_ret_only_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_rd7_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_rd7_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_prefix331_param_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_param_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_split_m_axi_if0_live_nonzero_pointer_like_b64_arg_handoff_illegal_access_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_split_m_axi_if0_live_nonzero_pointer_like_b64_arg_handoff_illegal_access_debug",
        )
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_rd4_ret_only_smoke_status"], "illegal_memory_access")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_rd7_ret_only_smoke_status"], "illegal_memory_access")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_rd1_ret_only_compile_status"], "timed_out")

    def test_prefers_split_m_axi_if0_compilable_live_nonzero_pointer_like_handoff_debug_when_rd6_and_imm1_only_time_out(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={"status": "ok", "output_exists": True, "output_size": 121416128},
            full_cubin_probe_payload={"status": "timed_out", "output_exists": False, "output_size": None},
            nvcc_device_link_cubin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            nvcc_device_link_fatbin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument",
                    "run_vl_hybrid.c:212 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload={
                "max_accepted_stack_limit": 523712,
                "min_rejected_stack_limit_target": 523744,
                "launch_at_max_result": {
                    "status": "invalid_argument",
                    "last_stage": "before_first_kernel_launch",
                },
            },
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload={
                "launch_sequence": [
                    "vl_ico_batch_gpu",
                    "vl_nba_comb_batch_gpu",
                    "vl_nba_sequent_batch_gpu",
                ]
            },
            split_compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 122127168,
                "stderr_tail": "\n".join(
                    [
                        "ptxas info    : Function properties for vl_ico_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_comb_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_sequent_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                    ]
                ),
            },
            split_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_cuModuleLoad",
                    "run_vl_hybrid.c:259 CUDA error 200: device kernel image is invalid",
                ]
            )
            + "\n",
            split_nvcc_device_link_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_ico_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block1_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block8_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_sequent_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix330_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix330_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix331_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_ret_after_first_store_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_min_store_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_min_store_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_noarg_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_noarg_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_b64_zero_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_b64_one_ret_only_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_rd4_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_rd4_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_rd1_ret_only_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_rd6_ret_only_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_rd7_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_rd7_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_prefix331_param_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_param_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_split_m_axi_if0_compilable_live_nonzero_pointer_like_b64_arg_handoff_illegal_access_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_split_m_axi_if0_compilable_live_nonzero_pointer_like_b64_arg_handoff_illegal_access_debug",
        )
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_rd6_ret_only_compile_status"], "timed_out")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_b64_imm1_ret_only_compile_status"], "timed_out")

    def test_prefers_split_m_axi_if0_compilable_live_nonzero_b64_handoff_debug_when_rd3_variant_also_fails(self) -> None:
        payload = self.module.build_status(
            caliptra_status_payload={
                "outcome": {
                    "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
                },
                "gpu_build": {
                    "status": "llc_tls_global_blocked",
                    "blocker_kind": "nvptx_tls_lowering",
                },
            },
            bypass_ll_exists=True,
            official_ptx_exists=True,
            official_cubin_exists=True,
            compile_only_probe_payload={"status": "ok", "output_exists": True, "output_size": 121416128},
            full_cubin_probe_payload={"status": "timed_out", "output_exists": False, "output_size": None},
            nvcc_device_link_cubin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            nvcc_device_link_fatbin_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
            },
            compile_only_kernel_symbol_present=True,
            cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320 target=564320",
                    "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=564320 err=1:invalid argument",
                    "run_vl_hybrid.c:212 CUDA error 1: invalid argument",
                ]
            )
            + "\n",
            stack_limit_probe_payload={
                "max_accepted_stack_limit": 523712,
                "min_rejected_stack_limit_target": 523744,
                "launch_at_max_result": {
                    "status": "invalid_argument",
                    "last_stage": "before_first_kernel_launch",
                },
            },
            trial_ptx_exists=True,
            trial_ptxas_log_text="",
            split_kernel_manifest_payload={
                "launch_sequence": [
                    "vl_ico_batch_gpu",
                    "vl_nba_comb_batch_gpu",
                    "vl_nba_sequent_batch_gpu",
                ]
            },
            split_compile_only_probe_payload={
                "status": "ok",
                "output_exists": True,
                "output_size": 122127168,
                "stderr_tail": "\n".join(
                    [
                        "ptxas info    : Function properties for vl_ico_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_comb_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                        "ptxas info    : Function properties for vl_nba_sequent_batch_gpu",
                        "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                    ]
                ),
            },
            split_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_cuModuleLoad",
                    "run_vl_hybrid.c:259 CUDA error 200: device kernel image is invalid",
                ]
            )
            + "\n",
            split_nvcc_device_link_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_cubin_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_ico_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block1_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_block8_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_sequent_smoke_log_text="run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n",
            split_nba_comb_prefix330_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix330_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_prefix331_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_ret_after_first_store_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_min_store_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_min_store_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_noarg_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_noarg_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_b64_zero_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_b64_one_ret_only_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_rd3_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_rd3_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid: stage=before_final_sync",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_rd3_shr12_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid: stage=before_final_sync",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid: stage=before_final_sync",
                    "run_vl_hybrid.c:563 CUDA error 716: misaligned address",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid: stage=before_final_sync",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_b64_synth16_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid: stage=before_final_sync",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_rd4_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_rd4_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_rd4_trunc_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_rd1_ret_only_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_rd6_ret_only_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_rd7_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_rd7_ret_only_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_rd7_trunc_ret_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_ret_only_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ret_only_trunc_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_ldptr_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_first_store_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=after_first_kernel_launch",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_final_sync",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_final_sync",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_final_sync",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_final_sync",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_final_sync",
                    "run_vl_hybrid.c:563 CUDA error 700: an illegal memory access was encountered",
                ]
            )
            + "\n",
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke_log_text=(
                "error: cubin not found\n"
            ),
            split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe_payload={
                "compile": {"status": "timed_out"},
                "link": {"status": "skipped"},
                "observations": {"linked_exists": False},
            },
            split_nba_comb_prefix331_param_only_probe_payload={
                "compile": {"status": "ok"},
                "link": {"status": "ok"},
                "observations": {"linked_exists": True},
            },
            split_nba_comb_prefix331_param_only_smoke_log_text=(
                "run_vl_hybrid: stage=after_cleanup\nok: steps=1 kernels_per_step=1\n"
            ),
        )

        self.assertEqual(
            payload["decision"]["status"],
            "ready_for_deeper_caliptra_split_m_axi_if0_first_store_compilable_branch1_load_provenance_nonconstant_loaded_byte_dependent_store_source_bits_runtime_fault_debug",
        )
        self.assertEqual(
            payload["decision"]["recommended_next_tactic"],
            "deeper_caliptra_split_m_axi_if0_first_store_compilable_branch1_load_provenance_nonconstant_loaded_byte_dependent_store_source_bits_runtime_fault_debug",
        )
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_rd3_ret_only_smoke_status"], "illegal_memory_access")
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke_status"],
            "illegal_memory_access",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_status"],
            "misaligned_address",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_status"],
            "illegal_memory_access",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_status"],
            "illegal_memory_access",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_status"],
            "ok",
        )
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_rd4_ret_only_smoke_status"], "illegal_memory_access")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_status"], "ok")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_rd7_ret_only_smoke_status"], "illegal_memory_access")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_status"], "ok")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_ret_only_trunc_smoke_status"], "ok")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke_status"], "ok")
        self.assertEqual(payload["observations"]["split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke_status"], "ok")
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke_status"],
            "ok",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke_status"],
            "illegal_memory_access",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke_status"],
            "ok",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke_status"],
            "ok",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke_status"],
            "illegal_memory_access",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke_status"],
            "ok",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke_status"],
            "illegal_memory_access",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke_status"],
            "illegal_memory_access",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke_status"],
            "illegal_memory_access",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke_status"],
            "illegal_memory_access",
        )
        self.assertEqual(
            payload[
                "observations"
            ]["split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload[
                "observations"
            ]["split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload[
                "observations"
            ]["split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload[
                "observations"
            ]["split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload[
                "observations"
            ]["split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload[
                "observations"
            ]["split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload[
                "observations"
            ]["split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke_status"],
            "ok",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke_status"],
            "ok",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke_status"],
            "illegal_memory_access",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_compile_status"],
            "timed_out",
        )
        self.assertEqual(
            payload["observations"]["split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_compile_status"],
            "timed_out",
        )

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            status_json = root / "status.json"
            bypass_ll = root / "vl_batch_gpu_caliptra_tls_bypass.ll"
            official_ptx = root / "vl_batch_gpu.ptx"
            compile_only_probe_json = root / "compile_only_probe.json"
            full_cubin_probe_json = root / "full_cubin_probe.json"
            compile_only_object = root / "compile_only_probe.o"
            cubin_smoke_log = root / "cubin_smoke.log"
            stack_limit_probe_json = root / "stack_limit_probe.json"
            nvcc_device_link_cubin_probe_json = root / "nvcc_cubin.json"
            nvcc_device_link_fatbin_probe_json = root / "nvcc_fatbin.json"
            trial_ptx = root / "trial.ptx"
            trial_log = root / "trial.log"
            split_kernel_manifest = root / "split_manifest.json"
            split_compile_only_probe_json = root / "split_compile_only_probe.json"
            split_smoke_log = root / "split_smoke.log"
            split_nvcc_device_link_probe_json = root / "split_nvcc_device_link_probe.json"
            split_cubin_smoke_log = root / "split_cubin_smoke.log"
            split_ico_smoke_log = root / "split_ico.log"
            split_nba_comb_smoke_log = root / "split_nba_comb.log"
            split_nba_comb_block1_smoke_log = root / "split_nba_comb_block1.log"
            split_nba_comb_block8_smoke_log = root / "split_nba_comb_block8.log"
            split_nba_sequent_smoke_log = root / "split_nba_sequent.log"
            split_nba_comb_prefix330_probe_json = root / "split_nba_comb_prefix330_probe.json"
            split_nba_comb_prefix330_smoke_log = root / "split_nba_comb_prefix330.log"
            split_nba_comb_prefix331_probe_json = root / "split_nba_comb_prefix331_probe.json"
            split_nba_comb_prefix331_smoke_log = root / "split_nba_comb_prefix331.log"
            split_nba_comb_m_axi_if0_zero_high_offsets_probe_json = root / "split_nba_comb_m_axi_if0_zero_high_offsets_probe.json"
            split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log = root / "split_nba_comb_m_axi_if0_zero_high_offsets.log"
            split_nba_comb_m_axi_if0_ret_after_first_store_probe_json = root / "split_nba_comb_m_axi_if0_ret_after_first_store_probe.json"
            split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log = root / "split_nba_comb_m_axi_if0_ret_after_first_store.log"
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_json = root / "split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe.json"
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log = root / "split_nba_comb_m_axi_if0_first_half_zero_high_offsets.log"
            split_nba_comb_m_axi_if0_min_store_only_probe_json = root / "split_nba_comb_m_axi_if0_min_store_only_probe.json"
            split_nba_comb_m_axi_if0_min_store_only_smoke_log = root / "split_nba_comb_m_axi_if0_min_store_only.log"
            split_nba_comb_m_axi_if0_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_ret_only_probe.json"
            split_nba_comb_m_axi_if0_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_ret_only.log"
            split_nba_comb_m_axi_if0_noarg_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_noarg_ret_only_probe.json"
            split_nba_comb_m_axi_if0_noarg_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_noarg_ret_only.log"
            split_nba_comb_m_axi_if0_b64_zero_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_b64_zero_ret_only_probe.json"
            split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_b64_zero_ret_only.log"
            split_nba_comb_m_axi_if0_b64_one_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_b64_one_ret_only_probe.json"
            split_nba_comb_m_axi_if0_b64_one_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_b64_one_ret_only.log"
            split_nba_comb_m_axi_if0_rd3_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_rd3_ret_only_probe.json"
            split_nba_comb_m_axi_if0_rd3_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_rd3_ret_only.log"
            split_nba_comb_m_axi_if0_rd3_shr12_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_rd3_shr12_ret_only_probe.json"
            split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_rd3_shr12_ret_only.log"
            split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_probe.json"
            split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only.log"
            split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_probe.json"
            split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only.log"
            split_nba_comb_m_axi_if0_b64_synth16_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_b64_synth16_ret_only_probe.json"
            split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_b64_synth16_ret_only.log"
            split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_probe.json"
            split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only.log"
            split_nba_comb_m_axi_if0_rd4_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_rd4_ret_only_probe.json"
            split_nba_comb_m_axi_if0_rd4_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_rd4_ret_only.log"
            split_nba_comb_m_axi_if0_rd4_trunc_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_rd4_trunc_ret_only_probe.json"
            split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_rd4_trunc_ret_only.log"
            split_nba_comb_m_axi_if0_rd1_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_rd1_ret_only_probe.json"
            split_nba_comb_m_axi_if0_rd1_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_rd1_ret_only.log"
            split_nba_comb_m_axi_if0_rd6_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_rd6_ret_only_probe.json"
            split_nba_comb_m_axi_if0_rd6_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_rd6_ret_only.log"
            split_nba_comb_m_axi_if0_rd7_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_rd7_ret_only_probe.json"
            split_nba_comb_m_axi_if0_rd7_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_rd7_ret_only.log"
            split_nba_comb_m_axi_if0_rd7_trunc_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_rd7_trunc_ret_only_probe.json"
            split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_rd7_trunc_ret_only.log"
            split_nba_comb_m_axi_if0_ret_only_trunc_probe_json = root / "split_nba_comb_m_axi_if0_ret_only_trunc_probe.json"
            split_nba_comb_m_axi_if0_ret_only_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_ret_only_trunc.log"
            split_nba_comb_m_axi_if0_ldptr_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_ldptr_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_ldptr_ret_trunc.log"
            split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_high_offset_load_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc.log"
            split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_probe_json = root / "split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_probe.json"
            split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke_log = root / "split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc.log"
            split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe_json = root / "split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe.json"
            split_nba_comb_m_axi_if0_b64_imm1_ret_only_smoke_log = root / "split_nba_comb_m_axi_if0_b64_imm1_ret_only.log"
            split_nba_comb_prefix331_param_only_probe_json = root / "split_nba_comb_prefix331_param_only_probe.json"
            split_nba_comb_prefix331_param_only_smoke_log = root / "split_nba_comb_prefix331_param_only.log"
            json_out = root / "tactics.json"

            status_json.write_text(
                json.dumps(
                    {
                        "outcome": {
                            "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
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
            bypass_ll.write_text("; fake\n", encoding="utf-8")
            official_ptx.write_text("// fake ptx\n", encoding="utf-8")
            compile_only_probe_json.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "output_exists": True,
                        "output_size": 121416128,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            full_cubin_probe_json.write_text(
                json.dumps(
                    {
                        "status": "timed_out",
                        "output_exists": False,
                        "output_size": None,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            compile_only_object.write_text("", encoding="utf-8")
            cubin_smoke_log.write_text(
                "run_vl_hybrid: attr vl_eval_batch_gpu LOCAL_SIZE_BYTES=564320\nrun_vl_hybrid: ctx_limit STACK_SIZE current=1024 required=564320\nrun_vl_hybrid.c:212 CUDA error 1: invalid argument\n",
                encoding="utf-8",
            )
            stack_limit_probe_json.write_text(
                json.dumps(
                    {
                        "max_accepted_stack_limit": 523712,
                        "min_rejected_stack_limit_target": 523744,
                        "launch_at_max_result": {
                            "status": "invalid_argument",
                            "last_stage": "before_first_kernel_launch",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            nvcc_device_link_cubin_probe_json.write_text(
                json.dumps({"compile": {"status": "timed_out"}, "link": {"status": "skipped"}}) + "\n",
                encoding="utf-8",
            )
            nvcc_device_link_fatbin_probe_json.write_text(
                json.dumps({"compile": {"status": "timed_out"}, "link": {"status": "skipped"}}) + "\n",
                encoding="utf-8",
            )
            trial_ptx.write_text("// fake trial ptx\n", encoding="utf-8")
            trial_log.write_text(
                "ptxas warning : Unresolved extern variable '_ZN9Verilated3t_sE' in whole program compilation, ignoring extern qualifier\n",
                encoding="utf-8",
            )
            split_kernel_manifest.write_text(
                json.dumps(
                    {
                        "kernels": [
                            {"name": "vl_ico_batch_gpu"},
                            {"name": "vl_nba_comb_batch_gpu"},
                            {"name": "vl_nba_sequent_batch_gpu"},
                        ],
                        "launch_sequence": [
                            "vl_ico_batch_gpu",
                            "vl_nba_comb_batch_gpu",
                            "vl_nba_sequent_batch_gpu",
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            split_compile_only_probe_json.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "output_exists": True,
                        "output_size": 122127168,
                        "stderr_tail": "\n".join(
                            [
                                "ptxas info    : Function properties for vl_ico_batch_gpu",
                                "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                                "ptxas info    : Function properties for vl_nba_comb_batch_gpu",
                                "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                                "ptxas info    : Function properties for vl_nba_sequent_batch_gpu",
                                "    0 bytes stack frame, 0 bytes spill stores, 0 bytes spill loads",
                            ]
                        ),
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            split_smoke_log.write_text(
                "run_vl_hybrid: stage=before_cuModuleLoad\n",
                encoding="utf-8",
            )
            split_ico_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_block1_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_block8_smoke_log.write_text("", encoding="utf-8")
            split_nba_sequent_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_prefix330_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_prefix330_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_prefix331_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_prefix331_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_zero_high_offsets_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_ret_after_first_store_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_min_store_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_min_store_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_noarg_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_noarg_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_b64_zero_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_b64_one_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_b64_one_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd3_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd3_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd3_shr12_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_b64_synth16_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd4_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd4_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd4_trunc_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd1_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd1_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd6_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd6_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd7_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd7_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd7_trunc_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_ret_only_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_ret_only_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_ldptr_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_probe_json.write_text(
                "{}\n", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke_log.write_text(
                "", encoding="utf-8"
            )
            split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_m_axi_if0_b64_imm1_ret_only_smoke_log.write_text("", encoding="utf-8")
            split_nba_comb_prefix331_param_only_probe_json.write_text("{}\n", encoding="utf-8")
            split_nba_comb_prefix331_param_only_smoke_log.write_text("", encoding="utf-8")

            argv = [
                "audit_campaign_caliptra_debug_tactics.py",
                "--caliptra-status-json",
                str(status_json),
                "--bypass-ll",
                str(bypass_ll),
                "--official-ptx",
                str(official_ptx),
                "--compile-only-probe-json",
                str(compile_only_probe_json),
                "--full-cubin-probe-json",
                str(full_cubin_probe_json),
                "--nvcc-device-link-cubin-probe-json",
                str(nvcc_device_link_cubin_probe_json),
                "--nvcc-device-link-fatbin-probe-json",
                str(nvcc_device_link_fatbin_probe_json),
                "--compile-only-object",
                str(compile_only_object),
                "--cubin-smoke-log",
                str(cubin_smoke_log),
                "--stack-limit-probe-json",
                str(stack_limit_probe_json),
                "--trial-ptx",
                str(trial_ptx),
                "--trial-ptxas-log",
                str(trial_log),
                "--split-kernel-manifest",
                str(split_kernel_manifest),
                "--split-compile-only-probe-json",
                str(split_compile_only_probe_json),
                "--split-smoke-log",
                str(split_smoke_log),
                "--split-nvcc-device-link-probe-json",
                str(split_nvcc_device_link_probe_json),
                "--split-cubin-smoke-log",
                str(split_cubin_smoke_log),
                "--split-ico-smoke-log",
                str(split_ico_smoke_log),
                "--split-nba-comb-smoke-log",
                str(split_nba_comb_smoke_log),
                "--split-nba-comb-block1-smoke-log",
                str(split_nba_comb_block1_smoke_log),
                "--split-nba-comb-block8-smoke-log",
                str(split_nba_comb_block8_smoke_log),
                "--split-nba-sequent-smoke-log",
                str(split_nba_sequent_smoke_log),
                "--split-nba-comb-prefix330-probe-json",
                str(split_nba_comb_prefix330_probe_json),
                "--split-nba-comb-prefix330-smoke-log",
                str(split_nba_comb_prefix330_smoke_log),
                "--split-nba-comb-prefix331-probe-json",
                str(split_nba_comb_prefix331_probe_json),
                "--split-nba-comb-prefix331-smoke-log",
                str(split_nba_comb_prefix331_smoke_log),
                "--split-nba-comb-m-axi-if0-zero-high-offsets-probe-json",
                str(split_nba_comb_m_axi_if0_zero_high_offsets_probe_json),
                "--split-nba-comb-m-axi-if0-zero-high-offsets-smoke-log",
                str(split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log),
                "--split-nba-comb-m-axi-if0-ret-after-first-store-probe-json",
                str(split_nba_comb_m_axi_if0_ret_after_first_store_probe_json),
                "--split-nba-comb-m-axi-if0-ret-after-first-store-smoke-log",
                str(split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log),
                "--split-nba-comb-m-axi-if0-first-half-zero-high-offsets-probe-json",
                str(split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_json),
                "--split-nba-comb-m-axi-if0-first-half-zero-high-offsets-smoke-log",
                str(split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log),
                "--split-nba-comb-m-axi-if0-min-store-only-probe-json",
                str(split_nba_comb_m_axi_if0_min_store_only_probe_json),
                "--split-nba-comb-m-axi-if0-min-store-only-smoke-log",
                str(split_nba_comb_m_axi_if0_min_store_only_smoke_log),
                "--split-nba-comb-m-axi-if0-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-noarg-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_noarg_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-noarg-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_noarg_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-b64-zero-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_b64_zero_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-b64-zero-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-b64-one-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_b64_one_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-b64-one-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_b64_one_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-rd3-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_rd3_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-rd3-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_rd3_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-rd3-shr12-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_rd3_shr12_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-rd3-shr12-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-rd3-small-nonzero-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-rd3-small-nonzero-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-rd3-small-aligned-nonzero-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-rd3-small-aligned-nonzero-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-b64-synth16-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_b64_synth16_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-b64-synth16-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-b64-synth16-trunc-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-b64-synth16-trunc-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-rd4-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_rd4_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-rd4-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_rd4_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-rd4-trunc-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_rd4_trunc_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-rd4-trunc-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-rd1-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_rd1_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-rd1-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_rd1_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-rd6-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_rd6_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-rd6-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_rd6_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-rd7-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_rd7_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-rd7-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_rd7_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-rd7-trunc-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_rd7_trunc_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-rd7-trunc-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_log),
                "--split-nba-comb-m-axi-if0-ret-only-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_ret_only_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-ret-only-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_ret_only_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-ldptr-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_ldptr_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-ldptr-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-high-offset-load-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-high-offset-load-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-branch-merge-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-branch-merge-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-zero-data-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-zero-data-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-one-data-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-one-data-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mov-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mov-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-zero-store-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-zero-store-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-predicated01-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-predicated01-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-predicated11-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-predicated11-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-predicated10-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-predicated10-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const1-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const1-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const1-and255-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const1-and255-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const2-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const2-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const3-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const3-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const129-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const129-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const257-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const257-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const513-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const513-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const0-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const0-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-dead-mask-const1-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-dead-mask-const1-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-selp-same-const1-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-selp-same-const1-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-predicated01-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-predicated01-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-force-else-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-force-else-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-selp-const1-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-selp-const1-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-mask1-shl8-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-mask1-shl8-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-mask1-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-masked-data-mask1-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-dead-mask-const1-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-dead-mask-const1-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-dead-mask-zero-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-dead-mask-zero-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-same-const1-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-same-const1-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-same-const257-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-selp-same-const257-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl8-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl8-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl8-and255-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl8-and255-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl1-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl1-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl4-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl4-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl6-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl6-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl7-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl7-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl9-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl9-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shr8-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shr8-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl8-sep-reg-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl8-sep-reg-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-sep-reg-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-sep-reg-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-xor-self-zero-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-xor-self-zero-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-self-load-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-self-load-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-store-plus1-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-store-plus1-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-or1-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-or1-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask2-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask2-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-maskff-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-maskff-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask3-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask3-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-first-store-branch1-alt-load-ret-trunc-probe-json",
                str(split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_probe_json),
                "--split-nba-comb-m-axi-if0-first-store-branch1-alt-load-ret-trunc-smoke-log",
                str(split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke_log),
                "--split-nba-comb-m-axi-if0-b64-imm1-ret-only-probe-json",
                str(split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe_json),
                "--split-nba-comb-m-axi-if0-b64-imm1-ret-only-smoke-log",
                str(split_nba_comb_m_axi_if0_b64_imm1_ret_only_smoke_log),
                "--split-nba-comb-prefix331-param-only-probe-json",
                str(split_nba_comb_prefix331_param_only_probe_json),
                "--split-nba-comb-prefix331-param-only-smoke-log",
                str(split_nba_comb_prefix331_param_only_smoke_log),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                self.module,
                "_symbol_present",
                return_value=True,
            ):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_caliptra_debug_tactics")
            self.assertEqual(
                payload["decision"]["status"],
                "ready_for_deeper_caliptra_split_kernel_executable_path_debug",
            )


if __name__ == "__main__":
    unittest.main()
