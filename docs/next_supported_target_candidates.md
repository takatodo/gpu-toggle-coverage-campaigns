# Next Supported Target Candidates

## Purpose

`tlul_socket_m1` の次に、どの design を 2 本目の supported stock-hybrid target 候補として扱うかを整理する。
ただし 2026-04-04 時点では、`tlul_fifo_sync` はもう純粋な候補ではなく、
checked-in `thin_top_reference_design` surface である。

## Fixed Context

- 現在の first supported target は `tlul_socket_m1`
- `tlul_request_loopback` は current milestone では `phase_b_reference_design` に凍結する
- `tlul_fifo_sync` は current milestone では `thin_top_reference_design` に固定する
- 候補母集団は `config/slice_launch_templates/index.json` の `status == ready_for_campaign` から取る

## Immediate Candidate Pool

`ready_for_campaign` かつ、すでに役割が固定されている 3 design を除いた候補は次の 6 本。

- `tlul_socket_1n`
- `xbar_main`
- `xbar_peri`
- `tlul_fifo_async`
- `tlul_err`
- `tlul_sink`

除外理由:

- `tlul_socket_m1`: すでに first supported target
- `tlul_request_loopback`: current milestone では reference-design に凍結
- `tlul_fifo_sync`: current milestone では `thin_top_reference_design` に固定
- `onboarding_in_progress` 群: immediate candidate pool にはまだ入れない

## Triage Buckets

### Tier 0: fixed second reference surface

- `tlul_fifo_sync`
  - `support_tier=thin_top_reference_design`
  - checked-in `thin_top_edge_parity_v1` gate を持つ
  - 現在の論点は候補選定ではなく、`Tier R` のまま維持するか `Tier S` を目指すか

### Tier 1: first-pass candidates

新しい design を掘るなら、まず見るべき候補はこの 1 本。

- `tlul_socket_1n`
  - `priority=2`
  - single-clock / single-reset
  - `runner_generalization_required=false`
  - `driver_defaults` は増えるが、`socket_m1` と同じ TL-UL fabric 系で比較しやすい

### Tier 2: fallback single-clock candidates

Tier 1 が両方とも不適なら次に見る候補。

- `tlul_err`
  - single-clock で、checked-in `tlul_err_gpu_cov_tb.sv` / coverage manifest から stock build と host probe は通る
  - ただし current `tb_timed_coroutine` model の最初の host->GPU pilot では output delta が出ていない
- `tlul_sink`
  - single-clock で、checked-in `tlul_sink_gpu_cov_tb.sv` / coverage manifest から stock build と host probe は通る
  - ただし current `tb_timed_coroutine` model の最初の host->GPU pilot では output delta が出ていない

### Tier 3: defer unless ownership model changes

current milestone では優先しない候補。

- `tlul_fifo_async`
  - `multi_clock=true`
  - host/top ownership 問題を先に再燃させやすい
- `xbar_main`
  - `multi_clock=true`
  - clock/reset port 数が多く、2 本目の target としては ownership cost が高い
- `xbar_peri`
  - `multi_clock=true`
  - `xbar_main` より小さいが、それでも multi-clock で current supported model から遠い

## Selection Criteria

次の supported target を選ぶときは、少なくともこの 4 条件で見る。

1. 既存の generic TL-UL slice host probe を大きく崩さずに初期化できるか
2. stable validation JSON に載せやすい completion / progress / safety signal を持つか
3. host probe の時点では未完了で、GPU replay 側に前進余地を残しやすいか
4. `socket_m1` 専用 ABI や `loopback` 専用 tuning のような設計固有 work を最小にできるか

## Concrete Evaluation Tasks

1. `tlul_fifo_sync` と `tlul_socket_1n` の 2 本だけを対象に、generic host probe compile/run の viability を確認する
2. その 2 本で stable validation JSON に載せる completion / progress / safety signal の候補を洗い出す
3. host probe baseline が「未完了だが前進余地あり」になる方を 2 本目の supported target に選ぶ
4. もし 2 本とも current TB-owned clock model に素直に乗らないなら、その時点で初めて thinner host-driven top を blocker に昇格させる
5. Tier 1 が両方とも落ちた場合にだけ、`tlul_err` / `tlul_sink` を current-model fallback 候補として再評価する
6. `multi_clock=true` の 3 design は、ownership model を拡張する判断が下るまで selection の対象外にする

