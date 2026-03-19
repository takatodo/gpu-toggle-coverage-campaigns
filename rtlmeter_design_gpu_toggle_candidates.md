# RTLMeter GPU Toggle Candidate Ranking

| Design | Priority | Score | Sources | Standard | Sanity | GPU TB | Manifest | Readiness | Next step |
|---|---|---:|---:|---|---|---|---|---|---|
| VeeR-EH1 | high | 14 | 43 | True | True | True | True | ready_for_gpu_toggle | integrate VeeR-EH1 gpu_cov flow with generic baseline/pilot runner |
| VeeR-EH2 | high | 14 | 49 | True | True | True | True | ready_for_gpu_toggle | integrate VeeR-EH2 gpu_cov flow with generic baseline/pilot runner |
| VeeR-EL2 | high | 14 | 51 | True | True | True | True | ready_for_gpu_toggle | integrate VeeR-EL2 gpu_cov flow with generic baseline/pilot runner |
| XuanTie-E902 | high | 13 | 124 | True | True | True | True | ready_for_gpu_toggle | integrate XuanTie-E902 gpu_cov flow with generic baseline/pilot runner |
| Example | high | 11 | 1 | True | True | True | True | ready_for_gpu_toggle | integrate Example gpu_cov flow with generic baseline/pilot runner |
| XuanTie-E906 | high | 11 | 250 | True | True | True | True | ready_for_gpu_toggle | integrate XuanTie-E906 gpu_cov flow with generic baseline/pilot runner |
| Vortex | high | 9 | 126 | True | True | True | True | ready_for_gpu_toggle | integrate Vortex gpu_cov flow with generic baseline/pilot runner |
| XiangShan | high | 8 | 8 | True | True | True | True | ready_for_gpu_toggle | integrate XiangShan gpu_cov flow with generic baseline/pilot runner |
| OpenPiton | medium | 5 | 250 | True | True | True | True | ready_for_gpu_toggle | integrate OpenPiton gpu_cov flow with generic baseline/pilot runner |
| XuanTie-C906 | medium | 5 | 292 | True | True | True | True | ready_for_gpu_toggle | integrate XuanTie-C906 gpu_cov flow with generic baseline/pilot runner |
| BlackParrot | medium | 5 | 320 | True | True | True | True | ready_for_gpu_toggle | integrate BlackParrot gpu_cov flow with generic baseline/pilot runner |
| XuanTie-C910 | medium | 4 | 468 | True | True | True | True | ready_for_gpu_toggle | integrate XuanTie-C910 gpu_cov flow with generic baseline/pilot runner |
| OpenTitan | low | 2 | 641 | True | True | True | True | gpu_toggle_contract_ready | add OpenTitan gpu_cov_tb and coverage_regions manifest |
| NVDLA | low | -2 | 403 | False | True | False | False | needs_gpu_cov_tb_and_manifest | add NVDLA gpu_cov_tb and coverage_regions manifest |
| Caliptra | low | -2 | 612 | True | True | False | False | needs_gpu_cov_tb_and_manifest | add Caliptra gpu_cov_tb and coverage_regions manifest |

## Recommended Next Designs

- `VeeR-EH1`: high, ready_for_gpu_toggle, source_count_small, has_standard_test, has_sanity_test, preferred_single_core_cpu_family, already_gpu_toggle_ready
- `VeeR-EH2`: high, ready_for_gpu_toggle, source_count_small, has_standard_test, has_sanity_test, preferred_single_core_cpu_family, already_gpu_toggle_ready
- `VeeR-EL2`: high, ready_for_gpu_toggle, source_count_small, has_standard_test, has_sanity_test, preferred_single_core_cpu_family, already_gpu_toggle_ready
- `XuanTie-E902`: high, ready_for_gpu_toggle, source_count_medium_small, has_standard_test, has_sanity_test, preferred_single_core_cpu_family, already_gpu_toggle_ready
- `Example`: high, ready_for_gpu_toggle, source_count_small, has_standard_test, has_sanity_test, already_gpu_toggle_ready
