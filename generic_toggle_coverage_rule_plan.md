# Generic GPU Toggle Coverage Plan

## Weakest Point

The mainline weakest point is no longer rule search and it is no longer late-family artifact bring-up.

The generic rule family is now frozen at `scope_limited_final_freeze`: the frozen rule table is supported by `OpenTitan` slice validation, `Tier-1` and `Tier-2` A/B/C evidence, and late-family `gpu_cov_gate` prechecks on `VeeR` and `XuanTie`.

The remaining weaknesses are follow-on items rather than freeze blockers:

- direct bench reuse is no longer limited to preload-free warm paths, and it now matches on both the EH1 sparse-entry preload path and the EL2 heavier Dhrystone preload path; `run_rtlmeter_gpu_toggle_baseline.py` itself now defaults to reuse for GPU executions, the VeeR and XuanTie family validation runners plus the main Tier-2 / rule-guided GPU orchestrators inherit that behavior, the OpenTitan slice baseline family is separately validated to land on `cached_bundle_kernel` with warm bundle cache hits, GPU-memory-aware batching policy now reaches both the rule-guided runners and the low-level OpenTitan slice sweep/campaign chokepoints, and the backend-compare stack now reuses shared cached bundles
- `./runtime_runner_scope.md` and `./runtime_runner_scope.json` now classify the remaining direct scripts explicitly: `run_veer_gpu_cov_cpu_debug.py`, `run_veer_direct_vsim.py`, and `run_example_cpu_baseline.py` are scoped-out debug/raw or Tier-0 harness paths, so no residual mainline rollout blocker remains
- raw timing-based late-family sim-accel `gpu_cov` paths on `VeeR/XuanTie` still show localized execution-contract bugs

Those raw late-family pathologies are treated as localized harness debt outside the current freeze scope unless a future milestone explicitly requires raw late-family runtime parity.

For the current follow-on phase, the weakest point is no longer rule validity,
family bring-up, launch legality, structured second-wave proof feasibility, or
scope-limited ROCm portability. `XuanTie-E902/E906` are now back to actual GPU
`18/18` under `gpu_cov_gate`, and the current blocker has narrowed to where
`GPRO` really creates coverage headroom on top of the now-canonical native
lane. `run_gpro_coverage_improvement.py` now honors the template-local
`runner_args_template`, so the official runner is no longer masking the
template `dead-region` profile behind a hardcoded `mixed` preset.
That split the OpenTitan slices cleanly:

- `tlul_socket_1n` now reaches `14/18` with `dead_region_count=0`
  under the official template-priority runner
  (`/tmp/gpro_tlul_socket_1n_gpro_runner_v1/summary.json`)
- `tlul_socket_m1` also clears the crossbar plateau, reaching `9/18` with
  `dead_region_count=1`
  (`/tmp/gpro_tlul_socket_m1_gpro_runner_v1/summary.json`)
- `xbar_peri` still plateaus at `8/18` with `dead_region_count=0`
  (`/tmp/gpro_xbar_peri_campaign_v1/summary.json`,
  `/tmp/gpro_xbar_peri_campaign_v2_dead/summary.json`,
  `/tmp/gpro_xbar_peri_gpro_runner_v3/summary.json`)
- `xbar_main` still stalls at `4/18` with `dead_region_count=3`
  (`/tmp/gpro_xbar_main_campaign_v1/summary.json`,
  `/tmp/gpro_xbar_main_campaign_v2_dead/summary.json`,
  `/tmp/gpro_xbar_main_gpro_runner_v3/summary.json`)
- `tlul_fifo_sync` remains effectively flat at `0/18`
  (`/tmp/gpro_tlul_fifo_sync_sweep_smoke_v1/summary.json`)

The first-order blocker is therefore no longer portability, ready-family
closure, runner preset mismatch, generic `GPRO` value, `GRPO` rollout
integration, or raw socket-policy quality. `GRPO` proposals now run through the
existing sweep runner on the socket slices, and the socket packet now has a
slice-aware shape rather than a one-target-fits-all shape.

- `tlul_socket_1n` policy-on still lands at `14/18`, `dead_region_count=0`,
  while shrinking `total_candidate_space` from `320` to `64`; under
  `target_region=reqfifo_storage_upper`, `selection_mode=slice`, throughput is
  still volatile across repeats, ranging from `1087.99` vs baseline `1115.42`
  to `809.67` vs baseline `1030.39`
  (`/tmp/grpo_socket1n_compare_v4/comparison.json`,
  `/tmp/grpo_socket1n_compare_v6/comparison.json`)
