# Metrics-Driven GPU Validation Matrix

## Purpose

Turn the new `simple circuits first` plan into a concrete execution order for
`A/B/C` experiments:

- `A`: CPU baseline
- `B`: GPU-metrics-only
- `C`: GPU-guided

The matrix below is intentionally ordered to separate three questions:

1. can the harness run at all
2. do the metric kernels show a plausible GPU win region
3. does GPU guidance improve `coverage gain / hour` or `bug / hour`

`VeeR` is excluded from the first gate on purpose and re-enters only as a late
stress path.

## Fixed Metrics

- `time_to_10_30_50_80_coverage`
- `time_to_first_bug`
- `coverage_gain_per_hour`
- `unique_bugs_per_hour`
- `useful_simulations_ratio`
- `transfer_overhead_ratio`
- `score_to_actual_gain_correlation`

## Tier Order

| Tier | Target | Class | Why first | Current state | First use |
|---|---|---|---|---|---|
| `T0` | `Example:kind:hello` | harness sanity | smallest existing RTLMeter case; cheap reruns; confirms A-flow wiring | execute-pass confirmed | CPU baseline scaffolding |
| `T0` | `tiny_accel.v` | local microbench seed | smallest local sequential RTL; no external lowering complexity | source-only local file present | metric-kernel prototyping |
| `T1` | `OpenTitan.tlul_fifo_sync` | simple realistic routing slice | existing GPU campaign assets already exist; moderate structure; known knobs | production defaults and campaign manifests exist | first A/B/C comparison with real coverage loop |
| `T1` | `OpenTitan.tlul_socket_1n` | adjacent routing slice | close to `tlul_fifo_sync`; helps test rule reuse on similar topology | existing slice plan and rollout assets exist | first cross-slice reuse check |
| `T2` | `Vortex:gpu_cov` | medium external design | has standard/sanity tests; more state and arbitration structure | fixed-test `sgemm` Tier-2 `A/B/C` exists; first medium-design gate passed; partial mem-path regions remain | medium-circuit validation |
| `T3` | `VeeR-EL2/EH1/EH2` | late stress path | difficult lowering and runtime path; good portability test after the method is proven | bounded direct-LLVM refresh path preserved | late external-family stress validation |

## Experiment Entry Criteria

### `T0 Example`

- pass `CPU baseline`
- emit a repeatable wall-clock and simulation-count summary
- no GPU requirement yet

### `T0 tiny_accel`

- use as the first local metric-kernel input shape
- no rule search yet
- use to measure `toggle`, `diff`, `popcount`, `histogram`, and `top-k`

## Tier-0 Exit Condition

- `CPU baseline` artifact is repeatable
- the smallest sequential RTL seed has a repeatable metric microbench artifact
- metric-path bottleneck attribution is available at coarse breakdown level

### `T1 OpenTitan.tlul_fifo_sync`

- first design that must support all three flows `A/B/C`
- fixed wall-clock budget and candidate budget
- first place where `coverage_gain_per_hour` matters

### `T1 OpenTitan.tlul_socket_1n`

- same metrics and same reporting shape as `tlul_fifo_sync`
- used to test whether the first provisional rule transfers to a nearby circuit

### `T2 Vortex:gpu_cov`

- only starts after a useful signal appears on `T1`
- used to test whether the method survives a larger and less routing-specific design

### `T3 VeeR`

- only starts after provisional rules exist
- used to separate `metrics-driven value` from `external lowering/runtime stress`

## Immediate Execution Order

1. `Example:kind:hello`
   - freeze CPU-baseline harness shape
2. `tiny_accel.v`
   - freeze metric-kernel microbench shape
3. `OpenTitan.tlul_fifo_sync`
   - first real `A/B/C` comparison
4. `OpenTitan.tlul_socket_1n`
   - first transferability check
5. `Vortex:gpu_cov`
   - first medium external design
6. `VeeR-EL2/EH1/EH2`
   - late stress path

## Current Evidence

- `Example:kind:hello` already executes successfully through RTLMeter.
- `tiny_accel.v` exists locally as the smallest sequential RTL seed.
- `Example:kind:hello` now has a repeatable CPU-baseline wrapper artifact:
  - `./run_example_cpu_baseline.py`
  - `/tmp/metrics_driven_t0/example_kind_hello_cpu_baseline.json`
- `tiny_accel.v` now has a first metric-kernel microbench artifact at `131072` states and `64` cycles:
  - `./run_tiny_accel_metric_microbench.py`
  - `/tmp/metrics_driven_t0/tiny_accel_metric_microbench.json`
  - current single-run `metric_total_ms`: `775.77`
- `tiny_accel.v` now also has a repeat/sweep stability artifact:
  - `./run_tiny_accel_metric_stability_matrix.py`
  - `/tmp/metrics_driven_t0/tiny_accel_metric_stability_matrix.json`
  - `131072 states x 64 cycles` repeated `3` times: `metric_total_ms mean = 695.77`, `CV = 0.0116`
  - the earlier `611.03 ms` observation should be treated as a first-run sample, not the stable baseline
  - the dominant coarse buckets at `131072 x 64` are `toggle_popcount`, `candidate_popcount`, `packing`, and `unpacking`
  - real `host↔device transfer` is still unavailable in Tier `0`; only a host-copy proxy is reported until a GPU backend exists
