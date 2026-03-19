# Design Scope Expansion Packet

- status: `scope_expansion_order_frozen`
- first phase focus: `(none)`
- first fallback target: `Caliptra`

## Rationale

- Do not mix ready_for_gpu_toggle families with wrapper/manifest bring-up families in the same expansion step.
- First extend actual GPU evidence across already wrapper-ready families, then introduce exactly one fallback bring-up family.

## Expansion Order

| Design | Phase | Validation | Readiness | Feature | Rule | Standard tests |
|---|---|---|---|---|---|---|
| VeeR-EH1 | already_in_scope | gate_validated_only | ready_for_gpu_toggle | wrapper_ready_general | balanced_source_general | dhry |
| VeeR-EH2 | already_in_scope | gate_validated_only | ready_for_gpu_toggle | wrapper_ready_core | balanced_source_general | cmark_iccm_mt |
| VeeR-EL2 | already_in_scope | gate_validated_only | ready_for_gpu_toggle | wrapper_ready_core | balanced_source_general | dhry |
| XuanTie-E902 | already_in_scope | actual_gpu_validated | ready_for_gpu_toggle | wrapper_ready_core | balanced_source_general | memcpy |
| Example | already_in_scope | actual_gpu_validated | ready_for_gpu_toggle | wrapper_ready_general | balanced_source_general | user |
| XuanTie-E906 | already_in_scope | actual_gpu_validated | ready_for_gpu_toggle | wrapper_ready_core | balanced_source_general | cmark |
| Vortex | already_in_scope | actual_gpu_validated | ready_for_gpu_toggle | wrapper_ready_core | balanced_source_general | sgemm |
| XiangShan | already_in_scope | actual_gpu_validated | ready_for_gpu_toggle | wrapper_ready_general | balanced_source_general | cmark |
| BlackParrot | already_in_scope | actual_gpu_validated | ready_for_gpu_toggle | wrapper_ready_core | balanced_source_general | cmark |
| OpenPiton | already_in_scope | actual_gpu_validated | ready_for_gpu_toggle | wrapper_ready_core | balanced_source_general | fib |
| XuanTie-C906 | already_in_scope | actual_gpu_validated | ready_for_gpu_toggle | wrapper_ready_core | balanced_source_general | cmark |
| XuanTie-C910 | already_in_scope | actual_gpu_validated | ready_for_gpu_toggle | wrapper_ready_core | balanced_source_general | memcpy |
| OpenTitan | already_in_scope | slice_scope_validated | gpu_toggle_contract_ready |  |  |  |
| Caliptra | phase_4_large_integration | gpu_cov_codegen_proven_not_yet_validated | gpu_cov_codegen_proven_build_scalability_blocker | generic_external_fallback |  | hello |
| NVDLA | phase_4_large_integration | not_validated_in_scope_packet | needs_gpu_cov_tb_and_manifest | generic_external_fallback |  |  |
