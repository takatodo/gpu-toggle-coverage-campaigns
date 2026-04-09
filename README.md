# GPU Toggle Coverage Campaigns

GPU-accelerated RTL toggle coverage collection across multiple open-source RISC-V and SoC designs, using [RTLMeter](https://github.com/verilator/rtlmeter) and LLVM/NVPTX toolchains where applicable.

## Architecture

**Recommended path — stock Verilator → LLVM IR → cubin** (no sim-accel fork):

The **Verilator sim-accel fork** was abandoned here: its lowered CUDA / IR pipeline **does not preserve full RTL semantics** (e.g. `always_ff` reset behavior, preload stubs), so GPU toggle numbers can diverge from RTL simulation. New work uses **normal `verilator --cc`** output, `clang++ -emit-llvm`, **`vlgpugen`**, and `opt`/`llc`/`ptxas` — see README section *Experimental: Standard Verilator → LLVM IR → GPU* and `src/tools/build_vl_gpu.py`.

```
RTL (SystemVerilog)
    │
    └─[stock Verilator --cc --flatten]─→ V*.cpp
                                          │
                                  clang++-18 -emit-llvm -O1
                                          │
                                    llvm-link-18 → merged.ll
                                          │
                                  vlgpugen --storage-size=N --out=vl_batch_gpu.ll
                                          │
                                  opt-18 (+ VlGpuPasses.so) → opt -O3
                                          │
                                  llc-18 (nvptx64) → ptxas → cubin
                                          │
                                   GPU parallel simulation (AoS batched _eval)
                                          │
                                 toggle coverage bits
```

### Backend selection (RTLMeter / legacy runners)

| Backend | Description | Status |
|---------|-------------|--------|
| **Stock path** | `verilator --cc` → `vlgpugen` → `opt` → PTX/cubin | **recommended** for new GPU IR |
| `cuda_vl_ir` | sim-accel `full_comb`/`full_seq` → LLVM → cubin (inside `verilator_sim_accel_bench`) | **legacy** — semantic mismatches vs RTL |
| `rocm_llvm` | Same class of flow as `cuda_vl_ir`, AMD GPU | legacy / environment-specific |
| `cuda_circt_cubin` | CIRCT flow (`program.json` → chunked cubin) | legacy compat |

Known issues on the **legacy `cuda_vl_ir` / sim-accel** path (not claimed for stock + `vlgpugen`):

- `preload_word` stub gaps, `always_ff` conditional reset handling, and related **GPU vs RTL toggle mismatches**.

### Why stock Verilator C++ → LLVM IR

The CIRCT / `program.json` path splits assigns into comb/seq domains before IR; `program.json` assigns are **interleaved in global dependency order**, so naive splitting **corrupts execution order**.

**Stock Verilator** emits ordinary C++ (`--cc`) with consistent ordering. `clang++ -emit-llvm` lowers that to LLVM IR; **`vlgpugen`** extracts the GPU slice, stubs host/runtime calls, and emits the batch kernel. Downstream: `clang-18`, `llvm-link-18`, `llc-18`, `ptxas` (no `nvcc` for that compile chain).

## Status At A Glance

- The **minimum supported goal is already met**.
- The broader campaign goal is **partially demonstrated but not yet closed**: the active campaign line now has nine checked-in time-to-threshold comparisons, `socket_m1`, `tlul_fifo_sync`, `tlul_request_loopback`, `tlul_err`, `tlul_sink`, `tlul_socket_1n`, `tlul_fifo_async`, `xbar_main`, and `xbar_peri`, and all nine report `winner=hybrid`.
- The current supported source of truth is `output/validation/socket_m1_stock_hybrid_validation.json`.
- That JSON now also carries the normalized campaign blocks `campaign_threshold` and `campaign_measurement`.
- That `socket_m1` flow is enough to claim the README target state: stock-Verilator-only, supported host->GPU handoff, toggle readback, explainable classifier output, and documented entrypoint.
- Remaining work is **post-goal expansion or refinement**.
- The next weakest point is therefore not "can one design run," but "whether the current full ready-pool line should be accepted as the first real campaign-goal checkpoint, and which non-OpenTitan axis should come next."
- Concretely, the remaining campaign tasks are:
  - keep the current active comparison line stable under `per_target_ready`,
  - add the next comparison surface intentionally,
  - only then revisit stronger common semantics or promotion work if they help the broader KPI.
- The first checked-in packet for that comparison line is `docs/socket_m1_time_to_threshold_packet.md`.
- The CC-facing implementation packet for that line is `docs/socket_m1_time_to_threshold_execution_packet.md`.
- The schema-alignment packet for that line is `docs/socket_m1_campaign_schema_packet.md`.
- The proof-matrix packet for reject / unresolved / winner semantics is `docs/socket_m1_campaign_proof_matrix.md`.
- The completed WP0 additive-migration packet for the checked-in hybrid JSON is `docs/socket_m1_hybrid_schema_normalization_packet.md`.
- The completed WP0 implementation packet is `docs/socket_m1_hybrid_schema_wp0_execution_packet.md`.
- The first checked-in campaign-speed source of truth is `output/validation/socket_m1_time_to_threshold_comparison.json`, which currently reports `winner=hybrid` and `speedup_ratio≈15.06` for `campaign_threshold = toggle_bits_hit >= 3`.
- The second checked-in campaign surface is `output/validation/tlul_fifo_sync_time_to_threshold_comparison.json`, which currently reports `winner=hybrid` and `speedup_ratio≈1.16` on the `thin_top_reference_design` surface.
- The third checked-in campaign surface is `output/validation/tlul_request_loopback_time_to_threshold_comparison.json`, which currently reports `winner=hybrid` and `speedup_ratio≈4.87` on the frozen `phase_b_reference_design` surface.
- `work/campaign_next_kpi_audit.json` now turns that state into a machine-readable recommendation: `recommended_next_kpi=stronger_thresholds`.
- A threshold-5 trial now also exists as candidate-only evidence, not as the checked-in source of truth:
  `output/validation/socket_m1_time_to_threshold_comparison_threshold5.json` reports `winner=hybrid`, `speedup_ratio≈22.53`,
  while `output/validation/tlul_fifo_sync_time_to_threshold_comparison_threshold5.json` reports `winner=hybrid`, `speedup_ratio≈1.20`.
- That trial did **not** change the machine-readable recommendation: `work/campaign_next_kpi_audit_threshold5.json` still returns `recommended_next_kpi=stronger_thresholds`.
- `work/campaign_threshold_candidate_matrix.json` makes the promotion decision explicit:
  `threshold5` is still `candidate_only`, and the current action is `keep_current_threshold_and_define_stronger_candidate`.
- `work/campaign_threshold_headroom_experiments.json` adds the boundary evidence:
  `socket_m1` plateaus at `bits_hit=5` under the current candidate settings,
  `socket_m1 threshold=6` is unresolved,
  `tlul_fifo_sync threshold=24` is still only a weak hybrid win,
  and `tlul_fifo_sync threshold=25` is unresolved.
- `work/tlul_fifo_sync_threshold_semantics_audit.json` adds the next boundary:
  `tlul_fifo_sync` is strongest on `1`,
  still wins on the checked-in `1,0` replay depth,
  but `1,0,1` already flips the winner to baseline,
  so the next stronger threshold cannot just be a longer replay sequence.
- `work/campaign_threshold_policy_options.json` compares the remaining policy options:
  checked-in common v1, common threshold5, and the design-specific minimal-progress candidate.
  The next practical decision is whether campaign v2 may allow design-specific threshold semantics.
- `config/campaign_threshold_policies/index.json` is the checked-in scenario definition for that policy comparison.
- `config/campaign_threshold_policies/selection.json` is the checked-in policy switch for both
  `profile_name`, `allow_per_target_thresholds`, and `require_matching_thresholds`.
- `work/campaign_threshold_policy_gate.json` resolves that switch against the available policy options.
  With the current checked-in setting (`profile_name=per_target_ready`,
  `allow_per_target_thresholds=true`, `require_matching_thresholds=false`),
  the active campaign-threshold gate promotes the design-specific v2 line.
- `work/campaign_speed_scoreboard_active.json` now materializes the active comparison set selected by that gate.
- `work/campaign_next_kpi_active.json` is the policy-aware next-KPI audit for the currently selected campaign line.
- The current active scoreboard now contains nine hybrid wins:
  `socket_m1 threshold5 ≈22.53x`, `tlul_err threshold9 ≈14.06x`, `tlul_fifo_async threshold35 ≈11.23x`, `tlul_fifo_sync seq1 threshold24 ≈2.64x`, `tlul_request_loopback threshold2 ≈4.87x`, `tlul_sink threshold5 ≈10.42x`, `tlul_socket_1n threshold26 ≈8.05x`, `xbar_main threshold47 ≈12.66x`, and `xbar_peri threshold47 ≈11.70x`.
- `work/campaign_threshold_policy_preview.json` now shows the policy matrix over
  `allow_per_target_thresholds` and `require_matching_thresholds`.
  Under the current checked-in profile, `current_selection` already reaches `broader_design_count`;
  reverting either axis falls back to the common v1 line and `stronger_thresholds`.
- `work/campaign_policy_decision_readiness.json` now compresses that matrix into the policy-switch state.
  With policy already checked in, treat its `recommended_active_task` as historical context rather than the current campaign task.
- `work/campaign_policy_change_impact.json` shows the concrete before/after diff from the current checked-in line to a candidate reversion branch,
  so the remaining task is readable as keeping or narrowing the active campaign line, not as more threshold-value exploration.
- `work/campaign_threshold_policy_profiles.json` adds named policy profiles for that same decision:
  `common_v1_hold`, `per_target_blocked`, and `per_target_ready`.
- `work/campaign_third_surface_candidates.json` keeps a legacy filename but is now effectively historical for the current ready pool.
  Since `xbar_peri` is now also active, the current artifact is empty: the OpenTitan `ready_for_campaign` pool is exhausted under the current policy.
- `work/campaign_checkpoint_readiness.json` now makes the breadth question machine-readable.
  The current artifact says the checked-in line is `cross_family_checkpoint_ready`: enough surfaces, margin, and family diversity for a first checkpoint, with `OpenTitan.TLUL` and `OpenTitan.XBAR` both represented and the entire ready pool active.
- `work/campaign_post_checkpoint_axes.json` now makes the post-checkpoint axis machine-readable.
  The current recommendation is `broaden_non_opentitan_family`, with `XuanTie` first and `VeeR` as the fallback family.
- `work/campaign_non_opentitan_entry.json` now makes the first non-OpenTitan deliverable shape machine-readable.
  The current recommendation is `XuanTie + family_pilot`.
- `work/campaign_non_opentitan_entry_readiness.json` now makes that recommendation executable-or-blocked instead of aspirational.
  The current workspace is `legacy_family_pilot_failed_but_single_surface_override_ready`.
  `output/legacy_validation/xuantie_family_gpu_toggle_validation.json` is still the negative source of truth for `XuanTie + family_pilot`, but `work/xuantie_e902_gpu_cov_gate_stock_verilator_cc_bootstrap.json` and `work/xuantie_e906_gpu_cov_gate_stock_verilator_cc_bootstrap.json` prove that `XuanTie-E902` / `XuanTie-E906` already have a stock-Verilator `single_surface` override path.
  So `XuanTie + family_pilot` is not the only viable next step: the concrete decision is whether to restore the legacy bench or explicitly switch to a `single_surface` override.
- `work/campaign_non_opentitan_override_candidates.json` now makes the override branch machine-readable.
  The current recommendation is `XuanTie-E902` first, with `XuanTie-E906` as the fallback.
  `E902` is no longer only bootstrap-ready: it now has a checked-in stock-hybrid / CPU-baseline / comparison trio with `winner=hybrid`.
  `E906` has now advanced beyond pure bootstrap fallback: its default checked-in trio is still unresolved at `toggle_bits_hit >= 8`, but `output/validation/xuantie_e906_time_to_threshold_comparison_threshold2.json` proves a candidate-only `threshold=2` hybrid win (`speedup_ratio≈30.37x`).
- `work/xuantie_e906_case_variants.json` now fixes the next E906 question more tightly.
  The checked-in `cmark`, `hello`, and `memcpy` case-pat variants all plateau at `bits_hit=2`, so swapping among the current known workloads does not rescue the default `toggle_bits_hit >= 8` gate.
- `work/campaign_non_opentitan_entry_profiles.json` now turns that branch into named profiles.
  The current checked-in profile is now `xuantie_single_surface_e902`; the legacy hold profile remains `xuantie_family_pilot_hold`.
- `work/campaign_non_opentitan_entry_gate.json` is the current active outcome for that selection.
  Right now it says `single_surface_trio_ready`, which is the entry-side proof that the checked-in `XuanTie-E902` trio is ready for acceptance.
- `src/tools/set_campaign_non_opentitan_entry.py` is the operational entrypoint for that decision:
  it applies a named non-OpenTitan entry profile to `selection.json` and regenerates the active entry gate.
- `work/campaign_non_opentitan_seed_status.json` is the machine-readable summary of that checkpoint-to-seed transition.
  With the current artifacts it still reports `ready_to_accept_selected_seed`.
- `work/campaign_real_goal_acceptance_profiles.json` now turns the remaining checkpoint/seed choice into named profiles:
  `hold_checkpoint_and_seed`, `accept_checkpoint_only`, and `accept_checkpoint_and_seed`.
- `work/campaign_real_goal_acceptance_gate.json` is the current checked-in acceptance state.
  Right now it says `accepted_checkpoint_and_seed`, so the active campaign baseline is no longer "OpenTitan checkpoint ready + E902 seed ready" but "OpenTitan checkpoint accepted + `XuanTie-E902` seed accepted".
- `work/campaign_xuantie_breadth_status.json` now compresses the next XuanTie decision after that acceptance.
  The current status is `decide_threshold2_promotion_vs_non_cutoff_default_gate`: `XuanTie-E906` is still unresolved at the default `toggle_bits_hit >= 8` gate, the checked-in `cmark/hello/memcpy` sweep all plateau at `bits_hit=2`, and `threshold=2` is now proven to be the strongest ready numeric gate while `family_pilot` remains blocked.
- `work/xuantie_e906_threshold_options.json` now makes that gate claim explicit.
  It says `threshold2_is_strongest_ready_numeric_gate`, with blocked numeric thresholds `3..8`.
- `work/campaign_xuantie_breadth_profiles.json` now turns that branch into named breadth profiles.
  The current checked-in profile is now `e906_candidate_only_threshold2`; `e906_default_gate_hold` is the historical hold branch and `xuantie_family_pilot_recovery` remains the blocked fallback.
- `work/campaign_xuantie_breadth_gate.json` is the current active outcome for that selection.
  Right now it says `candidate_only_ready`, so the current E906 branch is no longer blocked on profile choice.
- `work/campaign_xuantie_breadth_acceptance_gate.json` is the checked-in acceptance state for that selected breadth step.
  Right now it says `accepted_selected_xuantie_breadth`, so the active non-OpenTitan baseline is no longer just `XuanTie-E902` seed accepted; it is `XuanTie-E902` seed accepted + `XuanTie-E906 threshold2` breadth accepted.
- `work/campaign_non_opentitan_breadth_axes.json` now compresses the next post-E906 branch.
  Right now it says `decide_continue_xuantie_breadth_vs_open_fallback_family`, with remaining same-family candidates `XuanTie-C906` / `XuanTie-C910` and fallback family `VeeR`.
- `work/campaign_non_opentitan_breadth_profiles.json` now turns that post-E906 branch into named profiles.
  The current checked-in profile is now `xuantie_continue_same_family`; the remaining ready alternative is
  `open_veer_fallback_family`.
- `work/campaign_non_opentitan_breadth_gate.json` is the current active outcome for that post-E906 branch selection.
  Right now it says `continue_same_family_ready`, so the active non-OpenTitan breadth line is no longer hold;
  it is "continue inside XuanTie".
- `work/campaign_non_opentitan_breadth_branch_candidates.json` now compares those two ready branches on the current repo state.
  The current recommendation remains `xuantie_continue_same_family` first, with `XuanTie-C906` as the first same-family design and `open_veer_fallback_family` as the fallback branch.
- `work/campaign_xuantie_same_family_step.json` now compresses the first concrete same-family step after that branch choice.
  Right now it says `decide_selected_same_family_design_candidate_only_vs_new_default_gate`: `XuanTie-C906`
  already has a candidate-only `threshold=5` hybrid win, while the default `toggle_bits_hit >= 8` line is still unresolved.
- `work/campaign_xuantie_same_family_profiles.json` now turns that step into named profiles.
  The current checked-in profile is `c906_candidate_only_threshold5`; `c906_default_gate_hold` is the historical hold branch.
- `work/campaign_xuantie_same_family_gate.json` is the current active outcome for that selected same-family step.
  Right now it says `candidate_only_ready`.
- `work/campaign_xuantie_same_family_acceptance_gate.json` is the checked-in acceptance state for that selected same-family step.
  Right now it says `accepted_selected_same_family_step`, so the active XuanTie breadth baseline is no longer just `E902 + E906`; it is `E902 + E906 + C906 threshold5`.
- `work/campaign_xuantie_same_family_next_axes.json` now compresses the next decision after that accepted same-family step.
  Right now it says `decide_continue_to_remaining_same_family_design_vs_open_fallback_family`, with `XuanTie-C910` as the remaining same-family design and `VeeR` as the fallback family.
- `work/campaign_xuantie_c910_runtime_status.json` now compresses the actual `C910` blocker after that branch choice.
  Right now it says `decide_hybrid_runtime_debug_vs_open_veer_fallback_family`: the CPU baseline is `ok`, the `O0` low-opt rebuild aborts inside `llc`, the `O1` low-opt PTX trace still stops at `before_cuModuleLoad`, and an offline `ptxas` probe now times out at `180s` without producing a cubin.
  So the strongest unresolved same-family debug path is deeper cubin-first `C910` debug, but it is no longer the current checked-in branch.
- `config/campaign_xuantie_c910_runtime/selection.json` and `work/campaign_xuantie_c910_runtime_gate.json`
  now turn that blocker into a named runtime-branch decision.
  The current checked-in profile is `open_veer_fallback_family`.
- `work/campaign_xuantie_c910_runtime_profiles.json` compares the ready alternatives for that runtime branch.
  Right now the current checked-in profile is also the recommended one, `open_veer_fallback_family`; the debug branch remains ready as a lower-priority fallback, and the summary now records `debug_tactic_recommended_next_tactic=open_veer_fallback_family`.
- `work/campaign_xuantie_c910_split_phase_trial.json` now fixes the result of the split-phase PTX/module-first trial.
  Right now it says `timed_out_before_cuModuleLoad`: the split-phase run still times out with `returncode=137`, and the last traced stage is still `before_cuModuleLoad`.
- `work/campaign_xuantie_c910_debug_tactics.json` now compresses the next concrete debug tactic under that accepted runtime-debug branch.
  Right now it recommends `open_veer_fallback_family`, with `deeper_c910_cubin_debug` kept as the fallback tactic, because the split-phase trial also failed before module load.
- `work/campaign_veer_fallback_candidates.json` now turns that fallback branch into a first concrete design choice.
  Right now it recommends `VeeR-EH1` first, with `VeeR-EH2` as the next fallback candidate, because all three VeeR `gpu_cov` compile cases are stock-Verilator bootstrap ready and `EH1` has the smallest known compile footprint.
- `work/campaign_veer_first_surface_gate.json` and `work/campaign_veer_first_surface_acceptance_gate.json`
  now fix that first VeeR step as checked-in state.
  Right now `VeeR-EH1 threshold5` is no longer pending policy discussion; it is accepted fallback-family breadth evidence.
- `work/campaign_veer_next_axes.json` now compresses the next same-family question after that accepted first VeeR surface.
  Right now it says `decide_continue_to_remaining_veer_design`, with `VeeR-EH2` next and `VeeR-EL2` as the remaining fallback inside the same family.
- `work/campaign_veer_same_family_step.json`, `work/campaign_veer_same_family_gate.json`, and
  `work/campaign_veer_same_family_acceptance_gate.json` now fix the next VeeR same-family step as checked-in state.
  Right now `VeeR-EH2 threshold4` is no longer pending policy discussion; it is accepted same-family breadth evidence.
- `work/campaign_veer_same_family_next_axes.json` now moves the active same-family question again.
  Right now it says `decide_continue_to_remaining_veer_design`, with `VeeR-EL2` as the next remaining design inside the family.
- `work/campaign_veer_final_same_family_step.json`,
  `work/campaign_veer_final_same_family_gate.json`, and
  `work/campaign_veer_final_same_family_acceptance_gate.json` now fix the last remaining VeeR design as checked-in state.
  Right now `VeeR-EL2 threshold6` is no longer pending policy discussion; it is accepted final same-family breadth evidence.
- `work/campaign_veer_post_family_exhaustion_axes.json` now moves the active question beyond the exhausted VeeR family.
  Right now it says `decide_open_next_non_veer_family_after_veer_exhaustion`, with `XiangShan` first and `OpenPiton` fallback.
- `work/xiangshan_gpu_cov_stock_verilator_cc_bootstrap.json` and `output/validation/xiangshan_cpu_baseline_validation.json`
  now establish the first XiangShan surface past bootstrap: descriptor-backed `cppSourceFiles` are enrolled,
  stock-Verilator bootstrap is `ok`, and the CPU baseline is also `ok` with `bits_hit=2`.
- `work/campaign_xiangshan_first_surface_status.json` now narrows the active XiangShan question.
  Right now it says `ready_to_finish_xiangshan_first_trio`: the current checked-in XiangShan branch is no longer
  blocked at `before_cuModuleLoad`, because the working runtime line now uses `vl_batch_gpu.cubin`
  produced by the official `nvcc --device-c PTX -> nvcc --device-link --cubin` path.
- `work/xiangshan_ptxas_probe.json` now turns that XiangShan cubin-first line into a checked-in negative probe.
  Right now the offline `ptxas -O0` attempt times out at `180s` without producing a cubin.
- `work/xiangshan_nvcc_device_link_probe.json` now fixes the first official XiangShan success path as a checked-in probe.
  `nvcc --device-c vl_batch_gpu.ptx` produces a `17M` relocatable object that keeps `STO_ENTRY vl_eval_batch_gpu`,
  and `nvcc --device-link --cubin` turns that into a `19M` executable cubin that also keeps the kernel symbol.
- `work/campaign_xiangshan_vortex_branch_resolution.json` now resolves that XiangShan/Vortex reopen loop into one stable next tactic.
  Right now it says `avoid_xiangshan_vortex_reopen_loop_keep_current_xiangshan_branch`, so the current checked-in
  branch stays `reopen_xiangshan_fallback_family`, the next tactic is `deeper_xiangshan_cubin_first_debug`,
  and the heavier cross-branch fallback is `deeper_vortex_tls_lowering_debug`.
- `work/xiangshan_ptxas_compile_only_probe.json`,
  `work/xiangshan_compile_only_smoke_trace.log`,
  `work/xiangshan_nvlink_smoke_trace.log`,
  `work/xiangshan_fatbin_smoke_trace.log`, and
  `work/xiangshan_nvcc_dlink_smoke_trace.log`
  now fix the first deeper XiangShan packaging experiments. `ptxas --compile-only` succeeds in about `42s`
  and retains `vl_eval_batch_gpu`, but direct object/fatbin loads still fail with `device kernel image is invalid`,
  while `nvlink` / `nvcc -dlink` packaged variants load the module and then fail with `named symbol not found`.
- `work/xiangshan_fatbinary_device_c_probe.fatbin`,
  `work/xiangshan_fatbinary_device_c_link_probe.fatbin`,
  `work/xiangshan_fatbinary_device_c_probe_smoke_trace.log`, and
  `work/xiangshan_fatbinary_device_c_link_probe_smoke_trace.log`
  now narrow that packaging line again: `fatbinary --device-c` keeps `vl_eval_batch_gpu` visible in the packaged image,
  but `cuModuleGetFunction(vl_eval_batch_gpu)` still reports `device kernel image is invalid`.
- `work/xiangshan_nvlink_probe.cubin` and `work/xiangshan_nvcc_dlink.fatbin`
  now narrow the executable-link side too: both linked outputs are tiny (`760B` / `840B`), symbol-less, and
  `cuobjdump --dump-resource-usage` reports only `GLOBAL:0`.
- `work/xiangshan_ptx_fatbin_probe.fatbin` and `work/xiangshan_ptx_fatbin_probe_smoke_trace.log`
  now show that the obvious PTX-JIT bypass is also blocked: the bounded smoke run still stalls at
  `before_cuModuleLoad` and times out.
- `work/campaign_xiangshan_deeper_debug_status.json` now compresses that deeper XiangShan line into one current next tactic.
  Right now it says `ready_to_finish_xiangshan_first_trio`, because the official `nvcc device-c/device-link`
  line restores a non-empty linked kernel image and the minimal runtime smoke is `ok`.
- `output/validation/xiangshan_stock_hybrid_validation.json` and
  `output/validation/xiangshan_time_to_threshold_comparison.json`
  now establish the default XiangShan trio state: stock-hybrid is `ok`, but the default
  `toggle_bits_hit >= 8` gate is unresolved because both baseline and hybrid plateau at `bits_hit=2`.
- `output/validation/xiangshan_cpu_baseline_validation_threshold2.json`,
  `output/validation/xiangshan_stock_hybrid_validation_threshold2.json`, and
  `output/validation/xiangshan_time_to_threshold_comparison_threshold2.json`
  now establish the first XiangShan candidate-only line: `winner=hybrid`, `speedup_ratio≈3.13x`.
- `work/campaign_xiangshan_first_surface_step.json` compressed the active XiangShan policy question,
  and that question is now closed in favor of the checked-in candidate-only line.
- `work/campaign_xiangshan_first_surface_gate.json` and
  `work/campaign_xiangshan_first_surface_acceptance_gate.json`
  now fix that XiangShan line as checked-in state.
  Right now the selected `threshold=2` line is `candidate_only_ready` and
  `accepted_selected_xiangshan_first_surface_step`.
- `work/openpiton_gpu_cov_stock_verilator_cc_bootstrap.json`,
  `output/validation/openpiton_cpu_baseline_validation.json`,
  `output/validation/openpiton_stock_hybrid_validation.json`, and
  `output/validation/openpiton_time_to_threshold_comparison.json`
  now establish the first OpenPiton surface past trio execution. The checked-in default shape is
  `gpu_nstates=1`, `gpu_sequential_steps=1`; both baseline and hybrid satisfy `toggle_bits_hit >= 8`,
  and the current default-gate comparison is `winner=hybrid` at `≈1.56x`.
- `work/campaign_openpiton_first_surface_step.json` now compresses the active post-XiangShan fallback question.
  Right now it says `ready_to_accept_openpiton_default_gate`.
- `work/campaign_openpiton_first_surface_gate.json` and
  `work/campaign_openpiton_first_surface_acceptance_gate.json` now fix that OpenPiton line as checked-in state.
  Right now `OpenPiton` is no longer pending policy discussion; the default-gate line is accepted next-family breadth evidence.
- `work/campaign_post_openpiton_axes.json` now moves the active question beyond accepted `OpenPiton`.
  Right now it says `decide_open_next_family_after_openpiton_acceptance`, with `BlackParrot` first and blocked `XiangShan` as the fallback branch.
- `work/campaign_post_blackparrot_axes.json` now moves the active question beyond `BlackParrot` baseline loss.
  Right now it says `decide_open_next_family_after_blackparrot_baseline_loss`, with `Vortex` first and blocked `XiangShan` as the fallback branch.
- `work/vortex_gpu_cov_stock_verilator_cc_bootstrap.json` and `output/validation/vortex_cpu_baseline_validation.json`
  now establish the first Vortex surface past bootstrap: stock-Verilator bootstrap is `ok`,
  and the CPU baseline is also `ok` with `bits_hit=4`.
- `output/validation/vortex_stock_hybrid_validation.json`,
  `output/validation/vortex_time_to_threshold_comparison.json`, and
  `output/validation/vortex_time_to_threshold_comparison_threshold4.json`
  now establish the first Vortex trio beyond pure recovery. The default line is still unresolved at
  `toggle_bits_hit >= 8`, but the checked-in `threshold=4` candidate-only line is `winner=hybrid`
  at `≈1.07x`.
- `work/campaign_vortex_first_surface_status.json` and
  `work/campaign_vortex_first_surface_step.json`
  now move Vortex out of GPU-build blocker handling and into gate policy. Right now the branch
  status is `ready_to_finish_vortex_first_trio`, and the current policy question is
  `decide_vortex_candidate_only_vs_new_default_gate`.
- `config/campaign_vortex_first_surface/selection.json`,
  `work/campaign_vortex_first_surface_gate.json`, and
  `work/campaign_vortex_first_surface_profiles.json` now fix that choice as checked-in state.
  Right now the current branch is still `debug_vortex_tls_lowering`, but the branch outcome is
  `vortex_gpu_build_recovered_ready_to_finish_trio`.
- `work/campaign_vortex_first_surface_policy_gate.json` and
  `work/campaign_vortex_first_surface_acceptance_gate.json` now close the Vortex policy task in
  checked-in state. Right now `Vortex threshold4` is accepted as candidate-only non-OpenTitan
  breadth evidence.
- `work/campaign_post_vortex_axes.json` now moves the active question past accepted `Vortex`.
  Right now it says `decide_open_next_family_after_vortex_acceptance`, with `Caliptra` first and
  `Example` as the fallback family.
- `work/caliptra_gpu_cov_stock_verilator_cc_bootstrap.json`,
  `output/validation/caliptra_cpu_baseline_validation.json`, and
  `work/campaign_caliptra_first_surface_status.json` now move the active question past
  "open Caliptra" and into the concrete blocker. Right now Caliptra bootstrap is `ok`, the CPU
  baseline is `ok`, and the current branch says
  `decide_caliptra_tls_lowering_debug_vs_open_example_fallback`: GPU codegen is blocked inside
  `llc` while lowering `GlobalTLSAddress<... @_ZN9Verilated3t_sE>`.
- `work/campaign_caliptra_debug_tactics.json` now narrows that Caliptra line again.
  Right now the checked-in build path already recovers PTX via the scoped Verilated TLS-slot bypass,
  a checked-in cubin now exists, and the stack-limit probe closes the single-kernel blocker:
  the driver accepts stack sizes up to `523712` but rejects `523744+`, while the
  monolithic kernel advertises `LOCAL_SIZE_BYTES=564320` and still fails at
  `before_first_kernel_launch` even when run at that maximum accepted stack limit.
  The line is now narrower than generic stack tuning, though: `work/caliptra_split_phase_probe/`
  shows a split-kernel manifest (`vl_ico_batch_gpu`, `vl_nba_comb_batch_gpu`,
  `vl_nba_sequent_batch_gpu`), the split compile-only probe succeeds, and the split entry kernels
  report `0 bytes stack frame`. The official `nvcc --device-c -> --device-link --cubin` line for
  that split PTX also now succeeds and yields a linked cubin with the split entry symbols, but the
  traced smoke reaches `after_first_kernel_launch` and then fails with `CUDA error 700: an illegal
  memory access was encountered`. Per-kernel smokes narrow that again: `vl_ico_batch_gpu` and
  `vl_nba_sequent_batch_gpu` complete, while `vl_nba_comb_batch_gpu` still fails, including at
  `block=1` / `block=8`. Additional split probes show `prefix330` is clean while `prefix331`
  reintroduces the fault with only the `m_axi_if__0` callseq added, a `param-only` variant runs
  cleanly, a `noarg ret-only` helper call also runs cleanly, and even a `b64 zero ret-only`
  helper call runs cleanly. A pre-`cvta` live `%rd4` ret-only helper variant, a shifted-down
  small nonzero `%rd3` ret-only variant, and a compilable small nonzero `%rd3`-derived ret-only
  variant still fault post-launch; forcing that same `%rd3`-derived small nonzero value to
  16-byte alignment flips the fault from `misaligned address` to `illegal memory access`.
  But the higher-signal truncated-after-`callseq 331` probes now show the fault is narrower:
  synthetic `16`, `%rd4`, `%rd7`, and the isolated `%rd5` truncated variants all run cleanly
  there. The newer `first_branch_merge_ret_trunc` probe also runs cleanly, while restoring only
  the first store reproduces the fault immediately. Overwriting that first-store payload with
  constant `0` or `1` runs cleanly, the branch1-only first-store variant still faults, the
  corresponding branch1-load-zero-store variant runs cleanly, but `branch1-load-mask1`,
  `branch1-predicated01`, `branch1-selp-const1`, and `first-store-masked-data` still fault.
  New `branch1-load-dead-mask-const1` and `branch1-selp-same-const1` probes both run cleanly, so
  the remaining blocker is narrower: the loaded byte has to change the first-store source bits,
  not merely be consumed before the store or participate in predicate flow. The arm-reversed
  `branch1-predicated10` probe times out before compile completes, and analogous
  `first-store-masked-data-dead-mask-const1`, `first-store-masked-data-mask1`,
  `first-store-masked-data-predicated01`, `first-store-masked-data-force-else`,
  `first-store-masked-data-selp-const1`, and `first-store-masked-data-mask1-shl8`
  probes also time out before compile completes, while `branch1-selp-same-const1`
  already runs cleanly, so predicate-only or masked-data-neighbor constantized lines are
  not the actionable branch either. The newer
  `branch1-load-mask1-shl8` probe still faults, while a same-register `branch1-load-mask1-shl8-and255`
  variant times out before link, and a semantically similar `branch1-load-mask1-sep-reg`
  probe times out in `ptxas`, a `branch1-load-xor-self-zero` probe also times out before a
  linked cubin exists, the newer `branch1-load-mask1-or1` arithmetic-constantization probe also
  times out before link, `branch1-load-mask1-shl8-sep-reg` times out while same-register
  `branch1-load-mask1-shl8` still faults, a minimal `branch1-load-mov` probe also times out
  before link, and even `branch1-alt-load` times out before link.
  The newer `branch1-load-dead-mask-zero`, `branch1-load-mask1-shr8`,
  `branch1-load-mask1-shl1`, `branch1-load-mask1-shl4`, `branch1-load-mask1-shl6`,
  `branch1-load-mask1-shl7`, `branch1-load-mask1-shl9`, `branch1-selp-const0`,
  `branch1-selp-const1-and255`,
  `branch1-selp-const513`,
  `branch1-load-mask1-shl8-and255`, `branch1-load-mask2`,
  `branch1-load-maskff`, and
  `branch1-load-mask3` probes also time out, so the actionable line is now the compilable
  nonconstant variants that keep the current branch1-load provenance. The current
  task is therefore
  `deeper_caliptra_split_m_axi_if0_first_store_compilable_branch1_load_provenance_nonconstant_loaded_byte_dependent_store_source_bits_runtime_fault_debug`,
  with `Example` kept as the fallback family.
- `src/tools/probe_vl_hybrid_stack_limit.py` is the reusable probe that established that
  `Caliptra` ceiling. Its checked-in artifact is `work/caliptra_stack_limit_probe.json`.
- `work/caliptra_nvcc_device_link_cubin_probe.json` and
  `work/caliptra_nvcc_device_link_fatbin_probe.json` now record that the cheap `nvcc --device-c`
  packaging escape hatch is not currently viable either: both compile steps time out at `240s`
  before producing an object, so the main line stays on kernel stack footprint reduction rather
  than a packaging swap.
- `work/campaign_vortex_debug_tactics.json` and
  `work/campaign_xiangshan_vortex_branch_resolution.json`
  now no longer point back into the XiangShan/Vortex reopen loop. They both read the accepted
  Vortex state and point at the post-Vortex family axis instead.
- `src/tools/run_vl_hybrid.py --trace-stages` and the rebuilt `src/hybrid/run_vl_hybrid` now provide the lightweight localization hook that established that `before_cuModuleLoad` boundary.
- `src/hybrid/Makefile` now also supports distro / WSL CUDA layouts (`/usr/lib/cuda/include`, `/usr/lib/wsl/lib`) instead of requiring a populated `/usr/local/cuda`.
- `src/tools/set_campaign_non_opentitan_breadth.py` is the operational entrypoint for that decision:
  it applies one named post-E906 breadth profile to `config/campaign_non_opentitan_breadth/selection.json`
  and regenerates the active breadth gate.
- For the current milestone, promotion-to-supported work beyond `socket_m1` is still explicitly deferred; the active campaign line is `socket_m1 + tlul_fifo_sync + tlul_request_loopback + tlul_err + tlul_sink + tlul_socket_1n + tlul_fifo_async + xbar_main + xbar_peri`, the first real checkpoint is accepted, the first non-OpenTitan seed is accepted, `XuanTie-C906 threshold5` is accepted same-family breadth evidence, the current checked-in runtime branch is `open_veer_fallback_family`, `VeeR-EH1 threshold5`, `VeeR-EH2 threshold4`, and `VeeR-EL2 threshold6` are all accepted VeeR breadth evidence, `OpenPiton` is accepted as the next non-VeeR family surface, `BlackParrot` has already failed even on its strongest checked-in candidate-only line, `XiangShan threshold2` is accepted breadth evidence, and `Vortex threshold4` is now also accepted breadth evidence; the next remaining task is `deeper_caliptra_split_m_axi_if0_first_store_compilable_branch1_load_provenance_nonconstant_loaded_byte_dependent_store_source_bits_runtime_fault_debug`, with `Example` kept as the fallback family. The current actionable line is constrained further by probe budget: `first-store-masked-data-selp-same-const1`, `first-store-masked-data-selp-const1`, `first-store-masked-data-force-else`, `first-store-masked-data-mask1-shl8`, `branch1-load-dead-mask-zero`, `branch1-load-mask1-shr8`, `branch1-load-mask1-shl1`, `branch1-load-mask1-shl4`, `branch1-load-mask1-shl6`, `branch1-load-mask1-shl8-sep-reg`, `branch1-load-mask1-sep-reg`, `branch1-selp-const2`, `branch1-selp-const3`, `branch1-selp-const129`, `branch1-selp-const0`, `branch1-selp-same-const257`, `branch1-load-xor-self-zero`, `first-store-self-load`, `branch1-load-store-plus1`, `branch1-load-mask1-or1`, and `branch1-alt-load` all time out before a linked cubin exists.
- The thin-top branch now has a stable reference surface: `output/validation/tlul_fifo_sync_stock_hybrid_validation.json` records `support_tier=thin_top_reference_design`, `acceptance_gate=thin_top_edge_parity_v1`, and `clock_ownership=host_direct_ports`.
- That means the thin-top question has changed. Host-only `1,0` edge replay on `tlul_fifo_sync_gpu_cov_host_tb` already produces design-visible delta (`progress_cycle_count_o: 6 -> 7`, `progress_signature_o: 0 -> 2654435858`, toggle bitmap words `0 -> nonzero`), and the checked-in CPU/GPU parity residuals are now internal-only. The checked-in project decision is to keep `tlul_fifo_sync` at `Tier R` for the current milestone; `thin_top_supported_v1` is kept only as a next-milestone promotion proposal in `docs/tlul_fifo_sync_promotion_packet.md`.
- Repo-wide coverage expansion beyond `socket_m1` is tracked separately in `docs/rtlmeter_coverage_plan.md`.

## Repository Structure

```
src/
├── runners/        Execution scripts (run_veer_*, run_xuantie_*, run_opentitan_*, ...)
├── scripts/        Shared utilities and test scripts
├── hybrid/         Minimal CUDA driver stub (run_vl_hybrid) for stock-Verilator cubin
├── sim_accel/      Legacy sim-accel / RTLMeter bench helpers (build_bench_bundle.py, etc.)
├── generators/     Artifact generation scripts
├── grpo/           GRPO policy scripts
├── rocm/           ROCm backend scripts
└── meta/           Inventory management

config/
├── rules/                  Toggle coverage rule definitions (input to runners)
└── slice_launch_templates/ OpenTitan TLUL slice JSON templates

docs/
├── phase_b_ico_nba_spike.md  Phase B notes (ico/nba multi-kernel direction)
└── roadmap_tasks.md          Goal-to-task breakdown and current priorities

third_party/
├── rtlmeter/   takatodo/rtlmeter fork, feature/gpu-cov (gpu_cov + gpu_cov_gate designs)
├── verilator/  optional: sim-accel fork (legacy RTLMeter bench only — not required for stock + vlgpugen)
└── circt/      llvm/circt (reference)

rtlmeter/       Python venv + requirements
work/           Build artifacts and GPU sim outputs (gitignored)
output/         Generated research artifacts (gitignored)
```

## Quick Start

`./quickstart.sh` initializes submodules, creates the RTLMeter venv, checks `nvcc`/ROCm, builds
`src/passes` (`vlgpugen`, `VlGpuPasses.so`) when LLVM-18 is present, and runs unit tests.
**Sim-accel VeeR smoke is off by default** (fork semantics unreliable); opt in with
`--legacy-sim-accel-smoke` if you still have `verilator_sim_accel_bench`.

```bash
git clone --recurse-submodules <this-repo-url>
cd gpu-toggle-coverage-campaigns

./quickstart.sh                          # checks + passes build; no sim-accel smoke
./quickstart.sh --legacy-sim-accel-smoke # optional: old VeeR cuda_vl_ir bench smoke
./quickstart.sh --skip-run               # skip step 7 entirely (no messages / no legacy smoke)
./quickstart.sh --skip-passes            # skip make -C src/passes
```

## Setup (manual)

```bash
git clone --recurse-submodules <this-repo-url>

# RTLMeter Python deps (venv path rtlmeter/venv matches quickstart.sh)
python3 -m venv rtlmeter/venv
rtlmeter/venv/bin/pip install -r rtlmeter/python-requirements.txt

# Stock Verilator GPU path: system Verilator (or any --cc output), LLVM 18, CUDA ptxas.
# See: python3 src/tools/build_vl_gpu.py <verilator-cc-dir>
#
# Legacy only: sim-accel fork + verilator_sim_accel_bench for old RTLMeter cuda_vl_ir runners.
```

## Running

```bash
# Stock Verilator → cubin (recommended)
python3 src/tools/build_vl_gpu.py <path-to-verilator--cc-output-dir> [--sm sm_89]
# Build output now also includes <mdir>/vl_classifier_report.json, a per-function GPU/runtime
# placement report from vlgpugen; <mdir>/vl_batch_gpu.meta.json points to it via classifier_report.
# Audit that report against the checked-in reference expectations:
#   python3 src/tools/audit_vl_classifier_report.py <mdir>/vl_classifier_report.json --expect config/classifier_expectations/<target>.json
# Phase B: print ___ico_sequent / ___nba_* reachability after merged.ll, then continue to cubin;
#   also writes <mdir>/vl_phase_analysis.json (machine-readable). Example:
#   python3 src/tools/build_vl_gpu.py <mdir> --analyze-phases
# Phase B multi-kernel: build_vl_gpu.py --kernel-split-phases → meta launch_sequence; run_vl_hybrid.py --mdir chains kernels per step.
#   Split builds also write <mdir>/vl_kernel_manifest.json; meta launch_sequence is copied from that manifest.
# Phase B compare harness: compare single vl_eval_batch_gpu vs phase-split launch_sequence;
#   JSON includes raw-byte mismatch counts, root-field annotations from *_root.h,
#   final-state acceptance policies, and per-prefix delta summaries (`delta_from_previous_prefix`,
#   `first_*_delta_*`); prefix comparisons are diagnostic only:
#   python3 src/tools/compare_vl_hybrid_modes.py <mdir> --json-out <out.json> [--dump-dir <dir>]
#   Current state (2026-04-03): both helper-only (`tlul_socket_m1`) and helper+inline
#   (`tlul_request_loopback`) `_eval_nba` designs can now be replayed as guarded `vl_nba_seg*`
#   kernels via `vl_kernel_manifest.json`. Both reference designs now reach the project Phase B
#   endpoint: final `design_state` / `top_level_io` / `other` mismatch is zero, and the remaining
#   internal-only bytes are restricted to `__VicoPhaseResult`, `__VactIterCount`,
#   `__VinactIterCount`, and `__VicoTriggered` (the compare policy `phase_b_endpoint` passes for
#   both). That result still holds at least through `--nstates 256 --steps 3`.
#   `strict_final_state` parity remains an optional refinement for Verilator convergence bookkeeping,
#   not a blocker for the supported CPU slice.
#   python3 src/tools/compare_vl_hybrid_modes.py <mdir> --nstates 1 --json-out <out.json>  # easier-to-read mismatch counts
#   python3 src/tools/compare_vl_hybrid_modes.py <mdir> --acceptance-policy phase_b_endpoint
# Phase B writer trace: map mismatch fields back to generated Verilator phase functions:
#   python3 src/tools/trace_vl_field_writers.py <mdir> <field> [<field> ...] --json-out <out.json>
# Phase B IR store trace: map those phase functions down to concrete LLVM store sites for the selected fields:
#   python3 src/tools/trace_vl_ir_stores.py <mdir> <mangled-function> [<mangled-function> ...] --fields <field> [<field> ...] --json-out <out.json>
# Headers should match the Verilator that generated mdir: default include is third_party/verilator/include;
# set VERILATOR_ROOT or VL_INCLUDE to override (see build_vl_gpu.verilator_include_dir). Emit-LLVM uses -std=c++20.

# Load cubin + launch vl_eval_batch_gpu (Phase D skeleton)
make -C src/hybrid
python3 src/tools/run_vl_hybrid.py --mdir <same-verilator-cc-dir> [--nstates N] [--steps S] [--patch off:byte ...]

# Same path as a quickstart-style script (checks, build_vl_gpu, hybrid binary, run + GPU timing)
./quickstart_hybrid.sh --mdir <same-verilator-cc-dir> [--steps S] [--patch off:byte ...]
# With no args, default --mdir is work/vl_ir_exp/socket_m1_vl: the script mkdirs it if missing and runs
# src/tools/bootstrap_hybrid_socket_m1_cc.py (stock Verilator --cc) when *_classes.mk is absent. Use --no-bootstrap to skip.
# After a full run, ./quickstart_hybrid.sh --fast reuses cubin + skips submodule/git and make when up to date.
# ./quickstart_hybrid.sh --analyze-phases forwards Phase B reporting into build_vl_gpu.py.
# Step 7 defaults to --nstates 256 (not 4096) to keep GPU launch light; use --nstates 4096 or --lite (64) as needed.
# First supported socket_m1 flow: quickstart host probe -> GPU handoff on the guarded-segment build.
./quickstart_hybrid.sh --mdir work/vl_ir_exp/socket_m1_vl --socket-m1-host-gpu-flow --lite

# Phase C host probe: build a stock-Verilator host binary for tlul_socket_m1 and prove
# constructor / vlSymsp / reset wiring against generated C++ output.
python3 src/tools/run_socket_m1_host_probe.py --mdir work/vl_ir_exp/socket_m1_vl
# Optional artifact:
#   --json-out work/vl_ir_exp/socket_m1_vl/socket_m1_host_probe_report.json
# Supported clock source (2026-04-03): the generated tlul_socket_m1_gpu_cov_tb still contains a
# timed clock coroutine (`always #5 clk_i = ~clk_i`), and the first supported socket_m1 flow now
# intentionally keeps that TB-owned clock instead of blocking on a thinner host-driven top.

# Supported Phase C/D glue for the first target: run the host probe, dump one raw root image,
# upload it as the GPU init-state, then summarize the first state's done/signature/toggle outputs.
python3 src/tools/run_socket_m1_host_gpu_flow.py --mdir work/vl_ir_exp/socket_m1_vl --nstates 64 --steps 1

# Supported stock-hybrid validation runner: wraps the same socket_m1 flow in a stable JSON schema
# with host probe status, toggle bitmap summary, GPU timing metrics, and artifacts.classifier_report.
python3 src/runners/run_socket_m1_stock_hybrid_validation.py --mdir work/vl_ir_exp/socket_m1_vl --nstates 64 --steps 1
# Reference-design validation runner: reuses the stable stock-hybrid schema for tlul_request_loopback,
# but marks the result as support_tier=phase_b_reference_design rather than a supported CPU slice;
# the JSON now includes promotion_gate, handoff_gate, and promotion_assessment, and currently
# freezes loopback at the reference-design tier under the checked-in template because GPU replay
# does not advance progress beyond the host-probe baseline. A tuned terminal-state candidate exists:
#   --host-post-reset-cycles 120 --host-set cfg_req_valid_pct_i=92
# which passes promotion_gate but still fails handoff_gate in a separate artifact under
# work/vl_ir_exp/tlul_request_loopback_vl/. A nearby search over req_valid_pct/post-reset/steps
# also found no handoff_gate passes; for the current milestone loopback stays a reference-design
# surface rather than a pending promotion target. Reproduce the nearby search with:
# python3 src/tools/search_tlul_request_loopback_handoff.py --mdir work/vl_ir_exp/tlul_request_loopback_vl
python3 src/runners/run_tlul_request_loopback_stock_hybrid_validation.py --mdir work/vl_ir_exp/tlul_request_loopback_vl

# Thin-top host-driven proof for tlul_fifo_sync: bootstrap the host wrapper, build the cubin,
# prove host-owned clk/reset, then run the first host-owned clock pilot.
python3 src/tools/bootstrap_hybrid_tlul_slice_cc.py \
    --slice-name tlul_fifo_sync \
    --out-dir work/vl_ir_exp/tlul_fifo_sync_host_vl \
    --tb-path third_party/rtlmeter/designs/OpenTitan/src/tlul_fifo_sync_gpu_cov_host_tb.sv \
    --top-module tlul_fifo_sync_gpu_cov_host_tb --force
python3 src/tools/build_vl_gpu.py work/vl_ir_exp/tlul_fifo_sync_host_vl
python3 src/tools/run_tlul_slice_host_probe.py \
    --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl \
    --template config/slice_launch_templates/tlul_fifo_sync.json
python3 src/tools/run_tlul_slice_host_gpu_flow.py \
    --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl \
    --template config/slice_launch_templates/tlul_fifo_sync.json \
    --target tlul_fifo_sync \
    --support-tier thin_top_seed \
    --nstates 1 \
    --host-clock-sequence 1,0 \
    --host-clock-sequence-steps 1
# Current truth: host-owned clk/reset is proven, host-only edge trace already advances progress/signature/toggles,
# and direct CPU root___eval, fake-vlSymsp root___eval, raw-state-import CPU root___eval, and GPU replay now
# all reduce to internal-only parity residuals on the checked-in `1,0` edge sequence.
# Promote that result into the stable reference validation surface with:
python3 src/runners/run_tlul_fifo_sync_stock_hybrid_validation.py --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl
# This writes output/validation/tlul_fifo_sync_stock_hybrid_validation.json with
# support_tier=thin_top_reference_design and acceptance_gate=thin_top_edge_parity_v1.
# The parity proof is summarized in `docs/tlul_fifo_sync_handoff_parity_packet.md`; the remaining product question is
# whether this reference surface should stay Tier R or be promoted further.

# VeeR family (legacy RTLMeter + sim-accel backends) — default aggregate JSON now lives under
# output/legacy_validation/, not under work/, to avoid being confused with the supported stock path.
python3 src/runners/run_veer_family_gpu_toggle_validation.py

# XuanTie family
python3 src/runners/run_xuantie_family_gpu_toggle_validation.py

# Single baseline (defaults to cuda_vl_ir — legacy sim-accel bench)
python3 src/runners/run_rtlmeter_gpu_toggle_baseline.py \
    --case VeeR-EL2:gpu_cov_gate:hello \
    --build-dir work/VeeR-EL2/gpu_cov_gate \
    --nstates 256 --gpu-reps 1
```

## Design Coverage Status

| Design | Family | Status | Rule |
|--------|--------|--------|------|
| VeeR-EL2/EH1/EH2 | VeeR | gate_validated | balanced_source_general |
| XuanTie-E902/E906 | XuanTie | actual_gpu (18/18) | balanced_source_general |
| XuanTie-C906/C910 | XuanTie | actual_gpu | balanced_source_general |
| Vortex | — | actual_gpu | balanced_source_general |
| XiangShan | — | actual_gpu | balanced_source_general |
| BlackParrot | — | actual_gpu | balanced_source_general |
| OpenPiton | — | actual_gpu | balanced_source_general |
| OpenTitan | Slice scope | slice_scope_validated | (per-slice) |
| Caliptra | Phase 4 | cpu_baseline_proven_split_linked_cubin_built_nba_comb_runtime_blocked | balanced_source_general |

## Experimental: Standard Verilator → LLVM IR → GPU

An experimental flow lives under `work/vl_ir_exp/` (see also `work/circt_exp/gen_vl_gpu_kernel.py`).

**Motivation:** The CIRCT path does not support `seq.firmem` or combinational loops, which blocks
tlul_socket_1n / crossbar-style designs. **Stock Verilator** can compile complex SystemVerilog,
including UVM. This path reuses that frontend strength to emit GPU kernels **without** the sim-accel fork.

```
RTL (SystemVerilog)
    │
    └─[stock Verilator --cc --flatten]─→ V*.cpp  (ordinary C++ simulator output)
                                              │
                                      clang++-18 -S -emit-llvm -O1
                                              │ (multiple .ll)
                                      llvm-link-18 → merged.ll
                                              │
                                  vlgpugen merged.ll --storage-size=N --out=vl_batch_gpu.ll
                                    · reachable from _eval, runtime vs GPU split
                                    · stub externs + drop host-only globals
                                    · NVPTX datalayout/triple, @fake_syms_buf, AoS kernel
                                              │
                                  opt-18 (lowerinvoke + VlGpuPasses.so) → opt -O3
                                              │
                                      llc-18 -march=nvptx64 → ptxas
                                              │
                                           cubin
```

**Status (2026-03-23, `tlul_socket_m1` storage_size rechecked locally on 2026-03-28):**

| Slice | storage_size | cubin | ns/state/cycle (65K states) |
|----------|-------------|-------|-----------------------------|
| tlul_request_loopback | 192 bytes | ✓ | ~2.6 ns |
| tlul_socket_m1 | 2112 bytes | ✓ | ~13.5 ns |

**Convergence loop and runtime safety:**

When Verilator is built with `--no-timing`, timed testbench constructs such as
`always #5 clk_i = ~clk_i` become combinational feedback loops. Then `eval_phase__ico`
stays true and the convergence loop never terminates.

1–2 are implemented in LLVM IR by **`VlPatchConvergencePass`** (`src/passes/VlGpuPasses.cpp`), run from
`build_vl_gpu.py` via `opt-18 --load-pass-plugin=... -passes=lowerinvoke,simplifycfg,vl-strip-x86-attrs,vl-patch-convergence`:

1. **Fatal block redirect:** after `VL_FATAL_MT`, rewrite the fatal block’s branch to `%exit` instead of `%body`.
2. **Single-pass threshold:** `icmp ugt i32 %N, 100` → `icmp ugt i32 %N, 0`
   (fatal after the first body iteration → at most two iterations to leave the loop).

3. **VerilatedSyms / vlSymsp:** handled in **`vlgpugen`** (generation mode): TBAA regex finds the field
   offset; `@fake_syms_buf` is stored into each state’s `vlSymsp` slot before calling `_eval`.

**Comparison vs. CIRCT path:**

| Aspect | CIRCT arc | Stock Verilator IR |
|--------|-----------|-------------------|
| `seq.firmem` | ✗ | ✓ (handled by Verilator) |
| Combinational loops | ✗ | ✓ |
| UVM | ✗ | ✓ |
| tlul_socket_m1 | ✗ (blocked on firmem) | ✓ (cubin built and run) |
| Storage size | 156 bytes (loopback) | 192 bytes (loopback), 2112 bytes (socket_m1) |
| Extern stubs | not required | `VL_FATAL_MT` + VerilatedSyms-related |

**Files:**
- `src/passes/vlgpugen.cpp` — **production** merged.ll → `vl_batch_gpu.ll` (analysis or `--out` generation)
- `src/tools/build_vl_gpu.py` — Verilator `--cc` output dir → cubin (`vlgpugen` + `opt` + `VlGpuPasses.so`)
- `src/passes/VlGpuPasses.cpp` — `vl-strip-x86-attrs`, `vl-patch-convergence` (plugin `.so`)
- `src/tools/gen_vl_gpu_kernel.py` — legacy Python path (reference / parity checks vs `vlgpugen`)
- `work/vl_ir_exp/loopback_vl/` — tlul_request_loopback: Verilator C++ / LLVM IR / cubin
- `work/vl_ir_exp/socket_m1_vl/` — tlul_socket_m1: Verilator C++ / LLVM IR / cubin
- `work/vl_ir_exp/bench_vl_sweep.cu` — NSTATES sweep benchmark (`STORAGE_SIZE` macro)

### Pipeline layout (current)

| Stage | Location | Responsibility |
|-------|----------|----------------|
| Reachability, runtime split, stubs, host globals, kernel, TBAA offset | **`vlgpugen`** (`--out`) | Replaces former `gen_vl_gpu_kernel.py` pipeline (Phase 3) |
| EH lowering | `opt -passes=lowerinvoke` | `invoke` → `call` (LLVM built-in) |
| Strip x86 / convergence CFG | `VlGpuPasses.so` | `vl-strip-x86-attrs`, `vl-patch-convergence` |

**Reference Python (parity / experiments only):**

| File | Role |
|------|------|
| `llvm_ir_parse.py` | Text IR helpers used by `gen_vl_gpu_kernel.py` |
| `llvm_stub_gen.py` | Stub text generation (Python path) |
| `vl_runtime_filter.py` | Same heuristics as `vlgpugen`’s `isRuntimeFunction` |

There is **no** `llvm_ir_patch.py`; lowering and CFG/attribute fixes run in `opt`, not ad-hoc regex passes on `.ll`.

### C++ pass migration plan

**Option A — `opt` plugin + Python orchestrator (superseded for stock-Verilator GPU IR):** was used while
stub/kernel emission lived in `gen_vl_gpu_kernel.py`. **Production now uses Option B** (`vlgpugen`) for
that stage; `opt` + `VlGpuPasses.so` are unchanged downstream.

**Option B — `vlgpugen` (production for merged.ll → `vl_batch_gpu.ll`):** LLVM API + typed IR transforms;
host-global cleanup and kernel injection live here. Build: `make -C src/passes` (links `libLLVM-18`).

**Option A vs. Option B:**

| | **Option A** (`opt` plugin + Python) | **Option B** (`vlgpugen`) |
|---|--------------------------------------|---------------------------|
| **IR representation** | Text `.ll`; Python regex/splicing + `opt` on the same file | In-memory `Module`; no string IR edits |
| **Entry commands** | `gen_vl_gpu_kernel.py` → `opt` … → `ptxas` (reference only) | `vlgpugen … --out=vl_batch_gpu.ll` → `opt` (plugin + built-ins) → `opt -O3` → `llc` → `ptxas` |
| **Reachability / stubs / kernel** | Python text IR + helpers | **`vlgpugen`** (LLVM `Module` API: BFS, stubs, globals, kernel) |
| **Build** | `python3` + optional scripts | `make -C src/passes` → `vlgpugen` + `VlGpuPasses.so` (links `libLLVM`) |
| **Pros** | Easy to diff against C++ for parity | Typed IR; production path for `build_vl_gpu.py` |
| **Cons** | Not used in default cubin build anymore | LLVM major-version upgrades require rebuild + occasional API tweaks |
| **Fit** | Legacy / diff vs `vlgpugen` | **Production** stock-Verilator path (Phase 3 complete) |

**Logic → implementation (after Phase 3):**

| Logic | Kind | Where |
|-------|------|--------|
| EH | strip exception handling | `-lowerinvoke` (`opt`) |
| x86 noise | attrs / comdat / personality | `VlStripX86AttrsPass` |
| convergence loop | CFG | `VlPatchConvergencePass` |
| stubs + reachable + kernel + TBAA offset + host globals | IR rewrite | **`vlgpugen`** (`--out`) |

**Phased rollout:**

| Phase | Status | Work |
|-------|--------|------|
| 1 | **done** | `lowerinvoke` only via `opt` in `build_vl_gpu.py` (no Python `lower_invoke_to_call`) |
| 2 | **done** | `VlStripX86Attrs` + `VlPatchConvergence` in `src/passes/VlGpuPasses.cpp` + `src/passes/Makefile` |
| 3 | **done** | `vlgpugen`: full generation (stubs, host-global removal, kernel, NVPTX module). `build_vl_gpu.py` invokes `vlgpugen` instead of `gen_vl_gpu_kernel.py`. |

**Production pipeline (current):**

```
merged.ll
    ↓ vlgpugen --storage-size=N --out=vl_batch_gpu.ll
    ↓ opt --load-pass-plugin=VlGpuPasses.so
          -passes="lowerinvoke,simplifycfg,vl-strip-x86-attrs,vl-patch-convergence"
    ↓ opt -O3 | llc -march=nvptx64 | ptxas
    ↓ cubin
```

**Verified (representative tlul slice build):** `make -C src/passes` succeeds; analysis reports eval + reachable
functions (e.g. **14** reachable, **11** GPU / **3** runtime), **vlSymsp** offset **2000** bytes; generation
stubs **6** extern calls, removes **6** host-only globals, emits `vl_batch_gpu.ll`; end-to-end cubin **~71 KiB**,
matching the previous Python generator output.

**vlgpugen usage:**

```bash
make -C src/passes
# analysis only (no --out): summary to stdout
./src/passes/vlgpugen path/to/merged.ll
# generation mode
./src/passes/vlgpugen path/to/merged.ll --storage-size=N --out=vl_batch_gpu.ll
```

**LLVM version bumps:**

Update the tool paths in `build_vl_gpu.py` (`CLANG` / `LLVMLINK` / `OPT` / `LLC`) and rebuild `vlgpugen` / `VlGpuPasses.so` against the same LLVM. When bumping LLVM, also watch:
- `_clean_param_type` attribute lists — new LLVM attrs can break stub parsing
- `detect_vlsyms_offset` `"any pointer"` pattern — TBAA shape changes can mis-detect offsets
- `NVPTX_DATALAYOUT` — must match the new LLVM version’s expectations

## Goal: Hybrid CPU-GPU Architecture

The long-term goal is **hybrid CPU–GPU execution using the stock Verilator frontend**:
no sim-accel fork, and broad design coverage including UVM, `seq.firmem`, and combinational loops.

```
CPU (host)                          GPU (device)
─────────────────────────────────   ───────────────────────────────────
constructors / initial values       ___ico_sequent  (combinational eval)
rst_n drive / reset sequencing      ___nba_sequent  (sequential assigns)
clk toggle (write all NSTATES)  →   eval kernel × NSTATES threads
toggle bit readback             ←
assertions, tracing (stub OK)
```

**Target build flow:**

```
verilator --cc --flatten
    │
    ├─ inject CXX="clang++ -emit-llvm" into Makefile
    │       ↓
    │   merged.ll
    │       ↓ classify functions
    │   GPU: ico_sequent / nba_sequent
    │        (single pointer arg, no unsafe extern side effects)
    │       ↓
    │   vlgpugen → opt/llc/ptxas → cubin
    │
    └─ CPU: init / clk drive / collect
            ↓
        plain clang++ → host binary
            ↓
    Hybrid runtime (load host binary + cubin)
```

**Roadmap — steps from today’s pipeline to hybrid runtime**

| Phase | What exists / what to build | Outcome |
|-------|-----------------------------|---------|
| **A — done** | `build_vl_gpu.py`: Verilator `--cc` → `.ll` → **`vlgpugen`** → `opt` + `VlGpuPasses.so` → cubin | Single **batch `_eval`** kernel over many states (AoS); runtime/host calls stubbed; `VlPatchConvergence` for `--no-timing` TB loops |
| **B — complete at supported endpoint** | `vlgpugen --analyze-phases`, manifest-driven guarded `vl_nba_seg*` kernels, `build_vl_gpu.py --kernel-split-phases`, compare tooling, and `run_vl_hybrid.py` launch sequencing exist; both reference designs now pass `phase_b_endpoint`, including `nstates=256, steps=3` compare runs | Reduces semantic gap vs event-driven RTL sim; remaining optional work is `strict_final_state` refinement on Verilator bookkeeping only |
| **C — supported (first target)** | `src/hybrid/host_abi.h` and `docs/phase_c_socket_m1_host_abi.md` pin the first target ABI (`tlul_socket_m1`), `src/tools/run_socket_m1_host_probe.py` proves constructor / `vlSymsp` / reset behavior against generated C++ output, and `src/tools/run_socket_m1_host_gpu_flow.py` plus `./quickstart_hybrid.sh --socket-m1-host-gpu-flow` provide the first supported host->GPU handoff. The supported clock source is the timed coroutine already embedded in `tlul_socket_m1_gpu_cov_tb` | One stock-Verilator design now has a supported construction/reset/handoff path; future refinement is a thinner host-driven top, not a blocker for the first flow |
| **D — minimal implemented** | CUDA Driver stub loads `cubin`, supports repeated `--steps`, optional patches, and honors `launch_sequence` from `vl_batch_gpu.meta.json`; `src/runners/run_socket_m1_stock_hybrid_validation.py` emits the supported validation JSON, `src/runners/run_tlul_request_loopback_stock_hybrid_validation.py` reuses the schema for a reference-design validation surface, and `src/runners/run_tlul_fifo_sync_stock_hybrid_validation.py` now adds a thin-top reference surface | End-to-end toggle campaign without sim-accel; replaces ad-hoc `bench_vl_sweep.cu`-style harnesses |
| **E — prototype** | `vlgpugen` already merges CallGraph hints with `isRuntimeFunction`, now writes `vl_classifier_report.json`, and the stable validation surfaces expose that artifact path; `src/tools/audit_vl_classifier_report.py` plus `config/classifier_expectations/*.json` now pin the checked-in `socket_m1` / `tlul_request_loopback` reports, but the classifier remains heuristic | Scales beyond hand-tuned `is_runtime` lists while keeping placement decisions inspectable |

Concrete task tracker: [docs/roadmap_tasks.md](docs/roadmap_tasks.md). Phase C ABI draft for the first supported target: [docs/phase_c_socket_m1_host_abi.md](docs/phase_c_socket_m1_host_abi.md).
Status source-of-truth map: [docs/status_surfaces.md](docs/status_surfaces.md).
Input / output artifact map: [docs/input_output_map.md](docs/input_output_map.md).
Thin-top branch design note: [docs/tlul_fifo_sync_thin_top_design.md](docs/tlul_fifo_sync_thin_top_design.md).
Thin-top promotion decision packet: [docs/tlul_fifo_sync_promotion_packet.md](docs/tlul_fifo_sync_promotion_packet.md).

**Current expansion status:** the first supported target remains `tlul_socket_m1`. `tlul_request_loopback`
is intentionally frozen at `phase_b_reference_design` for the current milestone. The next-second-target search
has already eliminated the naive current-model path: `tlul_fifo_sync`, `tlul_socket_1n`, `tlul_err`, and
`tlul_sink` all now pass stock build plus generic host probe, but every checked-in host->GPU pilot still leaves
the observed outputs unchanged under the current `tb_timed_coroutine` ownership model. For `tlul_socket_1n`,
broader observability (`rvalid_o`, `tl_h_o`, `tl_d_o`) and shallower handoff points
(`host_post_reset_cycles=0,1,2,4,8`) still produced no watched-field delta beyond the host baseline. For
`tlul_err` and `tlul_sink`, restoring checked-in `*_gpu_cov_tb.sv` sources and running the first host->GPU
pilot moved them to build+probe status, but those pilots also produced `changed_watch_field_count=0` and no
output delta beyond the host baseline. The repeatable feasibility audit at
`work/second_target_feasibility_audit.json` therefore reduces the real branch choice to two options: either
continue the thinner host-driven top branch on `tlul_fifo_sync`, or defer second-target work again. That
thin-top branch is no longer just a seed seam: `work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_probe_report.json`
proves `clock_ownership=host_direct_ports`, `host_clock_control=true`, and `host_reset_control=true`, while
`output/validation/tlul_fifo_sync_stock_hybrid_validation.json` now captures the checked-in `1,0` edge result as
`support_tier=thin_top_reference_design`. The corresponding `thin_top_edge_parity_v1` gate passes because
host `eval_step`, direct CPU `root___eval`, fake-`vlSymsp` CPU `root___eval`, raw-state-import CPU `root___eval`,
and GPU replay all reduce to internal-only parity residuals on that same edge sequence. For the current milestone,
the project still takes the defer branch explicitly and keeps supported stock status `socket_m1`-only; the open
question is promotion policy, not whether the thin-top reference surface works.

**Phase D (minimal, implemented):** after `build_vl_gpu.py`, `vl_batch_gpu.meta.json` records `cubin`, `storage_size`, `sm`, `schema_version`. Build and run the CUDA Driver stub:

```bash
make -C src/hybrid    # produces src/hybrid/run_vl_hybrid (needs CUDA headers + libcuda)
python3 src/tools/run_vl_hybrid.py --mdir <verilator-cc-dir> [--nstates 4096]
```

This loads `vl_batch_gpu.cubin`, zero-fills device storage (`nstates * storage_size`), and launches `@vl_eval_batch_gpu` (grid/block layout matches the LLVM kernel). Use **`--steps`** and **`--patch global_offset:byte`** on `run_vl_hybrid.py` to repeat launches with host-injected bytes (minimal CPU time axis), or **`--init-state path.bin`** to seed device memory from a host-generated raw root image. The first checked-in CPU-side proof is `src/tools/run_socket_m1_host_probe.py`; the first supported host->GPU handoff is `src/tools/run_socket_m1_host_gpu_flow.py`; `./quickstart_hybrid.sh --socket-m1-host-gpu-flow` is the first supported entrypoint for that path; `src/tools/run_tlul_slice_host_probe.py` now generalizes raw TL-UL slice initialization for reference designs; `src/tools/run_tlul_slice_host_gpu_flow.py` adds watch-field-aware candidate summaries for second-target triage; `src/runners/run_socket_m1_stock_hybrid_validation.py` remains the supported validation runner; `src/runners/run_tlul_request_loopback_stock_hybrid_validation.py` reuses that schema for a `phase_b_reference_design` surface; and `src/runners/run_tlul_fifo_sync_stock_hybrid_validation.py` now provides a thin-top reference-design surface. See `src/hybrid/host_abi.h`, `docs/phase_c_socket_m1_host_abi.md`, and `docs/status_surfaces.md`.

For repo-wide expansion beyond the minimum goal, `python3 src/tools/audit_rtlmeter_ready_scoreboard.py --json-out work/rtlmeter_ready_scoreboard.json` is now the source-of-truth scoreboard for the OpenTitan `ready_for_campaign` set. As of 2026-04-05, that scoreboard reads `Tier S=1` (`tlul_socket_m1`), `Tier R=8` (`tlul_err`, `tlul_fifo_async`, `tlul_request_loopback`, `tlul_fifo_sync`, `tlul_sink`, `tlul_socket_1n`, `xbar_main`, `xbar_peri`), `Tier B=0`, `Tier T=0`, and `Tier M=0`.

`python3 src/tools/audit_rtlmeter_expansion_branches.py --scoreboard work/rtlmeter_ready_scoreboard.json --feasibility work/second_target_feasibility_audit.json --json-out work/rtlmeter_expansion_branch_audit.json` now turns that scoreboard plus the second-target feasibility audit into objective-oriented branch recommendations. With the current artifacts, there is no remaining near-term raw tier-count gain on the `tb_timed_coroutine` path, `maximize_second_r_or_s_candidate` now also resolves to `defer_second_target` because `tlul_fifo_sync` is already `Tier R`, and `minimize_delivery_risk` remains `defer_second_target`. The next expansion decision is therefore whether to promote `tlul_fifo_sync` beyond `Tier R`, not whether the project has a second `Tier R/S` candidate at all.

**Per-launch cost:** one launch = one `_eval` per `nstates` slot; time ~ **(_eval work) × nstates × steps** (design-dependent, not “one cycle”). Lighten with smaller `--cc` / TB, lower `--nstates` / `--steps`, or `--lite`; profile with `nsys` if needed. **Shorter `_eval` IR:** `build_vl_gpu.py --clang-O O3` (or `quickstart_hybrid.sh --fast-sim`) re-emits `.ll` with heavier clang opt; rebuild with `--force` or change opt level (tracked via `mdir/.vl_gpu_clang_opt`).

**WSL2:** If `nvidia-smi` works but `run_vl_hybrid` fails with CUDA error 100 (no device), prepend the host driver library path: `export LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH` — `run_vl_hybrid.py` and `quickstart_hybrid.sh` do this automatically when `/usr/lib/wsl/lib/libcuda.so.1` exists.

**Wall clock:** By default `run_vl_hybrid` uses **one** `cuCtxSynchronize()` after all `--steps` (fewer host–GPU round trips). For per-step sync (old behavior), set `RUN_VL_HYBRID_SYNC_EACH_STEP=1`. For a one-off untimed launch to hide first-kernel latency, set `RUN_VL_HYBRID_WARMUP=1`.

**Phase B spike:** `vlgpugen --analyze-phases <merged.ll>` reports whether `___ico_sequent` / `___nba_comb` / `___nba_sequent` appear reachable from `_eval`. See [docs/phase_b_ico_nba_spike.md](docs/phase_b_ico_nba_spike.md).

**Phase E prototype:** `vlgpugen` uses LLVM **CallGraph**-based callee hints merged with `isRuntimeFunction` (see `classifyRuntimeFunctions` in `vlgpugen.cpp`).

Dependencies: **B** may feed into **C** (what must stay on host). **D** can start with a minimal host that only drives clocks and collects toggles before full assertion parity.

**Benefits:**

| Aspect | sim-accel fork | **Hybrid (target)** |
|--------|----------------|---------------------|
| sim-accel dependency | required | none |
| UVM / firmem | ✗ | ✓ (stock Verilator) |
| Combinational loops | ✗ | ✓ |
| GPU region selection | hard-coded in fork | structural analysis / automation |
| Applicability | validated designs (VeeR, XuanTie, …) | arbitrary SystemVerilog |

## Known Limitations

- **Legacy `cuda_vl_ir` / sim-accel fork:** RTL vs GPU toggle mismatch (e.g. `preload_word`, `always_ff`
  conditional reset) — **this is why sim-accel is not the recommended path**; use stock Verilator + `vlgpugen`.

## Prerequisites

- CUDA-capable GPU (sm_80+) or ROCm GPU (for cubin execution and `ptxas` / drivers)
- Python 3.10+
- **Stock GPU IR path:** LLVM 18 (`clang++-18`, `llvm-link-18`, `opt-18`, `llc-18`), `ptxas`, `make -C src/passes`
- **Legacy RTLMeter bench:** `third_party/verilator/bin/verilator_sim_accel_bench` (sim-accel fork) — optional
