# Campaign Non-OpenTitan Entry

## Purpose

`work/campaign_post_checkpoint_axes.json` が `broaden_non_opentitan_family` を返した後は、
次の論点は family 名だけでは足りない。
**最初の deliverable を `single_surface` で始めるか `family_pilot` で始めるか** を固定する必要がある。

この packet は、その first-entry shape を定義する。

## Current Recommendation

axis recommendation と current checked-in selection は今は分けて読む必要がある。

- axis recommendation:
  - family: `XuanTie`
  - entry mode: `family_pilot`
- current checked-in selection:
  - profile: `xuantie_single_surface_e902`
  - active gate: `single_surface_trio_ready`

source of truth:

- `work/campaign_post_checkpoint_axes.json`
- `work/campaign_non_opentitan_entry.json`
- `work/campaign_non_opentitan_entry_readiness.json`
- `work/campaign_non_opentitan_entry_gate.json`

## Why `family_pilot`

`XuanTie` では次が揃っている。

1. `*_gpu_cov_tb.sv` が 4 design 分ある
2. `src/runners/run_xuantie_family_gpu_toggle_validation.py` がある
3. `run_xuantie_c906_gpu_toggle_validation.py`
   と `run_xuantie_c910_gpu_toggle_validation.py` があり、family entry の下支えもある
4. `xuantie_single_surface_e902` 側には stock-hybrid / CPU-baseline / comparison の checked-in trio ができたが、
   current recommended entry shape 自体はまだ `family_pilot`

そのため、最初の non-OpenTitan deliverable は
`1 design をいきなり campaign line に入れる` より、
`family-level legacy pilot を source-of-truth 化してから 1 surface を切り出す` ほうが自然である。

fallback family は `VeeR` で、こちらも current recommendation は `family_pilot`。

## Current Readiness

current workspace では、この recommendation はそのままでは実行できない。

- `work/campaign_non_opentitan_entry_readiness.json`
- current state: `legacy_family_pilot_failed_but_single_surface_override_ready`
- `family_pilot` blocking file: `third_party/verilator/bin/verilator_sim_accel_bench`
- `single_surface` ready artifacts:
  - `work/xuantie_e902_gpu_cov_gate_stock_verilator_cc_bootstrap.json`
  - `work/xuantie_e906_gpu_cov_gate_stock_verilator_cc_bootstrap.json`
- `work/campaign_non_opentitan_override_candidates.json`
  - current recommendation: `XuanTie-E902`
  - fallback: `XuanTie-E906`
- `work/campaign_non_opentitan_entry_profiles.json`
  - current profile: `xuantie_family_pilot_hold`
  - ready alternative: `xuantie_single_surface_e902`
- `work/campaign_non_opentitan_entry_gate.json`
  - current outcome: `family_pilot_blocked`
- `output/validation/xuantie_e902_stock_hybrid_validation.json`
- `output/validation/xuantie_e902_cpu_baseline_validation.json`
- `output/validation/xuantie_e902_time_to_threshold_comparison.json`
  - `XuanTie-E902` override は already-implemented trio で、comparison は `winner=hybrid`
- `output/validation/xuantie_e906_stock_hybrid_validation.json`
- `output/validation/xuantie_e906_cpu_baseline_validation.json`
- `output/validation/xuantie_e906_time_to_threshold_comparison.json`
  - `XuanTie-E906` default trio は `comparison_ready=false`、理由は `toggle_bits_hit >= 8` を満たさないため
- `output/validation/xuantie_e906_time_to_threshold_comparison_threshold2.json`
  - ただし `XuanTie-E906` には candidate-only `threshold=2` line があり、comparison は `winner=hybrid`
- `work/xuantie_e906_case_variants.json`
  - checked-in `cmark / hello / memcpy` variant は全部 `bits_hit=2` で plateau していて、既知 workload の差し替えだけでは default gate を救えない

つまり current state はもう family 名の再議論でも entry profile switch でもなく、
`XuanTie-E902` trio を first non-OpenTitan seed として受け入れ、
`XuanTie-E906 threshold2` line を次の breadth step として受け入れた後の branch である。
その acceptance は `work/campaign_real_goal_acceptance_gate.json` が `status=accepted_checkpoint_and_seed` として固定している。
`XuanTie-E906` breadth acceptance は `work/campaign_xuantie_breadth_acceptance_gate.json` が `status=accepted_selected_xuantie_breadth` として固定している。
`family_pilot` は current axis recommendation ではあるが、checked-in breadth baseline でも active next step でもない。

## Next Tasks

1. accepted `XuanTie-E902 + XuanTie-E906 + XuanTie-C906` baseline の次は、`work/campaign_xuantie_c910_runtime_status.json` で読む
2. current branch は `XuanTie-C910` の hybrid runtime を深掘りするか、fallback family `VeeR` を開くかの判断である
3. `family_pilot` 復旧は same-family runtime debug と fallback-family branch の両方を捨てるときだけ再開する

## Non-Goals

- いきなり non-OpenTitan family を `Tier S` に上げる
- current OpenTitan 9-surface line を崩してまで breadth を急ぐ
- `strict_final_state` や promotion debt を再度 main line に戻す
