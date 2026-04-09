# Status Surfaces

このプロジェクトでは、status を読む場所を次の 5 種類に分ける。
入出力物の一覧は [input_output_map.md](input_output_map.md) を参照。

## 1. Supported stock-Verilator status

現在の source of truth はこれ。

- `output/validation/socket_m1_stock_hybrid_validation.json`

意味:

- stock Verilator frontend
- supported `tlul_socket_m1` hybrid flow
- host probe、toggle bitmap、GPU timing、`artifacts.classifier_report` を含む安定 JSON
- campaign line 向けに `campaign_threshold` と `campaign_measurement` も含む
- minimum README goal を主張するときの根拠

このファイルを「現在の supported 状態」として読む。
この 1 本で current milestone の `socket_m1`-only supported 状態と minimum goal 達成を示す。
同時に、future baseline/comparison line における hybrid 側 source of truth としても読む。

## 2. Stable reference-design validation JSON

stable schema を使うが、supported source of truth ではないもの。

- `output/validation/tlul_request_loopback_stock_hybrid_validation.json`
- `output/validation/tlul_fifo_sync_stock_hybrid_validation.json`

意味:

- stock Verilator frontend
- `tlul_request_loopback` reference-design flow
- `phase_b_reference_design` tier の validation
- schema は `socket_m1` runner と揃えるが、supported CPU slice へ昇格したとは読まない
- `promotion_gate` を読み、何が blocker かを確認する
- `handoff_gate` を読み、GPU replay が host-probe baseline を本当に前へ進めたかを確認する
- `promotion_assessment.decision` が `freeze_at_phase_b_reference_design` なら、checked-in surface はまだ昇格対象ではない
- current milestone では `tlul_request_loopback` を意図的にこの tier に留める
- tuned candidate の調査結果は `work/vl_ir_exp/tlul_request_loopback_vl/tlul_request_loopback_validation_*.json` 側で読む
- nearby handoff search の再生成は `python3 src/tools/search_tlul_request_loopback_handoff.py --mdir work/vl_ir_exp/tlul_request_loopback_vl` を使う
- `tlul_fifo_sync` は thin-top host-driven wrapper を使う reference-design flow
- `support_tier=thin_top_reference_design`、`acceptance_gate=thin_top_edge_parity_v1`
- checked-in `1,0` edge sequence について、host-owned `clk/reset` 証明と host/CPU/GPU parity residual が internal-only まで揃ったことを読む
- ただし current milestone の supported source of truth に昇格したとは読まない
- `thin_top_supported_v1` は proposal であって、まだ current status surface ではない

## 3. Stock-Verilator diagnostic artifacts

調査や比較に使うが、supported status の single source of truth ではないもの。

- `work/vl_ir_exp/<design>_vl/`
- `work/second_target_feasibility_audit.json`
- `work/rtlmeter_ready_scoreboard.json`
- `work/rtlmeter_expansion_branch_audit.json`
- `vl_phase_analysis.json`
- `vl_classifier_report.json`
- `vl_classifier_audit.json`
- `vl_kernel_manifest.json`
- `vl_hybrid_compare*.json`
- raw state dump / trace JSON

意味:

- Phase B/C の診断
- 2 本目 supported target を今の ownership model で広げるかどうかの mechanism audit
- compare / trace / ABI probe / placement classifier / classifier audit の補助証拠
- supported / unsupported の最終判定そのものではない

## 4. Legacy sim-accel status

legacy runner の集約 JSON はここに置く。

- `output/legacy_validation/veer_family_gpu_toggle_validation.json`
- `output/legacy_validation/xuantie_family_gpu_toggle_validation.json`

意味:

- sim-accel / RTLMeter 系 runner の結果
- stock-Verilator hybrid の supported 状態とは別系統

## 5. Campaign comparison artifacts

minimum goal の status surface ではないが、real campaign goal を測るための checked-in artifact。

- `output/validation/socket_m1_cpu_baseline_validation.json`
- `output/validation/socket_m1_time_to_threshold_comparison.json`
- `output/validation/tlul_fifo_sync_cpu_baseline_validation.json`
- `output/validation/tlul_fifo_sync_time_to_threshold_comparison.json`
- `output/validation/tlul_request_loopback_cpu_baseline_validation.json`
- `output/validation/tlul_request_loopback_time_to_threshold_comparison.json`
- `output/validation/tlul_err_cpu_baseline_validation.json`
- `output/validation/tlul_err_time_to_threshold_comparison.json`
- `output/validation/tlul_sink_cpu_baseline_validation.json`
- `output/validation/tlul_sink_time_to_threshold_comparison.json`
- `output/validation/tlul_socket_1n_cpu_baseline_validation.json`
- `output/validation/tlul_socket_1n_time_to_threshold_comparison.json`
- `work/campaign_speed_scoreboard.json`
- `work/campaign_next_kpi_audit.json`
- `work/campaign_speed_scoreboard_active.json`
- `work/campaign_next_kpi_active.json`

意味:

- `socket_m1` の normal-sim baseline
- `socket_m1` の hybrid vs baseline `time-to-threshold` comparison
- `tlul_fifo_sync` の normal-sim baseline
- `tlul_fifo_sync` の hybrid vs baseline `time-to-threshold` comparison
- `tlul_request_loopback` の normal-sim baseline
- `tlul_request_loopback` の hybrid vs baseline `time-to-threshold` comparison
- `tlul_err` の normal-sim baseline
- `tlul_err` の hybrid vs baseline `time-to-threshold` comparison
- `tlul_sink` の normal-sim baseline
- `tlul_sink` の hybrid vs baseline `time-to-threshold` comparison
- `tlul_socket_1n` の normal-sim baseline
- `tlul_socket_1n` の hybrid vs baseline `time-to-threshold` comparison
- comparison 群を集約した machine-readable scoreboard
- 「通常 sim より早く coverage target を満たせるか」を測る campaign artifact
- policy gate を反映した current active campaign line

