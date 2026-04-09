# RTLMeter Coverage Expansion Plan

## Purpose

minimum goal は `tlul_socket_m1` で達成済みだが、`third_party/rtlmeter` 全体に対する coverage はまだ薄い。
この文書は、`socket_m1` 単独 supported 状態から、repo 全体で「どこまで実際に踏めたか」を
段階的に広げるための実行計画を定義する。

ただし real campaign goal は、design 数を増やすこと自体ではない。
**複数 design で、通常 sim より短い時間で coverage target に到達できること**が本来の目的である。
そのため、tier expansion は baseline-vs-hybrid の speed evidence と結び付けて読む必要がある。

## Why The Current Backlog Is Weak

既存 backlog の弱点は 2 つある。

- `2 本目 target をどうするか` までは整理されているが、`third_party/rtlmeter` 全体をどう広げるかの順序がない
- `supported / reference / buildable / template-only / missing-source` が同じ候補一覧に混ざり、coverage の伸びが測れない

この計画では、まず coverage を tier で測り、その上で branch を選ぶ。

## Coverage Tiers

repo-wide coverage は、各 design を次の tier のどこまで上げられたかで測る。

- `Tier S: supported`
  - stable validation JSON があり、supported source of truth として読める
- `Tier R: reference`
  - stable schema はあるが supported ではない
- `Tier B: build+probe`
  - stock build と host probe までは通るが、stable validation には上がっていない
- `Tier T: template-ready`
  - template はあるが、まだ build/probe artifact がない
- `Tier M: missing-source`
  - template はあるが coverage TB source など bootstrap 前提が欠けている
- `Tier U: untracked`
  - まだ slice index / campaign inventory の管理対象に入っていない

## Baseline (2026-04-04)

- `third_party/rtlmeter/designs` には 15 family がある
- checked-in `*_gpu_cov_tb.sv` は 19 本ある
- OpenTitan slice template index は 18 本で、`ready_for_campaign=9`, `onboarding_in_progress=9`
- checked-in scoreboard artifact は `work/rtlmeter_ready_scoreboard.json`
- checked-in branch audit artifact は `work/rtlmeter_expansion_branch_audit.json`

現時点の主な配置:

- `Tier S`
  - `tlul_socket_m1`
- `Tier R`
  - `tlul_request_loopback`
  - `tlul_fifo_sync`
  - `tlul_err`
  - `tlul_sink`
  - `tlul_socket_1n`
  - `tlul_fifo_async`
  - `xbar_main`
  - `xbar_peri`

scoreboard count:

- `Tier S=1`
- `Tier R=8`
- `Tier B=0`
- `Tier T=0`
- `Tier M=0`

補足:

- `tlul_fifo_sync` の thin-top branch は seed seam を越えて、true host-driven `clk/reset` top と host probe までは実装済み
- さらに CPU `root___eval` parity probe、fake-`vlSymsp` parity、raw-state-import parity、GPU replay parity が checked-in `1,0` edge sequence で internal-only residual まで揃っており、`output/validation/tlul_fifo_sync_stock_hybrid_validation.json` が `thin_top_reference_design` surface を固定している
- `onboarding_in_progress` の 9 design は current expansion line にはまだ入れない
- non-OpenTitan family は `Tier U` とみなし、current OpenTitan expansion の後段で扱う

## Expansion Goal

repo-wide coverage expansion の最小達成ラインは、次の 3 点を満たすこととする。

1. OpenTitan `ready_for_campaign` 9 本について、全 design を `Tier S/R/B/T/M` のいずれかで明示的に棚卸しする
2. `tlul_socket_m1` 以外に、少なくとも 1 本を `Tier S` か `Tier R` まで上げる
3. OpenTitan 以外から 1 family を選び、`Tier U` から `Tier B` 以上へ初回昇格させる

2026-04-04 時点では 2 が already met で、checked-in surface は `tlul_request_loopback` と `tlul_fifo_sync` の 2 本ある。

## Campaign Success Metric

coverage expansion を campaign goal に結び付けるには、次の 3 つが必要である。

1. 各 design に対して machine-readable な coverage-satisfaction threshold がある
2. 同じ threshold で normal sim と stock-hybrid を比較できる
3. 比較結果が "time-to-threshold" として記録される

