# Phase B spike: `___ico_sequent` / `___nba_*` split kernels

## Goal

When a single batched `_eval` is insufficient for RTL timestep fidelity, emit **separate NVPTX entry points** (e.g. combinational vs sequential phases) and launch them from the host in Verilator order.

## What to verify per design

1. Run `vlgpugen --analyze-phases <merged.ll>` after `llvm-link`, or `python3 src/tools/build_vl_gpu.py <mdir> --analyze-phases` (runs the same analysis after linking, then builds cubin). The Python path always writes **`mdir/vl_phase_analysis.json`** (`schema_version`, per-phase `any_reachable_from_eval`, function list). For a one-off file: `vlgpugen merged.ll --analyze-phases --analyze-phases-json=/tmp/out.json`.
2. Check stdout or JSON: per-phase `any_reachable_from_eval` and each function’s `reachable` (human log lines list `reachable=0|1` per symbol).
3. If `ico` / `nba` are **reachable from `_eval`** but **not inlined away**, names typically look like:
   - `...___ico_sequent`
   - `...___nba_comb`
   - `...___nba_sequent` (if present)

## Implementation status / next steps

- **Initial split (done):** `vlgpugen --kernel-split=phases` and `build_vl_gpu.py --kernel-split-phases` emit `vl_eval_batch_gpu` plus manifest-driven split kernels. For simple cases that is still `vl_ico_batch_gpu` + legacy `vl_nba_*`; for current reference designs it is `vl_ico_batch_gpu` + ordered guarded `vl_nba_seg*`. `vl_batch_gpu.meta.json` includes `launch_sequence`; `run_vl_hybrid.py --mdir` sets `RUN_VL_HYBRID_KERNELS` so each step runs that sequence.
- **Comparison harness (done):** `python3 src/tools/compare_vl_hybrid_modes.py <mdir> --json-out <out.json> [--dump-dir <dir>]` rebuilds both modes, runs `run_vl_hybrid.py`, compares final raw state bytes, annotates mismatches with root-field names via a local `offsetof` probe against `*_root.h`, classifies deltas into `verilator_internal` / `design_state` / `top_level_io`, and now emits `delta_from_previous_prefix` plus `first_*_delta_*` keys so each added kernel can be blamed directly.
- **Writer trace (done):** `python3 src/tools/trace_vl_field_writers.py <mdir> <field>... --json-out <out.json>` maps compare-field names back to generated Verilator C++ writer sites, including `___nba_comb__TOP__*` / `___nba_sequent__TOP__*` functions and `__Vdly*` delayed-state temporaries.
- **IR store trace (done):** `python3 src/tools/trace_vl_ir_stores.py <mdir> <function>... --fields <field>... --json-out <out.json>` maps those phase functions down to concrete LLVM `store` sites, including direct `%class...` GEPs and `%struct.anon` GEPs for CData fields.
- **Inline eval trace (done, loopback root cause):** the same IR-store tracer can target `_eval_nba` itself. On 2026-03-29, `tlul_request_loopback` showed 19 inline stores inside `_Z54Vtlul_request_loopback_gpu_cov_tb___024root___eval_nba...` that sit outside the split helper calls. See `work/vl_ir_exp/tlul_request_loopback_vl/vl_eval_nba_inline_trace.json`.
- **Current results (2026-03-29, `nstates=1`, `steps=1`):**
  - `tlul_request_loopback`: generic guarded-segment extraction now covers helper calls and inline `_eval_nba` regions. `vl_kernel_manifest.json` emits `vl_nba_seg0_batch_gpu` .. `vl_nba_seg3_batch_gpu`, with `seg1` / `seg2` tagged as `___eval_nba_inline_region:*`. The final compare now drops from `22` mismatching bytes to `4`, and all remaining bytes are `verilator_internal`: `__VicoPhaseResult`, `__VactIterCount`, `__VinactIterCount`, `__VicoTriggered`. `design_state_mismatch_bytes=0` and `top_level_io_mismatch_bytes=0`, so `ignore_verilator_internal_final_state` now passes for this design as well. See `work/vl_ir_exp/tlul_request_loopback_vl/vl_kernel_manifest.json` and `work/vl_ir_exp/tlul_request_loopback_vl/vl_hybrid_compare.json`.
  - `tlul_socket_m1`: guarded helper replay still closes the design-visible gap. `vlgpugen` emits `vl_kernel_manifest.json` with `vl_nba_seg0_batch_gpu` .. `vl_nba_seg3_batch_gpu`, corresponding to guarded wrappers around `TOP__0`, `TOP__1`, `TOP__2`, and `nba_comb__TOP__0`. The final compare remains at `4` mismatching bytes, all `verilator_internal`: `__VicoPhaseResult`, `__VactIterCount`, `__VinactIterCount`, `__VicoTriggered`. `design_state_mismatch_bytes=0` and `top_level_io_mismatch_bytes=0`, so `ignore_verilator_internal_final_state` passes here too. See `work/vl_ir_exp/socket_m1_vl/vl_kernel_manifest.json` and `work/vl_ir_exp/socket_m1_vl/vl_hybrid_compare.json`.
- **Non-trivial batch confirmation (2026-04-03, `nstates=256`, `steps=3`):**
  - `tlul_request_loopback`: the larger-batch compare stays internal-only. `mismatch_count=1024`, all bytes belong to the same four `verilator_internal` fields, and `ignore_verilator_internal_final_state` still passes. See `work/vl_ir_exp/tlul_request_loopback_vl/vl_hybrid_compare_n256_s3.json`.
  - `tlul_socket_m1`: the larger-batch compare shows the same pattern. `mismatch_count=1024`, all bytes remain in `__VicoPhaseResult`, `__VactIterCount`, `__VinactIterCount`, `__VicoTriggered`, and `ignore_verilator_internal_final_state` still passes. See `work/vl_ir_exp/socket_m1_vl/vl_hybrid_compare_n256_s3.json`.
