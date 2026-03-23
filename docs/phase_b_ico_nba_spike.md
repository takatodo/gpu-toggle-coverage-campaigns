# Phase B spike: `___ico_sequent` / `___nba_*` split kernels

## Goal

When a single batched `_eval` is insufficient for RTL timestep fidelity, emit **separate NVPTX entry points** (e.g. combinational vs sequential phases) and launch them from the host in Verilator order.

## What to verify per design

1. Run `vlgpugen --analyze-phases <merged.ll>` after `llvm-link`, or `python3 src/tools/build_vl_gpu.py <mdir> --analyze-phases` (runs the same analysis after linking, then builds cubin).
2. Check lines `ico_reachable`, `nba_comb_reachable`, `nba_sequent_reachable`.
3. If `ico` / `nba` are **reachable from `_eval`** but **not inlined away**, names typically look like:
   - `...___ico_sequent`
   - `...___nba_comb`
   - `...___nba_sequent` (if present)

## Next implementation steps (not automated yet)

- In `vlgpugen`, optional mode `--kernel-split=ico_nba` that:
  - Keeps three subgraphs from `merged.ll`, each with its own wrapper kernel (same AoS stride).
  - Emits `vl_ico_batch_gpu`, `vl_nba_comb_batch_gpu`, … or a single module with multiple kernels.
- Host (`run_vl_hybrid` successor) launches: `ico` → `nba_comb` → `nba_sequent` per simulated cycle (or as required by the slice).

## Reference slice

Use OpenTitan TLUL `tlul_request_loopback` or `tlul_socket_m1` `merged.ll` as the first regression for `--analyze-phases` output.
