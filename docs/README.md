# Docs Index

---

## 1. プロジェクト全体

| ドキュメント | 内容 |
|---|---|
| `roadmap_tasks.md` | 全体目標・到達点・優先タスク |
| `status_surfaces.md` | supported / reference-design / diagnostic / legacy の読み分け |

---

## 2. 設計記録

| ドキュメント | 内容 |
|---|---|
| `phase_c_socket_m1_host_abi.md` | `tlul_socket_m1` ABI と host→GPU flow（Phase C 起点） |
| `tlul_fifo_sync_thin_top_design.md` | thin-top branch の実装方針（Tier R まで完了） |
| `phase_b_ico_nba_spike.md` | `___ico_sequent` / `___nba_*` split kernel の調査結果 |
| `phase_b_splitter_redesign.md` | guarded `_eval_nba` segment split への切り替えメモ |

---

## 3. Campaign 計測

### Contract・Schema

| ドキュメント | 内容 |
|---|---|
| `socket_m1_time_to_threshold_packet.md` | time-to-threshold 比較の定義 |
| `socket_m1_campaign_schema_packet.md` | hybrid / baseline / comparison JSON の同型スキーマ |
| `socket_m1_campaign_proof_matrix.md` | reject / unresolved / winner の判定ルール |
| `socket_m1_hybrid_schema_normalization_packet.md` | hybrid JSON への `campaign_threshold` 追加 WP0 |
| `campaign_next_kpi_packet.md` | threshold 強化か design 数拡大かを決める packet |
| `campaign_post_checkpoint_axes_packet.md` | checkpoint 後にどの拡張軸へ進むかの packet |
| `campaign_non_opentitan_entry_packet.md` | first non-OpenTitan family をどう入れるかの packet |

### Threshold Policy ツール

実行順（policy chain）: options → gate → active\_scoreboard

| ツール | 出力 |
|---|---|
| `src/tools/audit_campaign_threshold_policy_options.py` | `work/campaign_threshold_policy_options.json` |
| `src/tools/audit_campaign_threshold_policy_gate.py` | `work/campaign_threshold_policy_gate.json` |
| `src/tools/audit_campaign_active_scoreboard.py` | `work/campaign_speed_scoreboard_active.json` |
| `src/tools/audit_campaign_threshold_policy_preview.py` | `work/campaign_threshold_policy_preview.json` |
| `src/tools/audit_campaign_policy_decision_readiness.py` | `work/campaign_policy_decision_readiness.json` |
| `src/tools/audit_campaign_policy_change_impact.py` | `work/campaign_policy_change_impact.json` |
| `src/tools/audit_campaign_threshold_policy_profiles.py` | `work/campaign_threshold_policy_profiles.json` |
| `src/tools/set_campaign_threshold_policy.py` | `selection.json` 更新 + active artifacts 再生成（operational entrypoint） |
| `config/campaign_threshold_policies/index.json` | policy 候補一覧の source of truth |
| `config/campaign_threshold_policies/selection.json` | 現在選択中 policy の source of truth |

### Scoreboard・KPI ツール