読み方:

- `socket_m1_time_to_threshold_comparison.json` が first campaign-speed source of truth
- minimum technical goal ではなく campaign goal の根拠として読む
- current v1 comparison では `campaign_threshold.kind=toggle_bits_hit`, `value=3` で
  `winner=hybrid`, `speedup_ratio≈15.06` が checked-in artifact になった
- `tlul_fifo_sync_time_to_threshold_comparison.json` は second campaign surface の checked-in artifact で、
  current v1 result は `winner=hybrid`, `speedup_ratio≈1.16`
- `tlul_request_loopback_time_to_threshold_comparison.json` は third campaign surface の checked-in artifact で、
  current active result は `winner=hybrid`, `speedup_ratio≈4.87`
- `tlul_err_time_to_threshold_comparison.json` は fourth campaign surface の checked-in artifact で、
  current active result は `winner=hybrid`, `speedup_ratio≈14.06`
- `tlul_sink_time_to_threshold_comparison.json` は fifth campaign surface の checked-in artifact で、
  current active result は `winner=hybrid`, `speedup_ratio≈10.42`
- `tlul_socket_1n_time_to_threshold_comparison.json` は sixth campaign surface の checked-in artifact で、
  current active result は `winner=hybrid`, `speedup_ratio≈8.05`
- `tlul_fifo_async_time_to_threshold_comparison.json` は seventh campaign surface の checked-in artifact で、
  current active result は `winner=hybrid`, `speedup_ratio≈11.23`
- `xbar_main_time_to_threshold_comparison.json` は eighth campaign surface の checked-in artifact で、
  current active result は `winner=hybrid`, `speedup_ratio≈12.66`
- `xbar_peri_time_to_threshold_comparison.json` は ninth campaign surface の checked-in artifact で、
  current active result は `winner=hybrid`, `speedup_ratio≈11.70`
- `*_threshold5.json` 群は candidate-only artifact であり、current checked-in source of truth ではない
- threshold5 candidate では `socket_m1` が `speedup_ratio≈22.53`、`tlul_fifo_sync` が `≈1.20` まで伸びたが、
  `work/campaign_next_kpi_audit_threshold5.json` でも recommendation はなお `stronger_thresholds`
- ただしこれは still `thin_top_reference_design` 上の 2 本目比較であり、
  repo-wide campaign closure ではなく「2 design / v1 threshold」までの前進として読む
- `work/campaign_speed_scoreboard.json` は historical な 2-surface aggregate で、
  current active line ではなく threshold-policy 導入前の snapshot として読む
- `work/campaign_next_kpi_audit.json` は threshold 強化を検討していた時点の historical next-KPI recommendation を返す
- current checked-in recommendation は `work/campaign_next_kpi_active.json` の `recommended_next_kpi=broader_design_count` で、
  根拠は active design-specific v2 line で 9 本とも hybrid 勝ちしており、
  weakest win (`tlul_fifo_sync`) も `≈2.64x` を維持していること
- `work/campaign_threshold_candidate_matrix.json` は checked-in v1 と candidate threshold 群の promote 判断を返し、
  現在は `recommended_action=keep_current_threshold_and_define_stronger_candidate`
- `work/campaign_threshold_headroom_experiments.json` は threshold headroom 実験の要約で、
  `socket_m1` plateau / `threshold=6 unresolved` / `tlul_fifo_sync threshold24 weak win` / `threshold25 unresolved` を固定する
- `work/tlul_fifo_sync_threshold_semantics_audit.json` は `tlul_fifo_sync` 専用の stronger-threshold boundary で、
  `1` は strongest positive case (`≈2.64x`)、checked-in `1,0` は still hybrid win、`1,0,1` に伸ばすと baseline win に反転することを固定する
- `work/campaign_threshold_policy_options.json` は checked-in common v1 / common threshold5 /
  design-specific minimal-progress candidate を並べて、
  campaign v2 で design-specific semantics を許すかどうかの machine-readable choice を返す
- `config/campaign_threshold_policies/index.json` はその scenario 定義の source of truth
- `config/campaign_threshold_policies/selection.json` は `profile_name`, `allow_per_target_thresholds`, `require_matching_thresholds` を持つ checked-in policy switch
- `work/campaign_threshold_policy_gate.json` は `policy_options` と `selection` を合成した current active policy gate で、
  いま採用中の threshold line を machine-readable に返す
- 現在の checked-in selection は `profile_name=per_target_ready`, `allow_per_target_thresholds=true`, `require_matching_thresholds=false` なので、
  active policy は design-specific v2 line である
- `work/campaign_speed_scoreboard_active.json` はその active gate が実際に選んだ comparison 群の scoreboard
- `work/campaign_next_kpi_active.json` はその active scoreboard に対する next-KPI recommendation
- `work/campaign_threshold_policy_preview.json` は 2 軸 policy matrix の差分 artifact で、
  current selection がすでに `broader_design_count` を返し、
  `allow_per_target_thresholds` を戻すと common v1 + `stronger_thresholds` に落ち、
  さらに `require_matching_thresholds` まで戻すと `stabilize_existing_surfaces` に落ちることを固定する
- `work/campaign_policy_decision_readiness.json` は policy decision artifact として、
  policy が already checked-in であることを返す。`active task` は policy-switch 時点の historical field として読む
- `work/campaign_policy_change_impact.json` は current checked-in line と candidate branch の before/after diff artifact で、
  いまは current design-specific v2 line から戻したときに design count がどう縮むかを固定する
