# `tlul_fifo_sync` Promotion Packet

## Purpose

この文書は、`tlul_fifo_sync` を current `thin_top_reference_design` から
**supported target (`Tier S`) に昇格させるかどうか**を判断するための packet である。

技術的 weakest point はもう GPU parity ではない。
それは [tlul_fifo_sync_stock_hybrid_validation.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/tlul_fifo_sync_stock_hybrid_validation.json)
が `thin_top_edge_parity_v1` pass を返している時点で閉じている。

残っているのは、**`Tier R` と `Tier S` の差を何で定義するか**だけである。

## Current Truth

- minimum goal は `tlul_socket_m1` で達成済み
- `tlul_request_loopback` は `phase_b_reference_design`
- `tlul_fifo_sync` は `thin_top_reference_design`
- checked-in source of truth:
  - [socket_m1_stock_hybrid_validation.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/socket_m1_stock_hybrid_validation.json)
  - [tlul_request_loopback_stock_hybrid_validation.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/tlul_request_loopback_stock_hybrid_validation.json)
  - [tlul_fifo_sync_stock_hybrid_validation.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/tlul_fifo_sync_stock_hybrid_validation.json)
- repo-wide scoreboard:
  - [rtlmeter_ready_scoreboard.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/rtlmeter_ready_scoreboard.json)
  - current counts: `Tier S=1`, `Tier R=2`, `Tier B=3`, `Tier T=3`, `Tier M=0`
- branch audit:
  - [rtlmeter_expansion_branch_audit.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/rtlmeter_expansion_branch_audit.json)
  - `maximize_second_r_or_s_candidate` is already met
  - current recommendation is `defer_second_target`

## Weakest Point

いま一番弱い点は、`tlul_fifo_sync` が技術的には reference surface として成立しているのに、
**supported に上げるための追加条件が定義されていない**ことだ。

このままだと次の 2 つが起きやすい。

- `Tier R` と `Tier S` の違いが人によって変わる
- もう終わった parity work を再度掘り返して、promotion judgement がぶれる

## Promotion Question

次に決めるべき問いは 1 つ。

**`thin_top_edge_parity_v1` の先に、何を supported gate として要求するか。**

候補は大きく 3 つある。

### Option A: Keep Tier R

- `tlul_fifo_sync` は reference surface のまま据え置く
- supported は引き続き `socket_m1` 単独
- 利点:
  - 追加 delivery risk が最小
  - current README goal には影響しない
- 欠点:
  - thin-top branch は proving surface で止まり、supported flow にはならない

### Option B: Promote On Stronger Parity

- `thin_top_edge_parity_v1` に加えて、より広い再現条件を要求する
- 候補:
  - `nstates > 1`
  - `steps > 1`
  - 複数 edge sequence
  - additional output / watch contract
- 利点:
  - 昇格理由が still technical で説明しやすい
- 欠点:
  - 何を “十分強い parity” とみなすかを先に決める必要がある

### Option C: Promote On Product Contract

- parity はもう通っている前提で、
  user-facing supported flow 条件を追加する
- 候補:
  - stable quickstart entrypoint
  - stable validation schema with campaign metrics
  - documented host-driven operation contract
- 利点:
  - `Tier S` を「技術証明」ではなく「運用可能 surface」として定義できる
- 欠点:
  - `socket_m1` の supported 基準と揃える整理が必要

## Recommended Next Decision

current milestone で open にしてよい問いでは、もうない。
まず project decision を固定する。

1. current milestone では `tlul_fifo_sync` を `Tier R` に据え置く
2. 次 milestone で昇格を再開する場合だけ、Option B と Option C のどちらで gate を定義するかを再度開く

この packetの推奨は次。

- default: **Option A**
  - current milestone では `Tier R` に据え置く
- promote を本当にやるなら:
  - **Option C** を先に選ぶ
  - 理由:
    - parity 基盤はすでにある
    - 次の曖昧さは semantics より supported contract 側にある

## Current Milestone Decision

2026-04-04 時点の checked-in decision は次。

- `tlul_fifo_sync` は current milestone では `Tier R` に据え置く
- `socket_m1` を唯一の `Tier S` として維持する
- `thin_top_supported_v1` は **採用済み gate ではなく、次 milestone 用の proposal** として保持する

