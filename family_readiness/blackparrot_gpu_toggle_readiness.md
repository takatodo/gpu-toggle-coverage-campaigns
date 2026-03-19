# BlackParrot GPU Toggle Readiness

- status: `actual_gpu_validated`
- rule family target: `balanced_source_general`
- validated configuration: `gpu_cov_gate`

## Weakest Point

`BlackParrot` is no longer blocked on missing wrapper or manifest artifacts.
Both `hello` and `1x1 cmark` now survive the baseline GPU runner at `18/18`
with `dead_region_count=0`. The remaining work is follow-on runtime
maintenance, not contract bring-up.

## Completed

| Item | Status | Artifact | Notes |
|---|---|---|---|
| `gpu_cov` wrapper added | completed | [blackparrot_gpu_cov_tb.sv](~/GEM_try/rtlmeter/designs/BlackParrot/src/bp/blackparrot_gpu_cov_tb.sv) | wrapper reuses `testbench` directly and exports coarse coverage proxies |
| `coverage_regions` manifest added | completed | [blackparrot_gpu_cov_coverage_regions.json](~/GEM_try/rtlmeter/designs/BlackParrot/tests/blackparrot_gpu_cov_coverage_regions.json) | manifest groups `control_progress`, memory, DRAM, and finish |
| `gpu_cov/gpu_cov_gate` descriptor entries added | completed | [descriptor.yaml](~/GEM_try/rtlmeter/designs/BlackParrot/descriptor.yaml) | `hello` and `1x1 cmark` are explicit baseline-runner targets |
| runtime `+init_mem` lowering closed | completed | [run_rtlmeter_gpu_toggle_baseline.py](./run_rtlmeter_gpu_toggle_baseline.py) | `prog.mem` now lowers into hidden preload payload plus target descriptor |
| static candidate refresh | completed | [rtlmeter_design_gpu_toggle_candidates.json](./rtlmeter_design_gpu_toggle_candidates.json) | `readiness=ready_for_gpu_toggle`, `priority=medium` |
| static feature/assignment refresh | completed | [rtlmeter_design_toggle_features.json](./rtlmeter_design_toggle_features.json), [rtlmeter_design_toggle_rule_assignments.json](./rtlmeter_design_toggle_rule_assignments.json) | `feature_family=wrapper_ready_core`, `rule_family=balanced_source_general` |
| actual GPU `hello` | completed | [/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/hello/summary.json](/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/hello/summary.json) | `18/18`, `dead_region_count=0`, all 5 coarse regions active |
| actual GPU `cmark` | completed | [/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/cmark/summary.json](/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/cmark/summary.json) | `18/18`, `dead_region_count=0`, same 5 regions active |
| family validation packet | completed | [/tmp/blackparrot_gpu_cov_gate_v6/blackparrot_gpu_toggle_validation.json](/tmp/blackparrot_gpu_cov_gate_v6/blackparrot_gpu_toggle_validation.json) | canonical `hello + cmark` validation artifact |

## Runtime Contract Notes

- The first blocker was not the protocol shape but `+init_mem=prog.mem`:
  the baseline runner had to lower BlackParrot's memory image into hidden
  preload payloads.
- The wrapper now exposes `gpu_cov_program_words`, and the runner materializes
  both:
  [/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/hello/blackparrot_prog_mem_entries.bin](/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/hello/blackparrot_prog_mem_entries.bin)
  and
  [/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/hello/blackparrot_gpu_cov_tb.init_mem.target.json](/tmp/blackparrot_gpu_cov_gate_v6/gpu_cov_gate/hello/blackparrot_gpu_cov_tb.init_mem.target.json)
- The runner still lands on `bench_runtime_mode=wrapper` on this first canonical
  validation pass; direct-reuse follow-on work is maintenance, not a bring-up
  blocker.

## Evidence Summary

- `hello` and `cmark` both hit all `18/18` subset words.
- All coarse regions are active:
  `control_progress`, `finish_protocol`, `memory_request_path`,
  `memory_response_path`, `dram_path`.
- `dead_region_count=0` and `partial_region_count=0` on both tests.

## Next Step

Treat `BlackParrot` as actual-GPU validated and move scope expansion to the
next fallback family recorded in
[design_scope_expansion_packet.md](./design_scope_expansion_packet.md).