- `tlul_socket_m1` policy-on still lands at `9/18`, `dead_region_count=1`,
  and the misleading regression disappears once the compare uses the slice's
  actual productive region, `target_region=rspfifo_storage_upper`; under the
  same `320 -> 64` compression, `selection_mode=blend` is now `568.63` vs
  baseline `549.69`, and `selection_mode=exact` is `567.73` vs baseline
  `566.38`
  (`/tmp/grpo_socketm1_compare_v6_rspfifo_blend/comparison.json`,
  `/tmp/grpo_socketm1_compare_v7_rspfifo_exact/comparison.json`)
- `xbar_peri/xbar_main` stay as crossbar control slices for semantic follow-on
  work

The current blocker is therefore no longer "does diversity-aware `GRPO` help at
all", it is no longer formalizing the socket family as a dual-mode packet, and
it is no longer deciding whether `xbar_peri/xbar_main` should stay search
targets. Those choices are already fixed:

- `tlul_socket_1n -> diversity_focused`
- `tlul_socket_m1 -> throughput_focused`
- `xbar_peri/xbar_main -> crossbar control slices`

The weakest point has shifted downstream again. The canonical socket packet now
exists as an operational pair rather than a packet-only split: the mixed-GPU
dispatcher has actual `tlul_socket_1n` and `tlul_socket_m1` runs where
`sim_lane=run_gpro_coverage_improvement.py` and
`learner_lane=run_grpo_phase0_pipeline.py` both pass under the canonical mode
for each slice. That means the blocker is no longer generic operationalization
or carrying the proof from `tlul_socket_1n` to `tlul_socket_m1`. The next
blocker is refreshing the canonical packets around the operational socket pair
and expanding from the effective socket slices while `xbar_peri/xbar_main`
stay control slices and `Caliptra` stays as a background large-family
validation lane.

Among the current OpenTitan templates, the next candidate is no longer
undiscovered and `tlul_request_loopback` is no longer only a smoke candidate.
`xbar_peri/xbar_main` are control slices, `tlul_fifo_sync` remains flat,
`tlul_fifo_async` has been reduced to a partial nonpositive sixth slice, and
`tlul_request_loopback` is now the third operational mixed-GPU / GRPO slice.
The next step is no longer async rescue or request-loopback operationalization.
It is discovering or onboarding the next positive slice after the current
operational trio.

Canonical evidence for that milestone is:

- [llvm_backend_readiness.md](./llvm_backend_readiness.md)
- [llvm_backend_readiness.json](./llvm_backend_readiness.json)
- [llvm_backend_portability_plan.md](./llvm_backend_portability_plan.md)
- [llvm_backend_portability_plan.json](./llvm_backend_portability_plan.json)
- [rocm_structured_second_wave_semantic_gap_waiver.md](./rocm_structured_second_wave_semantic_gap_waiver.md)
- [rocm_structured_second_wave_semantic_gap_waiver.json](./rocm_structured_second_wave_semantic_gap_waiver.json)
- [rocm_native_hsaco_mainline_probe.md](./rocm_native_hsaco_mainline_probe.md)
- [rocm_native_hsaco_mainline_probe.json](./rocm_native_hsaco_mainline_probe.json)
- [rocm_native_general_bundle_smoke.md](./rocm_native_general_bundle_smoke.md)
- [rocm_native_general_bundle_smoke.json](./rocm_native_general_bundle_smoke.json)
- [grpo_socket_policy_compare.md](./grpo_socket_policy_compare.md)
- [grpo_socket_policy_compare.json](./grpo_socket_policy_compare.json)
- [grpo_socket_mode_packet.md](./grpo_socket_mode_packet.md)
- [grpo_socket_mode_packet.json](./grpo_socket_mode_packet.json)
- [grpo_effective_slice_selection_packet.md](./grpo_effective_slice_selection_packet.md)
- [grpo_effective_slice_selection_packet.json](./grpo_effective_slice_selection_packet.json)
- [grpo_next_slice_onboarding_packet.md](./grpo_next_slice_onboarding_packet.md)
- [grpo_next_slice_onboarding_packet.json](./grpo_next_slice_onboarding_packet.json)
- [/tmp/mixed_gpu_dispatcher_grpo_socket1n_actual_v2/dispatcher_summary.json](/tmp/mixed_gpu_dispatcher_grpo_socket1n_actual_v2/dispatcher_summary.json)
- [/tmp/mixed_gpu_dispatcher_grpo_socketm1_actual_v1/dispatcher_summary.json](/tmp/mixed_gpu_dispatcher_grpo_socketm1_actual_v1/dispatcher_summary.json)
- [grpo_xbar_control_packet.md](./grpo_xbar_control_packet.md)
- [grpo_xbar_control_packet.json](./grpo_xbar_control_packet.json)

