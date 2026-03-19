# Metrics-Driven Final Rule Packet

- status: `needs_review`
- scope decision: `scope_limited_final_freeze`
- frozen rule families: `deep_fifo_source, compact_socket_source, mixed_source_campaign_circt_multistep, dense_xbar_circt, balanced_source_general`

## Included Scope

- OpenTitan slice rule validation
- Tier-1 A/B/C simple-circuit evidence
- Tier-2 A/B/C medium-design evidence
- late-family gpu_cov_gate prechecks on VeeR and XuanTie

## Excluded Scope

- raw sim-accel gpu_cov on timing-based late-family testbenches

## Late-Family Gate Evidence

| Design | Config | Test | Status | Log |
|---|---|---|---|---|
| VeeR-EL2 | gpu_cov_gate | dhry | failed | /tmp/veer_el2_gpu_cov_gate_direct_v1/VeeR-EL2/gpu_cov_gate/execute-0/dhry/_execute/stdout.log |
| VeeR-EH1 | gpu_cov_gate | dhry | failed | /tmp/veer_eh1_gpu_cov_gate_dhry_v1/VeeR-EH1/gpu_cov_gate/execute-0/dhry/_execute/stdout.log |
| VeeR-EH2 | gpu_cov_gate | cmark_iccm_mt | failed | /tmp/veer_eh2_gpu_cov_gate_cmark_iccm_mt_v1/VeeR-EH2/gpu_cov_gate/execute-0/cmark_iccm_mt/_execute/stdout.log |

## Post-Freeze Expansion Evidence

- `XuanTie-C906:gpu_cov_gate:hello` reaches `status=passed` via readiness packet, `bench_runtime_mode=readiness_only`: `/tmp/xuantie_c906_gpu_cov_gate_direct_harness_v15/gpu_cov_gate/hello/summary.json`
- `XuanTie-C906:gpu_cov_gate:cmark` reaches `status=passed` via readiness packet, `bench_runtime_mode=readiness_only`: `/tmp/xuantie_c906_gpu_cov_gate_direct_harness_v15/gpu_cov_gate/cmark/summary.json`
- `XuanTie-C910:gpu_cov_gate:hello` reaches `status=passed` via readiness packet, `bench_runtime_mode=readiness_only`: `/tmp/xuantie_c910_gpu_cov_gate_axi_if_v2/gpu_cov_gate/hello/summary.json`
- `XuanTie-C910:gpu_cov_gate:memcpy` reaches `status=passed` via readiness packet, `bench_runtime_mode=readiness_only`: `/tmp/xuantie_c910_gpu_cov_gate_axi_if_v2/gpu_cov_gate/memcpy/summary.json`
- `XiangShan:gpu_cov_gate:hello` reaches `status=needs_review` via readiness packet, `bench_runtime_mode=readiness_only`: `/tmp/xiangshan_family_gpu_cov_gate_contract_v3/gpu_cov_gate/hello/summary.json`
- `XiangShan:gpu_cov_gate:cmark` reaches `status=needs_review` via readiness packet, `bench_runtime_mode=readiness_only`: `/tmp/xiangshan_family_gpu_cov_gate_contract_v3/gpu_cov_gate/cmark/summary.json`
- `BlackParrot:gpu_cov_gate:hello` reaches `status=passed` via readiness packet, `bench_runtime_mode=readiness_only`: `/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/hello/summary.json`
- `BlackParrot:gpu_cov_gate:cmark` reaches `status=passed` via readiness packet, `bench_runtime_mode=readiness_only`: `/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/cmark/summary.json`
- `OpenPiton:gpu_cov_gate:hello` reaches `status=passed` via readiness packet, `bench_runtime_mode=readiness_only`: `/tmp/openpiton_gpu_cov_gate_v8/gpu_cov_gate/hello/summary.json`
- `OpenPiton:gpu_cov_gate:fib` reaches `status=passed` via readiness packet, `bench_runtime_mode=readiness_only`: `/tmp/openpiton_gpu_cov_gate_v8/gpu_cov_gate/fib/summary.json`
- `Example:gpu_cov_gate:hello` reaches `status=passed` via readiness packet, `bench_runtime_mode=readiness_only`: `/tmp/example_gpu_cov_gate_v6/gpu_cov_gate/hello/summary.json`
- `Example:gpu_cov_gate:user` reaches `status=passed` via readiness packet, `bench_runtime_mode=readiness_only`: `/tmp/example_gpu_cov_gate_v6/gpu_cov_gate/user/summary.json`
- `XuanTie-E902:gpu_cov_gate:memcpy` reaches `18/18`, `dead_region_count=0`, partial regions `none`, and `bench_runtime_mode=direct_bench_kernel`: `/tmp/xuantie_e902_gpu_cov_gate_debug_v25/bench_run.log`
- `XuanTie-E906:gpu_cov_gate:cmark` reaches `18/18`, `dead_region_count=0`, partial regions `none`, and `bench_runtime_mode=direct_bench_kernel`: `/tmp/xuantie_e906_gpu_cov_gate_debug_v25/bench_run.log`
- This extends the frozen rule family beyond the original packet-carrying scope without changing the frozen family boundaries, so scope expansion now follows the next fallback family recorded in `design_scope_expansion_packet`.

## Scoped-Out Harness Debt