ここは前進済みで、current repo は `socket_m1`, `tlul_fifo_sync`, `tlul_request_loopback`,
`tlul_err`, `tlul_sink`, `tlul_socket_1n`, `tlul_fifo_async`, `xbar_main`, `xbar_peri`
について normal sim baseline と threshold-to-time comparison artifact を持つ。
いま弱いのは「comparison loop があるか」ではなく、「この cross-family full-ready-pool line を checkpoint と見なすか、その先の breadth をどう増やすか」である。
current checked-in active recommendation は `work/campaign_next_kpi_active.json` に固定されていて、
design-specific v2 line の下で `broader_design_count` を返す。
`toggle_bits_hit >= 5` の candidate trial も追加済みだが、
`work/campaign_next_kpi_audit_threshold5.json` でも recommendation は変わらず `stronger_thresholds` のままだった。
さらに `work/campaign_threshold_headroom_experiments.json` により、
raw `bits_hit` cutoff の単純引き上げだけでは weakest surface (`tlul_fifo_sync`) の evidence が十分強くならないことも確認済みである。
加えて `work/tlul_fifo_sync_threshold_semantics_audit.json` により、
`tlul_fifo_sync` では `1` が strongest positive case で、
checked-in `1,0` replay depth から `1,0,1` に伸ばすだけで
winner が baseline に反転することも fixed された。
つまり policy decision はすでに終わっていて、current line は minimal-progress sequence を含む design-specific semantics である。
この policy の候補比較は `work/campaign_threshold_policy_options.json` を使い、
current checked-in active line は `work/campaign_threshold_policy_gate.json` と `work/campaign_speed_scoreboard_active.json` で読み、
matrix 差分は `work/campaign_threshold_policy_preview.json` で読む。

## Workstream Order

### Wave 1: Make Coverage Measurable

目的:

- coverage を候補一覧ではなく scoreboard として読む

タスク:

1. `ready_for_campaign` 9 本を tier 付きで一覧化する source of truth を作る
2. 各 design について、`coverage_tb_exists`, `build_artifacts`, `host_probe_exists`, `watch_summary_exists`, `stable_validation_exists` を同じ schema で記録する
3. `Tier T` と `Tier M` の境界を source presence ベースで固定する

done 条件:

- `ready_for_campaign` 9 本が全て tier 付きで監査 JSON か docs table に載っている

現在の状態:

- done
- source of truth は `python3 src/tools/audit_rtlmeter_ready_scoreboard.py --json-out work/rtlmeter_ready_scoreboard.json`
- `xbar_peri` まで checked-in comparison artifacts が揃い、`Tier R=8`, `Tier T=0` になった

### Wave 2: Choose One Expansion Mechanism

目的:

- 2 本目 target を design 名ではなく mechanism で進める

branch A: `current tb_timed_coroutine model`

- `tlul_err`, `tlul_sink` は source 復旧済みなので、必要なら current model で pilot を追加する
- `tlul_fifo_async`, `tlul_err`, `tlul_sink` の中から current model で再評価する対象を 1 本選ぶ
- 選んだ design で stock build -> host probe -> watch summary を再実行する
- どれか 1 本でも GPU-driven delta が出れば、その branch を継続する

branch B: `thinner host-driven top`

- `tlul_fifo_sync` host wrapper を本線として維持する
- `host_clock_control=true` かつ `host_reset_control=true` は確認済みの gate として扱う
- `thin_top_edge_parity_v1` は checked-in `Tier R` gate として扱う
- 次の gate は、その reference surfaceを `Tier S` へ昇格させるために何を追加で要求するかを定義すること

branch decision gate:

- current model を続けるなら、checked-in pilots のあとでも 1 本は `Tier B -> Tier R/S` の上昇見込みが必要
- thin-top を続けるなら、`tlul_fifo_sync` はすでに `Tier R` なので、
  次は promotion-to-`Tier S` work を本当にやるかどうかの判断が必要

### Wave 3: Land The Second Target

目的:

- `socket_m1` 依存の特例状態を抜ける

タスク:

1. Wave 2 で見込みが出た design を 1 本選ぶ、または既存 `Tier R` surface を `Tier S` に昇格させる
2. stable validation JSON を追加する
3. supported に上げるか、reference-design に留めるかを gate で明示する

done 条件:

- `Tier S` か `Tier R` が `socket_m1` 以外に 1 本増える

### Wave 4: Re-enter Multi-Clock OpenTitan

目的:

- `xbar_main`, `xbar_peri`, `tlul_fifo_async` のいずれか 1 本で ownership 拡張の妥当性を測る

タスク:

1. single-clock expansion の結果を使って、multi-clock design 1 本を選ぶ
2. watch field と safety signal を設計し直す
3. `Tier T/M -> Tier B` を最低限の達成ラインに置く

### Wave 5: First Non-OpenTitan Family

目的:

- repo-wide coverage を OpenTitan subset から外へ広げる

selection rule:

- checked-in `*_gpu_cov_tb.sv` がある
- wrapper / source layout が単純
- OpenTitan TL-UL slice 専用 probe を全面改造しなくても、最小 adapter で build/probe まで持ち込める

done 条件:

- non-OpenTitan 1 family が `Tier U -> Tier B` 以上に上がる

## Immediate Next Tasks

1. `socket_m1` comparison を最初の campaign-speed source of truth として維持する
2. `tlul_fifo_sync` comparison を second campaign artifact として読む
   - historical v1 result は `winner=hybrid`, `speedup_ratio≈1.16`
3. `tlul_request_loopback` comparison を third campaign artifact として維持する
   - current active result は `winner=hybrid`, `speedup_ratio≈4.87`
4. `tlul_err` comparison を fourth campaign artifact として維持する
   - current active result は `winner=hybrid`, `speedup_ratio≈14.06`
5. `tlul_sink` comparison を fifth campaign artifact として維持する
   - current active result は `winner=hybrid`, `speedup_ratio≈10.42`
6. `tlul_socket_1n` comparison を sixth campaign artifact として維持する
   - current active result は `winner=hybrid`, `speedup_ratio≈8.05`
   - `work/campaign_speed_scoreboard_active.json` が current active 6 本を集約する machine-readable source of truth
7. current active recommendation の通り、next surface ではなく next axis を選ぶ
8. `work/campaign_post_checkpoint_axes.json` を post-checkpoint planning の source of truth として使う
9. current recommendation は `broaden_non_opentitan_family` で、first family は `XuanTie`、fallback は `VeeR`
10. `work/campaign_non_opentitan_entry.json` を first-deliverable-shape の source of truth として使う
    - current recommendation は `XuanTie + family_pilot`
11. `work/campaign_non_opentitan_entry_readiness.json` を current workspace でその entry shape が実行可能かの source of truth として使う
    - current state は `legacy_family_pilot_failed_but_single_surface_override_ready`
    - `output/legacy_validation/xuantie_family_gpu_toggle_validation.json` が `family_pilot` の negative source of truth
    - `work/xuantie_e902_gpu_cov_gate_stock_verilator_cc_bootstrap.json` と `work/xuantie_e906_gpu_cov_gate_stock_verilator_cc_bootstrap.json` が `single_surface` override の ready source of truth
    - つまり次の decision は `XuanTie` の是非ではなく、legacy bench を復旧するか `XuanTie-E902` / `XuanTie-E906` の `single_surface` override に切り替えるか
12. `work/campaign_non_opentitan_override_candidates.json` を override branch の first-design decision の source of truth として使う
    - current recommendation は `XuanTie-E902`
    - fallback は `XuanTie-E906`
    - `XuanTie-E902` は `output/validation/xuantie_e902_{stock_hybrid_validation,cpu_baseline_validation,time_to_threshold_comparison}.json` の checked-in trio を持ち、comparison は `winner=hybrid`
    - `XuanTie-E906` は default checked-in trio では unresolved だが、`output/validation/xuantie_e906_time_to_threshold_comparison_threshold2.json` に candidate-only `threshold=2` hybrid win がある
    - `work/xuantie_e906_case_variants.json` は `cmark / hello / memcpy` の known workload sweep を固定し、default gate が workload swap では解けないことを示す
