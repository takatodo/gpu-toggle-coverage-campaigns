# BlackParrot GPU Toggle Enablement Plan

## Weakest Point

`BlackParrot` is no longer blocked on bring-up. The weakest point has moved to
follow-on runtime maintenance and the next fallback-family expansion after
BlackParrot.

## Current Direction

Treat `BlackParrot` as actual-GPU validated under `balanced_source_general`
using the smallest existing configuration:

- configuration: `1x1`
- sanity test: `hello`
- standard test: `cmark`
- wrapper: `blackparrot_gpu_cov_tb`
- gate alias: `gpu_cov_gate`

## Current Facts

- Descriptor: [descriptor.yaml](~/GEM_try/rtlmeter/designs/BlackParrot/descriptor.yaml)
- Wrapper: [blackparrot_gpu_cov_tb.sv](~/GEM_try/rtlmeter/designs/BlackParrot/src/bp/blackparrot_gpu_cov_tb.sv)
- Manifest: [blackparrot_gpu_cov_coverage_regions.json](~/GEM_try/rtlmeter/designs/BlackParrot/tests/blackparrot_gpu_cov_coverage_regions.json)
- Validation runner: [run_blackparrot_gpu_toggle_validation.py](./run_blackparrot_gpu_toggle_validation.py)
- Canonical family validation:
  [/tmp/blackparrot_gpu_cov_gate_v6/blackparrot_gpu_toggle_validation.json](/tmp/blackparrot_gpu_cov_gate_v6/blackparrot_gpu_toggle_validation.json)
- `hello` summary:
  [/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/hello/summary.json](/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/hello/summary.json)
- `cmark` summary:
  [/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/cmark/summary.json](/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/cmark/summary.json)

The actual runtime contract is now closed through hidden preload lowering:

- `+init_mem=prog.mem` is lowered into a binary payload plus explicit target
  descriptor
- the wrapper exposes `gpu_cov_program_words`
- the baseline runner materializes the preload image and target JSON directly

## Validation Gate

The first-pass BlackParrot gate is now satisfied:

1. `BlackParrot:gpu_cov_gate:hello` compiles and runs through the baseline runner
2. `BlackParrot:gpu_cov_gate:cmark` on `1x1` survives the same path
3. the manifest emits non-trivial evidence for:
   - `control_progress`
   - `memory_request_path`
   - `memory_response_path`
   - `dram_path`
   - `finish_protocol`

Both canonical tests now reach `18/18`, `dead_region_count=0`, and all five
coarse regions are active.

## Recommended Next Step

1. Refresh the scope packet and final packet to treat `BlackParrot` as
   actual-GPU validated.
2. Keep runtime follow-on work separate from this bring-up closure.
3. Move the next fallback-family step to the next design in the scope packet.