| ツール | 出力 |
|---|---|
| `src/tools/audit_campaign_active_scoreboard.py` | `work/campaign_speed_scoreboard_active.json`（policy-aware、現 canonical） |
| `src/tools/audit_campaign_speed_scoreboard.py` | `work/campaign_speed_scoreboard.json`（policy 導入前 2-surface snapshot） |
| `src/tools/audit_campaign_next_kpi.py` | `work/campaign_next_kpi_audit.json`（threshold 強化検討時点の historical decision） |
| `src/tools/audit_campaign_third_surface_candidates.py` | `work/campaign_third_surface_candidates.json` |
| `src/tools/audit_campaign_third_surface_preview.py` | `work/campaign_third_surface_preview.json` |
| `src/tools/audit_campaign_post_checkpoint_axes.py` | `work/campaign_post_checkpoint_axes.json` |
| `src/tools/audit_campaign_non_opentitan_entry.py` | `work/campaign_non_opentitan_entry.json` |
| `src/tools/audit_campaign_non_opentitan_entry_readiness.py` | `work/campaign_non_opentitan_entry_readiness.json` |
| `src/tools/audit_campaign_non_opentitan_override_candidates.py` | `work/campaign_non_opentitan_override_candidates.json` |
| `src/tools/audit_campaign_non_opentitan_entry_profiles.py` | `work/campaign_non_opentitan_entry_profiles.json` |
| `src/tools/set_campaign_non_opentitan_entry.py` | `config/campaign_non_opentitan_entry/selection.json`, `work/campaign_non_opentitan_entry_gate.json` |
| `src/tools/audit_campaign_real_goal_acceptance_profiles.py` | `work/campaign_real_goal_acceptance_profiles.json` |
| `src/tools/set_campaign_real_goal_acceptance.py` | `config/campaign_real_goal_acceptance/selection.json`, `work/campaign_real_goal_acceptance_gate.json` |
| `src/tools/audit_campaign_xuantie_breadth_status.py` | `work/campaign_xuantie_breadth_status.json` |
| `src/tools/audit_campaign_xuantie_breadth_profiles.py` | `work/campaign_xuantie_breadth_profiles.json` |
| `src/tools/set_campaign_xuantie_breadth.py` | `config/campaign_xuantie_breadth/selection.json`, `work/campaign_xuantie_breadth_gate.json` |
| `src/tools/audit_campaign_xuantie_breadth_acceptance_profiles.py` | `work/campaign_xuantie_breadth_acceptance_profiles.json` |
| `src/tools/set_campaign_xuantie_breadth_acceptance.py` | `config/campaign_xuantie_breadth_acceptance/selection.json`, `work/campaign_xuantie_breadth_acceptance_gate.json` |
| `src/tools/audit_campaign_non_opentitan_breadth_axes.py` | `work/campaign_non_opentitan_breadth_axes.json` |
| `src/tools/audit_campaign_non_opentitan_breadth_profiles.py` | `work/campaign_non_opentitan_breadth_profiles.json` |
| `src/tools/set_campaign_non_opentitan_breadth.py` | `config/campaign_non_opentitan_breadth/selection.json`, `work/campaign_non_opentitan_breadth_gate.json` |
| `src/tools/audit_campaign_non_opentitan_breadth_branch_candidates.py` | `work/campaign_non_opentitan_breadth_branch_candidates.json` |
| `src/tools/audit_campaign_xuantie_same_family_step.py` | `work/campaign_xuantie_same_family_step.json` |
| `src/tools/audit_campaign_xuantie_same_family_profiles.py` | `work/campaign_xuantie_same_family_profiles.json` |
| `src/tools/set_campaign_xuantie_same_family.py` | `config/campaign_xuantie_same_family/selection.json`, `work/campaign_xuantie_same_family_gate.json` |
| `src/tools/audit_campaign_xuantie_same_family_acceptance_profiles.py` | `work/campaign_xuantie_same_family_acceptance_profiles.json` |
| `src/tools/set_campaign_xuantie_same_family_acceptance.py` | `config/campaign_xuantie_same_family_acceptance/selection.json`, `work/campaign_xuantie_same_family_acceptance_gate.json` |
| `src/tools/audit_campaign_xuantie_same_family_next_axes.py` | `work/campaign_xuantie_same_family_next_axes.json` |
| `src/tools/audit_campaign_xuantie_c910_split_phase_trial.py` | `work/campaign_xuantie_c910_split_phase_trial.json` |
| `src/tools/audit_campaign_veer_fallback_candidates.py` | `work/campaign_veer_fallback_candidates.json` |
| `src/tools/audit_campaign_veer_first_surface_step.py` | `work/campaign_veer_first_surface_step.json` |
| `src/tools/audit_campaign_veer_first_surface_gate.py` | `work/campaign_veer_first_surface_gate.json` |
| `src/tools/audit_campaign_veer_first_surface_acceptance_gate.py` | `work/campaign_veer_first_surface_acceptance_gate.json` |
| `src/tools/audit_campaign_veer_next_axes.py` | `work/campaign_veer_next_axes.json` |
| `src/tools/audit_campaign_veer_same_family_step.py` | `work/campaign_veer_same_family_step.json` |
| `src/tools/audit_campaign_veer_same_family_gate.py` | `work/campaign_veer_same_family_gate.json` |
| `src/tools/audit_campaign_veer_same_family_acceptance_gate.py` | `work/campaign_veer_same_family_acceptance_gate.json` |
| `src/tools/set_campaign_veer_same_family.py` | `config/campaign_veer_same_family/selection.json`, `work/campaign_veer_same_family_gate.json` |
| `src/tools/set_campaign_veer_same_family_acceptance.py` | `config/campaign_veer_same_family_acceptance/selection.json`, `work/campaign_veer_same_family_acceptance_gate.json` |
| `src/tools/audit_campaign_veer_same_family_next_axes.py` | `work/campaign_veer_same_family_next_axes.json` |
| `src/tools/audit_campaign_veer_final_same_family_step.py` | `work/campaign_veer_final_same_family_step.json` |
| `src/tools/audit_campaign_veer_final_same_family_gate.py` | `work/campaign_veer_final_same_family_gate.json` |
| `src/tools/set_campaign_veer_final_same_family.py` | `config/campaign_veer_final_same_family/selection.json`, `work/campaign_veer_final_same_family_gate.json` |
| `src/tools/audit_campaign_veer_final_same_family_acceptance_gate.py` | `work/campaign_veer_final_same_family_acceptance_gate.json` |
| `src/tools/set_campaign_veer_final_same_family_acceptance.py` | `config/campaign_veer_final_same_family_acceptance/selection.json`, `work/campaign_veer_final_same_family_acceptance_gate.json` |
| `src/tools/audit_campaign_veer_post_family_exhaustion_axes.py` | `work/campaign_veer_post_family_exhaustion_axes.json` |
| `src/tools/audit_campaign_xiangshan_first_surface_status.py` | `work/campaign_xiangshan_first_surface_status.json` |
| `src/tools/audit_campaign_xiangshan_debug_tactics.py` | `work/campaign_xiangshan_debug_tactics.json` |
| `src/tools/audit_campaign_xiangshan_vortex_branch_resolution.py` | `work/campaign_xiangshan_vortex_branch_resolution.json` |
| `src/tools/audit_campaign_xiangshan_deeper_debug_status.py` | `work/campaign_xiangshan_deeper_debug_status.json` |
| `src/tools/probe_vl_gpu_nvcc_device_link.py` | `work/xiangshan_nvcc_device_link_probe.json` |
| `src/tools/audit_campaign_xiangshan_first_surface_step.py` | `work/campaign_xiangshan_first_surface_step.json` |
| `src/tools/audit_campaign_xiangshan_first_surface_gate.py` | `work/campaign_xiangshan_first_surface_gate.json` |
| `src/tools/set_campaign_xiangshan_first_surface.py` | `config/campaign_xiangshan_first_surface/selection.json`, `work/campaign_xiangshan_first_surface_gate.json` |
| `src/tools/audit_campaign_xiangshan_first_surface_acceptance_gate.py` | `work/campaign_xiangshan_first_surface_acceptance_gate.json` |
| `src/tools/set_campaign_xiangshan_first_surface_acceptance.py` | `config/campaign_xiangshan_first_surface_acceptance/selection.json`, `work/campaign_xiangshan_first_surface_acceptance_gate.json` |
| `src/tools/audit_campaign_openpiton_first_surface_step.py` | `work/campaign_openpiton_first_surface_step.json` |
| `src/tools/audit_campaign_openpiton_first_surface_gate.py` | `work/campaign_openpiton_first_surface_gate.json` |
| `src/tools/set_campaign_openpiton_first_surface.py` | `config/campaign_openpiton_first_surface/selection.json`, `work/campaign_openpiton_first_surface_gate.json` |
| `src/tools/audit_campaign_openpiton_first_surface_acceptance_gate.py` | `work/campaign_openpiton_first_surface_acceptance_gate.json` |
| `src/tools/set_campaign_openpiton_first_surface_acceptance.py` | `config/campaign_openpiton_first_surface_acceptance/selection.json`, `work/campaign_openpiton_first_surface_acceptance_gate.json` |
| `src/tools/audit_campaign_post_openpiton_axes.py` | `work/campaign_post_openpiton_axes.json` |
| `src/tools/audit_campaign_vortex_first_surface_status.py` | `work/campaign_vortex_first_surface_status.json` |
| `src/tools/audit_campaign_vortex_first_surface_gate.py` | `work/campaign_vortex_first_surface_gate.json` |
| `src/tools/set_campaign_vortex_first_surface.py` | `config/campaign_vortex_first_surface/selection.json`, `work/campaign_vortex_first_surface_gate.json` |
| `src/tools/audit_campaign_vortex_first_surface_policy_gate.py` | `work/campaign_vortex_first_surface_policy_gate.json` |
| `src/tools/set_campaign_vortex_first_surface_policy.py` | `config/campaign_vortex_first_surface_policy/selection.json`, `work/campaign_vortex_first_surface_policy_gate.json` |
| `src/tools/audit_campaign_vortex_first_surface_acceptance_gate.py` | `work/campaign_vortex_first_surface_acceptance_gate.json` |
| `src/tools/set_campaign_vortex_first_surface_acceptance.py` | `config/campaign_vortex_first_surface_acceptance/selection.json`, `work/campaign_vortex_first_surface_acceptance_gate.json` |
| `src/tools/audit_campaign_vortex_first_surface_profiles.py` | `work/campaign_vortex_first_surface_profiles.json` |
| `src/tools/audit_campaign_vortex_debug_tactics.py` | `work/campaign_vortex_debug_tactics.json` |
| `src/tools/audit_campaign_post_vortex_axes.py` | `work/campaign_post_vortex_axes.json` |
| `src/tools/audit_campaign_caliptra_first_surface_status.py` | `work/campaign_caliptra_first_surface_status.json` |
| `src/tools/audit_campaign_caliptra_debug_tactics.py` | `work/campaign_caliptra_debug_tactics.json` |
| `src/tools/audit_xuantie_e906_threshold_options.py` | `work/xuantie_e906_threshold_options.json` |

