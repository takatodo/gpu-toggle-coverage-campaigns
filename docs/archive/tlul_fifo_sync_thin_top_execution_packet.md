# `tlul_fifo_sync` Thin-Top Execution Packet

## Purpose

この文書は、`docs/tlul_fifo_sync_thin_top_design.md` を
**Claude Code がそのまま実装に着手できる execution packet** に変換したもの。
2026-04-04 時点では、WP1-WP5 を `Tier R` まで完了させた execution record でもある。

設計の再説明ではなく、次の 1 スプリントで

- 何を触るか
- 何を触らないか
- どこで止めるか
- 何を proof とみなすか

を固定する。

## Weakest Point

いま一番弱い点は、`thin-top branch` の最初の実装パスはもう完了しているのに、
**packet 上の終点が `Tier R` まで進んだことと、次の仕事が promotion gate 定義だという点が明示されていない**ことだ。

この状態を放置すると、次の 2 つが起きやすい。

- もう終わった WP1-WP4 を再度なぞってしまい、critical path がぶれる
- 本当の blocker である `changed_watch_field_count=0` の説明より先に、probe / runner 側 special-case が増える

## Current Truth

2026-04-04 実装後の truth はこれ。

- minimum goal は `tlul_socket_m1` で達成済み
- `tlul_request_loopback` は `phase_b_reference_design`
- `tlul_fifo_sync_cpu_replay_tb` は historical seed seam として残るが、本線ではない
- `tlul_fifo_sync_gpu_cov_tb` は shared core + timed wrapper に分離済み
- `tlul_fifo_sync_gpu_cov_host_tb` は build/probe まで通り、`host_clock_control=true`, `host_reset_control=true` を返す
- `output/validation/tlul_fifo_sync_stock_hybrid_validation.json` が
  `support_tier=thin_top_reference_design`, `acceptance_gate=thin_top_edge_parity_v1`
  を返す
- host-only `1,0` edge trace は design-visible delta を生む
- direct CPU `root___eval` と fake-`vlSymsp` CPU `root___eval` は、その same-edge behavior を design-visible に再現する
- raw-state-import CPU `root___eval` も、その same-edge behavior を design-visible に再現する
- GPU replay も checked-in `1,0` edge sequence では internal-only residual まで揃う
- current-model branch は `tlul_fifo_sync` / `tlul_socket_1n` / `tlul_err` / `tlul_sink` で no GPU-driven delta

根拠:

- [roadmap_tasks.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/roadmap_tasks.md)
- [rtlmeter_expansion_branch_audit.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/rtlmeter_expansion_branch_audit.json)
- [tlul_fifo_sync_thin_top_design.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/tlul_fifo_sync_thin_top_design.md)
- [tlul_fifo_sync_host_probe_report.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_probe_report.json)
- [tlul_fifo_sync_host_gpu_flow_watch_summary.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json)

## Sprint Goal

この execution packet の current sprint goal は historical に 1 つだけだった。

**`tlul_fifo_sync` thin-top branch の next blocker を、CPU parity / GPU parity の責任切り分けに固定する。**

すでに達成済みのもの:

- `tlul_fifo_sync` に対して、true host-owned `clk_i` / `rst_ni` を持つ thin-top proof surface を作る
- stock Verilator `--cc` で host wrapper を bootstrap/build/probe する

この sprint の外だったもの:

- second supported target への昇格
- `Tier R -> Tier S` の gate 定義

## Scope

### In scope

- shared core 抽出
- timed wrapper の温存
- host-driven wrapper の追加
- bootstrap path の追加
- host-driven probe の追加または generic probe の再利用
- first host baseline proof

### Out of scope

- `tlul_request_loopback`
- `tlul_socket_1n`
- `tlul_err` / `tlul_sink`
- `strict_final_state`
- general multi-design thin-top framework
- validation runner 昇格

## Write Set

CC が最初の実装パスで触ってよい write set は次。

### RTL / wrapper

