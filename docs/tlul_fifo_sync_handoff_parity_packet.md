# `tlul_fifo_sync` Handoff Parity Packet

## Purpose

この文書は、`tlul_fifo_sync` thin-top branch の open blocker を
**次の 1 スプリントで実装すべき診断パス** に固定するための packet である。
2026-04-04 時点では、この packet は completed proof packet として読む。

対象は `docs/tlul_fifo_sync_thin_top_execution_packet.md` の WP5 を、
「CPU 側でも same-edge parity が崩れるのか」「崩れないなら GPU 側だけが悪いのか」に分解すること。

## Weakest Point

この packet が解くべき weakest point は、`tlul_fifo_sync_gpu_cov_host_tb` の first pilot で見えた
**design-visible mismatch の責任を、host baseline / CPU `root___eval` / GPU replay のどこへ帰属させるべきか未確定**
だったことだ。

現状わかっているのは次だけである。

- host-owned `clk_i` / `rst_ni` は証明済み
- checked-in handoff pilot は `changed_watch_field_count=0`
- raw state delta は `8` byte ある
- その `8` byte は `__VicoPhaseResult`, `__VicoTriggered`, `vlSymsp`
  に解決し、all-internal only

この前段では、

- `run_vl_hybrid.py` の patch-per-run semantics が足りないのか
- direct CPU `root___eval` でも host edge trace からずれるのか
- `vlSymsp` rebinding 自体が壊しているのか

がまだ分からなかった。

## Current Truth

2026-04-04 時点の checked-in truth:

- [tlul_fifo_sync_host_probe_report.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_probe_report.json)
  は `clock_ownership=host_direct_ports`, `host_clock_control=true`,
  `host_reset_control=true`
- [tlul_fifo_sync_host_gpu_flow_watch_summary.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json)
  は `host_clock_sequence=1,0`, `host_clock_sequence_steps=1` で
  `changed_watch_field_count=0`
- [tlul_fifo_sync_host_state_delta_annotations.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_state_delta_annotations.json)
  は final delta が all-internal only だと示している
- [tlul_fifo_sync_host_run1_delta_annotations.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_run1_delta_annotations.json)
  は first rising edge 相当の run でも `clk_i` 以外は internal field しか変わっていないことを示している
- その後の host-only edge trace 実装で、
  [tlul_fifo_sync_host_edge_trace.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_edge_trace.json)
  は CPU 側の `1,0` sequence が design-visible delta を生むことを示した:
  `progress_cycle_count_o: 6 -> 7`, `progress_signature_o: 0 -> 2654435858`,
  `toggle_bitmap_word{0,1,2}_o: 0 -> nonzero`
- 同じ summary
  [tlul_fifo_sync_host_gpu_flow_watch_summary.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json)
  の `edge_parity` は、same `1,0` sequence の host-only vs GPU replay が
  edge あたり internal-only residual に収まることを示している
- 新しい CPU parity probe
  [tlul_fifo_sync_handoff_parity_summary.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_handoff_parity_summary.json)
  は、host `eval_step` と direct CPU `root___eval` が same-edge design-visible behavior で一致し、
  diff は `vlSymsp` / `vlNamep` の internal-only 5 bytes per edge だけだと示している
- 同じ artifact は fake `vlSymsp` buffer を rebinding した CPU `root___eval` でも
  design-visible parity が崩れず、diff は internal-only 9 bytes per edge だけだと示している
- 同じ artifact は raw dumped state を別 model に import してから `root___eval` しても
  design-visible parity が崩れず、diff は internal-only 6 bytes per edge だけだと示している

## Sprint Goal

この packet の sprint goal は 1 つだけ。

**`tlul_fifo_sync` host-driven top で、single-edge parity を host-only / CPU `root___eval` /
raw-state-import CPU `root___eval` / GPU replay の 4 者で取り、design-visible mismatch の責任箇所を切る。**

Status (2026-04-04):

- done
- conclusion:
  - host-only edge trace already produces design-visible delta
  - direct CPU `root___eval` preserves that same-edge behavior
  - fake-`vlSymsp` CPU `root___eval` also preserves that same-edge behavior
  - raw-state-import CPU `root___eval` also preserves that same-edge behavior
  - checked-in parity packet の目的は達成済みで、next blocker は promotion policy である

## Questions To Answer

順番に答えるべき問いは次の 3 つ。

1. host-only の `1,0` edge sequence で design-visible delta は出るのか
2. direct CPU `root___eval` はその same-edge semantics を保てるのか
3. raw dumped state を経由しても CPU 側は保てるのか
4. もし CPU 側は保てるなら、GPU replay も internal-only residual に収まるのか

## Decision Table

### Case A

- host-only edge trace: design-visible delta > 0
- CPU `root___eval`: design-visible parity pass
- raw-state-import CPU `root___eval`: design-visible parity pass
- GPU replay: design-visible parity fail

結論:

- checked-in `thin_top_edge_parity_v1` gate は成立
- 次の実装タスクは promotion gate 定義である

### Case B

- host-only edge trace: design-visible delta > 0
- CPU `root___eval`: design-visible parity fail