## Goal

Decide generic, reusable rules that accelerate toggle-coverage convergence on GPU across multiple RTL designs, not only OpenTitan slices.

## Roles

The role split is fixed to `Validation / Runtime-Aggregation / Portability / Freeze`.

| Role | Responsibility | Current focus |
|---|---|---|
| `Validation` | Preserve the frozen packet and actual-GPU evidence while `GRPO` mainlining resumes | Keep the refreshed `E902/E906` packets stable while `Caliptra` stays as a background large-family validation lane |
| `Runtime-Aggregation` | Turn the canonical socket-side `GRPO` dual-mode packet into the main operational path | Keep `tlul_socket_1n` as the diversity-quality canary, `tlul_socket_m1` as the throughput canary, feed them through mixed-GPU orchestration, and keep `xbar_peri/xbar_main` as control slices |
| `Portability` | Keep the native `hsaco` lane stable as resumed validation leans on it | Treat portability as maintenance rather than the current blocker |
| `Freeze` | Feature-based rule family, metric set, thresholds, operator packet | Preserve the frozen generic rule family while follow-on evidence accumulates |

## Priority Order

1. `Runtime-Aggregation`: preserve the operational mixed-GPU socket pair and refresh the canonical packet around `tlul_socket_1n` and `tlul_socket_m1`.
2. `Runtime-Aggregation`: maintain the canonical socket packet under the reduced candidate budget and carry `xbar_peri/xbar_main` as control slices.
3. `Runtime-Aggregation`: preserve `tlul_request_loopback` as the third operational mixed-GPU / GRPO slice and decide the next positive-slice onboarding path.
4. `Validation`: keep the canonical `OpenTitan`, `XiangShan`, `BlackParrot`, `OpenPiton`, `XuanTie`, and `Example` packets stable while `Caliptra` stays in background validation.
5. `Runtime-Aggregation`: keep the mixed-device orchestration entrypoint stable so `GeForce=sim / Radeon=learner` can be exercised without manual env juggling.
6. `Portability`: keep `rocm_wsl_bridge` detection and native `hsaco` summaries honest while the mainline leans on them.
7. `Freeze`: preserve the frozen feature-based rule table and update it only when cross-design evidence materially changes the family boundaries.

## Current Follow-on Tasks

1. `Runtime-Aggregation`
   - keep `tlul_socket_1n` as the diversity-quality canary and `tlul_socket_m1` as the throughput canary for socket-side `GRPO`
   - preserve the current `320 -> 64` candidate compression under the canonical mode split in [grpo_socket_mode_packet.md](./grpo_socket_mode_packet.md)
   - keep `tlul_socket_1n` `throughput` as the least-regressive measured profile rather than letting it override the diversity-focused recommendation
   - carry `xbar_peri` and `xbar_main` as control slices through [grpo_xbar_control_packet.md](./grpo_xbar_control_packet.md)
2. `Runtime-Aggregation`
  - preserve [run_mixed_gpu_dispatcher.py](./run_mixed_gpu_dispatcher.py) as the canonical operational entrypoint for the socket pair
  - keep [mixed_gpu_dispatcher.md](./mixed_gpu_dispatcher.md) aligned with the socket packet rather than only the Torch env split
  - preserve the actual `tlul_socket_1n` and `tlul_socket_m1` mixed-GPU evidence as the canonical operational socket pair
3. `Runtime-Aggregation`
  - refresh the downstream packet/readout around the operational trio
  - preserve the statement that `tlul_request_loopback` is the third operational positive slice while `xbar_peri/xbar_main` stay frozen as control slices and `tlul_fifo_async` stays partial/nonpositive
