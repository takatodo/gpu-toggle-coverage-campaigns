# Input / Output Map

このドキュメントは、stock-Verilator hybrid flow の入出力物を
`何を入力として受けるか` と `何をどこへ出すか` の観点で整理する。

status の読み分けは [status_surfaces.md](status_surfaces.md) を参照。
ここでは `コマンド -> 入力物 -> 出力物` の対応だけを見る。

## 1. 基本の考え方

このリポジトリの入出力物は大きく 5 層に分かれる。

| 層 | 主な入力 | 主な出力 | 置き場所 |
|---|---|---|---|
| build / analysis | Verilator `--cc` 出力ディレクトリ (`mdir`) | cubin, meta, phase report, classifier report, compare / trace artifact | `work/vl_ir_exp/<design>_vl/` |
| host probe / host->GPU glue | `mdir`, template JSON, host ABI | host report JSON, init-state bin, flow summary JSON | `work/vl_ir_exp/<design>_vl/` |
| stable validation | flow summary, host report, GPU stdout | validation JSON | `output/validation/` |
| campaign comparison | stable hybrid validation, CPU baseline validation | baseline JSON, time-to-threshold comparison JSON | `output/validation/` |
| legacy validation | sim-accel / RTLMeter runner inputs | legacy aggregate JSON | `output/legacy_validation/` |

## 2. 共通入力物

### 2.1 `mdir`

もっとも重要な入力は Verilator `--cc` 出力ディレクトリ。

例:

- `work/vl_ir_exp/socket_m1_vl`
- `work/vl_ir_exp/tlul_request_loopback_vl`

`mdir` に最低限必要なもの:

- `*_classes.mk`
- Verilator 生成 `.cpp`
- Verilator 生成 header
- `libverilated.a` を作れる Makefile 群

### 2.2 template JSON

TL-UL slice 系 host probe が使う静的入力。

場所:

- `config/slice_launch_templates/tlul_request_loopback.json`

役割:

- host probe の `cfg_*` 初期値
- runner の既定 `nstates`
- runner の既定 `steps`
- optional `debug_internal_output_names` による watch field 候補

### 2.3 classifier expectation JSON

classifier report 監査の静的入力。

場所:

- `config/classifier_expectations/tlul_socket_m1.json`
- `config/classifier_expectations/tlul_request_loopback.json`

役割:

- `reachable/gpu/runtime` 件数の期待値
- 必須 reason category
- 必須 function pattern

## 3. build / analysis の入出力

### 3.1 `build_vl_gpu.py`

コマンド:

```bash
python3 src/tools/build_vl_gpu.py <mdir> [--analyze-phases] [--kernel-split-phases]
```

主入力:

- `<mdir>`
- optional: `--analyze-phases`
- optional: `--kernel-split-phases`

主出力:

- `<mdir>/merged.ll`
- `<mdir>/vl_phase_analysis.json`
- `<mdir>/vl_classifier_report.json`
- `<mdir>/vl_kernel_manifest.json`
- `<mdir>/vl_batch_gpu.ll`
- `<mdir>/vl_batch_gpu_patched.ll`
- `<mdir>/vl_batch_gpu_opt.ll`
- `<mdir>/vl_batch_gpu.ptx`
- `<mdir>/vl_batch_gpu.cubin`
- `<mdir>/vl_batch_gpu.meta.json`

特に読むべき出力:

| 出力 | 意味 |
|---|---|
| `vl_phase_analysis.json` | `_eval` から `___ico_*` / `___nba_*` が到達可能か |
| `vl_classifier_report.json` | 関数ごとの `gpu` / `runtime` 分類理由 |
| `vl_kernel_manifest.json` | split kernel の順序と selector |
| `vl_batch_gpu.meta.json` | runner が読む build contract |

### 3.2 `audit_vl_classifier_report.py`

コマンド:

```bash
python3 src/tools/audit_vl_classifier_report.py <mdir>/vl_classifier_report.json \
  --expect config/classifier_expectations/<target>.json \
  --json-out <mdir>/vl_classifier_audit.json
```

主入力:

- `vl_classifier_report.json`
- `config/classifier_expectations/*.json`

主出力:

- `<mdir>/vl_classifier_audit.json`

役割:

- classifier drift を実 design で検出する

### 3.3 `compare_vl_hybrid_modes.py`

コマンド:

```bash
python3 src/tools/compare_vl_hybrid_modes.py <mdir> --json-out <out.json>
```

主入力:

- `<mdir>/vl_batch_gpu.cubin`
- `<mdir>/vl_batch_gpu.meta.json`

主出力:

- `<mdir>/vl_hybrid_compare*.json`
- optional raw dump

役割:

- single `_eval` と split launch の parity 比較

### 3.4 `audit_second_target_feasibility.py`

コマンド:

```bash
python3 src/tools/audit_second_target_feasibility.py \
  --json-out work/second_target_feasibility_audit.json
```

主入力:

- `config/slice_launch_templates/index.json`
- `config/slice_launch_templates/*.json`
- `work/vl_ir_exp/<candidate>_vl/` の build / probe / watch artifacts
- `third_party/rtlmeter/designs/OpenTitan/src/*_gpu_cov_tb.sv`
- `third_party/rtlmeter/designs/OpenTitan/src/*_gpu_cov_cpu_replay_tb.sv`

主出力:

- `work/second_target_feasibility_audit.json`

役割:

- 2 本目 supported target 候補の blocker を 1 枚に集約する
- `thinner host-driven top` を選ぶならどの design を seed にするかを recommendation として返す
- current `tb_timed_coroutine` model に quick win が残っているか、それとも defer が妥当かを返す

### 3.5 `audit_rtlmeter_ready_scoreboard.py`

コマンド:

```bash
python3 src/tools/audit_rtlmeter_ready_scoreboard.py \
  --json-out work/rtlmeter_ready_scoreboard.json
```

主入力:

- `config/slice_launch_templates/index.json`
- `config/slice_launch_templates/*.json`
- `output/validation/*_stock_hybrid_validation.json`
- `work/vl_ir_exp/<design>_vl/` の build / probe / watch artifacts

主出力:

- `work/rtlmeter_ready_scoreboard.json`

役割:

- OpenTitan `ready_for_campaign` 9 本を `Tier S/R/B/T/M` に機械分類する
- repo-wide coverage expansion の分母と current counts を固定する
- `xbar_peri` まで campaign reference surface に上がり、OpenTitan `ready_for_campaign` pool が `Tier S=1`, `Tier R=8`, `Tier T=0` になったことを 1 枚で読む

### 3.6 `audit_rtlmeter_expansion_branches.py`

コマンド:

```bash
python3 src/tools/audit_rtlmeter_expansion_branches.py \
  --scoreboard work/rtlmeter_ready_scoreboard.json \
  --feasibility work/second_target_feasibility_audit.json \
  --json-out work/rtlmeter_expansion_branch_audit.json
```

主入力:

- `work/rtlmeter_ready_scoreboard.json`
- `work/second_target_feasibility_audit.json`

主出力:

- `work/rtlmeter_expansion_branch_audit.json`

役割:

- `coverage を早く増やす` と `2 本目の Tier R/S を最短で狙う` を分けて branch recommendation を返す
- `current tb_timed_coroutine model` / `thinner host-driven top` / `defer` の 3 択を objective ごとに固定する
- 2026-04-04 時点では、raw tier-count quick win が尽きたため `maximize_ready_tier_count_quickly` も `defer_second_target` を返しうる

### 3.7 `audit_agents_guidelines.py`

コマンド:

```bash
python3 src/tools/audit_agents_guidelines.py \
  --json-out work/agents_guideline_audit.json
```

主入力:

- `AGENTS.md`
- `README.md`
- `docs/**/*.md`
- `src/tools/*.py`
- `src/runners/*.py`
- `src/scripts/tests/test_*.py`

主出力:

- `work/agents_guideline_audit.json`

役割:

- `AGENTS.md` の配置・命名・test/doc 同期ルールを machine-readable に集計する
- hard gate として `repo_root_python_file_count == 0` と `banned_python_filename_count == 0` を返す
- scoreboard として CLI の test 追従率、doc 追従率、長大 CLI 本数を返す

### 3.8 `audit_campaign_post_checkpoint_axes.py`

コマンド:

```bash
python3 src/tools/audit_campaign_post_checkpoint_axes.py \
  --json-out work/campaign_post_checkpoint_axes.json
```

主入力:

- `work/campaign_checkpoint_readiness.json`
- `work/campaign_speed_scoreboard_active.json`
- `work/campaign_next_kpi_active.json`
- `third_party/rtlmeter/designs/**/_gpu_cov_tb.sv`
- `src/runners/run_*_gpu_toggle_validation.py`
- `src/runners/run_*_family_gpu_toggle_validation.py`

主出力:

- `work/campaign_post_checkpoint_axes.json`

役割:

- current checkpoint の後で、次の本線を `next surface` ではなく `next axis` として返す
- `broaden_non_opentitan_family` / `strengthen_thresholds` / `reopen_supported_promotion` を並べる
- current ready pool が exhausted かつ active line が still OpenTitan-only なら、first non-OpenTitan family を recommendation として返す

### 3.9 `audit_campaign_non_opentitan_entry.py`

コマンド:

```bash
python3 src/tools/audit_campaign_non_opentitan_entry.py \
  --json-out work/campaign_non_opentitan_entry.json
```

主入力:

- `work/campaign_post_checkpoint_axes.json`
- `src/runners/run_*_gpu_toggle_validation.py`
- `src/runners/run_*_family_gpu_toggle_validation.py`

主出力:

- `work/campaign_non_opentitan_entry.json`

役割:

- first non-OpenTitan family を `single_surface` で始めるか `family_pilot` で始めるかを返す
- current checked-in state では `XuanTie + family_pilot` を recommendation として返す

### 3.10 `audit_campaign_non_opentitan_entry_readiness.py`

コマンド:

```bash
python3 src/tools/audit_campaign_non_opentitan_entry_readiness.py \
  --json-out work/campaign_non_opentitan_entry_readiness.json
```

入力:

- `work/campaign_non_opentitan_entry.json`
- `third_party/verilator/bin/verilator_sim_accel_bench`
- `third_party/verilator/bin/verilator`
- `rtlmeter/venv/bin/python`
- `output/legacy_validation/<family>_family_gpu_toggle_validation.json`

出力:

- `work/campaign_non_opentitan_entry_readiness.json`

読み方:

- current recommended entry shape が current workspace で本当に実行可能かを返す
- current checked-in state では `XuanTie + family_pilot` に対して
  `readiness=legacy_family_pilot_failed_but_single_surface_override_ready` を返し、
  `output/legacy_validation/xuantie_family_gpu_toggle_validation.json` を `family_pilot` の negative source of truth としつつ、
  `work/xuantie_e902_gpu_cov_gate_stock_verilator_cc_bootstrap.json` / `work/xuantie_e906_gpu_cov_gate_stock_verilator_cc_bootstrap.json` を `single_surface` override の ready source of truth として使う

`work/campaign_non_opentitan_override_candidates.json`

読み方:

- ready な `single_surface` override 候補を rank する
- current checked-in state では `recommended_design=XuanTie-E902`, `fallback_design=XuanTie-E906` を返す
- `ranked_candidates[*].best_candidate_variant_path` があれば、checked-in trio とは別に candidate-only threshold variant があることを意味する
- `work/xuantie_e906_case_variants.json`
  - `XuanTie-E906` の `cmark / hello / memcpy` workload sweep を集約する
  - default gate blocked か、known workload swap で headroom が増えるかを返す
- `XuanTie-E902` については `stock_hybrid / cpu_baseline / comparison` trio の有無も併記し、現在は `validated_trio_ready=true`, `hybrid_wins=true` を返す

### 3.11 `audit_campaign_non_opentitan_entry_profiles.py`

コマンド:

```bash
python3 src/tools/audit_campaign_non_opentitan_entry_profiles.py \
  --json-out work/campaign_non_opentitan_entry_profiles.json
```