- `OpenTitan.tlul_fifo_sync` already has campaign manifests, frozen defaults, and GPU execution assets in this workspace.
- `OpenTitan.tlul_fifo_sync` now also has a fixed-budget Tier-1 `A/B/C` entrypoint:
  - `./run_tier1_tlul_fifo_sync_abc.py`
  - `/tmp/metrics_driven_t1/tlul_fifo_sync_abc_manifest.json`
  - `A = CPU-only campaign`, `B = single-pass GPU metrics/ranking`, `C = closed-loop GPU-guided campaign`
  - Tier-1 defaults now coalesce `B` launches to `512` states / `128` candidates per launch
  - for the current `512` base-case, `4`-variant sweep, this reduces expected `B` relaunch count from `256` to `16`
  - the current comparable `A/B/C` run artifacts are:
    - `A`: `/tmp/metrics_driven_t1_exec_v6/tlul_fifo_sync/A_cpu_baseline/summary.json`
    - `B`: `/tmp/metrics_driven_t1_exec_v9/tlul_fifo_sync/B_gpu_metrics_only/summary.json`
    - `C`: `/tmp/metrics_driven_t1_exec_v7/tlul_fifo_sync/C_gpu_guided/summary.json`
  - at the current fixed budget, `B` reaches the same best hit/dead-region point as `A/C` with `4` launches and `24.10s` wall-clock, versus `26.12s` for `A` and `26.57s` for `C`
- `OpenTitan.tlul_socket_1n` now also has a fixed-budget Tier-1 `A/B/C` entrypoint:
  - `./run_tier1_tlul_socket_1n_abc.py`
  - `/tmp/metrics_driven_t1/tlul_socket_1n_B_only_manifest_v1.json`
  - comparable `A/B/C` run artifacts are:
    - `A`: `/tmp/metrics_driven_t1_socket_exec_v2/tlul_socket_1n/A_cpu_baseline/summary.json`
    - `B`: `/tmp/metrics_driven_t1_socket_exec_v4/tlul_socket_1n/B_gpu_metrics_only/summary.json`
    - `C`: `/tmp/metrics_driven_t1_socket_exec_v3/tlul_socket_1n/C_gpu_guided/summary.json`
  - `B` survives transfer to the adjacent slice and reaches the same best hit/dead-region point, but warm-cache E2E is still slightly slower at this small budget (`2.72s` vs `1.81s` for `A` and `1.70s` for `C`)
  - the first Tier-1 crossover study now exists at `/tmp/metrics_driven_t1_socket_scale_v1/tlul_socket_1n_ab_scale.json`
  - current socket crossover evidence suggests `GPU-metrics-only` stops being clearly launch-dominated around `candidate_count ~= 132-264`
- `Vortex:gpu_cov` is now the first completed Tier-2 medium-design candidate.
- The first enablement packet is implemented and documented in:
  - `./vortex_gpu_toggle_enablement_plan.md`
  - `./vortex_gpu_toggle_readiness.md`
- Current Vortex evidence is no longer wrapper/manifest creation:
  - direct RTLMeter smoke passes for `Vortex:gpu_cov:hello`
  - shared generic baseline passes for `Vortex:gpu_cov:hello` and `Vortex:gpu_cov:sgemm`
  - fixed-test Tier-2 `A/B/C` summaries now exist at:
    - `A`: `/tmp/metrics_driven_t2_exec_v2/A_cpu_baseline/summary.json`
    - `B`: `/tmp/metrics_driven_t2_exec_v2/B_gpu_metrics_only/summary.json`
    - `C`: `/tmp/metrics_driven_t2_exec_v2/C_gpu_guided/summary.json`
  - the second standard workload now also has comparable `A/B/C` summaries at:
    - `A`: `/tmp/metrics_driven_t2_exec_v3_saxpy/A_cpu_baseline/summary.json`
    - `B`: `/tmp/metrics_driven_t2_exec_v3_saxpy/B_gpu_metrics_only/summary.json`
    - `C`: `/tmp/metrics_driven_t2_exec_v3_saxpy/C_gpu_guided/summary.json`
  - `Vortex sgemm` now exposes nonzero GPU-side `real_toggle_subset` words and reaches the same `10/18` point result under `A/B/C`
  - `saxpy` reproduces the same `10/18` point result and the same GPU compact SHA as `sgemm`, which confirms flow stability across the second standard test name but does not expand the active region set
  - `B/C` each run near `0.53s` while `A` is `3.50s` on the same fixed test
  - the first wrapper warm-cache runtime probe exists at `/tmp/runtime_log_job/vortex_t2_B_sgemm/runtime_summary.json`, and the first validated direct-reuse probe exists at `/tmp/runtime_log_job/vortex_t2_B_reuse_v1/runtime_summary.json`
  - with `--reuse-bench-kernel-if-present`, the monitored `B` command drops from `109.56s` to `2.49s` while preserving the same compact SHA and the same `10/18` hit result
  - the remaining runtime question is no longer whether Tier-2 can survive warm-cache E2E, but whether this reuse path can be generalized beyond preload-free warm workloads
  - the remaining validation question is no longer whether a second standard Vortex test survives, but whether the current partial `mem_request_path` / `mem_response_path` regions are already enough for provisional rule freeze
- The first provisional freeze packet now exists:
  - `./metrics_driven_provisional_rule_packet.json`
  - `./metrics_driven_provisional_rule_packet.md`
  - current status is `provisional_rule_family_frozen`
  - `tlul_socket_1n` is carried as `simple_transfer_evidence` rather than a regression, because warm-cache crossover appears around `candidate_count ~= 132`
  - the second standard Vortex workload `saxpy` reproduces the same packet and compact SHA as `sgemm`, so the remaining issue is late-family portability and region richness rather than single-test instability
- `VeeR` lowering progress is preserved, but it is now intentionally decoupled from the first metrics-driven validation gate.

## Exit Conditions

- `T0` exits when the harness is repeatable, the metric microbench is repeatable, and coarse bottleneck attribution is available.
- `T1` exits when at least one real design shows a meaningful `A/B/C` separation.
- `T2` exits when the first provisional rule survives a medium design.
- `T3` exits when late external-family stress does not overturn the earlier conclusion.