---

## 4. 対象拡大

| ドキュメント / ツール | 内容・出力 |
|---|---|
| `next_supported_target_candidates.md` | 次の supported target 候補と first-pass 実測 |
| `tlul_fifo_sync_handoff_parity_packet.md` | CPU parity vs GPU parity の分解 |
| `tlul_fifo_sync_promotion_packet.md` | Tier R → Tier S 昇格の判断（current decision: Tier R 維持） |
| `rtlmeter_coverage_plan.md` | repo-wide coverage 拡大 Wave 1–5 |
| `src/tools/audit_second_target_feasibility.py` | `work/second_target_feasibility_audit.json` |
| `src/tools/audit_rtlmeter_ready_scoreboard.py` | `work/rtlmeter_ready_scoreboard.json` |
| `src/tools/audit_rtlmeter_expansion_branches.py` | `work/rtlmeter_expansion_branch_audit.json` |
| `src/tools/audit_tlul_fifo_sync_threshold_semantics.py` | `work/tlul_fifo_sync_threshold_semantics_audit.json` |
| `src/tools/run_design_enrollment_trio.py` | 新デザインの hybrid / baseline / comparison trio を汎用実行。`--probe-threshold` で plateau 時の最大有効 threshold を自動算出 |
| `src/runners/enrollment_common.py` | 上記 trio の共有ロジック（runtime input setup, payload building, threshold probe） |

