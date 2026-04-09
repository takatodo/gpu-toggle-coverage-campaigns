#!/usr/bin/env python3
"""
Preview how the campaign line changes across the policy matrix:
per-target threshold semantics allowed/denied and threshold mismatch allowed/denied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_campaign_active_scoreboard import build_active_scoreboard_from_gate_payload
from audit_campaign_next_kpi import build_audit_from_scoreboard_payload
from audit_campaign_threshold_policy_gate import build_gate


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_OPTIONS_JSON = REPO_ROOT / "work" / "campaign_threshold_policy_options.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_threshold_policies" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_threshold_policy_preview.json"
DEFAULT_MIN_READY_SURFACES = 2
DEFAULT_MIN_STRONG_MARGIN = 2.0


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _variant_payload(
    *,
    allow_per_target_thresholds: bool,
    require_matching_thresholds: bool,
    options_payload: dict[str, Any],
    selection_payload: dict[str, Any],
    options_path: Path,
    selection_path: Path,
    minimum_ready_surfaces: int,
    minimum_strong_margin: float,
) -> dict[str, Any]:
    current_selection = dict(selection_payload)
    current_selection["allow_per_target_thresholds"] = allow_per_target_thresholds
    current_selection["require_matching_thresholds"] = require_matching_thresholds
    if (
        bool(selection_payload.get("allow_per_target_thresholds")) != allow_per_target_thresholds
        or bool(selection_payload.get("require_matching_thresholds", True)) != require_matching_thresholds
    ):
        current_selection["profile_name"] = None
    gate = build_gate(
        options_payload=options_payload,
        selection_payload=current_selection,
        options_path=options_path,
        selection_path=selection_path,
    )
    scoreboard = build_active_scoreboard_from_gate_payload(gate, policy_gate_path=selection_path)
    next_kpi = build_audit_from_scoreboard_payload(
        scoreboard,
        minimum_ready_surfaces=minimum_ready_surfaces,
        minimum_strong_margin=minimum_strong_margin,
        require_matching_thresholds=require_matching_thresholds,
        scoreboard_path=None,
        policy_gate_path=selection_path,
    )
    return {
        "allow_per_target_thresholds": allow_per_target_thresholds,
        "require_matching_thresholds": require_matching_thresholds,
        "gate": gate,
        "active_scoreboard": scoreboard,
        "active_next_kpi": next_kpi,
    }


def build_preview(
    *,
    options_payload: dict[str, Any],
    selection_payload: dict[str, Any],
    options_path: Path,
    selection_path: Path,
    minimum_ready_surfaces: int,
    minimum_strong_margin: float,
) -> dict[str, Any]:
    current_allow = bool(selection_payload.get("allow_per_target_thresholds"))
    current_require_match = bool(selection_payload.get("require_matching_thresholds", True))
    variants = {
        "current_selection": _variant_payload(
            allow_per_target_thresholds=current_allow,
            require_matching_thresholds=current_require_match,
            options_payload=options_payload,
            selection_payload=selection_payload,
            options_path=options_path,
            selection_path=selection_path,
            minimum_ready_surfaces=minimum_ready_surfaces,
            minimum_strong_margin=minimum_strong_margin,
        ),
        "flip_allow_per_target": _variant_payload(
            allow_per_target_thresholds=not current_allow,
            require_matching_thresholds=current_require_match,
            options_payload=options_payload,
            selection_payload=selection_payload,
            options_path=options_path,
            selection_path=selection_path,
            minimum_ready_surfaces=minimum_ready_surfaces,
            minimum_strong_margin=minimum_strong_margin,
        ),
        "flip_require_matching": _variant_payload(
            allow_per_target_thresholds=current_allow,
            require_matching_thresholds=not current_require_match,
            options_payload=options_payload,
            selection_payload=selection_payload,
            options_path=options_path,
            selection_path=selection_path,
            minimum_ready_surfaces=minimum_ready_surfaces,
            minimum_strong_margin=minimum_strong_margin,
        ),
        "flip_both": _variant_payload(
            allow_per_target_thresholds=not current_allow,
            require_matching_thresholds=not current_require_match,
            options_payload=options_payload,
            selection_payload=selection_payload,
            options_path=options_path,
            selection_path=selection_path,
            minimum_ready_surfaces=minimum_ready_surfaces,
            minimum_strong_margin=minimum_strong_margin,
        ),
    }

    current_variant = variants["current_selection"]
    flip_allow_variant = variants["flip_allow_per_target"]
    flip_both_variant = variants["flip_both"]
    current_gate = dict(current_variant["gate"].get("outcome") or {})
    flip_allow_gate = dict(flip_allow_variant["gate"].get("outcome") or {})
    flip_both_gate = dict(flip_both_variant["gate"].get("outcome") or {})
    current_decision = dict(current_variant["active_next_kpi"].get("decision") or {})
    flip_allow_decision = dict(flip_allow_variant["active_next_kpi"].get("decision") or {})
    flip_both_decision = dict(flip_both_variant["active_next_kpi"].get("decision") or {})
    current_summary = dict(current_variant["active_scoreboard"].get("summary") or {})
    flip_both_summary = dict(flip_both_variant["active_scoreboard"].get("summary") or {})

    return {
        "schema_version": 1,
        "scope": "campaign_threshold_policy_preview",
        "options_path": str(options_path.resolve()),
        "selection_path": str(selection_path.resolve()),
        "policy": {
            "minimum_ready_surfaces": minimum_ready_surfaces,
            "minimum_strong_margin": minimum_strong_margin,
        },
        "current_selection": {
            "allow_per_target_thresholds": current_allow,
            "require_matching_thresholds": current_require_match,
        },
        "variants": variants,
        "summary": {
            "current_policy_status": current_gate.get("status"),
            "flip_allow_policy_status": flip_allow_gate.get("status"),
            "flip_both_policy_status": flip_both_gate.get("status"),
            "current_selected_scenario": current_gate.get("selected_scenario_name"),
            "flip_allow_selected_scenario": flip_allow_gate.get("selected_scenario_name"),
            "flip_both_selected_scenario": flip_both_gate.get("selected_scenario_name"),
            "current_next_kpi": current_decision.get("recommended_next_kpi"),
            "flip_allow_next_kpi": flip_allow_decision.get("recommended_next_kpi"),
            "flip_both_next_kpi": flip_both_decision.get("recommended_next_kpi"),
            "current_weakest_hybrid_win": dict(current_summary.get("weakest_hybrid_win") or {}),
            "flip_both_weakest_hybrid_win": dict(flip_both_summary.get("weakest_hybrid_win") or {}),
            "flip_allow_changes_active_line": current_gate.get("selected_scenario_name")
            != flip_allow_gate.get("selected_scenario_name"),
            "flip_allow_changes_next_kpi": current_decision.get("recommended_next_kpi")
            != flip_allow_decision.get("recommended_next_kpi"),
            "flip_allow_triggers_threshold_schema_mismatch": (
                flip_allow_decision.get("reason") == "threshold_schema_mismatch"
            ),
            "flip_both_unlocks_broader_design_count": (
                flip_both_decision.get("recommended_next_kpi") == "broader_design_count"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-options-json", type=Path, default=DEFAULT_OPTIONS_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--minimum-ready-surfaces", type=int, default=DEFAULT_MIN_READY_SURFACES)
    parser.add_argument("--minimum-strong-margin", type=float, default=DEFAULT_MIN_STRONG_MARGIN)
    args = parser.parse_args()

    options_path = args.policy_options_json.resolve()
    selection_path = args.selection_config.resolve()
    payload = build_preview(
        options_payload=_read_json(options_path),
        selection_payload=_read_json(selection_path),
        options_path=options_path,
        selection_path=selection_path,
        minimum_ready_surfaces=args.minimum_ready_surfaces,
        minimum_strong_margin=args.minimum_strong_margin,
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
