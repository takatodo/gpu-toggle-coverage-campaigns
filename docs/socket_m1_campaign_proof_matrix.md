# `tlul_socket_m1` Campaign Proof Matrix

## Purpose

この packet は、`socket_m1` campaign line の

- hybrid validation JSON
- CPU baseline validation JSON
- time-to-threshold comparison JSON

に対して、**何を test で固定するか**を明文化する proof matrix である。

## Weakest Point

いま一番弱い点は、schema packet と execution packet はあるのに、

- comparison runner が何を reject すべきか
- threshold 未到達を何として報告すべきか
- `winner` / `speedup_ratio` をいつ確定してよいか

がまだ曖昧なことだ。

さらに、古い packet の一部には

- `threshold`
- flattened `baseline.wall_time_ms`

のような pre-normalization 表現が残っていた。

comparison v1 はもうそれでは駄目で、source of truth は
**artifact 自身が持つ `campaign_threshold` / `campaign_measurement`** に統一する。

## Decision

comparison v1 は次の 2 段階で判定する。

1. `reject`
   - artifact schema が欠ける
   - `campaign_threshold` が一致しない
2. `resolve`
   - schema は一致する
   - そのうえで threshold 到達可否を見て
     - `winner = hybrid | baseline | tie`
     - または `winner = unresolved`

## Normalized Comparison Output

comparison JSON は少なくとも次を持つ。

```json
{
  "target": "tlul_socket_m1",
  "campaign_threshold": {
    "kind": "toggle_bits_hit",
    "value": 3,
    "aggregation": "bitwise_or_across_trials"
  },
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
  "winner": "hybrid",
  "caveats": []
}
```

## Reject Semantics

comparison runner は次を **reject** する。

- `campaign_threshold` が無い
- `campaign_measurement` が無い
- `campaign_threshold.kind` が不一致
- `campaign_threshold.value` が不一致
- `campaign_threshold.aggregation` が不一致

v1 では reject は「comparison artifact を campaign evidence として使ってはいけない」状態である。
runner は非ゼロ終了でよい。

## Unresolved Semantics

comparison runner は schema 互換だが threshold 未到達のとき、
それを reject ではなく **unresolved** として扱う。

具体的には:

- `comparison_ready = false`
- `winner = "unresolved"`
- `speedup_ratio = null`

とする。

この状態は「比較不能」ではなく、
**同じ threshold に対してまだどちらも勝者を宣言できない**
という campaign artifact である。

## Winner Rules

`comparison_ready = true` は、baseline / hybrid の両方が
`campaign_measurement.threshold_satisfied = true`
のときだけ立てる。

そのときの判定は次。

- `hybrid.wall_time_ms < baseline.wall_time_ms` -> `winner = "hybrid"`
- `hybrid.wall_time_ms > baseline.wall_time_ms` -> `winner = "baseline"`
- 同値 -> `winner = "tie"`

`speedup_ratio` は v1 では

```json
baseline.wall_time_ms / hybrid.wall_time_ms
```

とする。

## Required Tests

### H1: hybrid schema normalization

- `run_socket_m1_stock_hybrid_validation.py` は
  - `campaign_threshold`
  - `campaign_measurement`
  を出す
- 既存の
  - `toggle_coverage`
  - `performance`
  - `artifacts`
  は保持する

### B1: baseline schema normalization

- `run_socket_m1_cpu_baseline_validation.py` は
  - 同じ `campaign_threshold`
  - 同型の `campaign_measurement`
  を出す

### C1: threshold kind mismatch rejects

- `kind` 不一致なら comparison runner は reject する

### C2: threshold value mismatch rejects

- `value` 不一致なら comparison runner は reject する

### C3: aggregation mismatch rejects

- `aggregation` 不一致なら comparison runner は reject する

### C4: unresolved when threshold not reached

- 片方または両方が `threshold_satisfied=false` なら
  - `comparison_ready=false`
  - `winner="unresolved"`
  - `speedup_ratio=null`

### C5: hybrid win

- 両方 `threshold_satisfied=true`
- hybrid の `wall_time_ms` が小さい
- `winner="hybrid"`

### C6: baseline win

- 両方 `threshold_satisfied=true`
- baseline の `wall_time_ms` が小さい
- `winner="baseline"`

### C7: tie

- 両方 `threshold_satisfied=true`
- `wall_time_ms` が同値
- `winner="tie"`

## Required Write Set

- `src/runners/run_socket_m1_stock_hybrid_validation.py`
- `src/runners/run_socket_m1_cpu_baseline_validation.py`
- `src/runners/run_socket_m1_time_to_threshold_comparison.py`
- `src/scripts/tests/test_run_socket_m1_stock_hybrid_validation.py`
- future baseline / comparison contract tests under `src/scripts/tests/`

## Exit

この packet は次で満たされる。

1. hybrid JSON が normalized schema を持つ
2. baseline JSON が同じ schema を持つ
3. comparison runner が reject / unresolved / winner を区別する
4. comparison JSON が campaign evidence として読める
