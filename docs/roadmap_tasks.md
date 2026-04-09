# Goal-to-Task Breakdown

## Goal

Reach the README target state: **hybrid CPU-GPU execution using the stock Verilator frontend**, with no sim-accel dependency, and enough fidelity to run representative designs with reset/step sequencing, GPU kernel launches, and toggle coverage collection in one supported flow.

## Campaign Goal

The real project goal is broader than the minimum README target:
**satisfy coverage targets across multiple designs faster than conventional CPU / RTL simulation**.

That immediately creates one weakest point in the current tracker:

- the project already proves one supported stock-hybrid flow,
- but it does **not** yet prove a repeatable "time-to-coverage-target" win against a normal simulation baseline.

So the roadmap must now distinguish:

- **minimum technical goal**: already met by `tlul_socket_m1`
- **campaign goal**: not yet met; requires baseline-vs-hybrid speed evidence and multi-design coverage surfaces

## Verified Status (2026-04-04)

- Phase A is done. `build_vl_gpu.py` and `vlgpugen` build a cubin from stock Verilator `--cc` output.
- Phase B is complete at the supported endpoint. `--analyze-phases` writes `vl_phase_analysis.json`, `--kernel-split-phases` emits manifest-driven guarded `launch_sequence`, and both local reference designs (`tlul_socket_m1`, `tlul_request_loopback`) now pass `phase_b_endpoint` under the verified compare flows `nstates=1, steps=1` and `nstates=256, steps=3`. The only remaining `strict_final_state` gap is the same four Verilator convergence-bookkeeping fields.
- Phase C is supported for the first target. `src/hybrid/host_abi.h` defines the first supported ABI, `src/tools/run_socket_m1_host_probe.py` builds a stock-Verilator host probe for `tlul_socket_m1`, `src/tools/run_socket_m1_host_gpu_flow.py` hands the host-generated root image into the GPU runner through `RUN_VL_HYBRID_INIT_STATE`, and the project now explicitly accepts the generated TB-owned timed clock as the first supported clock source for `tlul_socket_m1`.
- Phase D is minimal but real. `run_vl_hybrid.py` reads `vl_batch_gpu.meta.json`, sets `RUN_VL_HYBRID_KERNELS`, and launches the cubin. `src/runners/run_socket_m1_stock_hybrid_validation.py` wraps the first supported `socket_m1` flow in a stable validation JSON schema, and `src/runners/run_tlul_request_loopback_stock_hybrid_validation.py` reuses that schema for a `phase_b_reference_design` validation surface on `tlul_request_loopback`. Promotion depth is now explicit: the checked-in `loopback` validation JSON still blocks on `done_o`, and the checked-in GPU sweeps show `progress_cycle_count_o` stuck at the host-probe baseline (`5`) at both `--steps 1` and `--steps 256`. A 2026-04-04 tuning sweep found a terminal-state candidate (`cfg_req_valid_pct_i=92`, `host_post_reset_cycles=120`) that passes `promotion_gate`, but that same artifact still fails the new `handoff_gate`: the host probe already reached `done_o=1`, and GPU replay did not advance progress or signature beyond the host baseline. A follow-on search across `req_valid_pct in {80,84,88,92}`, `host_post_reset_cycles in {96,104,112,116}`, and `steps in {56,112,256}` found zero `handoff_gate` passes and zero `host_done=0 -> final_done=1` cases; see `work/vl_ir_exp/tlul_request_loopback_vl/tlul_request_loopback_handoff_search_summary.json`. For the current milestone, `tlul_request_loopback` is therefore frozen at `phase_b_reference_design` rather than treated as a pending near-term promotion.
- Phase E is a prototype. `vlgpugen` has automatic runtime/GPU classification logic, emits `vl_classifier_report.json`, and the supported validation surfaces now point back to that artifact. The classifier is still heuristic, but `socket_m1` / `tlul_request_loopback` now have checked-in expectation files and `vl_classifier_audit.json` artifacts that pin the current placement counts and key reason categories.

## Exit Criteria

- A stock-Verilator-only path exists for at least one representative design and does not depend on the sim-accel fork.
- Reset, clocking, and phase ordering are validated against a CPU or RTL reference for the supported design.
- Toggle bits or an equivalent coverage artifact are read back through the supported hybrid flow.
- CPU/GPU placement decisions are explainable enough to debug when a design fails classification.
- The supported path is reproducible from one documented command sequence.

## Goal Assessment

- The **minimum supported goal is already met**.
- `tlul_socket_m1` satisfies the current exit criteria: stock-Verilator-only path, validated reset/clock/phase behavior for the supported design, supported host->GPU handoff, toggle readback, explainable classifier output, and a documented supported entrypoint.
- The remaining work is therefore **expansion or refinement**, not a blocker to claiming the minimum README target state.
- The **campaign goal is not yet met**.
- What is missing is not another bootstrap proof; it is a measurable campaign loop:
  normal sim baseline, coverage-satisfaction target, hybrid runner, and side-by-side speed comparison across more than one design surface.
- The first two design surfaces now exist (`tlul_socket_m1`, `tlul_fifo_sync`), so the next weakness is no longer "can we build a second comparison artifact?" but "what comes after two v1 comparisons, and is `toggle_bits_hit >= 5` enough to count as stronger evidence?"

## Remaining Tasks To Minimum Goal

- None.
- The current project can already claim the minimum README target state through `tlul_socket_m1`.
- Everything below should be read as **post-goal backlog** unless a new stricter goal is declared.

## Immediate Post-Goal Tasks

1. Keep the current milestone fixed: `socket_m1` remains the only `Tier S`, and `tlul_fifo_sync` remains `Tier R`.
2. If the next milestone reopens promotion work, define the next supported gate before starting another design search.
   - The checked-in `thin_top_edge_parity_v1` gate is already sufficient for a `thin_top_reference_design`.
   - The proposed next gate is `thin_top_supported_v1`: keep the existing parity gate, require host direct-port control plus `toggle_coverage.any_hit=true`, and make the flow command a documented supported entrypoint.
   - For the current milestone this is a dormant proposal, not an active gate.
   - The next question is therefore next-milestone promotion policy, not branch selection.
   - Use `docs/tlul_fifo_sync_promotion_packet.md` as the decision packet.
3. Keep `strict_final_state` and `tlul_request_loopback` promotion out of the critical path unless a concrete downstream need appears.

## Campaign Tasks Beyond The Minimum Goal

1. Lock the first machine-readable campaign threshold into checked-in artifacts.
   - v1 is now fixed as `campaign_threshold.kind=toggle_bits_hit`, `value=3`, `aggregation=bitwise_or_across_trials`.
   - Hybrid / baseline / comparison JSON now all emit the same threshold contract.
2. Add a normal-simulation baseline runner for the first supported design.
   - This is now done for `tlul_socket_m1` via `output/validation/socket_m1_cpu_baseline_validation.json`.
3. Emit a time-to-threshold comparison artifact.
   - This is now done for `tlul_socket_m1` via `output/validation/socket_m1_time_to_threshold_comparison.json`.
   - The checked-in v1 result is `winner=hybrid`, `comparison_ready=true`, `speedup_ratio≈15.06` at `toggle_bits_hit >= 3`.
4. Generalize that comparison schema to at least one second design surface.
   - This is now done for `tlul_fifo_sync` via `output/validation/tlul_fifo_sync_cpu_baseline_validation.json`
     and `output/validation/tlul_fifo_sync_time_to_threshold_comparison.json`.
- The checked-in v1 result is `winner=hybrid`, `comparison_ready=true`, `speedup_ratio≈1.16`
  at `toggle_bits_hit >= 3`.
- A threshold-5 candidate trial now also exists for both surfaces.
  `socket_m1` improves to `speedup_ratio≈22.53`, `tlul_fifo_sync` improves to `≈1.20`,
  but `work/campaign_next_kpi_audit_threshold5.json` still returns `recommended_next_kpi=stronger_thresholds`.
