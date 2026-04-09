# `tlul_socket_m1` Campaign Schema Packet

## Purpose

この packet は、`socket_m1` の

- hybrid validation JSON
- CPU baseline validation JSON
- time-to-threshold comparison JSON

の間で schema drift を起こさないための contract packet である。

## Weakest Point

当初の weakest point は、execution packet が

- baseline と hybrid の両方が threshold を report する

ことを前提にしているのに、現行の
[socket_m1_stock_hybrid_validation.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/socket_m1_stock_hybrid_validation.json)
には threshold object がまだ無かったことだ。

その drift は WP0 で解消済みだが、baseline / comparison 側が同じ schema を採らないと再発する。
防ぎたい drift は次の通り。

- baseline 側だけ threshold field を持つ
- comparison runner が packet hardcode に依存する
- source-of-truth JSON から threshold を逆算できない

## Decision

comparison v1 では、baseline と hybrid の両方に
同じ `campaign_threshold` / `campaign_measurement` block を持たせる。

comparison runner は packet を読むのではなく、
**artifact 自身が持つ schema** を比較する。

## Required Common Fields

### `campaign_threshold`

両 runner に必須:

```json
{
  "kind": "toggle_bits_hit",
  "value": 3,
  "aggregation": "bitwise_or_across_trials"
}
```

### `campaign_measurement`

両 runner に必須:

```json
{
  "bits_hit": 3,
  "threshold_satisfied": true,
  "wall_time_ms": 0.529,
  "steps_executed": 1
}
```

## Mapping Rules

### Hybrid JSON

For
[run_socket_m1_stock_hybrid_validation.py](/home/takatodo/gpu-toggle-coverage-campaigns/src/runners/run_socket_m1_stock_hybrid_validation.py):

- `campaign_threshold.kind` <- fixed string `toggle_bits_hit`
- `campaign_threshold.value` <- fixed int `3`
- `campaign_threshold.aggregation` <- fixed string `bitwise_or_across_trials`
- `campaign_measurement.bits_hit` <- `toggle_coverage.bits_hit`
- `campaign_measurement.threshold_satisfied` <- `toggle_coverage.bits_hit >= 3`
- `campaign_measurement.wall_time_ms` <- `performance.wall_time_ms`
- `campaign_measurement.steps_executed` <- `inputs.steps`

### CPU Baseline JSON

For the future CPU baseline runner:

- use the same `campaign_threshold`
- `campaign_measurement.bits_hit` <- OR-aggregated bits across baseline trials
- `campaign_measurement.threshold_satisfied` <- `bits_hit >= 3`
- `campaign_measurement.wall_time_ms` <- measured baseline wall time
- `campaign_measurement.steps_executed` <- serial CPU steps consumed until threshold

## Comparison JSON

The comparison runner should read the normalized fields above and emit:

```json
{
  "target": "tlul_socket_m1",
  "campaign_threshold": { "...": "..." },
  "baseline": {
    "runner_json": "...",
    "campaign_measurement": { "...": "..." }
  },
  "hybrid": {
    "runner_json": "...",
    "campaign_measurement": { "...": "..." }
  },
  "comparison_ready": true,
  "speedup_ratio": 1.0,
  "winner": "hybrid"
}
```

Comparison semantics such as `reject` vs `unresolved` are defined in
[socket_m1_campaign_proof_matrix.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/socket_m1_campaign_proof_matrix.md).
The additive migration policy for the checked-in hybrid JSON is defined in
[socket_m1_hybrid_schema_normalization_packet.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/socket_m1_hybrid_schema_normalization_packet.md).

## Required Write Set

If CC implements the campaign line, the minimum write set is:

- `src/runners/run_socket_m1_stock_hybrid_validation.py`
  - add normalized campaign blocks
- `src/runners/run_socket_m1_cpu_baseline_validation.py`
  - emit the same campaign blocks
- `src/runners/run_socket_m1_time_to_threshold_comparison.py`
  - read normalized campaign blocks

## Proof Gate

This packet is satisfied when:

1. hybrid JSON contains `campaign_threshold`
2. hybrid JSON contains `campaign_measurement`
3. baseline JSON contains the same two blocks
4. comparison runner rejects mismatched threshold schema

## Out Of Scope

- changing the threshold value
- multi-design comparison
- `tlul_fifo_sync` schema reuse
- stronger campaign metrics than `toggle_bits_hit`