## `tlul_fifo_sync` Viability Pass

### Task 1: stock build viability

- stock Verilator `--cc` 出力から `tlul_fifo_sync` の `mdir` を起こす
- `build_vl_gpu.py` で cubin / meta / classifier report まで到達する
- ここで落ちるなら、2 本目候補としての優先度を一段下げる

### Task 2: generic host-probe viability

- generic TL-UL slice host probe が compile できる
- constructor / raw root image dump / field offset 読み出しが通る
- この時点で special-case ABI を追加しない

### Task 3: validation-surface viability

- stable validation JSON に載せる completion / progress / safety signal を 1 組選べる
- host probe baseline が「すでに完了」ではなく、GPU replay に前進余地を残すことを確認する
- current TB-owned clock model のままで 1 回は host->GPU handoff を試せる

### Done Criteria

`tlul_fifo_sync` を 2 本目の supported target 候補として維持してよい条件は次の 3 つ。

1. stock build が通る
2. generic host probe が special-case ABI なしで通る
3. validation surface 用の signal 候補が取れ、host baseline が未完了 state を残せる

この 3 つのうち 1 つでも落ちたら、即 `tlul_socket_1n` に切り替える。

## Historical Tier-1 Pivot

Tier 1 を最初に棚卸しした時点では、`tlul_fifo_sync` と `tlul_socket_1n` のどちらかを
2 本目の supported target に絞る方針だった。

その historical pivot は次の順で実施済み。

1. `tlul_fifo_sync` を first-pass 候補として評価
2. Task 3 で止まったので `tlul_socket_1n` に切り替え
3. `tlul_socket_1n` も Task 3 で止まったため、現在は candidate selection ではなく mechanism decision に移行

## First-Pass Result

`tlul_fifo_sync` を最初に評価した結果は次のとおり。

- Task 1: pass
  - stock `--cc` 出力と `build_vl_gpu.py` は完走
  - `storage_size=6080`
  - classifier は `reachable=16`, `gpu=9`, `runtime=7`
- Task 2: pass
  - generic host probe は compile/run できた
  - ただし reset control field は `rst_ni` ではなく `reset_like_w` だった
  - host probe baseline は `done_o=0`, `progress_cycle_count_o=6`, `rsp_queue_overflow_o=0`
- Task 3: fail
  - host-generated init-state から GPU replay を `steps=1` と `steps=56` で試しても
    `done_o`, `progress_cycle_count_o`, `progress_signature_o`, `rsp_queue_overflow_o`,
    `toggle_bitmap_word*` は全部不変
  - current generic signal set では stable validation surface の progress proof が作れない

根拠 artifact:

- `work/vl_ir_exp/tlul_fifo_sync_vl/tlul_fifo_sync_host_probe_report.json`
- `work/vl_ir_exp/tlul_fifo_sync_vl/tlul_fifo_sync_gpu_final_state.bin`
- `work/vl_ir_exp/tlul_fifo_sync_vl/tlul_fifo_sync_gpu_final_state_steps56.bin`

## Historical Recommendation After `tlul_fifo_sync`

`tlul_fifo_sync` の first-pass viability が Task 3 で止まった時点では、次の評価先を
`tlul_socket_1n` に切り替えた。

その時点の理由:

- single-clock / single-reset を維持できる
- Tier 1 の残り 1 本で、fallback 先として最も自然
- `socket_m1` と同じ TL-UL fabric 系で、progress / response 信号の見立てを流用しやすい

この判断自体は historical record として残すが、現在の active recommendation は後段の
`Updated Recommendation` を正とする。

## `tlul_socket_1n` First-Pass Result

`tlul_socket_1n` を次に評価した結果は次のとおり。

- Task 1: pass
  - stock `--cc` 出力と `build_vl_gpu.py` は完走
  - `storage_size=2240`
  - classifier は `reachable=12`, `gpu=11`, `runtime=1`