- `work/campaign_threshold_policy_profiles.json` は named policy profile 比較 artifact で、
  `common_v1_hold` / `per_target_blocked` / `per_target_ready` を固定名で比較しつつ、current selection が `per_target_ready` だと返す
- `work/campaign_third_surface_candidates.json` は legacy file name のまま active policy 下で次の comparison surface 候補を rank し、
  現在は empty で、current ready-for-campaign pool に未選択候補が残っていないことを返す
- `work/campaign_checkpoint_readiness.json` は current active line が first checkpoint と呼べるかを要約する artifact で、
  いまは `cross_family_checkpoint_ready`、つまり surface 数・margin・family diversity が first checkpoint を満たし、
  active line が ready pool 全体を覆っていると返す
- `work/campaign_post_checkpoint_axes.json` はその next-axis decision を machine-readable に固定する artifact で、
  現在は `recommended_next_axis=broaden_non_opentitan_family`、`recommended_family=XuanTie`、fallback は `VeeR`
- `work/campaign_non_opentitan_entry.json` は first non-OpenTitan deliverable shape を固定する artifact で、
  現在は `recommended_family=XuanTie`、`recommended_entry_mode=family_pilot`
- `work/campaign_non_opentitan_entry_readiness.json` はその entry shape が current workspace で実行可能かを固定する artifact で、
  現在は `readiness=legacy_family_pilot_failed_but_single_surface_override_ready`、reason は `legacy_family_pilot_failed_but_stock_verilator_single_surface_bootstrap_exists`
- つまり `output/legacy_validation/xuantie_family_gpu_toggle_validation.json` が `XuanTie + family_pilot` の negative source of truth である一方、
  `work/xuantie_e902_gpu_cov_gate_stock_verilator_cc_bootstrap.json` と `work/xuantie_e906_gpu_cov_gate_stock_verilator_cc_bootstrap.json` が `single_surface` override の ready source of truth になっている
- `work/campaign_non_opentitan_override_candidates.json` はその override branch の first design を固定する artifact で、
  現在は `recommended_design=XuanTie-E902`、`fallback_design=XuanTie-E906`、かつ `XuanTie-E902` は checked-in trio (`stock_hybrid / cpu_baseline / comparison`) と `winner=hybrid` を持つ
  `XuanTie-E906` は default checked-in trio では `comparison_ready=false` だが、`best_candidate_variant_path=output/validation/xuantie_e906_time_to_threshold_comparison_threshold2.json` で candidate-only `winner=hybrid` を持つ
- `work/xuantie_e906_case_variants.json` は E906 の known workload sweep を固定する artifact で、
  現在は `cmark / hello / memcpy` 全部が `bits_hit=2` で、`status=default_gate_blocked_across_known_case_pats`
- `work/xuantie_e906_threshold_options.json` は E906 の numeric threshold options を固定する artifact で、
  現在は `status=threshold2_is_strongest_ready_numeric_gate`、`threshold=2` が strongest ready gate、`3..8` は blocked
- `work/campaign_non_opentitan_entry_profiles.json` はその branch を named profile に落とす artifact で、
  現在は current=`xuantie_single_surface_e902`、alternate hold profile=`xuantie_family_pilot_hold`
- `work/campaign_non_opentitan_entry_gate.json` は current selection の active outcome を返す artifact で、
  現在の current selection は `status=single_surface_trio_ready`
- `work/campaign_non_opentitan_seed_status.json` は checkpoint readiness と current XuanTie selection を 1 枚に圧縮する artifact で、
  現在は `status=ready_to_accept_selected_seed`
- `work/campaign_real_goal_acceptance_profiles.json` は checkpoint / seed acceptance を named profile に落とす artifact で、
  現在は `accept_checkpoint_and_seed` が accepted、`accept_checkpoint_only` が partial、`hold_checkpoint_and_seed` が hold
- `work/campaign_real_goal_acceptance_gate.json` は current checked-in acceptance state を返す artifact で、
  現在は `status=accepted_checkpoint_and_seed`、つまり OpenTitan 9-surface checkpoint と `XuanTie-E902` seed が current campaign baseline として checked-in されている
- `work/campaign_xuantie_breadth_status.json` は acceptance 後の XuanTie breadth decision を 1 枚に圧縮する artifact で、
  現在は `status=decide_threshold2_promotion_vs_non_cutoff_default_gate`
- `work/campaign_xuantie_breadth_profiles.json` はその E906 breadth branch を named profile に落とす artifact で、
  現在は current=`e906_candidate_only_threshold2`、historical hold=`e906_default_gate_hold`、blocked alternative=`xuantie_family_pilot_recovery`
- `work/campaign_xuantie_breadth_gate.json` は current selection の active outcome を返す artifact で、
  現在の current selection は `status=candidate_only_ready`
- `work/campaign_xuantie_breadth_acceptance_profiles.json` は selected breadth step の acceptance decision を named profile に落とす artifact で、
  現在は current=`accept_selected_xuantie_breadth`、hold=`hold_selected_xuantie_breadth`
- `work/campaign_xuantie_breadth_acceptance_gate.json` は current breadth acceptance state を返す artifact で、
  現在は `status=accepted_selected_xuantie_breadth`、つまり `XuanTie-E906 threshold2` line が checked-in breadth baseline として受け入れ済み
- `work/campaign_non_opentitan_breadth_axes.json` は E902+E906 accepted baseline の次を圧縮する artifact で、
  現在は `status=decide_continue_xuantie_breadth_vs_open_fallback_family`、remaining same-family designs は `XuanTie-C906` / `XuanTie-C910`、fallback family は `VeeR`
- `work/campaign_non_opentitan_breadth_profiles.json` はその post-E906 branch を named profile 比較に落とす artifact で、
  現在は current=`xuantie_continue_same_family`、ready alternative=`open_veer_fallback_family`