- `third_party/rtlmeter/designs/OpenTitan/src/tlul_fifo_sync_gpu_cov_tb.sv`
- `third_party/rtlmeter/designs/OpenTitan/src/tlul_fifo_sync_gpu_cov_cpu_replay_tb.sv`
- `third_party/rtlmeter/designs/OpenTitan/src/tlul_fifo_sync_gpu_cov_host_tb.sv`
- 必要なら shared core 用の新 file 1 本

### Tooling

- `src/tools/bootstrap_hybrid_tlul_slice_cc.py`
- `src/tools/run_tlul_slice_host_probe.py`

### Probe

- `src/hybrid/tlul_slice_host_probe.cpp`
  で再利用できるならそれを優先
- 専用 probe が要る場合は
  `src/hybrid/tlul_fifo_sync_host_probe.cpp`
  または同等の 1 file に留める

### Tests

- `src/scripts/tests/test_bootstrap_hybrid_tlul_slice_cc.py`
- host probe / contract に対応する test 1 本以上

### Docs

- `docs/tlul_fifo_sync_thin_top_design.md`
- `docs/roadmap_tasks.md`
- 必要なら `docs/README.md`

## Do Not Touch

最初の実装パスでは次を触らない。

- `src/tools/run_vl_hybrid.py`
- `src/runners/run_socket_m1_stock_hybrid_validation.py`
- `src/runners/run_tlul_request_loopback_stock_hybrid_validation.py`
- `vlgpugen` / Phase B compare ロジック

理由:

- まず proof すべきは host-owned `clk/reset` surface であって、
  GPU runner や validation schema の再設計ではない

## Work Packages

### WP1: extract shared core

目的:

- timed wrapper と host-driven wrapper が同じ本体ロジックを共有する状態を作る

完了条件:

- `tlul_fifo_sync_gpu_cov_tb` は top 名を維持
- timed wrapper から clock coroutine と reset synthesis 以外の本体ロジックが大きく減る
- current timed wrapper を bootstrap した build が壊れない

Status:

- done

### WP2: add host-driven wrapper

目的:

- `tlul_fifo_sync_gpu_cov_host_tb` を追加し、top-level に `clk_i` / `rst_ni` を expose する

完了条件:

- raw root に `clk_i` / `rst_ni` が直接見える
- wrapper-local `always #5` が存在しない
- wrapper-local reset synthesis が存在しない

Status:

- done

### WP3: bootstrap host-driven top

目的:

- stock Verilator `--cc` で host-driven wrapper を `mdir` 化できるようにする

完了条件:

- `bootstrap_hybrid_tlul_slice_cc.py --tb-path ... --top-module tlul_fifo_sync_gpu_cov_host_tb`
  が通る
- `build_vl_gpu.py <new mdir>` も通る

Status:

- done

### WP4: prove host-owned control

目的:

- host probe で `clk_i` / `rst_ni` ownership を示す

最低完了条件:

- `host_clock_control=true`
- `host_reset_control=true`

望ましい追加証拠:

- host が clock edge を進めるたびに progress/watch field が変わる
- `events_pending_after_init=false`
  もしくは pending event が proof を邪魔しないと説明できる

Status:

- partially done
- required gate is done:
  - `host_clock_control=true`
  - `host_reset_control=true`
- extra behavior proof is still open:
  - current pilot has pending events drained during probe, but watched outputs still do not change under GPU replay

### WP5: first handoff pilot

目的:

- host baseline から GPU replay へ handoff したときに、timed-wrapper seed ではなく
  host-driven top 由来の state seam が動くことを示す

最低完了条件:

- baseline が未完了
- replay 後に watched field または generic outputs に delta が出る

Status:

- done for `Tier R`
- current result:
  - baseline is incomplete
  - host-only `1,0` edge replay produces design-visible delta
  - CPU parity and GPU parity now both reduce to internal-only residuals on that checked-in sequence
  - the result is promoted into `output/validation/tlul_fifo_sync_stock_hybrid_validation.json`
    as `support_tier=thin_top_reference_design`

Artifacts:

- [tlul_fifo_sync_host_probe_report.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_probe_report.json)
- [tlul_fifo_sync_host_gpu_flow_watch_summary.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json)
- [tlul_fifo_sync_handoff_parity_packet.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/tlul_fifo_sync_handoff_parity_packet.md)
- [tlul_fifo_sync_stock_hybrid_validation.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/tlul_fifo_sync_stock_hybrid_validation.json)

## Hard Abort Conditions

次のどれかが起きたら、その sprint では thin-top 実装を止めて review に戻す。

1. `tlul_fifo_sync_gpu_cov_tb` の timed-wrapper build が壊れる  
2. host-driven wrapper が結果的に large copy/fork になる  
3. proof のために probe / runner 側へ slice 固有の重い special-case が増え始める  
4. `clk_i` / `rst_ni` ownership を示せないまま handoff 実験に進もうとする  

## Proof Commands

最初の proof commands はこの順で十分。

1. timed wrapper が壊れていないこと

```bash
python3 src/tools/bootstrap_hybrid_tlul_slice_cc.py --slice-name tlul_fifo_sync --force
python3 src/tools/build_vl_gpu.py work/vl_ir_exp/tlul_fifo_sync_vl
```

2. host-driven wrapper bootstrap

```bash
python3 src/tools/bootstrap_hybrid_tlul_slice_cc.py \
  --slice-name tlul_fifo_sync \
  --out-dir work/vl_ir_exp/tlul_fifo_sync_host_vl \
  --tb-path third_party/rtlmeter/designs/OpenTitan/src/tlul_fifo_sync_gpu_cov_host_tb.sv \
  --top-module tlul_fifo_sync_gpu_cov_host_tb \
  --force
```

3. host-driven build

```bash
python3 src/tools/build_vl_gpu.py work/vl_ir_exp/tlul_fifo_sync_host_vl
```

4. host-driven probe

```bash
python3 src/tools/run_tlul_slice_host_probe.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl \
  --json-out work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_probe_report.json
```

5. first host-owned clock pilot

```bash
python3 src/tools/run_tlul_slice_host_gpu_flow.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl \
  --template config/slice_launch_templates/tlul_fifo_sync.json \
  --target tlul_fifo_sync \
  --support-tier thin_top_seed \
  --nstates 1 \
  --host-clock-sequence 1,0 \
  --host-clock-sequence-steps 1 \
  --json-out work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json
```

6. stable thin-top reference validation

```bash
python3 src/runners/run_tlul_fifo_sync_stock_hybrid_validation.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl
```

## Review Checklist For Codex

Codex が review で見るべき点は次。

- wrapper separation は実際に shared-core になっているか
- timed wrapper が accidental fork になっていないか
- host-driven wrapper に timed coroutine が残っていないか
- `host_clock_control` / `host_reset_control` は artifact で本当に立っているか
- proof のために tool 側 special-case が増えすぎていないか

## Success / Failure Interpretation

### Success

- host-driven wrapper が build/probe まで通る
- host-owned `clk/reset` が artifact で証明される

この条件は **すでに満たしている**。現時点の branch は `Tier R` とみなせる。

### Failure

- current wrapper 構造では shared-core 化が無理
- host-owned `clk/reset` を持たせると semantic drift が大きすぎる

この場合は、

- `tlul_fifo_sync` thin-top branch は高コスト
- current milestone では `socket_m1` 単独 supported を維持

という判断に戻る。

## Current Open Question

- thin-top parity packet の結果、open question は 1 つに絞れた:
  `thin_top_edge_parity_v1` の先に、何を `Tier S` 昇格 gate として要求するのか
- したがって、次の実装は runner 修正ではなく、promotion policy の定義である
- 結果の根拠:
  [tlul_fifo_sync_handoff_parity_packet.md](/home/takatodo/gpu-toggle-coverage-campaigns/docs/tlul_fifo_sync_handoff_parity_packet.md)
  と
  [tlul_fifo_sync_stock_hybrid_validation.json](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/tlul_fifo_sync_stock_hybrid_validation.json)