13. `work/campaign_non_opentitan_entry_profiles.json` と `work/campaign_non_opentitan_entry_gate.json` を named profile decision の source of truth として使う
    - current profile は `xuantie_single_surface_e902`
    - current gate は `single_surface_trio_ready`
    - alternate hold profile は `xuantie_family_pilot_hold` で、profile matrix 上の outcome は `family_pilot_blocked`
14. `work/campaign_non_opentitan_seed_status.json` を checkpoint 後の first non-OpenTitan seed readiness proof として使う
    - current status は `ready_to_accept_selected_seed`
    - active acceptance state 自体は `work/campaign_real_goal_acceptance_gate.json` が持ち、現在は `accepted_checkpoint_and_seed`
15. `work/campaign_xuantie_breadth_status.json` を accepted `XuanTie-E902` seed の次に何を決めるかの source of truth として使う
    - current status は `decide_threshold2_promotion_vs_non_cutoff_default_gate`
    - ただし current checked-in selection はもう `e906_candidate_only_threshold2` で、`work/campaign_xuantie_breadth_gate.json` は `candidate_only_ready`
16. `work/campaign_xuantie_breadth_acceptance_gate.json` を current XuanTie breadth baseline の acceptance state として使う
    - current status は `accepted_selected_xuantie_breadth`
    - つまり `XuanTie-E906 threshold2` line は checked-in breadth evidence として受け入れ済み
17. `work/campaign_non_opentitan_breadth_axes.json` を E902+E906 accepted baseline 後の次 branch の source of truth として使う
    - current status は `decide_continue_xuantie_breadth_vs_open_fallback_family`
    - remaining same-family designs は `XuanTie-C906` / `XuanTie-C910`
    - fallback family は `VeeR`
18. `work/campaign_xuantie_same_family_step.json` を selected same-family branch の first concrete step の source of truth として使う
    - current status は `decide_selected_same_family_design_candidate_only_vs_new_default_gate`
    - current selected design は `XuanTie-C906`
    - default gate は unresolved、candidate-only `threshold=5` line は hybrid win
19. `work/campaign_xuantie_same_family_acceptance_gate.json` を current same-family breadth evidence の acceptance state として使う
    - current status は `accepted_selected_same_family_step`
    - つまり `XuanTie-C906 threshold5` line は checked-in same-family breadth evidence として受け入れ済み
20. `work/campaign_xuantie_same_family_next_axes.json` を accepted `C906` line の次 branch の source of truth として使う
    - current status は `decide_continue_to_remaining_same_family_design_vs_open_fallback_family`
    - remaining same-family design は `XuanTie-C910`
    - fallback family は `VeeR`
21. `work/campaign_xuantie_c910_runtime_status.json` を `XuanTie-C910` を実際に開いた後の blocker summary として使う
    - current status は `decide_hybrid_runtime_debug_vs_open_veer_fallback_family`
    - CPU baseline は `ok`
    - PTX-backed hybrid runtime は minimal shape でも `SIGKILL`
22. `work/campaign_xuantie_c910_runtime_gate.json` と `work/campaign_xuantie_c910_runtime_profiles.json` を current C910 runtime branch の source of truth として使う
    - current checked-in profile は `debug_c910_hybrid_runtime`
    - ready alternatives は `debug_c910_hybrid_runtime` と `open_veer_fallback_family`
    - recommended profile は `debug_c910_hybrid_runtime`
23. `work/campaign_xuantie_c910_debug_tactics.json` を accepted C910 runtime-debug branch の next tactic source of truth として使う
    - current status は `try_kernel_split_phases_before_opening_fallback_family`
    - current recommendation は `kernel_split_phases_ptx_module_first`
    - fallback tactic は `open_veer_fallback_family`

comparison contract の source of truth は `docs/socket_m1_time_to_threshold_packet.md` を引き続き使う。
next-KPI decision の source of truth は `docs/campaign_next_kpi_packet.md` を使う。

## Explicit Non-Goals

- `strict_final_state` を coverage expansion の blocker にしない
- `tlul_request_loopback` の nearby tuning を main line に戻さない
- current milestone の `socket_m1` supported status を崩してまで 2 本目 target を急がない