- `work/campaign_non_opentitan_breadth_gate.json` は current checked-in post-E906 breadth selection の active outcome を返す artifact で、
  現在は `status=continue_same_family_ready`、つまり active non-OpenTitan breadth line は same-family continuation
- `work/campaign_non_opentitan_breadth_branch_candidates.json` はその open branch を current repo state で rank する artifact で、
  現在は `status=recommend_same_family_first`、recommended profile=`xuantie_continue_same_family`、recommended first design=`XuanTie-C906`
- `work/campaign_xuantie_same_family_step.json` は selected same-family branch の最初の concrete design step を圧縮する artifact で、
  現在は `status=decide_selected_same_family_design_candidate_only_vs_new_default_gate`、selected design=`XuanTie-C906`、candidate threshold=`5`
- `work/campaign_xuantie_same_family_profiles.json` はその selected same-family step を named profile 比較に落とす artifact で、
  現在は current=`c906_candidate_only_threshold5`、historical hold=`c906_default_gate_hold`
- `work/campaign_xuantie_same_family_gate.json` は current checked-in same-family step selection の active outcome を返す artifact で、
  現在は `status=candidate_only_ready`
- `work/campaign_xuantie_same_family_acceptance_gate.json` は current checked-in same-family step の acceptance state を返す artifact で、
  現在は `status=accepted_selected_same_family_step`、つまり `XuanTie-C906 threshold5` line は checked-in same-family breadth evidence として受け入れ済み
- `work/campaign_xuantie_same_family_next_axes.json` は accepted `XuanTie-C906` same-family step の次を圧縮する artifact で、
  現在は `status=decide_continue_to_remaining_same_family_design_vs_open_fallback_family`、remaining same-family design=`XuanTie-C910`、fallback family=`VeeR`
- `work/campaign_xuantie_c910_runtime_status.json` は `XuanTie-C910` を実際に開いた後の blocker を圧縮する artifact で、
  現在は `status=decide_hybrid_runtime_debug_vs_open_veer_fallback_family`、CPU baseline は `ok`、`O0` low-opt rebuild は `llc` abort、`O1` low-opt trace も `before_cuModuleLoad` で止まり、offline `ptxas` probe も `180s` timeout で cubin 未生成
- `work/campaign_xuantie_c910_runtime_gate.json` は current checked-in C910 runtime profile selection の active outcome を返す artifact で、
  現在は `status=open_fallback_family_ready`、つまり current checked-in state は same-family runtime debug branch ではなく `VeeR` fallback branch を採用済み
- `work/campaign_xuantie_c910_runtime_profiles.json` はその C910 runtime branch を named profile 比較に落とす artifact で、
  現在は current=`open_veer_fallback_family`、ready alternatives=`debug_c910_hybrid_runtime`,`open_veer_fallback_family`、recommended=`open_veer_fallback_family`
  summary には `debug_tactic_recommended_next_tactic=open_veer_fallback_family` が載る
- `work/campaign_xuantie_c910_split_phase_trial.json` は split-phase PTX/module-first trial の実測を固定する artifact で、
  現在は `status=timed_out_before_cuModuleLoad`、`returncode=137`、last stage=`before_cuModuleLoad`
- `work/campaign_xuantie_c910_debug_tactics.json` は accepted runtime-debug branch の下で次の concrete tactic を圧縮する artifact で、
  現在は `status=prefer_fallback_family_after_split_phase_trial_failed`、recommended=`open_veer_fallback_family`、fallback=`deeper_c910_cubin_debug`
- `work/campaign_veer_fallback_candidates.json` は selected fallback family の first concrete design choice を圧縮する artifact で、
  現在は `status=recommend_first_veer_single_surface_candidate`、recommended=`VeeR-EH1`、fallback=`VeeR-EH2`
- `work/campaign_veer_first_surface_step.json` は accepted `VeeR-EH1` より前の historical first-surface decision packet で、
  `status=decide_veer_eh1_candidate_only_vs_new_default_gate`、
  default `threshold=8` line unresolved と `threshold=5` line hybrid win (`≈3.37x`) を固定する
- `work/campaign_veer_first_surface_gate.json` は current checked-in first VeeR profile の active outcome を返す artifact で、
  現在は `status=candidate_only_ready`
- `work/campaign_veer_first_surface_acceptance_gate.json` は current checked-in first VeeR acceptance state を返す artifact で、
  現在は `status=accepted_selected_veer_first_surface_step`、つまり `VeeR-EH1 threshold5` line は checked-in fallback-family breadth evidence として受け入れ済み
- `work/campaign_veer_next_axes.json` は accepted `VeeR-EH1` line の次を圧縮する artifact で、
  現在は `status=decide_continue_to_remaining_veer_design`、recommended next design=`VeeR-EH2`、remaining fallback inside the family=`VeeR-EL2`
- `work/campaign_veer_same_family_step.json` は accepted `VeeR-EH1` 後の historical EH2 policy packet で、
  `status=decide_veer_eh2_candidate_only_vs_new_default_gate`、
  default `threshold=8` line unresolved と `threshold=4` line hybrid win (`≈2.97x`) を固定する
- `work/campaign_veer_same_family_gate.json` は current checked-in VeeR same-family profile の active outcome を返す artifact で、
  現在は `status=candidate_only_ready`
- `work/campaign_veer_same_family_acceptance_gate.json` は current checked-in VeeR same-family acceptance state を返す artifact で、
  現在は `status=accepted_selected_veer_same_family_step`、つまり `VeeR-EH2 threshold4` line は checked-in same-family breadth evidence として受け入れ済み