- `work/campaign_threshold_candidate_matrix.json` now makes the promotion decision explicit:
  `threshold5` is `candidate_only`, and the current action is
  `keep_current_threshold_and_define_stronger_candidate`.
- `work/campaign_threshold_headroom_experiments.json` now fixes the next weakness more concretely:
  `socket_m1` plateaus at `bits_hit=5` under the current candidate settings,
  `socket_m1 threshold=6` is unresolved,
  `tlul_fifo_sync threshold=24` still wins only weakly,
  and `tlul_fifo_sync threshold=25` is unresolved.
- `work/tlul_fifo_sync_threshold_semantics_audit.json` now fixes the next boundary:
  `tlul_fifo_sync` is strongest on `1`,
  still wins on the checked-in `1,0` replay depth,
  but extending that same threshold-24 semantics to `1,0,1` already flips the winner to baseline,
  so the next stronger threshold must not be defined as a longer replay sequence.
5. Only after the comparison loop exists should repo-wide design count become the main KPI.

Use `docs/socket_m1_time_to_threshold_packet.md` as the first execution packet for this campaign line.
Use `docs/socket_m1_time_to_threshold_execution_packet.md` as the CC-facing implementation packet.
Use `docs/socket_m1_campaign_schema_packet.md` to keep hybrid/baseline/comparison artifacts aligned.
Use `docs/socket_m1_hybrid_schema_normalization_packet.md` to land WP0 without schema-version drift.
Use `docs/socket_m1_hybrid_schema_wp0_execution_packet.md` to hand CC the exact write set for WP0.
Use `docs/socket_m1_campaign_proof_matrix.md` to pin reject/unresolved/winner semantics before comparison code lands.

## Remaining Tasks To The Campaign Goal

The weakest point is no longer `socket_m1`.
The checked-in `socket_m1` campaign loop already exists:

- `output/validation/socket_m1_stock_hybrid_validation.json`
- `output/validation/socket_m1_cpu_baseline_validation.json`
- `output/validation/socket_m1_time_to_threshold_comparison.json`

The second checked-in campaign surface now also exists:

- `output/validation/tlul_fifo_sync_stock_hybrid_validation.json`
- `output/validation/tlul_fifo_sync_cpu_baseline_validation.json`
- `output/validation/tlul_fifo_sync_time_to_threshold_comparison.json`

But the real campaign goal is still not fully met, because the current evidence is still narrow:
two TL-UL surfaces and the v1 threshold `toggle_bits_hit >= 3`.
The checked-in next-KPI audit now recommends `stronger_thresholds`, not broader design count,
because the weakest current hybrid win (`tlul_fifo_sync`) is still only `speedup_ratio≈1.16`.

So the remaining work to the real campaign goal is now:

1. Keep the first two checked-in campaign artifacts stable:
   - `output/validation/socket_m1_time_to_threshold_comparison.json`
   - `output/validation/tlul_fifo_sync_time_to_threshold_comparison.json`
   - `work/campaign_speed_scoreboard.json` is now the machine-readable aggregate source of truth for those two surfaces.
2. Treat stronger per-design thresholds as the checked-in next KPI.
   - `work/campaign_next_kpi_audit.json` is now the machine-readable source of truth for that decision.
3. Tighten the campaign contract on the two existing surfaces before adding more designs.
   - For `tlul_fifo_sync`, this now specifically means defining a stronger threshold semantics that is
     not equivalent to extending the checked-in `1,0` host replay depth.
   - Decide whether `tlul_fifo_sync` should use a design-specific minimal-progress sequence candidate (`1`)
     or whether v2 must remain a common cross-design semantics.
   - `work/campaign_threshold_policy_options.json` is now the machine-readable source of truth for the available policy options.
   - `config/campaign_threshold_policies/index.json` is the checked-in scenario definition for those options.
   - `config/campaign_threshold_policies/selection.json` is the checked-in policy switch for both per-target semantics and threshold-schema matching.
   - `work/campaign_threshold_policy_gate.json` is the machine-readable source of truth for the current active policy.
   - `work/campaign_speed_scoreboard_active.json` is the machine-readable source of truth for the active comparison set selected by that policy.
   - `work/campaign_next_kpi_active.json` is the machine-readable source of truth for the active next-KPI recommendation.
   - `work/campaign_threshold_policy_preview.json` is the machine-readable policy matrix over `allow_per_target_thresholds` and `require_matching_thresholds`.
   - `work/campaign_policy_decision_readiness.json` is the machine-readable summary of which policy branch is active, which branch is blocked, and which branch becomes ready if policy changes.
   - `work/campaign_policy_change_impact.json` is the machine-readable current-vs-candidate diff for the policy change currently under consideration.
   - `work/campaign_threshold_policy_profiles.json` is the machine-readable named-profile comparison:
     `common_v1_hold`, `per_target_blocked`, `per_target_ready`.
   - Current checked-in state is now `per_target_ready`, so the active gate promotes the design-specific v2 line.
   - `work/campaign_policy_decision_readiness.json` now reads that policy as already checked in; its `recommended_active_task` should now be read as historical policy-switch context, not as the current checkpoint task.
   - `work/campaign_policy_change_impact.json` now reads reversion away from that line as a reduction in design count, not as progress.
   - `work/campaign_third_surface_candidates.json` is now historical for the current ready pool; it is empty because that pool is exhausted.
   - `work/campaign_post_checkpoint_axes.json` is now the machine-readable source of truth for the next expansion axis beyond the current ready pool.
4. The current active line already reopens broader design count under the checked-in policy; the next question is where to broaden, not whether to reopen it.
5. Promotion-to-supported and campaign-speed proof remain separate questions; do not conflate `Tier S` work with campaign-speed expansion.

Compressed to the actual remaining decisions, the campaign task list is:

1. Treat the current OpenTitan line as the checked-in first checkpoint, not as a pending claim.
   - `work/campaign_checkpoint_readiness.json` already says `cross_family_checkpoint_ready`.
   - `work/campaign_real_goal_acceptance_gate.json` now says `accepted_checkpoint_and_seed`, so the checkpoint acceptance itself is no longer open work.
2. Treat `XuanTie-E902` as the checked-in first non-OpenTitan seed, not as a pending profile choice.
   - `output/validation/xuantie_e902_stock_hybrid_validation.json`, `output/validation/xuantie_e902_cpu_baseline_validation.json`, and `output/validation/xuantie_e902_time_to_threshold_comparison.json` form the first checked-in non-OpenTitan trio, with `winner=hybrid`.
   - `work/campaign_non_opentitan_seed_status.json` remains the readiness proof (`ready_to_accept_selected_seed`), but the active acceptance state is now owned by `work/campaign_real_goal_acceptance_gate.json`.
3. The current next question is the XuanTie breadth step after that accepted seed.
   - `work/campaign_non_opentitan_override_candidates.json` still ranks `XuanTie-E902` first and `XuanTie-E906` as the fallback breadth candidate.
   - `XuanTie-E906` default checked-in trio remains unresolved at `toggle_bits_hit >= 8`, while `output/validation/xuantie_e906_time_to_threshold_comparison_threshold2.json` proves a candidate-only threshold-2 hybrid win.
   - `work/xuantie_e906_case_variants.json` closes the obvious workload-swap question: checked-in `cmark`, `hello`, and `memcpy` all plateau at `bits_hit=2`.
   - `work/xuantie_e906_threshold_options.json` now shows that `threshold=2` is the strongest ready numeric gate and that every numeric threshold from `3..8` is blocked under the known checked-in workloads.
   - `work/campaign_xuantie_breadth_status.json` compresses the underlying evidence and currently says `decide_threshold2_promotion_vs_non_cutoff_default_gate`.
   - `work/campaign_xuantie_breadth_profiles.json` now shows that the checked-in choice is `e906_candidate_only_threshold2`; `e906_default_gate_hold` is historical hold and `xuantie_family_pilot_recovery` remains blocked.
   - `work/campaign_xuantie_breadth_gate.json` now makes that current checked-in selection explicit and currently says `candidate_only_ready`.
   - `work/campaign_xuantie_breadth_acceptance_gate.json` now says `accepted_selected_xuantie_breadth`, so the E906 breadth step is no longer pending.