4. `Validation`
  - preserve the frozen actual-GPU packets while `Caliptra` runs as a background large-family validation lane
  - keep `E902/E906` reflected as actual-GPU validated in the canonical scope packet
5. `Validation`
  - keep the `Caliptra` codegen/build/runtime proof live in [caliptra_gpu_toggle_readiness.md](./caliptra_gpu_toggle_readiness.md) without letting it retake the foreground
  - pick the next fallback family after `Caliptra` in [design_scope_expansion_packet.md](./design_scope_expansion_packet.md)
6. `Portability`
  - keep runtime detection on the `rocm_wsl_bridge` path under WSL Radeon
  - keep summary packets from collapsing to false `GPU unavailable` just because `/dev/kfd` is absent
7. `Freeze-maintenance`
  - do not refreeze the rule family unless resumed `GPRO` or expansion evidence materially changes the usable family boundaries
8. `Runtime-Aggregation`
  - keep [run_mixed_gpu_dispatcher.py](./run_mixed_gpu_dispatcher.py) as the minimal canonical entrypoint for `GeForce=sim / Radeon=learner`
  - preserve the current actual verify evidence under [/tmp/mixed_gpu_dispatcher_verify_v1/dispatcher_summary.json](/tmp/mixed_gpu_dispatcher_verify_v1/dispatcher_summary.json)

## Design Scope Expansion

The next scope-expansion risk is not lack of candidate designs but mixing `ready_for_gpu_toggle` families with `needs_gpu_cov_tb_and_manifest` families too early.

The expansion order is therefore fixed to:

1. preserve the already-validated wrapper-ready families already in scope
   - `XuanTie-E902`
   - `XuanTie-E906`
   - `XiangShan`
   - `BlackParrot`
   - `OpenPiton`
   - `XuanTie-C906`
   - `Example`
   - `XuanTie-C910`
2. move the next remaining large-integration fallback family into bring-up
   - `Caliptra`
3. keep the remaining large integration designs after that
   - `NVDLA`

The frozen expansion packet is:

- [design_scope_expansion_packet.md](./design_scope_expansion_packet.md)
- [design_scope_expansion_packet.json](./design_scope_expansion_packet.json)

The purpose of this order is:

- keep the already-cleared wrapper/manifest families stable in-scope
- test whether `balanced_source_general` survives the remaining large-integration designs without reopening raw harness debt
- introduce exactly one new wrapper/manifest bring-up family at a time
- defer the last large integration-heavy designs until the next fallback family pattern is proven

## Execution Ladder

1. `Validation`: define three comparison flows
   - `A`: `CPU baseline`
   - `B`: `GPU-metrics-only`
   - `C`: `GPU-guided`
2. `Validation`: select `Tier 1` simple circuits
   - `FIFO`
   - `arbiter`
   - `AXI-lite bridge`
   - `simple NoC router`
3. `Freeze`: fix the metric set used in every experiment
   - `time-to-coverage`
   - `time-to-bug`
   - `coverage gain / hour`
   - `unique bugs / hour`
   - `useful simulations / total simulations`
   - `transfer overhead ratio`
   - `score-to-actual-gain correlation`
4. `Runtime-Aggregation`: run microbenches for
   - `toggle count`
   - `diff/XOR + popcount`
   - `histogram`
   - `top-k ranking`
5. `Validation`: run `Tier 1` ranking experiments under fixed wall-clock budgets
6. `Validation`: identify the smallest scale where `GPU-metrics-only` or `GPU-guided` beats `CPU baseline`
7. `Validation`: roll to `Tier 2` medium circuits
   - `DMA`
   - `crossbar`
   - `cache slice`
   - `OpenTitan` slice-level designs
8. `Freeze`: extract the first provisional generic rule family from `Tier 1 + Tier 2`
9. `Runtime-Aggregation`: optimize `D2H/sync`, feature caching, shard merge, and ranking overhead
10. `Lowering`: use the preserved `VeeR` direct-LLVM work as a late stress path, not as the first gate
11. `Validation`: check that the same rule family survives `VeeR-EL2/EH1/EH2`
12. `Validation`: extend to `XuanTie-E902/E906`
13. `Freeze`: final rule freeze

The current concrete target order is fixed in:

- [metrics_driven_gpu_validation_matrix.md](./metrics_driven_gpu_validation_matrix.md)
- [metrics_driven_gpu_validation_matrix.json](./metrics_driven_gpu_validation_matrix.json)

## Decision Rules

### Rule family should decide

- backend family or evaluation branch
- `gpu_nstates`
- `campaign_gpu_nstates`
- `states_per_case`
- `candidate_count`
- `shard_count`
- `recommended_stop`
- `region_budget`
- metric weighting for ranking

### Rule family should NOT decide yet

- family-name hard-coding
- VeeR-specific lowering workarounds
- backend-specific micro-optimizations without cross-design evidence
- deep model-based search before simple/medium-circuit results exist

## Current Evidence

- OpenTitan 5-slice rule-guided `sweep/campaign` validation passes.
- `full_all` is integrated and production defaults are frozen for OpenTitan slices.
- Campaign-wide `CPU/GPU` ratio is still close to parity, which means host overhead remains a first-order bottleneck.
- The current missing evidence is not another `VeeR` probe, but a clean `A/B/C` comparison on simple circuits.
- `Tier 0` is now executable rather than conceptual:
  - `Example:kind:hello` has a repeatable CPU-baseline wrapper artifact at `/tmp/metrics_driven_t0/example_kind_hello_cpu_baseline.json`
  - `tiny_accel.v` has a coarse-breakdown metric-kernel artifact at `/tmp/metrics_driven_t0/tiny_accel_metric_microbench.json`
  - `tiny_accel.v` also has a repeat/sweep stability artifact at `/tmp/metrics_driven_t0/tiny_accel_metric_stability_matrix.json`
  - the stable `131072 states x 64 cycles` baseline is `metric_total_ms mean = 695.77` across `3` repeats with `CV = 0.0116`
  - the earlier `611.03 ms` sample should not be treated as the Tier-0 stable baseline
  - current dominant coarse buckets are `toggle_popcount`, `candidate_popcount`, `packing`, and `unpacking`
  - real `host↔device transfer` remains unmeasured at Tier `0`; only a host-copy proxy is reported until a GPU backend exists
- `Tier 1` is no longer just a target name:
  - `tlul_fifo_sync` now has a fixed-budget `A/B/C` orchestration entrypoint at `./run_tier1_tlul_fifo_sync_abc.py`
  - the prepared manifest is `/tmp/metrics_driven_t1/tlul_fifo_sync_abc_manifest.json`
  - `A = CPU-only campaign`, `B = single-pass GPU metrics/ranking`, `C = closed-loop GPU-guided campaign`
  - Tier-1 `B` now defaults to `512` states / `128` candidates per launch rather than `32` states / `8` candidates per launch
