# Campaign Post-Checkpoint Axes

## Purpose

`work/campaign_checkpoint_readiness.json` が `cross_family_checkpoint_ready` になった後は、
次の論点は「もう checkpoint と呼べるか」ではなく、
**その次にどの軸へ広げるか** である。

この packet は、その post-checkpoint decision を 3 択に固定する。

- `broaden_non_opentitan_family`
- `strengthen_thresholds`
- `reopen_supported_promotion`

## Current Weak Point

現在の active line は 9 surfaces / 9 hybrid wins で、
OpenTitan `ready_for_campaign` pool を使い切っている。
ただし repo-family としてはまだ `OpenTitan` 1 family に偏っている。

source of truth:

- `work/campaign_speed_scoreboard_active.json`
- `work/campaign_checkpoint_readiness.json`
- `work/campaign_post_checkpoint_axes.json`

## Current Recommendation

checked-in recommendation は `broaden_non_opentitan_family`。

理由:

1. current ready pool は exhausted
2. active KPI はすでに `broader_design_count`
3. active repo family はまだ `OpenTitan` だけ

machine-readable artifact:

- `work/campaign_post_checkpoint_axes.json`

## First Family Recommendation

current recommended first family は `XuanTie`。

根拠:

- `*_gpu_cov_tb.sv` が 4 design 分ある
- `src/runners/run_xuantie_family_gpu_toggle_validation.py` が既にある
- 同条件の `VeeR` より design count が多い

fallback は `VeeR`。

## Next Tasks

1. current 9-surface line を first campaign-goal checkpoint baseline として固定する
2. `XuanTie` を first non-OpenTitan expansion family として採るか決める
3. 採るなら、最初の deliverable を
   - one comparison surface
   - family pilot
   のどちらにするか決める

## Non-Goals

- `strict_final_state`
- `tlul_request_loopback` promotion
- `tlul_fifo_sync` の `Tier R -> Tier S` promotion