---

## 5. 参照

| ドキュメント / ツール | 内容 |
|---|---|
| `input_output_map.md` | 各 flow / CLI の入出力対応表 |
| `codebase_complexity_audit.md` | ファイル煩雑度の定量レポート |
| `src/tools/audit_agents_guidelines.py` | AGENTS.md ガイドライン準拠チェック → `work/agents_guideline_audit.json` |

---

## Archive

完了済み execution packet（実装記録として保存）:

| ファイル | 対象 |
|---|---|
| `docs/archive/tlul_fifo_sync_thin_top_execution_packet.md` | thin-top WP1–WP5（Tier R 完了） |
| `docs/archive/socket_m1_time_to_threshold_execution_packet.md` | baseline/comparison runner 実装 |
| `docs/archive/socket_m1_hybrid_schema_wp0_execution_packet.md` | hybrid JSON schema 正規化 WP0 |

---

## 現在の状態

**Checkpoint**: first OpenTitan campaign checkpoint 確定済み。XuanTie 拡張進行中。

> **OpenTitan**: ready pool 9 surface 全勝（最弱 2.64x）、comparison_ready=9、reject=0。Tier S=1（`socket_m1`）。
> **XuanTie-E902**: full trio 完了、winner=hybrid ≈16.79x。first non-OpenTitan campaign surface 確立。
> **XuanTie-E906**: candidate-only threshold=2 で winner=hybrid ≈30.37x（default gate は unresolved）。
> **XuanTie-C906**: candidate-only threshold=5 で winner=hybrid ≈9.59x。
> **XuanTie-C910**: CPU baseline OK、hybrid は `before_cuModuleLoad` で blocked。split-phase trial も timeout。
> 「任意 RTL に一般化できた」とはまだ言えない（default gate 未達 surface あり、C910 blocked）。

**Campaign surfaces**（OpenTitan: 9 本 checked-in）:

| Surface | winner | speedup |
|---|---|---|
| `socket_m1` | hybrid | ≈22.53 |
| `tlul_fifo_sync` | hybrid | ≈2.64 |
| `tlul_request_loopback` | hybrid | ≈4.87 |
| `tlul_err` | hybrid | ≈14.06 |
| `tlul_sink` | hybrid | ≈10.42 |
| `tlul_socket_1n` | hybrid | ≈8.05 |
| `tlul_fifo_async` | hybrid | ≈11.23 |
| `xbar_main` | hybrid | ≈12.66 |
| `xbar_peri` | hybrid | ≈11.70 |

**Campaign surfaces**（XuanTie: 進行中）:

| Design | gate | winner | speedup | 備考 |
|---|---|---|---|---|
| `XuanTie-E902` | default | hybrid | ≈16.79x | full trio 完了 |
| `XuanTie-E906` | candidate-only threshold=2 | hybrid | ≈30.37x | default gate は unresolved |
| `XuanTie-C906` | candidate-only threshold=5 | hybrid | ≈9.59x | — |
| `XuanTie-C910` | — | — | — | CPU baseline OK、hybrid blocked、split-phase trial も timeout |

**Campaign surfaces**（VeeR: 進行中）:

| Design | gate | winner | speedup | 備考 |
|---|---|---|---|---|
| `VeeR-EH1` | candidate-only threshold=5 | hybrid | ≈3.37x | accepted fallback-family breadth evidence |
| `VeeR-EH2` | candidate-only threshold=4 | hybrid | ≈2.97x | accepted same-family breadth evidence; default gate 8 は unresolved、bits_hit=4 で plateau |
| `VeeR-EL2` | candidate-only threshold=6 | hybrid | ≈2.78x | default gate 8 は unresolved、bits_hit=6 で plateau |

current active scoreboard → `work/campaign_speed_scoreboard_active.json`

**Policy**:
- current selection: `profile_name=per_target_ready`, `allow_per_target_thresholds=true`, `require_matching_thresholds=false`
- → active campaign threshold policy は design-specific v2 line（`all_thresholds_match=false`）
- policy を `allow_per_target_thresholds=false` に戻すと common v1 + `stronger_thresholds` に落ちる

**XuanTie entry**:
- 次の拡大軸: `non-OpenTitan family breadth`、対象 family = `XuanTie`
  （`work/campaign_post_checkpoint_axes.json` → `recommended_next_axis=broaden_non_opentitan_family`）
- current profile: `xuantie_single_surface_e902`
  （`work/campaign_non_opentitan_entry_gate.json` → `status=single_surface_trio_ready`）
- legacy hold profile: `xuantie_family_pilot_hold`
  （profile matrix 上では `status=family_pilot_blocked`）
- validated override candidate: `XuanTie-E902:gpu_cov_gate`
  （`work/campaign_non_opentitan_override_candidates.json` → `recommended_design=XuanTie-E902`, `status=recommend_validated_single_surface_candidate`）
- bootstrap fallback candidate: `XuanTie-E906:gpu_cov_gate`
  （`work/campaign_non_opentitan_override_candidates.json` → `fallback_design=XuanTie-E906`）