出力:

- `work/campaign_non_opentitan_entry_profiles.json`

読み方:

- `family_pilot` と `single_surface` override を named profile で比較する
- current checked-in state では `current_profile_name=xuantie_single_surface_e902`
- alternate hold profile は `xuantie_family_pilot_hold`
- current selection は `single_surface_trio_ready` を返す

### 3.12 `set_campaign_non_opentitan_entry.py`

コマンド:

```bash
python3 src/tools/set_campaign_non_opentitan_entry.py \
  --profile-name xuantie_single_surface_e902
```

出力:

- `config/campaign_non_opentitan_entry/selection.json`
- `work/campaign_non_opentitan_entry_gate.json`

読み方:

- current selected profile の active outcome を返す
- current checked-in state では `status=single_surface_trio_ready`

### 3.13 `audit_campaign_non_opentitan_seed_status.py`

コマンド:

```bash
python3 src/tools/audit_campaign_non_opentitan_seed_status.py \
  --json-out work/campaign_non_opentitan_seed_status.json
```

出力:

- `work/campaign_non_opentitan_seed_status.json`

読み方:

- current OpenTitan checkpoint と selected non-OpenTitan entry を 1 枚に圧縮する
- current checked-in state では `status=ready_to_accept_selected_seed`
- これは readiness proof として読む
- active acceptance state 自体は `work/campaign_real_goal_acceptance_gate.json` が持つ

### 3.14 `audit_campaign_real_goal_acceptance_profiles.py`

コマンド:

```bash
python3 src/tools/audit_campaign_real_goal_acceptance_profiles.py \
  --json-out work/campaign_real_goal_acceptance_profiles.json
```

出力:

- `work/campaign_real_goal_acceptance_profiles.json`

読み方:

- OpenTitan checkpoint と selected non-OpenTitan seed の acceptance を named profile で比較する
- current checked-in state では `accept_checkpoint_and_seed` が `accepted`
- つまり current question は checkpoint/seed acceptance ではなく、その次の XuanTie breadth decision

### 3.15 `set_campaign_real_goal_acceptance.py`

コマンド:

```bash
python3 src/tools/set_campaign_real_goal_acceptance.py \
  --profile-name accept_checkpoint_and_seed
```

出力:

- `config/campaign_real_goal_acceptance/selection.json`
- `work/campaign_real_goal_acceptance_gate.json`

読み方:

- checkpoint/seed acceptance profile を selection に適用する
- current checked-in state では gate は `status=accepted_checkpoint_and_seed`

### 3.16 `audit_campaign_xuantie_breadth_status.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xuantie_breadth_status.py \
  --json-out work/campaign_xuantie_breadth_status.json
```

出力:

- `work/campaign_xuantie_breadth_status.json`

読み方:

- accepted checkpoint + accepted `XuanTie-E902` seed の次に何を決めるかを 1 枚に圧縮する
- current checked-in state では `status=decide_threshold2_promotion_vs_non_cutoff_default_gate`
- つまり next task は `threshold=2` を昇格させるか、numeric cutoff ではない新しい default gate を定義するかの判断

### 3.17 `audit_campaign_xuantie_breadth_profiles.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xuantie_breadth_profiles.py \
  --json-out work/campaign_xuantie_breadth_profiles.json
```

出力:

- `work/campaign_xuantie_breadth_profiles.json`

読み方:

- `XuanTie-E906` breadth branch を named profile で比較する
- current checked-in state では current=`e906_candidate_only_threshold2`
- historical hold は `e906_default_gate_hold`
- blocked alternative は `xuantie_family_pilot_recovery`

### 3.18 `set_campaign_xuantie_breadth.py`

コマンド:

```bash
python3 src/tools/set_campaign_xuantie_breadth.py \
  --profile-name e906_candidate_only_threshold2
```

出力:

- `config/campaign_xuantie_breadth/selection.json`
- `work/campaign_xuantie_breadth_gate.json`

読み方:

- E906 breadth profile を selection に適用する
- current checked-in state では gate は `status=candidate_only_ready`

### 3.19 `audit_xuantie_e906_threshold_options.py`

コマンド:

```bash
python3 src/tools/audit_xuantie_e906_threshold_options.py \
  --json-out work/xuantie_e906_threshold_options.json
```

出力:

- `work/xuantie_e906_threshold_options.json`

読み方:

- checked-in `cmark / hello / memcpy` workload 群に対して、どの numeric `toggle_bits_hit` gate がまだ候補かを圧縮する
- current checked-in state では `status=threshold2_is_strongest_ready_numeric_gate`
- つまり `threshold=2` は ready、`3..8` は blocked で、new default gate を作るなら numeric cutoff 以外の semantics が要る

### 3.20 `audit_campaign_xuantie_breadth_acceptance_profiles.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xuantie_breadth_acceptance_profiles.py \
  --json-out work/campaign_xuantie_breadth_acceptance_profiles.json
```

出力:

- `work/campaign_xuantie_breadth_acceptance_profiles.json`

読み方:

- selected `XuanTie` breadth step の acceptance branch を named profile で比較する
- current checked-in state では current=`accept_selected_xuantie_breadth`
- hold alternative は `hold_selected_xuantie_breadth`

### 3.21 `set_campaign_xuantie_breadth_acceptance.py`

コマンド:

```bash
python3 src/tools/set_campaign_xuantie_breadth_acceptance.py \
  --profile-name accept_selected_xuantie_breadth
```

出力:

- `config/campaign_xuantie_breadth_acceptance/selection.json`
- `work/campaign_xuantie_breadth_acceptance_gate.json`

読み方:

- selected breadth acceptance profile を selection に適用する
- current checked-in state では gate は `status=accepted_selected_xuantie_breadth`

### 3.22 `audit_campaign_non_opentitan_breadth_axes.py`

コマンド:

```bash
python3 src/tools/audit_campaign_non_opentitan_breadth_axes.py \
  --json-out work/campaign_non_opentitan_breadth_axes.json
```

出力:

- `work/campaign_non_opentitan_breadth_axes.json`

読み方:

- accepted checkpoint + accepted `XuanTie-E902` seed + accepted `XuanTie-E906` breadth の次 branch を 1 枚に圧縮する
- current checked-in state では `status=decide_continue_xuantie_breadth_vs_open_fallback_family`
- same-family remaining designs は `XuanTie-C906` / `XuanTie-C910`
- fallback family は `VeeR`

### 3.23 `audit_campaign_non_opentitan_breadth_profiles.py`

コマンド:

```bash
python3 src/tools/audit_campaign_non_opentitan_breadth_profiles.py \
  --json-out work/campaign_non_opentitan_breadth_profiles.json
```

出力:

- `work/campaign_non_opentitan_breadth_profiles.json`

読み方:

- accepted `XuanTie-E902` seed + accepted `XuanTie-E906` breadth の次 branch を named profile で比較する
- current checked-in state では current=`xuantie_continue_same_family`
- remaining ready alternative は `open_veer_fallback_family`
- branch recommendation は `xuantie_continue_same_family` first / `XuanTie-C906` first design

### 3.24 `set_campaign_non_opentitan_breadth.py`

コマンド:

```bash
python3 src/tools/set_campaign_non_opentitan_breadth.py \
  --profile-name xuantie_continue_same_family
```

出力:

- `config/campaign_non_opentitan_breadth/selection.json`
- `work/campaign_non_opentitan_breadth_gate.json`

読み方:

- post-E906 non-OpenTitan breadth の named profile を checked-in selection に適用する
- `xuantie_continue_same_family` を選ぶと next action は `choose_the_next_same_family_design`
- `open_veer_fallback_family` を選ぶと next action は `open_fallback_non_opentitan_family`
- current checked-in state では selection は `xuantie_continue_same_family`

### 3.25 `audit_campaign_non_opentitan_breadth_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_non_opentitan_breadth_gate.py \
  --json-out work/campaign_non_opentitan_breadth_gate.json
```

出力:

- `work/campaign_non_opentitan_breadth_gate.json`

読み方:

- current checked-in post-E906 breadth selection の active outcome を返す
- current checked-in state では `status=continue_same_family_ready`
- つまり E902+E906 accepted baseline の次 branch は same-family continuation として checked-in

### 3.26 `audit_campaign_non_opentitan_breadth_branch_candidates.py`

コマンド:

```bash
python3 src/tools/audit_campaign_non_opentitan_breadth_branch_candidates.py \
  --json-out work/campaign_non_opentitan_breadth_branch_candidates.json
```

出力:

- `work/campaign_non_opentitan_breadth_branch_candidates.json`

読み方:

- selected same-family branch と fallback family branch を current repo state で比較する
- current checked-in state では `status=recommend_same_family_first`
- recommended profile は `xuantie_continue_same_family`
- recommended first design は `XuanTie-C906`
- fallback profile は `open_veer_fallback_family`

### 3.27 `audit_campaign_xuantie_same_family_step.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xuantie_same_family_step.py \
  --json-out work/campaign_xuantie_same_family_step.json
```

出力:

- `work/campaign_xuantie_same_family_step.json`

読み方:

- active `xuantie_continue_same_family` branch の first concrete step を圧縮する
- current checked-in state では `status=decide_selected_same_family_design_candidate_only_vs_new_default_gate`
- current selected design は `XuanTie-C906`
- default line は `output/validation/xuantie_c906_time_to_threshold_comparison.json`
- candidate-only line は `output/validation/xuantie_c906_time_to_threshold_comparison_threshold5.json`

### 3.28 `audit_campaign_xuantie_same_family_profiles.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xuantie_same_family_profiles.py \
  --json-out work/campaign_xuantie_same_family_profiles.json
```

出力:

- `work/campaign_xuantie_same_family_profiles.json`

読み方:

- selected same-family step を named profile で比較する
- current checked-in state では current=`c906_candidate_only_threshold5`
- historical hold は `c906_default_gate_hold`

### 3.29 `set_campaign_xuantie_same_family.py`

コマンド:

```bash
python3 src/tools/set_campaign_xuantie_same_family.py \
  --profile-name c906_candidate_only_threshold5
```

出力:

- `config/campaign_xuantie_same_family/selection.json`
- `work/campaign_xuantie_same_family_gate.json`

読み方:

- selected same-family step の named profile を checked-in selection に適用する
- `c906_candidate_only_threshold5` を選ぶと next action は `accept_selected_same_family_candidate_only_step`
- `c906_default_gate_hold` を選ぶと same-family step を unresolved default gate に戻す

### 3.30 `audit_campaign_xuantie_same_family_acceptance_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xuantie_same_family_acceptance_gate.py \
  --json-out work/campaign_xuantie_same_family_acceptance_gate.json
```

出力:

- `work/campaign_xuantie_same_family_acceptance_gate.json`

読み方:

- current checked-in same-family step の acceptance state を返す
- current checked-in state では `status=accepted_selected_same_family_step`

### 3.31 `audit_campaign_xuantie_same_family_acceptance_profiles.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xuantie_same_family_acceptance_profiles.py \
  --json-out work/campaign_xuantie_same_family_acceptance_profiles.json
```

出力:

- `work/campaign_xuantie_same_family_acceptance_profiles.json`

読み方:

- same-family step acceptance を named profile で比較する
- current checked-in state では current=`accept_selected_same_family_step`
- hold alternative は `hold_selected_same_family_step`

### 3.32 `set_campaign_xuantie_same_family_acceptance.py`

コマンド:

```bash
python3 src/tools/set_campaign_xuantie_same_family_acceptance.py \
  --profile-name accept_selected_same_family_step
```

出力:

- `config/campaign_xuantie_same_family_acceptance/selection.json`
- `work/campaign_xuantie_same_family_acceptance_gate.json`

読み方:

- selected same-family step の acceptance profile を checked-in selection に適用する
- current checked-in state では selection は `accept_selected_same_family_step`

### 3.33 `audit_campaign_xuantie_same_family_next_axes.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xuantie_same_family_next_axes.py \
  --json-out work/campaign_xuantie_same_family_next_axes.json