- `work/campaign_veer_same_family_next_axes.json` は accepted `VeeR-EH2` line の次を圧縮する artifact で、
  現在は `status=decide_continue_to_remaining_veer_design`、recommended next design=`VeeR-EL2`
- `work/campaign_veer_final_same_family_step.json` は accepted `VeeR-EH2` 後の current EL2 policy packet で、
  現在は `status=decide_veer_el2_candidate_only_vs_new_default_gate`、
  default `threshold=8` line は unresolved、`threshold=6` line は `winner=hybrid` (`≈2.78x`)
- `work/campaign_veer_final_same_family_gate.json` は current checked-in final VeeR same-family profile の active outcome を返す artifact で、
  現在は `status=candidate_only_ready`
- `work/campaign_veer_final_same_family_acceptance_gate.json` は current checked-in final VeeR same-family acceptance state を返す artifact で、
  現在は `status=accepted_selected_veer_final_same_family_step`、つまり `VeeR-EL2 threshold6` line は checked-in final same-family breadth evidence として受け入れ済み
- `work/campaign_veer_post_family_exhaustion_axes.json` は accepted `VeeR-EL2` 後の next non-VeeR family を圧縮する artifact で、
  現在は `status=decide_open_next_non_veer_family_after_veer_exhaustion`、recommended family=`XiangShan`、fallback=`OpenPiton`
- `work/xiangshan_gpu_cov_stock_verilator_cc_bootstrap.json` は XiangShan first surface の stock-Verilator bootstrap artifact で、
  現在は `status=ok`、`cpp_source_count=5`、`cpp_include_count=1`
- `output/validation/xiangshan_cpu_baseline_validation.json` は XiangShan first surface の CPU baseline artifact で、
  現在は `status=ok`、`bits_hit=2`、default `toggle_bits_hit >= 8` は unresolved
- `work/campaign_xiangshan_first_surface_status.json` は XiangShan first surface の active blocker を圧縮する artifact で、
  現在は `status=ready_to_finish_xiangshan_first_trio`、
  current branch source=`campaign_vortex_first_surface_gate`、`gpu_module.module_format=cubin`、
  smoke の last stage=`after_cleanup`
- `work/xiangshan_ptxas_probe.json` は XiangShan first surface の cheap offline cubin-first probe artifact で、
  現在は `status=timed_out`、`timeout_seconds=180`、cubin は未生成
- `work/campaign_xiangshan_vortex_branch_resolution.json` は XiangShan/Vortex の reopen loop を 1 本の current tactic に解決する artifact で、
  現在は `status=avoid_xiangshan_vortex_reopen_loop_keep_current_xiangshan_branch`、
  recommended=`deeper_xiangshan_cubin_first_debug`、heavier fallback=`deeper_vortex_tls_lowering_debug`
- `work/xiangshan_ptxas_compile_only_probe.json` は XiangShan deeper cubin-first line の first packaging probe artifact で、
  現在は `status=ok`、`ptxas --compile-only -O0` が通り、relocatable object を出す
- `work/xiangshan_compile_only_smoke_trace.log` はその relocatable object を直接 load した trace で、
  現在は `after_cuModuleLoad` まで進むが `device kernel image is invalid`
- `work/xiangshan_nvlink_smoke_trace.log` は `nvlink` packaged cubin の trace で、
  現在は `after_cuModuleLoad` まで進むが `named symbol not found`
- `work/xiangshan_fatbin_smoke_trace.log` は `fatbinary` packaged module の trace で、
  現在は `after_cuModuleLoad` まで進むが `device kernel image is invalid`
- `work/xiangshan_nvcc_dlink_smoke_trace.log` は `nvcc -dlink -fatbin` packaged module の trace で、
  現在は `after_cuModuleLoad` まで進むが `named symbol not found`
- `work/xiangshan_fatbinary_device_c_probe.fatbin` と
  `work/xiangshan_fatbinary_device_c_link_probe.fatbin` は `fatbinary --device-c` packaging probe artifact で、
  現在はどちらも `vl_eval_batch_gpu` symbol を保持する
- `work/xiangshan_fatbinary_device_c_probe_smoke_trace.log` と
  `work/xiangshan_fatbinary_device_c_link_probe_smoke_trace.log` はその `device-c` packaged module の trace で、
  現在はどちらも `after_cuModuleLoad` まで進むが `device kernel image is invalid`
- `work/xiangshan_nvlink_probe.cubin` と `work/xiangshan_nvcc_dlink.fatbin` は current executable-link packaging probe artifact で、
  現在はどちらも tiny (`760B` / `840B`) かつ symbol-less、resource usage も `GLOBAL:0`
- `work/xiangshan_ptx_fatbin_probe.fatbin` と `work/xiangshan_ptx_fatbin_probe_smoke_trace.log` は current PTX-JIT packaging probe artifact で、
  現在は `before_cuModuleLoad` で stall し、bounded run では timeout する
- `work/xiangshan_nvcc_device_link_probe.json` は XiangShan の official `nvcc --device-c PTX -> --device-link --cubin` probe artifact で、
  現在は compile=`ok`、link=`ok`、`object_kernel_symbol_present=true`、`linked_kernel_symbol_present=true`
- `work/xiangshan_nvcc_device_link_from_ptx_smoke_trace.log` はその official linked cubin の runtime trace で、
  現在は `after_cleanup` まで進み `ok`
- `work/campaign_xiangshan_deeper_debug_status.json` は current deeper XiangShan packaging line を圧縮する artifact で、
  現在は `status=ready_to_finish_xiangshan_first_trio`、
  recommended=`finish_xiangshan_stock_hybrid_validation_and_compare_gate_policy`、fallback=`deeper_vortex_tls_lowering_debug`
