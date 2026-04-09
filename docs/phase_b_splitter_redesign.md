# Phase B Splitter Redesign

## Problem

Status as of 2026-03-29:

- `vlgpugen` can now write `vl_kernel_manifest.json`
- `build_vl_gpu.py` copies `launch_sequence` from that manifest into `vl_batch_gpu.meta.json`
- build/run contract tests no longer assume the three legacy kernel names
- helper-only `_eval_nba` chains can now be outlined into guarded segment kernels; `tlul_socket_m1` emits `vl_nba_seg0_batch_gpu` .. `vl_nba_seg3_batch_gpu` and reaches internal-only mismatch against single `_eval`
- helper+inline `_eval_nba` chains can now also be outlined into guarded segment kernels; `tlul_request_loopback` emits `vl_nba_seg0_batch_gpu` .. `vl_nba_seg3_batch_gpu` with inline-region selectors and also reaches internal-only mismatch against single `_eval`

That groundwork removes the transport bottleneck and proves the segment model on the two reference designs. The remaining problem is no longer "can we represent ordered guarded segments?" but "how far Phase B should go beyond the provisional gate, and how to keep this behavior pinned by regression tests."

The current `--kernel-split=phases` implementation assumes three things that are now known to be false:

1. Helper-name substrings are enough to reconstruct `_eval_nba` semantics.
2. A fixed `ico -> nba_comb -> nba_sequent` launch sequence is expressive enough.
3. Split kernels may replay their assigned helpers unconditionally.

The two reference designs break those assumptions in different ways.

- `tlul_request_loopback`
  - `_eval_nba` contains `19` helper-external inline stores.
  - A mask-`3` inline block runs before the later mask-`1` `___nba_sequent__TOP__2` region.
  - This means "group into sequent vs comb" cannot preserve original order.
- `tlul_socket_m1`
  - `_eval_nba` is helper-only for the tracked mismatch fields.
  - It still guards top-level regions on `__VnbaTriggered`.
  - The split kernels replay those helpers unconditionally, so they already diverge before any helper-body bug is proven.

## Weak Point In The Current Plan

The weakest part of the current roadmap is now different from when this note was opened.

The design change landed, but one weak point still remains:

- The current extractor is only proven on the narrow linear guard pattern covered by the new regression; broader `_eval_nba` shapes may still need fresh counterexamples before generalization. Phase B itself is now considered complete at `phase_b_endpoint`; `strict_final_state` is optional refinement work for Verilator bookkeeping only.

## Proposed Model

Treat `_eval_nba` as an ordered schedule of guarded segments.

Example for `tlul_socket_m1`:

1. `if (__VnbaTriggered & 1) call ___nba_sequent__TOP__0`
2. `if (__VnbaTriggered & 3) call ___nba_sequent__TOP__1`
3. `if (__VnbaTriggered & 1) call ___nba_sequent__TOP__2`
4. `if (__VnbaTriggered & 3) call ___nba_comb__TOP__0`

Example for `tlul_request_loopback`:

1. `if (__VnbaTriggered & 1) call ___nba_sequent__TOP__0`
2. `if (__VnbaTriggered & 3) run inline block A`
3. `if (__VnbaTriggered & 1) call ___nba_sequent__TOP__2`
4. `if (__VnbaTriggered & 3) call ___nba_comb__TOP__0`

Implementation target:

- ordered segment extraction from `_eval_nba`
- one synthetic function per segment
- one GPU kernel per segment, in original order
- `launch_sequence` taken from the segment list, not from hard-coded phase names

## Minimal Viable Redesign

### 1. Extract top-level guarded segments

Add a pass in `vlgpugen` that walks `_eval_nba` and recognizes a narrow Verilator pattern:

- linear chain of `if (mask-test) { body }`
- each body is either a single helper call or an inline block ending at the next join
- the guard is a constant-mask test over `__VnbaTriggered[0]`

If the pattern is not recognized, do not emit split kernels for that design; fall back to single `vl_eval_batch_gpu`.

### 2. Outline each segment into a synthetic function

For each extracted segment, create an internal helper such as `__vlgpu_nba_seg0`.

Each synthetic helper must preserve:

- the original guard test
- the original helper call or inline instructions
- the original order relative to neighboring segments

This keeps `injectBatchKernel()` mostly unchanged: it can continue to call functions, while the difficult part moves into outlining `_eval_nba` regions into callable helpers.

### 3. Emit generic ordered kernels

Replace the fixed phase kernel table with design-dependent kernels such as:

- `vl_ico_batch_gpu`
- `vl_nba_seg0_batch_gpu`
- `vl_nba_seg1_batch_gpu`
- ...

The kernel count is now design-dependent. That is acceptable because:

- `run_vl_hybrid.py` already forwards arbitrary `launch_sequence`
- `compare_vl_hybrid_modes.py` already iterates arbitrary prefix lengths

The fixed-name assumption mainly lives in generation and tests, not in the runner.

### 4. Emit manifest-driven launch metadata

`build_vl_gpu.py` no longer hard-codes:

```json
["vl_ico_batch_gpu", "vl_nba_comb_batch_gpu", "vl_nba_sequent_batch_gpu"]
```

The next step is for `vlgpugen` to emit a manifest that includes:

- kernel order
- source segment kind: `helper` or `inline`
- optional conceptual phase tag: `ico`, `nba_sequent`, `nba_comb`
- guard summary for debugging

Then `build_vl_gpu.py` copies the emitted kernel order into `vl_batch_gpu.meta.json`.

## Acceptance Criteria

The redesign is good enough when it proves these points in order:

1. `tlul_socket_m1`
   - guarded helper replay reduces the current `84`-byte final mismatch
   - current status: satisfied for the provisional gate; only four `verilator_internal` bytes remain
2. `tlul_request_loopback`
   - segment extraction captures both helper calls and inline blocks
   - the current `22`-byte final mismatch drops after guard + inline preservation
   - current status: satisfied for the provisional gate; only the same four `verilator_internal` bytes remain
3. Tooling
   - `vl_batch_gpu.meta.json` carries a design-dependent `launch_sequence`
   - tests stop assuming exactly three fixed split kernels
   - current status: satisfied for the current extractor shape; `test_vlgpugen_segment_manifest.py` now pins helper-only and helper+inline manifest emission

## Concrete Task List

1. Keep the segment extractor narrow until a new counterexample appears, and use additional real designs to test whether the guarded-region model still holds.
2. If `strict_final_state` becomes necessary, isolate where `__VicoPhaseResult`, `__VactIterCount`, `__VinactIterCount`, and `__VicoTriggered` diverge and choose whether to normalize or replay them.
3. Otherwise, keep effort on supported-flow work and treat `phase_b_endpoint` as the closed Phase B milestone.
