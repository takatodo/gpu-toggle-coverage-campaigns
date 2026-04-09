# `tlul_socket_m1` Time-to-Threshold Packet

## Purpose

この packet は、project の real campaign goal

- **通常 sim より短い時間で coverage target を満たす**

を、最初の supported target `tlul_socket_m1` で checked-in artifact に落とすための実行パケットである。

minimum technical goal はすでに達成済みであり、
この packet が扱う weakest point はそこではない。

## Weakest Point

initial weakest point は、`socket_m1` に

- supported hybrid runner はある
- toggle summary もある
- GPU throughput もある

のに、**normal sim baseline と同じ threshold で比較する contract がない**ことだ。

その gap は now closed for `socket_m1`。
現在の weakest point は、同じ comparison loop がまだ第2 design に広がっていないことだ。

このままだと次の 3 つが起きる。

- hybrid の `steps_per_second` を campaign success と誤読する
- CPU baseline が single-state / single-seed / different threshold で drift する
- 「速い」の意味が人によって変わる

## Current Truth

checked-in source of truth:

- [socket_m1_stock_hybrid_validation.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/socket_m1_stock_hybrid_validation.json)
- [socket_m1_cpu_baseline_validation.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/socket_m1_cpu_baseline_validation.json)
- [socket_m1_time_to_threshold_comparison.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/socket_m1_time_to_threshold_comparison.json)
- [socket_m1_host_gpu_flow_summary.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/socket_m1_vl/socket_m1_host_gpu_flow_summary.json)
- [socket_m1_host_probe_report.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/socket_m1_vl/socket_m1_host_probe_report.json)

known facts:

- `support_tier=first_supported_target`
- `acceptance_gate=phase_b_endpoint`
- `clock_ownership=tb_timed_coroutine`
- checked-in hybrid validation already reports:
  - `toggle_coverage.bits_hit`
  - `toggle_coverage.any_hit`
  - `performance.wall_time_ms`
  - `performance.throughput.state_steps_per_second`

resolved facts:

- normal sim baseline for the same target now exists
- the shared threshold definition is fixed at `toggle_bits_hit >= 3`
- a comparison artifact now answers `time_to_threshold`
- normalized campaign fields are present in the checked-in hybrid JSON itself

remaining missing fact:

- the same comparison loop is not yet checked in for a second design surface

## Comparison Contract

comparison は、次の 4 点を固定して行う。

1. same design surface
   - `tlul_socket_m1_gpu_cov_tb`
2. same threshold definition
   - coverage target は baseline / hybrid で同一
3. same state family generator
   - seed progression や host reset/post-reset template を揃える
4. same success question
   - `how long until threshold T is reached`

比較対象を「throughput」だけにしない。
campaign goal は throughput ではなく **wall-clock-to-threshold** だからである。

## First Threshold Proposal

v1 では threshold を次で固定する。

- `threshold_kind = toggle_bits_hit`
- `threshold_value = 3`

理由:

- checked-in hybrid source of truth がすでに `bits_hit=3` を返している
- `any_hit=true` よりは弱すぎず、追加 instrumentation なしで両系に載せられる
- first comparison packet の目的は「比較 loop を固定すること」であり、
  最終 campaign threshold を一気に決めることではない

### Non-goal For v1

v1 の threshold は、最終 campaign の coverage closure 条件ではない。

今は次を先に固定する。

- threshold を machine-readable にする
- normal sim と hybrid を同じ threshold で比較する
- comparison artifact を checked-in にする

より強い threshold

- coverage ratio
- region completion
- campaign rule completion

は v2 以降でよい。

## Fairness Rules

v1 比較の fairness rule は次。

### CPU baseline

- stock Verilator C++ を CPU only で回す
- 1 state at a time
- per-trial toggle bitmap を OR 集約する
- `bits_hit >= 3` に到達するまで wall-clock を計測する

### Hybrid