- `output/validation/xiangshan_stock_hybrid_validation.json` と
  `output/validation/xiangshan_time_to_threshold_comparison.json` は XiangShan default trio artifact で、
  現在は stock-hybrid=`ok` だが default `toggle_bits_hit >= 8` line は unresolved
- `output/validation/xiangshan_time_to_threshold_comparison_threshold2.json` は XiangShan first candidate-only comparison artifact で、
  現在は `winner=hybrid`、`speedup_ratio≈3.13x`
- `work/campaign_xiangshan_first_surface_step.json` は XiangShan first-surface policy step を圧縮する artifact で、
  現在は `status=decide_xiangshan_candidate_only_vs_new_default_gate`
- `work/campaign_xiangshan_first_surface_gate.json` は current checked-in XiangShan first-surface profile の active outcome を返す artifact で、
  現在は `status=candidate_only_ready`
- `work/campaign_xiangshan_first_surface_acceptance_gate.json` は current checked-in XiangShan first-surface acceptance state を返す artifact で、
  現在は `status=accepted_selected_xiangshan_first_surface_step`、つまり `threshold=2` line は reopened fallback-family breadth evidence として受け入れ済み
- `work/openpiton_gpu_cov_stock_verilator_cc_bootstrap.json` は OpenPiton first surface の stock-Verilator bootstrap artifact で、
  現在は `status=ok`、`cpp_source_count=1`
- `output/validation/openpiton_cpu_baseline_validation.json` は OpenPiton first surface の CPU baseline artifact で、
  現在は `status=ok`、`bits_hit=8`、default `toggle_bits_hit >= 8` を満たす
- `output/validation/openpiton_stock_hybrid_validation.json` は OpenPiton first surface の stock-hybrid artifact で、
  現在は checked-in default shape=`1x1`、`status=ok`、`bits_hit=8`
- `output/validation/openpiton_time_to_threshold_comparison.json` は OpenPiton first surface の comparison artifact で、
  現在は `comparison_ready=true`、`winner=hybrid`、`speedup_ratio≈1.56x`
- `work/campaign_openpiton_first_surface_step.json` は OpenPiton fallback first surface の current policy step を圧縮する artifact で、
  現在は `status=ready_to_accept_openpiton_default_gate`
- `work/campaign_openpiton_first_surface_gate.json` は current checked-in OpenPiton first-surface profile の active outcome を返す artifact で、
  現在は `status=default_gate_ready`
- `work/campaign_openpiton_first_surface_acceptance_gate.json` は current checked-in OpenPiton first-surface acceptance state を返す artifact で、
  現在は `status=accepted_selected_openpiton_first_surface_step`、つまり `OpenPiton` default-gate line は checked-in next-family breadth evidence として受け入れ済み
- `work/campaign_post_openpiton_axes.json` は accepted `OpenPiton` 後の next family を圧縮する artifact で、
  現在は `status=decide_open_next_family_after_openpiton_acceptance`、recommended family=`BlackParrot`、fallback=`XiangShan`
- `work/campaign_blackparrot_first_surface_step.json` は OpenPiton 後に開いた `BlackParrot` first surface の current outcome を圧縮する artifact で、
  現在は `status=blackparrot_candidate_only_baseline_win`、つまり checked-in candidate-only line でも baseline loss
- `work/campaign_post_blackparrot_axes.json` は `BlackParrot` baseline loss 後の next family を圧縮する artifact で、
  現在は `status=decide_open_next_family_after_blackparrot_baseline_loss`、recommended family=`Vortex`、fallback=`XiangShan`
- `work/vortex_gpu_cov_stock_verilator_cc_bootstrap.json` は Vortex first surface の stock-Verilator bootstrap artifact で、
  現在は `status=ok`、`cpp_source_count=1`
- `output/validation/vortex_cpu_baseline_validation.json` は Vortex first surface の CPU baseline artifact で、
  現在は `status=ok`、`bits_hit=4`、default `toggle_bits_hit >= 8` は unresolved
- `output/validation/vortex_stock_hybrid_validation.json` と
  `output/validation/vortex_time_to_threshold_comparison.json` は Vortex first surface の official trio artifact で、
  現在は default `toggle_bits_hit >= 8` が unresolved
- `output/validation/vortex_time_to_threshold_comparison_threshold4.json` は Vortex first surface の checked-in candidate-only comparison artifact で、
  現在は `winner=hybrid`、`speedup_ratio≈1.07x`
- `work/campaign_vortex_first_surface_status.json` は Vortex first surface の branch status artifact で、
  現在は `status=ready_to_finish_vortex_first_trio`
- `work/campaign_vortex_first_surface_gate.json` は current checked-in Vortex first-surface branch profile の active outcome を返す artifact で、
  現在は `status=vortex_gpu_build_recovered_ready_to_finish_trio`、つまり checked-in branch は `debug_vortex_tls_lowering`
- `work/campaign_vortex_first_surface_step.json` は Vortex first surface の current policy question を返す artifact で、
  現在は `status=decide_vortex_candidate_only_vs_new_default_gate`
- `work/campaign_vortex_first_surface_policy_gate.json` は selected Vortex policy profile の active outcome を返す artifact で、
  現在は `status=candidate_only_ready`、selected profile は `vortex_candidate_only_threshold4`
- `work/campaign_vortex_first_surface_acceptance_gate.json` は selected Vortex policy line の acceptance artifact で、
  現在は `status=accepted_selected_vortex_first_surface_step`
- `work/campaign_vortex_first_surface_profiles.json` は named Vortex branch profile の比較 artifact で、
  現在は current=`debug_vortex_tls_lowering`、recommended=`debug_vortex_tls_lowering`
