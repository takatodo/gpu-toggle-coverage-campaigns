# Runtime Runner Scope

- status: `mainline_runtime_rollout_complete_scope_limited`
- decision: `scope_out_debug_raw_runners`

## Mainline Runtime Runners

| Runner | Classification | Reason | Evidence |
|---|---|---|---|
| run_rtlmeter_gpu_toggle_baseline.py | mainline_default | Shared GPU baseline runner that now defaults to direct bench reuse and underpins late-family gate reruns. | /tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/summary_auto.json<br>/tmp/veer_el2_gpu_cov_gate_reuse_validation_v1/reuse_compare.json |
| run_rtlmeter_design_rule_guided_sweep.py | mainline_default | Rule-guided GPU orchestrator in the frozen packet; defaults to reuse and device-aware batching. | /tmp/device_aware_rule_slice_v1/run.json |
| run_tier2_vortex_abc.py | mainline_default | Tier-2 A/B/C medium-design runner retained as part of the frozen rule evidence; flows B/C default to reuse. | /tmp/metrics_driven_t2_exec_v2/B_gpu_metrics_only/summary.json<br>/tmp/runtime_log_job/vortex_t2_B_reuse_v1/runtime_summary.json |
| run_veer_family_gpu_toggle_validation.py | mainline_default | VeeR late-family gate runner retained in final packet scope and now defaults to reuse for gpu_cov_gate. | /tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/reuse_compare.json<br>/tmp/veer_el2_gpu_cov_gate_reuse_validation_v1/reuse_compare.json |
| run_xuantie_family_gpu_toggle_validation.py | mainline_default | XuanTie late-family gate runner retained in final packet scope and now reaches direct_bench_kernel on warm reruns. | /tmp/xuantie_family_gpu_cov_gate_baseline_v5/reuse_compare.json |
| run_opentitan_tlul_slice_gpu_baseline.py | mainline_default | OpenTitan slice baseline family is part of the frozen packet and lands on cached_bundle_kernel with warm cache hits. | /tmp/opentitan_slice_bundle_cache_validation_v1/bundle_reuse_compare.json |
| run_opentitan_tlul_slice_trace_gpu_sweep.py | mainline_default | Low-level OpenTitan slice sweep chokepoint now carries device-aware batching policy. | /tmp/slice_sweep_policy_validate_v1/summary.json |
| run_opentitan_tlul_slice_trace_gpu_sweep_campaign.py | mainline_default | Low-level OpenTitan slice campaign chokepoint now carries device-aware batching policy. | /tmp/slice_campaign_policy_validate_v1/campaign_manifest.json<br>/tmp/slice_campaign_policy_validate_v1/summary.json |
| run_opentitan_tlul_slice_backend_compare.py | mainline_default | Backend-compare runner now reuses cached bundles and remains part of the OpenTitan control-plane selection flow. | /tmp/backend_compare_run_v3/backend_cache_compare.json<br>/tmp/backend_compare_run_v3/backend_compare_run.json |
| prepare_opentitan_tlul_slice_backend_compare.py | mainline_support | Plan generator for backend compare; kept because the compare runner depends on its cached-bundle plan outputs. | /tmp/backend_compare_plan_v1/backend_compare_plan.json |

## Scoped-Out Runners

| Runner | Classification | Packet Required | Reason |
|---|---|---|---|
| run_veer_gpu_cov_cpu_debug.py | debug_raw_debt | False | Directly reruns an existing _execute/cmd with extra debug plusargs; it does not participate in the frozen packet or runtime-default stack. |
| run_veer_direct_vsim.py | debug_raw_debt | False | Raw simulator bring-up/debug helper for obj_dir/Vsim execution; intentionally outside the mainline baseline/cached-bundle path. |
| run_example_cpu_baseline.py | tier0_cpu_harness | False | Tier-0 CPU-only harness artifact used to anchor the smallest repeatable RTLMeter case, not part of the GPU runtime rollout. |

## Follow-On Debt

- Only revisit scoped-out runners if the freeze scope later expands to require raw debug/runtime parity.