```

出力:

- `work/campaign_xuantie_same_family_next_axes.json`

読み方:

- accepted same-family step の次 branch を圧縮する
- current checked-in state では `status=decide_continue_to_remaining_same_family_design_vs_open_fallback_family`
- remaining same-family design は `XuanTie-C910`
- fallback family は `VeeR`

### 3.34 `audit_campaign_xuantie_c910_runtime_status.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xuantie_c910_runtime_status.py \
  --json-out work/campaign_xuantie_c910_runtime_status.json
```

出力:

- `work/campaign_xuantie_c910_runtime_status.json`

読み方:

- `XuanTie-C910` を実際に開いた後の blocker を圧縮する
- current checked-in state では `status=decide_hybrid_runtime_debug_vs_open_veer_fallback_family`
- CPU baseline は `ok`
- `O0` low-opt rebuild は `llc` の `AtomicLoad acquire (s64)` selection で abort
- `O1` low-opt trace でも last stage は `before_cuModuleLoad`

### 3.35 `audit_campaign_xuantie_c910_runtime_profiles.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xuantie_c910_runtime_profiles.py \
  --json-out work/campaign_xuantie_c910_runtime_profiles.json
```

出力:

- `work/campaign_xuantie_c910_runtime_profiles.json`

読み方:

- `C910` runtime branch を named profile で比較する
- current checked-in state では current=`open_veer_fallback_family`
- ready alternatives は `debug_c910_hybrid_runtime` と `open_veer_fallback_family`
- current recommendation は `open_veer_fallback_family`

### 3.36 `set_campaign_xuantie_c910_runtime.py`

コマンド:

```bash
python3 src/tools/set_campaign_xuantie_c910_runtime.py \
  --profile-name open_veer_fallback_family
```

出力:

- `config/campaign_xuantie_c910_runtime/selection.json`
- `work/campaign_xuantie_c910_runtime_gate.json`

読み方:

- `C910` runtime branch の named profile を checked-in selection に適用する
- `debug_c910_hybrid_runtime` を選ぶと same-family continuation を保ったまま runtime debug が active
- `open_veer_fallback_family` を選ぶと `VeeR` fallback へ切り替える

### 3.37 `audit_campaign_xuantie_c910_debug_tactics.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xuantie_c910_debug_tactics.py \
  --split-phase-trial-json work/campaign_xuantie_c910_split_phase_trial.json \
  --json-out work/campaign_xuantie_c910_debug_tactics.json
```

出力:

- `work/campaign_xuantie_c910_debug_tactics.json`

読み方:

- accepted `debug_c910_hybrid_runtime` branch の下で、次の concrete debug tactic を返す
- current checked-in state では
  `status=prefer_fallback_family_after_split_phase_trial_failed`
- current recommendation は `open_veer_fallback_family`
- fallback tactic は `deeper_c910_cubin_debug`

### 3.38 `audit_campaign_xuantie_c910_split_phase_trial.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xuantie_c910_split_phase_trial.py \
  --json-out work/campaign_xuantie_c910_split_phase_trial.json
```

出力:

- `work/campaign_xuantie_c910_split_phase_trial.json`

読み方:

- `C910` の split-phase PTX/module-first trial を machine-readable に固定する
- current checked-in state では `status=timed_out_before_cuModuleLoad`
- traced last stage は `before_cuModuleLoad`
- next action は `choose_between_open_veer_fallback_family_and_deeper_c910_cubin_debug`

### 3.39 `audit_campaign_veer_fallback_candidates.py`

コマンド:

```bash
python3 src/tools/audit_campaign_veer_fallback_candidates.py \
  --json-out work/campaign_veer_fallback_candidates.json
```

出力:

- `work/campaign_veer_fallback_candidates.json`

読み方:

- `VeeR` fallback family の first concrete design choice を返す
- current checked-in state では `status=recommend_first_veer_single_surface_candidate`
- current recommendation は `VeeR-EH1`
- fallback design は `VeeR-EH2`

### 3.40 `audit_campaign_veer_first_surface_step.py`

コマンド:

```bash
python3 src/tools/audit_campaign_veer_first_surface_step.py \
  --json-out work/campaign_veer_first_surface_step.json
```

出力:

- `work/campaign_veer_first_surface_step.json`

読み方:

- accepted `VeeR-EH1` より前の historical first-surface decision packet を返す
- artifact 自体は `status=decide_veer_eh1_candidate_only_vs_new_default_gate`
- default comparison path は `output/validation/veer_eh1_time_to_threshold_comparison.json`
- candidate-only path は `output/validation/veer_eh1_time_to_threshold_comparison_threshold5.json`

### 3.41 `audit_campaign_veer_first_surface_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_veer_first_surface_gate.py \
  --json-out work/campaign_veer_first_surface_gate.json
```

出力:

- `work/campaign_veer_first_surface_gate.json`

読み方:

- checked-in な first VeeR profile の active outcome を返す
- current checked-in state では `status=candidate_only_ready`

### 3.42 `audit_campaign_veer_first_surface_acceptance_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_veer_first_surface_acceptance_gate.py \
  --json-out work/campaign_veer_first_surface_acceptance_gate.json
```

出力:

- `work/campaign_veer_first_surface_acceptance_gate.json`

読み方:

- selected VeeR first surface が checked-in breadth evidence として受け入れ済みかを返す
- current checked-in state では `status=accepted_selected_veer_first_surface_step`

### 3.43 `audit_campaign_veer_next_axes.py`

コマンド:

```bash
python3 src/tools/audit_campaign_veer_next_axes.py \
  --json-out work/campaign_veer_next_axes.json
```

出力:

- `work/campaign_veer_next_axes.json`

読み方:

- accepted `VeeR-EH1` の次に同 family をどう続けるかを返す
- current checked-in state では `status=decide_continue_to_remaining_veer_design`
- recommended next design は `VeeR-EH2`
- remaining fallback inside the family は `VeeR-EL2`

### 3.44 `audit_campaign_veer_same_family_step.py`

コマンド:

```bash
python3 src/tools/audit_campaign_veer_same_family_step.py \
  --json-out work/campaign_veer_same_family_step.json
```

出力:

- `work/campaign_veer_same_family_step.json`

読み方:

- accepted `VeeR-EH1` 後の current concrete VeeR step を返す
- current checked-in state では `status=decide_veer_eh2_candidate_only_vs_new_default_gate`
- default comparison path は `output/validation/veer_eh2_time_to_threshold_comparison.json`
- candidate-only path は `output/validation/veer_eh2_time_to_threshold_comparison_threshold4.json`

### 3.45 `set_campaign_veer_same_family.py`

コマンド:

```bash
python3 src/tools/set_campaign_veer_same_family.py \
  --profile-name veer_eh2_candidate_only_threshold4
```

出力:

- `config/campaign_veer_same_family/selection.json`
- `work/campaign_veer_same_family_gate.json`

読み方:

- selected `VeeR-EH2` same-family profile を checked-in selection にする
- current checked-in state では `profile_name=veer_eh2_candidate_only_threshold4`
- gate outcome は `status=candidate_only_ready`

### 3.46 `set_campaign_veer_same_family_acceptance.py`

コマンド:

```bash
python3 src/tools/set_campaign_veer_same_family_acceptance.py \
  --profile-name accept_selected_veer_same_family_step
```

出力:

- `config/campaign_veer_same_family_acceptance/selection.json`
- `work/campaign_veer_same_family_acceptance_gate.json`

読み方:

- selected `VeeR-EH2` same-family step を checked-in breadth evidence として受け入れる
- current checked-in state では `status=accepted_selected_veer_same_family_step`

### 3.47 `audit_campaign_veer_same_family_next_axes.py`

コマンド:

```bash
python3 src/tools/audit_campaign_veer_same_family_next_axes.py \
  --json-out work/campaign_veer_same_family_next_axes.json
```

出力:

- `work/campaign_veer_same_family_next_axes.json`

読み方:

- accepted `VeeR-EH2` 後の next same-family design を返す
- current checked-in state では `status=decide_continue_to_remaining_veer_design`
- recommended next design は `VeeR-EL2`

### 3.48 `audit_campaign_veer_final_same_family_step.py`

コマンド:

```bash
python3 src/tools/audit_campaign_veer_final_same_family_step.py \
  --json-out work/campaign_veer_final_same_family_step.json
```

出力:

- `work/campaign_veer_final_same_family_step.json`

読み方:

- accepted `VeeR-EH2` 後の current concrete `VeeR-EL2` step を返す
- current checked-in state では `status=decide_veer_el2_candidate_only_vs_new_default_gate`
- default comparison path は `output/validation/veer_el2_time_to_threshold_comparison.json`
- candidate-only path は `output/validation/veer_el2_time_to_threshold_comparison_threshold6.json`

### 3.49 `audit_campaign_veer_final_same_family_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_veer_final_same_family_gate.py \
  --json-out work/campaign_veer_final_same_family_gate.json
```

出力:

- `work/campaign_veer_final_same_family_gate.json`

読み方:

- selected `VeeR-EL2` final same-family profile の active outcome を返す
- current checked-in state では `status=candidate_only_ready`
- selected profile は `veer_el2_candidate_only_threshold6`

### 3.50 `set_campaign_veer_final_same_family.py`

コマンド:

```bash
python3 src/tools/set_campaign_veer_final_same_family.py \
  --profile-name veer_el2_candidate_only_threshold6
```

出力:

- `config/campaign_veer_final_same_family/selection.json`
- `work/campaign_veer_final_same_family_gate.json`

読み方:

- named `VeeR-EL2` final same-family profile を checked-in selection として適用する
- current checked-in state では `veer_el2_candidate_only_threshold6`

### 3.51 `audit_campaign_veer_final_same_family_acceptance_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_veer_final_same_family_acceptance_gate.py \
  --json-out work/campaign_veer_final_same_family_acceptance_gate.json
```

出力:

- `work/campaign_veer_final_same_family_acceptance_gate.json`

読み方:

- selected `VeeR-EL2` final same-family step を checked-in breadth evidence として受け入れたかを返す
- current checked-in state では `status=accepted_selected_veer_final_same_family_step`

### 3.52 `set_campaign_veer_final_same_family_acceptance.py`

コマンド:

```bash
python3 src/tools/set_campaign_veer_final_same_family_acceptance.py \
  --profile-name accept_selected_veer_final_same_family_step
```

出力:

- `config/campaign_veer_final_same_family_acceptance/selection.json`
- `work/campaign_veer_final_same_family_acceptance_gate.json`

読み方:

- selected `VeeR-EL2` final same-family step の acceptance profile を checked-in selection として適用する
- current checked-in state では accepted profile が選ばれている

### 3.53 `audit_campaign_veer_post_family_exhaustion_axes.py`

コマンド:

```bash
python3 src/tools/audit_campaign_veer_post_family_exhaustion_axes.py \
  --json-out work/campaign_veer_post_family_exhaustion_axes.json
