# `tlul_socket_m1` Time-to-Threshold Execution Packet

## Purpose

この packet は [socket_m1_time_to_threshold_packet.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/socket_m1_time_to_threshold_packet.md)
を、CC が実装できる work package に分解した execution packet である。

## Weakest Point

initial weakest point は、comparison contract 自体は定義したが、

- どの runner を新設するか
- どこまで既存 code を再利用してよいか
- 何を proof gate にするか

がまだ implementation 単位まで固定されていないことだった。

特に注意すべきは、既存の generic baseline runner をそのまま再利用しないことだ。

- [run_opentitan_tlul_slice_gpu_baseline.py](/home/takatodo/gpu-toggle-coverage-campaigns/src/runners/run_opentitan_tlul_slice_gpu_baseline.py)
  は sim-accel / legacy baseline line のため、
  current stock-Verilator CPU baseline の source of truth には使わない

comparison v1 の baseline は、**stock Verilator `--cc` 出力に対する CPU-only runner** として新設済みである。

さらに、comparison 実装に入る前の drift point として次があった。

- current hybrid JSON は `toggle_coverage.bits_hit` を持つ
- だが `campaign_threshold` / `campaign_measurement` block はまだ持たなかった

この点は WP0 で解消済みで、実装順としては baseline/comparison が次の段階になる。
そのうえで schema contract の source of truth は
[socket_m1_campaign_schema_packet.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/socket_m1_campaign_schema_packet.md)
とする。
WP0 の additive/backward-compat source of truth は
[socket_m1_hybrid_schema_normalization_packet.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/socket_m1_hybrid_schema_normalization_packet.md)
とする。
comparison semantics の source of truth は
[socket_m1_campaign_proof_matrix.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/socket_m1_campaign_proof_matrix.md)
とする。

## Checked-In Reuse

再利用するもの:

- [run_socket_m1_host_probe.py](/home/takatodo/gpu-toggle-coverage-campaigns/src/tools/run_socket_m1_host_probe.py)
- [socket_m1_host_probe.cpp](/home/takatodo/gpu-toggle-coverage-campaigns/src/hybrid/socket_m1_host_probe.cpp)
- [run_socket_m1_stock_hybrid_validation.py](/home/takatodo/gpu-toggle-coverage-campaigns/src/runners/run_socket_m1_stock_hybrid_validation.py)
- [stock_hybrid_validation_common.py](/home/takatodo/gpu-toggle-coverage-campaigns/src/runners/stock_hybrid_validation_common.py)
- [socket_m1_time_to_threshold_packet.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/socket_m1_time_to_threshold_packet.md)

再利用しないもの:

- [run_opentitan_tlul_slice_gpu_baseline.py](/home/takatodo/gpu-toggle-coverage-campaigns/src/runners/run_opentitan_tlul_slice_gpu_baseline.py)
  - reason: sim-accel / legacy backend line
- legacy family validation runners
  - reason: backend and metric semantics differ from current stock-hybrid line

## Target Artifacts

### Baseline JSON

- `output/validation/socket_m1_cpu_baseline_validation.json`

### Comparison JSON

- `output/validation/socket_m1_time_to_threshold_comparison.json`

## Work Packages

### WP1: CPU baseline runner

Create:

- `src/runners/run_socket_m1_cpu_baseline_validation.py`

May add:

- a small helper under `src/tools/` if the runner needs a reusable stepping wrapper
- tests under `src/scripts/tests/`

Must not do:

- route through sim-accel
- define a different threshold schema than the hybrid side

Required behavior:

1. build or reuse the stock-Verilator `socket_m1` host binary
2. run CPU-only stepping on the same design surface
3. compute:
   - `campaign_threshold`
   - `coverage.bits_hit`
   - `coverage.any_hit`
   - `performance.wall_time_ms`
   - `performance.steps_executed`
4. emit stable JSON under `output/validation/`

### WP0: schema normalization on the hybrid side

Update:

- `src/runners/run_socket_m1_stock_hybrid_validation.py`

Required behavior:

1. emit `campaign_threshold`
2. emit `campaign_measurement`
3. keep existing fields intact

Do this before or together with WP1, so comparison does not depend on packet hardcode.
Do not change `schema_version` in WP0; this is an additive normalization step only.
Status:

- checked-in implementation complete

### WP2: comparison runner

Create:

- `src/runners/run_socket_m1_time_to_threshold_comparison.py`

Required behavior:

1. read:
   - `socket_m1_cpu_baseline_validation.json`
   - `socket_m1_stock_hybrid_validation.json`
2. verify threshold compatibility
3. reject mismatched threshold schema
4. emit `comparison_ready=false` / `winner=unresolved` when threshold is not satisfied by both sides
5. emit:
   - `baseline.campaign_measurement`
   - `hybrid.campaign_measurement`
   - `comparison_ready`
   - `speedup_ratio`
   - `winner`
   - `caveats`

Status:

- checked-in implementation complete

### WP3: docs sync

Update only after WP1 and WP2 exist:

- `README.md`
- `docs/status_surfaces.md`
- `docs/input_output_map.md`
- `docs/roadmap_tasks.md`

Status:

- current status surfaces and roadmap docs now point at the checked-in baseline/comparison artifacts

## Threshold v1

Use exactly:

- `campaign_threshold.kind = toggle_bits_hit`
- `campaign_threshold.value = 3`

Do not strengthen the threshold during WP1/WP2.
If stronger closure criteria are wanted later, do that in a separate packet.

## Fairness Rules

### Baseline side

- serial CPU stepping is acceptable
- one state at a time is acceptable
- OR-aggregation of toggle bitmap across trials is acceptable

### Hybrid side

- checked-in supported `socket_m1` flow remains unchanged
- current source of truth stays:
  [socket_m1_stock_hybrid_validation.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/socket_m1_stock_hybrid_validation.json)

### Comparison rule

compare `wall_time_ms to reach threshold`, not raw throughput.

## Proof Gates

### Gate A: baseline JSON exists

pass when:

- `output/validation/socket_m1_cpu_baseline_validation.json` is emitted
- schema includes `campaign_threshold` / `campaign_measurement` / performance sections

### Gate 0: hybrid schema normalized

pass when:

- `socket_m1_stock_hybrid_validation.json` emits
  - `campaign_threshold`
  - `campaign_measurement`

### Gate B: threshold compatibility

pass when:

- baseline and hybrid JSON both report
  - `campaign_threshold.kind = toggle_bits_hit`
  - `campaign_threshold.value = 3`

### Gate C: comparison JSON exists

pass when:

- `output/validation/socket_m1_time_to_threshold_comparison.json` is emitted
- `comparison_ready`, `speedup_ratio`, and `winner` are explicit

### Gate D: campaign line is measurable

pass when:

- repo can answer whether hybrid beats CPU baseline for `socket_m1`
- even if hybrid does not win, the comparison contract is stable and reusable

## Suggested Tests

Add tests for:

- baseline runner schema contract
- threshold compatibility rejection
- unresolved semantics when threshold is not reached
- comparison JSON schema and winner calculation

Do not add tests that depend on real GPU hardware for this packet.

## Out Of Scope

- `tlul_fifo_sync` baseline/comparison
- multi-design campaign comparison
- stronger threshold than `bits_hit >= 3`
- `strict_final_state`
- `tlul_request_loopback` promotion

## Exit

This packet is done when:

1. `socket_m1` CPU baseline JSON exists
2. `socket_m1` time-to-threshold comparison JSON exists
3. docs can point to those artifacts as the first campaign-speed source of truth