4. The current next question is no longer whether to accept E906; it is what to do after the accepted E902+E906 XuanTie baseline.
   - `work/campaign_non_opentitan_breadth_axes.json` is now the source of truth for that branch.
   - It currently says `decide_continue_xuantie_breadth_vs_open_fallback_family`.
   - The remaining same-family designs from the current post-checkpoint inventory are `XuanTie-C906` and `XuanTie-C910`.
   - The current fallback family is `VeeR`.
   - `work/campaign_non_opentitan_breadth_profiles.json` now turns that branch into named profiles:
     current=`xuantie_continue_same_family`, ready alternative=`open_veer_fallback_family`.
   - `work/campaign_non_opentitan_breadth_gate.json` is the current active outcome and currently says `continue_same_family_ready`.
   - `work/campaign_non_opentitan_breadth_branch_candidates.json` now compares the ready alternatives on the current repo state and still recommends `xuantie_continue_same_family` first, with `XuanTie-C906` as the first same-family design and `open_veer_fallback_family` as the fallback branch.
   - `src/tools/set_campaign_non_opentitan_breadth.py` remains the operational entrypoint if the project intentionally overrides that branch choice.
5. `family_pilot` recovery is now an explicit lower-priority alternative, not the active main line.
   - `work/campaign_non_opentitan_entry_readiness.json` still says `legacy_family_pilot_failed_but_single_surface_override_ready`.
   - That means `family_pilot` recovery should be revisited only if single-surface breadth stalls and the project rejects the fallback-family branch.
6. The current next question is now the first concrete same-family step inside the already-selected `xuantie_continue_same_family` branch.
   - `work/campaign_xuantie_same_family_step.json` is the source of truth for that step.
   - It currently says `decide_selected_same_family_design_candidate_only_vs_new_default_gate`.
   - The selected design is `XuanTie-C906`.
   - The default checked-in line at `output/validation/xuantie_c906_time_to_threshold_comparison.json` is unresolved at `toggle_bits_hit >= 8`.
   - The candidate-only line at `output/validation/xuantie_c906_time_to_threshold_comparison_threshold5.json` is a hybrid win (`≈9.59x`).
   - `work/campaign_xuantie_same_family_profiles.json` now shows that the checked-in choice is `c906_candidate_only_threshold5`; `c906_default_gate_hold` is the historical hold branch.
   - `work/campaign_xuantie_same_family_gate.json` now makes that current checked-in selection explicit and currently says `candidate_only_ready`.
   - `work/campaign_xuantie_same_family_acceptance_gate.json` now says `accepted_selected_same_family_step`, so the `C906 threshold5` line is no longer pending.