- direct bench reuse is no longer only a Vortex warm-path optimization:
  - `/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/reuse_compare.json` shows wrapper vs direct-bench reuse agreement on `VeeR-EH1:gpu_cov_gate:hello`
  - `/tmp/veer_el2_gpu_cov_gate_reuse_validation_v1/reuse_compare.json` shows the same agreement on the heavier `VeeR-EL2:gpu_cov_gate:dhry` path
  - both paths preserve compact SHA, coverage points, and real-toggle subset points while runtime preload materialization emits `memory_image.direct.tsv` and `memory_image.payload.tsv`
  - `run_rtlmeter_gpu_toggle_baseline.py` itself now defaults to reuse on GPU executions; `/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/summary_auto.json` confirms a flag-free rerun lands on `bench_runtime_mode=direct_bench_kernel`
  - `/tmp/opentitan_slice_bundle_cache_validation_v1/bundle_reuse_compare.json` shows the separate OpenTitan slice baseline family lands on `cached_bundle_kernel`, with `bundle_cache_hit` moving from `false` to `true` while preserving the same compact SHA on `tlul_fifo_sync`
  - `/tmp/device_aware_rule_slice_v1/run.json` shows the rule-guided slice runner applying a 32GB-tier runtime policy to `compact_socket_source`, lifting `gpu_nstates` from `64` to `96` and `keep_top_k` from `24` to `36`
  - `/tmp/slice_campaign_policy_validate_v1/campaign_manifest.json` and `/tmp/slice_sweep_policy_validate_v1/summary.json` show the low-level OpenTitan slice campaign/sweep chokepoints carrying the same policy, with `compact_socket_source`-style scaling reflected in their own `gpu_runtime_policy` / `effective_search_defaults`
  - `/tmp/device_aware_batch_policy_examples.json` records the shared policy examples, including `compact_socket_source` `pilot_campaign_candidate_count: 66 -> 132` and `balanced_source_general` `4096 -> 8192` on a 32GB-tier GPU
  - `run_veer_family_gpu_toggle_validation.py` now defaults to reuse for `gpu_cov_gate`
  - `/tmp/xuantie_family_gpu_cov_gate_baseline_v5/reuse_compare.json` shows the XuanTie family runner moving from wrapper first-pass execution to `direct_bench_kernel` on the warm rerun, and the later staged-contract refresh at `/tmp/xuantie_e902_gpu_cov_gate_debug_v25/bench_run.log` plus `/tmp/xuantie_e906_gpu_cov_gate_debug_v25/bench_run.log` recovers actual-GPU `18/18` with `dead_region_count=0`
  - `/tmp/opentitan_slice_backend_bundle_cache_validation_v1/bundle_reuse_compare.json` shows `measure_bench_backends.py` itself rebuilding `source/circt-cubin` bundles on the first run and reusing them on the warm run, and `/tmp/backend_compare_run_v3/backend_cache_compare.json` shows the higher-level `run_opentitan_tlul_slice_backend_compare.py` stack also reusing those cached bundles once `/tmp/opentitan_tlul_slice_generated_dir_cache/generated_dir_manifest.json` reports `cache_hit=true` for `tlul_fifo_sync`
  - `run_rtlmeter_design_rule_guided_sweep.py` now defaults to reuse for GPU execution, and `run_tier2_vortex_abc.py` now defaults to reuse for flows `B/C`
  - the remaining runtime-generalization question is therefore the residual debug/raw runner surface outside those direct-reuse / cached-bundle defaults, not whether preload-bearing reuse, late-family baseline-runner reuse, or backend-compare cached-bundle reuse works at all
  - the fresh `B` run at `/tmp/metrics_driven_t1_exec_v5/tlul_fifo_sync/B_gpu_metrics_only/summary.json` completed, with expected relaunch count reduced to `16` for the current `512` base-case, `4`-variant sweep
  - the first comparable `A/B/C` summaries now exist at `/tmp/metrics_driven_t1_exec_v6/tlul_fifo_sync/A_cpu_baseline/summary.json`, `/tmp/metrics_driven_t1_exec_v9/tlul_fifo_sync/B_gpu_metrics_only/summary.json`, and `/tmp/metrics_driven_t1_exec_v7/tlul_fifo_sync/C_gpu_guided/summary.json`
  - at this fixed budget, `B` reaches the same best hit/dead-region point as `A/C` with lower wall-clock (`24.10s` vs `26.12s` for `A` and `26.57s` for `C`)
  - `tlul_socket_1n` now also has a fixed-budget `A/B/C` orchestration entrypoint at `./run_tier1_tlul_socket_1n_abc.py`
  - the comparable `A/B/C` summaries now exist at `/tmp/metrics_driven_t1_socket_exec_v2/tlul_socket_1n/A_cpu_baseline/summary.json`, `/tmp/metrics_driven_t1_socket_exec_v4/tlul_socket_1n/B_gpu_metrics_only/summary.json`, and `/tmp/metrics_driven_t1_socket_exec_v3/tlul_socket_1n/C_gpu_guided/summary.json`
  - this adjacent-slice transfer check confirms that `B` survives beyond `tlul_fifo_sync`, but small-budget E2E is still slightly slower on `tlul_socket_1n`
  - the first Tier-1 crossover artifact now exists at `/tmp/metrics_driven_t1_socket_scale_v1/tlul_socket_1n_ab_scale.json`, with the current break-even region around `candidate_count ~= 132-264`
