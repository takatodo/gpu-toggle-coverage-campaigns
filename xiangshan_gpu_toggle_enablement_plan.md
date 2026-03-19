# XiangShan GPU Toggle Enablement Plan

## Weakest Point

The blocker for `XiangShan` is no longer "missing family selection." The weak
point is narrower: `XiangShan` was the first `generic_external_fallback`
target, but it had no `gpu_cov_tb` or `coverage_regions` manifest, so there
was no actual GPU bring-up path to validate against the frozen rule family.

## Current Direction

Use the smallest stable fallback path first:

- configuration: `mini-chisel6`
- sanity test: `hello`
- standard test: `cmark`
- wrapper: `xiangshan_gpu_cov_tb`
- precheck alias: `gpu_cov_gate`

This keeps the first bring-up on the smallest `SimTop` source and the lowest
standard workload pressure while preserving the stock `tb` contract.

For the first actual-GPU gate, do not force one giant fused `full_all`
compile. The current `gpu_cov_gate` runner now defaults to:

- `SIM_ACCEL_NVCC_FLAGS='-O0 -std=c++17 -Xptxas -O0 -gencode arch=compute_89,code=sm_89'`
- `--no-compile-full-all-only`
- `--assigns-per-kernel 5000`
- `SIM_ACCEL_NVCC_OBJECT_JOBS=2`

This keeps the path on the baseline GPU runner while avoiding an excessive
single-CUDA-unit compile on the first XiangShan pass. The gate is validating
contract correctness, not optimized throughput, so compile latency is the
first-order concern here.

## Current Facts

- Descriptor: [descriptor.yaml](~/GEM_try/rtlmeter/designs/XiangShan/descriptor.yaml)
- Existing top: [tb.v](~/GEM_try/rtlmeter/designs/XiangShan/src/common/tb.v)
- New wrapper: [xiangshan_gpu_cov_tb.sv](~/GEM_try/rtlmeter/designs/XiangShan/src/xiangshan_gpu_cov_tb.sv)
- New manifest: [xiangshan_gpu_cov_coverage_regions.json](~/GEM_try/rtlmeter/designs/XiangShan/tests/xiangshan_gpu_cov_coverage_regions.json)

The stock `tb` already provides:

- `clock` / `reset`
- UART progress through `difftest_uart_out_valid/ch`
- `+iterations`
- program load through the existing RTLMeter include contract
- `Hit Good Trap` based completion through `Difftest.v` and `tests/post.bash`

That means the first fallback wrapper can safely instantiate `tb dut();`
instead of reimplementing XiangShan runtime semantics from scratch.

## First-Pass Signal Contract

The first wrapper exports only coarse proxies:

- progress:
  `progress_cycle_count_o`, UART activity, `Hit Good Trap`
- memory path:
  `dut.top.memory.io_axi4_0_*` handshakes
- MMIO path:
  `dut.top.l_simMMIO.io_axi4_0_*` handshakes
- finish:
  UART `Hit Good Trap` detection, `dut.top._SimJTAG_exit`

This is intentionally closer to the `Vortex` first-pass contract than to a deep
microarchitectural wrapper.

## Validation Gate

The XiangShan fallback bring-up is good enough when:

1. `XiangShan:gpu_cov_gate:hello` compiles and runs through the baseline runner
2. `XiangShan:gpu_cov_gate:cmark` survives the same path
3. the manifest produces non-trivial coverage regions for:
   - `control_progress`
   - `memory_request_path`
   - `memory_response_path`
   - `mmio_path`
   - `finish_protocol`

It does not need deep region richness on the first pass.

## Current Runtime Observation

The first full-all-only XiangShan pass was structurally alive but compile-heavy:

- `kernel_generated.full_all.cu` was about `115 MiB`
- `cicc` stayed busy on the same unit for a long time before runtime

The current gate strategy therefore shifts to a partitioned first pass. The
lighter rerun has already moved to `kernel_partitions=16`, with most partition
sources landing in the `6-9.5 MiB` range, and all partition objects have now
been driven through the warm-cache/parallel-object path. The latest seqpart-
enabled rerun keeps the same partition count, emits `12` sequential-tail
`seqpart` sources, removes `kernel_generated.full_seq.cu` from the bench
compile set, and resolves the bench CUDA arch to `sm_89`. The post-codegen
bottleneck has therefore moved away from the first-launch PTX JIT and toward
the remaining native-arch `kernel_generated.link.cu` plus late `part10/part11`
compile wave.

## Recommended Next Step

1. Run [run_xiangshan_gpu_toggle_validation.py](./run_xiangshan_gpu_toggle_validation.py) on `gpu_cov_gate`.
2. If `hello` passes but `cmark` fails, keep the family in fallback scope and debug the execution contract before expanding coverage regions.
3. If both pass, refresh the candidate/features/scope packets and move `XiangShan` from `needs_gpu_cov_tb_and_manifest` to a validated fallback-ready state.