- Task 2: pass
  - generic host probe は compile/run できた
  - host probe baseline は `done_o=0`, `progress_cycle_count_o=2`, `progress_signature_o=3`, `rsp_queue_overflow_o=0`
  - toggle bitmap は baseline で非ゼロ
- Task 3: fail
  - host-generated init-state から GPU replay を `steps=1` と `steps=56` で試しても
    `done_o`, `progress_cycle_count_o`, `progress_signature_o`, `rsp_queue_overflow_o`,
    `toggle_bitmap_word*` は全部不変
  - current generic signal set では stable validation surface の GPU-driven progress proof が作れない

根拠 artifact:

- `work/vl_ir_exp/tlul_socket_1n_vl/tlul_socket_1n_host_probe_report.json`
- `work/vl_ir_exp/tlul_socket_1n_vl/tlul_socket_1n_gpu_final_state.bin`
- `work/vl_ir_exp/tlul_socket_1n_vl/tlul_socket_1n_gpu_final_state_steps56.bin`

## Tier 2 Availability Check

Tier 1 が両方とも Task 3 で止まったので、Tier 2 fallback の bootstrap 可否も確認した。

- `tlul_err`: Task 1/2 pass, first pilot fail
  - `bootstrap_hybrid_tlul_slice_cc.py --slice-name tlul_err` と `build_vl_gpu.py work/vl_ir_exp/tlul_err_vl` は通る
  - `run_tlul_slice_host_probe.py --mdir work/vl_ir_exp/tlul_err_vl` も通る
  - ただし `run_tlul_slice_host_gpu_flow.py` の最初の pilot は `changed_watch_field_count=0` で、generic outputs も host baseline と不変
- `tlul_sink`: Task 1/2 pass, first pilot fail
  - `bootstrap_hybrid_tlul_slice_cc.py --slice-name tlul_sink` と `build_vl_gpu.py work/vl_ir_exp/tlul_sink_vl` は通る
  - `run_tlul_slice_host_probe.py --mdir work/vl_ir_exp/tlul_sink_vl` も通る
  - ただし `run_tlul_slice_host_gpu_flow.py` の最初の pilot は `changed_watch_field_count=0` で、generic outputs も host baseline と不変

つまり current workspace では、`tlul_err` / `tlul_sink` は「未評価不能」ではなく、
「`Tier B` までは上がったが、current model branch の quick win にはならなかった候補」である。

## Broader Observability Result

`tlul_socket_1n` と `tlul_fifo_sync` の両方で、current generic signal set を超える watch fields を
host probe / GPU replay summary に入れて再評価した。

- `tlul_socket_1n`: still fail
  - watch fields:
    - host FIFO `reqfifo.rvalid_o` / `rspfifo.rvalid_o`
    - device FIFO `reqfifo.rvalid_o` / `rspfifo.rvalid_o` for all 4 ports
    - `tl_h_o`
    - `tl_d_o`
  - result:
    - `changed_watch_field_count=0`
    - host probe baseline と GPU replay 後の値が全部一致
  - artifact:
    - `work/vl_ir_exp/tlul_socket_1n_vl/tlul_socket_1n_host_gpu_flow_watch_summary.json`

- `tlul_fifo_sync`: still fail
  - watch fields:
    - `reqfifo.full_o` / `depth_o`
    - `rspfifo.full_o` / `depth_o`
    - `reqfifo.rvalid_o` / `wready_o`
    - `rspfifo.rvalid_o` / `wready_o`
  - result:
    - `changed_watch_field_count=0`
    - host probe baseline と GPU replay 後の値が全部一致
  - artifact:
    - `work/vl_ir_exp/tlul_fifo_sync_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json`

この時点で分かったことは、Tier 1 の弱点が「generic signal set が粗すぎた」だけではない、ということ。
少なくとも current `tb_timed_coroutine` handoff model では、2 design とも broader observability でも
GPU-driven change を観測できていない。

## Updated Recommendation

current milestone では、2 本目 target を無理に抱え込まず、`socket_m1` 単独 supported のまま閉じる。
この文書は current milestone の active TODO ではなく、**次 milestone の分岐メモ** として読む。
ただし `tlul_fifo_sync` はもう branch seed だけではなく、checked-in `Tier R` surface まで上がっている。