- next breadth evidence for `XuanTie-E906`: default trio は unresolved だが、`threshold=2` candidate-only comparison は `winner=hybrid`
  （`output/validation/xuantie_e906_time_to_threshold_comparison_threshold2.json`）
- known workload sweep for `XuanTie-E906`: `cmark / hello / memcpy` は全部 `bits_hit=2` で plateau
  （`work/xuantie_e906_case_variants.json` → `status=default_gate_blocked_across_known_case_pats`）
- seed-status summary: `ready_to_accept_selected_seed`
  （`work/campaign_non_opentitan_seed_status.json`）
- acceptance profile: `accept_checkpoint_and_seed`
  （`work/campaign_real_goal_acceptance_gate.json` → `status=accepted_checkpoint_and_seed`）
- next breadth summary: `XuanTie-E906` は `default_gate_blocked_across_known_case_pats`、
  ただし `threshold=2` candidate-only line は `winner=hybrid`
  （`work/campaign_xuantie_breadth_status.json`）
- numeric gate summary: `threshold=2` が strongest ready gate、`3..8` は blocked
  （`work/xuantie_e906_threshold_options.json`）
- current breadth profile: `e906_candidate_only_threshold2`
  （`work/campaign_xuantie_breadth_gate.json` → `status=candidate_only_ready`）
- breadth acceptance profile: `accept_selected_xuantie_breadth`
  （`work/campaign_xuantie_breadth_acceptance_gate.json` → `status=accepted_selected_xuantie_breadth`）
- post-E906 breadth axis: `decide_continue_xuantie_breadth_vs_open_fallback_family`
  （`work/campaign_non_opentitan_breadth_axes.json`）
- post-E906 breadth profiles:
  current=`xuantie_continue_same_family`
  ready alternatives=`open_veer_fallback_family`
  （`work/campaign_non_opentitan_breadth_profiles.json`）
- current active post-E906 breadth gate:
  `continue_same_family_ready`
  （`work/campaign_non_opentitan_breadth_gate.json`）
- post-E906 branch recommendation:
  `xuantie_continue_same_family` first, `XuanTie-C906` first design, fallback=`open_veer_fallback_family`
  （`work/campaign_non_opentitan_breadth_branch_candidates.json`）
- current same-family concrete step:
  `decide_selected_same_family_design_candidate_only_vs_new_default_gate`
  （`work/campaign_xuantie_same_family_step.json`）
- same-family step profiles:
  current=`c906_candidate_only_threshold5`
  （`work/campaign_xuantie_same_family_profiles.json`）
- same-family step gate:
  `candidate_only_ready`
  （`work/campaign_xuantie_same_family_gate.json`）
- same-family step acceptance:
  `accepted_selected_same_family_step`
  （`work/campaign_xuantie_same_family_acceptance_gate.json`）
- next same-family/fallback axis:
  `decide_continue_to_remaining_same_family_design_vs_open_fallback_family`
  （`work/campaign_xuantie_same_family_next_axes.json`）
- current C910 runtime summary:
  `decide_hybrid_runtime_debug_vs_open_veer_fallback_family`
  （`work/campaign_xuantie_c910_runtime_status.json`）
- current C910 runtime localization:
  `O0` low-opt rebuild は `llc` の `AtomicLoad acquire (s64)` selection で abort、
  `O1` low-opt trace でも `before_cuModuleLoad` で止まり、offline `ptxas` probe も `180s` timeout で cubin 未生成
  → current blocker は kernel launch ではなく PTX/JIT + cubin assembly 側、next debug line は deeper cubin-first
- current C910 runtime profile:
  `open_veer_fallback_family`
  （`work/campaign_xuantie_c910_runtime_gate.json`）
- C910 runtime profile matrix:
  current=recommended=`open_veer_fallback_family`, ready alternative=`debug_c910_hybrid_runtime`
  （`work/campaign_xuantie_c910_runtime_profiles.json`）
- split-phase PTX/module-first trial:
  `returncode=137`、last stage=`before_cuModuleLoad`
  （`work/campaign_xuantie_c910_split_phase_trial.json`）
- current C910 debug tactic:
  `prefer_fallback_family_after_split_phase_trial_failed`
  （`work/campaign_xuantie_c910_debug_tactics.json`）
- current VeeR fallback candidate:
  `VeeR-EH1` first, `VeeR-EH2` fallback
  （`work/campaign_veer_fallback_candidates.json`）
- current VeeR first-surface gate:
  `candidate_only_ready`
  （`work/campaign_veer_first_surface_gate.json`）
- current VeeR first-surface acceptance:
  `accepted_selected_veer_first_surface_step`
  （`work/campaign_veer_first_surface_acceptance_gate.json`）
- current VeeR next axes:
  `decide_continue_to_remaining_veer_design`
  （`work/campaign_veer_next_axes.json`）
- current VeeR same-family gate:
  `candidate_only_ready`
  （`work/campaign_veer_same_family_gate.json`）
- current VeeR same-family acceptance:
  `accepted_selected_veer_same_family_step`
  （`work/campaign_veer_same_family_acceptance_gate.json`）
