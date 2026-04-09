#!/usr/bin/env python3
"""
Summarize the next concrete Caliptra debug tactic after the first-surface status
establishes that Caliptra is the current post-Vortex family.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_CALIPTRA_STATUS_JSON = REPO_ROOT / "work" / "campaign_caliptra_first_surface_status.json"
DEFAULT_BYPASS_LL = (
    REPO_ROOT / "work" / "vl_ir_exp" / "caliptra_gpu_cov_vl" / "vl_batch_gpu_caliptra_tls_bypass.ll"
)
DEFAULT_OFFICIAL_PTX = REPO_ROOT / "work" / "vl_ir_exp" / "caliptra_gpu_cov_vl" / "vl_batch_gpu.ptx"
DEFAULT_OFFICIAL_CUBIN = REPO_ROOT / "work" / "vl_ir_exp" / "caliptra_gpu_cov_vl" / "vl_batch_gpu.cubin"
DEFAULT_COMPILE_ONLY_PROBE_JSON = REPO_ROOT / "work" / "caliptra_ptxas_compile_only_probe.json"
DEFAULT_FULL_CUBIN_PROBE_JSON = REPO_ROOT / "work" / "caliptra_ptxas_timeout_probe.json"
DEFAULT_NVCC_DEVICE_LINK_CUBIN_PROBE_JSON = REPO_ROOT / "work" / "caliptra_nvcc_device_link_cubin_probe.json"
DEFAULT_NVCC_DEVICE_LINK_FATBIN_PROBE_JSON = REPO_ROOT / "work" / "caliptra_nvcc_device_link_fatbin_probe.json"
DEFAULT_COMPILE_ONLY_OBJECT = REPO_ROOT / "work" / "caliptra_ptxas_compile_only_probe.o"
DEFAULT_CUBIN_SMOKE_LOG = REPO_ROOT / "work" / "caliptra_cubin_smoke_trace.log"
DEFAULT_STACK_LIMIT_PROBE_JSON = REPO_ROOT / "work" / "caliptra_stack_limit_probe.json"
DEFAULT_TRIAL_PTX = (
    REPO_ROOT / "work" / "vl_ir_exp" / "caliptra_gpu_cov_vl" / "vl_batch_gpu_caliptra_tls_bypass_trial.ptx"
)
DEFAULT_TRIAL_PTXAS_LOG = REPO_ROOT / "work" / "caliptra_tls_bypass_trial_ptxas.log"
DEFAULT_SPLIT_KERNEL_MANIFEST = REPO_ROOT / "work" / "caliptra_split_phase_probe" / "vl_kernel_manifest.json"
DEFAULT_SPLIT_COMPILE_ONLY_PROBE_JSON = (
    REPO_ROOT / "work" / "caliptra_split_phase_probe" / "vl_batch_gpu_split_compile_only_probe.json"
)
DEFAULT_SPLIT_SMOKE_LOG = REPO_ROOT / "work" / "caliptra_split_phase_probe" / "split_ptx_smoke_trace.log"
DEFAULT_SPLIT_NVCC_DEVICE_LINK_PROBE_JSON = (
    REPO_ROOT / "work" / "caliptra_split_phase_probe" / "vl_batch_gpu_split_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_CUBIN_SMOKE_LOG = (
    REPO_ROOT / "work" / "caliptra_split_phase_probe" / "split_cubin_smoke_trace.log"
)
DEFAULT_SPLIT_ICO_SMOKE_LOG = (
    REPO_ROOT / "work" / "caliptra_split_phase_probe" / "split_cubin_ico_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_SMOKE_LOG = (
    REPO_ROOT / "work" / "caliptra_split_phase_probe" / "split_cubin_nba_comb_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_BLOCK1_SMOKE_LOG = (
    REPO_ROOT / "work" / "caliptra_split_phase_probe" / "split_cubin_nba_comb_block1_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_BLOCK8_SMOKE_LOG = (
    REPO_ROOT / "work" / "caliptra_split_phase_probe" / "split_cubin_nba_comb_block8_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_SEQUENT_SMOKE_LOG = (
    REPO_ROOT / "work" / "caliptra_split_phase_probe" / "split_cubin_nba_sequent_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_PREFIX330_PROBE_JSON = (
    REPO_ROOT / "work" / "caliptra_split_phase_probe" / "vl_batch_gpu_split_nba_comb_prefix330_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_PREFIX330_SMOKE_LOG = (
    REPO_ROOT / "work" / "caliptra_split_phase_probe" / "split_cubin_nba_comb_prefix330_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_PREFIX331_PROBE_JSON = (
    REPO_ROOT / "work" / "caliptra_split_phase_probe" / "vl_batch_gpu_split_nba_comb_prefix331_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_PREFIX331_SMOKE_LOG = (
    REPO_ROOT / "work" / "caliptra_split_phase_probe" / "split_cubin_nba_comb_prefix331_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_ZERO_HIGH_OFFSETS_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_zero_high_offsets_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_ZERO_HIGH_OFFSETS_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_zero_high_offsets_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RET_AFTER_FIRST_STORE_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_ret_after_first_store_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RET_AFTER_FIRST_STORE_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_ret_after_first_store_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_HALF_ZERO_HIGH_OFFSETS_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_half_zero_high_offsets_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_HALF_ZERO_HIGH_OFFSETS_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_MIN_STORE_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_min_store_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_MIN_STORE_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_min_store_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_NOARG_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_noarg_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_NOARG_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_noarg_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_ZERO_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_b64_zero_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_ZERO_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_ONE_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_b64_one_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_ONE_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_b64_one_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_rd3_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_rd3_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_SHR12_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_rd3_shr12_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_SHR12_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_SMALL_NONZERO_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_SMALL_NONZERO_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_SMALL_ALIGNED_NONZERO_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_SMALL_ALIGNED_NONZERO_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_SYNTH16_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_b64_synth16_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_SYNTH16_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_SYNTH16_TRUNC_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_SYNTH16_TRUNC_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD4_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_rd4_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD4_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_rd4_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD4_TRUNC_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_rd4_trunc_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD4_TRUNC_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD1_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_rd1_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD1_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_rd1_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD6_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_rd6_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD6_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_rd6_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD7_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_rd7_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD7_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_rd7_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD7_TRUNC_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_rd7_trunc_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD7_TRUNC_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RET_ONLY_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_ret_only_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RET_ONLY_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_ret_only_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_LDPTR_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_ldptr_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_LDPTR_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_HIGH_OFFSET_LOAD_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_HIGH_OFFSET_LOAD_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_BRANCH_MERGE_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_BRANCH_MERGE_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_ZERO_DATA_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_ZERO_DATA_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_ONE_DATA_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_ONE_DATA_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MOV_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MOV_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_ZERO_STORE_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_ZERO_STORE_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_PREDICATED01_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_PREDICATED01_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_PREDICATED11_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_PREDICATED11_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_PREDICATED10_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_PREDICATED10_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST1_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST1_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST1_AND255_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST1_AND255_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST2_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST2_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST3_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST3_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST129_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST129_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST257_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST257_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST513_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST513_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST0_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST0_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_DEAD_MASK_CONST1_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_DEAD_MASK_CONST1_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_SELP_SAME_CONST1_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_SELP_SAME_CONST1_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_MASK1_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_MASK1_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_PREDICATED01_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_PREDICATED01_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_FORCE_ELSE_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_FORCE_ELSE_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_SELP_CONST1_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_SELP_CONST1_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_MASK1_SHL8_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_MASK1_SHL8_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_DEAD_MASK_CONST1_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_DEAD_MASK_CONST1_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_DEAD_MASK_ZERO_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_DEAD_MASK_ZERO_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_SAME_CONST1_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_SAME_CONST1_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_SAME_CONST257_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_SAME_CONST257_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL8_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL8_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL8_AND255_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL8_AND255_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL1_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL1_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL4_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL4_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL6_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL6_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL7_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL7_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL9_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL9_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHR8_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHR8_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL8_SEP_REG_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL8_SEP_REG_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SEP_REG_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SEP_REG_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_XOR_SELF_ZERO_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_XOR_SELF_ZERO_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_SELF_LOAD_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_SELF_LOAD_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_STORE_PLUS1_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_STORE_PLUS1_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_OR1_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_OR1_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK2_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK2_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASKFF_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASKFF_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK3_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK3_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_ALT_LOAD_RET_TRUNC_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_ALT_LOAD_RET_TRUNC_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_IMM1_RET_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_m_axi_if0_b64_imm1_ret_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_IMM1_RET_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_m_axi_if0_b64_imm1_ret_only_smoke_trace.log"
)
DEFAULT_SPLIT_NBA_COMB_PREFIX331_PARAM_ONLY_PROBE_JSON = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "vl_batch_gpu_split_nba_comb_prefix331_param_only_nvcc_device_link_probe.json"
)
DEFAULT_SPLIT_NBA_COMB_PREFIX331_PARAM_ONLY_SMOKE_LOG = (
    REPO_ROOT
    / "work"
    / "caliptra_split_phase_probe"
    / "split_cubin_nba_comb_prefix331_param_only_smoke_trace.log"
)
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_caliptra_debug_tactics.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return _read_json(path)


def _read_text_if_exists(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _symbol_present(path: Path, symbol_name: str) -> bool | None:
    if not path.is_file():
        return None
    completed = subprocess.run(
        ["cuobjdump", "--dump-elf-symbols", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    haystack = "\n".join([completed.stdout or "", completed.stderr or ""])
    return symbol_name in haystack


def _smoke_status(log_text: str | None) -> dict[str, Any]:
    if not log_text:
        return {"status": None, "last_stage": None, "stack_limit_current": None, "stack_limit_required": None}
    last_stage = None
    stack_limit_current = None
    stack_limit_required = None
    for line in log_text.splitlines():
        prefix = "run_vl_hybrid: stage="
        if line.startswith(prefix):
            last_stage = line[len(prefix) :].strip()
        if "run_vl_hybrid: ctx_limit STACK_SIZE current=" in line:
            try:
                _, tail = line.split("current=", 1)
                current_raw, required_raw = tail.split(" required=", 1)
                required_raw = required_raw.split(" target=", 1)[0]
                stack_limit_current = int(current_raw.strip())
                stack_limit_required = int(required_raw.strip())
            except ValueError:
                pass
    if "run_vl_hybrid: ctx_limit STACK_SIZE updated=" in log_text:
        stack_limit_updated = True
    else:
        stack_limit_updated = False
    if (
        "CUDA error 1: invalid argument" in log_text
        and stack_limit_current is not None
        and stack_limit_required is not None
        and not stack_limit_updated
    ):
        status = "stack_limit_invalid_argument"
    elif "CUDA error 1: invalid argument" in log_text:
        status = "invalid_argument"
    elif "CUDA error 200: device kernel image is invalid" in log_text:
        status = "device_kernel_image_invalid"
    elif "CUDA error 500: named symbol not found" in log_text:
        status = "named_symbol_not_found"
    elif "CUDA error 700: an illegal memory access was encountered" in log_text:
        status = "illegal_memory_access"
    elif "CUDA error 716: misaligned address" in log_text:
        status = "misaligned_address"
    elif "CUDA error 719: unspecified launch failure" in log_text:
        status = "unspecified_launch_failure"
    elif "ok: steps=" in log_text:
        status = "ok"
    else:
        status = "unknown"
    return {
        "status": status,
        "last_stage": last_stage,
        "stack_limit_current": stack_limit_current,
        "stack_limit_required": stack_limit_required,
    }


RUNTIME_FAULT_STATUSES = {"illegal_memory_access", "unspecified_launch_failure", "misaligned_address"}


def _probe_reports_zero_stack_for_split_kernels(
    probe_payload: dict[str, Any] | None,
    kernel_names: list[str],
) -> bool:
    if not probe_payload:
        return False
    stderr_tail = str(probe_payload.get("stderr_tail") or "")
    if not stderr_tail:
        return False
    for kernel_name in kernel_names:
        marker = f"Function properties for {kernel_name}"
        if marker not in stderr_tail:
            return False
    return stderr_tail.count("0 bytes stack frame") >= len(kernel_names)


def build_status(
    *,
    caliptra_status_payload: dict[str, Any],
    bypass_ll_exists: bool,
    official_ptx_exists: bool,
    official_cubin_exists: bool,
    compile_only_probe_payload: dict[str, Any] | None,
    full_cubin_probe_payload: dict[str, Any] | None,
    nvcc_device_link_cubin_probe_payload: dict[str, Any] | None,
    nvcc_device_link_fatbin_probe_payload: dict[str, Any] | None,
    compile_only_kernel_symbol_present: bool | None,
    cubin_smoke_log_text: str | None,
    stack_limit_probe_payload: dict[str, Any] | None,
    trial_ptx_exists: bool,
    trial_ptxas_log_text: str | None,
    split_kernel_manifest_payload: dict[str, Any] | None,
    split_compile_only_probe_payload: dict[str, Any] | None,
    split_smoke_log_text: str | None,
    split_nvcc_device_link_probe_payload: dict[str, Any] | None = None,
    split_cubin_smoke_log_text: str | None = None,
    split_ico_smoke_log_text: str | None = None,
    split_nba_comb_smoke_log_text: str | None = None,
    split_nba_comb_block1_smoke_log_text: str | None = None,
    split_nba_comb_block8_smoke_log_text: str | None = None,
    split_nba_sequent_smoke_log_text: str | None = None,
    split_nba_comb_prefix330_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_prefix330_smoke_log_text: str | None = None,
    split_nba_comb_prefix331_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_prefix331_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_zero_high_offsets_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_ret_after_first_store_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_min_store_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_min_store_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_noarg_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_noarg_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_b64_zero_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_b64_one_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_b64_one_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_rd3_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_rd3_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_rd3_shr12_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_b64_synth16_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_rd4_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_rd4_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_rd4_trunc_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_rd1_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_rd1_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_rd6_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_rd6_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_rd7_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_rd7_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_rd7_trunc_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_ret_only_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_ret_only_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_ldptr_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_probe_payload: dict[
        str, Any
    ]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke_log_text: str
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke_log_text: str
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke_log_text: str
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_probe_payload: dict[
        str, Any
    ]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke_log_text: str
    | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_probe_payload: dict[
        str, Any
    ]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke_log_text: str
    | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_probe_payload: dict[
        str, Any
    ]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_probe_payload: dict[
        str, Any
    ]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke_log_text: str
    | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_probe_payload: dict[
        str, Any
    ]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke_log_text: str
    | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_probe_payload: dict[
        str, Any
    ]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke_log_text: str
    | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_probe_payload: dict[
        str, Any
    ]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke_log_text: str
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_probe_payload: dict[
        str, Any
    ]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke_log_text: str
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_probe_payload: dict[
        str, Any
    ]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke_log_text: str
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_probe_payload: dict[
        str, Any
    ]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke_log_text: str
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_probe_payload: dict[str, Any]
    | None = None,
    split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke_log_text: str | None = None,
    split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_m_axi_if0_b64_imm1_ret_only_smoke_log_text: str | None = None,
    split_nba_comb_prefix331_param_only_probe_payload: dict[str, Any] | None = None,
    split_nba_comb_prefix331_param_only_smoke_log_text: str | None = None,
) -> dict[str, Any]:
    outcome = dict(caliptra_status_payload.get("outcome") or {})
    gpu_build = dict(caliptra_status_payload.get("gpu_build") or {})
    current_status = str(outcome.get("status") or "")
    blocker_kind = str(gpu_build.get("blocker_kind") or "")
    compile_only_probe = dict(compile_only_probe_payload or {})
    full_cubin_probe = dict(full_cubin_probe_payload or {})
    nvcc_device_link_cubin_probe = dict(nvcc_device_link_cubin_probe_payload or {})
    nvcc_device_link_fatbin_probe = dict(nvcc_device_link_fatbin_probe_payload or {})
    compile_only_probe_status = str(compile_only_probe.get("status") or "")
    full_cubin_probe_status = str(full_cubin_probe.get("status") or "")
    nvcc_device_link_cubin_probe_status = str(nvcc_device_link_cubin_probe.get("compile", {}).get("status") or "")
    nvcc_device_link_fatbin_probe_status = str(nvcc_device_link_fatbin_probe.get("compile", {}).get("status") or "")
    compile_only_probe_output_exists = bool(compile_only_probe.get("output_exists"))
    cubin_smoke = _smoke_status(cubin_smoke_log_text)
    stack_limit_probe = dict(stack_limit_probe_payload or {})
    max_accepted_stack_limit = stack_limit_probe.get("max_accepted_stack_limit")
    min_rejected_stack_limit_target = stack_limit_probe.get("min_rejected_stack_limit_target")
    launch_at_max_result = dict(stack_limit_probe.get("launch_at_max_result") or {})
    split_kernel_manifest = dict(split_kernel_manifest_payload or {})
    split_kernel_names = [
        str(kernel.get("name") or "")
        for kernel in list(split_kernel_manifest.get("kernels") or [])
        if str(kernel.get("name") or "")
    ]
    split_launch_sequence = [
        str(name or "")
        for name in list(split_kernel_manifest.get("launch_sequence") or [])
        if str(name or "")
    ]
    split_compile_only_probe = dict(split_compile_only_probe_payload or {})
    split_compile_only_probe_status = str(split_compile_only_probe.get("status") or "")
    split_compile_only_probe_output_exists = bool(split_compile_only_probe.get("output_exists"))
    split_compile_only_zero_stack = _probe_reports_zero_stack_for_split_kernels(
        split_compile_only_probe,
        split_launch_sequence or split_kernel_names,
    )
    split_smoke = _smoke_status(split_smoke_log_text)
    split_nvcc_device_link_probe = dict(split_nvcc_device_link_probe_payload or {})
    split_nvcc_compile_status = str(split_nvcc_device_link_probe.get("compile", {}).get("status") or "")
    split_nvcc_link_status = str(split_nvcc_device_link_probe.get("link", {}).get("status") or "")
    split_nvcc_observations = dict(split_nvcc_device_link_probe.get("observations") or {})
    split_cubin_smoke = _smoke_status(split_cubin_smoke_log_text)
    split_ico_smoke = _smoke_status(split_ico_smoke_log_text)
    split_nba_comb_smoke = _smoke_status(split_nba_comb_smoke_log_text)
    split_nba_comb_block1_smoke = _smoke_status(split_nba_comb_block1_smoke_log_text)
    split_nba_comb_block8_smoke = _smoke_status(split_nba_comb_block8_smoke_log_text)
    split_nba_sequent_smoke = _smoke_status(split_nba_sequent_smoke_log_text)
    split_nba_comb_prefix330_probe = dict(split_nba_comb_prefix330_probe_payload or {})
    split_nba_comb_prefix330_compile_status = str(
        split_nba_comb_prefix330_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_prefix330_link_status = str(
        split_nba_comb_prefix330_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_prefix330_observations = dict(split_nba_comb_prefix330_probe.get("observations") or {})
    split_nba_comb_prefix330_smoke = _smoke_status(split_nba_comb_prefix330_smoke_log_text)
    split_nba_comb_prefix331_probe = dict(split_nba_comb_prefix331_probe_payload or {})
    split_nba_comb_prefix331_compile_status = str(
        split_nba_comb_prefix331_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_prefix331_link_status = str(
        split_nba_comb_prefix331_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_prefix331_observations = dict(split_nba_comb_prefix331_probe.get("observations") or {})
    split_nba_comb_prefix331_smoke = _smoke_status(split_nba_comb_prefix331_smoke_log_text)
    split_nba_comb_m_axi_if0_zero_high_offsets_probe = dict(
        split_nba_comb_m_axi_if0_zero_high_offsets_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_zero_high_offsets_compile_status = str(
        split_nba_comb_m_axi_if0_zero_high_offsets_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_zero_high_offsets_link_status = str(
        split_nba_comb_m_axi_if0_zero_high_offsets_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_zero_high_offsets_observations = dict(
        split_nba_comb_m_axi_if0_zero_high_offsets_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_zero_high_offsets_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log_text
    )
    split_nba_comb_m_axi_if0_ret_after_first_store_probe = dict(
        split_nba_comb_m_axi_if0_ret_after_first_store_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_ret_after_first_store_compile_status = str(
        split_nba_comb_m_axi_if0_ret_after_first_store_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_ret_after_first_store_link_status = str(
        split_nba_comb_m_axi_if0_ret_after_first_store_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_ret_after_first_store_observations = dict(
        split_nba_comb_m_axi_if0_ret_after_first_store_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_ret_after_first_store_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe = dict(
        split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_half_zero_high_offsets_compile_status = str(
        split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_half_zero_high_offsets_link_status = str(
        split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_half_zero_high_offsets_observations = dict(
        split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log_text
    )
    split_nba_comb_m_axi_if0_min_store_only_probe = dict(
        split_nba_comb_m_axi_if0_min_store_only_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_min_store_only_compile_status = str(
        split_nba_comb_m_axi_if0_min_store_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_min_store_only_link_status = str(
        split_nba_comb_m_axi_if0_min_store_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_min_store_only_observations = dict(
        split_nba_comb_m_axi_if0_min_store_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_min_store_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_min_store_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_ret_only_probe = dict(split_nba_comb_m_axi_if0_ret_only_probe_payload or {})
    split_nba_comb_m_axi_if0_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_ret_only_smoke = _smoke_status(split_nba_comb_m_axi_if0_ret_only_smoke_log_text)
    split_nba_comb_m_axi_if0_noarg_ret_only_probe = dict(split_nba_comb_m_axi_if0_noarg_ret_only_probe_payload or {})
    split_nba_comb_m_axi_if0_noarg_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_noarg_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_noarg_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_noarg_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_noarg_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_noarg_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_noarg_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_noarg_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_b64_zero_ret_only_probe = dict(
        split_nba_comb_m_axi_if0_b64_zero_ret_only_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_b64_zero_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_b64_zero_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_b64_zero_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_b64_zero_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_b64_zero_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_b64_zero_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_b64_one_ret_only_probe = dict(
        split_nba_comb_m_axi_if0_b64_one_ret_only_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_b64_one_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_b64_one_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_b64_one_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_b64_one_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_b64_one_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_b64_one_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_b64_one_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_b64_one_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_rd3_ret_only_probe = dict(split_nba_comb_m_axi_if0_rd3_ret_only_probe_payload or {})
    split_nba_comb_m_axi_if0_rd3_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_rd3_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd3_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_rd3_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd3_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_rd3_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_rd3_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_rd3_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_rd3_shr12_ret_only_probe = dict(
        split_nba_comb_m_axi_if0_rd3_shr12_ret_only_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_rd3_shr12_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_rd3_shr12_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd3_shr12_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_rd3_shr12_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd3_shr12_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_rd3_shr12_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_probe = dict(
        split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_probe = dict(
        split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_b64_synth16_ret_only_probe = dict(
        split_nba_comb_m_axi_if0_b64_synth16_ret_only_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_b64_synth16_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_b64_synth16_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_b64_synth16_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_b64_synth16_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_b64_synth16_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_b64_synth16_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_probe = dict(
        split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_rd4_ret_only_probe = dict(split_nba_comb_m_axi_if0_rd4_ret_only_probe_payload or {})
    split_nba_comb_m_axi_if0_rd4_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_rd4_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd4_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_rd4_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd4_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_rd4_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_rd4_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_rd4_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_rd4_trunc_ret_only_probe = dict(
        split_nba_comb_m_axi_if0_rd4_trunc_ret_only_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_rd4_trunc_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_rd4_trunc_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd4_trunc_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_rd4_trunc_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd4_trunc_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_rd4_trunc_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_rd1_ret_only_probe = dict(split_nba_comb_m_axi_if0_rd1_ret_only_probe_payload or {})
    split_nba_comb_m_axi_if0_rd1_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_rd1_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd1_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_rd1_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd1_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_rd1_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_rd1_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_rd1_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_rd6_ret_only_probe = dict(split_nba_comb_m_axi_if0_rd6_ret_only_probe_payload or {})
    split_nba_comb_m_axi_if0_rd6_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_rd6_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd6_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_rd6_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd6_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_rd6_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_rd6_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_rd6_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_rd7_ret_only_probe = dict(split_nba_comb_m_axi_if0_rd7_ret_only_probe_payload or {})
    split_nba_comb_m_axi_if0_rd7_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_rd7_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd7_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_rd7_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd7_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_rd7_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_rd7_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_rd7_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_rd7_trunc_ret_only_probe = dict(
        split_nba_comb_m_axi_if0_rd7_trunc_ret_only_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_rd7_trunc_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_rd7_trunc_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd7_trunc_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_rd7_trunc_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_rd7_trunc_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_rd7_trunc_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_log_text
    )
    split_nba_comb_m_axi_if0_ret_only_trunc_probe = dict(
        split_nba_comb_m_axi_if0_ret_only_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_ret_only_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_ret_only_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_ret_only_trunc_link_status = str(
        split_nba_comb_m_axi_if0_ret_only_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_ret_only_trunc_observations = dict(
        split_nba_comb_m_axi_if0_ret_only_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_ret_only_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_ret_only_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_ldptr_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_ldptr_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_ldptr_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_ldptr_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_ldptr_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_ldptr_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_ldptr_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_ldptr_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_probe.get("compile", {}).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_probe.get("link", {}).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_probe.get("compile", {}).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_probe.get("link", {}).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_probe.get("compile", {}).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_probe.get("link", {}).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_probe_payload
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_probe.get("compile", {}).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_probe.get("link", {}).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_probe.get("observations")
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_probe.get("compile", {}).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_probe.get("link", {}).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_probe.get("link", {}).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_probe.get("observations")
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_probe_payload
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_probe.get("link", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_probe.get("compile", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_probe.get("link", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_probe.get("observations")
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_probe.get("compile", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_probe.get("link", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_probe.get("observations")
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_probe.get("compile", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_probe.get("link", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_probe.get("observations")
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_probe_payload
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_probe.get("link", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_probe.get("observations")
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_probe.get("link", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_probe.get("link", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_probe.get("compile", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_probe.get("link", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_probe.get("observations")
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_probe_payload
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_probe.get(
            "link", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_probe.get(
            "observations"
        )
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_probe.get("link", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_probe.get("observations")
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_probe.get("link", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_probe.get("observations")
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_probe.get(
            "compile", {}
        ).get("status")
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_probe.get("link", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_probe.get("observations")
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_probe = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_compile_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_probe.get("compile", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_link_status = str(
        split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_probe.get("link", {}).get(
            "status"
        )
        or ""
    )
    split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_observations = dict(
        split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_probe.get("observations")
        or {}
    )
    split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke_log_text
    )
    split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe = dict(
        split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe_payload or {}
    )
    split_nba_comb_m_axi_if0_b64_imm1_ret_only_compile_status = str(
        split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_b64_imm1_ret_only_link_status = str(
        split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_m_axi_if0_b64_imm1_ret_only_observations = dict(
        split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe.get("observations") or {}
    )
    split_nba_comb_m_axi_if0_b64_imm1_ret_only_smoke = _smoke_status(
        split_nba_comb_m_axi_if0_b64_imm1_ret_only_smoke_log_text
    )
    split_nba_comb_prefix331_param_only_probe = dict(split_nba_comb_prefix331_param_only_probe_payload or {})
    split_nba_comb_prefix331_param_only_compile_status = str(
        split_nba_comb_prefix331_param_only_probe.get("compile", {}).get("status") or ""
    )
    split_nba_comb_prefix331_param_only_link_status = str(
        split_nba_comb_prefix331_param_only_probe.get("link", {}).get("status") or ""
    )
    split_nba_comb_prefix331_param_only_observations = dict(
        split_nba_comb_prefix331_param_only_probe.get("observations") or {}
    )
    split_nba_comb_prefix331_param_only_smoke = _smoke_status(split_nba_comb_prefix331_param_only_smoke_log_text)

    warning_lines = []
    if trial_ptxas_log_text:
        warning_lines = [
            line for line in trial_ptxas_log_text.splitlines() if "warning" in line.lower() or "error" in line.lower()
        ]
    warning_only = bool(warning_lines) and not any("error" in line.lower() and "warning" not in line.lower() for line in warning_lines)

    if official_cubin_exists:
        if cubin_smoke.get("status") == "ok":
            decision = {
                "status": "ready_to_finish_caliptra_first_trio",
                "reason": "caliptra_tls_bypass_reaches_a_built_gpu_module_on_the_checked-in_build_path",
                "recommended_next_tactic": "finish_caliptra_stock_hybrid_validation_and_compare_gate_policy",
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
            and split_launch_sequence
            and split_compile_only_probe_status == "ok"
            and split_compile_only_probe_output_exists
            and split_compile_only_zero_stack
            and split_nvcc_compile_status == "ok"
            and split_nvcc_link_status == "ok"
            and split_nvcc_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_compile_status == "ok"
            and split_nba_comb_prefix330_link_status == "ok"
            and split_nba_comb_prefix330_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_smoke.get("status") == "ok"
            and split_nba_comb_prefix331_compile_status == "ok"
            and split_nba_comb_prefix331_link_status == "ok"
            and split_nba_comb_prefix331_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_ret_only_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_only_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_ldptr_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ldptr_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_ldptr_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_first_store_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke.get("status")
            in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_observations.get("linked_exists")
            is True
            and split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke.get("status")
            == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_observations.get("linked_exists")
            is True
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke.get("status")
            in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_observations.get("linked_exists")
            is True
            and split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke.get("status")
            in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_observations.get("linked_exists")
            is True
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke.get("status")
            in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_observations.get("linked_exists")
            is True
            and split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke.get("status")
            in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_observations.get(
                "linked_exists"
            )
            is True
            and split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke.get(
                "status"
            )
            == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_observations.get(
                "linked_exists"
            )
            is True
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke.get("status")
            == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_observations.get(
                "linked_exists"
            )
            is True
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke.get("status")
            in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_compile_status == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_link_status == "skipped"
            and split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_observations.get("linked_exists")
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_compile_status
            == "timed_out"
            and split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_link_status
            == "skipped"
            and split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_observations.get(
                "linked_exists"
            )
            is False
            and split_nba_comb_m_axi_if0_b64_imm1_ret_only_compile_status == "timed_out"
            and split_nba_comb_prefix331_param_only_compile_status == "ok"
            and split_nba_comb_prefix331_param_only_link_status == "ok"
            and split_nba_comb_prefix331_param_only_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_param_only_smoke.get("status") == "ok"
        ):
            decision = {
                "status": (
                    "ready_for_deeper_caliptra_split_m_axi_if0_first_store_compilable_branch1_load_"
                    "provenance_nonconstant_loaded_byte_dependent_store_source_bits_runtime_fault_debug"
                ),
                "reason": (
                    "prefix330_runs_cleanly_and_prefix331_reproduces_the_fault_with_only_the_m_axi_if__0_"
                    "callseq_added,_while_the_param-only_variant,_the_no-arg_ret-only_helper_call,_"
                    "the_b64-zero_ret-only_helper_call,_and_truncated_after-callseq331_variants_that_"
                    "pass_synthetic_16,_%rd4,_%rd7,_%rd5_ret-only,_%rd5_ldptr-ret,_%rd5_high-"
                    "offset-load-ret,_and_the_first_branch_merge_variant_all_run_cleanly;_restoring_"
                    "only_the_first_store_reproduces_the_runtime_fault,_and_overwriting_the_store_"
                    "payload_with_constant_0_or_1_runs_cleanly;_the_branch1-only_first-store_variant_"
                    "that_loads_the_byte_from_%rd1+3130507_and_stores_it_still_reproduces_the_runtime_"
                    "fault,_the_corresponding_branch1-load_zero-store_variant_runs_cleanly,_but_"
                    "branch1-load_mask1,_branch1-predicated01,_branch1-selp-const1,_and_first-store-"
                    "masked-data_variants_still_fault,_while_a_dead-mask-const1_variant_that_keeps_the_"
                    "same_loaded_byte_live_but_overwrites_the_first_store_source_with_constant_1_runs_"
                    "cleanly,_but_an_analogous_masked-data-dead-mask-const1_variant_does_not_finish_"
                    "compile_within_the_same_budget,_while_a_same-register_dead-mask-zero_variant_does_not_finish_compile_within_"
                    "the_same_240s_probe_budget,_showing_that_constant-0_rewrites_already_fall_off_the_"
                    "current_compilable_line;_a_branch1-predicated10_variant_that_keeps_the_same_loaded-"
                    "byte-derived_predicate_shape_but_flips_the_0/1_arm_assignment_does_not_finish_"
                    "compile_within_the_same_budget;_a_branch1-selp-same-const1_variant_that_"
                    "keeps_predicate_flow_but_forces_the_full-width_store_source_bits_to_constant_1_"
                    "also_runs_cleanly,_while_a_branch1-selp-const2_variant_that_keeps_the_same_selp_"
                    "shape_but_a_same-register_branch1-selp-const1-and255_variant_that_clears_the_"
                    "upper_bits_again_before_the_store_does_not_finish_compile_within_the_same_budget;_"
                    "while_a_branch1-selp-const2_variant_that_keeps_the_same_selp_"
                    "shape_but_only_raises_the_alternate_arm_to_small_low-bit_constant_2_does_not_"
                    "finish_compile_within_the_same_budget;_while_a_branch1-selp-const3_variant_that_keeps_the_same_selp_"
                    "shape_but_only_raises_the_alternate_arm_to_small_low-bit_constant_3_does_not_"
                    "finish_compile_within_the_same_budget;_while_a_branch1-selp-const129_variant_that_keeps_the_same_selp_"
                    "shape_but_moves_the_alternate_arm_to_bit7-valued_constant_129_does_not_finish_"
                    "compile_within_the_same_budget;_while_a_branch1-selp-const257_variant_that_keeps_the_same_selp_"
                    "shape_but_flips_the_1/257_arm_assignment_does_not_finish_compile_within_the_same_budget;_"
                    "while_a_branch1-selp-const513_variant_that_keeps_the_same_selp_shape_but_moves_the_"
                    "alternate_arm_to_upper-byte-only_constant_513_does_not_finish_compile_within_the_same_"
                    "budget;_"
                    "while_a_branch1-selp-same-const257_variant_that_keeps_the_same_selp_shape_but_"
                    "pins_the_full-width_store_source_to_constant_0x0101_does_not_finish_compile_within_"
                    "the_same_budget;_"
                    "a_branch1-selp-const0_variant_that_keeps_predicate_flow_but_moves_all_dynamic_"
                    "dependence_into_the_upper_byte_does_not_finish_compile_within_the_same_budget;_"
                    "the_branch1-load-mask1-shl8_variant_still_faults,_showing_that_upper-byte-only_"
                    "arithmetic_dependence_also_reproduces_the_runtime_fault,_while_a_same-register_"
                    "branch1-load-mask1-shl8-and255_variant_that_clears_the_upper_bits_again_before_"
                    "the_store_does_not_finish_compile_within_the_same_budget,_and_even_nearer_"
                    "same-register_branch1-load-mask1-shl1,_mask1-shl4,_mask1-shl6,_mask1-shl7,_and_"
                    "mask1-shl9_variants_do_not_finish_compile_within_the_same_budget,_and_the_"
                    "corresponding_same-register_branch1-load-mask1-shr8_variant_also_does_not_finish_"
                    "compile_within_the_same_budget,_so_the_shift-family_runtime_line_has_collapsed_to_"
                    "mask1-shl8_only;_the_separate-temp_"
                    "branch1-load-mask1-shl8-sep-reg_variant_does_not_finish_"
                    "compile_within_the_same_budget;_a_semantically_similar_branch1-load-mask1-sep-reg_"
                    "variant_also_does_not_finish_compile_within_the_same_budget,_a_branch1-load-xor-"
                    "self-zero_variant_also_does_not_finish_compile_within_the_same_budget,_and_neither_"
                    "a_self-load/store_variant,_a_store-plus1_destination_variant,_nor_a_branch1-load-"
                    "mask1-or1_variant_that_arithmetic-constantizes_the_final_store_value_to_1_finishes_"
                    "compile_within_the_same_budget,_and_even_a_same-register_branch1-load-mask2_"
                    "variant_does_not_finish_compile_before_link;_the_corresponding_same-register_"
                    "branch1-load-maskff_variant_that_explicitly_clamps_the_loaded_byte_to_8_bits_"
                    "also_does_not_finish_compile_before_link;_a_narrower_same-register_branch1-load-"
                    "mask3_variant_also_does_not_finish_compile_before_link,_and_even_a_minimal_"
                    "branch1-load-mov-to-new-register_variant_does_not_finish_compile_before_link,_"
                    "so_the_non-actionable_side_now_covers_small_multi-bit_and_full-byte_same-register_"
                    "clamps_as_well_as_a_simple_nonconstant_source-register_handoff;_even_a_branch1_"
                    "alt-load_variant_that_"
                    "keeps_the_same_same-register_store_shape_but_swaps_the_loaded_byte_provenance_to_"
                    "%rd1+3130443_does_not_finish_compile_within_the_same_budget;_the_remaining_"
                    "actionable_repro_line_has_narrowed_to_compilable_current-branch1-load-provenance_"
                    "nonconstant_loaded-byte-dependent_first-store_source_bits_in_"
                    "m_axi_if__0_rather_than_mere_loaded-byte_consumption,_predicate_participation_"
                    "alone,_the_store_instruction_itself,_the_final_stored_byte_value,_a_branch1-only_"
                    "raw_byte_range,_a_constant-1_or_constant-0_same-register_rewrite,_an_explicit_"
                    "8-bit_or_small-multi-bit_same-register_clamp,_a_simple_source-register_move_"
                    "handoff,_an_alt-load-provenance_variant,_or_a_non-compiling_constant-foldable_"
                    "source-data_variant"
                ),
                "recommended_next_tactic": (
                    "deeper_caliptra_split_m_axi_if0_first_store_compilable_branch1_load_provenance_"
                    "nonconstant_loaded_byte_dependent_store_source_bits_runtime_fault_debug"
                ),
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
            and split_launch_sequence
            and split_compile_only_probe_status == "ok"
            and split_compile_only_probe_output_exists
            and split_compile_only_zero_stack
            and split_nvcc_compile_status == "ok"
            and split_nvcc_link_status == "ok"
            and split_nvcc_observations.get("linked_exists") is True
            and split_cubin_smoke.get("status") == "illegal_memory_access"
            and split_ico_smoke.get("status") == "ok"
            and split_nba_sequent_smoke.get("status") == "ok"
            and split_nba_comb_prefix330_compile_status == "ok"
            and split_nba_comb_prefix330_link_status == "ok"
            and split_nba_comb_prefix330_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_smoke.get("status") == "ok"
            and split_nba_comb_prefix331_compile_status == "ok"
            and split_nba_comb_prefix331_link_status == "ok"
            and split_nba_comb_prefix331_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_ret_only_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_only_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_ldptr_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ldptr_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_ldptr_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_first_store_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke.get("status")
            in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_observations.get("linked_exists")
            is True
            and split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke.get("status")
            == "ok"
            and split_nba_comb_m_axi_if0_b64_imm1_ret_only_compile_status == "timed_out"
            and split_nba_comb_prefix331_param_only_compile_status == "ok"
            and split_nba_comb_prefix331_param_only_link_status == "ok"
            and split_nba_comb_prefix331_param_only_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_param_only_smoke.get("status") == "ok"
        ):
            decision = {
                "status": "ready_for_deeper_caliptra_split_m_axi_if0_first_store_source_data_runtime_fault_debug",
                "reason": (
                    "prefix330_runs_cleanly_and_prefix331_reproduces_the_fault_with_only_the_m_axi_if__0_"
                    "callseq_added,_while_the_param-only_variant,_the_no-arg_ret-only_helper_call,_"
                    "the_b64-zero_ret-only_helper_call,_and_truncated_after-callseq331_variants_that_"
                    "pass_synthetic_16,_%rd4,_%rd7,_%rd5_ret-only,_%rd5_ldptr-ret,_%rd5_high-"
                    "offset-load-ret,_and_the_first_branch_merge_variant_all_run_cleanly;_restoring_"
                    "only_the_first_store_reproduces_the_runtime_fault,_but_first-store_variants_that_"
                    "overwrite_the_store_payload_with_constant_0_or_1_run_cleanly;_the_remaining_"
                    "actionable_repro_line_has_narrowed_to_the_computed_first-store_source-data_path_"
                    "in_m_axi_if__0_beyond_the_store_instruction_itself"
                ),
                "recommended_next_tactic": (
                    "deeper_caliptra_split_m_axi_if0_first_store_source_data_runtime_fault_debug"
                ),
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
            and split_launch_sequence
            and split_compile_only_probe_status == "ok"
            and split_compile_only_probe_output_exists
            and split_compile_only_zero_stack
            and split_nvcc_compile_status == "ok"
            and split_nvcc_link_status == "ok"
            and split_nvcc_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_compile_status == "ok"
            and split_nba_comb_prefix330_link_status == "ok"
            and split_nba_comb_prefix330_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_smoke.get("status") == "ok"
            and split_nba_comb_prefix331_compile_status == "ok"
            and split_nba_comb_prefix331_link_status == "ok"
            and split_nba_comb_prefix331_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_zero_high_offsets_compile_status == "ok"
            and split_nba_comb_m_axi_if0_zero_high_offsets_link_status == "ok"
            and split_nba_comb_m_axi_if0_zero_high_offsets_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_zero_high_offsets_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_ret_after_first_store_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_after_first_store_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_after_first_store_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_after_first_store_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_min_store_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_min_store_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_min_store_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_min_store_only_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_only_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_noarg_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_noarg_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_noarg_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_noarg_ret_only_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_rd3_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_rd3_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_rd3_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_rd3_ret_only_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_rd3_shr12_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_rd3_shr12_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_rd3_shr12_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke.get("status")
            in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_b64_synth16_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_b64_synth16_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_b64_synth16_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_rd4_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_rd4_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_rd4_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_rd4_ret_only_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_rd4_trunc_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_rd4_trunc_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_rd4_trunc_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_rd1_ret_only_compile_status == "timed_out"
            and split_nba_comb_m_axi_if0_rd6_ret_only_compile_status == "timed_out"
            and split_nba_comb_m_axi_if0_rd7_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_rd7_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_rd7_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_rd7_ret_only_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_rd7_trunc_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_rd7_trunc_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_rd7_trunc_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_ret_only_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_only_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_ldptr_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ldptr_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_ldptr_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_first_store_ret_trunc_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_ret_trunc_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_store_ret_trunc_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke.get("status") in RUNTIME_FAULT_STATUSES
            and split_nba_comb_m_axi_if0_b64_one_ret_only_compile_status == "timed_out"
            and split_nba_comb_m_axi_if0_b64_imm1_ret_only_compile_status == "timed_out"
            and split_nba_comb_prefix331_param_only_compile_status == "ok"
            and split_nba_comb_prefix331_param_only_link_status == "ok"
            and split_nba_comb_prefix331_param_only_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_param_only_smoke.get("status") == "ok"
        ):
            decision = {
                "status": "ready_for_deeper_caliptra_split_m_axi_if0_first_store_runtime_fault_debug",
                "reason": (
                    "prefix330_runs_cleanly_and_prefix331_reproduces_the_fault_with_only_the_m_axi_if__0_"
                    "callseq_added,_while_the_param-only_variant,_the_no-arg_ret-only_helper_call,_"
                    "the_b64-zero_ret-only_helper_call,_and_truncated_after-callseq331_variants_that_"
                    "pass_synthetic_16,_%rd4,_%rd7,_%rd5_ret-only,_%rd5_ldptr-ret,_%rd5_high-"
                    "offset-load-ret,_and_the_first_branch_merge_variant_all_run_cleanly_while_"
                    "restoring_only_the_first_store_reproduces_the_runtime_fault;_the_remaining_"
                    "actionable_repro_line_has_narrowed_to_the_first_store_path_in_m_axi_if__0_"
                    "beyond_the_first_branch_merge"
                ),
                "recommended_next_tactic": (
                    "deeper_caliptra_split_m_axi_if0_first_store_runtime_fault_debug"
                ),
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
            and split_launch_sequence
            and split_compile_only_probe_status == "ok"
            and split_compile_only_probe_output_exists
            and split_compile_only_zero_stack
            and split_nvcc_compile_status == "ok"
            and split_nvcc_link_status == "ok"
            and split_nvcc_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_compile_status == "ok"
            and split_nba_comb_prefix330_link_status == "ok"
            and split_nba_comb_prefix330_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_smoke.get("status") == "ok"
            and split_nba_comb_prefix331_compile_status == "ok"
            and split_nba_comb_prefix331_link_status == "ok"
            and split_nba_comb_prefix331_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_smoke.get("status") in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_zero_high_offsets_compile_status == "ok"
            and split_nba_comb_m_axi_if0_zero_high_offsets_link_status == "ok"
            and split_nba_comb_m_axi_if0_zero_high_offsets_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_zero_high_offsets_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_ret_after_first_store_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_after_first_store_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_after_first_store_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_after_first_store_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_min_store_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_min_store_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_min_store_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_min_store_only_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_only_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_noarg_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_noarg_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_noarg_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_noarg_ret_only_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_rd4_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_rd4_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_rd4_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_rd4_ret_only_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_rd1_ret_only_compile_status == "timed_out"
            and split_nba_comb_m_axi_if0_rd6_ret_only_compile_status == "timed_out"
            and split_nba_comb_m_axi_if0_rd7_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_rd7_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_rd7_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_rd7_ret_only_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_b64_one_ret_only_compile_status == "timed_out"
            and split_nba_comb_m_axi_if0_b64_imm1_ret_only_compile_status == "timed_out"
            and split_nba_comb_prefix331_param_only_compile_status == "ok"
            and split_nba_comb_prefix331_param_only_link_status == "ok"
            and split_nba_comb_prefix331_param_only_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_param_only_smoke.get("status") == "ok"
        ):
            decision = {
                "status": "ready_for_deeper_caliptra_split_m_axi_if0_compilable_live_nonzero_pointer_like_b64_arg_handoff_illegal_access_debug",
                "reason": (
                    "prefix330_runs_cleanly_and_prefix331_reproduces_the_fault_with_only_the_m_axi_if__0_"
                    "callseq_added,_while_the_param-only_variant,_the_no-arg_ret-only_helper_call,_and_"
                    "a_b64-zero_ret-only_helper_call_all_run_cleanly_while_both_the_pre-cvta_live_%rd4_"
                    "ret-only_helper_call_and_the_module-global_%rd7_ret-only_helper_call_still_fault,_"
                    "while_the_raw_%rd6_helper_call,_the_%rd1_live-value_probe,_and_small_nonzero_b64_"
                    "immediate_variants_all_time_out_at_compile-only,_so_the_remaining_actionable_repro_"
                    "line_has_narrowed_to_compilable_live_nonzero_pointer-like_b64_argument_handoffs_"
                    "into_m_axi_if__0"
                ),
                "recommended_next_tactic": (
                    "deeper_caliptra_split_m_axi_if0_compilable_live_nonzero_pointer_like_b64_arg_handoff_illegal_access_debug"
                ),
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
            and split_launch_sequence
            and split_compile_only_probe_status == "ok"
            and split_compile_only_probe_output_exists
            and split_compile_only_zero_stack
            and split_nvcc_compile_status == "ok"
            and split_nvcc_link_status == "ok"
            and split_nvcc_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_compile_status == "ok"
            and split_nba_comb_prefix330_link_status == "ok"
            and split_nba_comb_prefix330_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_smoke.get("status") == "ok"
            and split_nba_comb_prefix331_compile_status == "ok"
            and split_nba_comb_prefix331_link_status == "ok"
            and split_nba_comb_prefix331_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_smoke.get("status") in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_zero_high_offsets_compile_status == "ok"
            and split_nba_comb_m_axi_if0_zero_high_offsets_link_status == "ok"
            and split_nba_comb_m_axi_if0_zero_high_offsets_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_zero_high_offsets_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_ret_after_first_store_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_after_first_store_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_after_first_store_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_after_first_store_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_min_store_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_min_store_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_min_store_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_min_store_only_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_only_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_noarg_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_noarg_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_noarg_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_noarg_ret_only_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_rd4_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_rd4_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_rd4_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_rd4_ret_only_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_rd7_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_rd7_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_rd7_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_rd7_ret_only_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_prefix331_param_only_compile_status == "ok"
            and split_nba_comb_prefix331_param_only_link_status == "ok"
            and split_nba_comb_prefix331_param_only_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_param_only_smoke.get("status") == "ok"
        ):
            decision = {
                "status": "ready_for_deeper_caliptra_split_m_axi_if0_live_nonzero_pointer_like_b64_arg_handoff_illegal_access_debug",
                "reason": (
                    "prefix330_runs_cleanly_and_prefix331_reproduces_the_fault_with_only_the_m_axi_if__0_"
                    "callseq_added,_while_the_param-only_variant,_the_no-arg_ret-only_helper_call,_and_"
                    "a_b64-zero_ret-only_helper_call_all_run_cleanly_while_both_the_pre-cvta_live_%rd4_"
                    "ret-only_helper_call_and_the_module-global_%rd7_ret-only_helper_call_still_fault,_"
                    "so_the_remaining_blocker_has_narrowed_from_storage-specific_handoff_to_the_live_"
                    "nonzero_pointer-like_b64_argument_handoff_into_m_axi_if__0"
                ),
                "recommended_next_tactic": (
                    "deeper_caliptra_split_m_axi_if0_live_nonzero_pointer_like_b64_arg_handoff_illegal_access_debug"
                ),
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
            and split_launch_sequence
            and split_compile_only_probe_status == "ok"
            and split_compile_only_probe_output_exists
            and split_compile_only_zero_stack
            and split_nvcc_compile_status == "ok"
            and split_nvcc_link_status == "ok"
            and split_nvcc_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_compile_status == "ok"
            and split_nba_comb_prefix330_link_status == "ok"
            and split_nba_comb_prefix330_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_smoke.get("status") == "ok"
            and split_nba_comb_prefix331_compile_status == "ok"
            and split_nba_comb_prefix331_link_status == "ok"
            and split_nba_comb_prefix331_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_smoke.get("status") in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_zero_high_offsets_compile_status == "ok"
            and split_nba_comb_m_axi_if0_zero_high_offsets_link_status == "ok"
            and split_nba_comb_m_axi_if0_zero_high_offsets_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_zero_high_offsets_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_ret_after_first_store_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_after_first_store_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_after_first_store_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_after_first_store_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_min_store_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_min_store_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_min_store_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_min_store_only_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_only_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_noarg_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_noarg_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_noarg_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_noarg_ret_only_smoke.get("status") == "ok"
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke.get("status") == "ok"
            and split_nba_comb_prefix331_param_only_compile_status == "ok"
            and split_nba_comb_prefix331_param_only_link_status == "ok"
            and split_nba_comb_prefix331_param_only_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_param_only_smoke.get("status") == "ok"
        ):
            decision = {
                "status": "ready_for_deeper_caliptra_split_m_axi_if0_live_b64_arg_handoff_illegal_access_debug",
                "reason": (
                    "prefix330_runs_cleanly_and_prefix331_reproduces_the_fault_with_only_the_m_axi_if__0_"
                    "callseq_added,_while_the_param-only_variant,_the_no-arg_ret-only_helper_call,_and_"
                    "a_b64-zero_ret-only_helper_call_all_run_cleanly_so_the_remaining_blocker_has_"
                    "narrowed_to_the_live_%rd5_b64_argument_handoff_into_m_axi_if__0"
                ),
                "recommended_next_tactic": "deeper_caliptra_split_m_axi_if0_live_b64_arg_handoff_illegal_access_debug",
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
            and split_launch_sequence
            and split_compile_only_probe_status == "ok"
            and split_compile_only_probe_output_exists
            and split_compile_only_zero_stack
            and split_nvcc_compile_status == "ok"
            and split_nvcc_link_status == "ok"
            and split_nvcc_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_compile_status == "ok"
            and split_nba_comb_prefix330_link_status == "ok"
            and split_nba_comb_prefix330_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_smoke.get("status") == "ok"
            and split_nba_comb_prefix331_compile_status == "ok"
            and split_nba_comb_prefix331_link_status == "ok"
            and split_nba_comb_prefix331_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_smoke.get("status") in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_zero_high_offsets_compile_status == "ok"
            and split_nba_comb_m_axi_if0_zero_high_offsets_link_status == "ok"
            and split_nba_comb_m_axi_if0_zero_high_offsets_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_zero_high_offsets_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_ret_after_first_store_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_after_first_store_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_after_first_store_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_after_first_store_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_min_store_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_min_store_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_min_store_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_min_store_only_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_only_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_noarg_ret_only_compile_status == "ok"
            and split_nba_comb_m_axi_if0_noarg_ret_only_link_status == "ok"
            and split_nba_comb_m_axi_if0_noarg_ret_only_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_noarg_ret_only_smoke.get("status") == "ok"
            and split_nba_comb_prefix331_param_only_compile_status == "ok"
            and split_nba_comb_prefix331_param_only_link_status == "ok"
            and split_nba_comb_prefix331_param_only_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_param_only_smoke.get("status") == "ok"
        ):
            decision = {
                "status": "ready_for_deeper_caliptra_split_m_axi_if0_b64_arg_call_entry_abi_illegal_access_debug",
                "reason": (
                    "prefix330_runs_cleanly_and_prefix331_reproduces_the_fault_with_only_the_m_axi_if__0_"
                    "callseq_added,_while_both_the_param-only_variant_and_a_no-arg_ret-only_helper_call_"
                    "run_cleanly_so_the_remaining_blocker_has_narrowed_to_the_b64_argument-bearing_"
                    "call_entry_abi_into_m_axi_if__0"
                ),
                "recommended_next_tactic": "deeper_caliptra_split_m_axi_if0_b64_arg_call_entry_abi_illegal_access_debug",
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
            and split_launch_sequence
            and split_compile_only_probe_status == "ok"
            and split_compile_only_probe_output_exists
            and split_compile_only_zero_stack
            and split_nvcc_compile_status == "ok"
            and split_nvcc_link_status == "ok"
            and split_nvcc_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_compile_status == "ok"
            and split_nba_comb_prefix330_link_status == "ok"
            and split_nba_comb_prefix330_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_smoke.get("status") == "ok"
            and split_nba_comb_prefix331_compile_status == "ok"
            and split_nba_comb_prefix331_link_status == "ok"
            and split_nba_comb_prefix331_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_smoke.get("status") in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_zero_high_offsets_compile_status == "ok"
            and split_nba_comb_m_axi_if0_zero_high_offsets_link_status == "ok"
            and split_nba_comb_m_axi_if0_zero_high_offsets_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_zero_high_offsets_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_ret_after_first_store_compile_status == "ok"
            and split_nba_comb_m_axi_if0_ret_after_first_store_link_status == "ok"
            and split_nba_comb_m_axi_if0_ret_after_first_store_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_ret_after_first_store_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_compile_status == "ok"
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_link_status == "ok"
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_observations.get("linked_exists") is True
            and split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke.get("status")
            in {"illegal_memory_access", "unspecified_launch_failure"}
            and not (
                split_nba_comb_m_axi_if0_min_store_only_compile_status == "ok"
                and split_nba_comb_m_axi_if0_min_store_only_link_status == "ok"
                and split_nba_comb_m_axi_if0_min_store_only_observations.get("linked_exists") is True
                and split_nba_comb_m_axi_if0_min_store_only_smoke.get("status")
                in {"illegal_memory_access", "unspecified_launch_failure"}
                and split_nba_comb_m_axi_if0_ret_only_compile_status == "ok"
                and split_nba_comb_m_axi_if0_ret_only_link_status == "ok"
                and split_nba_comb_m_axi_if0_ret_only_observations.get("linked_exists") is True
                and split_nba_comb_m_axi_if0_ret_only_smoke.get("status")
                in {"illegal_memory_access", "unspecified_launch_failure"}
            )
        ):
            decision = {
                "status": "ready_for_deeper_caliptra_split_m_axi_if0_first_half_core_illegal_access_debug",
                "reason": (
                    "even_after_zeroing_the_m_axi_if__0_high-offset_loads_and_cutting_the_helper_after_"
                    "its_first_store_the_split_nba_comb_probe_still_reproduces_illegal_memory_access_"
                    "so_the_remaining_blocker_is_the_first-half_core_path_before_the_second_output"
                ),
                "recommended_next_tactic": "deeper_caliptra_split_m_axi_if0_first_half_core_illegal_access_debug",
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
            and split_launch_sequence
            and split_compile_only_probe_status == "ok"
            and split_compile_only_probe_output_exists
            and split_compile_only_zero_stack
            and split_nvcc_compile_status == "ok"
            and split_nvcc_link_status == "ok"
            and split_nvcc_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_compile_status == "ok"
            and split_nba_comb_prefix330_link_status == "ok"
            and split_nba_comb_prefix330_observations.get("linked_exists") is True
            and split_nba_comb_prefix330_smoke.get("status") == "ok"
            and split_nba_comb_prefix331_compile_status == "ok"
            and split_nba_comb_prefix331_link_status == "ok"
            and split_nba_comb_prefix331_observations.get("linked_exists") is True
            and split_nba_comb_prefix331_smoke.get("status") in {"illegal_memory_access", "unspecified_launch_failure"}
        ):
            decision = {
                "status": "ready_for_deeper_caliptra_split_m_axi_if0_illegal_access_debug",
                "reason": (
                    "the_zero-call_split_nba_comb_prefix_runs_cleanly_but_adding_only_the_first_"
                    "m_axi_if__0_callseq_reproduces_the_fault_so_the_current_blocker_has_narrowed_"
                    "to_the_initial_split_nba_comb_helper_path"
                ),
                "recommended_next_tactic": "deeper_caliptra_split_m_axi_if0_illegal_access_debug",
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
            and split_launch_sequence
            and split_compile_only_probe_status == "ok"
            and split_compile_only_probe_output_exists
            and split_compile_only_zero_stack
            and split_nvcc_compile_status == "ok"
            and split_nvcc_link_status == "ok"
            and split_nvcc_observations.get("linked_exists") is True
            and split_ico_smoke.get("status") == "ok"
            and split_nba_sequent_smoke.get("status") == "ok"
            and split_nba_comb_smoke.get("status") in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_block1_smoke.get("status") in {"illegal_memory_access", "unspecified_launch_failure"}
            and split_nba_comb_block8_smoke.get("status") in {"illegal_memory_access", "unspecified_launch_failure"}
        ):
            decision = {
                "status": "ready_for_deeper_caliptra_split_nba_comb_illegal_access_debug",
                "reason": (
                    "the_split_ico_and_nba_sequent_kernels_run_successfully_but_the_split_nba_comb_kernel_"
                    "still_fails_even_under_small_block_sizes_so_the_remaining_blocker_is_nba_comb_runtime"
                ),
                "recommended_next_tactic": "deeper_caliptra_split_nba_comb_illegal_access_debug",
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
            and split_launch_sequence
            and split_compile_only_probe_status == "ok"
            and split_compile_only_probe_output_exists
            and split_compile_only_zero_stack
            and split_nvcc_compile_status == "ok"
            and split_nvcc_link_status == "ok"
            and split_nvcc_observations.get("linked_exists") is True
            and split_cubin_smoke.get("status") == "illegal_memory_access"
        ):
            decision = {
                "status": "ready_for_deeper_caliptra_split_runtime_illegal_access_debug",
                "reason": (
                    "the_Caliptra_split-kernel_line_now_reaches_linked_cubin_load_kernel_resolution_"
                    "and_first_launch_so_the_remaining_blocker_is_runtime_illegal_memory_access"
                ),
                "recommended_next_tactic": "deeper_caliptra_split_runtime_illegal_access_debug",
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
            and split_launch_sequence
            and split_compile_only_probe_status == "ok"
            and split_compile_only_probe_output_exists
            and split_compile_only_zero_stack
            and split_nvcc_compile_status == "ok"
            and split_nvcc_link_status == "ok"
            and split_nvcc_observations.get("linked_exists") is True
        ):
            decision = {
                "status": "ready_to_debug_caliptra_split_cubin_runtime_after_link_recovery",
                "reason": (
                    "the_Caliptra_split-kernel_line_now_reaches_an_executable_linked_cubin_"
                    "so_the_next_blocker_has_moved_past_split_build_completion_and_into_runtime"
                ),
                "recommended_next_tactic": "deeper_caliptra_split_cubin_runtime_debug",
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
            and split_launch_sequence
            and split_compile_only_probe_status == "ok"
            and split_compile_only_probe_output_exists
            and split_compile_only_zero_stack
        ):
            decision = {
                "status": "ready_for_deeper_caliptra_split_kernel_executable_path_debug",
                "reason": (
                    "the_checked-in_Caliptra_single-kernel_cubin_is_stack-ceiling_blocked_"
                    "but_the_split-kernel_compile-only_probe_now_shows_zero-stack_entry_kernels_"
                    "so_the_next_blocker_is_the_split_executable_path"
                ),
                "recommended_next_tactic": "deeper_caliptra_split_kernel_executable_path_debug",
                "fallback_tactic": "open_example_fallback_family",
            }
        elif (
            cubin_smoke.get("status") == "stack_limit_invalid_argument"
            and max_accepted_stack_limit is not None
            and min_rejected_stack_limit_target is not None
            and launch_at_max_result.get("status") == "invalid_argument"
        ):
            decision = {
                "status": "ready_for_deeper_caliptra_kernel_stack_footprint_reduction_debug",
                "reason": (
                    "the_checked-in_Caliptra_cubin_requires_more_stack_than_the_driver_accepts_"
                    "and_still_fails_at_the_first_kernel_launch_even_at_the_maximum_accepted_stack_limit"
                ),
                "recommended_next_tactic": "deeper_caliptra_kernel_stack_footprint_reduction_debug",
                "fallback_tactic": "open_example_fallback_family",
            }
        elif cubin_smoke.get("status") == "stack_limit_invalid_argument":
            decision = {
                "status": "ready_for_deeper_caliptra_stack_limit_ceiling_debug",
                "reason": (
                    "caliptra_now_builds_a_checked-in_cubin_but_the_runtime_needs_a_stack_limit_"
                    "larger_than_the_driver_accepts_before_the_first_kernel_launch"
                ),
                "recommended_next_tactic": "deeper_caliptra_stack_limit_ceiling_debug",
                "fallback_tactic": "open_example_fallback_family",
            }
        else:
            decision = {
                "status": "ready_for_deeper_caliptra_launch_shape_runtime_debug",
                "reason": (
                    "caliptra_now_builds_a_checked-in_cubin_and_loads_it_successfully_but_the_traced_hybrid_run_"
                    "still_fails_at_or_immediately_after_the_first_kernel_launch"
                ),
                "recommended_next_tactic": "deeper_caliptra_launch_shape_runtime_debug",
                "fallback_tactic": "open_example_fallback_family",
            }
    elif (
        current_status == "decide_caliptra_tls_lowering_debug_vs_open_example_fallback"
        and blocker_kind == "nvptx_tls_lowering"
        and bypass_ll_exists
        and official_ptx_exists
        and compile_only_probe_status == "ok"
        and compile_only_probe_output_exists
        and compile_only_kernel_symbol_present is True
        and full_cubin_probe_status == "timed_out"
    ):
        decision = {
            "status": "ready_for_deeper_caliptra_full_cubin_completion_debug",
            "reason": (
                "the_checked-in_Caliptra_build_path_now_reaches_PTX_and_ptxas_compile-only_recovers_"
                "a_kernel-bearing_relocatable_object_but_a_bounded_full-cubin_probe_still_times_out"
            ),
            "recommended_next_tactic": "deeper_caliptra_full_cubin_completion_debug",
            "fallback_tactic": "open_example_fallback_family",
        }
    elif (
        current_status == "decide_caliptra_tls_lowering_debug_vs_open_example_fallback"
        and blocker_kind == "nvptx_tls_lowering"
        and bypass_ll_exists
        and official_ptx_exists
    ):
        decision = {
            "status": "prefer_deeper_caliptra_ptxas_cubin_debug_after_tls_bypass_recovered_ptx",
            "reason": (
                "the_checked-in_Caliptra_build_path_now_reaches_PTX_after_a_Verilated_TLS_slot_bypass_"
                "so_the_current_blocker_has_moved_past_llc_and_into_ptxas_or_cubin_completion"
            ),
            "recommended_next_tactic": "deeper_caliptra_ptxas_cubin_debug",
            "fallback_tactic": "open_example_fallback_family",
        }
    else:
        decision = {
            "status": "keep_caliptra_tls_lowering_debug_as_the_current_line",
            "reason": "the_available_Caliptra_artifacts_do_not_yet_prove_that_the_TLS_bypass_recovers_the_build_past_llc",
            "recommended_next_tactic": "offline_caliptra_tls_lowering_debug",
            "fallback_tactic": "open_example_fallback_family",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_caliptra_debug_tactics",
        "current_branch": {
            "caliptra_status": current_status or None,
            "gpu_build_status": gpu_build.get("status"),
            "gpu_blocker_kind": blocker_kind or None,
        },
        "observations": {
            "bypass_ll_exists": bypass_ll_exists,
            "official_ptx_exists": official_ptx_exists,
            "official_cubin_exists": official_cubin_exists,
            "compile_only_probe_status": compile_only_probe_status or None,
            "compile_only_probe_output_exists": compile_only_probe_output_exists,
            "compile_only_probe_output_size": compile_only_probe.get("output_size"),
            "compile_only_kernel_symbol_present": compile_only_kernel_symbol_present,
            "full_cubin_probe_status": full_cubin_probe_status or None,
            "full_cubin_probe_output_exists": bool(full_cubin_probe.get("output_exists")),
            "full_cubin_probe_output_size": full_cubin_probe.get("output_size"),
            "nvcc_device_link_cubin_probe_status": nvcc_device_link_cubin_probe_status or None,
            "nvcc_device_link_cubin_link_status": str(nvcc_device_link_cubin_probe.get("link", {}).get("status") or "") or None,
            "nvcc_device_link_fatbin_probe_status": nvcc_device_link_fatbin_probe_status or None,
            "nvcc_device_link_fatbin_link_status": str(nvcc_device_link_fatbin_probe.get("link", {}).get("status") or "") or None,
            "cubin_smoke_status": cubin_smoke.get("status"),
            "cubin_smoke_last_stage": cubin_smoke.get("last_stage"),
            "cubin_smoke_stack_limit_current": cubin_smoke.get("stack_limit_current"),
            "cubin_smoke_stack_limit_required": cubin_smoke.get("stack_limit_required"),
            "stack_limit_probe_max_accepted_stack_limit": max_accepted_stack_limit,
            "stack_limit_probe_min_rejected_stack_limit_target": min_rejected_stack_limit_target,
            "stack_limit_probe_launch_at_max_status": launch_at_max_result.get("status"),
            "stack_limit_probe_launch_at_max_last_stage": launch_at_max_result.get("last_stage"),
            "split_kernel_manifest_exists": bool(split_kernel_manifest),
            "split_launch_sequence": split_launch_sequence,
            "split_compile_only_probe_status": split_compile_only_probe_status or None,
            "split_compile_only_probe_output_exists": split_compile_only_probe_output_exists,
            "split_compile_only_probe_output_size": split_compile_only_probe.get("output_size"),
            "split_compile_only_zero_stack": split_compile_only_zero_stack,
            "split_smoke_status": split_smoke.get("status"),
            "split_smoke_last_stage": split_smoke.get("last_stage"),
            "split_nvcc_device_link_compile_status": split_nvcc_compile_status or None,
            "split_nvcc_device_link_link_status": split_nvcc_link_status or None,
            "split_nvcc_device_link_linked_exists": split_nvcc_observations.get("linked_exists"),
            "split_nvcc_device_link_linked_size": split_nvcc_observations.get("linked_size"),
            "split_nvcc_device_link_linked_kernel_symbol_present": split_nvcc_observations.get(
                "linked_kernel_symbol_present"
            ),
            "split_cubin_smoke_status": split_cubin_smoke.get("status"),
            "split_cubin_smoke_last_stage": split_cubin_smoke.get("last_stage"),
            "split_cubin_smoke_stack_limit_current": split_cubin_smoke.get("stack_limit_current"),
            "split_cubin_smoke_stack_limit_required": split_cubin_smoke.get("stack_limit_required"),
            "split_ico_smoke_status": split_ico_smoke.get("status"),
            "split_ico_smoke_last_stage": split_ico_smoke.get("last_stage"),
            "split_nba_comb_smoke_status": split_nba_comb_smoke.get("status"),
            "split_nba_comb_smoke_last_stage": split_nba_comb_smoke.get("last_stage"),
            "split_nba_comb_block1_smoke_status": split_nba_comb_block1_smoke.get("status"),
            "split_nba_comb_block1_smoke_last_stage": split_nba_comb_block1_smoke.get("last_stage"),
            "split_nba_comb_block8_smoke_status": split_nba_comb_block8_smoke.get("status"),
            "split_nba_comb_block8_smoke_last_stage": split_nba_comb_block8_smoke.get("last_stage"),
            "split_nba_sequent_smoke_status": split_nba_sequent_smoke.get("status"),
            "split_nba_sequent_smoke_last_stage": split_nba_sequent_smoke.get("last_stage"),
            "split_nba_comb_prefix330_compile_status": split_nba_comb_prefix330_compile_status or None,
            "split_nba_comb_prefix330_link_status": split_nba_comb_prefix330_link_status or None,
            "split_nba_comb_prefix330_linked_exists": split_nba_comb_prefix330_observations.get("linked_exists"),
            "split_nba_comb_prefix330_smoke_status": split_nba_comb_prefix330_smoke.get("status"),
            "split_nba_comb_prefix330_smoke_last_stage": split_nba_comb_prefix330_smoke.get("last_stage"),
            "split_nba_comb_prefix331_compile_status": split_nba_comb_prefix331_compile_status or None,
            "split_nba_comb_prefix331_link_status": split_nba_comb_prefix331_link_status or None,
            "split_nba_comb_prefix331_linked_exists": split_nba_comb_prefix331_observations.get("linked_exists"),
            "split_nba_comb_prefix331_smoke_status": split_nba_comb_prefix331_smoke.get("status"),
            "split_nba_comb_prefix331_smoke_last_stage": split_nba_comb_prefix331_smoke.get("last_stage"),
            "split_nba_comb_m_axi_if0_zero_high_offsets_compile_status": (
                split_nba_comb_m_axi_if0_zero_high_offsets_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_zero_high_offsets_link_status": (
                split_nba_comb_m_axi_if0_zero_high_offsets_link_status or None
            ),
            "split_nba_comb_m_axi_if0_zero_high_offsets_linked_exists": (
                split_nba_comb_m_axi_if0_zero_high_offsets_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_zero_high_offsets_smoke_status": (
                split_nba_comb_m_axi_if0_zero_high_offsets_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_zero_high_offsets_smoke_last_stage": (
                split_nba_comb_m_axi_if0_zero_high_offsets_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_ret_after_first_store_compile_status": (
                split_nba_comb_m_axi_if0_ret_after_first_store_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_ret_after_first_store_link_status": (
                split_nba_comb_m_axi_if0_ret_after_first_store_link_status or None
            ),
            "split_nba_comb_m_axi_if0_ret_after_first_store_linked_exists": (
                split_nba_comb_m_axi_if0_ret_after_first_store_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_ret_after_first_store_smoke_status": (
                split_nba_comb_m_axi_if0_ret_after_first_store_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_ret_after_first_store_smoke_last_stage": (
                split_nba_comb_m_axi_if0_ret_after_first_store_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_half_zero_high_offsets_compile_status": (
                split_nba_comb_m_axi_if0_first_half_zero_high_offsets_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_half_zero_high_offsets_link_status": (
                split_nba_comb_m_axi_if0_first_half_zero_high_offsets_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_half_zero_high_offsets_linked_exists": (
                split_nba_comb_m_axi_if0_first_half_zero_high_offsets_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_status": (
                split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_min_store_only_compile_status": (
                split_nba_comb_m_axi_if0_min_store_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_min_store_only_link_status": (
                split_nba_comb_m_axi_if0_min_store_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_min_store_only_linked_exists": (
                split_nba_comb_m_axi_if0_min_store_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_min_store_only_smoke_status": (
                split_nba_comb_m_axi_if0_min_store_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_min_store_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_min_store_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_ret_only_link_status": (
                split_nba_comb_m_axi_if0_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_noarg_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_noarg_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_noarg_ret_only_link_status": (
                split_nba_comb_m_axi_if0_noarg_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_noarg_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_noarg_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_noarg_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_noarg_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_noarg_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_noarg_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_b64_zero_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_b64_zero_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_b64_zero_ret_only_link_status": (
                split_nba_comb_m_axi_if0_b64_zero_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_b64_zero_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_b64_zero_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_b64_one_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_b64_one_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_b64_one_ret_only_link_status": (
                split_nba_comb_m_axi_if0_b64_one_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_b64_one_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_b64_one_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_b64_one_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_b64_one_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_b64_one_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_b64_one_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_rd3_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_rd3_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_rd3_ret_only_link_status": (
                split_nba_comb_m_axi_if0_rd3_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_rd3_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_rd3_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_rd3_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_rd3_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_rd3_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_rd3_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_rd3_shr12_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_rd3_shr12_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_rd3_shr12_ret_only_link_status": (
                split_nba_comb_m_axi_if0_rd3_shr12_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_rd3_shr12_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_rd3_shr12_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_link_status": (
                split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_link_status": (
                split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_b64_synth16_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_b64_synth16_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_b64_synth16_ret_only_link_status": (
                split_nba_comb_m_axi_if0_b64_synth16_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_b64_synth16_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_b64_synth16_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_link_status": (
                split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_rd4_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_rd4_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_rd4_ret_only_link_status": (
                split_nba_comb_m_axi_if0_rd4_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_rd4_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_rd4_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_rd4_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_rd4_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_rd4_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_rd4_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_rd4_trunc_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_rd4_trunc_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_rd4_trunc_ret_only_link_status": (
                split_nba_comb_m_axi_if0_rd4_trunc_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_rd4_trunc_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_rd4_trunc_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_rd1_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_rd1_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_rd1_ret_only_link_status": (
                split_nba_comb_m_axi_if0_rd1_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_rd1_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_rd1_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_rd1_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_rd1_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_rd1_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_rd1_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_rd6_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_rd6_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_rd6_ret_only_link_status": (
                split_nba_comb_m_axi_if0_rd6_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_rd6_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_rd6_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_rd6_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_rd6_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_rd6_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_rd6_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_rd7_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_rd7_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_rd7_ret_only_link_status": (
                split_nba_comb_m_axi_if0_rd7_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_rd7_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_rd7_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_rd7_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_rd7_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_rd7_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_rd7_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_rd7_trunc_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_rd7_trunc_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_rd7_trunc_ret_only_link_status": (
                split_nba_comb_m_axi_if0_rd7_trunc_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_rd7_trunc_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_rd7_trunc_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_ret_only_trunc_compile_status": (
                split_nba_comb_m_axi_if0_ret_only_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_ret_only_trunc_link_status": (
                split_nba_comb_m_axi_if0_ret_only_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_ret_only_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_ret_only_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_ret_only_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_ret_only_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_ret_only_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_ret_only_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_ldptr_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_ldptr_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_ldptr_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_ldptr_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_ldptr_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_ldptr_ret_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_ret_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_compile_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_link_status
                or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke.get(
                    "status"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke.get(
                    "last_stage"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_compile_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_link_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_link_status or None
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_linked_exists": (
                split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_observations.get(
                    "linked_exists"
                )
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke_status": (
                split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke_last_stage": (
                split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke.get("last_stage")
            ),
            "split_nba_comb_m_axi_if0_b64_imm1_ret_only_compile_status": (
                split_nba_comb_m_axi_if0_b64_imm1_ret_only_compile_status or None
            ),
            "split_nba_comb_m_axi_if0_b64_imm1_ret_only_link_status": (
                split_nba_comb_m_axi_if0_b64_imm1_ret_only_link_status or None
            ),
            "split_nba_comb_m_axi_if0_b64_imm1_ret_only_linked_exists": (
                split_nba_comb_m_axi_if0_b64_imm1_ret_only_observations.get("linked_exists")
            ),
            "split_nba_comb_m_axi_if0_b64_imm1_ret_only_smoke_status": (
                split_nba_comb_m_axi_if0_b64_imm1_ret_only_smoke.get("status")
            ),
            "split_nba_comb_m_axi_if0_b64_imm1_ret_only_smoke_last_stage": (
                split_nba_comb_m_axi_if0_b64_imm1_ret_only_smoke.get("last_stage")
            ),
            "split_nba_comb_prefix331_param_only_compile_status": (
                split_nba_comb_prefix331_param_only_compile_status or None
            ),
            "split_nba_comb_prefix331_param_only_link_status": (
                split_nba_comb_prefix331_param_only_link_status or None
            ),
            "split_nba_comb_prefix331_param_only_linked_exists": (
                split_nba_comb_prefix331_param_only_observations.get("linked_exists")
            ),
            "split_nba_comb_prefix331_param_only_smoke_status": (
                split_nba_comb_prefix331_param_only_smoke.get("status")
            ),
            "split_nba_comb_prefix331_param_only_smoke_last_stage": (
                split_nba_comb_prefix331_param_only_smoke.get("last_stage")
            ),
            "trial_ptx_exists": trial_ptx_exists,
            "trial_ptxas_warning_only": warning_only,
            "trial_ptxas_warning_lines": warning_lines[-8:],
        },
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--caliptra-status-json", type=Path, default=DEFAULT_CALIPTRA_STATUS_JSON)
    parser.add_argument("--bypass-ll", type=Path, default=DEFAULT_BYPASS_LL)
    parser.add_argument("--official-ptx", type=Path, default=DEFAULT_OFFICIAL_PTX)
    parser.add_argument("--official-cubin", type=Path, default=DEFAULT_OFFICIAL_CUBIN)
    parser.add_argument("--compile-only-probe-json", type=Path, default=DEFAULT_COMPILE_ONLY_PROBE_JSON)
    parser.add_argument("--full-cubin-probe-json", type=Path, default=DEFAULT_FULL_CUBIN_PROBE_JSON)
    parser.add_argument("--nvcc-device-link-cubin-probe-json", type=Path, default=DEFAULT_NVCC_DEVICE_LINK_CUBIN_PROBE_JSON)
    parser.add_argument("--nvcc-device-link-fatbin-probe-json", type=Path, default=DEFAULT_NVCC_DEVICE_LINK_FATBIN_PROBE_JSON)
    parser.add_argument("--compile-only-object", type=Path, default=DEFAULT_COMPILE_ONLY_OBJECT)
    parser.add_argument("--cubin-smoke-log", type=Path, default=DEFAULT_CUBIN_SMOKE_LOG)
    parser.add_argument("--stack-limit-probe-json", type=Path, default=DEFAULT_STACK_LIMIT_PROBE_JSON)
    parser.add_argument("--trial-ptx", type=Path, default=DEFAULT_TRIAL_PTX)
    parser.add_argument("--trial-ptxas-log", type=Path, default=DEFAULT_TRIAL_PTXAS_LOG)
    parser.add_argument("--split-kernel-manifest", type=Path, default=DEFAULT_SPLIT_KERNEL_MANIFEST)
    parser.add_argument("--split-compile-only-probe-json", type=Path, default=DEFAULT_SPLIT_COMPILE_ONLY_PROBE_JSON)
    parser.add_argument("--split-smoke-log", type=Path, default=DEFAULT_SPLIT_SMOKE_LOG)
    parser.add_argument("--split-nvcc-device-link-probe-json", type=Path, default=DEFAULT_SPLIT_NVCC_DEVICE_LINK_PROBE_JSON)
    parser.add_argument("--split-cubin-smoke-log", type=Path, default=DEFAULT_SPLIT_CUBIN_SMOKE_LOG)
    parser.add_argument("--split-ico-smoke-log", type=Path, default=DEFAULT_SPLIT_ICO_SMOKE_LOG)
    parser.add_argument("--split-nba-comb-smoke-log", type=Path, default=DEFAULT_SPLIT_NBA_COMB_SMOKE_LOG)
    parser.add_argument("--split-nba-comb-block1-smoke-log", type=Path, default=DEFAULT_SPLIT_NBA_COMB_BLOCK1_SMOKE_LOG)
    parser.add_argument("--split-nba-comb-block8-smoke-log", type=Path, default=DEFAULT_SPLIT_NBA_COMB_BLOCK8_SMOKE_LOG)
    parser.add_argument("--split-nba-sequent-smoke-log", type=Path, default=DEFAULT_SPLIT_NBA_SEQUENT_SMOKE_LOG)
    parser.add_argument("--split-nba-comb-prefix330-probe-json", type=Path, default=DEFAULT_SPLIT_NBA_COMB_PREFIX330_PROBE_JSON)
    parser.add_argument("--split-nba-comb-prefix330-smoke-log", type=Path, default=DEFAULT_SPLIT_NBA_COMB_PREFIX330_SMOKE_LOG)
    parser.add_argument("--split-nba-comb-prefix331-probe-json", type=Path, default=DEFAULT_SPLIT_NBA_COMB_PREFIX331_PROBE_JSON)
    parser.add_argument("--split-nba-comb-prefix331-smoke-log", type=Path, default=DEFAULT_SPLIT_NBA_COMB_PREFIX331_SMOKE_LOG)
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-zero-high-offsets-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_ZERO_HIGH_OFFSETS_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-zero-high-offsets-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_ZERO_HIGH_OFFSETS_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-ret-after-first-store-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RET_AFTER_FIRST_STORE_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-ret-after-first-store-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RET_AFTER_FIRST_STORE_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-half-zero-high-offsets-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_HALF_ZERO_HIGH_OFFSETS_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-half-zero-high-offsets-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_HALF_ZERO_HIGH_OFFSETS_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-min-store-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_MIN_STORE_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-min-store-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_MIN_STORE_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-noarg-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_NOARG_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-noarg-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_NOARG_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-b64-zero-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_ZERO_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-b64-zero-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_ZERO_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-b64-one-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_ONE_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-b64-one-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_ONE_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd3-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd3-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd3-shr12-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_SHR12_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd3-shr12-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_SHR12_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd3-small-nonzero-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_SMALL_NONZERO_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd3-small-nonzero-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_SMALL_NONZERO_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd3-small-aligned-nonzero-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_SMALL_ALIGNED_NONZERO_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd3-small-aligned-nonzero-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD3_SMALL_ALIGNED_NONZERO_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-b64-synth16-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_SYNTH16_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-b64-synth16-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_SYNTH16_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-b64-synth16-trunc-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_SYNTH16_TRUNC_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-b64-synth16-trunc-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_SYNTH16_TRUNC_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd4-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD4_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd4-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD4_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd4-trunc-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD4_TRUNC_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd4-trunc-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD4_TRUNC_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd1-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD1_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd1-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD1_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd6-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD6_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd6-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD6_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd7-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD7_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd7-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD7_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd7-trunc-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD7_TRUNC_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-rd7-trunc-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RD7_TRUNC_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-ret-only-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RET_ONLY_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-ret-only-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_RET_ONLY_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-ldptr-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_LDPTR_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-ldptr-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_LDPTR_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-high-offset-load-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_HIGH_OFFSET_LOAD_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-high-offset-load-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_HIGH_OFFSET_LOAD_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-branch-merge-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_BRANCH_MERGE_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-branch-merge-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_BRANCH_MERGE_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-zero-data-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_ZERO_DATA_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-zero-data-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_ZERO_DATA_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-one-data-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_ONE_DATA_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-one-data-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_ONE_DATA_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mov-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MOV_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mov-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MOV_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-zero-store-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_ZERO_STORE_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-zero-store-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_ZERO_STORE_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-predicated01-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_PREDICATED01_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-predicated01-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_PREDICATED01_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-predicated11-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_PREDICATED11_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-predicated11-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_PREDICATED11_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-predicated10-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_PREDICATED10_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-predicated10-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_PREDICATED10_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const1-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST1_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const1-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST1_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const1-and255-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST1_AND255_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const1-and255-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST1_AND255_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const2-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST2_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const2-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST2_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const3-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST3_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const3-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST3_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const129-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST129_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const129-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST129_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const257-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST257_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const257-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST257_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const513-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST513_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const513-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST513_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const0-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST0_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-const0-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_CONST0_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-dead-mask-const1-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_DEAD_MASK_CONST1_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-dead-mask-const1-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_DEAD_MASK_CONST1_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-selp-same-const1-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_SELP_SAME_CONST1_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-selp-same-const1-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_SELP_SAME_CONST1_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-mask1-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_MASK1_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-mask1-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_MASK1_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-predicated01-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_PREDICATED01_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-predicated01-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_PREDICATED01_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-force-else-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_FORCE_ELSE_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-force-else-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_FORCE_ELSE_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-selp-const1-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_SELP_CONST1_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-selp-const1-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_SELP_CONST1_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-mask1-shl8-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_MASK1_SHL8_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-masked-data-mask1-shl8-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_MASKED_DATA_MASK1_SHL8_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-dead-mask-const1-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_DEAD_MASK_CONST1_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-dead-mask-const1-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_DEAD_MASK_CONST1_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-dead-mask-zero-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_DEAD_MASK_ZERO_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-dead-mask-zero-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_DEAD_MASK_ZERO_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-same-const1-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_SAME_CONST1_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-same-const1-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_SAME_CONST1_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-same-const257-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_SAME_CONST257_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-selp-same-const257-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_SELP_SAME_CONST257_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl8-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL8_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl8-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL8_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl8-and255-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL8_AND255_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl8-and255-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL8_AND255_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl1-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL1_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl1-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL1_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl4-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL4_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl4-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL4_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl6-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL6_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl6-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL6_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl7-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL7_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl7-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL7_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl9-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL9_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl9-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL9_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shr8-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHR8_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shr8-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHR8_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl8-sep-reg-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL8_SEP_REG_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-shl8-sep-reg-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SHL8_SEP_REG_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-sep-reg-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SEP_REG_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-sep-reg-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_SEP_REG_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-xor-self-zero-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_XOR_SELF_ZERO_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-xor-self-zero-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_XOR_SELF_ZERO_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-self-load-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_SELF_LOAD_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-self-load-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_SELF_LOAD_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-store-plus1-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_STORE_PLUS1_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-store-plus1-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_STORE_PLUS1_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-or1-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_OR1_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask1-or1-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK1_OR1_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask2-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK2_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask2-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK2_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-maskff-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASKFF_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-maskff-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASKFF_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask3-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK3_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-load-mask3-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_LOAD_MASK3_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-alt-load-ret-trunc-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_ALT_LOAD_RET_TRUNC_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-first-store-branch1-alt-load-ret-trunc-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_FIRST_STORE_BRANCH1_ALT_LOAD_RET_TRUNC_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-b64-imm1-ret-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_IMM1_RET_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-m-axi-if0-b64-imm1-ret-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_M_AXI_IF0_B64_IMM1_RET_ONLY_SMOKE_LOG,
    )
    parser.add_argument(
        "--split-nba-comb-prefix331-param-only-probe-json",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_PREFIX331_PARAM_ONLY_PROBE_JSON,
    )
    parser.add_argument(
        "--split-nba-comb-prefix331-param-only-smoke-log",
        type=Path,
        default=DEFAULT_SPLIT_NBA_COMB_PREFIX331_PARAM_ONLY_SMOKE_LOG,
    )
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_status(
        caliptra_status_payload=_read_json(args.caliptra_status_json.resolve()),
        bypass_ll_exists=args.bypass_ll.resolve().is_file(),
        official_ptx_exists=args.official_ptx.resolve().is_file(),
        official_cubin_exists=args.official_cubin.resolve().is_file(),
        compile_only_probe_payload=_read_json_if_exists(args.compile_only_probe_json.resolve()),
        full_cubin_probe_payload=_read_json_if_exists(args.full_cubin_probe_json.resolve()),
        nvcc_device_link_cubin_probe_payload=_read_json_if_exists(args.nvcc_device_link_cubin_probe_json.resolve()),
        nvcc_device_link_fatbin_probe_payload=_read_json_if_exists(args.nvcc_device_link_fatbin_probe_json.resolve()),
        compile_only_kernel_symbol_present=_symbol_present(
            args.compile_only_object.resolve(),
            "vl_eval_batch_gpu",
        ),
        cubin_smoke_log_text=_read_text_if_exists(args.cubin_smoke_log.resolve()),
        stack_limit_probe_payload=_read_json_if_exists(args.stack_limit_probe_json.resolve()),
        trial_ptx_exists=args.trial_ptx.resolve().is_file(),
        trial_ptxas_log_text=_read_text_if_exists(args.trial_ptxas_log.resolve()),
        split_kernel_manifest_payload=_read_json_if_exists(args.split_kernel_manifest.resolve()),
        split_compile_only_probe_payload=_read_json_if_exists(args.split_compile_only_probe_json.resolve()),
        split_smoke_log_text=_read_text_if_exists(args.split_smoke_log.resolve()),
        split_nvcc_device_link_probe_payload=_read_json_if_exists(args.split_nvcc_device_link_probe_json.resolve()),
        split_cubin_smoke_log_text=_read_text_if_exists(args.split_cubin_smoke_log.resolve()),
        split_ico_smoke_log_text=_read_text_if_exists(args.split_ico_smoke_log.resolve()),
        split_nba_comb_smoke_log_text=_read_text_if_exists(args.split_nba_comb_smoke_log.resolve()),
        split_nba_comb_block1_smoke_log_text=_read_text_if_exists(args.split_nba_comb_block1_smoke_log.resolve()),
        split_nba_comb_block8_smoke_log_text=_read_text_if_exists(args.split_nba_comb_block8_smoke_log.resolve()),
        split_nba_sequent_smoke_log_text=_read_text_if_exists(args.split_nba_sequent_smoke_log.resolve()),
        split_nba_comb_prefix330_probe_payload=_read_json_if_exists(args.split_nba_comb_prefix330_probe_json.resolve()),
        split_nba_comb_prefix330_smoke_log_text=_read_text_if_exists(args.split_nba_comb_prefix330_smoke_log.resolve()),
        split_nba_comb_prefix331_probe_payload=_read_json_if_exists(args.split_nba_comb_prefix331_probe_json.resolve()),
        split_nba_comb_prefix331_smoke_log_text=_read_text_if_exists(args.split_nba_comb_prefix331_smoke_log.resolve()),
        split_nba_comb_m_axi_if0_zero_high_offsets_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_zero_high_offsets_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_zero_high_offsets_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_ret_after_first_store_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_ret_after_first_store_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_ret_after_first_store_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_half_zero_high_offsets_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_min_store_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_min_store_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_min_store_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_min_store_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_noarg_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_noarg_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_noarg_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_noarg_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_b64_zero_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_b64_zero_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_b64_one_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_b64_one_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_b64_one_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_b64_one_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_rd3_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_rd3_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_rd3_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_rd3_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_rd3_shr12_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_rd3_shr12_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_rd3_shr12_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_b64_synth16_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_b64_synth16_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_rd4_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_rd4_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_rd4_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_rd4_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_rd4_trunc_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_rd4_trunc_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_rd1_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_rd1_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_rd1_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_rd1_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_rd6_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_rd6_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_rd6_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_rd6_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_rd7_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_rd7_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_rd7_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_rd7_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_rd7_trunc_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_rd7_trunc_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_ret_only_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_ret_only_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_ret_only_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_ret_only_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_ldptr_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_ldptr_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_ldptr_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_high_offset_load_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mov_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_predicated01_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_predicated11_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_predicated10_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const1_and255_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const2_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const3_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const129_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const257_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const513_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_const0_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_dead_mask_const1_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_selp_same_const1_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_mask1_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_predicated01_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_force_else_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_selp_const1_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_masked_data_mask1_shl8_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_const1_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_dead_mask_zero_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const1_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_selp_same_const257_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_and255_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl1_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl4_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl6_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl7_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl9_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shr8_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_sep_reg_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_xor_self_zero_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_self_load_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_store_plus1_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask1_or1_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask2_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_maskff_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_load_mask3_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_first_store_branch1_alt_load_ret_trunc_smoke_log.resolve()
        ),
        split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_m_axi_if0_b64_imm1_ret_only_probe_json.resolve()
        ),
        split_nba_comb_m_axi_if0_b64_imm1_ret_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_m_axi_if0_b64_imm1_ret_only_smoke_log.resolve()
        ),
        split_nba_comb_prefix331_param_only_probe_payload=_read_json_if_exists(
            args.split_nba_comb_prefix331_param_only_probe_json.resolve()
        ),
        split_nba_comb_prefix331_param_only_smoke_log_text=_read_text_if_exists(
            args.split_nba_comb_prefix331_param_only_smoke_log.resolve()
        ),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