- `work/campaign_vortex_deeper_debug_status.json` は current deeper Vortex line を圧縮する artifact で、
  現在は `status=ready_for_vortex_dpi_wrapper_abi_debug`、
  temporary TLS-slot bypass で `llc` は抜けるが `ptxas` は GPU-reachable `mem_access` DPI wrapper ABI mismatch で止まる historical deeper line を保持する
- `work/campaign_vortex_debug_tactics.json` は checked-in Vortex debug branch の下で next concrete tactic を圧縮する artifact で、
  現在は `status=vortex_first_surface_already_accepted`、recommended=`decide_post_vortex_family_axes_after_accepting_vortex`
- `work/campaign_post_vortex_axes.json` は accepted `Vortex` 後の next family axis を返す artifact で、
  現在は `status=decide_open_next_family_after_vortex_acceptance`、recommended family=`Caliptra`、fallback=`Example`
- `work/caliptra_gpu_cov_stock_verilator_cc_bootstrap.json` は Caliptra first surface の stock-Verilator bootstrap artifact で、
  現在は `status=ok`
- `output/validation/caliptra_cpu_baseline_validation.json` は Caliptra first surface の CPU baseline artifact で、
  現在は `status=ok`、`bits_hit=8`、default `toggle_bits_hit >= 8` を満たす
- `output/validation/caliptra_stock_hybrid_validation.json` は Caliptra first surface の historical stock-hybrid artifact で、
  現在は GPU module artifact 未生成のまま走った error record として読み、current blocker 自体はここではなく build log 側で読む
- `work/campaign_caliptra_first_surface_status.json` は Caliptra first surface の current branch status artifact で、
  現在は `status=decide_caliptra_tls_lowering_debug_vs_open_example_fallback`、
  bootstrap / CPU baseline は `ok` だが GPU codegen は `llc` の Verilated TLS lowering で blocked
- `work/campaign_caliptra_debug_tactics.json` は checked-in Caliptra line の next concrete tactic を圧縮する artifact で、
  現在は `status=ready_for_deeper_caliptra_split_m_axi_if0_first_store_compilable_branch1_load_provenance_nonconstant_loaded_byte_dependent_store_source_bits_runtime_fault_debug`、
  `ptxas --compile-only -O0` は `vl_eval_batch_gpu` を含む relocatable object を生成でき、
  checked-in cubin も `cuModuleLoad` までは通る一方、
  stack-limit probe では driver が `523712` までは受けるが `523744+` は拒否し、
  kernel 自体は `LOCAL_SIZE_BYTES=564320` を要求して、`523712` で run しても
  `before_first_kernel_launch` で `invalid argument` のまま。
  ただし `work/caliptra_split_phase_probe/vl_kernel_manifest.json` は split launch sequence を固定し、
  current split line では `first_store_ret_trunc` が still fault する一方、`first_store_zero_data_ret_trunc` と
  `first_store_one_data_ret_trunc` は clean、さらに `first_store_branch1_load_ret_trunc` は still fault し、
  `first_store_branch1_load_zero_store_ret_trunc` は clean、`first_store_branch1_load_mask1_ret_trunc` と
  `first_store_branch1_predicated01_ret_trunc`、`first_store_branch1_selp_const1_ret_trunc` に加えて
  `first_store_masked_data_ret_trunc` も still fault する。一方で
  `first_store_branch1_load_dead_mask_const1_ret_trunc` と
  `first_store_branch1_selp_same_const1_ret_trunc` は clean、さらに
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
  `first_store_branch1_selp_same_const257_ret_trunc` と
  `first_store_branch1_load_mask2_ret_trunc` と
  `first_store_branch1_load_maskff_ret_trunc` と
  `first_store_branch1_load_mask3_ret_trunc` は compile timeout、
  `first_store_branch1_load_mask1_shl8_sep_reg_ret_trunc`、
  `first_store_branch1_load_mask1_sep_reg_ret_trunc`、
  `first_store_branch1_load_xor_self_zero_ret_trunc`、
  `first_store_self_load_ret_trunc`、
  `first_store_branch1_load_store_plus1_ret_trunc`、
  `first_store_branch1_load_mask1_or1_ret_trunc`、
  `first_store_branch1_load_mov_ret_trunc`
  は compile timeout なので、残ブロッカーは
  `m_axi_if__0` first store の compilable current-branch1-load-provenance nonconstant loaded-byte-dependent full-width store source bits に圧縮されている。
  truncated `%rd5` isolated variants と first-branch-merge truncation は clean だが、
  first-store truncation を戻すと runtime fault が再現するので、
  current blocker は `m_axi_if__0` helper body 全体ではなく first store path に圧縮されている
  `work/caliptra_split_phase_probe/vl_batch_gpu_split_compile_only_probe.json` は split entry kernels が
  `0 bytes stack frame` で compile-only `ok` を返す。
  さらに `work/caliptra_split_phase_probe/vl_batch_gpu_split_nvcc_device_link_probe.json` は
  official split `nvcc --device-c -> --device-link --cubin` line が `ok` で linked cubin と
  split entry symbols を残すことを示し、
  `work/caliptra_split_phase_probe/split_cubin_smoke_trace.log` は traced runtime が
  `after_first_kernel_launch` まで進んだあと `illegal memory access` で落ちる。
  さらに `work/caliptra_split_phase_probe/split_cubin_ico_smoke_trace.log` と
  `work/caliptra_split_phase_probe/split_cubin_nba_sequent_smoke_trace.log` は
  `ico` / `nba_sequent` 単体 run が `ok` であることを示し、
  `work/caliptra_split_phase_probe/split_cubin_nba_comb_smoke_trace.log` と
  `work/caliptra_split_phase_probe/split_cubin_nba_comb_block1_smoke_trace.log` /
  `work/caliptra_split_phase_probe/split_cubin_nba_comb_block8_smoke_trace.log` は
  culprit が `vl_nba_comb_batch_gpu` で small block sizes でも落ちることを示す。
  さらに `split_cubin_nba_comb_prefix330_smoke_trace.log` は `ok`、`prefix331` は failure に戻り、
  `split_cubin_nba_comb_m_axi_if0_zero_high_offsets_smoke_trace.log` /
  `split_cubin_nba_comb_m_axi_if0_ret_after_first_store_smoke_trace.log` /
  `split_cubin_nba_comb_m_axi_if0_first_half_zero_high_offsets_smoke_trace.log` /
  `split_cubin_nba_comb_m_axi_if0_min_store_only_smoke_trace.log` /
  `split_cubin_nba_comb_m_axi_if0_ret_only_smoke_trace.log` は
  `illegal memory access` のままだが、
  `split_cubin_nba_comb_prefix331_param_only_smoke_trace.log` と
  `split_cubin_nba_comb_m_axi_if0_noarg_ret_only_smoke_trace.log` と
  `split_cubin_nba_comb_m_axi_if0_b64_zero_ret_only_smoke_trace.log` は `ok`、
  `split_cubin_nba_comb_m_axi_if0_rd4_ret_only_smoke_trace.log` と
  `split_cubin_nba_comb_m_axi_if0_rd7_ret_only_smoke_trace.log` は still runtime fault、
  `split_cubin_nba_comb_m_axi_if0_rd3_small_nonzero_ret_only_smoke_trace.log` は
  `misaligned address`、一方で
  `split_cubin_nba_comb_m_axi_if0_rd3_small_aligned_nonzero_ret_only_smoke_trace.log` は
  `illegal memory access`、さらに
  `split_cubin_nba_comb_m_axi_if0_b64_synth16_ret_only_smoke_trace.log` も
  `illegal memory access` だが、
  `split_cubin_nba_comb_m_axi_if0_b64_synth16_trunc_ret_only_smoke_trace.log`、
  `split_cubin_nba_comb_m_axi_if0_rd4_trunc_ret_only_smoke_trace.log`、
  `split_cubin_nba_comb_m_axi_if0_rd7_trunc_ret_only_smoke_trace.log` は `ok` なので、
  cheap `vl_batch_gpu_split_nba_comb_m_axi_if0_b64_one_ret_only_nvcc_device_link_probe.json` と
  `vl_batch_gpu_split_nba_comb_m_axi_if0_rd1_ret_only_nvcc_device_link_probe.json` は compile timeout なので、
  current main line は `deeper_caliptra_split_m_axi_if0_composite_body_runtime_fault_debug`、
  fallback は `Example`