- current VeeR same-family next axes:
  `decide_continue_to_remaining_veer_design`
  （`work/campaign_veer_same_family_next_axes.json`）
- current VeeR final same-family step:
  `decide_veer_el2_candidate_only_vs_new_default_gate`
  （`work/campaign_veer_final_same_family_step.json`）
- current VeeR final same-family gate:
  `candidate_only_ready`
  （`work/campaign_veer_final_same_family_gate.json`）
- current VeeR final same-family acceptance:
  `accepted_selected_veer_final_same_family_step`
  （`work/campaign_veer_final_same_family_acceptance_gate.json`）
- current VeeR post-family exhaustion axes:
  `decide_open_next_non_veer_family_after_veer_exhaustion`
  （`work/campaign_veer_post_family_exhaustion_axes.json`）

**次のタスク**（1 本）:
1. `Caliptra` の split `nba_comb` runtime blocker を潰す。
   - `work/campaign_vortex_first_surface_acceptance_gate.json` の current state は
     `accepted_selected_vortex_first_surface_step`
   - `work/campaign_post_vortex_axes.json` の current state は
     `decide_open_next_family_after_vortex_acceptance`
   - `work/caliptra_gpu_cov_stock_verilator_cc_bootstrap.json` は `status=ok`
   - `output/validation/caliptra_cpu_baseline_validation.json` は `status=ok`
   - `work/campaign_caliptra_first_surface_status.json` の current state は
      `decide_caliptra_tls_lowering_debug_vs_open_example_fallback`
   - `work/campaign_caliptra_debug_tactics.json` の current state は
     `ready_for_deeper_caliptra_split_m_axi_if0_first_store_compilable_branch1_load_provenance_nonconstant_loaded_byte_dependent_store_source_bits_runtime_fault_debug`
   - `work/caliptra_split_phase_probe/vl_kernel_manifest.json` は
     `vl_ico_batch_gpu / vl_nba_comb_batch_gpu / vl_nba_sequent_batch_gpu`
     の split launch sequence を固定している
   - `work/caliptra_split_phase_probe/vl_batch_gpu_split_compile_only_probe.json` は
     split compile-only probe が `ok` で、split entry kernels が `0 bytes stack frame` を報告する
   - `work/caliptra_split_phase_probe/vl_batch_gpu_split_nvcc_device_link_probe.json` は
     split PTX の `nvcc --device-c -> --device-link --cubin` line が `ok` で、
     linked cubin と split entry symbols を保持することを示す
   - `work/caliptra_split_phase_probe/split_cubin_smoke_trace.log` は
     current split linked-cubin runtime が `after_first_kernel_launch` まで進み、
     その後 `CUDA error 700: illegal memory access` で落ちることを示す
   - `work/caliptra_split_phase_probe/split_cubin_ico_smoke_trace.log` と
     `work/caliptra_split_phase_probe/split_cubin_nba_sequent_smoke_trace.log` は
     `ico` / `nba_sequent` 単体 run が `ok` であることを示す
   - `work/caliptra_split_phase_probe/split_cubin_nba_comb_smoke_trace.log`,
     `work/caliptra_split_phase_probe/split_cubin_nba_comb_block1_smoke_trace.log`,
     `work/caliptra_split_phase_probe/split_cubin_nba_comb_block8_smoke_trace.log` は
     culprit が `vl_nba_comb_batch_gpu` で、small block sizes でも落ちることを示す
   - `work/caliptra_split_phase_probe/split_cubin_nba_comb_prefix330_smoke_trace.log` は `ok`、
     `split_cubin_nba_comb_prefix331_smoke_trace.log` は `illegal memory access`
   - `split_cubin_nba_comb_prefix331_param_only_smoke_trace.log`,
     `split_cubin_nba_comb_m_axi_if0_noarg_ret_only_smoke_trace.log`,
     `split_cubin_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_trace.log` は `ok`、
     さらに truncated-after-`callseq 331` の
     `split_cubin_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_trace.log`,
     `split_cubin_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_trace.log`,
     `split_cubin_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_trace.log` も `ok` です。
     一方で truncated `%rd5` isolated line も clean です。さらに
     `split_cubin_nba_comb_m_axi_if0_first_branch_merge_ret_trunc_smoke_trace.log` は `ok` で、
     `split_cubin_nba_comb_m_axi_if0_first_store_ret_trunc_smoke_trace.log` は `illegal memory access`、
     ただし `split_cubin_nba_comb_m_axi_if0_first_store_zero_data_ret_trunc_smoke_trace.log` と
     `split_cubin_nba_comb_m_axi_if0_first_store_one_data_ret_trunc_smoke_trace.log` は `ok` です。
     さらに `split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_ret_trunc_smoke_trace.log` は
     still fault し、`split_cubin_nba_comb_m_axi_if0_first_store_branch1_load_zero_store_ret_trunc_smoke_trace.log`
     は `ok` です。加えて `first_store_branch1_load_mask1_ret_trunc`、
     `first_store_branch1_predicated01_ret_trunc`、`first_store_branch1_selp_const1_ret_trunc`、
     `first_store_masked_data_ret_trunc` も still fault します。一方で
     `first_store_branch1_load_dead_mask_const1_ret_trunc` と
     `first_store_branch1_selp_same_const1_ret_trunc` は `ok`、さらに
     `first_store_branch1_load_mask1_shl8_ret_trunc` は still fault し、
     `first_store_masked_data_dead_mask_const1_ret_trunc` と
     `first_store_masked_data_predicated01_ret_trunc` と
     `first_store_masked_data_force_else_ret_trunc` と
     `first_store_masked_data_mask1_ret_trunc` と
     `first_store_masked_data_mask1_shl8_ret_trunc` と
     `first_store_masked_data_selp_const1_ret_trunc` と
     `first_store_masked_data_selp_same_const1_ret_trunc` と
     `first_store_branch1_predicated10_ret_trunc` と
     `first_store_branch1_load_dead_mask_zero_ret_trunc` と
     `first_store_branch1_load_mask1_shr8_ret_trunc` と
     `first_store_branch1_load_mask1_shl1_ret_trunc` と
     `first_store_branch1_load_mask1_shl4_ret_trunc` と
     `first_store_branch1_load_mask1_shl6_ret_trunc` と
     `first_store_branch1_load_mask1_shl7_ret_trunc` と
     `first_store_branch1_load_mask1_shl9_ret_trunc` と
     `first_store_branch1_load_mask1_shl8_and255_ret_trunc` と
     `first_store_branch1_selp_const2_ret_trunc` と
     `first_store_branch1_selp_const3_ret_trunc` と
     `first_store_branch1_selp_const129_ret_trunc` と
     `first_store_branch1_selp_const257_ret_trunc` と
     `first_store_branch1_selp_const1_and255_ret_trunc` と
     `first_store_branch1_selp_const513_ret_trunc` と
     `first_store_branch1_selp_const0_ret_trunc` と
     `first_store_branch1_load_mask2_ret_trunc` と
     `first_store_branch1_load_maskff_ret_trunc` と
     `first_store_branch1_load_mask3_ret_trunc` は compile timeout、
     `first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc`、
     `first_store_branch1_load_mask1_sep_reg_ret_trunc`、
     `first_store_branch1_load_xor_self_zero_ret_trunc`、
     `first_store_self_load_ret_trunc`、
     `first_store_branch1_load_store_plus1_ret_trunc`、
     `first_store_branch1_load_mask1_or1_ret_trunc`、
     `first_store_branch1_load_mov_ret_trunc`、
     `first_store_branch1_alt_load_ret_trunc`
     は compile timeout です。なので、
     current culprit は `m_axi_if__0` first store の compilable current-branch1-load-provenance
     nonconstant loaded-byte-dependent full-width store source bits です。
   - current main line は `deeper_caliptra_split_m_axi_if0_first_store_compilable_branch1_load_provenance_nonconstant_loaded_byte_dependent_store_source_bits_runtime_fault_debug`、fallback は `Example`
   - 補助観測として `first_store_masked_data_selp_same_const1_ret_trunc` と `first_store_masked_data_selp_const1_ret_trunc` と `first_store_masked_data_force_else_ret_trunc` と `first_store_masked_data_mask1_shl8_ret_trunc` も `compile=timed_out` で、masked-data merge shape の same-const1 analog と selp-const1 analog と else-force analog と mask1-shl8 analog も actionable runtime line に入りません
   - 補助観測として `first_store_branch1_selp_const2_ret_trunc` も `compile=timed_out` で、small low-bit `1/2` arm split も actionable runtime line に入りません
   - 補助観測として `first_store_branch1_selp_const3_ret_trunc` も `compile=timed_out` で、small low-bit `1/3` arm split も actionable runtime line に入りません
   - 補助観測として `first_store_branch1_selp_const129_ret_trunc` も `compile=timed_out` で、bit7-only `1/129` arm split も actionable runtime line に入りません
   - 補助観測として `first_store_branch1_selp_const257_ret_trunc` も `compile=timed_out` で、`1/257` arm 反転だけでは actionable runtime line に戻りません
   - 補助観測として `first_store_branch1_selp_const1_and255_ret_trunc` も `compile=timed_out` で、same-register upper-bit clear でも actionable runtime line に入りません
   - 補助観測として `first_store_branch1_selp_const513_ret_trunc` も `compile=timed_out` で、upper-byte-only `1/513` arm split も actionable runtime line に入りません
   - 補助観測として `first_store_branch1_selp_same_const257_ret_trunc` も `compile=timed_out` で、`same-register 0x0101` 定数化は actionable runtime line に入らない

