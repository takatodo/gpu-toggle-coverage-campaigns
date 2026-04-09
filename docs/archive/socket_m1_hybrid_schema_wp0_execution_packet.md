# `tlul_socket_m1` Hybrid Schema WP0 Execution Packet

## Purpose

この packet は
[socket_m1_hybrid_schema_normalization_packet.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/socket_m1_hybrid_schema_normalization_packet.md)
を、CC がそのまま実装できる最小 write set に落とした WP0 execution packet である。

対象は
[run_socket_m1_stock_hybrid_validation.py](/home/takatodo/gpu-toggle-coverage-campaigns/src/runners/run_socket_m1_stock_hybrid_validation.py)
だけで、baseline runner や comparison runner にはまだ入らない。

## Weakest Point

いま一番弱い点は、WP0 の policy 自体は決まったが、

- 既存 runner のどの seam を触るか
- `campaign_measurement` をどの値から導出するか
- happy-path / error-path をどの test で固定するか

が実装単位まで固定されていないことだ。

このままだと CC は field を足せても、

- `toggle_coverage` を消す
- `schema_version` を上げる
- error payload で `campaign_measurement` を省略する

ような drift を起こしやすい。

## Target File

- [run_socket_m1_stock_hybrid_validation.py](/home/takatodo/gpu-toggle-coverage-campaigns/src/runners/run_socket_m1_stock_hybrid_validation.py)
- [test_run_socket_m1_stock_hybrid_validation.py](/home/takatodo/gpu-toggle-coverage-campaigns/src/scripts/tests/test_run_socket_m1_stock_hybrid_validation.py)

## Existing Seam

実装 seam は 1 箇所で十分。

- `_build_validation_payload(...)`

ここですでに:

- `toggle_words`
- `status`
- `toggle_coverage`
- `performance`
- `inputs.steps`

が全部揃っている。

したがって WP0 は runner 全体をいじらず、
`_build_validation_payload()` の additive patch に限定する。

## Decision

### No refactor

WP0 では新しい helper を増やさない。

理由:

- logic は 4 field の静的写像だけ
- shared helper に切り出すほど複雑でない
- baseline/comparison 実装は別 packet でまとめて設計する

### Additive only

- `schema_version` stays `1`
- existing keys stay unchanged
- new keys are:
  - `campaign_threshold`
  - `campaign_measurement`

## Required Mapping

### Step 1: compute `toggle_summary`

既存 code の `toggle_coverage_summary(toggle_words)` を一度だけ呼び、
local 変数に束ねる。

```python
toggle_summary = toggle_coverage_summary(toggle_words)
```

### Step 2: compute `campaign_threshold`

固定値:

```python
campaign_threshold = {
    "kind": "toggle_bits_hit",
    "value": 3,
    "aggregation": "bitwise_or_across_trials",
}
```

### Step 3: compute `campaign_measurement`

導出規則:

- `bits_hit` <- `toggle_summary["bits_hit"]`
- `threshold_satisfied` <- `toggle_summary["bits_hit"] >= 3 and status == "ok"`
- `wall_time_ms` <- `metrics.get("wall_time_ms")`
- `steps_executed` <- `args.steps`

注意:

- `wall_time_ms` は error path では `None` でもよい
- `threshold_satisfied` は error path なら必ず `False`

## Required Payload Shape

runner JSON は既存 payload に次を追加する。

```json
{
  "campaign_threshold": {
    "kind": "toggle_bits_hit",
    "value": 3,
    "aggregation": "bitwise_or_across_trials"
  },
  "campaign_measurement": {
    "bits_hit": 3,
    "threshold_satisfied": true,
    "wall_time_ms": 0.529,
    "steps_executed": 1
  }
}
```

### Placement Rule

JSON key orderは本質ではないが、読みやすさのため

- `toggle_coverage`
- `campaign_threshold`
- `campaign_measurement`
- `performance`

の順を推奨する。

## Test Delta

### T1: extend existing happy-path test

既存の
[test_run_socket_m1_stock_hybrid_validation.py](/home/takatodo/gpu-toggle-coverage-campaigns/src/scripts/tests/test_run_socket_m1_stock_hybrid_validation.py)
の happy-path test に次を追加する。

- `payload["schema_version"] == 1`
- `payload["campaign_threshold"]["kind"] == "toggle_bits_hit"`
- `payload["campaign_threshold"]["value"] == 3`
- `payload["campaign_threshold"]["aggregation"] == "bitwise_or_across_trials"`
- `payload["campaign_measurement"]["bits_hit"] == payload["toggle_coverage"]["bits_hit"]`
- `payload["campaign_measurement"]["threshold_satisfied"] is True`
- `payload["campaign_measurement"]["wall_time_ms"] == payload["performance"]["wall_time_ms"]`
- `payload["campaign_measurement"]["steps_executed"] == payload["inputs"]["steps"]`

### T2: add error-path contract test

新しい failure-side test を追加する。

mock `subprocess.run()` should return:

- `returncode != 0`
- no `flow_json` written
- maybe minimal stderr/stdout

固定すること:

- `payload["status"] == "error"`
- `payload["campaign_threshold"]` exists
- `payload["campaign_measurement"]` exists
- `payload["campaign_measurement"]["bits_hit"] == 0`
- `payload["campaign_measurement"]["threshold_satisfied"] is False`
- `payload["campaign_measurement"]["steps_executed"] == payload["inputs"]["steps"]`
- `payload["schema_version"] == 1`
- `payload["toggle_coverage"]["bits_hit"] == 0`

## Must Not Change

- `support_tier`
- `acceptance_gate`
- `artifacts.classifier_report`
- `toggle_coverage`
- `performance`
- `stdout_tail` / `stderr_tail` behavior on failure

## Proof Commands

最小 proof:

```bash
python3 -m unittest src.scripts.tests.test_run_socket_m1_stock_hybrid_validation
```

望ましい follow-up:

```bash
python3 -m unittest discover -s src/scripts -p 'test_*.py'
```

## Exit

この packet は次で完了。

1. checked-in hybrid runner が additive に campaign fields を出す
2. `schema_version` は 1 のまま
3. happy-path test が normalized fields を固定する
4. error-path test が schema stability を固定する