```

出力:

- `work/campaign_veer_post_family_exhaustion_axes.json`

読み方:

- accepted `VeeR-EL2` 後の next non-VeeR family branch を返す
- current checked-in state では `status=decide_open_next_non_veer_family_after_veer_exhaustion`
- recommended family は `XiangShan`
- fallback family は `OpenPiton`

## 3.14 `audit_campaign_openpiton_first_surface_step.py`

コマンド:

```bash
python3 src/tools/audit_campaign_openpiton_first_surface_step.py
```

主入力:

- `work/campaign_xiangshan_first_surface_status.json`
- `output/validation/openpiton_time_to_threshold_comparison.json`

出力:

- `work/campaign_openpiton_first_surface_step.json`

読み方:

- XiangShan fallback branch から見た OpenPiton first surface の current policy step を返す
- current checked-in state では `status=ready_to_accept_openpiton_default_gate`
- default threshold は `toggle_bits_hit >= 8`
- current checked-in comparison は `winner=hybrid`

## 3.15 `audit_campaign_openpiton_first_surface_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_openpiton_first_surface_gate.py
```

主入力:

- `work/campaign_openpiton_first_surface_step.json`
- `config/campaign_openpiton_first_surface/selection.json`

出力:

- `work/campaign_openpiton_first_surface_gate.json`

読み方:

- current checked-in OpenPiton first-surface profile の active outcome を返す
- current checked-in state では `status=default_gate_ready`
- checked-in default threshold は `toggle_bits_hit >= 8`

## 3.16 `audit_campaign_openpiton_first_surface_acceptance_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_openpiton_first_surface_acceptance_gate.py
```

主入力:

- `work/campaign_xiangshan_first_surface_status.json`
- `work/campaign_openpiton_first_surface_gate.json`
- `config/campaign_openpiton_first_surface_acceptance/selection.json`

出力:

- `work/campaign_openpiton_first_surface_acceptance_gate.json`

読み方:

- OpenPiton first surface を checked-in acceptance state に進めた current outcome を返す
- current checked-in state では `status=accepted_selected_openpiton_first_surface_step`

## 3.17 `audit_campaign_post_openpiton_axes.py`

コマンド:

```bash
python3 src/tools/audit_campaign_post_openpiton_axes.py
```

主入力:

- `work/campaign_openpiton_first_surface_acceptance_gate.json`
- `work/campaign_xiangshan_first_surface_status.json`
- `third_party/rtlmeter/designs/*/*_gpu_cov_tb.sv`
- `output/family_readiness/*_gpu_toggle_readiness.md`

出力:

- `work/campaign_post_openpiton_axes.json`

読み方:

- accepted `OpenPiton` 後の next family branch を返す
- current checked-in state では `status=decide_open_next_family_after_openpiton_acceptance`
- recommended family は `BlackParrot`
- fallback family は blocked `XiangShan`

## 3.17a `audit_campaign_xiangshan_debug_tactics.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xiangshan_debug_tactics.py
```

主入力:

- `work/campaign_xiangshan_first_surface_status.json`
- `work/campaign_vortex_first_surface_profiles.json`
- optional: `work/xiangshan_ptxas_probe.json`

出力:

- `work/campaign_xiangshan_debug_tactics.json`

読み方:

- current reopened XiangShan branch の next concrete tactic を返す
- current checked-in state では `status=follow_post_vortex_axes_after_accepting_vortex`
- current recommendation は historical に `open_the_next_post_vortex_family`
- current main line は `work/campaign_caliptra_first_surface_status.json` で読む
- Vortex accepted 後は XiangShan/Vortex reopen arbitration 自体が main line ではない

## 3.18 `audit_campaign_vortex_first_surface_status.py`

コマンド:

```bash
python3 src/tools/audit_campaign_vortex_first_surface_status.py
```

主入力:

- `work/campaign_post_blackparrot_axes.json`
- `work/vortex_gpu_cov_stock_verilator_cc_bootstrap.json`
- `output/validation/vortex_cpu_baseline_validation.json`
- optional: `work/vl_ir_exp/vortex_gpu_cov_vl/vl_batch_gpu.meta.json`
- optional: `work/vortex_build_vl_gpu.log`

出力:

- `work/campaign_vortex_first_surface_status.json`

読み方:

- `BlackParrot` baseline loss 後に開いた `Vortex` first surface の branch status を返す
- current checked-in state では `status=ready_to_finish_vortex_first_trio`
- bootstrap と CPU baseline は `ok`
- current line では GPU build recovered を優先し、old failure log より checked-in `meta` を重く見る
- default gate policy はこの artifact ではなく `campaign_vortex_first_surface_step.json` で読む

## 3.19 `audit_campaign_vortex_first_surface_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_vortex_first_surface_gate.py
```

主入力:

- `work/campaign_vortex_first_surface_status.json`
- `work/campaign_post_blackparrot_axes.json`
- `work/campaign_xiangshan_first_surface_status.json`
- `config/campaign_vortex_first_surface/selection.json`

出力:

- `work/campaign_vortex_first_surface_gate.json`

読み方:

- current checked-in Vortex branch profile の active outcome を返す
- current checked-in state では `status=vortex_gpu_build_recovered_ready_to_finish_trio`
- current selected profile は `debug_vortex_tls_lowering`
- ready alternative は `reopen_xiangshan_fallback_family`

## 3.20 `audit_campaign_vortex_first_surface_profiles.py`

コマンド:

```bash
python3 src/tools/audit_campaign_vortex_first_surface_profiles.py
```

主入力:

- `work/campaign_vortex_first_surface_status.json`
- `work/campaign_post_blackparrot_axes.json`
- `work/campaign_xiangshan_first_surface_status.json`
- `config/campaign_vortex_first_surface/profiles/*.json`
- `config/campaign_vortex_first_surface/selection.json`

出力:

- `work/campaign_vortex_first_surface_profiles.json`

読み方:

- named Vortex branch profile を current selection と independent に比較する
- current checked-in state では current=`debug_vortex_tls_lowering`
- current checked-in recommendation も `debug_vortex_tls_lowering`
- ready alternative profile は `reopen_xiangshan_fallback_family`

## 3.20a `audit_campaign_vortex_first_surface_policy_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_vortex_first_surface_policy_gate.py
```

主入力:

- `work/campaign_vortex_first_surface_step.json`
- `config/campaign_vortex_first_surface_policy/selection.json`

出力:

- `work/campaign_vortex_first_surface_policy_gate.json`

読み方:

- Vortex first surface の current policy profile を step summary に照合する
- current checked-in state では `status=candidate_only_ready`
- current selected profile は `vortex_candidate_only_threshold4`
- current policy line は `threshold=4` candidate-only hybrid win

## 3.20b `audit_campaign_vortex_first_surface_acceptance_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_vortex_first_surface_acceptance_gate.py
```

主入力:

- `work/campaign_vortex_first_surface_gate.json`
- `work/campaign_vortex_first_surface_policy_gate.json`
- `config/campaign_vortex_first_surface_acceptance/selection.json`

出力:

- `work/campaign_vortex_first_surface_acceptance_gate.json`

読み方:

- selected Vortex policy line を checked-in breadth evidence として受け入れる acceptance artifact
- current checked-in state では `status=accepted_selected_vortex_first_surface_step`
- next action は `decide_post_vortex_family_axes_after_accepting_vortex`

## 3.20c `audit_campaign_post_vortex_axes.py`

コマンド:

```bash
python3 src/tools/audit_campaign_post_vortex_axes.py
```

主入力:

- `work/campaign_vortex_first_surface_acceptance_gate.json`
- `third_party/rtlmeter/designs/*/*_gpu_cov_tb.sv`
- `src/runners`
- `output/family_readiness`

出力:

- `work/campaign_post_vortex_axes.json`

読み方:

- accepted `Vortex` 後の next family axis を inventory から返す
- current checked-in state では `status=decide_open_next_family_after_vortex_acceptance`
- current recommendation は `Caliptra` first、fallback は `Example`

## 3.20d `audit_campaign_caliptra_first_surface_status.py`

コマンド:

```bash
python3 src/tools/audit_campaign_caliptra_first_surface_status.py
```

主入力:

- `work/campaign_post_vortex_axes.json`
- `work/caliptra_gpu_cov_stock_verilator_cc_bootstrap.json`
- `output/validation/caliptra_cpu_baseline_validation.json`
- optional: `output/validation/caliptra_stock_hybrid_validation.json`
- optional: `work/caliptra_build_vl_gpu.log`

出力:

- `work/campaign_caliptra_first_surface_status.json`

読み方:

- accepted `Vortex` 後に開いた `Caliptra` first surface の current branch status を返す
- current checked-in state では `status=decide_caliptra_tls_lowering_debug_vs_open_example_fallback`
- bootstrap と CPU baseline は `ok`
- current blocker は runtime ではなく、`llc` の `GlobalTLSAddress<... @_ZN9Verilated3t_sE>` TLS lowering failure
- fallback family は `Example`

## 3.20e `audit_campaign_caliptra_debug_tactics.py`

コマンド:

```bash
python3 src/tools/audit_campaign_caliptra_debug_tactics.py
```

主入力:

- `work/campaign_caliptra_first_surface_status.json`
- `work/vl_ir_exp/caliptra_gpu_cov_vl/vl_batch_gpu_caliptra_tls_bypass.ll`
- optional: `work/vl_ir_exp/caliptra_gpu_cov_vl/vl_batch_gpu.ptx`
- optional: `work/vl_ir_exp/caliptra_gpu_cov_vl/vl_batch_gpu.cubin`
- optional: `work/caliptra_ptxas_compile_only_probe.json`
- optional: `work/caliptra_ptxas_timeout_probe.json`
- optional: `work/caliptra_ptxas_compile_only_probe.o`
- optional: `work/vl_ir_exp/caliptra_gpu_cov_vl/vl_batch_gpu_caliptra_tls_bypass_trial.ptx`
- optional: `work/caliptra_tls_bypass_trial_ptxas.log`

出力:

- `work/campaign_caliptra_debug_tactics.json`
- `work/caliptra_stack_limit_probe.json`
- `work/caliptra_nvcc_device_link_cubin_probe.json`
- `work/caliptra_nvcc_device_link_fatbin_probe.json`
- `work/caliptra_split_phase_probe/vl_kernel_manifest.json`
- `work/caliptra_split_phase_probe/vl_batch_gpu_split_compile_only_probe.json`
- `work/caliptra_split_phase_probe/split_ptx_smoke_trace.log`
- `work/caliptra_split_phase_probe/vl_batch_gpu_split_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_nvcc_device_link_probe.json`
- `work/caliptra_split_phase_probe/split_cubin_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_trace.log`
- `work/caliptra_split_phase_probe/vl_batch_gpu_split_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_nvcc_device_link_probe.json`
- `work/caliptra_split_phase_probe/split_cubin_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_trace.log`
- `work/caliptra_split_phase_probe/vl_batch_gpu_split_nba_comb_m_axi_if0_b64_synth16_ret_only_nvcc_device_link_probe.json`
- `work/caliptra_split_phase_probe/split_cubin_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_trace.log`
- `work/caliptra_split_phase_probe/vl_batch_gpu_split_nvcc_device_link_probe.json`
- `work/caliptra_split_phase_probe/split_cubin_smoke_trace.log`
- `work/caliptra_split_phase_probe/split_cubin_ico_smoke_trace.log`
- `work/caliptra_split_phase_probe/split_cubin_nba_comb_smoke_trace.log`
- `work/caliptra_split_phase_probe/split_cubin_nba_comb_block1_smoke_trace.log`
- `work/caliptra_split_phase_probe/split_cubin_nba_comb_block8_smoke_trace.log`
- `work/caliptra_split_phase_probe/split_cubin_nba_sequent_smoke_trace.log`

読み方:

- checked-in Caliptra line の next concrete tactic を返す
- current checked-in state では
  `status=ready_for_deeper_caliptra_split_m_axi_if0_first_store_compilable_branch1_load_provenance_nonconstant_loaded_byte_dependent_store_source_bits_runtime_fault_debug`
- current main line は `deeper_caliptra_split_m_axi_if0_first_store_compilable_branch1_load_provenance_nonconstant_loaded_byte_dependent_store_source_bits_runtime_fault_debug`
- 補助観測として `first_store_masked_data_dead_mask_const1_ret_trunc`, `first_store_masked_data_predicated01_ret_trunc`, `first_store_masked_data_force_else_ret_trunc`, `first_store_masked_data_mask1_ret_trunc`, `first_store_masked_data_mask1_shl8_ret_trunc`, `first_store_masked_data_selp_const1_ret_trunc`, `first_store_masked_data_selp_same_const1_ret_trunc`, `first_store_branch1_predicated10_ret_trunc`, `first_store_branch1_load_dead_mask_zero_ret_trunc`, `first_store_branch1_load_mask1_shr8_ret_trunc`, `first_store_branch1_load_mask1_shl1_ret_trunc`, `first_store_branch1_load_mask1_shl4_ret_trunc`, `first_store_branch1_load_mask1_shl6_ret_trunc`, `first_store_branch1_load_mask1_shl7_ret_trunc`, `first_store_branch1_load_mask1_shl9_ret_trunc`, `first_store_branch1_load_mask1_shl8_and255_ret_trunc`, `first_store_branch1_selp_const2_ret_trunc`, `first_store_branch1_selp_const3_ret_trunc`, `first_store_branch1_selp_const129_ret_trunc`, `first_store_branch1_selp_const257_ret_trunc`, `first_store_branch1_selp_const1_and255_ret_trunc`, `first_store_branch1_selp_const513_ret_trunc`, `first_store_branch1_selp_const0_ret_trunc`, `first_store_branch1_selp_same_const257_ret_trunc`, `first_store_branch1_load_mask2_ret_trunc`, `first_store_branch1_load_maskff_ret_trunc`, `first_store_branch1_load_mask3_ret_trunc`, `first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc`, `first_store_branch1_load_mask1_sep_reg_ret_trunc`, `first_store_branch1_load_xor_self_zero_ret_trunc`, `first_store_self_load_ret_trunc`, `first_store_branch1_load_store_plus1_ret_trunc`, `first_store_branch1_load_mask1_or1_ret_trunc`, `first_store_branch1_load_mov_ret_trunc`, `first_store_branch1_alt_load_ret_trunc` はいずれも compile timeout で、actionable repro line は compilable current-branch1-load-provenance nonconstant variants に限られる
- fallback family は `Example`
- `work/caliptra_stack_limit_probe.json` は `run_vl_hybrid` の stack-limit probe artifact で、
  current checked-in state では `max_accepted_stack_limit=523712`、
  `min_rejected_stack_limit_target=523744`、`launch_at_max_result.status=invalid_argument`
- `work/caliptra_nvcc_device_link_cubin_probe.json` / `work/caliptra_nvcc_device_link_fatbin_probe.json` は
  cheap `nvcc --device-c` packaging probe artifact で、
  current checked-in state ではどちらも compile step が `timed_out`、link は `skipped`
- `work/caliptra_split_phase_probe/vl_kernel_manifest.json` は split launch sequence
  `vl_ico_batch_gpu -> vl_nba_comb_batch_gpu -> vl_nba_sequent_batch_gpu` を固定する
- `work/caliptra_split_phase_probe/vl_batch_gpu_split_compile_only_probe.json` は split compile-only probe artifact で、
  current checked-in state では `status=ok`、split entry kernels は `0 bytes stack frame`
- `work/caliptra_split_phase_probe/split_ptx_smoke_trace.log` は split PTX smoke artifact で、
  current checked-in state では traced run が `before_cuModuleLoad` まで進む
- `work/caliptra_split_phase_probe/vl_batch_gpu_split_nvcc_device_link_probe.json` は split PTX の
  official `nvcc --device-c -> --device-link --cubin` probe artifact で、
  current checked-in state では compile/link とも `ok`、linked cubin と split entry symbols を保持する
- `work/caliptra_split_phase_probe/split_cubin_smoke_trace.log` は split linked-cubin smoke artifact で、
  current checked-in state では traced run が `after_first_kernel_launch` まで進み、その後 `illegal_memory_access`
- `work/caliptra_split_phase_probe/split_cubin_ico_smoke_trace.log` と
  `work/caliptra_split_phase_probe/split_cubin_nba_sequent_smoke_trace.log` は
  split `ico` / `nba_sequent` single-kernel smoke artifact で、
  current checked-in state ではどちらも `ok`
- `work/caliptra_split_phase_probe/split_cubin_nba_comb_smoke_trace.log`,
  `work/caliptra_split_phase_probe/split_cubin_nba_comb_block1_smoke_trace.log`,
  `work/caliptra_split_phase_probe/split_cubin_nba_comb_block8_smoke_trace.log` は
  split `nba_comb` single-kernel smoke artifact で、
  current checked-in state では culprit が `nba_comb` であり、small block sizes でも failure が残る

## 3.21 `audit_campaign_vortex_debug_tactics.py`

コマンド:

```bash
python3 src/tools/audit_campaign_vortex_debug_tactics.py
```

主入力:

- `work/campaign_vortex_first_surface_status.json`
- `work/campaign_vortex_first_surface_gate.json`
- optional: `work/campaign_vortex_deeper_debug_status.json`
- optional: `work/vortex_build_o0.log`
- optional: `work/vortex_build_o1.log`

出力:

- `work/campaign_vortex_debug_tactics.json`

読み方:

- checked-in `Vortex` debug branch の下で next concrete tactic を返す
- current checked-in state では `status=vortex_first_surface_already_accepted`
- current recommendation は `decide_post_vortex_family_axes_after_accepting_vortex`
- accepted 後は heavier fallback は使わず、main line は `post-Vortex axes`

## 3.21a `audit_campaign_vortex_deeper_debug_status.py`

コマンド:

```bash
python3 src/tools/audit_campaign_vortex_deeper_debug_status.py
```

主入力:

- `work/campaign_xiangshan_first_surface_acceptance_gate.json`
- `work/campaign_vortex_first_surface_status.json`
- `work/vl_ir_exp/vortex_gpu_cov_vl/vl_batch_gpu_vortex_tls_bypass.ptx`
- `work/vortex_tls_bypass_ptxas.log`
- optional: `work/vl_ir_exp/vortex_gpu_cov_vl/vl_classifier_report.json`

出力:

- `work/campaign_vortex_deeper_debug_status.json`

読み方:

- XiangShan accepted 後の deeper Vortex line を 1 枚に圧縮する
- current checked-in state では `status=ready_for_vortex_dpi_wrapper_abi_debug`
- temporary TLS-slot bypass で `llc` は抜け、`vl_eval_batch_gpu` entry も PTX 上に残る
- その次の blocker は `ptxas` の `mem_access` `__Vdpiimwrap_*` formal-parameter ABI mismatch
- classifier report 上でも当該 wrapper は `placement=gpu`, `reason=gpu_reachable`
- current recommendation は `deeper_vortex_dpi_wrapper_abi_debug`
- heavier fallback は `deeper_vortex_tls_lowering_debug`

## 3.22 `audit_campaign_xiangshan_vortex_branch_resolution.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xiangshan_vortex_branch_resolution.py
```

主入力:

- `work/campaign_vortex_first_surface_gate.json`
- `work/campaign_xiangshan_first_surface_status.json`
- `work/campaign_xiangshan_debug_tactics.json`
- `work/campaign_vortex_debug_tactics.json`

出力:

- `work/campaign_xiangshan_vortex_branch_resolution.json`

読み方:

- XiangShan と Vortex が互いに相手 branch を reopen し続ける loop を 1 本の stable tactic に圧縮する
- current checked-in state では `status=follow_post_vortex_axes_after_accepting_vortex`
- current checked-in branch は `debug_vortex_tls_lowering`
- current recommendation は historical に `open_the_next_post_vortex_family`
- current main line は `work/campaign_caliptra_first_surface_status.json` で読む
- accepted `Vortex` 後は cross-branch fallback 自体が inactive になる

## 3.23 `audit_campaign_xiangshan_deeper_debug_status.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xiangshan_deeper_debug_status.py
```

主入力:

- `work/campaign_xiangshan_vortex_branch_resolution.json`
- `work/xiangshan_ptxas_probe.json`
- `work/xiangshan_ptxas_compile_only_probe.json`
- `work/xiangshan_compile_only_smoke_trace.log`
- `work/xiangshan_nvlink_smoke_trace.log`
- `work/xiangshan_fatbin_smoke_trace.log`
- `work/xiangshan_nvcc_dlink_smoke_trace.log`
- `work/xiangshan_fatbinary_device_c_probe.fatbin`
- `work/xiangshan_fatbinary_device_c_link_probe.fatbin`
- `work/xiangshan_fatbinary_device_c_probe_smoke_trace.log`
- `work/xiangshan_fatbinary_device_c_link_probe_smoke_trace.log`
- `work/xiangshan_nvcc_device_link_probe.json`
- `work/xiangshan_nvcc_device_link_from_ptx_smoke_trace.log`
- cheap symbol inspection via `cuobjdump --dump-elf-symbols`

出力:

- `work/campaign_xiangshan_deeper_debug_status.json`

読み方:

- XiangShan deeper cubin-first / packaging line を 1 枚に圧縮する
- current checked-in state では `status=ready_to_finish_xiangshan_first_trio`
- cheap `ptxas` line は negative artifact のままだが、official `nvcc --device-c PTX -> --device-link --cubin`
  line は linked cubin を復旧し、minimal smoke も `ok`
- `ptxas --compile-only` は成功し、relocatable object には `vl_eval_batch_gpu` が残る
- `fatbinary --device-c` packaged variants でも `vl_eval_batch_gpu` は残るが、`cuModuleGetFunction` で `device kernel image is invalid` になる
- `nvlink` / `nvcc -dlink` の linked executable outputs は tiny で symbol-less (`760B` / `840B`)
- PTX fatbin JIT probe も `before_cuModuleLoad` で stall し、bounded run では timeout する
- current recommendation は `finish_xiangshan_stock_hybrid_validation_and_compare_gate_policy`
- heavier fallback は `deeper_vortex_tls_lowering_debug`

## 3.24 `audit_campaign_xiangshan_first_surface_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xiangshan_first_surface_gate.py
```

主入力:

- `work/campaign_xiangshan_first_surface_step.json`
- `config/campaign_xiangshan_first_surface/selection.json`
- `config/campaign_xiangshan_first_surface/profiles/*.json`

出力:

- `work/campaign_xiangshan_first_surface_gate.json`

読み方:

- XiangShan first surface の current checked-in profile を current policy step に照合する
- current checked-in state では selection は `xiangshan_candidate_only_threshold2`
- current checked-in gate は `status=candidate_only_ready`
- つまり `threshold=2` candidate-only line は checked-in profile として成立している

## 3.25 `set_campaign_xiangshan_first_surface.py`

コマンド:

```bash
python3 src/tools/set_campaign_xiangshan_first_surface.py \
  --profile-name xiangshan_candidate_only_threshold2
```

主入力:

- `config/campaign_xiangshan_first_surface/profiles/*.json`
- `work/campaign_xiangshan_first_surface_step.json`

主出力:

- `config/campaign_xiangshan_first_surface/selection.json`
- `work/campaign_xiangshan_first_surface_gate.json`

役割:

- named XiangShan first-surface profile を current selection に適用して active gate を再生成する

## 3.26 `audit_campaign_xiangshan_first_surface_acceptance_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_xiangshan_first_surface_acceptance_gate.py
```

主入力:

- `work/campaign_vortex_first_surface_gate.json`
- `work/campaign_xiangshan_first_surface_gate.json`
- `config/campaign_xiangshan_first_surface_acceptance/selection.json`
- `config/campaign_xiangshan_first_surface_acceptance/profiles/*.json`

出力:

- `work/campaign_xiangshan_first_surface_acceptance_gate.json`

読み方:

- reopened XiangShan fallback branch の accepted state を返す
- current checked-in state では `status=accepted_selected_xiangshan_first_surface_step`
- current next action は `reopen_vortex_tls_lowering_debug_after_accepting_xiangshan`

## 3.27 `set_campaign_xiangshan_first_surface_acceptance.py`

コマンド:

```bash
python3 src/tools/set_campaign_xiangshan_first_surface_acceptance.py \
  --profile-name accept_selected_xiangshan_first_surface_step
```

主入力:

- `config/campaign_xiangshan_first_surface_acceptance/profiles/*.json`
- `work/campaign_vortex_first_surface_gate.json`
- `work/campaign_xiangshan_first_surface_gate.json`

主出力:

- `config/campaign_xiangshan_first_surface_acceptance/selection.json`
- `work/campaign_xiangshan_first_surface_acceptance_gate.json`

役割:

- named XiangShan first-surface acceptance profile を current selection に適用して active acceptance gate を再生成する

## 4. low-level GPU runner の入出力

### 4.1 `run_vl_hybrid.py`

コマンド:

```bash
python3 src/tools/run_vl_hybrid.py --mdir <mdir> [--steps S] [--patch off:byte ...]
python3 src/tools/run_vl_hybrid.py --mdir <mdir> --init-state init.bin --dump-state out.bin
```

主入力:

- `<mdir>/vl_batch_gpu.cubin`
- `<mdir>/vl_batch_gpu.meta.json`
- optional: `--init-state <bin>`
- optional: `--patch global_off:byte`

主出力:

- stdout の timing / shape summary
- optional: `--dump-state <bin>`

注意:

- `run_vl_hybrid.py` 自体は stable JSON を出さない
- stable な読み口が必要なら `src/runners/run_*_stock_hybrid_validation.py` を使う

## 5. supported `socket_m1` flow の入出力

### 5.1 `run_socket_m1_host_probe.py`

コマンド:

```bash
python3 src/tools/run_socket_m1_host_probe.py --mdir work/vl_ir_exp/socket_m1_vl
```

主入力:

- `work/vl_ir_exp/socket_m1_vl`

主出力:

- `<mdir>/socket_m1_host_probe_report.json`
- optional: `<mdir>/socket_m1_host_init_state.bin`
- `<mdir>/socket_m1_host_probe` binary

### 5.2 `run_socket_m1_host_gpu_flow.py`

コマンド:

```bash
python3 src/tools/run_socket_m1_host_gpu_flow.py --mdir work/vl_ir_exp/socket_m1_vl
```

主入力:

- `socket_m1_host_probe_report.json`
- `socket_m1_host_init_state.bin`
- `vl_batch_gpu.cubin`
- `vl_batch_gpu.meta.json`

主出力:

- `<mdir>/socket_m1_host_gpu_flow_summary.json`
- `<mdir>/socket_m1_gpu_final_state.bin`

### 5.3 `run_socket_m1_stock_hybrid_validation.py`

コマンド:

```bash
python3 src/runners/run_socket_m1_stock_hybrid_validation.py --mdir work/vl_ir_exp/socket_m1_vl
```

主入力:

- `socket_m1` host->GPU flow 一式

主出力:

- `output/validation/socket_m1_stock_hybrid_validation.json`

これは current supported source of truth。

必須 field:

- `toggle_coverage`
- `campaign_threshold`
- `campaign_measurement`
- `performance`
- `artifacts.classifier_report`

## 6. `socket_m1` campaign comparison の入出力

この節は current milestone の minimum-goal source of truth ではないが、
checked-in campaign artifact を整理する。

### 6.1 `run_socket_m1_cpu_baseline_validation.py`

コマンド:

```bash
python3 src/runners/run_socket_m1_cpu_baseline_validation.py --mdir work/vl_ir_exp/socket_m1_vl
```

主入力:

- `work/vl_ir_exp/socket_m1_vl`
- `socket_m1` stock-Verilator generated closure
- fixed `campaign_threshold`

主出力:

- `output/validation/socket_m1_cpu_baseline_validation.json`

必須 field:

- `campaign_threshold`
- `campaign_measurement`
- `coverage`
- `performance`
- `commands.flow`

### 6.2 `run_socket_m1_time_to_threshold_comparison.py`

コマンド:

```bash
python3 src/runners/run_socket_m1_time_to_threshold_comparison.py \
  --baseline output/validation/socket_m1_cpu_baseline_validation.json \
  --hybrid output/validation/socket_m1_stock_hybrid_validation.json
```

主入力:

- `output/validation/socket_m1_cpu_baseline_validation.json`
- `output/validation/socket_m1_stock_hybrid_validation.json`

主出力:

- `output/validation/socket_m1_time_to_threshold_comparison.json`

必須 field:

- `campaign_threshold`
- `baseline.campaign_measurement`
- `hybrid.campaign_measurement`
- `comparison_ready`
- `speedup_ratio`
- `winner`

schema contract:

- [socket_m1_campaign_schema_packet.md](socket_m1_campaign_schema_packet.md)

proof semantics:

- [socket_m1_campaign_proof_matrix.md](socket_m1_campaign_proof_matrix.md)

execution order:

- [socket_m1_time_to_threshold_execution_packet.md](socket_m1_time_to_threshold_execution_packet.md)

### 6.3 `run_tlul_fifo_sync_cpu_baseline_validation.py`

コマンド:

```bash
python3 src/runners/run_tlul_fifo_sync_cpu_baseline_validation.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl
```

主入力:

- `work/vl_ir_exp/tlul_fifo_sync_host_vl`
- `config/slice_launch_templates/tlul_fifo_sync.json`
- host-owned clock sequence (`1,0` by default)

主出力:

- `output/validation/tlul_fifo_sync_cpu_baseline_validation.json`
- `work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_cpu_baseline_host_report.json`

必須 field:

- `campaign_threshold`
- `campaign_measurement`
- `coverage`
- `performance`
- `commands.flow`

### 6.4 `run_tlul_fifo_sync_time_to_threshold_comparison.py`

コマンド:

```bash
python3 src/runners/run_tlul_fifo_sync_time_to_threshold_comparison.py \
  --baseline output/validation/tlul_fifo_sync_cpu_baseline_validation.json \
  --hybrid output/validation/tlul_fifo_sync_stock_hybrid_validation.json
```

主入力:

- `output/validation/tlul_fifo_sync_cpu_baseline_validation.json`
- `output/validation/tlul_fifo_sync_stock_hybrid_validation.json`

主出力:

- `output/validation/tlul_fifo_sync_time_to_threshold_comparison.json`

必須 field:

- `campaign_threshold`
- `baseline.campaign_measurement`
- `hybrid.campaign_measurement`
- `comparison_ready`
- `speedup_ratio`
- `winner`

読み方:

- current checked-in result は `winner=hybrid`, `speedup_ratio≈1.16`
- second campaign surface はできたが、まだ `thin_top_reference_design` 上の v1 比較なので
  次の論点は「threshold を強くするか」「design 数を増やすか」である

### 6.5 `audit_campaign_speed_scoreboard.py`

コマンド:

```bash
python3 src/tools/audit_campaign_speed_scoreboard.py \
  --json-out work/campaign_speed_scoreboard.json
```

主入力:

- `output/validation/*_time_to_threshold_comparison.json`

主出力:

- `work/campaign_speed_scoreboard.json`

必須 field:

- `rows[*].target`
- `rows[*].winner`
- `rows[*].speedup_ratio`
- `summary.comparison_ready_count`
- `summary.hybrid_win_count`
- `summary.all_thresholds_match`

### 6.6 `audit_campaign_next_kpi.py`

コマンド:

```bash
python3 src/tools/audit_campaign_next_kpi.py \
  --scoreboard work/campaign_speed_scoreboard.json \
  --json-out work/campaign_next_kpi_audit.json
```

または policy-aware active line を読む場合:

```bash
python3 src/tools/audit_campaign_next_kpi.py \
  --policy-gate work/campaign_threshold_policy_gate.json \
  --json-out work/campaign_next_kpi_active.json
```

主入力:

- `work/campaign_speed_scoreboard.json`
- optional: `work/campaign_threshold_policy_gate.json`

主出力:

- `work/campaign_next_kpi_audit.json`
- optional: `work/campaign_next_kpi_active.json`

必須 field:

- `decision.recommended_next_kpi`
- `decision.reason`
- `policy.minimum_ready_surfaces`
- `policy.minimum_strong_margin`

読み方:

- `work/campaign_next_kpi_audit.json` 自体は threshold 強化を検討していた時点の historical recommendation
- current checked-in recommendation は `--policy-gate` 経由で作る `work/campaign_next_kpi_active.json` の
  `recommended_next_kpi=broader_design_count`
- `*_threshold5.json` candidate 群を `--glob '*_time_to_threshold_comparison_threshold5.json'` で集計しても、
  weakest hybrid win は `tlul_fifo_sync` の `speedup_ratio≈1.20` に留まり、
  next-KPI recommendation は still `stronger_thresholds`
- `--policy-gate` を使うと、current checked-in selection が選んだ active comparison set に対する next-KPI recommendation を返す

### 6.7 `audit_campaign_threshold_candidates.py`

コマンド:

```bash
python3 src/tools/audit_campaign_threshold_candidates.py \
  --json-out work/campaign_threshold_candidate_matrix.json
```

入力:

- `work/campaign_speed_scoreboard.json`
- `work/campaign_speed_scoreboard_threshold5.json`

出力:

- `work/campaign_threshold_candidate_matrix.json`

読み方:

- first scoreboard is treated as the current checked-in threshold line
- later scoreboards are treated as promotion candidates
- current result は `threshold5` を `candidate_only` と判定し、
  `summary.recommended_action=keep_current_threshold_and_define_stronger_candidate`

### 6.8 `campaign_threshold_headroom_experiments.json`

生成物:

- `work/campaign_threshold_headroom_experiments.json`

読み方:

- `socket_m1` は `threshold=5` で plateau し、`threshold=6` は unresolved
- `tlul_fifo_sync` は `threshold=24` まで still `winner=hybrid` だが margin は weak
- `threshold=25` は unresolved
- 結論として、次の v2 は raw `bits_hit` cutoff の単純増加ではなく、
  weakest surface の time-to-threshold を変える semantics が必要

### 6.9 `audit_tlul_fifo_sync_threshold_semantics.py`

コマンド:

```bash
python3 src/tools/audit_tlul_fifo_sync_threshold_semantics.py \
  --json-out work/tlul_fifo_sync_threshold_semantics_audit.json
```

入力:

- `output/validation/tlul_fifo_sync_time_to_threshold_comparison_seq1_threshold24.json`
- `output/validation/tlul_fifo_sync_time_to_threshold_comparison_threshold24.json`
- `output/validation/tlul_fifo_sync_time_to_threshold_comparison_seq101_threshold24.json`
- `output/validation/tlul_fifo_sync_time_to_threshold_comparison_seq1010_threshold24.json`

出力:

- `work/tlul_fifo_sync_threshold_semantics_audit.json`

読み方:

- `seq1` は current strongest positive case (`winner=hybrid`, `speedup_ratio≈2.64`)
- checked-in `1,0` replay depth は still `winner=hybrid`
- `1,0,1` へ伸ばすと already `winner=baseline`
- `1,0,1,0` ではさらに baseline 優位が強くなる
- したがって `tlul_fifo_sync` の stronger threshold は、
  host replay sequence を単純に長くする semantics では定義しない。
  次の候補は、minimal-progress sequence (`1`) を design-specific semantics として扱うかどうかである

### 6.10 `audit_campaign_threshold_policy_options.py`

コマンド:

```bash
python3 src/tools/audit_campaign_threshold_policy_options.py \
  --config config/campaign_threshold_policies/index.json \
  --json-out work/campaign_threshold_policy_options.json
```

入力:

- `config/campaign_threshold_policies/index.json`
- `output/validation/socket_m1_time_to_threshold_comparison.json`
- `output/validation/tlul_fifo_sync_time_to_threshold_comparison.json`
- `output/validation/socket_m1_time_to_threshold_comparison_threshold5.json`
- `output/validation/tlul_fifo_sync_time_to_threshold_comparison_threshold5.json`
- `output/validation/tlul_fifo_sync_time_to_threshold_comparison_seq1_threshold24.json`

出力:

- `work/campaign_threshold_policy_options.json`

読み方:

- scenario definition 自体の source of truth は `config/campaign_threshold_policies/index.json`
- `checked_in_common_v1`: current checked-in common threshold line
- `candidate_common_threshold5`: stronger common raw-bits candidate
- `candidate_design_specific_minimal_progress`: `socket_m1 threshold5` + `tlul_fifo_sync seq1 threshold24`
- current decision は、common candidate がまだ weak で design-specific candidate は strong なので、
  campaign v2 で design-specific semantics を許すかを先に決めること

### 6.11 `audit_campaign_threshold_policy_gate.py`

コマンド:

```bash
python3 src/tools/audit_campaign_threshold_policy_gate.py \
  --policy-options-json work/campaign_threshold_policy_options.json \
  --selection-config config/campaign_threshold_policies/selection.json \
  --json-out work/campaign_threshold_policy_gate.json
```

入力:

- `work/campaign_threshold_policy_options.json`
- `config/campaign_threshold_policies/selection.json`

出力:

- `work/campaign_threshold_policy_gate.json`

読み方:

- `policy_options` は候補比較、`policy_gate` は current checked-in gate
- `selection.profile_name` は checked-in policy を fixed name で指す
- `selection.allow_per_target_thresholds=false` なら design-specific candidate が strong でも active policy は common v1 を維持する
- `selection.allow_per_target_thresholds=true` に変えたときだけ、
  design-specific candidate が strong なら `promote_design_specific_v2` に進める
- `selection.require_matching_thresholds=true` は active next-KPI 側で `all_thresholds_match` を hard requirement に残す

### 6.12 `audit_campaign_active_scoreboard.py`

コマンド:

```bash
python3 src/tools/audit_campaign_active_scoreboard.py \
  --policy-gate work/campaign_threshold_policy_gate.json \
  --json-out work/campaign_speed_scoreboard_active.json
```

入力:

- `work/campaign_threshold_policy_gate.json`

出力:

- `work/campaign_speed_scoreboard_active.json`

読み方:

- `policy_gate` が選んだ `selected_paths` だけを集計した policy-aware scoreboard
- current checked-in selection では common v1 の 2 surface を集計する
- `selection.json` を切り替えると active scoreboard も同じ policy に追従する

### 6.13 `audit_campaign_threshold_policy_preview.py`

コマンド:

```bash
python3 src/tools/audit_campaign_threshold_policy_preview.py \
  --policy-options-json work/campaign_threshold_policy_options.json \
  --selection-config config/campaign_threshold_policies/selection.json \
  --json-out work/campaign_threshold_policy_preview.json
```

入力:

- `work/campaign_threshold_policy_options.json`
- `config/campaign_threshold_policies/selection.json`

出力:

- `work/campaign_threshold_policy_preview.json`

読み方:

- current selection と 2 軸 policy matrix を並べる差分 artifact
- current checked-in selection (`allow_per_target_thresholds=true`, `require_matching_thresholds=false`) では design-specific v2 / `broader_design_count`
- allow/matching を戻す hypothetical variant では common v1 / `stronger_thresholds` に落ちる
- current policy を維持するか戻すかの差分を読む artifact

### 6.14 `audit_campaign_policy_decision_readiness.py`

コマンド:

```bash
python3 src/tools/audit_campaign_policy_decision_readiness.py \
  --preview-json work/campaign_threshold_policy_preview.json \
  --json-out work/campaign_policy_decision_readiness.json
```

入力:

- `work/campaign_threshold_policy_preview.json`

出力:

- `work/campaign_policy_decision_readiness.json`

読み方:

- current checked-in branch / blocked branch / ready branch を 1 枚に圧縮した artifact
- 現在は policy decision が完了しており、current branch は design-specific v2 のまま active
- `summary.recommended_active_task` は policy-switch 時点の残タスクを返す historical field として読む
- policy を戻した場合の branch は current line を narrow する fallback として読む

### 6.15 `audit_campaign_policy_change_impact.py`

コマンド:

```bash
python3 src/tools/audit_campaign_policy_change_impact.py \
  --preview-json work/campaign_threshold_policy_preview.json \
  --from-variant current_selection \
  --to-variant flip_both \
  --json-out work/campaign_policy_change_impact.json
```

入力:

- `work/campaign_threshold_policy_preview.json`

出力:

- `work/campaign_policy_change_impact.json`

読み方:

- current checked-in line と alternative policy branch の before/after diff artifact
- `policy_changes` にどの switch を変えるかが出る
- `delta` に selected scenario / next-KPI / threshold set / selected path の変化が出る
- 現在は policy reversion が design count をどう縮めるかを読む artifact

### 6.16 `audit_campaign_threshold_policy_profiles.py`

コマンド:

```bash
python3 src/tools/audit_campaign_threshold_policy_profiles.py \
  --policy-options-json work/campaign_threshold_policy_options.json \
  --profiles-dir config/campaign_threshold_policies/profiles \
  --json-out work/campaign_threshold_policy_profiles.json
```

入力:

- `work/campaign_threshold_policy_options.json`
- `config/campaign_threshold_policies/profiles/*.json`

出力:

- `work/campaign_threshold_policy_profiles.json`

読み方:

- `flip_*` のような相対名ではなく named profile を固定名で比較する artifact
- `summary.current_profile_name` が current checked-in line を返す
- `per_target_blocked` は per-target を許すが threshold-schema mismatch で blocked な branch
- `per_target_ready` は design-specific v2 を check-in したときの first ready branch

### 6.17 `set_campaign_threshold_policy.py`

コマンド:

```bash
python3 src/tools/set_campaign_threshold_policy.py \
  --profile-name per_target_ready \
  --profiles-dir config/campaign_threshold_policies/profiles \
  --policy-options-json work/campaign_threshold_policy_options.json \
  --selection-config config/campaign_threshold_policies/selection.json \
  --gate-json-out work/campaign_threshold_policy_gate.json \
  --scoreboard-json-out work/campaign_speed_scoreboard_active.json \
  --next-kpi-json-out work/campaign_next_kpi_active.json
```

入力:

- `config/campaign_threshold_policies/profiles/<profile>.json`
- `work/campaign_threshold_policy_options.json`

出力:

- `config/campaign_threshold_policies/selection.json`
- `work/campaign_threshold_policy_gate.json`
- `work/campaign_speed_scoreboard_active.json`
- `work/campaign_next_kpi_active.json`

読み方:

- named profile を checked-in selection に反映する operational tool
- `per_target_ready` を再適用すれば current line の artifacts を再生成できる
- `common_v1_hold` を選べば common v1 line へ戻した場合の checked-in artifact をまとめて更新できる

### 6.18 `audit_campaign_third_surface_candidates.py`

コマンド:

```bash
python3 src/tools/audit_campaign_third_surface_candidates.py \
  --ready-scoreboard-json work/rtlmeter_ready_scoreboard.json \
  --active-scoreboard-json work/campaign_speed_scoreboard_active.json \
  --json-out work/campaign_third_surface_candidates.json
```

入力:

- `work/rtlmeter_ready_scoreboard.json`
- `work/campaign_speed_scoreboard_active.json`
- optional stable validation JSON / watch summary JSON referenced from the ready scoreboard

出力:

- `work/campaign_third_surface_candidates.json`

読み方:

- current active campaign line 以外の ready-for-campaign targets を rank する
- `summary.recommended_next_target` が次の comparison surface 候補
- `candidate_state` と `blocking_reason` で、
  frozen reference surface を使うか、Tier B / Tier T に落ちるかを読める

### 6.19 `audit_campaign_post_checkpoint_axes.py`

コマンド:

```bash
python3 src/tools/audit_campaign_post_checkpoint_axes.py \
  --json-out work/campaign_post_checkpoint_axes.json
```

入力:

- `work/campaign_checkpoint_readiness.json`
- `work/campaign_speed_scoreboard_active.json`
- `work/campaign_next_kpi_active.json`
- `third_party/rtlmeter/designs/**/_gpu_cov_tb.sv`
- `src/runners/run_*_gpu_toggle_validation.py`
- `src/runners/run_*_family_gpu_toggle_validation.py`

出力:

- `work/campaign_post_checkpoint_axes.json`

読み方:

- `cross_family_checkpoint_ready` の後に、何を next axis とみなすかを固定する
- current checked-in state では `recommended_next_axis=broaden_non_opentitan_family`
- first recommended family は `XuanTie`、fallback は `VeeR`

### 6.20 `audit_campaign_non_opentitan_entry.py`

コマンド:

```bash
python3 src/tools/audit_campaign_non_opentitan_entry.py \
  --json-out work/campaign_non_opentitan_entry.json
