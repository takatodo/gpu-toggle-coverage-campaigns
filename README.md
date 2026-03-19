# GPU Toggle Coverage Campaigns

GPU-accelerated RTL toggle coverage collection, rule management, and multi-design expansion using [RTLMeter](https://github.com/googleresearch/rtlmeter).

## Overview

This repository contains the frozen canonical artifacts for a GPU-accelerated toggle coverage campaign targeting multiple open-source RTL designs. The core output is a **generic rule family** — a set of per-design toggle coverage configurations validated across OpenTitan, VeeR, XuanTie, XiangShan, BlackParrot, OpenPiton, and Vortex — plus the tooling to run, validate, and extend them.

## Frozen Rule Families

| Rule | Anchor Design | Backend | nstates |
|------|--------------|---------|--------:|
| `deep_fifo_source` | tlul_fifo_async | source | 512 |
| `compact_socket_source` | tlul_socket_1n | source | 256 |
| `mixed_source_campaign_circt_multistep` | tlul_socket_m1, xbar_peri | source + circt-cubin | 512 |
| `dense_xbar_circt` | xbar_main | circt-cubin | 512 |
| `balanced_source_general` | tlul_fifo_sync, tlul_err, tlul_request_loopback | source | 512 |

Status: `scope_limited_final_freeze` — supported by OpenTitan slice validation, Tier-1/2 A/B/C evidence, and late-family `gpu_cov_gate` prechecks on VeeR and XuanTie.

## Repository Structure

### Read First

| File | Purpose |
|------|---------|
| `metrics_driven_final_rule_packet.md` | Frozen rule packet with full validation evidence |
| `toggle_coverage_generic_rules.md` | Rule family table and defaults |
| `generic_toggle_coverage_rule_plan.md` | High-level plan and current status |
| `runtime_runner_scope.md` | Mainline runners vs. scoped-out debug paths |
| `design_scope_expansion_packet.md` | Next design expansion order |

### Mainline Runners

| Script | Purpose |
|--------|---------|
| `run_rtlmeter_gpu_toggle_baseline.py` | GPU baseline runner (defaults to direct bench reuse) |
| `run_rtlmeter_design_rule_guided_sweep.py` | Rule-guided GPU sweep with device-aware batching |
| `run_veer_family_gpu_toggle_validation.py` | VeeR family (EL2/EH1/EH2) gpu_cov_gate validation |
| `run_xuantie_family_gpu_toggle_validation.py` | XuanTie family (C906/C910/E902/E906) gpu_cov_gate validation |
| `run_toggle_coverage_rule_guided_sweep.py` | Generic toggle coverage rule-guided sweep |

### Canonical Generators

Scripts that regenerate the frozen artifacts from source data:

| Script | Regenerates |
|--------|-------------|
| `freeze_metrics_driven_final_rule_packet.py` | Final frozen rule packet |
| `derive_toggle_coverage_generic_rules.py` | Generic rule family table |
| `freeze_design_scope_expansion.py` | Scope expansion order |
| `freeze_runtime_runner_scope.py` | Runtime runner boundary |
| `derive_rtlmeter_design_toggle_rule_assignments.py` | Per-design rule assignments |
| `extract_rtlmeter_design_toggle_features.py` | Per-design feature rows |
| `assess_rtlmeter_design_gpu_toggle_candidates.py` | Candidate ranking across designs |

### Cross-Design Validation

| File | Purpose |
|------|---------|
| `rtlmeter_design_generic_rule_validation.md` | Actual GPU and late-family gate validation summary |
| `rtlmeter_design_gpu_toggle_candidates.md` | Candidate ranking across RTLMeter designs |
| `rtlmeter_design_toggle_features.md` | Per-design feature and readiness breakdown |
| `metrics_driven_gpu_validation_matrix.md` | Tiered A/B/C validation matrix |

### OpenTitan Slice Artifacts

| File | Purpose |
|------|---------|
| `opentitan_tlul_slice_production_defaults.md` | Frozen production defaults per slice |
| `opentitan_tlul_slice_backend_selection.md` | Backend selection result (CIRCT vs. Verilator) |
| `opentitan_tlul_slice_convergence_freeze.md` | Convergence freeze used by rule derivation |
| `opentitan_tlul_slice_cpu_vs_gpu_campaign_efficiency.md` | CPU/GPU campaign efficiency comparison |

### Family Readiness

Per-design bring-up status and validation evidence:
`veer_family`, `veer_el2`, `xuantie_family`, `vortex`, `xiangshan`, `blackparrot`

## Design Coverage Status

| Design | Family | Validation | Rule |
|--------|--------|-----------|------|
| VeeR-EL2/EH1/EH2 | VeeR | gate_validated | balanced_source_general |
| XuanTie-E902/E906 | XuanTie | actual_gpu (18/18) | balanced_source_general |
| XuanTie-C906/C910 | XuanTie | actual_gpu | balanced_source_general |
| Vortex | Tier-2 | actual_gpu | balanced_source_general |
| XiangShan | Fallback | actual_gpu | balanced_source_general |
| BlackParrot | Fallback | actual_gpu | balanced_source_general |
| OpenPiton | Fallback | actual_gpu | balanced_source_general |
| OpenTitan | Slice scope | slice_scope_validated | (per-slice) |
| Caliptra | Phase 4 | gpu_cov_codegen_proven | TBD |

## Next Expansion

The next bring-up target after the current frozen scope is **Caliptra** (phase 4, large integration design). See `design_scope_expansion_packet.md` for the full ordered list.

## Prerequisites

- [RTLMeter](https://github.com/googleresearch/rtlmeter)
- GPU with ROCm or CUDA support
- Python 3.10+
