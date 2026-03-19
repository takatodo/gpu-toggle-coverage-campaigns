# Vortex GPU Toggle Readiness

- Design: `Vortex`
- Configuration: `gpu_cov`
- Readiness: `tier2_abc_completed_rule_freeze_pending`
- Weakest point: `Vortex gpu_cov` is no longer blocked on wrapper existence or zero observability. The fixed-test `sgemm` Tier-2 packet now runs under `A/B/C` with nonzero GPU-side `real_toggle_subset` words. The next question is whether the remaining partial memory-path regions are already sufficient for provisional rule freeze, or whether one more medium-design / region-budget refinement pass is needed first.

## Validated

- Descriptor now includes a dedicated `gpu_cov` configuration:
  - [descriptor.yaml](~/GEM_try/rtlmeter/designs/Vortex/descriptor.yaml)
- First-pass `gpu_cov` wrapper exists:
  - [vortex_gpu_cov_tb.sv](~/GEM_try/rtlmeter/designs/Vortex/src/vortex_gpu_cov_tb.sv)
- Coarse coverage manifest exists:
  - [vortex_gpu_cov_coverage_regions.json](~/GEM_try/rtlmeter/designs/Vortex/tests/vortex_gpu_cov_coverage_regions.json)
- Direct RTLMeter smoke passes for `Vortex:gpu_cov:hello`:
  - `/tmp/rtlmeter_vortex_gpu_cov_smoke_v5`
- Shared generic gpu-toggle baseline now also passes for `Vortex:gpu_cov:hello`:
  - `/tmp/vortex_gpu_cov_baseline_cpu_smoke_v2/summary.json`
- Shared generic gpu-toggle baseline now also passes for `Vortex:gpu_cov:sgemm` on both CPU and GPU paths:
  - `/tmp/vortex_gpu_cov_sgemm_cpu_probe_v2/summary.json`
  - `/tmp/vortex_gpu_cov_sgemm_gpu_probe_v4/summary.json`
- Candidate ranking now classifies `Vortex` as `ready_for_gpu_toggle`:
  - [rtlmeter_design_gpu_toggle_candidates.json](./rtlmeter_design_gpu_toggle_candidates.json)
- Feature extraction now classifies `Vortex` as `wrapper_ready_core`:
  - [rtlmeter_design_toggle_features.json](./rtlmeter_design_toggle_features.json)
- Rule assignment now exists for `Vortex:gpu_cov`:
  - [rtlmeter_design_toggle_rule_assignments.json](./rtlmeter_design_toggle_rule_assignments.json)
- Tier-2 fixed-test `A/B/C` entrypoint is prepared:
  - [run_tier2_vortex_abc.py](./run_tier2_vortex_abc.py)
  - `/tmp/metrics_driven_t2_exec_v2/vortex_abc_manifest.json`
- Tier-2 fixed-test `A/B/C` evidence now exists on the assigned `sgemm` workload:
  - `A`: `/tmp/metrics_driven_t2_exec_v2/A_cpu_baseline/summary.json`
  - `B`: `/tmp/metrics_driven_t2_exec_v2/B_gpu_metrics_only/summary.json`
  - `C`: `/tmp/metrics_driven_t2_exec_v2/C_gpu_guided/summary.json`
- The second standard workload now also has fixed-test `A/B/C` evidence:
  - `A`: `/tmp/metrics_driven_t2_exec_v3_saxpy/A_cpu_baseline/summary.json`
  - `B`: `/tmp/metrics_driven_t2_exec_v3_saxpy/B_gpu_metrics_only/summary.json`
  - `C`: `/tmp/metrics_driven_t2_exec_v3_saxpy/C_gpu_guided/summary.json`
- The GPU observability fix is now effective on `sgemm`:
  - nonzero `real_toggle_subset` words are present on the GPU compact path
  - all three flows reach the same `10/18` coverage-point result
  - `dead_region_count=0`, with `control_progress` and `dcr_programming` active and `mem_request_path` / `mem_response_path` partial
- `saxpy` reproduces the same `10/18` packet and the same GPU compact SHA as `sgemm`, which confirms flow stability across the second standard workload name but does not widen the active region set.
- At the current fixed test, `B/C` each land near `0.53s` wall-clock while `A` is `3.50s`.

## Current blocker

- Tier-2 evidence now exists as comparable `A/B/C` summaries, so the blocker is no longer wrapper readiness and no longer zero observability.
- Warm-cache runtime reuse is now also validated:
  - wrapper probe: `/tmp/runtime_log_job/vortex_t2_B_sgemm/runtime_summary.json`
  - direct-reuse probe: `/tmp/runtime_log_job/vortex_t2_B_reuse_v1/runtime_summary.json`
  - the monitored `B` command drops from `109.56s` to `2.49s` with the same compact SHA and the same `10/18` hit result
- The remaining weakness is region richness:
  - `mem_request_path` and `mem_response_path` are still only partial on `sgemm`
  - `8` real-toggle words remain dead in the current Tier-2 packet
  - `C` is not yet separating from `B` under the current fixed budget
  - the second standard workload `saxpy` does not add new active regions beyond `sgemm`
- The provisional rule packet is now strong enough to freeze at the current stage, because `saxpy` reproduces the same packet as `sgemm`.
- The next question is no longer provisional freeze readiness, but whether this frozen packet survives late-family stress without more region-budget refinement; runtime work now shifts to generalizing direct reuse beyond preload-free warm paths.

## Next Step

- Treat `Vortex` as the first completed Tier-2 medium-design gate, then move to provisional rule freeze and runtime/aggregation work. If the current partial memory-path regions prove too weak for freeze, add one more medium-design / region-budget refinement pass rather than reopening wrapper bring-up.