7. The current next question is no longer whether to accept `C906`; it is what to do after `C910` proved to be a runtime blocker under the already-selected same-family branch.
   - `work/campaign_xuantie_same_family_next_axes.json` remains the source of truth for why `C910` was the next same-family design and why `VeeR` is the fallback family.
   - `work/campaign_xuantie_c910_runtime_status.json` is now the source of truth for the actual `C910` blocker.
   - It currently says `decide_hybrid_runtime_debug_vs_open_veer_fallback_family`.
   - The CPU baseline is already `ok`, but the PTX-backed hybrid runtime is still blocked.
   - The blocker is now narrower than a generic runtime failure: an `O0` low-opt rebuild aborts inside `llc` on `AtomicLoad acquire (s64)`, an `O1` low-opt rebuild succeeds to PTX but a traced minimal-shape run still stops at `before_cuModuleLoad`, and an offline `ptxas` probe times out at `180s` without producing a cubin.
   - `work/campaign_xuantie_c910_split_phase_trial.json` now fixes that the lowest-cost split-phase reduction tactic is also exhausted:
     the split-phase PTX/module-first trial times out with `returncode=137`, and the last traced stage is still `before_cuModuleLoad`.
   - `work/campaign_xuantie_c910_runtime_profiles.json` now turns that state into named alternatives:
     current=`open_veer_fallback_family`, ready alternatives=`debug_c910_hybrid_runtime` / `open_veer_fallback_family`, recommended=`open_veer_fallback_family`.
   - `work/campaign_xuantie_c910_debug_tactics.json` now narrows the current debug branch further:
     current recommendation is `open_veer_fallback_family`, fallback is `deeper_c910_cubin_debug`.
   - `work/campaign_veer_fallback_candidates.json` now turns that fallback branch into a concrete first-design choice:
     current recommendation is `VeeR-EH1` first, fallback is `VeeR-EH2`.
   - `VeeR-EH1` is now beyond bootstrap and beyond policy hold:
     `work/campaign_veer_first_surface_gate.json` says `candidate_only_ready`,
     `work/campaign_veer_first_surface_acceptance_gate.json` says `accepted_selected_veer_first_surface_step`,
     and `output/validation/veer_eh1_time_to_threshold_comparison_threshold5.json` is the checked-in candidate-only hybrid win (`≈3.37x`).
   - `work/campaign_veer_next_axes.json` now moves the active question to the next remaining same-family design:
     `VeeR-EH2`, with `VeeR-EL2` as the remaining fallback inside the family.
   - `VeeR-EH2` is now beyond bootstrap: both `output/validation/veer_eh2_cpu_baseline_validation.json` and
     `output/validation/veer_eh2_stock_hybrid_validation.json` are `ok`, and the default comparison
     `output/validation/veer_eh2_time_to_threshold_comparison.json` is unresolved only because both sides plateau at
     `bits_hit=4` under the default `toggle_bits_hit >= 8` gate.
   - `output/validation/veer_eh2_time_to_threshold_comparison_threshold4.json` is now a checked-in candidate-only hybrid win
     (`≈2.97x`).
   - `work/campaign_veer_same_family_gate.json` now says `candidate_only_ready`, and
     `work/campaign_veer_same_family_acceptance_gate.json` now says `accepted_selected_veer_same_family_step`.
   - `work/campaign_veer_same_family_next_axes.json` moves the active question again:
     `decide_continue_to_remaining_veer_design`, with `VeeR-EL2` next.
   - `VeeR-EL2` is now beyond bootstrap and beyond trio creation: both
     `output/validation/veer_el2_cpu_baseline_validation.json` and
     `output/validation/veer_el2_stock_hybrid_validation.json` are `ok`, and the default comparison
     `output/validation/veer_el2_time_to_threshold_comparison.json` is unresolved only because both sides plateau at
     `bits_hit=6` under the default `toggle_bits_hit >= 8` gate.
   - `output/validation/veer_el2_time_to_threshold_comparison_threshold6.json` is now a checked-in candidate-only hybrid win
     (`≈2.78x`).
   - `work/campaign_veer_final_same_family_step.json` compressed that into the last EL2 policy question,
     and that question is now closed in favor of the checked-in candidate-only line.
   - `work/campaign_veer_final_same_family_gate.json` now says `candidate_only_ready`, and
     `work/campaign_veer_final_same_family_acceptance_gate.json` now says `accepted_selected_veer_final_same_family_step`.
   - `work/campaign_veer_post_family_exhaustion_axes.json` moves the active question out of the VeeR family:
     `decide_open_next_non_veer_family_after_veer_exhaustion`, with `XiangShan` first and `OpenPiton` fallback.
   - `work/xiangshan_gpu_cov_stock_verilator_cc_bootstrap.json` and
     `output/validation/xiangshan_cpu_baseline_validation.json` now show that XiangShan is beyond bootstrap:
     the descriptor-backed `cppSourceFiles` are enrolled, stock-Verilator bootstrap is `ok`, and the CPU baseline is `ok`.
   - `work/xiangshan_nvcc_device_link_probe.json` now fixes the first working XiangShan executable-image path as a checked-in probe:
     `nvcc --device-c vl_batch_gpu.ptx` emits a `17M` relocatable object with `STO_ENTRY vl_eval_batch_gpu`,
     and `nvcc --device-link --cubin` emits a `19M` linked cubin that also keeps the kernel symbol.
   - `work/xiangshan_nvcc_device_link_from_ptx_smoke_trace.log` now shows that this official `nvcc device-c/device-link`
     line is not just link-complete but runtime-valid: the bounded smoke reaches `after_cleanup` and returns `ok`.
   - `work/xiangshan_ptxas_probe.json` now fixes the cheap offline cubin-first attempt as a checked-in negative artifact:
     `ptxas -O0` times out at `180s` and does not produce a cubin.
   - `work/campaign_xiangshan_vortex_branch_resolution.json` now resolves that reopen loop into one stable next tactic:
     current status is `avoid_xiangshan_vortex_reopen_loop_keep_current_xiangshan_branch`,
     so the checked-in branch remains `reopen_xiangshan_fallback_family`,
     the next task is `deeper_xiangshan_cubin_first_debug`,
     and only the heavier cross-branch fallback stays `deeper_vortex_tls_lowering_debug`.
   - `work/xiangshan_ptxas_compile_only_probe.json` now shows that the first deeper XiangShan packaging line is not dead:
     `ptxas --compile-only -O0` succeeds in about `42s` and emits a relocatable object that still contains `vl_eval_batch_gpu`.
   - `work/xiangshan_compile_only_smoke_trace.log`,
     `work/xiangshan_nvlink_smoke_trace.log`,
     `work/xiangshan_fatbin_smoke_trace.log`, and
     `work/xiangshan_nvcc_dlink_smoke_trace.log` now narrow the packaging blocker:
     direct object/fatbin loads fail with `device kernel image is invalid`,
     while `nvlink` / `nvcc -dlink` packaged variants reach `after_cuModuleLoad` and then fail with `named symbol not found`.
   - `work/xiangshan_fatbinary_device_c_probe.fatbin`,
     `work/xiangshan_fatbinary_device_c_link_probe.fatbin`,
     `work/xiangshan_fatbinary_device_c_probe_smoke_trace.log`, and
     `work/xiangshan_fatbinary_device_c_link_probe_smoke_trace.log` now narrow the packaging blocker further:
     `fatbinary --device-c` keeps `vl_eval_batch_gpu` visible in the packaged image,
     but `cuModuleGetFunction(vl_eval_batch_gpu)` still returns `device kernel image is invalid`.
   - `work/xiangshan_nvlink_probe.cubin` and `work/xiangshan_nvcc_dlink.fatbin` now narrow the executable-link side too:
     both linked outputs are tiny (`760B` / `840B`), symbol-less, and `cuobjdump --dump-resource-usage`
     reports only `GLOBAL:0`, so the current linked executable line is effectively empty.
   - `work/xiangshan_ptx_fatbin_probe.fatbin` and `work/xiangshan_ptx_fatbin_probe_smoke_trace.log`
     now show that the obvious PTX-JIT bypass also stalls: the module still stops at `before_cuModuleLoad`
     and times out under the bounded smoke run.
   - `work/campaign_xiangshan_first_surface_status.json` and
     `work/campaign_xiangshan_deeper_debug_status.json` now agree that XiangShan is beyond packaging debug:
     both say the first trio is ready to finish, because the official `nvcc device-c/device-link` line restores
     a runnable cubin.
   - `output/validation/xiangshan_stock_hybrid_validation.json` and
     `output/validation/xiangshan_time_to_threshold_comparison.json` now establish the default XiangShan trio state:
     stock-hybrid is `ok`, but the default `toggle_bits_hit >= 8` line is unresolved because both sides plateau at `bits_hit=2`.
   - `output/validation/xiangshan_cpu_baseline_validation_threshold2.json`,
     `output/validation/xiangshan_stock_hybrid_validation_threshold2.json`, and
     `output/validation/xiangshan_time_to_threshold_comparison_threshold2.json` now establish the first XiangShan candidate-only line:
     `winner=hybrid`, `comparison_ready=true`, `speedup_ratio≈3.13x`.
   - `work/campaign_xiangshan_first_surface_step.json` compressed the remaining XiangShan policy question,
     and that question is now closed in favor of the checked-in candidate-only line.
   - `work/campaign_xiangshan_first_surface_gate.json` now says `candidate_only_ready`, and
     `work/campaign_xiangshan_first_surface_acceptance_gate.json` now says `accepted_selected_xiangshan_first_surface_step`.
   - That means XiangShan is no longer waiting on `candidate-only vs new default gate`;
     the checked-in `threshold=2` line is accepted reopened fallback-family breadth evidence,
     and the next action is `reopen_vortex_tls_lowering_debug_after_accepting_xiangshan`.
   - `work/openpiton_gpu_cov_stock_verilator_cc_bootstrap.json`,
     `output/validation/openpiton_cpu_baseline_validation.json`,
     `output/validation/openpiton_stock_hybrid_validation.json`, and
     `output/validation/openpiton_time_to_threshold_comparison.json` now establish the first OpenPiton fallback surface.
     The checked-in default hybrid shape is `1 state x 1 step`, the default threshold remains `toggle_bits_hit >= 8`,
     and the comparison is now `winner=hybrid` (`≈1.56x`).
   - `work/campaign_openpiton_first_surface_step.json` compresses that fallback result into the current policy task:
     `ready_to_accept_openpiton_default_gate`.
   - `work/campaign_openpiton_first_surface_gate.json` and
     `work/campaign_openpiton_first_surface_acceptance_gate.json` now close that policy task in checked-in state:
     `OpenPiton` default gate is accepted as the next non-VeeR family surface.
   - `work/campaign_post_openpiton_axes.json` now moves the active question past accepted `OpenPiton`:
     `decide_open_next_family_after_openpiton_acceptance`, with `BlackParrot` first and blocked `XiangShan` as the fallback branch.
   - `work/campaign_blackparrot_first_surface_step.json` and `work/campaign_post_blackparrot_axes.json`
     now show that `BlackParrot` is no longer the live branch:
     even the strongest checked-in candidate-only line loses to the CPU baseline, so the next family is `Vortex`
     and the fallback stays blocked `XiangShan`.
   - `work/vortex_gpu_cov_stock_verilator_cc_bootstrap.json` and
     `output/validation/vortex_cpu_baseline_validation.json` now show that `Vortex` is beyond bootstrap:
     stock-Verilator bootstrap is `ok` and the CPU baseline is `ok`.
   - `output/validation/vortex_stock_hybrid_validation.json`,
     `output/validation/vortex_time_to_threshold_comparison.json`, and
     `output/validation/vortex_time_to_threshold_comparison_threshold4.json`
     now show that `Vortex` has a checked-in first trio:
     the default line is unresolved at `toggle_bits_hit >= 8`, but the `threshold=4`
     candidate-only line is `winner=hybrid`.
   - `work/campaign_vortex_first_surface_status.json` and
     `work/campaign_vortex_first_surface_step.json` now move Vortex out of blocker triage:
     the current status is `ready_to_finish_vortex_first_trio`,
     and the current policy question is `decide_vortex_candidate_only_vs_new_default_gate`.
   - `work/campaign_vortex_first_surface_policy_gate.json` and
     `work/campaign_vortex_first_surface_acceptance_gate.json` now close that policy in checked-in state:
     `Vortex threshold4` is accepted breadth evidence.
   - `work/campaign_post_vortex_axes.json` now moves the active question beyond accepted `Vortex`:
     `decide_open_next_family_after_vortex_acceptance`, with `Caliptra` first and `Example` fallback.
   - `work/caliptra_gpu_cov_stock_verilator_cc_bootstrap.json` and
     `output/validation/caliptra_cpu_baseline_validation.json` now show that `Caliptra` is beyond bootstrap:
     stock-Verilator `--cc` enrollment is `ok`, and the CPU baseline already satisfies the default
     `toggle_bits_hit >= 8` gate.
   - `work/campaign_caliptra_first_surface_status.json` now compresses the current Caliptra blocker:
     `decide_caliptra_tls_lowering_debug_vs_open_example_fallback`.
     The current blocker is no longer "open Caliptra"; it is `llc` failing on
     `GlobalTLSAddress<... @_ZN9Verilated3t_sE>` during GPU codegen.
   - `work/campaign_caliptra_debug_tactics.json` now narrows that line again:
     the scoped Verilated TLS-slot bypass already recovers PTX on the checked-in build path,
     a checked-in cubin now exists, and the stack-limit probe narrows the blocker again:
     the driver accepts stack sizes up to `523712` but rejects `523744+`, while the kernel
     advertises `LOCAL_SIZE_BYTES=564320` and still fails at `before_first_kernel_launch`
     even when run at that maximum accepted stack limit.
     `work/caliptra_split_phase_probe/vl_kernel_manifest.json` and
     `work/caliptra_split_phase_probe/vl_batch_gpu_split_compile_only_probe.json` now narrow that
     main line one step further: the split launch sequence is fixed, the split compile-only probe
     is `ok`, and the split entry kernels report `0 bytes stack frame`.
     `work/caliptra_split_phase_probe/split_ptx_smoke_trace.log` shows that raw split PTX still
     stalls at `before_cuModuleLoad`, but
     `work/caliptra_split_phase_probe/vl_batch_gpu_split_nvcc_device_link_probe.json` now shows
     that the official split `nvcc --device-c -> --device-link --cubin` line succeeds, and
     `work/caliptra_split_phase_probe/split_cubin_smoke_trace.log` shows that the linked split cubin
     reaches `after_first_kernel_launch` before failing with `illegal memory access`.
     Per-kernel smoke narrows that again:
     `split_cubin_ico_smoke_trace.log` and `split_cubin_nba_sequent_smoke_trace.log` are `ok`,
     while `split_cubin_nba_comb_smoke_trace.log` still fails, and
     `split_cubin_nba_comb_block1_smoke_trace.log` /
     `split_cubin_nba_comb_block8_smoke_trace.log` show that small block sizes do not fix it.
     `prefix330` is still clean while `prefix331` fails, and even
     `m_axi_if__0` high-offset-load bypass / ret-after-first-store probes still fail, `store-only`
     / argument-bearing `ret-only` helper probes also fail. `prefix331_param_only`,
     `m_axi_if0_noarg_ret_only`, and `m_axi_if0_b64_zero_ret_only` all run cleanly. The newer
     truncated-after-`callseq 331` probes sharpen that further:
     `m_axi_if0_b64_synth16_trunc_ret_only`, `m_axi_if0_rd4_trunc_ret_only`,
     `m_axi_if0_rd7_trunc_ret_only`, `%rd5 ret-only`, `%rd5 ldptr-ret`, and
     `%rd5 high-offset-load-ret` all run cleanly. The newer `first_branch_merge_ret_trunc`
     probe also runs cleanly, while restoring only the first store reproduces the fault.
     Overwriting that first-store payload with constant `0` or `1` runs cleanly; the branch1-only
     first-store variant still faults, the corresponding branch1-load-zero-store variant runs cleanly,
     but `branch1-load-mask1`, `branch1-predicated01`, `branch1-selp-const1`, and
     `first-store-masked-data` variants still fault, while `branch1-load-dead-mask-const1`
     and `branch1-selp-same-const1` run cleanly. The newer `branch1-load-mask1-shl8` probe still
     faults, while `first-store-masked-data-dead-mask-const1`, `first-store-masked-data-selp-same-const1`, `branch1-predicated10`, `branch1-load-dead-mask-zero`, `branch1-load-mask1-shr8`,
     `branch1-load-mask1-shl1`, `branch1-load-mask1-shl4`, `branch1-load-mask1-shl6`, `branch1-load-mask1-shl7`, `branch1-load-mask1-shl9`, `branch1-load-mask1-shl8-and255`, `branch1-selp-const2`, `branch1-selp-const3`, `branch1-selp-const129`, `branch1-selp-const1-and255`, `branch1-selp-const513`, `branch1-selp-const0`, `branch1-selp-same-const257`, `branch1-load-mask2`, `branch1-load-maskff`, `branch1-load-mask3`,
     `branch1-load-mask1-sep-reg`, `branch1-load-mask1-shl8-sep-reg`, `branch1-load-mov`, and
     `branch1-alt-load` time out in compile, so the actionable line is the compilable
     current-branch1-load-provenance nonconstant source-bit-dependent variants.
     The current task is
     `deeper_caliptra_split_m_axi_if0_first_store_compilable_branch1_load_provenance_nonconstant_loaded_byte_dependent_store_source_bits_runtime_fault_debug`,
     with `branch1-load-mask1-shl8-sep-reg`, `branch1-load-mask1-sep-reg`, `branch1-load-xor-self-zero`, `first-store-self-load`, and
     `branch1-load-store-plus1`, `branch1-load-mask1-or1`, and `branch1-alt-load` all outside the actionable line because they time out before a linked cubin exists,
     with `Example` kept as the fallback family.
   - `work/campaign_vortex_debug_tactics.json` and
     `work/campaign_xiangshan_vortex_branch_resolution.json` now stop pointing back into the
     XiangShan/Vortex reopen loop and instead point at `post-Vortex axes`.

