# Phase C ABI: `tlul_socket_m1`

## Scope

This note freezes the first supported CPU-slice target to `tlul_socket_m1`.

Reason:

- it is already the canonical quickstart/bootstrap path
- it passes the provisional Phase B gate at `nstates=1, steps=1`
- it also passes the same gate at `nstates=256, steps=3`
- keeping `tlul_request_loopback` as the harder helper+inline regression lets Phase B and Phase C move independently

## Storage Contract

One state is the raw byte image of `Vtlul_socket_m1_gpu_cov_tb___024root`.

- `storage_size = 2112`
- AoS stride = `storage_size`
- state `k` begins at `storage_base + k * storage_size`

For the minimal supported flow:

- host owns allocation / initialization of the per-state byte image
- GPU kernels mutate that byte image in place
- host may patch bytes before launches and read back bytes after launches

## Required Byte Offsets

These offsets were probed from `work/vl_ir_exp/socket_m1_vl/Vtlul_socket_m1_gpu_cov_tb___024root.h`.

- `cfg_valid_i`: `0`
- `done_o`: `1`
- `clk_i`: `2`
- `rst_ni`: `3`
- `cfg_reset_cycles_i`: `172`
- `cfg_signature_o`: `196`
- `toggle_bitmap_word0_o`: `296`
- `toggle_bitmap_word1_o`: `300`
- `toggle_bitmap_word2_o`: `304`
- `vlSymsp`: `2040`

These values are mirrored in [host_abi.h](/home/takatodo/gpu-toggle-coverage-campaigns/src/hybrid/host_abi.h).

## Ownership Rules

### Host-owned fields

The host slice is responsible for writing:

- configuration inputs such as `cfg_valid_i` and `cfg_reset_cycles_i`
- reset/control bytes such as `rst_ni`
- any campaign-specific seed/config words before the first GPU launch

The `clk_i` offset stays in the ABI because it is part of the serialized root image and still
matters for diagnostics, but the first supported flow does **not** treat it as a host-owned,
step-by-step control field.

### GPU-owned fields

The GPU path is responsible for producing:

- `done_o`
- `cfg_signature_o`
- `toggle_bitmap_word[0..2]_o`
- the rest of the design-visible state mutated by the Verilator `_eval` path

### `vlSymsp`

`vlgpugen` writes a fake `vlSymsp` pointer before each GPU launch.

That means:

- device storage must treat byte range `[2040, 2048)` as GPU-scratch ABI, not stable serialized state
- any future CPU-side Verilator helper call must rebind `vlSymsp` after copying state back to host memory
- the minimal CPU slice should not assume GPU-produced `vlSymsp` bytes are reusable on the host

## Minimal Host Responsibilities

For the first supported hybrid flow, the CPU slice only needs to do four things:

1. initialize per-state storage and config words
2. construct a valid post-reset root image and hand it off to the timed testbench clock already embedded in `tlul_socket_m1_gpu_cov_tb`
3. launch the existing GPU kernel chain for the state batch
4. read back `done_o` and toggle bitmap words after each step sequence

This keeps Phase C narrow:

- no attempt to make `vlSymsp` or arbitrary host helpers persistent across device launches
- no recovery ABI for fatal/error paths
- no multi-design generalization yet

## Error Handling

The first supported flow is process-fatal.

- CUDA Driver API failures abort the process
- host-side Verilator helper failures abort the process
- no resumable error ABI is defined yet

This matches the current `run_vl_hybrid` behavior and is good enough for the first supported target.

## Current Proof Point

`src/tools/run_socket_m1_host_probe.py` now builds and runs a checked-in host probe against
`work/vl_ir_exp/socket_m1_vl/`:

```bash
python3 src/tools/run_socket_m1_host_probe.py \
  --mdir work/vl_ir_exp/socket_m1_vl \
  --json-out work/vl_ir_exp/socket_m1_vl/socket_m1_host_probe_report.json
```

The current report proves:

- constructors run with a host-owned `vlSymsp`
- all ABI offsets in [host_abi.h](/home/takatodo/gpu-toggle-coverage-campaigns/src/hybrid/host_abi.h) match the generated root layout
- reset can be driven from host memory without sim-accel glue

Representative result (2026-04-03):