理由:

- `tlul_fifo_sync` は `output/validation/tlul_fifo_sync_stock_hybrid_validation.json` により
  `thin_top_reference_design` として固定済み
- Tier 1 の新規候補である `tlul_socket_1n` は build/probe は通るが、broader observability でも不変
- Tier 2 の `tlul_err` / `tlul_sink` も build/probe/pilot までは通るが、current model pilot では不変
- したがって次の uncertainty は signal choice や source availability ではなく、
  `tlul_fifo_sync` を `Tier R` に留めるかどうかという promotion policy に移っている

次 milestone で 2 本目 target を再開するなら、次の順で進める。

1. `tlul_fifo_sync` を `Tier R` のまま維持するか、`Tier S` を目指すか決める
2. 新規 design を掘るなら、その後で `tlul_socket_1n` を起点に branch を決める
3. どちらもやらないなら、2 本目 target は引き続き scope 外として `socket_m1` 中心の supported surface を維持する

短く言うと、次 milestone の first action は design selection ではなく branch selection である。

## Repeatable Feasibility Audit

mechanism 判断を ad-hoc な議論に戻さないため、2026-04-04 時点の候補状態は
`python3 src/tools/audit_second_target_feasibility.py --json-out work/second_target_feasibility_audit.json`
で再生成できるようにした。

- artifact:
  - `work/second_target_feasibility_audit.json`
- covered candidates:
  - `tlul_fifo_sync`
  - `tlul_socket_1n`
  - `tlul_err`
  - `tlul_sink`
- tracked facts:
  - template / RTL / coverage TB source の存在
  - build artifact / host probe / watched-field summary の有無
  - shallow handoff search summary の有無
  - `*_gpu_cov_cpu_replay_tb.sv` wrapper の有無

2026-04-04 実測 recommendation は次の 3 本。

1. `thinner host-driven top` をやるなら seed は `tlul_fifo_sync`
   - 理由:
     - `tlul_fifo_sync` だけが thin-top branch の実装済み seed になっている
     - `tlul_socket_1n` には同等の host-driven wrapper も replay wrapper もない
     - 2026-04-04 時点で、`tlul_fifo_sync_gpu_cov_host_tb.sv` は
       `work/vl_ir_exp/tlul_fifo_sync_host_vl` に stock Verilator `--cc` bootstrap でき、
       `run_tlul_slice_host_probe.py` で `host_clock_control=true` /
       `host_reset_control=true` / `clock_ownership=host_direct_ports` まで確認済み
2. current `tb_timed_coroutine` model を維持する branch は、いまは quick win を持たない
   - 理由:
     - Tier 1 は `tlul_fifo_sync` / `tlul_socket_1n` ともに `no_gpu_driven_deltas_under_current_model`
     - Tier 2 の `tlul_err` / `tlul_sink` も source 復旧後の first pilot で `no_gpu_driven_deltas_under_current_model`
     - 2026-04-04 時点の branch audit は、`maximize_ready_tier_count_quickly` に対しても `defer_second_target` を返す
3. どちらもやらないなら、2 本目 target は current milestone では明示的に defer
   - なお `maximize_second_r_or_s_candidate` という objective 自体は、
     `tlul_fifo_sync` が `Tier R` に上がった時点で already met である

つまり、2 本目 target を再開する場合の first fork はこう整理される。

- thin-top branch:
  - seed は `socket_1n` ではなく `tlul_fifo_sync`
- thin-top branch の current fact:
  - `tlul_fifo_sync_gpu_cov_host_tb.sv` は **真の host-owned top** として build / probe まで通っている
  - `work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_probe_report.json`
    は `host_clock_control=true`, `host_reset_control=true`, `clock_ownership=host_direct_ports` を返す
  - `work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json`
    は final compare で `changed_watch_field_count=0` だが、checked-in `1,0` edge sequence の `edge_parity`
    は internal-only residual まで揃っている
  - さらに `work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_handoff_parity_summary.json`
    は host `eval_step`、CPU `root___eval`、fake-`vlSymsp` CPU `root___eval`、
    raw-state-import CPU `root___eval` parity が internal-only residual に揃うことを示している
  - したがって次 milestone でやるべきことは「seed の有無確認」でも
    「raw handoff setup の再確認」でもなく、`thin_top_edge_parity_v1` の先に何を supported gate として要求するかの判断