- `Tier 2` is no longer blocked on Vortex wrapper bring-up:
  - `Vortex:gpu_cov` now has comparable fixed-test `A/B/C` summaries at `/tmp/metrics_driven_t2_exec_v2/A_cpu_baseline/summary.json`, `/tmp/metrics_driven_t2_exec_v2/B_gpu_metrics_only/summary.json`, and `/tmp/metrics_driven_t2_exec_v2/C_gpu_guided/summary.json`
  - the assigned standard workload is now `sgemm`; `hello` remains only as a smoke test
  - `Vortex sgemm` now produces nonzero `real_toggle_subset` words on the GPU path and reaches the same `10/18` coverage-point result under `A/B/C`, with no dead regions and only partial `mem_request_path` / `mem_response_path`
  - `Vortex saxpy` now also has comparable `A/B/C` summaries at `/tmp/metrics_driven_t2_exec_v3_saxpy/A_cpu_baseline/summary.json`, `/tmp/metrics_driven_t2_exec_v3_saxpy/B_gpu_metrics_only/summary.json`, and `/tmp/metrics_driven_t2_exec_v3_saxpy/C_gpu_guided/summary.json`
  - `saxpy` reproduces the same `10/18` packet and the same GPU compact SHA as `sgemm`, which confirms flow stability across the second standard test name but does not add new region richness
  - at this fixed test, `B/C` both land near `0.53s` wall-clock while `A` is `3.50s`, so the first medium-design gate is satisfied
  - the next Tier-2 blocker is no longer observability existence but whether the remaining partial memory-path regions are already sufficient for provisional rule freeze or need region-budget refinement / a different medium design, since the second standard Vortex test does not widen the active region set
  - the readiness packet is now documented in `./vortex_gpu_toggle_readiness.md`
  - the first wrapper warm-cache runtime probe for `B` exists at `/tmp/runtime_log_job/vortex_t2_B_sgemm/runtime_summary.json`, and the first validated direct bench reuse probe exists at `/tmp/runtime_log_job/vortex_t2_B_reuse_v1/runtime_summary.json`
  - with `--reuse-bench-kernel-if-present`, the monitored `run_tier2_vortex_abc.py --flow B --tests sgemm` command now drops from `109.56s` to `2.49s` while preserving the same compact SHA (`af94002e61b2757864b2501b800ed80e782b8e531ea5f8d44365cbdaee0ffdf3`) and the same `10/18` hit result
  - this leaves direct-reuse warm-cache overhead at roughly `1.96s` outside the `~0.53s` GPU rep and shifts the next blocker away from raw Tier-2 runtime survival toward freeze sufficiency and reuse generalization
- the first provisional freeze packet now exists:
  - `./metrics_driven_provisional_rule_packet.json`
  - `./metrics_driven_provisional_rule_packet.md`
  - current packet status is `provisional_rule_family_frozen`
  - `deep_fifo_source` survives `tlul_fifo_sync`, `compact_socket_source` now has explicit `simple_transfer_evidence` on `tlul_socket_1n`, and `balanced_source_general` survives the first medium-design gate on `Vortex:gpu_cov:sgemm`
  - the second standard Vortex workload `saxpy` reproduces the same `10/18` packet and the same compact SHA as `sgemm`, so the provisional family is no longer tied only to one standard workload name
  - the next blocker is no longer whether a provisional packet can be formed or whether it can be frozen at all; the current blocker is cross-family late stress beyond the already-cleared VeeR family, while generalizing direct bench reuse beyond warm paths that do not need runtime preload materialization
