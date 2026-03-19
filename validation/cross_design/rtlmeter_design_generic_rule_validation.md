# RTLMeter Design Generic Rule Validation

| Design | Config | Test | Rule | Kind | Status | Notes |
|---|---|---|---|---|---|---|
| Vortex:gpu_cov:sgemm | gpu_cov | sgemm | balanced_source_general | actual_gpu_ab_c | passed | A/B/C agree; B/A wall 6.61x |
| Vortex:gpu_cov:saxpy | gpu_cov | saxpy | balanced_source_general | actual_gpu_ab_c | passed | A/B/C agree; B/A wall 6.46x |
| VeeR-EL2 | gpu_cov_gate | dhry | balanced_source_general | late_family_gate | failed | family-standard gate rerun |
| VeeR-EH1 | gpu_cov_gate | dhry | balanced_source_general | late_family_gate | failed | family-standard gate rerun |
| VeeR-EH2 | gpu_cov_gate | cmark_iccm_mt | balanced_source_general | late_family_gate | failed | family-standard gate rerun |
| XuanTie-C906 | gpu_cov_gate | hello | balanced_source_general | post_freeze_actual_gpu_gate | passed | post-freeze gate; readiness-backed actual GPU evidence |
| XuanTie-C906 | gpu_cov_gate | cmark | balanced_source_general | post_freeze_actual_gpu_gate | passed | post-freeze gate; readiness-backed actual GPU evidence |
| XuanTie-C910 | gpu_cov_gate | hello | balanced_source_general | post_freeze_actual_gpu_gate | passed | post-freeze gate; readiness-backed actual GPU evidence |
| XuanTie-C910 | gpu_cov_gate | memcpy | balanced_source_general | post_freeze_actual_gpu_gate | passed | post-freeze gate; readiness-backed actual GPU evidence |
| XiangShan | gpu_cov_gate | hello | balanced_source_general | post_freeze_actual_gpu_gate | needs_review | post-freeze gate; readiness-backed actual GPU evidence |
| XiangShan | gpu_cov_gate | cmark | balanced_source_general | post_freeze_actual_gpu_gate | needs_review | post-freeze gate; readiness-backed actual GPU evidence |
| BlackParrot | gpu_cov_gate | hello | balanced_source_general | post_freeze_actual_gpu_gate | passed | post-freeze gate; readiness-backed actual GPU evidence |
| BlackParrot | gpu_cov_gate | cmark | balanced_source_general | post_freeze_actual_gpu_gate | passed | post-freeze gate; readiness-backed actual GPU evidence |
| OpenPiton | gpu_cov_gate | hello | balanced_source_general | post_freeze_actual_gpu_gate | passed | post-freeze gate; readiness-backed actual GPU evidence |
| OpenPiton | gpu_cov_gate | fib | balanced_source_general | post_freeze_actual_gpu_gate | passed | post-freeze gate; readiness-backed actual GPU evidence |
| Example | gpu_cov_gate | hello | balanced_source_general | post_freeze_actual_gpu_gate | passed | post-freeze gate; readiness-backed actual GPU evidence |
| Example | gpu_cov_gate | user | balanced_source_general | post_freeze_actual_gpu_gate | passed | post-freeze gate; readiness-backed actual GPU evidence |
| XuanTie-E902 | gpu_cov_gate | memcpy | balanced_source_general | post_freeze_actual_gpu_gate | passed | post-freeze gate; hit 18/18 |
| XuanTie-E906 | gpu_cov_gate | cmark | balanced_source_general | post_freeze_actual_gpu_gate | passed | post-freeze gate; hit 18/18 |

## Scoped-Out Harness Debt

| Design | Config | Test | Status | Reason |
|---|---|---|---|---|
| VeeR-EL2 | gpu_cov | dhry | scoped_out_harness_debt | Raw tb_top-based gpu_cov path remains active but falls into a pathological TEST_FAILED loop despite program_loaded=1 and reset release. |
| XuanTie-E902 | gpu_cov | memcpy | scoped_out_harness_debt | Raw timing-based tb.v sim-accel gpu_cov path stays dead; the raw gpu_cov CPU summary-path and raw gpu_cov actual GPU path both return 0/18 with all three regions dead. |
| XuanTie-E906 | gpu_cov | cmark | scoped_out_harness_debt | Raw timing-based tb.v sim-accel gpu_cov path stays dead; the raw gpu_cov CPU summary-path and raw gpu_cov actual GPU path both return 0/18 with all three regions dead. |
