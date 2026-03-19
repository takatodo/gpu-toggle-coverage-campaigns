# XiangShan GPU Toggle Readiness

## Summary

- Weakest point: `XiangShan` is no longer blocked on missing artifacts, plain
  Verilator viability, or sim-accel dead coverage. The patched `gpu_cov_gate`
  actual-GPU path now closes on both `hello` and `cmark` at `17/18` with
  `dead_region_count=0`; the only remaining partial is the `finish_protocol`
  fail-side word, which is naturally unhit under the current pass-path
  workloads.
- Current runtime strategy: `gpu_cov_gate` now uses the lighter validation
  profile (`SIM_ACCEL_NVCC_FLAGS='-O0 -std=c++17 -Xptxas -O0 -gencode arch=compute_89,code=sm_89'`,
  `--no-compile-full-all-only`, `--assigns-per-kernel 2500`,
  `SIM_ACCEL_NVCC_OBJECT_JOBS=2`) and validation-first `nstates=1`.
- Current direction: treat `XiangShan` as actual-GPU validated under
  `balanced_source_general`, keep the current partial `finish_protocol` note as
  workload-shaped rather than blocker-shaped, and move the next scope-expansion
  focus to `BlackParrot`.

## Current Status

| Item | Status | Evidence | Result |
|---|---|---|---|
| `gpu_cov` wrapper added | completed | [xiangshan_gpu_cov_tb.sv](~/GEM_try/rtlmeter/designs/XiangShan/src/xiangshan_gpu_cov_tb.sv) | coarse wrapper now exists and reuses `tb` directly |
| `coverage_regions` manifest added | completed | [xiangshan_gpu_cov_coverage_regions.json](~/GEM_try/rtlmeter/designs/XiangShan/tests/xiangshan_gpu_cov_coverage_regions.json) | coarse `control_progress`, memory, MMIO, and finish groups are defined |
| `gpu_cov/gpu_cov_gate` descriptor entries added | completed | [descriptor.yaml](~/GEM_try/rtlmeter/designs/XiangShan/descriptor.yaml) | `mini-chisel6 + hello/cmark` fallback path is now explicit |
| static candidate packet refresh | completed | [rtlmeter_design_gpu_toggle_candidates.json](./rtlmeter_design_gpu_toggle_candidates.json) | `priority=high`, `readiness=ready_for_gpu_toggle` |
| static feature/assignment refresh | completed | [rtlmeter_design_toggle_features.json](./rtlmeter_design_toggle_features.json), [rtlmeter_design_toggle_rule_assignments.json](./rtlmeter_design_toggle_rule_assignments.json) | `feature_family=wrapper_ready_general`, `rule_family=balanced_source_general` |
| scope packet refresh | completed | [design_scope_expansion_packet.md](./design_scope_expansion_packet.md) | `XiangShan` moved into `phase_1_ready_family_actual_gpu` |
| plain `mini-chisel6:hello` baseline | completed | [/tmp/xiangshan_plain_verilator_v1/XiangShan/mini-chisel6/execute-0/hello/_execute/stdout.log](/tmp/xiangshan_plain_verilator_v1/XiangShan/mini-chisel6/execute-0/hello/_execute/stdout.log), [/tmp/xiangshan_plain_verilator_v1/XiangShan/mini-chisel6/execute-0/hello/_execute/metrics.json](/tmp/xiangshan_plain_verilator_v1/XiangShan/mini-chisel6/execute-0/hello/_execute/metrics.json) | plain Verilator reaches `Hello, XiangShan!`, `Hit Good Trap`, and clean `$finish` |
| plain `gpu_cov_gate:hello` baseline | completed | [/tmp/xiangshan_plain_gpu_cov_gate_v1/XiangShan/gpu_cov_gate/execute-0/hello/_execute/stdout.log](/tmp/xiangshan_plain_gpu_cov_gate_v1/XiangShan/gpu_cov_gate/execute-0/hello/_execute/stdout.log), [/tmp/xiangshan_plain_gpu_cov_gate_v1/XiangShan/gpu_cov_gate/execute-0/hello/_execute/metrics.json](/tmp/xiangshan_plain_gpu_cov_gate_v1/XiangShan/gpu_cov_gate/execute-0/hello/_execute/metrics.json) | the same `gpu_cov_gate` wrapper also reaches `Hello, XiangShan!`, `Hit Good Trap`, and clean `$finish` under plain Verilator |
| actual-GPU `gpu_cov_gate:hello` | completed | [/tmp/xiangshan_family_gpu_cov_gate_contract_v3/gpu_cov_gate/hello/summary.json](/tmp/xiangshan_family_gpu_cov_gate_contract_v3/gpu_cov_gate/hello/summary.json), [/tmp/xiangshan_family_gpu_cov_gate_contract_v3/gpu_cov_gate/hello/baseline_stdout.log](/tmp/xiangshan_family_gpu_cov_gate_contract_v3/gpu_cov_gate/hello/baseline_stdout.log) | patched sim-accel rerun reaches `17/18`, `dead_region_count=0`, `active_region_count=4`, `partial_region_count=1`; only `finish_protocol` fail-side remains unhit |
| actual-GPU `gpu_cov_gate:cmark` | completed | [/tmp/xiangshan_family_gpu_cov_gate_contract_v3/gpu_cov_gate/cmark/summary.json](/tmp/xiangshan_family_gpu_cov_gate_contract_v3/gpu_cov_gate/cmark/summary.json), [/tmp/xiangshan_family_gpu_cov_gate_contract_v3/gpu_cov_gate/cmark/baseline_stdout.log](/tmp/xiangshan_family_gpu_cov_gate_contract_v3/gpu_cov_gate/cmark/baseline_stdout.log) | actual-GPU rerun also reaches `17/18`, `dead_region_count=0`, and the same single partial `finish_protocol` region under `direct_bench_kernel` |
| baseline-runner compile profile | completed | [/tmp/xiangshan_family_gpu_cov_gate_fast_v10/gpu_cov_gate/hello/verilator_cuda.log](/tmp/xiangshan_family_gpu_cov_gate_fast_v10/gpu_cov_gate/hello/verilator_cuda.log), [/tmp/xiangshan_family_gpu_cov_gate_fast_v10/gpu_cov_gate/hello/build_nvcc.log](/tmp/xiangshan_family_gpu_cov_gate_fast_v10/gpu_cov_gate/hello/build_nvcc.log) | validation-first gate build reached `kernel_partitions=16`, moved off `full_seq`, and now uses native `sm_89` codegen |
| family fallback runner | completed | [run_xiangshan_gpu_toggle_validation.py](./run_xiangshan_gpu_toggle_validation.py) | canonical `hello/cmark` validation entry now exists |