- **Interpretation:** for both current reference designs, the remaining split mismatch is limited to Verilator convergence bookkeeping. The design-visible parity problem that motivated the spike is closed under the provisional final-state gate.
- **Interpretation:** the next decision is no longer "which phase diverges first?" but "whether the four internal bytes matter enough to require `strict_final_state` before Phase C". The tracing work remains useful as the explanation for why guarded segments were necessary.
- **Loopback root-cause refinement (2026-03-29):**
  - `launch_sequence` is ordered as `ico -> nba_comb -> nba_sequent`, but generated C++ `_eval_nba` runs `nba_sequent__TOP__0`, then additional inline NBA logic, then `nba_comb`; see `Vtlul_request_loopback_gpu_cov_tb___024root__0.cpp` and `merged.ll`.
  - Reordering the split launch sequence to `ico -> nba_sequent -> nba_comb` does **not** reduce the final mismatch: both orders still end at `22` mismatching bytes against single `_eval`.
  - The reason is not just launch order. `_eval_nba` in `merged.ll` has two semantic features that the current phase splitter drops: it guards work on `__VnbaTriggered`, and it contains helper-external inline store slices. In generated C++, `___nba_sequent__TOP__0` and `___nba_sequent__TOP__2` run only when `(1ULL & __VnbaTriggered[0])`, while the inline block and `___nba_comb__TOP__0` run only when `(3ULL & __VnbaTriggered[0])`; the split kernels call helpers unconditionally. The first inline cluster (lines `6233`-`6265` in `merged.ll`) writes `dut__DOT____Vcellout__u_rsp_source__q_o`, `dut__DOT____Vcellout__u_rsp_size__q_o`, `dut__DOT____Vcellout__u_rsp_opcode__q_o`, `dut__DOT__loopback_request_q`, and `dut__DOT__gen_intg_razwi_rsp__DOT__gen_rsp_intg__DOT__rsp` immediately before the eventual `nba_comb` call.
  - A second inline cluster (lines `6280`-`6381`) performs the `TOP__2`-like updates for `req_pending_*`, `rst_ni`, `__VdfgRegularize_he50b618e_0_1`, and `tl_d_o`. In other words, the design already disproves the assumption that phase splitting can be implemented by collecting helper functions by substring alone.
- **Socket refinement (2026-03-29):**
  - `socket_m1` does **not** show the same failure mode as `loopback`. Its generated `_eval_nba` in `merged.ll` is helper-only: `nba_sequent__TOP__0 -> nba_sequent__TOP__1 -> nba_sequent__TOP__2 -> nba_comb__TOP__0`, with no tracked inline stores between those calls. See `work/vl_ir_exp/socket_m1_vl/vl_eval_nba_inline_trace.json`.
  - That made it a clean first target for guarded segment replay. `vlgpugen` now detects this helper-only chain and emits five kernels in order: `vl_ico_batch_gpu`, `vl_nba_seg0_batch_gpu`, `vl_nba_seg1_batch_gpu`, `vl_nba_seg2_batch_gpu`, `vl_nba_seg3_batch_gpu`. The manifest is the source of truth for `launch_sequence`.
  - The result confirms the hypothesis: preserving the original `_eval_nba` helper guards removes the entire design-visible mismatch set for `socket_m1`. No `req_under_rst_seen_q`, `device_a_ready_q`, `host_pending_req_q`, `rsp_queue_q`, or debug-output drift remains in the final compare.
  - Current inference: for helper-only `_eval_nba` designs, lost trigger-guard semantics were the primary bug.
- **Loopback resolution (2026-03-29):**
  - The generalized extractor now also handles the inline-region case that originally blocked `loopback`.
  - `vl_kernel_manifest.json` now contains both guarded helper selectors and `___eval_nba_inline_region:seg*` selectors, preserving the original `_eval_nba` order.
  - With those inline regions restored, the design-visible `bootstrapped_q`, `target_rsp_pre_w`, `tl_h_o`, and `toggle_bitmap_word2_o` drift disappears from the final compare.
- **Acceptance rule (provisional):** use the final compare only. Prefix summaries are diagnostic against single-final state and are not phase-aligned pass/fail gates. Treat `strict_final_state` as the gold standard, and allow `ignore_verilator_internal_final_state` only as a temporary Phase B gate: final `design_state`, `top_level_io`, and `other` mismatch bytes must be zero; only `verilator_internal` bytes may differ.
- **Current gate status:** both `tlul_socket_m1` and `tlul_request_loopback` now pass `ignore_verilator_internal_final_state` at `nstates=1, steps=1` and `nstates=256, steps=3`. Neither design reaches `strict_final_state`; both still differ only on the same four `verilator_internal` bytes.
- **Further work:** decide whether those four internal bytes are acceptable Phase B residue or whether the project should normalize/replicate them to reach `strict_final_state`. Separately, add a regression that locks in real guarded-segment extraction, not just manifest transport, before pushing effort into Phase C.
  A concrete implementation sketch now lives in `docs/phase_b_splitter_redesign.md`.

## Reference slice

Use OpenTitan TLUL `tlul_request_loopback` or `tlul_socket_m1` `merged.ll` as the first regression for `--analyze-phases` output.
