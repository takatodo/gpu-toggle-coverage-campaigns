# `tlul_fifo_sync` Thin-Top Design

## Purpose

この文書は、`tlul_fifo_sync` を 2 本目の supported stock-hybrid target 候補として再開する場合の
**thin-top branch** を、Claude Code に渡せる実装単位まで落とすための設計メモである。

## Implementation Status (2026-04-04)

2026-04-04 時点で、thin-top branch は「設計だけ」ではなく、stable reference surface まで実装済みである。

- landed:
  - `tlul_fifo_sync_gpu_cov_tb.sv` は shared core + timed wrapper に分離済み
  - `tlul_fifo_sync_gpu_cov_host_tb.sv` が追加済み
  - `bootstrap_hybrid_tlul_slice_cc.py --tb-path ... --top-module tlul_fifo_sync_gpu_cov_host_tb`
    で `work/vl_ir_exp/tlul_fifo_sync_host_vl` を bootstrap/build できる
  - `run_tlul_slice_host_probe.py` が host wrapper 上で
    `host_clock_control=true`, `host_reset_control=true` を返す
  - `run_tlul_fifo_sync_stock_hybrid_validation.py` が
    `output/validation/tlul_fifo_sync_stock_hybrid_validation.json` を生成し、
    `support_tier=thin_top_reference_design`,
    `acceptance_gate=thin_top_edge_parity_v1`,
    `clock_ownership=host_direct_ports` を固定する
- still open:
  - この `Tier R` surface をそのまま維持するか、
    追加 gate を定義して `Tier S` を目指すかは未決

## Weakest Point

いまの weakest point は、thin-top branch の技術的 proof は `Tier R` まで閉じているのに、
**その surface を supported へ昇格させるべきかどうかの gate が未定義**なことだ。

根拠:

- host wrapper probe は
  [tlul_fifo_sync_host_probe_report.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_probe_report.json)
  で `clock_ownership=host_direct_ports`, `host_clock_control=true`,
  `host_reset_control=true` を返している
- host wrapper probe は
  [tlul_fifo_sync_host_probe_report.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_probe_report.json)
  で `clock_ownership=host_direct_ports`, `host_clock_control=true`,
  `host_reset_control=true` を返している
- host-only edge trace
  [tlul_fifo_sync_host_edge_trace.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_edge_trace.json)
  は checked-in `1,0` sequence で design-visible delta を返す
- CPU parity probe
  [tlul_fifo_sync_handoff_parity_summary.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_handoff_parity_summary.json)
  は host `eval_step`、direct CPU `root___eval`、fake-`vlSymsp` CPU `root___eval`、
  raw-state-import CPU `root___eval` が internal-only residual まで揃うことを示している
- GPU replay summary
  [tlul_fifo_sync_host_gpu_flow_watch_summary.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json)
  も `edge_parity.all_edges_internal_only=true` を返す
- stable validation surface
  [tlul_fifo_sync_stock_hybrid_validation.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/tlul_fifo_sync_stock_hybrid_validation.json)
  は `thin_top_edge_parity_v1` pass を固定している

つまり、現在の branch は「host-owned `clk/reset` を証明する top」も
「checked-in edge parity を `Tier R` gate として固定すること」も終えている。
残っているのは promotion policy だけである。

## Design Constraint

**既存 TB 3865 行をコピペした新 top は作らない。**

その方針の理由:

- copy-based fork は current timed wrapper と host-driven wrapper の semantic drift を招く
- 2 本目以降の design へ一般化しにくい
- AGENTS の「何でも専用スクリプト / 専用 top を増やさない」に反する

## Recommended Shape

推奨構成は **shared core + 2 wrappers** である。

### 1. shared core

新しい中核 module を切る。

仮名:

- `tlul_fifo_sync_gpu_cov_core`

役割:

- 既存 `tlul_fifo_sync_gpu_cov_tb` の本体ロジックをここへ寄せる
- explicit な `clk_i` / `rst_ni` を入力として受ける
- `cfg_*`、toggle、progress、debug、trace metric の interface を維持する
- `tlul_fifo_sync` DUT と traffic / replay / metric 更新の本体を持つ

この core には **timed clock coroutine を入れない**。

### 2. timed wrapper

現行の `tlul_fifo_sync_gpu_cov_tb` は wrapper 化する。

役割:

- 既存の top module 名を維持する
- `always #5 clk_i = ~clk_i` をここだけに残す
- 既存の `reset_like_w -> rst_ni` 派生もここに残す
- current `tb_timed_coroutine` branch の artifact 互換を維持する

### 3. host-driven wrapper

新しい host-driven top を追加する。

仮名:

- `tlul_fifo_sync_gpu_cov_host_tb`

役割:

- host-owned `clk_i` と `rst_ni` を top-level field として持つ
- `cfg_*` も現行 TB と同じ名前で持つ
- shared core を instantiate するだけの薄い wrapper にする
- internal timed event / `always #5` / wrapper-local reset synthesis は持たない

重要:

- generic host probe を再利用したいので、field 名は可能な限り現行 convention に合わせる
- reset field は `rst_ni` に寄せる
- `clk_i` も top-level の raw root field として直接見える形にする

## Why This Shape

この形の利点は 3 つある。

1. current timed model を壊さない  
   `tlul_fifo_sync_gpu_cov_tb` の top 名と semantic surface を残せる。

2. thin-top branch の proof target が明確になる  
   `tlul_fifo_sync_gpu_cov_host_tb` だけを build/probe/handoff すればよい。

3. drift を最小化できる  
   traffic generator / replay logic / metric logic の本体は 1 箇所に寄る。

## Required Proof Gates

thin-top branch を「実装に進んだ」と言うための gate は次の順。

### Gate A: bootstrap/build

- `bootstrap_hybrid_tlul_slice_cc.py` が host-driven wrapper を `--tb-path` / `--top-module` で bootstrap できる
- `build_vl_gpu.py` が cubin / meta / classifier report まで完走する

### Gate B: host-owned control

host probe で次を示す。

- `clk_i` が raw root field として直接 writable
- `rst_ni` が raw root field として直接 writable
- timed event を drain しなくても host が step/reset を意味ある単位で進められる

最低報告項目:

- `host_clock_control=true`
- `host_reset_control=true`
- `events_pending_after_init=false` もしくは「pending event は host-owned stepping に無関係」と説明できること

Status (2026-04-04):

- pass
- artifact:
  - [tlul_fifo_sync_host_probe_report.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_probe_report.json)
- observed facts:
  - `clock_field_name="clk_i"`
  - `reset_field_name="rst_ni"`
  - `clock_ownership="host_direct_ports"`
  - `host_clock_control=true`
  - `host_reset_control=true`

### Gate C: host->GPU handoff

- host baseline が未完了 state を残す
- GPU replay 後に watched field か generic outputs に delta が出る

最低限見たいもの:

- `changed_watch_field_count > 0`
  または
- `progress_cycle_count_o` / `progress_signature_o` / relevant FIFO signal が host baseline から動く

Status (2026-04-04):

- pass at `Tier R`
- artifact:
  - [tlul_fifo_sync_host_gpu_flow_watch_summary.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json)
  - [tlul_fifo_sync_stock_hybrid_validation.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/tlul_fifo_sync_stock_hybrid_validation.json)
- current result:
  - host-only edge trace already shows design-visible delta on the checked-in `1,0` sequence
  - final compare still reports `changed_watch_field_count=0`, but edge-by-edge parity is internal-only
  - `thin_top_edge_parity_v1` therefore passes as a checked-in reference gate
- parity result:
  - host-only vs CPU parity is internal-only
  - host-only vs GPU parity is internal-only
  - validation runner records this under `edge_parity_gate.passed=true`

### Gate D: promotion decision

この段階で初めて、

- `Tier R` のまま据え置く
  か
- `Tier R -> Tier S`

の判断に進む。

## Concrete Work Packages For CC

### WP1: extract shared core

- `tlul_fifo_sync_gpu_cov_tb.sv` から core 本体を分離する
- current timed wrapper の top 名と outputs を維持する
- 既存 current-model artifacts が semantic に変わらないことを確認する

Status: done (2026-04-04)

### WP2: add host-driven wrapper

- `tlul_fifo_sync_gpu_cov_host_tb.sv` を追加する
- `clk_i`, `rst_ni`, `cfg_*` を top-level field として expose する
- wrapper-local clock coroutine を持たない

Status: done (2026-04-04)

### WP3: add thin-top bootstrap path

- launch template か bootstrap path を 1 本追加する
- `bootstrap_hybrid_tlul_slice_cc.py` から new top を bootstrappable にする

Status: done (2026-04-04)

### WP4: add host-driven probe

- generic host probe を再利用できるならそのまま使う
- 使えないなら `tlul_fifo_sync` 専用の very thin probe を追加する
- ただし wrapper 固有 probe を増やしすぎない

Status: done (2026-04-04)

### WP5: run first handoff pilot

- host baseline state dump
- GPU replay
- watch summary

ここで初めて `current-model branch` と差が出るかを見る。

Status: done for `Tier R` (2026-04-04)

2026-04-04 update:

- parity packet は実行済み
- 結論は、checked-in `1,0` edge sequence について host/CPU/GPU residual が internal-only まで揃うこと
- その結果は stable validation runner に昇格済み
- 次の実装タスクは GPU parity 修正ではなく、`Tier R -> Tier S` promotion gate を定義すること

## Explicit Non-Goals

- `tlul_request_loopback` をこの branch に巻き込まない
- `strict_final_state` を thin-top branch の blocker にしない
- `cpu_replay_tb` wrapper をそのまま supported top に昇格させない

## Decision Rule

次 milestone の最初の branch decision は次でよい。

- 2 本目 target を本当に追う  
  -> yes ならこの文書の `shared core + 2 wrappers` を前提に、promotion gate 定義へ進む
- そこまで踏み込まない  
  -> no なら `socket_m1` 単独 supported を維持し、`tlul_fifo_sync` は `thin_top_reference_design` として凍結する