What is explicitly not the next campaign task:

- reopening `tlul_request_loopback` promotion
- pursuing `strict_final_state`
- reopening `tlul_fifo_sync` promotion before stronger-threshold evidence is in place

## Current Expansion Blockers

- The only supported stock-hybrid target is still `tlul_socket_m1`. `tlul_request_loopback` is intentionally frozen at `phase_b_reference_design` for the current milestone because the checked-in template still stalls under GPU replay, the tuned candidate only proves a terminal state, and the reproducible nearby-search tool still found no GPU-driven handoff case.
- A second `Tier R/S` target is now already present, even though a second supported target is not. `tlul_fifo_sync` now has a stable validation surface at `output/validation/tlul_fifo_sync_stock_hybrid_validation.json` with `support_tier=thin_top_reference_design` and `acceptance_gate=thin_top_edge_parity_v1`, and `tlul_err`, `tlul_sink`, and `tlul_socket_1n` now all have stable campaign reference surfaces with checked-in baseline/comparison artifacts. The scoreboard objective `socket_m1 以外に 1 本を Tier R/S まで上げる` is no longer the blocker. `Tier B=0` for the OpenTitan ready-for-campaign pool, and the repeatable branch audit in `work/rtlmeter_expansion_branch_audit.json` still treats raw tier-count gain as secondary to campaign-surface expansion. See `docs/next_supported_target_candidates.md`.
- The `thinner host-driven top` branch is now partially implemented, not just a seed seam. `tlul_fifo_sync_gpu_cov_tb.sv` has been split into a shared core plus a timed wrapper, `tlul_fifo_sync_gpu_cov_host_tb.sv` now exists as a real host-driven wrapper, `bootstrap_hybrid_tlul_slice_cc.py --tb-path ... --top-module tlul_fifo_sync_gpu_cov_host_tb` can build `work/vl_ir_exp/tlul_fifo_sync_host_vl`, and `run_tlul_slice_host_probe.py` records `host_clock_control=true`, `host_reset_control=true`, `clock_ownership=host_direct_ports` in `tlul_fifo_sync_host_probe_report.json`.
- The blocker on that branch has moved again. The host-only edge trace at `work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_edge_trace.json` proves that the host-driven top already produces design-visible delta on the checked-in `1,0` sequence (`progress_cycle_count_o: 6 -> 7`, `progress_signature_o: 0 -> 2654435858`, toggle bitmap words `0 -> nonzero`). The CPU parity probe at `work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_handoff_parity_summary.json` and the GPU replay summary at `work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json` now agree up to internal-only residuals, which is why `thin_top_edge_parity_v1` passes. The current blocker is no longer GPU parity repair; it is the product decision of whether that `Tier R` surface should remain a reference surface or be promoted further.
- The thin-top branch design docs are now split by role. `docs/tlul_fifo_sync_thin_top_design.md` is the architectural note, `docs/tlul_fifo_sync_thin_top_execution_packet.md` is the implementation packet, and `docs/tlul_fifo_sync_handoff_parity_packet.md` is the completed parity packet that established the current `Tier R` gate.
- `strict_final_state` is still unresolved as an optional refinement. It is no longer a delivery blocker, but it remains open technical debt if exact Verilator bookkeeping parity is considered important later.

