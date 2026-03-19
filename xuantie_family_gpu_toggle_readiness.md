# XuanTie Family GPU Toggle Readiness

## Summary

- Weakest point: `XuanTie-E902/E906` are no longer blocked on missing `gpu_cov` artifacts, on the generic runner's old `program.hex` assumption, on family-standard gate reruns, or on baseline-runner runtime defaults. The remaining gap is narrower and lower-level: the raw sim-accel `gpu_cov` path still produces dead compact outputs because the stock timing-based `tb.v` contract is not a good fit for the current sim-accel execution path.
- Current direction: use `gpu_cov_gate` as the default XuanTie late-family precheck path, treat the raw sim-accel `gpu_cov` dead output as a localized execution-contract bug, and keep any lower-level cycle-based harness rewrite off the main freeze path because final freeze is now explicitly scoped to exclude that raw late-family harness class.

## Current Status

| Design | Status | Evidence | Result |
|---|---|---|---|
| `XuanTie-E902` default `memcpy` standard baseline | executed | `/tmp/xuantie_e902_default_memcpy_v1/XuanTie-E902/default/execute-0/memcpy/_execute/stdout.log` | `TEST PASSED` with clean `$finish` at `tb.v:174` |
| `XuanTie-E906` default `cmark` standard baseline | executed | `/tmp/xuantie_e906_default_cmark_v1/XuanTie-E906/default/execute-0/cmark/_execute/stdout.log` | `TEST PASSED` with clean `$finish` at `tb.v:199` |
| `XuanTie-E902` gpu_cov standard precheck | executed | `/tmp/xuantie_e902_gpu_cov_memcpy_v1/XuanTie-E902/gpu_cov/execute-0/memcpy/_execute/stdout.log` | `TEST PASSED` with clean `$finish` at `tb.v:174` |
| `XuanTie-E906` gpu_cov standard precheck | executed | `/tmp/xuantie_e906_gpu_cov_cmark_v1/XuanTie-E906/gpu_cov/execute-0/cmark/_execute/stdout.log` | `TEST PASSED` with clean `$finish` at `tb.v:199` |
| `XuanTie-E902` `gpu_cov_gate:memcpy` late-family gate | executed | `/tmp/xuantie_family_gpu_cov_gate_direct_v1/XuanTie-E902/gpu_cov_gate/execute-0/memcpy/_execute/stdout.log` | `TEST PASSED` with clean `$finish` at `tb.v:174`; the wrapper itself survives the family-standard rerun under plain Verilator execute |
| `XuanTie-E906` `gpu_cov_gate:cmark` late-family gate | executed | `/tmp/xuantie_family_gpu_cov_gate_direct_v1/XuanTie-E906/gpu_cov_gate/execute-0/cmark/_execute/stdout.log` | `TEST PASSED` with clean `$finish` at `tb.v:199`; the same gate path survives the assigned standard CoreMark rerun |
| `XuanTie-E902/E906` `gpu_cov_gate` baseline-runner first pass | executed | `/tmp/xuantie_family_gpu_cov_gate_baseline_v5/first.json` | both assigned standard workloads complete through `run_rtlmeter_gpu_toggle_baseline.py`; first pass lands on `bench_runtime_mode=wrapper` |
| `XuanTie-E902/E906` `gpu_cov_gate` baseline-runner warm rerun | executed | `/tmp/xuantie_family_gpu_cov_gate_baseline_v5/second.json` | both assigned standard workloads now rerun through `bench_runtime_mode=direct_bench_kernel`, `bench_runtime_reused=true` |
| `XuanTie-E902/E906` `gpu_cov_gate` runtime reuse compare | executed | `/tmp/xuantie_family_gpu_cov_gate_baseline_v5/reuse_compare.json` | `aggregate_pass=true`; wrapper first pass and warm direct-bench rerun agree on compact SHA, `points_hit=0/18`, and `dead_region_count=3` |
| `XuanTie-E902` generic rule-guided summary path | executed | `/tmp/xuantie_e902_rule_guided_v2/memcpy/summary.json` | `pre_gpu_gate=pass`, `aggregate_pass=true`, `case.pat` iterations materialized at word `0x8000` |
| `XuanTie-E906` generic rule-guided summary path | executed | `/tmp/xuantie_e906_rule_guided_v2/cmark/summary.json` | `pre_gpu_gate=pass`, `aggregate_pass=true`, `case.pat` iterations materialized at word `0x8000` |
| `XuanTie-E902` actual `gpu_cov` rule-guided GPU run | executed | `/tmp/xuantie_e902_rule_guided_gpu_v1/memcpy/summary.json` | `collector.aggregate_pass=true`, but `points_hit=0/18`, `dead_region_count=3`; the raw sim-accel path is alive enough to return compact output yet still dead at the wrapper witness level |
| `XuanTie-E906` actual `gpu_cov` rule-guided GPU run | executed | `/tmp/xuantie_e906_rule_guided_gpu_v1/cmark/summary.json` | `collector.aggregate_pass=true`, but `points_hit=0/18`, `dead_region_count=3`; same failure signature as E902 |
| `XuanTie-E902` gpu-toggle candidate packet | refreshed | `./rtlmeter_design_gpu_toggle_candidates.json` | `priority=high`, `ready_for_gpu_toggle`, `has_standard_test=true`, `has_sanity_test=true` |
| `XuanTie-E906` gpu-toggle candidate packet | refreshed | `./rtlmeter_design_gpu_toggle_candidates.json` | `priority=high`, `ready_for_gpu_toggle`, `has_standard_test=true`, `has_sanity_test=true` |
| `XuanTie-E902/E906` generic baseline runner hello smoke | executed | `/tmp/xuantie_e902_rule_guided_hello_v2/hello/baseline_stdout.log`, `/tmp/xuantie_e906_rule_guided_hello_v2/hello/baseline_stdout.log` | both no-arg smoke paths reach sim-accel build/run; standard workloads now supersede hello as the meaningful late-family gate |

