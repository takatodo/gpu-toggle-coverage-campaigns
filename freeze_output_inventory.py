#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_OUT = SCRIPT_DIR / "output_inventory.json"
DEFAULT_MD_OUT = SCRIPT_DIR / "output_inventory.md"


SECTIONS: list[dict[str, Any]] = [
    {
        "title": "Canonical Decisions",
        "purpose": "Read these first. They define the frozen rule table, runtime scope, and next scope-expansion order.",
        "items": [
            ("metrics_driven_final_rule_packet.md", "Final frozen packet for the current scope."),
            ("toggle_coverage_generic_rules.md", "Frozen rule families and defaults."),
            ("design_scope_expansion_packet.md", "Next design-expansion order after the frozen scope."),
            ("runtime_runner_scope.md", "Mainline runtime runners versus scoped-out debug/raw debt."),
            ("generic_toggle_coverage_rule_plan.md", "High-level plan and current maintenance mode."),
            ("generic_toggle_coverage_rule_tasks.json", "Task-state tracker backing the plan."),
        ],
    },
    {
        "title": "Cross-Design Validation",
        "purpose": "These explain why the frozen rule family is considered valid across designs.",
        "items": [
            ("rtlmeter_design_generic_rule_validation.md", "Actual GPU and late-family gate validation summary."),
            ("rtlmeter_design_gpu_toggle_candidates.md", "Candidate ranking across RTLMeter designs."),
            ("rtlmeter_design_toggle_features.md", "Per-design feature/readiness breakdown."),
            ("rtlmeter_design_toggle_rule_assignments.md", "Per-design rule-family assignment."),
            ("metrics_driven_gpu_validation_matrix.md", "Tiered A/B/C validation matrix."),
        ],
    },
    {
        "title": "OpenTitan Slice Frozen Artifacts",
        "purpose": "Canonical OpenTitan slice outputs that feed the generic rule family and backend policy.",
        "items": [
            ("opentitan_tlul_slice_production_defaults.md", "Frozen production defaults per slice."),
            ("opentitan_tlul_slice_backend_selection.md", "Frozen backend-selection result."),
            ("opentitan_tlul_slice_convergence_freeze.md", "Convergence freeze used by rule derivation."),
            ("opentitan_tlul_slice_cpu_vs_gpu_campaign_efficiency.md", "CPU/GPU campaign efficiency summary."),
            ("opentitan_tlul_slice_execution_profiles.md", "Execution profile packet used by operator flow."),
        ],
    },
    {
        "title": "Family Readiness",
        "purpose": "Per-family bring-up and late-family readiness documents.",
        "items": [
            ("vortex_gpu_toggle_readiness.md", "Tier-2 medium-design readiness and runtime evidence."),
            ("xiangshan_gpu_toggle_enablement_plan.md", "First fallback-family bring-up plan and validation gate."),
            ("xiangshan_gpu_toggle_readiness.md", "XiangShan fallback-family readiness and in-flight runtime validation."),
            ("blackparrot_gpu_toggle_enablement_plan.md", "BlackParrot bring-up closure and next-step handoff after actual GPU validation."),
            ("blackparrot_gpu_toggle_readiness.md", "BlackParrot actual-GPU readiness and validation evidence."),
            ("veer_family_gpu_toggle_readiness.md", "VeeR family gate readiness and late-family notes."),
            ("xuantie_family_gpu_toggle_readiness.md", "XuanTie family gate readiness and raw-path debt."),
            ("veer_el2_gpu_toggle_readiness.md", "EL2-specific bring-up and raw-path notes."),
        ],
    },
    {
        "title": "Canonical Generators",
        "purpose": "Scripts that regenerate the main canonical artifacts.",
        "items": [
            ("freeze_metrics_driven_final_rule_packet.py", "Regenerates the final frozen packet."),
            ("derive_toggle_coverage_generic_rules.py", "Regenerates the frozen rule families."),
            ("freeze_design_scope_expansion.py", "Regenerates the scope-expansion packet."),
            ("freeze_runtime_runner_scope.py", "Regenerates the runtime runner boundary."),
            ("derive_rtlmeter_design_toggle_rule_assignments.py", "Regenerates per-design rule assignments."),
            ("extract_rtlmeter_design_toggle_features.py", "Regenerates per-design feature rows."),
            ("assess_rtlmeter_design_gpu_toggle_candidates.py", "Regenerates candidate ranking."),
        ],
    },
    {
        "title": "Cleanup Guides",
        "purpose": "Use these when physically reducing the top-level surface without breaking references.",
        "items": [
            ("output_cleanup_candidates.md", "Non-destructive cleanup/archive candidate list for top-level files."),
            ("freeze_output_cleanup_candidates.py", "Regenerates the cleanup/archive candidate list."),
        ],
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze a curated inventory of the canonical outputs in this directory.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args()


def main() -> int:
    ns = parse_args()
    payload = {
        "schema_version": "output-inventory-v1",
        "root": str(SCRIPT_DIR),
        "status": "curated_inventory_frozen",
        "sections": [
            {
                "title": section["title"],
                "purpose": section["purpose"],
                "items": [
                    {
                        "path": str(SCRIPT_DIR / rel),
                        "label": rel,
                        "purpose": purpose,
                    }
                    for rel, purpose in section["items"]
                ],
            }
            for section in SECTIONS
        ],
    }
    ns.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Output Inventory",
        "",
        f"- status: `{payload['status']}`",
        f"- root: `{payload['root']}`",
        "",
    ]
    for section in payload["sections"]:
        lines.extend([f"## {section['title']}", "", section["purpose"], ""])
        for item in section["items"]:
            lines.append(f"- `{item['label']}`: {item['purpose']}")
        lines.append("")
    ns.md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(ns.json_out)
    print(ns.md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