- `constructor_ok = true`
- `abi_ok = true`
- `vl_symsp_bound = true`
- `sim_time = 60`
- `drained_events = 12`
- `debug_reset_cycles_remaining_o = 0`

See [socket_m1_host_probe_report.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/socket_m1_vl/socket_m1_host_probe_report.json).

## Clock Ownership Decision

The generated `tlul_socket_m1_gpu_cov_tb` still contains a timed clock coroutine:

- `always #5 clk_i = ~clk_i` in the original TB
- `__VdlySched.delay(5ULL, ...)` in generated C++

The weakest point in the earlier plan was treating this as an unresolved mystery. It is not a
mystery; it is a scope decision. For the **first supported** stock-Verilator hybrid flow, the
project now keeps that TB-owned timed clock and treats a thinner host-driven top as follow-on work.

Reason:

- this keeps one canonical `tlul_socket_m1_gpu_cov_tb` path across Verilator `--cc`, host probe, and GPU build
- Phase B parity is already established on that exact top
- introducing a second host-driven wrapper top would create another semantic surface before the
  first supported flow is stabilized

Deferred follow-on:

- if assertions/tracing or cycle-accurate host control later require it, add a thinner host-driven
  top as a separate Phase C refinement rather than blocking the current supported path

## Supported Combined Flow

The repo now has a supported one-command handoff from the checked-in host probe into the GPU runner:

```bash
python3 src/tools/run_socket_m1_host_gpu_flow.py \
  --mdir work/vl_ir_exp/socket_m1_vl \
  --nstates 64 \
  --steps 1 \
  --json-out work/vl_ir_exp/socket_m1_vl/socket_m1_host_gpu_flow_summary.json
```

Or through the quickstart entrypoint:

```bash
./quickstart_hybrid.sh --mdir work/vl_ir_exp/socket_m1_vl --socket-m1-host-gpu-flow --lite
```

What it does:

1. runs `run_socket_m1_host_probe.py --state-out ...`
2. passes that raw root image into `run_vl_hybrid.py --init-state ...`
3. dumps the final GPU state and summarizes `done_o`, `cfg_signature_o`, and `toggle_bitmap_word[0..2]_o`

Representative result (2026-04-03):

- host probe still reports `constructor_ok = true`, `abi_ok = true`
- GPU launch succeeds with `nstates = 64`, `steps = 1`
- summarized final outputs are emitted in [socket_m1_host_gpu_flow_summary.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/socket_m1_vl/socket_m1_host_gpu_flow_summary.json)

This is useful because it proves the byte-image handoff works. It is **not** yet the final supported
multi-design flow, but it **is** now the first supported `tlul_socket_m1` flow. The current
clock source is intentionally the timed coroutine embedded in the generated testbench.

For a stable validation/reporting entrypoint on top of the same flow, use:

```bash
python3 src/runners/run_socket_m1_stock_hybrid_validation.py \
  --mdir work/vl_ir_exp/socket_m1_vl \
  --nstates 64 \
  --steps 1
```

This writes `output/validation/socket_m1_stock_hybrid_validation.json` by default and adds:

- host probe pass/fail summary
- toggle bitmap coverage summary
- parsed GPU timing / throughput metrics

## Candidate Host Compile Scope

The first CPU-slice attempt does not need the whole Verilator tree. The current generated sources suggest
this minimal host-side scope:

- `Vtlul_socket_m1_gpu_cov_tb.cpp`
  - constructor
  - destructor
  - `eval_step()`
  - `eventsPending()`
  - `nextTimeSlot()`
  - `final()`
- `Vtlul_socket_m1_gpu_cov_tb__Syms__Slow.cpp`
  - symbol-table construction and `TOP.__Vconfigure(true)`
- `Vtlul_socket_m1_gpu_cov_tb___024root__Slow.cpp`
  - `__Vconfigure(bool)`
- any additional generated unit required to satisfy the above link closure

For the minimal supported flow, the host binary only needs to prove:

- a host-owned `Vtlul_socket_m1_gpu_cov_tb__Syms` can exist
- the top/root object can be constructed
- reset and configuration can be established from host memory without sim-accel glue
- CPU-side initialization can coexist with the existing GPU kernel chain
