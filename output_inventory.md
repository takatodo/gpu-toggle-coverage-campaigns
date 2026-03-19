# Output Inventory

- status: `curated_inventory_frozen`
- root: `.`

## Canonical Decisions

Read these first. They define the frozen rule table, runtime scope, and next scope-expansion order.

- `metrics_driven_final_rule_packet.md`: Final frozen packet for the current scope.
- `toggle_coverage_generic_rules.md`: Frozen rule families and defaults.
- `design_scope_expansion_packet.md`: Next design-expansion order after the frozen scope.
- `runtime_runner_scope.md`: Mainline runtime runners versus scoped-out debug/raw debt.
- `generic_toggle_coverage_rule_plan.md`: High-level plan and current maintenance mode.
- `generic_toggle_coverage_rule_tasks.json`: Task-state tracker backing the plan.

## Cross-Design Validation

These explain why the frozen rule family is considered valid across designs.

- `rtlmeter_design_generic_rule_validation.md`: Actual GPU and late-family gate validation summary.
- `rtlmeter_design_gpu_toggle_candidates.md`: Candidate ranking across RTLMeter designs.
- `rtlmeter_design_toggle_features.md`: Per-design feature/readiness breakdown.
- `rtlmeter_design_toggle_rule_assignments.md`: Per-design rule-family assignment.
- `metrics_driven_gpu_validation_matrix.md`: Tiered A/B/C validation matrix.

## OpenTitan Slice Frozen Artifacts

Canonical OpenTitan slice outputs that feed the generic rule family and backend policy.

- `opentitan_tlul_slice_production_defaults.md`: Frozen production defaults per slice.
- `opentitan_tlul_slice_backend_selection.md`: Frozen backend-selection result.
- `opentitan_tlul_slice_convergence_freeze.md`: Convergence freeze used by rule derivation.
- `opentitan_tlul_slice_cpu_vs_gpu_campaign_efficiency.md`: CPU/GPU campaign efficiency summary.
- `opentitan_tlul_slice_execution_profiles.md`: Execution profile packet used by operator flow.

## Family Readiness

Per-family bring-up and late-family readiness documents.

- `vortex_gpu_toggle_readiness.md`: Tier-2 medium-design readiness and runtime evidence.
- `xiangshan_gpu_toggle_enablement_plan.md`: First fallback-family bring-up plan and validation gate.
- `xiangshan_gpu_toggle_readiness.md`: XiangShan fallback-family readiness and in-flight runtime validation.
- `blackparrot_gpu_toggle_enablement_plan.md`: BlackParrot bring-up closure and next-step handoff after actual GPU validation.
- `blackparrot_gpu_toggle_readiness.md`: BlackParrot actual-GPU readiness and validation evidence.
- `veer_family_gpu_toggle_readiness.md`: VeeR family gate readiness and late-family notes.
- `xuantie_family_gpu_toggle_readiness.md`: XuanTie family gate readiness and raw-path debt.
- `veer_el2_gpu_toggle_readiness.md`: EL2-specific bring-up and raw-path notes.

## Canonical Generators

Scripts that regenerate the main canonical artifacts.

- `freeze_metrics_driven_final_rule_packet.py`: Regenerates the final frozen packet.
- `derive_toggle_coverage_generic_rules.py`: Regenerates the frozen rule families.
- `freeze_design_scope_expansion.py`: Regenerates the scope-expansion packet.
- `freeze_runtime_runner_scope.py`: Regenerates the runtime runner boundary.
- `derive_rtlmeter_design_toggle_rule_assignments.py`: Regenerates per-design rule assignments.
- `extract_rtlmeter_design_toggle_features.py`: Regenerates per-design feature rows.
- `assess_rtlmeter_design_gpu_toggle_candidates.py`: Regenerates candidate ranking.

## Cleanup Guides

Use these when physically reducing the top-level surface without breaking references.

- `output_cleanup_candidates.md`: Non-destructive cleanup/archive candidate list for top-level files.
- `freeze_output_cleanup_candidates.py`: Regenerates the cleanup/archive candidate list.