```

入力:

- `work/campaign_post_checkpoint_axes.json`
- `src/runners/run_*_gpu_toggle_validation.py`
- `src/runners/run_*_family_gpu_toggle_validation.py`

出力:

- `work/campaign_non_opentitan_entry.json`

読み方:

- first non-OpenTitan family の first deliverable shape を固定する
- current checked-in state では `recommended_family=XuanTie`, `recommended_entry_mode=family_pilot`

### 6.21 `audit_campaign_non_opentitan_entry_readiness.py`

コマンド:

```bash
python3 src/tools/audit_campaign_non_opentitan_entry_readiness.py \
  --json-out work/campaign_non_opentitan_entry_readiness.json
```

入力:

- `work/campaign_non_opentitan_entry.json`
- `third_party/verilator/bin/verilator_sim_accel_bench`
- `third_party/verilator/bin/verilator`
- `rtlmeter/venv/bin/python`
- `output/legacy_validation/<family>_family_gpu_toggle_validation.json`

出力:

- `work/campaign_non_opentitan_entry_readiness.json`

読み方:

- current recommended entry shape が current workspace で実行可能かを返す
- current checked-in state では `XuanTie + family_pilot` に対して
  `readiness=legacy_family_pilot_failed_but_single_surface_override_ready` を返し、
  `output/legacy_validation/xuantie_family_gpu_toggle_validation.json` を `family_pilot` の negative source of truth としつつ、
  `work/xuantie_e902_gpu_cov_gate_stock_verilator_cc_bootstrap.json` / `work/xuantie_e906_gpu_cov_gate_stock_verilator_cc_bootstrap.json` を `single_surface` override の ready source of truth として使う

`work/campaign_non_opentitan_override_candidates.json`

読み方:

- ready な `single_surface` override 候補を rank する
- current checked-in state では `recommended_design=XuanTie-E902`, `fallback_design=XuanTie-E906` を返す
- `XuanTie-E902` については `validated_trio_ready=true`, `hybrid_wins=true` を返す

### 6.22 `audit_campaign_non_opentitan_entry_profiles.py`

コマンド:

```bash
python3 src/tools/audit_campaign_non_opentitan_entry_profiles.py \
  --json-out work/campaign_non_opentitan_entry_profiles.json