- The preserved `VeeR` work still matters later:
  - `VeeR-EL2/EH1/EH2` plain-Verilator `gpu_cov` pre-GPU gates are alive.
  - a fresh late-family `VeeR-EL2:gpu_cov:dhry` stress run under `/tmp/veer_family_late_validation_v1/VeeR-EL2/gpu_cov` shows that the standard `dhry` precheck still reaches `TEST_PASSED`, while the raw `tb_top`-based `gpu_cov` execute remains active (`program_loaded=1`, `rst_l=1`, `porst_l=1`, trace/WB/LSU activity visible) but falls into a pathological `TEST_FAILED` loop that exceeded `1.17 GiB` of stdout before manual stop
  - a new late-family gate run `VeeR-EL2:gpu_cov_gate:dhry` under `/tmp/veer_el2_gpu_cov_gate_direct_v1/VeeR-EL2/gpu_cov_gate` now reaches `TEST_PASSED` with clean `$finish`, so the immediate portability step is family rollout of `gpu_cov_gate`, not a mandatory lower-level harness rewrite
  - the same gate rollout now survives the assigned family-standard reruns: `VeeR-EH1:gpu_cov_gate:dhry` under `/tmp/veer_eh1_gpu_cov_gate_dhry_v1/VeeR-EH1/gpu_cov_gate` and `VeeR-EH2:gpu_cov_gate:cmark_iccm_mt` under `/tmp/veer_eh2_gpu_cov_gate_cmark_iccm_mt_v1/VeeR-EH2/gpu_cov_gate` both reach clean `TEST_PASSED`
  - this removes VeeR from the immediate late-family blocker set
  - `XuanTie-E902/E906` now also have `gpu_cov_tb`, `coverage_regions`, `gpu_cov`, and explicit `gpu_cov_gate` descriptor configurations
  - the assigned XuanTie family-standard gate reruns now pass too: `XuanTie-E902:gpu_cov_gate:memcpy` under `/tmp/xuantie_family_gpu_cov_gate_direct_v1/XuanTie-E902/gpu_cov_gate/execute-0/memcpy/_execute/stdout.log` and `XuanTie-E906:gpu_cov_gate:cmark` under `/tmp/xuantie_family_gpu_cov_gate_direct_v1/XuanTie-E906/gpu_cov_gate/execute-0/cmark/_execute/stdout.log` both reach clean `TEST_PASSED`
  - both assigned XuanTie standard workloads also survive the generic summary path at `/tmp/xuantie_e902_rule_guided_v2/memcpy/summary.json` and `/tmp/xuantie_e906_rule_guided_v2/cmark/summary.json` after materializing `case.pat` iteration patching inside the baseline runner
  - the raw sim-accel `gpu_cov` rule-guided GPU runs under `/tmp/xuantie_e902_rule_guided_gpu_v1/memcpy/summary.json` and `/tmp/xuantie_e906_rule_guided_gpu_v1/cmark/summary.json` still return `points_hit=0/18` with `dead_region_count=3`, so the remaining XuanTie issue is not artifact bring-up; it is a localized timing-based execution-contract bug in the raw sim-accel path
  - Direct CIRCT `DUT-only` import reaches bounded `LLVM IR` on `EL2`.
  - A bounded SCC-driven classifier now reproduces the `%14963 -> %22202` cut and reaches `LLVM IR` through a single refresh entrypoint.
  - The raw sim-accel sidecar path remains dead and is not the preferred correctness base for rule freeze.
- This means `VeeR` and `XuanTie` are now both best used as cleared late stress families at the `gpu_cov_gate` level rather than as the active blocker. The old raw `gpu_cov` paths still show family-specific execution-contract bugs, but the gate paths are already good enough to carry late-family prechecks forward; the remaining question is whether final freeze needs raw late-family sim-accel evidence or can scope those pathologies as localized harness debt.
- That scope decision is now made and recorded in:
  - `./metrics_driven_final_rule_packet.json`
  - `./metrics_driven_final_rule_packet.md`
  - `./rtlmeter_design_generic_rule_validation.json`
  - `./rtlmeter_design_generic_rule_validation.md`
- The final status is `final_rule_family_frozen_scope_limited`:
  - included scope: OpenTitan slice validation, Tier-1/Tier-2 A/B/C evidence, and `gpu_cov_gate` late-family prechecks on `VeeR` and `XuanTie`
  - excluded scope: raw timing-based late-family sim-accel `gpu_cov` paths, which remain localized harness debt

## Role Exit Criteria

- `Lowering`
  Exit the current blocking phase only after late external-family stress tests can be run on a stable path without redefining the earlier metric conclusions.
- `Validation`
  Exit the current blocking phase only after `Tier 1`, `Tier 2`, and at least one late external family all show interpretable results.
- `Runtime-Aggregation`
  Exit only after end-to-end overhead no longer erases the gain shown by the useful metric loop.
- `Freeze`
  Exit only after the rule family is explained by measurable circuit features and survives simple, medium, and late external-family validation.

## Success Criteria

1. At least one `Tier 1` and one `Tier 2` design show `GPU-metrics-only` or `GPU-guided` gain over the CPU baseline under fixed wall-clock budgets.
2. The generic rule family can be selected from circuit features instead of hard-coded family labels.
3. End-to-end overhead is reduced enough that the measured GPU gain survives `D2H/sync`, merge, and ranking costs.
4. The same rule family survives late `VeeR`/`XuanTie` validation strongly enough to freeze into a stable operator packet.