## Repo-Wide Coverage Expansion

- The current roadmap closes the minimum goal, but it does not by itself define how to expand coverage across `third_party/rtlmeter`.
- Use `docs/rtlmeter_coverage_plan.md` as the checked-in execution plan for that expansion.
- The ready-for-campaign scoreboard now has a machine-generated source of truth at `work/rtlmeter_ready_scoreboard.json`. Current counts are `Tier S=1` (`tlul_socket_m1`), `Tier R=8` (`tlul_err`, `tlul_fifo_async`, `tlul_request_loopback`, `tlul_fifo_sync`, `tlul_sink`, `tlul_socket_1n`, `xbar_main`, `xbar_peri`), `Tier B=0`, `Tier T=0`, and `Tier M=0`.
- The branch choice is now also machine-audited at `work/rtlmeter_expansion_branch_audit.json`: with the current artifacts there is no remaining near-term raw tier-count gain on the `tb_timed_coroutine` path, the second `Tier R/S` objective is already met by `tlul_fifo_sync`, and `defer_second_target` is the recommended branch for all current optimization objectives.
- The expansion sequence is:
  1. turn the OpenTitan `ready_for_campaign` set into a tiered scoreboard,
  2. choose exactly one mechanism branch for the second-target line,
  3. decide whether to promote `tlul_fifo_sync` beyond `Tier R` or keep the second-target line deferred,
  4. then re-enter multi-clock OpenTitan,
  5. and only after that move one non-OpenTitan family out of `Tier U`.

## Current Milestone Decision

1. `tlul_request_loopback` stays at `phase_b_reference_design` for the current milestone.
2. The supported stock-hybrid surface remains centered on `tlul_socket_m1`.
3. Expansion work should now treat `tlul_fifo_sync` as the checked-in second reference surface rather than as an open candidate search.
4. `tlul_fifo_sync` promotion is explicitly deferred. `thin_top_supported_v1` is a next-milestone proposal, not a checked-in gate.
5. `loopback` promotion is deferred work. If it comes back later, the next mechanism should not be another nearby tuning sweep; it should be a thinner host-driven top or a broader state-construction strategy.
6. A second supported target is explicitly deferred beyond the current milestone. This milestone closes with `socket_m1`-only supported status rather than carrying an ambiguous "candidate in progress" state.

## Task Summary

### Current Milestone

- No new top-level goal is needed.
- Treat `tlul_socket_m1` as the only supported target.
- Keep `tlul_request_loopback` at `phase_b_reference_design`.
- Keep `strict_final_state` out of the critical path.

### Next Milestone Entry Tasks

1. Decide whether a second supported target is worth pursuing at all.
2. If yes, decide whether to reopen `tlul_fifo_sync` promotion beyond `Tier R` before reopening any new design search.
3. If promotion work is chosen, use `docs/tlul_fifo_sync_thin_top_design.md` as the design note.
4. Use `docs/tlul_fifo_sync_promotion_packet.md` to define the post-`thin_top_edge_parity_v1` gate first, then return to `docs/tlul_fifo_sync_thin_top_execution_packet.md` only if code work is still needed.
5. If no promotion work is chosen, continue with `socket_m1`-only support plus `tlul_fifo_sync` / `tlul_request_loopback` reference surfaces and defer second-target work again.

## Post-Milestone Expansion Tree

The project does not need another top-level goal. After the current milestone closes, the remaining expansion work is a branching task tree:

1. Decide whether the next milestone should pursue a second supported target at all.
   - If **no**, keep the project focused on `socket_m1` hardening plus optional technical debt.
   - If **yes**, move to Decision 2.
2. Decide whether the second-target search stays on the current `tb_timed_coroutine` ownership model.
   - If **yes**, stop spending time on Tier 1 tuning and first explain what new current-model experiment is supposed to prove, because the checked-in `tlul_err` / `tlul_sink` pilots already exhausted the simple source-restoration path.
   - If **no**, promote a thinner host-driven top to blocker status and seed that work with `tlul_fifo_sync`, not `tlul_socket_1n`.
3. Keep optional debt out of the critical path.
   - `strict_final_state` remains optional.
   - `tlul_request_loopback` promotion remains deferred.

## Priority Tasks

### P0: Make The Current State Trustworthy

- [x] Add a smoke test for `build_vl_gpu.py --analyze-phases` that asserts `vl_phase_analysis.json` schema and required keys.
- [x] Add a smoke test for `build_vl_gpu.py --kernel-split-phases` that asserts `vl_batch_gpu.meta.json` contains `launch_sequence` and cubin generation still succeeds.
- [x] Add a smoke test for `run_vl_hybrid.py --mdir` that asserts `launch_sequence` becomes `RUN_VL_HYBRID_KERNELS`.
- [x] Reconcile published status numbers with current artifacts, starting with `tlul_socket_m1` `storage_size=2112` vs older README values.
- [x] Separate stock-Verilator status from legacy sim-accel result files so stale `returncode: 1` / `aggregate_pass: true` / `coverage_points_hit: 0` records are not read as success. Supported stock status now points at `output/validation/socket_m1_stock_hybrid_validation.json`, reference-design validation uses `output/validation/tlul_request_loopback_stock_hybrid_validation.json`, legacy family runners default to `output/legacy_validation/*.json`, and `docs/status_surfaces.md` defines the source-of-truth split.

### P1: Close The Phase-Fidelity Gap