- `work/caliptra_nvcc_device_link_cubin_probe.json` と `work/caliptra_nvcc_device_link_fatbin_probe.json` は
  Caliptra PTX の cheap `nvcc --device-c` packaging probe artifact で、
  現在はどちらも compile step が `240s` timeout、object 未生成、link skipped なので、
  packaging swap は current main line ではない
- `work/caliptra_split_phase_probe/split_ptx_smoke_trace.log` は Caliptra split PTX smoke artifact で、
  現在は traced run が `before_cuModuleLoad` まで進み、その先の executable path が unresolved
- `work/caliptra_split_phase_probe/vl_batch_gpu_split_nvcc_device_link_probe.json` は Caliptra split PTX の
  official `nvcc --device-c -> --device-link --cubin` probe artifact で、
  現在は compile/link とも `ok`、linked cubin は `26M`、split entry kernel symbol も保持する
- `work/caliptra_split_phase_probe/split_cubin_smoke_trace.log` は Caliptra split linked-cubin smoke artifact で、
  現在は `after_first_kernel_launch` まで進み、その後 `CUDA error 700: illegal memory access`
- `work/caliptra_split_phase_probe/split_cubin_ico_smoke_trace.log` は split `vl_ico_batch_gpu` smoke artifact で、
  現在は `status=ok`
- `work/caliptra_split_phase_probe/split_cubin_nba_sequent_smoke_trace.log` は split `vl_nba_sequent_batch_gpu` smoke artifact で、
  現在は `status=ok`
- `work/caliptra_split_phase_probe/split_cubin_nba_comb_smoke_trace.log` は split `vl_nba_comb_batch_gpu` smoke artifact で、
  現在は `illegal memory access`
- `work/caliptra_split_phase_probe/split_cubin_nba_comb_block1_smoke_trace.log` と
  `work/caliptra_split_phase_probe/split_cubin_nba_comb_block8_smoke_trace.log` は
  split `vl_nba_comb_batch_gpu` の small-block smoke artifact で、
  現在は `block=1` でも `unspecified launch failure`、`block=8` でも `illegal memory access`
- `work/campaign_xiangshan_vortex_branch_resolution.json` は XiangShan/Vortex loop の historical resolver だが、
  accepted `Vortex` 後は `status=follow_post_vortex_axes_after_accepting_vortex`、recommended=`open_the_next_post_vortex_family`
- schema contract は [socket_m1_campaign_schema_packet.md](socket_m1_campaign_schema_packet.md) を参照
- proof semantics は [socket_m1_campaign_proof_matrix.md](socket_m1_campaign_proof_matrix.md) を参照
- execution order は [socket_m1_time_to_threshold_execution_packet.md](socket_m1_time_to_threshold_execution_packet.md) を参照
- next-KPI decision packet は [campaign_next_kpi_packet.md](campaign_next_kpi_packet.md) を参照

## Historical files to ignore as current status

次のような `work/` 直下の古い JSON は、現行 supported 状態の根拠として読まない。

- `work/veer_family_gpu_toggle_validation.json`
- `work/coverage_summary.json`

これらは historical / legacy artifact であり、現在の source of truth ではない。