## Observed Build Profile

- the original `full_all`-only XiangShan pass generated a large fused CUDA
  unit: `kernel_generated.full_all.cu` is about `115 MiB`.
- that first canonical run was not stalled in the wrapper or runner.
  It was spending the time in `nvcc -> cicc` device compilation.
- the original compile profile from
  [verilator_cuda.log](/tmp/xiangshan_family_gpu_cov_gate_v1/gpu_cov_gate/hello/verilator_cuda.log)
  is already informative:
  - `assignw_supported=137878`
  - `assignw_total=269741`
  - `assignw_offload_pct=51.11`
  - `cluster_count=1810`
  - `kernel_partitions=1`
  - `preload_targets count=133`
- the current lighter gate profile from
  [verilator_cuda.log](/tmp/xiangshan_family_gpu_cov_gate_fast_v10/gpu_cov_gate/hello/verilator_cuda.log)
  keeps the same offload surface but now emits:
  - `kernel_partitions=16`
  - Verilator walltime `52.865 s` on the current rerun
  - `12` emitted `seqpart` sources for the sequential tail
  - `build_nvcc.log` no longer compiles `kernel_generated.full_seq.cu`
  - bench compile now resolves CUDA arch to `sm_89`, so the first runtime
    launch no longer falls back to `sm_52` PTX JIT
  - the first post-codegen bottleneck moved to `kernel_generated.link.cu`
    and the heavy native-arch partition wave
  - `07_build_run_phase.sh` now schedules partition objects in
    size-descending order so the next rerun pulls the heaviest `ptxas` jobs
    forward instead of leaving them as tail latency

