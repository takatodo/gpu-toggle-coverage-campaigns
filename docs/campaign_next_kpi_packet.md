# Campaign Next KPI Packet

## Purpose

この packet は、campaign line の current weakest point

- active campaign line が `socket_m1` / `tlul_fifo_sync` / `tlul_request_loopback` の 3 本まで広がった
- 3 本とも `winner=hybrid`
- ただし weakest win は依然として `tlul_fifo_sync`

という状態から、**次の KPI を何にするか**を固定するための packet である。

## Weakest Point

policy-aware な comparison loop が 3 本揃ったことで、
project は「design-specific v2 / 3 surfaces」までは進んだ。

いま一番弱い点は、

- この 3 本の active line をそのまま広げてよいのか
- それとも stronger common semantics へ戻るべきか

が文書ベースでしか決まっていないことだ。

特に current checked-in result は次である。

- `socket_m1`: `winner=hybrid`, `speedup_ratio≈22.53` at `threshold5`
- `tlul_fifo_sync`: `winner=hybrid`, `speedup_ratio≈2.64` at `seq1 threshold24`
- `tlul_request_loopback`: `winner=hybrid`, `speedup_ratio≈4.87` at `threshold2`

この時点で next KPI は threshold 値探しではなく、
**active line を 1 本広げるべきか**が論点である。

## Checked-in Decision

current checked-in decision は **broader design count under per-target v2** とする。

理由:

- active scoreboard では comparison-ready surface が 3 本ある
- `hybrid_win_count=3`
- weakest win (`tlul_fifo_sync`) も `speedup_ratio≈2.64` まで上がっている
- current checked-in policy は `per_target_ready` で、active next-KPI は `broader_design_count`

source of truth:

- [campaign_speed_scoreboard_active.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/campaign_speed_scoreboard_active.json)
- [campaign_next_kpi_active.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/campaign_next_kpi_active.json)
- [campaign_threshold_policy_gate.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/campaign_threshold_policy_gate.json)

## Historical Boundary Work

current line に至るまでの boundary work は残しておく。

historical / supporting artifacts:

- [socket_m1 hybrid threshold5](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/socket_m1_stock_hybrid_validation_threshold5.json)
- [socket_m1 baseline threshold5](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/socket_m1_cpu_baseline_validation_threshold5.json)
- [socket_m1 comparison threshold5](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/socket_m1_time_to_threshold_comparison_threshold5.json)
- [tlul_fifo_sync hybrid threshold5](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/tlul_fifo_sync_stock_hybrid_validation_threshold5.json)
- [tlul_fifo_sync baseline threshold5](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/tlul_fifo_sync_cpu_baseline_validation_threshold5.json)
- [tlul_fifo_sync comparison threshold5](/home/takatodo/gpu-toggle-coverage-campaigns/output/validation/tlul_fifo_sync_time_to_threshold_comparison_threshold5.json)
- [threshold5 scoreboard](/home/takatodo/gpu-toggle-coverage-campaigns/work/campaign_speed_scoreboard_threshold5.json)
- [threshold5 next-kpi audit](/home/takatodo/gpu-toggle-coverage-campaigns/work/campaign_next_kpi_audit_threshold5.json)
- [campaign_threshold_policy_options.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/campaign_threshold_policy_options.json)
- [campaign_threshold_policy_preview.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/campaign_threshold_policy_preview.json)
- [campaign_threshold_policy_profiles.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/campaign_threshold_policy_profiles.json)
- [campaign_policy_decision_readiness.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/campaign_policy_decision_readiness.json)

結果:

- `threshold5` 単体では next-KPI recommendation を変えられなかった
- `tlul_fifo_sync` では `seq1` が strongest positive case で、`1,0,1` 以降は baseline 優位へ反転した
- そのため current checked-in line は design-specific minimal-progress semantics を含む `per_target_ready` に切り替え済みである

## Branch Rules

### Branch A: broader design count

これが current checked-in recommendation。

条件:

- `comparison_ready_count >= 4`
- `hybrid_win_count == comparison_ready_count`
- weakest hybrid win が policy margin を超える

次の task:

1. active line を維持する
2. 次の comparison surface を意図的に 1 本選ぶ
3. その target で baseline / hybrid / comparison artifact を追加する

current recommended candidate:

- [campaign_third_surface_candidates.json](/home/takatodo/gpu-toggle-coverage-campaigns/work/campaign_third_surface_candidates.json)
- current top: `tlul_socket_1n`

### Branch B: stronger common thresholds

これは fallback branch。

条件:

- design-specific line を維持したくない
- or active line が broaden できず、threshold semantics を共通化し直す必要がある

このとき初めて、common semantics の定義へ戻る。

### Branch C: stabilize existing surfaces

比較 surface の負けや schema drift が出た場合はここへ落ちる。

## Current Recommendation

`work/campaign_next_kpi_active.json` の current checked-in recommendation は:

- `recommended_next_kpi = broader_design_count`
- `reason = current_surfaces_have_strong_hybrid_margin`

である。

## Non-goals

- `strict_final_state`
- `tlul_request_loopback` promotion
- `tlul_fifo_sync` の `Tier R -> Tier S` promotion judgement
- common stronger-threshold v3 の open-ended search

## Exit

この packet は次で fulfilled とみなす。

1. next KPI recommendation が machine-readable artifact に固定される
2. roadmap / README / docs index が同じ recommendation を指す
3. 次の具体 task が `add_next_comparison_surface` に一本化される