- current-model branch:
  - Tier 1 と Tier 2 の shallow/current-model pilots は打ち止め
  - 次にやるなら source 復旧ではなく、目的と mechanism を先に定義し直す
- defer branch:
  - current milestone は `socket_m1` 単独 supported のまま閉じる

## `tlul_socket_1n` TB-Timed Handoff Search

`tlul_socket_1n` については、「host probe が fixed point に行きすぎているだけか」を切るため、
`host_post_reset_cycles in {0,1,2,4,8}` と `steps in {1,56}` を振って再確認した。

- result:
  - `10/10` cases completed
  - `changed_watch_field_count=0` in every case
  - `done_o` は全 case で `0`
  - `rsp_queue_overflow_o` も全 case で `0`
  - `progress_cycle_count_o` / `progress_signature_o` は host baseline に応じて増えるが、
    GPU replay 後に baseline を超える変化は出ない
- artifact:
  - `work/vl_ir_exp/tlul_socket_1n_vl/watch_handoff_search/summary.json`

この結果で言えるのは、current `tb_timed_coroutine` model では
「post-reset を浅くすれば GPU-driven handoff proof が出る」という期待も弱い、ということ。
`socket_1n` を続けるなら、次は shallow tuning ではなく mechanism 側を変えるべき段階に入っている。

### `tlul_socket_1n` Instrumentation Candidates

`tlul_socket_1n` の root layout では、current generic signal set の外に次の候補が見えている。

- host-side FIFO visibility
  - `dut.fifo_h.reqfifo.rvalid_o`
  - `dut.fifo_h.rspfifo.rvalid_o`
  - `tl_h_o`
- device-side FIFO visibility
  - `dut.gen_dfifo[i].fifo_d.reqfifo.rvalid_o`
  - `dut.gen_dfifo[i].fifo_d.rspfifo.rvalid_o`
  - `tl_d_o`

2026-04-04 実測では、これらを watch fields に加えても `changed_watch_field_count=0` だった。

### `tlul_fifo_sync` Instrumentation Backup

`tlul_socket_1n` の broader instrumentation と並行して、`tlul_fifo_sync` では次の信号群を watch した。

- `dut.reqfifo.full_o`
- `dut.reqfifo.depth_o`
- `dut.rspfifo.full_o`
- `dut.rspfifo.depth_o`
- `dut.reqfifo.rvalid_o` / `wready_o`
- `dut.rspfifo.rvalid_o` / `wready_o`

2026-04-04 実測では、これらも `changed_watch_field_count=0` だった。

## `tlul_fifo_sync` Thin-Top Follow-Up

current-model branch が打ち止めになったあと、`tlul_fifo_sync` では thinner host-driven top 側も実装した。

- `tlul_fifo_sync_gpu_cov_tb.sv` は shared core + timed wrapper に分離済み
- `tlul_fifo_sync_gpu_cov_host_tb.sv` は top-level に `clk_i` / `rst_ni` を expose する
- `work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_probe_report.json` は
  `host_clock_control=true`, `host_reset_control=true`, `clock_ownership=host_direct_ports` を返す
- ただし first pilot
  `work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json`
  では `host_clock_sequence=1,0` でも `changed_watch_field_count=0`
- 同じ artifact の `state_delta` は host baseline に対して `8` byte の raw 差分を返す
- その 8 byte は
  [tlul_fifo_sync_host_state_delta_annotations.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_state_delta_annotations.json)
  で `__VicoPhaseResult`, `__VicoTriggered`, `vlSymsp` に解決していて、
  all-internal only である

したがって、`tlul_fifo_sync` の現状は「thin-top が未実装」ではなく、
「host-owned control は取れ、CPU/GPU parity も checked-in edge sequence では internal-only residual まで揃い、
  `thin_top_reference_design` surface は成立したが、そこから先の promotion policy が未決」である。