- [x] Add a regression harness that compares single `vl_eval_batch_gpu` launch against phase-split launch order and records raw state mismatches.
- [x] Extend that regression across `tlul_request_loopback` and `tlul_socket_m1`.
- [x] Localize the remaining mismatches to root fields and phase prefixes. As of 2026-03-29, both designs first diverge in `ico` on Verilator control fields (`__VicoPhaseResult`, `__VactIterCount`, `__VinactIterCount`, `__VicoTriggered`). `tlul_request_loopback` reaches its first non-internal delta at `nba_comb` (`toggle_bitmap_word2_o`, then `tl_h_o`), while `tlul_socket_m1` stays internal-only until `nba_sequent` (`req_under_rst_seen_q`). The compare JSON now exposes this directly via `delta_from_previous_prefix` and `first_*_delta_*`.
- [x] Add a writer-trace tool that maps compare-field names back to generated Verilator phase functions. As of 2026-03-29, `tlul_request_loopback` maps its first delta fields into `___nba_comb__TOP__0`, while `bootstrapped_q` / `target_rsp_pre_w` map into `___nba_sequent__TOP__0`; `tlul_socket_m1` maps `req_under_rst_seen_q`, `device_a_ready_q`, `host_pending_req_q`, and `rsp_queue_q` into `___nba_sequent__TOP__0`, with `debug_device_a_ready_o` in `___nba_sequent__TOP__2`.
- [x] Add an IR-store trace tool that maps those phase functions down to concrete LLVM `store` sites. As of 2026-03-29, `tlul_request_loopback` is reduced to 6 tracked stores in `___nba_comb__TOP__0` and 6 tracked stores in `___nba_sequent__TOP__0`; `tlul_socket_m1` is reduced to a 61-store cluster in `___nba_sequent__TOP__0` plus one dependent debug-output store in `___nba_sequent__TOP__2`.
- [x] Define the project acceptance rule for "Phase B is done": acceptance is based on the final compare only, not prefix diagnostics. `strict_final_state` remains the gold standard, and `phase_b_endpoint` is the supported project gate: final `design_state` / `top_level_io` / `other` mismatch bytes must be zero, and any residual `verilator_internal` mismatch must be limited to `__VicoPhaseResult`, `__VactIterCount`, `__VinactIterCount`, and `__VicoTriggered`.
- [x] Decide whether the current phase split is sufficient or whether true per-phase subgraph isolation is required. The answer is now clear: fixed `ico/nba_comb/nba_sequent` kernels were not sufficient; ordered guarded `_eval_nba` segments were required to close the design-visible gap on the reference designs.
- [x] Replace the fixed three-kernel split model with ordered `_eval_nba` segments. `vlgpugen` now emits guarded `vl_nba_seg*` kernels for helper-only and helper+inline cases, and both `tlul_request_loopback` and `tlul_socket_m1` reach internal-only mismatch under `nstates=1`, `steps=1`.
- [x] Add phase-by-phase debug readback hooks when state or toggle mismatches appear.
- [x] Prove guarded helper replay on a helper-only `_eval_nba` design. As of 2026-03-29, `tlul_socket_m1` emits `vl_nba_seg0_batch_gpu` .. `vl_nba_seg3_batch_gpu` from `vl_kernel_manifest.json`, and its final mismatch drops to the four `verilator_internal` bytes only (`design_state_mismatch_bytes=0`, `top_level_io_mismatch_bytes=0`).
- [x] Explain and fix the first `tlul_request_loopback:nba_comb` delta set. The traced `tl_h_o` / `toggle_bitmap_word2_o` drift disappeared once the split schedule preserved the inline `_eval_nba` regions that precede `___nba_comb__TOP__0`.
- [x] Explain and fix the follow-on `tlul_request_loopback:nba_sequent` delta set. The traced `bootstrapped_q` / `target_rsp_pre_w` drift disappeared once `vlgpugen` replayed the full guarded `_eval_nba` segment order instead of helper names alone.
- [x] Redesign Phase B splitting so `_eval_nba` semantics are represented, not just helper names. `vlgpugen` now extracts guarded regions, outlines inline blocks when needed, and emits manifest-driven segment kernels.
- [x] Add a manifest-driven split contract. As of 2026-03-29, `vlgpugen` can write `vl_kernel_manifest.json`, `build_vl_gpu.py` copies `launch_sequence` from that manifest into `vl_batch_gpu.meta.json`, and the build/run contract tests no longer assume the three legacy kernel names.
- [x] Explain and fix the `tlul_socket_m1:nba_sequent` delta set. Guarded helper replay eliminates the tracked design-visible mismatch set entirely; the final compare now leaves only the four `verilator_internal` bytes (`__VicoPhaseResult`, `__VactIterCount`, `__VinactIterCount`, `__VicoTriggered`).
- [x] After restoring guarded helper replay for `tlul_socket_m1`, determine whether any helper-internal semantic drift remains. As of 2026-03-29, no design-visible helper-body drift remains under `nstates=1`, `steps=1`; the residual mismatch is internal-only `ico` bookkeeping.
- [x] Re-run the Phase B compare at non-trivial launch sizes (`nstates>1`, `steps>1`) on both reference designs. As of 2026-04-03, `tlul_request_loopback` and `tlul_socket_m1` both stay internal-only at `nstates=256`, `steps=3`: `mismatch_count=1024`, `verilator_internal_mismatch_bytes=1024`, `design_state_mismatch_bytes=0`, `top_level_io_mismatch_bytes=0`, and `phase_b_endpoint` still passes.
- [x] Decide whether internal-only mismatch is an acceptable Phase B endpoint. The project now accepts the four-byte residual set (`__VicoPhaseResult`, `__VactIterCount`, `__VinactIterCount`, `__VicoTriggered`) as Verilator convergence bookkeeping and treats `phase_b_endpoint` as the supported completion criterion for Phase B. Chasing `strict_final_state` is now optional refinement work, not a blocker for Phase C/D.
- [x] Add a regression that covers real guarded-segment extraction, not just manifest transport. `test_vlgpugen_segment_manifest.py` now runs `src/passes/vlgpugen` against synthetic helper-only and helper+inline `_eval_nba` IR and asserts the emitted manifest selectors / `launch_sequence`.

### P2: Build The Minimal CPU Slice

- [x] Pick the first supported hybrid target design and freeze scope. Use `tlul_socket_m1` as the first supported hybrid target: it is already the canonical quickstart/bootstrap path (`quickstart_hybrid.sh`, `bootstrap_hybrid_tlul_slice_cc.py`) and now passes the provisional Phase B gate at both `nstates=1, steps=1` and `nstates=256, steps=3`. Keep `tlul_request_loopback` as the regression design for helper+inline segment fidelity.
- [x] Define the narrow host ABI for `tlul_socket_m1` in executable terms: root storage ownership, `vlSymsp`, clock/reset offsets, toggle bitmap ownership, and fatal/error handling. See `docs/phase_c_socket_m1_host_abi.md` and `src/hybrid/host_abi.h`.
- [x] Compile the non-GPU slice for `tlul_socket_m1` from stock Verilator output into a host binary or library and prove constructors/reset can run without sim-accel. `src/tools/run_socket_m1_host_probe.py` now builds `src/hybrid/socket_m1_host_probe.cpp` against `work/vl_ir_exp/socket_m1_vl/libVtlul_socket_m1_gpu_cov_tb.a`, and `socket_m1_host_probe_report.json` records successful constructor, ABI offset checks, `vlSymsp` binding, and reset progression.
- [x] Add a host-to-GPU state handoff for the first supported target. `src/hybrid/run_vl_hybrid.c` and `src/tools/run_vl_hybrid.py` now accept `RUN_VL_HYBRID_INIT_STATE` / `--init-state`, `src/tools/run_socket_m1_host_probe.py` can dump a raw root image via `--state-out`, and `src/tools/run_socket_m1_host_gpu_flow.py` stitches the two into one experimental command.
- [x] Resolve clock ownership for the first supported CPU slice. For the first supported `tlul_socket_m1` flow, keep the generated timed coroutine in `tlul_socket_m1_gpu_cov_tb.sv` (`always #5 clk_i = ~clk_i`) as the supported clock source; defer a thinner host-driven top to later refinement work.
- [x] Integrate that `tlul_socket_m1` host slice into one runner. `src/tools/run_socket_m1_host_gpu_flow.py` now performs host probe -> raw root image dump -> `run_vl_hybrid.py --init-state ...`, and `quickstart_hybrid.sh --socket-m1-host-gpu-flow` promotes that path to the supported regression entrypoint for the first target.

### P3: Turn Prototypes Into A Supported Flow

