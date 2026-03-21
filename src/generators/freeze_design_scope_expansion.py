#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_OUT = SCRIPT_DIR / "design_scope_expansion_packet.json"
DEFAULT_MD_OUT = SCRIPT_DIR / "design_scope_expansion_packet.md"

CANDIDATES_JSON = SCRIPT_DIR / "rtlmeter_design_gpu_toggle_candidates.json"
FEATURES_JSON = SCRIPT_DIR / "rtlmeter_design_toggle_features.json"
ASSIGNMENTS_JSON = SCRIPT_DIR / "rtlmeter_design_toggle_rule_assignments.json"
FINAL_PACKET_JSON = SCRIPT_DIR / "metrics_driven_final_rule_packet.json"

PHASE_LABELS = {
    "already_in_scope": "already_in_scope",
    "phase_1_ready_family_actual_gpu": "phase_1_ready_family_actual_gpu",
    "phase_2_first_fallback": "phase_2_first_fallback",
    "phase_3_fallback_follow_on": "phase_3_fallback_follow_on",
    "phase_4_large_integration": "phase_4_large_integration",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _phase_for_design(
    design: str,
    readiness: str,
    already_in_scope: bool,
) -> str:
    if already_in_scope:
        return PHASE_LABELS["already_in_scope"]
    if readiness == "ready_for_gpu_toggle":
        return PHASE_LABELS["phase_1_ready_family_actual_gpu"]
    if design == "XiangShan":
        return PHASE_LABELS["phase_2_first_fallback"]
    if design in {"XuanTie-C906", "OpenPiton", "BlackParrot"}:
        return PHASE_LABELS["phase_3_fallback_follow_on"]
    return PHASE_LABELS["phase_4_large_integration"]


def _validation_status(
    design: str,
    actual_gpu_designs: set[str],
    gate_designs: set[str],
) -> str:
    if design == "OpenTitan":
        return "slice_scope_validated"
    if design in actual_gpu_designs:
        return "actual_gpu_validated"
    if design in gate_designs:
        return "gate_validated_only"
    return "not_validated_in_scope_packet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the next design-scope expansion order after the scope-limited final rule freeze."
    )
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args()


def main() -> int:
    ns = parse_args()
    candidates = _load_json(CANDIDATES_JSON)
    features = _load_json(FEATURES_JSON)
    assignments = _load_json(ASSIGNMENTS_JSON)
    final_packet = _load_json(FINAL_PACKET_JSON)

    feature_rows = {str(row["design"]): row for row in list(features.get("rows") or [])}
    assignment_rows = {str(row["design"]): row for row in list(assignments.get("rows") or [])}

    actual_gpu_designs = {
        str(row.get("design") or "").split(":")[0]
        for row in list(((final_packet.get("design_validation") or {}).get("actual_gpu_rows") or []))
    }
    actual_gpu_designs.update(
        str(row.get("design") or "").split(":")[0]
        for row in list(((final_packet.get("design_validation") or {}).get("post_freeze_expansion_rows") or []))
    )
    gate_designs = {
        str(row.get("design") or "")
        for row in list(((final_packet.get("design_validation") or {}).get("late_family_gate_rows") or []))
    }

    rows: list[dict[str, Any]] = []
    for candidate in list(candidates.get("candidates") or []):
        design = str(candidate.get("design") or "")
        feature = feature_rows.get(design, {})
        assignment = assignment_rows.get(design, {})
        readiness = str(feature.get("readiness") or candidate.get("readiness") or "")
        phase = _phase_for_design(
            design,
            readiness,
            already_in_scope=(design in actual_gpu_designs or design in gate_designs or design == "OpenTitan"),
        )
        row = {
            "design": design,
            "priority": str(candidate.get("priority") or ""),
            "candidate_score": int(candidate.get("score") or feature.get("candidate_score") or 0),
            "readiness": readiness,
            "feature_family": str(feature.get("feature_family") or ""),
            "phase": phase,
            "validation_status": _validation_status(design, actual_gpu_designs, gate_designs),
            "rule_family": str(assignment.get("rule_family") or ""),
            "configuration": str(assignment.get("configuration") or "gpu_cov"),
            "standard_tests": list(assignment.get("campaign_tests") or []),
            "next_step": str(candidate.get("next_step") or ""),
        }
        rows.append(row)

    phase_order = {
        PHASE_LABELS["already_in_scope"]: 0,
        PHASE_LABELS["phase_1_ready_family_actual_gpu"]: 1,
        PHASE_LABELS["phase_2_first_fallback"]: 2,
        PHASE_LABELS["phase_3_fallback_follow_on"]: 3,
        PHASE_LABELS["phase_4_large_integration"]: 4,
    }
    rows.sort(key=lambda row: (phase_order[row["phase"]], -row["candidate_score"], row["design"]))

    first_phase_focus = [
        row["design"]
        for row in rows
        if row["phase"] == PHASE_LABELS["phase_1_ready_family_actual_gpu"]
    ]
    first_fallback_target = next(
        (
            row["design"]
            for row in rows
            if row["phase"]
            in {
                PHASE_LABELS["phase_2_first_fallback"],
                PHASE_LABELS["phase_3_fallback_follow_on"],
                PHASE_LABELS["phase_4_large_integration"],
            }
        ),
        "",
    )

    payload = {
        "schema_version": "design-scope-expansion-v1",
        "status": "scope_expansion_order_frozen",
        "rationale": [
            "Do not mix ready_for_gpu_toggle families with wrapper/manifest bring-up families in the same expansion step.",
            "First extend actual GPU evidence across already wrapper-ready families, then introduce exactly one fallback bring-up family.",
        ],
        "first_phase_focus": first_phase_focus,
        "first_fallback_target": first_fallback_target,
        "rows": rows,
    }
    ns.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Design Scope Expansion Packet",
        "",
        f"- status: `{payload['status']}`",
        f"- first phase focus: `{', '.join(payload['first_phase_focus']) or '(none)'}`",
        f"- first fallback target: `{payload['first_fallback_target']}`",
        "",
        "## Rationale",
        "",
    ]
    for item in payload["rationale"]:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "## Expansion Order",
            "",
            "| Design | Phase | Validation | Readiness | Feature | Rule | Standard tests |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            "| {design} | {phase} | {validation_status} | {readiness} | {feature_family} | {rule_family} | {tests} |".format(
                tests=", ".join(row["standard_tests"]),
                **row,
            )
        )
    ns.md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(ns.json_out)
    print(ns.md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
