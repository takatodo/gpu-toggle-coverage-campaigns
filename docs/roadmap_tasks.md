# Goal-to-Task Breakdown

## Goal

Reach the README target state: **hybrid CPU-GPU execution using the stock Verilator frontend**, with no sim-accel dependency, and enough fidelity to run representative designs with reset/step sequencing, GPU kernel launches, and toggle coverage collection in one supported flow.

## Verified Status (2026-04-03)

- Phase A is done. `build_vl_gpu.py` and `vlgpugen` build a cubin from stock Verilator `--cc` output.
- Phase B is partial. `--analyze-phases` writes `vl_phase_analysis.json`, `--kernel-split-phases` emits manifest-driven guarded `launch_sequence`, and both local reference designs (`tlul_socket_m1`, `tlul_request_loopback`) now pass `ignore_verilator_internal_final_state` under the verified compare flows `nstates=1, steps=1` and `nstates=256, steps=3`.
- Phase C is supported for the first target. `src/hybrid/host_abi.h` defines the first supported ABI, `src/tools/run_socket_m1_host_probe.py` builds a stock-Verilator host probe for `tlul_socket_m1`, `src/tools/run_socket_m1_host_gpu_flow.py` hands the host-generated root image into the GPU runner through `RUN_VL_HYBRID_INIT_STATE`, and the project now explicitly accepts the generated TB-owned timed clock as the first supported clock source for `tlul_socket_m1`.
- Phase D is minimal but real. `run_vl_hybrid.py` reads `vl_batch_gpu.meta.json`, sets `RUN_VL_HYBRID_KERNELS`, and launches the cubin. `src/runners/run_socket_m1_stock_hybrid_validation.py` now wraps the first supported `socket_m1` flow in a stable validation JSON schema that captures host probe status, toggle bitmap readback, and GPU timing.
- Phase E is a prototype. `vlgpugen` has automatic runtime/GPU classification logic, but it is still heuristic.

## Exit Criteria

- A stock-Verilator-only path exists for at least one representative design and does not depend on the sim-accel fork.
- Reset, clocking, and phase ordering are validated against a CPU or RTL reference for the supported design.
- Toggle bits or an equivalent coverage artifact are read back through the supported hybrid flow.
- CPU/GPU placement decisions are explainable enough to debug when a design fails classification.
- The supported path is reproducible from one documented command sequence.

## Priority Tasks

### P0: Make The Current State Trustworthy

- [x] Add a smoke test for `build_vl_gpu.py --analyze-phases` that asserts `vl_phase_analysis.json` schema and required keys.
- [x] Add a smoke test for `build_vl_gpu.py --kernel-split-phases` that asserts `vl_batch_gpu.meta.json` contains `launch_sequence` and cubin generation still succeeds.
- [x] Add a smoke test for `run_vl_hybrid.py --mdir` that asserts `launch_sequence` becomes `RUN_VL_HYBRID_KERNELS`.
- [x] Reconcile published status numbers with current artifacts, starting with `tlul_socket_m1` `storage_size=2112` vs older README values.
- [ ] Separate stock-Verilator status from legacy sim-accel result files so stale `returncode: 1` / `aggregate_pass: true` / `coverage_points_hit: 0` records are not read as success.

### P1: Close The Phase-Fidelity Gap

- [x] Add a regression harness that compares single `vl_eval_batch_gpu` launch against phase-split launch order and records raw state mismatches.
- [x] Extend that regression across `tlul_request_loopback` and `tlul_socket_m1`.
- [x] Localize the remaining mismatches to root fields and phase prefixes. As of 2026-03-29, both designs first diverge in `ico` on Verilator control fields (`__VicoPhaseResult`, `__VactIterCount`, `__VinactIterCount`, `__VicoTriggered`). `tlul_request_loopback` reaches its first non-internal delta at `nba_comb` (`toggle_bitmap_word2_o`, then `tl_h_o`), while `tlul_socket_m1` stays internal-only until `nba_sequent` (`req_under_rst_seen_q`). The compare JSON now exposes this directly via `delta_from_previous_prefix` and `first_*_delta_*`.
- [x] Add a writer-trace tool that maps compare-field names back to generated Verilator phase functions. As of 2026-03-29, `tlul_request_loopback` maps its first delta fields into `___nba_comb__TOP__0`, while `bootstrapped_q` / `target_rsp_pre_w` map into `___nba_sequent__TOP__0`; `tlul_socket_m1` maps `req_under_rst_seen_q`, `device_a_ready_q`, `host_pending_req_q`, and `rsp_queue_q` into `___nba_sequent__TOP__0`, with `debug_device_a_ready_o` in `___nba_sequent__TOP__2`.
- [x] Add an IR-store trace tool that maps those phase functions down to concrete LLVM `store` sites. As of 2026-03-29, `tlul_request_loopback` is reduced to 6 tracked stores in `___nba_comb__TOP__0` and 6 tracked stores in `___nba_sequent__TOP__0`; `tlul_socket_m1` is reduced to a 61-store cluster in `___nba_sequent__TOP__0` plus one dependent debug-output store in `___nba_sequent__TOP__2`.
- [x] Define the provisional acceptance rule for "Phase B is done": acceptance is based on the final compare only, not prefix diagnostics. `strict_final_state` is the gold standard, and `ignore_verilator_internal_final_state` is the temporary gate: final `design_state` / `top_level_io` / `other` mismatch bytes must be zero.
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
- [x] Re-run the Phase B compare at non-trivial launch sizes (`nstates>1`, `steps>1`) on both reference designs. As of 2026-04-03, `tlul_request_loopback` and `tlul_socket_m1` both stay internal-only at `nstates=256`, `steps=3`: `mismatch_count=1024`, `verilator_internal_mismatch_bytes=1024`, `design_state_mismatch_bytes=0`, `top_level_io_mismatch_bytes=0`, and `ignore_verilator_internal_final_state` still passes.
- [ ] Decide whether internal-only mismatch is an acceptable Phase B endpoint. Both reference designs now converge to the same four `verilator_internal` bytes; the project still needs to decide whether to normalize/replay them for `strict_final_state` or accept them as Phase B residue.
- [x] Add a regression that covers real guarded-segment extraction, not just manifest transport. `test_vlgpugen_segment_manifest.py` now runs `src/passes/vlgpugen` against synthetic helper-only and helper+inline `_eval_nba` IR and asserts the emitted manifest selectors / `launch_sequence`.