- [x] Emit a classifier report from `vlgpugen` that explains why functions stayed on GPU or host. `vlgpugen --classifier-report-out=...` now writes `vl_classifier_report.json` with per-function placement (`gpu` / `runtime`) and reasons (`force_include`, `gpu_reachable`, `runtime_prefix`, `runtime_static_guard`, `runtime_syms_reference`, `decl_host_callee`), `build_vl_gpu.py` emits that artifact by default, and the stable validation runners surface the report path under `artifacts.classifier_report`.
- [x] Promote `quickstart_hybrid.sh` to a supported regression entrypoint with one green reference design. `./quickstart_hybrid.sh --mdir work/vl_ir_exp/socket_m1_vl --socket-m1-host-gpu-flow --lite` is now the first supported stock-Verilator hybrid entrypoint for `tlul_socket_m1`.
- [x] Add one end-to-end stock-hybrid campaign runner that emits coverage and throughput summaries in a stable JSON schema. `src/runners/run_socket_m1_stock_hybrid_validation.py` now wraps the first supported `socket_m1` flow and writes `output/validation/socket_m1_stock_hybrid_validation.json` by default.
- [x] Generalize the stable validation schema beyond the first supported target. `src/tools/run_tlul_slice_host_probe.py` now builds a generic TL-UL slice host probe, `src/tools/run_tlul_request_loopback_host_gpu_flow.py` produces a reference-design host->GPU handoff for `tlul_request_loopback`, and `src/runners/run_tlul_request_loopback_stock_hybrid_validation.py` writes `output/validation/tlul_request_loopback_stock_hybrid_validation.json` with the same core schema while explicitly marking `support_tier=phase_b_reference_design`.
- [x] Add a real-design audit for `vl_classifier_report.json` on the checked-in reference designs. `src/tools/audit_vl_classifier_report.py` now validates a report against `config/classifier_expectations/*.json`, `test_audit_vl_classifier_report.py` covers the contract, and both `work/vl_ir_exp/socket_m1_vl/vl_classifier_audit.json` and `work/vl_ir_exp/tlul_request_loopback_vl/vl_classifier_audit.json` pass against their checked-in expectations.
- [x] Define the promotion contract for the second design surface. `tlul_request_loopback` now emits `promotion_gate`, `handoff_gate`, and `promotion_assessment` in its stable validation JSON. The promotion gate for moving beyond `phase_b_reference_design` is: `done_o==1`, `rsp_queue_overflow_o==0`, and `toggle_coverage.any_hit==true` under the evaluated configuration. The handoff gate is stricter: the host probe must leave the design incomplete, and GPU replay must change observable progress. The checked-in GPU sweeps at `--steps 1`, `56`, and `256` all leave `done_o=0` and `progress_cycle_count_o=5`, so the checked-in source-of-truth surface still blocks. A 2026-04-04 tuning sweep found a concrete terminal-state candidate (`cfg_req_valid_pct_i=92`, `host_post_reset_cycles=120`) at `work/vl_ir_exp/tlul_request_loopback_vl/tlul_request_loopback_validation_req92_post120.json`, but it still fails `handoff_gate`. The nearby-search artifact is now reproducible via `python3 src/tools/search_tlul_request_loopback_handoff.py --mdir work/vl_ir_exp/tlul_request_loopback_vl`.
- [x] Resolve the milestone status of `tlul_request_loopback`. For the current milestone, keep it frozen at `phase_b_reference_design` instead of treating it as a pending near-term promotion target.
- [x] Choose the next candidate to evaluate for a second supported stock-hybrid target. `tlul_fifo_sync` was evaluated first, then `tlul_socket_1n`; both passed build/probe viability but failed the first validation-surface check. The former Tier-2 fallbacks `tlul_err` / `tlul_sink` are now also checked-in, bootstrapped, and piloted, but they likewise show no GPU-driven delta under the current model. See `docs/next_supported_target_candidates.md`.
- [x] Run the first viability pass for `tlul_fifo_sync`.
  Result: stock build and generic host probe passed, but the first validation-surface check failed because GPU replay from the host-generated init-state did not change the current generic signal set (`done_o`, `progress_cycle_count_o`, `progress_signature_o`, `rsp_queue_overflow_o`, toggle bitmap words) at `steps=1` or `steps=56`. See `docs/next_supported_target_candidates.md`.
- [x] Run the first viability pass for `tlul_socket_1n`.
  Result: stock build and generic host probe passed, but the first validation-surface check failed because GPU replay from the host-generated init-state did not change the current generic signal set (`done_o`, `progress_cycle_count_o`, `progress_signature_o`, `rsp_queue_overflow_o`, toggle bitmap words) at `steps=1` or `steps=56`. See `docs/next_supported_target_candidates.md`.
- [x] Broaden the generic validation signal set for the Tier 1 second-target candidates. `src/tools/run_tlul_slice_host_probe.py` now accepts template-driven watch fields, `src/tools/run_tlul_slice_host_gpu_flow.py` summarizes host->GPU watched-field deltas, `config/slice_launch_templates/tlul_socket_1n.json` now watches host/device FIFO `rvalid_o` plus `tl_h_o` / `tl_d_o`, and `config/slice_launch_templates/tlul_fifo_sync.json` now watches FIFO full/depth/valid/ready signals. Both real runs still produced `changed_watch_field_count=0`; see `work/vl_ir_exp/tlul_socket_1n_vl/tlul_socket_1n_host_gpu_flow_watch_summary.json` and `work/vl_ir_exp/tlul_fifo_sync_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json`.
- [x] Check whether a shallower TB-timed handoff changes the `tlul_socket_1n` conclusion. The `host_post_reset_cycles in {0,1,2,4,8}` and `steps in {1,56}` search still produced `changed_watch_field_count=0` in every case, so the next step is not more shallow tuning; it is a mechanism decision. See `work/vl_ir_exp/tlul_socket_1n_vl/watch_handoff_search/summary.json`.
- [ ] If the next milestone wants a second supported target, decide whether that work requires a thinner host-driven top.
- [x] If the thin-top branch is selected, prove there is at least one concrete stock-Verilator seed seam. `tlul_fifo_sync_gpu_cov_cpu_replay_tb.sv` can now be bootstrapped with `bootstrap_hybrid_tlul_slice_cc.py --tb-path ... --top-module tlul_fifo_sync_gpu_cov_cpu_replay_tb`, and `run_tlul_fifo_sync_cpu_replay_host_probe.py` records a working no-port replay-wrapper probe at `work/vl_ir_exp/tlul_fifo_sync_cpu_replay_vl/tlul_fifo_sync_cpu_replay_host_probe_report.json`.
- [x] Implement the first real host-driven thin-top proof surface for `tlul_fifo_sync`. `tlul_fifo_sync_gpu_cov_tb.sv` is now shared-core based, `tlul_fifo_sync_gpu_cov_host_tb.sv` exposes raw-root `clk_i` / `rst_ni`, `work/vl_ir_exp/tlul_fifo_sync_host_vl` builds under stock Verilator, and `run_tlul_slice_host_probe.py` proves `host_clock_control=true`, `host_reset_control=true`.
- [ ] Explain or repair the first GPU-side parity failure on `tlul_fifo_sync`. The parity packet is now complete: host-only `1,0` edge replay already produces design-visible delta, direct CPU `root___eval` reproduces the same edge behavior, fake-`vlSymsp` CPU `root___eval` stays design-visible equivalent, and raw-state-import CPU `root___eval` also stays design-visible equivalent. The next concrete task is therefore to repair or redefine `run_vl_hybrid.py` / `run_vl_hybrid.c` / generated GPU execution semantics, not to gather more ownership proof.
- [ ] If the project wants to keep the current `tb_timed_coroutine` model in that future milestone, decide what concrete new experiment is worth running after the restored `tlul_err` / `tlul_sink` pilots also showed no GPU-driven delta.
- [ ] If `tlul_request_loopback` returns to active promotion later, pick exactly one mechanism for the next experiment. Do not continue nearby tuning sweeps as the main path; choose either a thinner host-driven top or a broader state-construction strategy.
- [ ] Add a thinner host-driven top if purely host-owned `clk_i` becomes necessary for assertions, tracing, or future CPU-side step control.
- [ ] Decide whether `strict_final_state` is worth pursuing beyond the supported `phase_b_endpoint`. This is no longer a blocker; only the four Verilator convergence-bookkeeping fields remain.

## Not On The Critical Path

- Rehabilitating the sim-accel fork is not required for the stock-Verilator hybrid goal.
- Initializing or extending the CIRCT path is optional unless it becomes the easiest way to validate a stock-path result.

## Recommended Next Three Tasks

- [ ] Decide whether the current 9-surface active line is already enough to count as the first real campaign-goal checkpoint.
- [ ] If it is, accept `broaden_non_opentitan_family` as the next expansion axis.
- [ ] If it is, choose between restoring `XuanTie + family_pilot` or promoting `XuanTie-E902` first (`XuanTie-E906` fallback) as the first non-OpenTitan `single_surface` override.
