# `tlul_socket_m1` Hybrid Schema Normalization Packet

## Purpose

この packet は、
[run_socket_m1_stock_hybrid_validation.py](/home/takatodo/gpu-toggle-coverage-campaigns/src/runners/run_socket_m1_stock_hybrid_validation.py)
に `campaign_threshold` / `campaign_measurement` を追加する WP0 の source of truth である。

baseline / comparison 実装より前に、
**checked-in hybrid JSON をどう拡張するか**を固定する。

## Weakest Point

いま一番弱い点は、schema packet は

- `campaign_threshold`
- `campaign_measurement`

を要求しているのに、

- `schema_version` を上げるのか
- 既存 field をどう保持するのか
- `status=error` のとき `campaign_measurement` をどう埋めるのか

がまだ未定なことだ。

このまま CC が実装すると、次の drift が起きやすい。

- additive change なのに `schema_version` を勝手に上げる
- `toggle_coverage` を campaign field に置き換えてしまう
- error payload で `campaign_measurement` を省略する

## Decision

WP0 は **additive normalization only** とする。

- `schema_version` は据え置きで `1`
- 既存 field は rename / delete しない
- `toggle_coverage` と `performance` はそのまま残す
- `campaign_threshold` と `campaign_measurement` を追加する

この packet の目的は、
comparison 実装の前提を checked-in hybrid JSON に先に埋め込むことだ。

## Required Additive Fields

### `campaign_threshold`

常に emit する。

```json
{
  "kind": "toggle_bits_hit",
  "value": 3,
  "aggregation": "bitwise_or_across_trials"
}
```

### `campaign_measurement`

常に emit する。

```json
{
  "bits_hit": 3,
  "threshold_satisfied": true,
  "wall_time_ms": 0.529,
  "steps_executed": 1
}
```

## Mapping Rules

### Success payload

`status == "ok"` のとき:

- `campaign_measurement.bits_hit` <- `toggle_coverage.bits_hit`
- `campaign_measurement.threshold_satisfied` <- `toggle_coverage.bits_hit >= 3`
- `campaign_measurement.wall_time_ms` <- `performance.wall_time_ms`
- `campaign_measurement.steps_executed` <- `inputs.steps`

### Error payload

`status != "ok"` のときも `campaign_measurement` は省略しない。

- `campaign_measurement.bits_hit` <- `toggle_coverage.bits_hit` if present else `0`
- `campaign_measurement.threshold_satisfied` <- `false`
- `campaign_measurement.wall_time_ms` <- `performance.wall_time_ms` if present else `null`
- `campaign_measurement.steps_executed` <- `inputs.steps`

v1 では error payload でも schema を壊さないことを優先する。
comparison runner 側の `reject` / `unresolved` semantics は
[socket_m1_campaign_proof_matrix.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/socket_m1_campaign_proof_matrix.md)
で扱う。

## Backward-Compat Rules

WP0 で守るべきこと:

- `schema_version` stays `1`
- `toggle_coverage.bits_hit` stays available
- `toggle_coverage.any_hit` stays available
- `performance.wall_time_ms` stays available when currently available
- `artifacts`, `commands`, `outputs`, `host_probe`, `flow_summary` stay intact

WP0 でやってはいけないこと:

- `toggle_coverage` を削る
- `performance` を `campaign_measurement` に吸収する
- `schema_version` を `2` に上げる
- `campaign_threshold` を CLI flag から受けるようにする

## Required Tests

### H0-1: happy path additive fields

既存の happy-path contract test を更新して、

- `campaign_threshold.kind == "toggle_bits_hit"`
- `campaign_threshold.value == 3`
- `campaign_threshold.aggregation == "bitwise_or_across_trials"`
- `campaign_measurement.bits_hit == toggle_coverage.bits_hit`
- `campaign_measurement.threshold_satisfied == true`
- `campaign_measurement.wall_time_ms == performance.wall_time_ms`
- `campaign_measurement.steps_executed == inputs.steps`

を固定する。

### H0-2: existing fields preserved

既存の contract から次が消えていないことを固定する。

- `toggle_coverage`
- `performance`
- `artifacts.classifier_report`
- `outputs.done_o`

### H0-3: error path stays normalized

failure-side test を追加して、

- `status == "error"`
- `campaign_threshold` exists
- `campaign_measurement` exists
- `campaign_measurement.threshold_satisfied == false`
- `campaign_measurement.steps_executed == inputs.steps`

を固定する。

## Required Write Set

- `src/runners/run_socket_m1_stock_hybrid_validation.py`
- `src/scripts/tests/test_run_socket_m1_stock_hybrid_validation.py`

## Exit

この packet は次で満たされる。

1. checked-in hybrid JSON が `campaign_threshold` を持つ
2. checked-in hybrid JSON が `campaign_measurement` を持つ
3. `schema_version=1` の additive change である
4. happy path と error path の contract test がある