**Deferred**（critical path に戻さない）:
- `family_pilot` 復旧（legacy bench owner・工数が見えたら再検討）
- `tlul_fifo_sync` promotion（Tier R 維持）
- `tlul_request_loopback` promotion
- `strict_final_state`
- 2 本目 supported target 探索（次 milestone で機構判断から再開）

**Tier 状況** (OpenTitan): Tier S=1, Tier R=8 / (XuanTie): E902=full trio、E906/C906=candidate-only、C910=hold / (VeeR): EH1/EH2/EL2=accepted breadth evidence / (OpenPiton): first default-gate trio accepted / (BlackParrot): baseline-loss branch / (Vortex): `threshold=4` candidate-only line accepted / (XiangShan): `threshold=2` candidate-only line accepted / (Caliptra): bootstrap+CPU baseline ok, monolithic kernel is stack-ceiling blocked, split compile-only probe succeeds, official split linked cubin also builds, `ico`/`nba_sequent` run, and current blocker is the first store path inside `m_axi_if__0` in `vl_nba_comb_batch_gpu`: the first branch-merge truncation runs cleanly, but restoring only the first store reproduces the runtime fault。

---

## Entrypoints

### Supported flow

```
./quickstart_hybrid.sh --mdir work/vl_ir_exp/socket_m1_vl --socket-m1-host-gpu-flow --lite
python3 src/runners/run_socket_m1_stock_hybrid_validation.py --mdir work/vl_ir_exp/socket_m1_vl --nstates 64 --steps 1
```