### P2: Build The Minimal CPU Slice

- [x] Pick the first supported hybrid target design and freeze scope. Use `tlul_socket_m1` as the first supported hybrid target: it is already the canonical quickstart/bootstrap path (`quickstart_hybrid.sh`, `bootstrap_hybrid_tlul_slice_cc.py`) and now passes the provisional Phase B gate at both `nstates=1, steps=1` and `nstates=256, steps=3`. Keep `tlul_request_loopback` as the regression design for helper+inline segment fidelity.
- [x] Define the narrow host ABI for `tlul_socket_m1` in executable terms: root storage ownership, `vlSymsp`, clock/reset offsets, toggle bitmap ownership, and fatal/error handling. See `docs/phase_c_socket_m1_host_abi.md` and `src/hybrid/host_abi.h`.
- [x] Compile the non-GPU slice for `tlul_socket_m1` from stock Verilator output into a host binary or library and prove constructors/reset can run without sim-accel. `src/tools/run_socket_m1_host_probe.py` now builds `src/hybrid/socket_m1_host_probe.cpp` against `work/vl_ir_exp/socket_m1_vl/libVtlul_socket_m1_gpu_cov_tb.a`, and `socket_m1_host_probe_report.json` records successful constructor, ABI offset checks, `vlSymsp` binding, and reset progression.
- [x] Add a host-to-GPU state handoff for the first supported target. `src/hybrid/run_vl_hybrid.c` and `src/tools/run_vl_hybrid.py` now accept `RUN_VL_HYBRID_INIT_STATE` / `--init-state`, `src/tools/run_socket_m1_host_probe.py` can dump a raw root image via `--state-out`, and `src/tools/run_socket_m1_host_gpu_flow.py` stitches the two into one experimental command.
- [x] Resolve clock ownership for the first supported CPU slice. For the first supported `tlul_socket_m1` flow, keep the generated timed coroutine in `tlul_socket_m1_gpu_cov_tb.sv` (`always #5 clk_i = ~clk_i`) as the supported clock source; defer a thinner host-driven top to later refinement work.
- [x] Integrate that `tlul_socket_m1` host slice into one runner. `src/tools/run_socket_m1_host_gpu_flow.py` now performs host probe -> raw root image dump -> `run_vl_hybrid.py --init-state ...`, and `quickstart_hybrid.sh --socket-m1-host-gpu-flow` promotes that path to the supported regression entrypoint for the first target.

### P3: Turn Prototypes Into A Supported Flow

- [ ] Emit a classifier report from `vlgpugen` that explains why functions stayed on GPU or host.
- [x] Promote `quickstart_hybrid.sh` to a supported regression entrypoint with one green reference design. `./quickstart_hybrid.sh --mdir work/vl_ir_exp/socket_m1_vl --socket-m1-host-gpu-flow --lite` is now the first supported stock-Verilator hybrid entrypoint for `tlul_socket_m1`.
- [x] Add one end-to-end stock-hybrid campaign runner that emits coverage and throughput summaries in a stable JSON schema. `src/runners/run_socket_m1_stock_hybrid_validation.py` now wraps the first supported `socket_m1` flow and writes `output/validation/socket_m1_stock_hybrid_validation.json` by default.
- [ ] Add a thinner host-driven top if purely host-owned `clk_i` becomes necessary for assertions, tracing, or future CPU-side step control.

## Not On The Critical Path

- Rehabilitating the sim-accel fork is not required for the stock-Verilator hybrid goal.
- Initializing or extending the CIRCT path is optional unless it becomes the easiest way to validate a stock-path result.

## Recommended Next Three Tasks

- [ ] Decide whether the four-byte internal-only mismatch must be eliminated for `strict_final_state` or can be accepted as the Phase B endpoint.
- [ ] Separate stock-Verilator status from legacy sim-accel result files so stale success/failure records stop contaminating the current project state.
- [ ] Generalize the new `socket_m1` validation runner beyond the first supported target and reuse its JSON schema for additional designs.