つまり、この packet の役割は「いま昇格するか」を再議論することではなく、
**昇格を再開する時に何を gate 名と必須条件にするかを固定しておくこと**である。

## Gap vs `socket_m1`

`tlul_fifo_sync` をすぐ `Tier S` に上げない weakest point は、
技術証明ではなく **supported contract がまだ `socket_m1` と同じ形で固定されていない**ことだ。

比較するとこうなる。

### すでに満たしているもの

- stable validation JSON がある
- `output/validation/` に source of truth を置ける
- host probe / host->GPU handoff / final state / classifier report path を返す
- toggle coverage と performance summary を返す
- checked-in gate が pass している

### まだ弱いもの

- `socket_m1` のような supported entrypoint が docs 上で明示されていない
- `thin_top_edge_parity_v1` は reference gate としては十分だが、
  「supported flow として何を保証するか」がまだ別名で固定されていない
- current caveat が明示的に `not a supported target` を含む

要するに、`tlul_fifo_sync` の gap は **技術不足ではなく product contract 不足** である。

## Proposed Supported Gate

もし `tlul_fifo_sync` を `Tier S` に上げるなら、次の gate 名を使うのが妥当。

- `thin_top_supported_v1`

### Proposed Criteria

1. `thin_top_edge_parity_v1` が pass している
2. `host_clock_control=true` かつ `host_reset_control=true`
3. `toggle_coverage.any_hit=true`
4. `commands.flow` が docs で supported entrypoint として公開されている
5. validation JSON の `caveats` から `not a supported target` を外してよいと判断できる

### Proposed Non-Criteria

これらは `thin_top_supported_v1` の必須条件にはしない。

- `strict_final_state`
- `tlul_request_loopback` と同時昇格
- multi-design generalization
- quickstart shell の追加

### Why This Gate

- parity 系の technical proof はもう揃っている
- 次の差分は運用面の commitment だけだから
- `socket_m1` と違って `clock_ownership=host_direct_ports` なのは弱点ではなく、
  むしろ contract 上は強い

## Recommendation

packet としての checked-in recommendation は次の順。

1. current milestone では依然として `Tier R` に据え置く
2. 次 milestone で昇格を本当にやるなら、まず `thin_top_supported_v1` を採用するか決める
3. 採用するなら、残る実装は「supported entrypoint の明示」と「validation caveat の更新」に絞る

## In Scope

- `tlul_fifo_sync` だけを見る
- `Tier R -> Tier S` の gate を文章で固定する
- 必要なら stable validation runner / docs の required fields を追加する

## Out Of Scope

- `tlul_request_loopback` promotion
- `strict_final_state`
- `tlul_socket_1n`, `tlul_err`, `tlul_sink`
- non-OpenTitan expansion

## Proof Inputs

promotion judgement の再確認に使う artifact は次。

- [tlul_fifo_sync_stock_hybrid_validation.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/tlul_fifo_sync_stock_hybrid_validation.json)
- [tlul_fifo_sync_host_probe_report.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_probe_report.json)
- [tlul_fifo_sync_host_edge_trace.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_edge_trace.json)
- [tlul_fifo_sync_host_gpu_flow_watch_summary.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json)
- [tlul_fifo_sync_handoff_parity_summary.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_handoff_parity_summary.json)

## Proof Commands

```bash
python3 src/runners/run_tlul_fifo_sync_stock_hybrid_validation.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl

python3 src/tools/audit_rtlmeter_ready_scoreboard.py \
  --json-out work/rtlmeter_ready_scoreboard.json

python3 src/tools/audit_rtlmeter_expansion_branches.py \
  --scoreboard work/rtlmeter_ready_scoreboard.json \
  --feasibility work/second_target_feasibility_audit.json \
  --json-out work/rtlmeter_expansion_branch_audit.json
```

## Exit States

### Exit A: Keep Tier R

- docs say `tlul_fifo_sync` is a checked-in reference surface
- no extra code work is required
- this is the **current checked-in exit**

### Exit B: Define Tier S Gate

- one new gate name exists
- required artifact fields are listed
- success / fail criteria are explicit

### Exit C: Defer

- current milestone remains `socket_m1`-only supported
- `tlul_fifo_sync` remains useful as a thin-top reference surface