### Reference-design validation

```
python3 src/runners/run_tlul_request_loopback_stock_hybrid_validation.py --mdir work/vl_ir_exp/tlul_request_loopback_vl
python3 src/runners/run_tlul_fifo_sync_stock_hybrid_validation.py --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl
python3 src/tools/search_tlul_request_loopback_handoff.py --mdir work/vl_ir_exp/tlul_request_loopback_vl
```

### Thin-top proof の再現

```
python3 src/tools/bootstrap_hybrid_tlul_slice_cc.py --slice-name tlul_fifo_sync \
  --out-dir work/vl_ir_exp/tlul_fifo_sync_host_vl \
  --tb-path third_party/rtlmeter/designs/OpenTitan/src/tlul_fifo_sync_gpu_cov_host_tb.sv \
  --top-module tlul_fifo_sync_gpu_cov_host_tb --force
python3 src/tools/build_vl_gpu.py work/vl_ir_exp/tlul_fifo_sync_host_vl
python3 src/tools/run_tlul_slice_host_probe.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl \
  --template config/slice_launch_templates/tlul_fifo_sync.json
python3 src/tools/run_tlul_slice_host_gpu_flow.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl \
  --template config/slice_launch_templates/tlul_fifo_sync.json \
  --target tlul_fifo_sync --support-tier thin_top_seed \
  --nstates 1 --host-clock-sequence 1,0 --host-clock-sequence-steps 1
python3 src/tools/run_tlul_slice_handoff_parity_probe.py \
  --mdir work/vl_ir_exp/tlul_fifo_sync_host_vl \
  --template config/slice_launch_templates/tlul_fifo_sync.json \
  --clock-sequence 1,0
```

---

## Audit Commands

### Campaign（policy chain → `work/`）

```
# step 1: options
python3 src/tools/audit_campaign_threshold_policy_options.py
# step 2: gate
python3 src/tools/audit_campaign_threshold_policy_gate.py
# step 3: active scoreboard
python3 src/tools/audit_campaign_active_scoreboard.py

# 影響分析（任意）
python3 src/tools/audit_campaign_threshold_policy_preview.py
python3 src/tools/audit_campaign_policy_decision_readiness.py
python3 src/tools/audit_campaign_policy_change_impact.py
python3 src/tools/audit_campaign_threshold_policy_profiles.py

# 次の surface 候補
python3 src/tools/audit_campaign_third_surface_candidates.py
python3 src/tools/audit_campaign_third_surface_preview.py
python3 src/tools/audit_campaign_post_checkpoint_axes.py
python3 src/tools/audit_campaign_non_opentitan_entry.py
```

### 対象拡大（→ `work/`）

```
python3 src/tools/audit_second_target_feasibility.py --json-out work/second_target_feasibility_audit.json
python3 src/tools/audit_rtlmeter_ready_scoreboard.py --json-out work/rtlmeter_ready_scoreboard.json
python3 src/tools/audit_rtlmeter_expansion_branches.py \
  --scoreboard work/rtlmeter_ready_scoreboard.json \
  --feasibility work/second_target_feasibility_audit.json \
  --json-out work/rtlmeter_expansion_branch_audit.json
python3 src/tools/audit_tlul_fifo_sync_threshold_semantics.py
```

### Classifier・Guidelines

```
python3 src/tools/audit_vl_classifier_report.py \
  work/vl_ir_exp/socket_m1_vl/vl_classifier_report.json \
  --expect config/classifier_expectations/tlul_socket_m1.json
python3 src/tools/audit_vl_classifier_report.py \
  work/vl_ir_exp/tlul_request_loopback_vl/vl_classifier_report.json \
  --expect config/classifier_expectations/tlul_request_loopback.json
python3 src/tools/audit_agents_guidelines.py --json-out work/agents_guideline_audit.json
```

### Complexity

```
python3 complexity_audit/audit.py --target . --config complexity_audit/config.json
python3 complexity_audit/audit.py --target . --config complexity_audit/config.json \
  --baseline work/complexity_baseline.json --report-out work/complexity_report.md
```

---

## Maintenance

```
python3 src/tools/analyze_rtlmeter_coverage_convergence.py
python3 src/tools/freeze_opentitan_tlul_slice_production_defaults.py
python3 src/tools/report_opentitan_tlul_slice_rollout_status.py
python3 src/tools/report_opentitan_tlul_surface_results.py
python3 src/tools/probe_sim_accel_runtime_contract.py
```