- checked-in `socket_m1` supported flow を使う
- batched states をそのまま使ってよい
- batch 内 toggle bitmap を OR 集約する
- `bits_hit >= 3` に到達するまで wall-clock を計測する

### Why This Is Fair Enough For v1

- hybrid の強みは multi-state parallel exploration にあるので、そこを消さない
- baseline は serial exploration として自然
- 両者とも「同じ coverage target へどの時間で届いたか」を比較できる

## Proposed Artifacts

Before new artifacts, the existing hybrid artifact should be normalized.

See:

- [socket_m1_campaign_schema_packet.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/socket_m1_campaign_schema_packet.md)

### Baseline validation JSON

checked-in artifact:

- `output/validation/socket_m1_cpu_baseline_validation.json`

必要 field:

- `target`
- `backend=stock_verilator_cpu_baseline`
- `campaign_threshold`
- `coverage.bits_hit`
- `coverage.any_hit`
- `performance.wall_time_ms`
- `performance.steps_executed`
- `commands.flow`
- `artifacts`

### Comparison JSON

checked-in artifact:

- `output/validation/socket_m1_time_to_threshold_comparison.json`

必要 field:

- `target`
- `campaign_threshold`
- `baseline.runner_json`
- `hybrid.runner_json`
- `baseline.campaign_measurement`
- `hybrid.campaign_measurement`
- `comparison_ready`
- `speedup_ratio`
- `winner`
- `caveats`

## Recommended Implementation Order

1. Add a CPU baseline runner for `tlul_socket_m1`
   - first normalize the checked-in hybrid JSON schema
   - host probe / generated TB を流用し、CPU-only で step する
2. Make the baseline runner emit the threshold-oriented JSON above
3. Add a comparison tool / runner that reads:
   - `socket_m1_cpu_baseline_validation.json`
   - `socket_m1_stock_hybrid_validation.json`
4. Emit `socket_m1_time_to_threshold_comparison.json`
   - use the normalized artifact schema
   - do not reintroduce pre-normalization `threshold` / flattened fields
5. Only after that, decide whether v2 threshold should be stronger than `bits_hit >= 3`

## Work Packages For CC

### WP1: CPU baseline runner

Write scope:

- `src/runners/run_socket_m1_cpu_baseline_validation.py`
- tests under `src/scripts/tests/`

done when:

- baseline JSON is emitted under `output/validation/`
- threshold fields and wall time fields exist

Status:

- checked-in implementation complete

### WP2: comparison artifact

Write scope:

- `src/runners/run_socket_m1_time_to_threshold_comparison.py`
- tests under `src/scripts/tests/`

done when:

- comparison JSON reads baseline + hybrid source-of-truth artifacts
- `comparison_ready`, `speedup_ratio`, and `winner` are explicit
- reject vs unresolved semantics are fixed by
  [socket_m1_campaign_proof_matrix.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/socket_m1_campaign_proof_matrix.md)

Status:

- checked-in implementation complete

### WP3: docs sync

Write scope:

- `README.md`
- `docs/status_surfaces.md`
- `docs/input_output_map.md`

done when:

- baseline JSON and comparison JSON are documented as campaign artifacts

Status:

- current status surfaces and roadmap docs now point at the checked-in campaign artifacts

## Out Of Scope

- `tlul_fifo_sync` promotion
- stronger v2/v3 coverage thresholds
- proof semantics beyond the v1 matrix in `docs/socket_m1_campaign_proof_matrix.md`
- repo-wide multi-design comparison
- `strict_final_state`
- `tlul_request_loopback` promotion

## Exit States

### Exit A: v1 Comparison Exists

- `socket_m1_cpu_baseline_validation.json` exists
- `socket_m1_time_to_threshold_comparison.json` exists
- threshold is explicit and shared

### Exit B: Campaign Goal Still Open But Measurable

- project can now say whether hybrid beats CPU baseline for one checked-in target
- multi-design expansion can then reuse the same schema