## What This Means

- The next XuanTie blocker is not plain runtime liveness, missing wrapper/manifest/config artifacts, or missing family-standard reruns.
- Both families already have standard-grade descriptor cases that execute successfully under the stock `tb` top.
- Both families also execute their assigned standard workloads successfully under both the `gpu_cov` wrapper and the explicit `gpu_cov_gate` alias.
- The `gpu_cov_gate` family runner now inherits the mainline baseline/reuse contract: a first pass builds through the wrapper, and a warm rerun reuses the existing `bench_kernel` directly on both E902 and E906.
- `case.pat` plusarg workloads now summarize through the generic baseline/rule-guided path by materializing the iteration count into the staged `case.pat`.
- The raw sim-accel `gpu_cov` path is where XuanTie still fails:
  - `progress_cycle_count_o` stays at `1`
  - the `real_toggle_subset_word*` witness set stays all-zero
  - `dead_region_count=3` on both E902 and E906
- This means the remaining XuanTie issue is execution-contract specific and looks analogous to the old VeeR raw `gpu_cov` path: it is not evidence that the provisional rule family itself has failed.

## Recommended Next Step

1. Treat `gpu_cov_gate` as the default XuanTie late-family precheck path.
2. Treat `/tmp/xuantie_family_gpu_cov_gate_baseline_v5/reuse_compare.json` as the XuanTie proof that the baseline-runner reuse contract now survives a family-standard late-family rerun.
3. Keep the raw sim-accel `gpu_cov` dead output as a localized timing/execution-contract bug until a cycle-based harness exists.
4. Use the final freeze packet at `./metrics_driven_final_rule_packet.md` as the canonical scope decision.
5. Only reopen lower-level XuanTie harness work if a later milestone explicitly requires actual late-family sim-accel/GPU evidence.