```

出力:

- `work/campaign_non_opentitan_entry_profiles.json`

読み方:

- `family_pilot` と `single_surface` override を named profile で比較する
- current checked-in state では `current_profile_name=xuantie_single_surface_e902`
- alternate hold profile は `xuantie_family_pilot_hold`
- current selection は `single_surface_trio_ready` を返す

### 6.23 `set_campaign_non_opentitan_entry.py`

コマンド:

```bash
python3 src/tools/set_campaign_non_opentitan_entry.py \
  --profile-name xuantie_single_surface_e902
```

出力:

- `config/campaign_non_opentitan_entry/selection.json`
- `work/campaign_non_opentitan_entry_gate.json`

読み方:

- current selected profile の active outcome を返す
- current checked-in state では `status=single_surface_trio_ready`

## 7. reference-design `tlul_request_loopback` flow の入出力

### 7.1 `run_tlul_slice_host_probe.py`

コマンド:

```bash
python3 src/tools/run_tlul_slice_host_probe.py --mdir work/vl_ir_exp/tlul_request_loopback_vl
```

主入力:

- `work/vl_ir_exp/tlul_request_loopback_vl`
- `config/slice_launch_templates/tlul_request_loopback.json`

主出力:

- `<mdir>/tlul_request_loopback_host_probe_report.json`
- optional: `<mdir>/tlul_request_loopback_host_init_state.bin`
- optional: `--clock-sequence` と `--edge-state-dir` を渡した場合は
  `<mdir>/...edge_trace.json` と `host_edge_trace/edge_*.bin`
- `<mdir>/tlul_slice_host_probe` binary

### 7.2 `run_tlul_slice_host_gpu_flow.py`

コマンド:

```bash
python3 src/tools/run_tlul_slice_host_gpu_flow.py \
  --mdir work/vl_ir_exp/tlul_socket_1n_vl \
  --template config/slice_launch_templates/tlul_socket_1n.json