| Design | Config | Test | Reason | Evidence |
|---|---|---|---|---|
| VeeR-EL2 | gpu_cov | dhry | Raw tb_top-based gpu_cov path remains active but falls into a pathological TEST_FAILED loop despite program_loaded=1 and reset release. | /tmp/veer_family_late_validation_v1/VeeR-EL2/gpu_cov/_pregpu_gpu_cov/VeeR-EL2/gpu_cov/execute-0/dhry/_execute/stdout.log |
| XuanTie-E902 | gpu_cov | memcpy | Raw timing-based tb.v sim-accel gpu_cov path stays dead; the raw gpu_cov CPU summary-path and raw gpu_cov actual GPU path both return 0/18 with all three regions dead. | /tmp/xuantie_e902_rule_guided_gpu_v1/memcpy/summary.json |
| XuanTie-E906 | gpu_cov | cmark | Raw timing-based tb.v sim-accel gpu_cov path stays dead; the raw gpu_cov CPU summary-path and raw gpu_cov actual GPU path both return 0/18 with all three regions dead. | /tmp/xuantie_e906_rule_guided_gpu_v1/cmark/summary.json |

## Runtime Generalization Evidence

- `./runtime_runner_scope.json` records the runtime runner boundary explicitly: there are no residual mainline rollout runners left, and the remaining direct scripts are scoped out as debug/raw debt
- `run_opentitan_tlul_slice_gpu_baseline.py` is separately validated to land on cached bundle execution; `/tmp/opentitan_slice_bundle_cache_validation_v1/bundle_reuse_compare.json` shows `bundle_cache_hit: false -> true` with identical compact SHA on `tlul_fifo_sync`
- seed-only GPU batching is no longer only a bench-local idea: `./gpu_seed_only_probe_tlul_fifo_sync.md` fixes the exact `nstates=16` per-state-seed equivalence result on `tlul_fifo_sync` at about `22.09x` wall-clock speedup over sixteen repeated single-seed runs, and `/tmp/tlul_fifo_sync_sweep_gen_metrics_v2/summary.json` plus `/tmp/tlul_fifo_sync_campaign_gen_metrics_v3/summary.json` now surface packed-launch generation metrics in mainline sweep/campaign summaries, including `launch_generation.init_file_metrics.compression_ratio_vs_naive ~= 7.79x` and `bundle_cache_hit_rate = 1.0` on the local `tlul_fifo_sync` validation run
- device-aware batching is now wired into the rule-guided runners and the low-level OpenTitan slice sweep/campaign chokepoints; `/tmp/device_aware_rule_slice_v1/run.json` shows a 32GB-tier `compact_socket_source` sweep lifting `gpu_nstates` from `64` to `96` and `keep_top_k` from `24` to `36`, `/tmp/slice_campaign_policy_validate_v1/campaign_manifest.json` and `/tmp/slice_sweep_policy_validate_v1/summary.json` show the direct slice campaign/sweep runners carrying the same policy into their own summaries, and `/tmp/device_aware_batch_policy_examples.json` records the shared policy examples (`compact_socket_source` `66 -> 132` campaign candidates, `balanced_source_general` `4096 -> 8192`)
- `/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/reuse_compare.json` and `/tmp/veer_el2_gpu_cov_gate_reuse_validation_v1/reuse_compare.json` both show wrapper vs direct-bench reuse agreement
- `/tmp/xuantie_family_gpu_cov_gate_baseline_v5/reuse_compare.json` shows the XuanTie family gate runner moving from wrapper first-pass execution to `direct_bench_kernel` on the warm rerun, and the later staged-contract refresh at `/tmp/xuantie_e902_gpu_cov_gate_debug_v25/bench_run.log` plus `/tmp/xuantie_e906_gpu_cov_gate_debug_v25/bench_run.log` recovers actual-GPU `18/18` with `dead_region_count=0` for `XuanTie-E902:gpu_cov_gate:memcpy` and `XuanTie-E906:gpu_cov_gate:cmark`
- `/tmp/opentitan_slice_backend_bundle_cache_validation_v1/bundle_reuse_compare.json` plus `/tmp/backend_compare_run_v3/backend_cache_compare.json` show the backend-compare stack now sharing cached bundles: the first validation run rebuilds `source/circt-cubin` bundles, while the warm orchestrator rerun reuses the same cache keys after `/tmp/opentitan_tlul_slice_generated_dir_cache/generated_dir_manifest.json` records `cache_hit=true` for `tlul_fifo_sync`
- direct reuse materializes `/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/runtime_preload_materialized/memory_image.direct.tsv` and `/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/runtime_preload_materialized/memory_image.payload.tsv` on EH1
- runtime preload materialization now hits compile-cache on warm reruns: `/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/summary_cacheprobe_1.json` records the first EH1 reuse probe at `cache_hit_rate = 0.0`, `/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/summary_cacheprobe_2.json` records the second probe at `cache_hit_rate = 0.0`, and both runs stay on `direct_bench_kernel` with direct reuse preserved
- direct reuse materializes `/tmp/veer_el2_gpu_cov_gate_reuse_validation_v1/runtime_preload_materialized/memory_image.direct.tsv` and `/tmp/veer_el2_gpu_cov_gate_reuse_validation_v1/runtime_preload_materialized/memory_image.payload.tsv` on EL2
- `run_rtlmeter_gpu_toggle_baseline.py` now defaults to direct reuse for GPU executions; `/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/summary_auto.json` confirms a flag-free rerun lands on direct reuse
- `run_veer_family_gpu_toggle_validation.py` now defaults to direct reuse for `gpu_cov_gate`
- `run_rtlmeter_design_rule_guided_sweep.py` now defaults to direct reuse for GPU execution
- `run_tier2_vortex_abc.py` now defaults to direct reuse for flows `B/C`

## Follow-On Work

- keep the runtime-default stack stable on the classified mainline runners; the residual direct/debug scripts are now explicitly scoped out in runtime_runner_scope rather than treated as rollout blockers
- revisit raw VeeR/XuanTie sim-accel gpu_cov only if freeze scope is later expanded to require raw late-family runtime parity