結論:

- blocker は GPU 固有ではない
- next task is host baseline / seam construction or CPU root-eval invocation semantics

### Case C

- host-only edge trace: design-visible delta = 0

結論:

- current baseline is unsuitable
- next task is shallower handoff point construction, not GPU parity debugging

## In Scope

- `tlul_fifo_sync_gpu_cov_host_tb` だけを見る
- host-only per-edge trace を追加する
- GPU per-edge trace と host-only trace を同じ sequence で比較する
- internal-only delta を parity 判定から分離する

## Out Of Scope

- `tlul_request_loopback`
- `tlul_socket_1n`
- `tlul_err` / `tlul_sink`
- 2 本目 target の promotion decision
- `strict_final_state`
- multi-design parity framework

## Normalization Rules

host-vs-GPU parity で最初から `design-visible delta` ではないものとして扱う候補は次。

- `vlSymsp`
- `__VicoPhaseResult`
- `__VicoTriggered`
- `__Vtrigprevexpr___TOP__clk_i__0`

注意:

- この packet では「無視してよい」と断定しない
- まずは `verilator_internal` として role 分離し、parity report 上で
  `internal_only_delta` として別集計する

## Write Set

CC がこの packet で触ってよい write set は次。

- `src/tools/run_tlul_slice_host_probe.py`
- `src/hybrid/tlul_slice_host_probe.cpp`
- `src/tools/run_tlul_slice_handoff_parity_probe.py`
- `src/hybrid/tlul_slice_handoff_parity_probe.cpp`
- それに対応する test 1 本以上
- `docs/tlul_fifo_sync_thin_top_execution_packet.md`
- `docs/tlul_fifo_sync_thin_top_design.md`
- `docs/roadmap_tasks.md`

## Work Packages

### WP6: add host-only edge trace

目的:

- host-owned `clk_i` を CPU 側で実際に動かしたときの per-edge state / watch / output delta を取る

最低完了条件:

- `run_tlul_slice_host_probe.py` か同等 tool が
  `clock_sequence=1,0` を host-only で回せる
- edge ごとに raw state dump と summary JSON を残せる
- final だけでなく `edge_1`, `edge_2` 単位で known-field / raw-byte delta が読める

推奨 artifact:

- `work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_edge_trace.json`
- `work/vl_ir_exp/tlul_fifo_sync_host_vl/host_edge_trace/edge_1.bin`
- `work/vl_ir_exp/tlul_fifo_sync_host_vl/host_edge_trace/edge_2.bin`

Status:

- done

### WP7: compare host-only vs GPU edge parity

目的:

- 同じ `1,0` sequence で host-only と GPU replay の差を切る

最低完了条件:

- host edge `1` と GPU run `1` を比較した JSON がある
- host edge `2` と GPU run `2` を比較した JSON がある
- comparison は
  - raw delta
  - known-field delta
  - `verilator_internal` / `design_state` / `top_level_io`
    の role 別 summary
  を持つ

推奨 artifact:

- `work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_edge_parity.json`

Status:

- done in-place via
  [tlul_fifo_sync_host_gpu_flow_watch_summary.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json)
  `edge_parity`

### WP8: make the branch decision

目的:

- `GPU kernel/device path` と `baseline/seam depth` のどちらが blocker かを固定する

最低完了条件:

- 上の Decision Table のどれに当たるかが docs に記録される

Status:

- done
- observed case:
  - Case A
  - checked-in parity gate is satisfied

## Hard Abort Conditions

次のどれかが起きたら、この sprint はそこで止めて review に戻す。

1. host-only edge trace を取るために `tlul_fifo_sync` 専用 special-case が probe に大量流入する
2. parity tool が raw offset の羅列だけで、role や field 名へ戻せない
3. `run_vl_hybrid.py` を直す前に「GPU semantics が悪い」と決め打ちしそうになる

## Proof Commands

host-driven top が既に build 済みである前提で、proof commands はこの順でよい。

1. host-only edge trace

```bash
python3 src/tools/run_tlul_slice_host_probe.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl \
  --template config/slice_launch_templates/tlul_fifo_sync.json \
  --clock-sequence 1,0 \
  --edge-state-dir work/vl_ir_exp/tlul_fifo_sync_host_vl/host_edge_trace \
  --json-out work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_edge_trace.json
```

2. GPU edge trace

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

3. final-state offset annotation

```bash
python3 src/tools/annotate_vl_state_offsets.py \
  work/vl_ir_exp/tlul_fifo_sync_host_vl \
  --summary work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json \
  --json-out work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_state_delta_annotations.json
```

## Review Checklist For Codex

- host-only edge trace は really host-only か
- same sequence / same baseline を host-only と GPU replay で比較しているか
- `verilator_internal` と `design-visible` が明示的に分かれているか
- 結論が Decision Table のどれかに落ちているか

## Current Decision

- `tlul_fifo_sync` thin-top branch の parity blocker は閉じた
- next implementation task は `thin_top_edge_parity_v1` の先に何を supported gate として要求するかを決めることである
- `host-owned clk/reset` の再証明や shallow/deep baseline search は current critical path ではない