```

主入力:

- `<mdir>/*_host_probe_report.json`
- `<mdir>/*_host_init_state.bin`
- `vl_batch_gpu.cubin`
- `vl_batch_gpu.meta.json`
- optional: template の `debug_internal_output_names`

主出力:

- `<mdir>/*_host_gpu_flow_watch_summary.json` または指定 `--json-out`
- `<mdir>/*_gpu_final_state.bin`

役割:

- host probe baseline と GPU replay 後の raw state を同じ field offsets で読む
- standard outputs に加えて、watch field の `host_probe_hex` / `gpu_final_hex` / `changed` を返す
- host-owned clock sequence が有効な top では、host-only edge trace を追加で作り、
  `edge_parity` に host-only vs GPU replay comparison を返す
- `state_delta` と per-run raw delta も返すので、watch surface の外で何が動いたかを切り分けられる
- second-target 候補で「generic signal set が粗すぎるだけか」を切り分ける

### 7.3 `run_tlul_slice_handoff_parity_probe.py`

コマンド:

```bash
python3 src/tools/run_tlul_slice_handoff_parity_probe.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl \
  --template config/slice_launch_templates/tlul_fifo_sync.json \
  --clock-sequence 1,0
```

主入力:

- `work/vl_ir_exp/tlul_fifo_sync_host_vl`
- `config/slice_launch_templates/tlul_fifo_sync.json`
- `<mdir>` の generated root header / `___024root___eval` symbol

主出力:

- `<mdir>/tlul_fifo_sync_handoff_parity_summary.json`
- `<mdir>/host_handoff_parity_trace/host_eval/edge_*.bin`
- `<mdir>/host_handoff_parity_trace/root_eval/edge_*.bin`
- `<mdir>/host_handoff_parity_trace/fake_syms_eval/edge_*.bin`
- `<mdir>/host_handoff_parity_trace/raw_import_eval/edge_*.bin`

役割:

- host `eval_step` と direct CPU `root___eval` の same-edge parity を取る
- fake `vlSymsp` rebinding でも design-visible parity が崩れないか確認する
- raw dumped state を別 model に import した CPU `root___eval` でも parity が崩れないか確認する
- GPU replay を疑う前に、CPU 側の raw handoff / root-eval semantics が成立しているかを固定する

### 7.4 thin-top host-driven proof: `run_tlul_slice_host_probe.py` + `run_tlul_slice_host_gpu_flow.py`

コマンド:

```bash
python3 src/tools/run_tlul_slice_host_probe.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl \
  --template config/slice_launch_templates/tlul_fifo_sync.json \
  --clock-sequence 1,0 \
  --edge-state-dir work/vl_ir_exp/tlul_fifo_sync_host_vl/host_edge_trace \
  --json-out work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_edge_trace.json

python3 src/tools/run_tlul_slice_host_gpu_flow.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl \
  --template config/slice_launch_templates/tlul_fifo_sync.json \
  --target tlul_fifo_sync \
  --support-tier thin_top_seed \
  --nstates 1 \
  --host-clock-sequence 1,0 \
  --host-clock-sequence-steps 1
```

主入力:

- `work/vl_ir_exp/tlul_fifo_sync_host_vl`
- `config/slice_launch_templates/tlul_fifo_sync.json`
- `vl_batch_gpu.cubin`
- `vl_batch_gpu.meta.json`

主出力:

- `<mdir>/tlul_fifo_sync_host_probe_report.json`
- `<mdir>/tlul_fifo_sync_host_init_state.bin`
- `<mdir>/tlul_fifo_sync_host_edge_trace.json`
- `<mdir>/host_edge_trace/edge_*.bin`
- `<mdir>/tlul_fifo_sync_host_gpu_flow_watch_summary.json`
- `<mdir>/tlul_fifo_sync_host_gpu_final_state.bin`

役割:

- `tlul_fifo_sync_gpu_cov_host_tb` が true host-owned `clk_i` / `rst_ni` を持つことを証明する
- `clock_ownership=host_direct_ports`, `host_clock_control=true`, `host_reset_control=true` を artifact に固定する
- host-only edge trace と same-sequence GPU replay を比較し、GPU-side parity blocker を切る

現時点の truth:

- host-owned `clk/reset` proof は通っている
- host-only edge trace は `progress_cycle_count_o: 6 -> 7`,
  `progress_signature_o: 0 -> 2654435858`,
  toggle bitmap words `0 -> nonzero` を示す
- same-sequence GPU replay は final compare では `changed_watch_field_count=0`
  のままだが、`edge_parity` は all-internal-only residual まで揃っている
- direct CPU `root___eval` parity、fake-`vlSymsp` parity、raw-state-import CPU parity も
  別 artifact で internal-only residual まで揃っている
- したがって、これは `thin-top branch の checked-in Tier R gate`
  を示す I/O surface である

補助診断:

```bash
python3 src/tools/annotate_vl_state_offsets.py \
  work/vl_ir_exp/tlul_fifo_sync_host_vl \
  --summary work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_gpu_flow_watch_summary.json \
  --json-out work/vl_ir_exp/tlul_fifo_sync_host_vl/tlul_fifo_sync_host_state_delta_annotations.json
```

- この annotation artifact により、current pilot の raw 8 byte delta は
  `__VicoPhaseResult`, `__VicoTriggered`, `vlSymsp` という
  `verilator_internal` field だけだと分かる

### 7.4.1 `run_tlul_fifo_sync_stock_hybrid_validation.py`

コマンド:

```bash
python3 src/runners/run_tlul_fifo_sync_stock_hybrid_validation.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl
```

主入力:

- `tlul_fifo_sync` thin-top host probe / host edge trace / host->GPU flow 一式
- `tlul_fifo_sync_handoff_parity_summary.json`

主出力:

- `output/validation/tlul_fifo_sync_stock_hybrid_validation.json`

これは stable validation surface だが、supported source of truth ではない。
この JSON は `support_tier=thin_top_reference_design`、`acceptance_gate=thin_top_edge_parity_v1`、
`clock_ownership=host_direct_ports` を固定し、checked-in `1,0` edge sequence について
host/CPU/GPU parity residual が internal-only まで揃っていることを返す。

### 7.5 historical thin-top seed seam: `run_tlul_fifo_sync_cpu_replay_host_probe.py`

コマンド:

```bash
python3 src/tools/run_tlul_fifo_sync_cpu_replay_host_probe.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_cpu_replay_vl
```

主入力:

- `work/vl_ir_exp/tlul_fifo_sync_cpu_replay_vl`
- `config/slice_launch_templates/tlul_fifo_sync.json`

主出力:

- `<mdir>/tlul_fifo_sync_cpu_replay_host_probe_report.json`
- optional: `<mdir>/tlul_fifo_sync_cpu_replay_host_init_state.bin`
- `<mdir>/tlul_fifo_sync_cpu_replay_host_probe` binary

役割:

- `tlul_fifo_sync_gpu_cov_cpu_replay_tb` という no-port replay wrapper が
  stock Verilator `--cc` で bootstrap 済みかを確認する
- host が wrapper-local config を initial block 後に書けることを確認する
- timed scheduler が動くことを `events_pending_after_init` と `event_drains` で確認する
- raw root image dump を取り、thin-top branch の seed seam を concrete artifact にする

注意:

- これは **真の host-driven `clk/reset` probe ではない**
- JSON も `host_clock_control=false`, `host_reset_control=false` を返す
- 目的は `thin-top branch の seed が存在するか` を固定することであって、
  `socket_m1` の supported host->GPU flow を増やすことではない

### 7.6 `run_tlul_request_loopback_host_gpu_flow.py`

コマンド:

```bash
python3 src/tools/run_tlul_request_loopback_host_gpu_flow.py --mdir work/vl_ir_exp/tlul_request_loopback_vl
```

主入力:

- `tlul_request_loopback_host_probe_report.json`
- `tlul_request_loopback_host_init_state.bin`
- `vl_batch_gpu.cubin`
- `vl_batch_gpu.meta.json`

主出力:

- `<mdir>/tlul_request_loopback_host_gpu_flow_summary.json`
- `<mdir>/tlul_request_loopback_gpu_final_state.bin`

### 7.7 `run_tlul_request_loopback_stock_hybrid_validation.py`

コマンド:

```bash
python3 src/runners/run_tlul_request_loopback_stock_hybrid_validation.py \
  --mdir work/vl_ir_exp/tlul_request_loopback_vl
```

主入力:

- `tlul_request_loopback` host->GPU flow 一式

主出力:

- `output/validation/tlul_request_loopback_stock_hybrid_validation.json`

これは stable validation surface だが、supported source of truth ではない。
この JSON には `promotion_gate` が入り、いま何が足りないから supported に昇格していないかを返す。
加えて `handoff_gate` が GPU replay 自体の進展を返し、`promotion_assessment` が現行 ownership/model のまま reference-design に凍結するべきかを返す。
候補設定の検証は `--host-post-reset-cycles` と `--host-set FIELD=VALUE` で行い、別名 JSON を `work/vl_ir_exp/tlul_request_loopback_vl/` に出す。

### 7.8 loopback handoff search

コマンド:

```bash
python3 src/tools/search_tlul_request_loopback_handoff.py \
  --mdir work/vl_ir_exp/tlul_request_loopback_vl
```

主入力:

- `tlul_request_loopback` validation runner
- `req_valid_pct` / `host_post_reset_cycles` / `steps` の探索空間

主出力:

- `work/vl_ir_exp/tlul_request_loopback_vl/tlul_request_loopback_handoff_search_summary.json`
- `work/vl_ir_exp/tlul_request_loopback_vl/handoff_search/*.json`

これは tuning 候補の探索 artifact であり、supported source of truth ではない。
各 case ごとに `promotion_gate` / `handoff_gate` の結果を保持し、summary 側は
`handoff_passes`、`promotion_only`、`host_incomplete_then_final_done` を集約する。

## 8. legacy flow の入出力

### 8.1 family runner

コマンド:

```bash
python3 src/runners/run_veer_family_gpu_toggle_validation.py
python3 src/runners/run_xuantie_family_gpu_toggle_validation.py
```

主入力:

- sim-accel / RTLMeter 系 build/run 環境

主出力:

- `output/legacy_validation/veer_family_gpu_toggle_validation.json`
- `output/legacy_validation/xuantie_family_gpu_toggle_validation.json`

注意:

- stock-Verilator hybrid の supported 状態とは別物
- `work/` 直下の古い legacy JSON は current status として読まない

## 9. どの出力を読めばよいか

目的ごとの読み口はこれ。

| 目的 | まず読む出力 |
|---|---|
| supported 状態を知りたい | `output/validation/socket_m1_stock_hybrid_validation.json` |
| reference-design 状態を知りたい | `output/validation/tlul_request_loopback_stock_hybrid_validation.json` |
| thin-top reference 状態を知りたい | `output/validation/tlul_fifo_sync_stock_hybrid_validation.json` |
| build の成否と launch contract を知りたい | `<mdir>/vl_batch_gpu.meta.json` |
| classifier の判断理由を知りたい | `<mdir>/vl_classifier_report.json` |
| classifier drift を知りたい | `<mdir>/vl_classifier_audit.json` |
| split parity を知りたい | `<mdir>/vl_hybrid_compare*.json` |
| host probe の ABI / reset 情報を知りたい | `<mdir>/*host_probe_report.json` |

## 10. 迷ったときのルール

- 人に見せる current status は `output/validation/` か `output/legacy_validation/` から読む
- `work/vl_ir_exp/` は診断 artifact として扱う
- `run_vl_hybrid.py` は low-level runner、最終判定には validation runner を使う
- `socket_m1` は supported、`tlul_request_loopback` は `phase_b_reference_design`、`tlul_fifo_sync` は `thin_top_reference_design` と読み分ける
