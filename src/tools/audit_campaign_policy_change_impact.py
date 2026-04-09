#!/usr/bin/env python3
"""
Summarize the impact of switching from the current campaign-threshold policy to a
selected preview variant.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_PREVIEW_JSON = REPO_ROOT / "work" / "campaign_threshold_policy_preview.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_policy_change_impact.json"
DEFAULT_FROM_VARIANT = "current_selection"
DEFAULT_TO_VARIANT = "flip_both"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _variant(payload: dict[str, Any], name: str) -> dict[str, Any]:
    variants = dict(payload.get("variants") or {})
    variant = dict(variants.get(name) or {})
    if not variant:
        raise KeyError(f"unknown preview variant: {name}")
    return variant


def _selected_thresholds(variant: dict[str, Any]) -> list[dict[str, Any]]:
    gate = dict(variant.get("gate") or {})
    outcome = dict(gate.get("outcome") or {})
    return list(outcome.get("selected_thresholds") or [])


def _selected_paths(variant: dict[str, Any]) -> list[str]:
    gate = dict(variant.get("gate") or {})
    outcome = dict(gate.get("outcome") or {})
    return list(outcome.get("selected_paths") or [])


def _summary(variant: dict[str, Any]) -> dict[str, Any]:
    scoreboard = dict(variant.get("active_scoreboard") or {})
    return dict(scoreboard.get("summary") or {})


def _decision(variant: dict[str, Any]) -> dict[str, Any]:
    next_kpi = dict(variant.get("active_next_kpi") or {})
    return dict(next_kpi.get("decision") or {})


def _gate_outcome(variant: dict[str, Any]) -> dict[str, Any]:
    gate = dict(variant.get("gate") or {})
    return dict(gate.get("outcome") or {})


def _list_diff(before: list[Any], after: list[Any]) -> dict[str, list[Any]]:
    before_set = {json.dumps(item, sort_keys=True) for item in before}
    after_set = {json.dumps(item, sort_keys=True) for item in after}
    added = [json.loads(item) for item in sorted(after_set - before_set)]
    removed = [json.loads(item) for item in sorted(before_set - after_set)]
    return {"added": added, "removed": removed}


def build_impact(
    *,
    preview_payload: dict[str, Any],
    preview_path: Path,
    from_variant: str,
    to_variant: str,
) -> dict[str, Any]:
    before = _variant(preview_payload, from_variant)
    after = _variant(preview_payload, to_variant)

    before_decision = _decision(before)
    after_decision = _decision(after)
    before_summary = _summary(before)
    after_summary = _summary(after)
    before_gate = _gate_outcome(before)
    after_gate = _gate_outcome(after)

    policy_changes: dict[str, dict[str, Any]] = {}
    for key in ("allow_per_target_thresholds", "require_matching_thresholds"):
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value != after_value:
            policy_changes[key] = {"from": before_value, "to": after_value}

    threshold_diff = _list_diff(_selected_thresholds(before), _selected_thresholds(after))
    path_diff = _list_diff(_selected_paths(before), _selected_paths(after))

    before_ready = str(before_decision.get("recommended_next_kpi") or "")
    after_ready = str(after_decision.get("recommended_next_kpi") or "")
    if before_ready != "broader_design_count" and after_ready == "broader_design_count":
        decision_type = "policy_switch_enables_broader_design_count"
        recommended_follow_up = (
            "If this policy is checked in, regenerate active artifacts and widen the active comparison line."
        )
    elif before_ready == "broader_design_count" and after_ready != "broader_design_count":
        decision_type = "policy_reversion_reduces_design_count"
        recommended_follow_up = (
            "Do not revert this policy unless you intentionally want to narrow the active campaign line."
        )
    else:
        decision_type = "policy_switch_requires_more_stabilization"
        recommended_follow_up = (
            "Do not check in this policy without first resolving the new stabilization blocker."
        )

    return {
        "schema_version": 1,
        "scope": "campaign_policy_change_impact",
        "preview_path": str(preview_path.resolve()),
        "from_variant": from_variant,
        "to_variant": to_variant,
        "policy_changes": policy_changes,
        "before": {
            "selected_scenario_name": before_gate.get("selected_scenario_name"),
            "selected_policy_mode": before_gate.get("selected_policy_mode"),
            "status": before_gate.get("status"),
            "recommended_next_kpi": before_ready,
            "decision_reason": before_decision.get("reason"),
            "thresholds": _selected_thresholds(before),
            "paths": _selected_paths(before),
            "summary": before_summary,
        },
        "after": {
            "selected_scenario_name": after_gate.get("selected_scenario_name"),
            "selected_policy_mode": after_gate.get("selected_policy_mode"),
            "status": after_gate.get("status"),
            "recommended_next_kpi": after_ready,
            "decision_reason": after_decision.get("reason"),
            "thresholds": _selected_thresholds(after),
            "paths": _selected_paths(after),
            "summary": after_summary,
        },
        "delta": {
            "selected_scenario_changed": before_gate.get("selected_scenario_name")
            != after_gate.get("selected_scenario_name"),
            "recommended_next_kpi_changed": before_ready != after_ready,
            "thresholds": threshold_diff,
            "paths": path_diff,
            "weakest_hybrid_win_before": dict(before_summary.get("weakest_hybrid_win") or {}),
            "weakest_hybrid_win_after": dict(after_summary.get("weakest_hybrid_win") or {}),
        },
        "impact_assessment": {
            "decision_type": decision_type,
            "recommended_follow_up": recommended_follow_up,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview-json", type=Path, default=DEFAULT_PREVIEW_JSON)
    parser.add_argument("--from-variant", default=DEFAULT_FROM_VARIANT)
    parser.add_argument("--to-variant", default=DEFAULT_TO_VARIANT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    preview_path = args.preview_json.resolve()
    payload = build_impact(
        preview_payload=_read_json(preview_path),
        preview_path=preview_path,
        from_variant=args.from_variant,
        to_variant=args.to_variant,
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