This means the remaining gap is no longer "artifact missing", "XiangShan
family dead", "wrapper cannot run", or "sim-accel still dead". The first
XiangShan fallback pass now survives actual GPU execution, and the remaining
local note is only that the current standard pass-path workloads do not trip
the fail-side finish word.

## Root-Cause Direction

- plain Verilator reaches `Good Trap` both on
  `XiangShan:mini-chisel6:hello` and on the same
  `XiangShan:gpu_cov_gate:hello` wrapper.
- the actual-GPU sim-accel path emits `gpu_output_compact.bin`, and the
  generated `vars.tsv/comm.tsv` do contain the expected `gpu_cov` output slots
  (`cfg_signature_o`, `done_o`, `progress_cycle_count_o`,
  `real_toggle_subset_word*`, `focused_wave_word*`).
- however, re-decoding that compact payload against the current
  `vars.tsv/comm.tsv` yields all-zero values for those outputs.
- the earlier dead summary at
  [summary.json](/tmp/xiangshan_family_gpu_cov_gate_fast_v14/gpu_cov_gate/hello/summary.json)
  showed:
  - `program.bin` staged but no `memory_image` runtime input
  - `direct_preload_file_count = 0`
  - `array_preload_payload_file_count = 0`
- XiangShan plain Verilator prints `Using simulated 8192MB RAM`, which comes
  from [ram.cpp](~/GEM_try/rtlmeter/designs/XiangShan/src/common/ram.cpp)
  and loads `program.bin`. The sim-accel bench path does not show that path and
  its staged `filelist` is Verilog-only.
- the runtime-contract probe at
  [xiangshan_sim_accel_contract_probe.md](./xiangshan_sim_accel_contract_probe.md)
  narrowed the first gap:
  - `program.bin` is staged
  - `MemRWHelper.v` and `FlashHelper.v` are present in the staged filelist
  - generated sim-accel `cpu.cpp` contains neither `ram_read/ram_write` nor
    `flash_read`
  - this led to the staged XiangShan contract patch that now exposes
    `top.memory.ram.rdata_mem.ram` and `flash_mem` as preload targets
- the patched rerun at
  `/tmp/xiangshan_family_gpu_cov_gate_contract_v1/gpu_cov_gate/hello`
  now passes `--memory-image ...program.bin --memory-image-target ...target.json`
  and the standalone materializer confirms `program.bin` lowers to
  `131072` hidden payload rows for the visible RAM target.

This is not a backend-comparison proof yet, but the strongest current
explanation is now stable: the original sim-accel bench path did not
reproduce XiangShan's `program.bin` loading contract (`tb.v` + `ram.cpp` + DPI
RAM helpers), and the packed observability representation also failed to
surface progress as coverage. The explicit preload path plus scalar sticky
observability closes the dead `0/18` result.

## What This Means

- `XiangShan` is no longer a `needs_gpu_cov_tb_and_manifest` design.
- The family now has the minimal artifacts needed to join the mainline GPU
  validation ladder.
- `XiangShan` now has actual-GPU `hello/cmark` evidence under
  `balanced_source_general`.
- The remaining XiangShan note is a workload-shaped partial
  `finish_protocol`, not a family bring-up blocker.

## Recommended Next Step

1. Refresh the scope packet and treat `XiangShan` as actual-GPU validated.
2. Open `BlackParrot` as the next fallback-family bring-up.
3. Only revisit `XiangShan` if a later milestone requires explicit fail-path
   workloads for the remaining `finish_protocol` word.
