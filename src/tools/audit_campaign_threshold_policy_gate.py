#!/usr/bin/env python3
"""
Resolve the active campaign-threshold policy from policy options and the repo's
allow/deny setting for per-target semantics and threshold-schema mismatch.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_OPTIONS_JSON = REPO_ROOT / "work" / "campaign_threshold_policy_options.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_threshold_policies" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_threshold_policy_gate.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _scenario_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(scenario.get("name")): dict(scenario) for scenario in list(payload.get("scenarios") or [])}


def _scenario_thresholds(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list((scenario.get("scoreboard_summary") or {}).get("threshold_keys") or [])
    parsed: list[dict[str, Any]] = []
    for key in rows:
        if not isinstance(key, str):
            continue
        parts = key.split(":", 2)
        if len(parts) != 3:
            continue
        kind, raw_value, aggregation = parts
        try:
            value: int | str = int(raw_value)
        except ValueError:
            value = raw_value
        parsed.append(
            {
                "kind": kind,
                "value": value,
                "aggregation": aggregation,
            }
        )
    return parsed


def _resolve_profile_payload(
    *,
    selection_payload: dict[str, Any],
    selection_path: Path,
) -> tuple[str | None, Path | None, dict[str, Any] | None]:
    profile_name = selection_payload.get("profile_name")
    if not isinstance(profile_name, str) or not profile_name.strip():
        return None, None, None
    normalized_name = profile_name.strip()
    profile_path = selection_path.resolve().parent / "profiles" / f"{normalized_name}.json"
    if not profile_path.is_file():
        raise FileNotFoundError(f"campaign threshold profile not found: {profile_path}")
    profile_payload = _read_json(profile_path)
    return normalized_name, profile_path, profile_payload


def _resolve_extra_paths(
    *,
    selection_payload: dict[str, Any],
) -> list[Path]:
    resolved: list[Path] = []
    seen: set[Path] = set()
    for raw in list(selection_payload.get("extra_comparison_paths") or []):
        path = Path(str(raw))
        if not path.is_absolute():
            path = (REPO_ROOT / path).resolve()
        else:
            path = path.resolve()
        if path not in seen:
            seen.add(path)
            resolved.append(path)
    return resolved


def _assert_selection_matches_profile(
    *,
    selection_payload: dict[str, Any],
    profile_payload: dict[str, Any],
    profile_path: Path,
) -> None:
    for key in ("allow_per_target_thresholds", "require_matching_thresholds"):
        selection_value = bool(selection_payload.get(key))
        profile_value = bool(profile_payload.get(key))
        if selection_value != profile_value:
            raise ValueError(
                f"selection.json disagrees with profile {profile_path} on {key}: "
                f"{selection_value!r} != {profile_value!r}"
            )


def _is_strong_hybrid_scenario(scenario: dict[str, Any], *, minimum_strong_margin: float) -> bool:
    summary = dict(scenario.get("scoreboard_summary") or {})
    ready = int(summary.get("comparison_ready_count") or 0)
    wins = int(summary.get("hybrid_win_count") or 0)
    weakest = dict(summary.get("weakest_hybrid_win") or {})
    ratio = weakest.get("speedup_ratio")
    ratio_f = float(ratio) if isinstance(ratio, (int, float)) else None
    return ready > 0 and wins == ready and ratio_f is not None and ratio_f >= minimum_strong_margin


def build_gate(
    *,
    options_payload: dict[str, Any],
    selection_payload: dict[str, Any],
    options_path: Path,
    selection_path: Path,
) -> dict[str, Any]:
    scenarios = _scenario_map(options_payload)
    minimum_strong_margin = float((options_payload.get("policy") or {}).get("minimum_strong_margin") or 0.0)
    profile_name, profile_path, profile_payload = _resolve_profile_payload(
        selection_payload=selection_payload,
        selection_path=selection_path,
    )
    if profile_payload is not None and profile_path is not None:
        _assert_selection_matches_profile(
            selection_payload=selection_payload,
            profile_payload=profile_payload,
            profile_path=profile_path,
        )
    allow_per_target = bool(selection_payload.get("allow_per_target_thresholds"))
    require_matching_thresholds = bool(selection_payload.get("require_matching_thresholds", True))
    decision = dict(options_payload.get("decision") or {})
    recommended_policy = str(decision.get("recommended_policy") or "")

    checked_in = scenarios.get("checked_in_common_v1")
    common_candidate = scenarios.get("candidate_common_threshold5")
    design_specific_candidate = scenarios.get("candidate_design_specific_minimal_progress")

    outcome: dict[str, Any] = {
        "status": "hold_current_v1",
        "reason": "default_to_checked_in_common_v1",
        "selected_scenario_name": "checked_in_common_v1",
        "selected_policy_mode": "common",
    }

    if recommended_policy == "promote_common_threshold_v2" and common_candidate is not None:
        outcome = {
            "status": "promote_common_v2",
            "reason": "policy_options_recommend_common_candidate",
            "selected_scenario_name": "candidate_common_threshold5",
            "selected_policy_mode": "common",
        }
    elif recommended_policy == "decide_if_design_specific_thresholds_are_allowed":
        if allow_per_target and design_specific_candidate is not None and _is_strong_hybrid_scenario(
            design_specific_candidate,
            minimum_strong_margin=minimum_strong_margin,
        ):
            outcome = {
                "status": "promote_design_specific_v2",
                "reason": "per_target_thresholds_allowed_and_candidate_is_strong",
                "selected_scenario_name": "candidate_design_specific_minimal_progress",
                "selected_policy_mode": "per_target",
            }
        else:
            outcome = {
                "status": "hold_current_v1",
                "reason": (
                    "per_target_thresholds_not_allowed"
                    if not allow_per_target
                    else "per_target_candidate_not_strong_enough"
                ),
                "selected_scenario_name": "checked_in_common_v1",
                "selected_policy_mode": "common",
            }
    elif checked_in is not None:
        outcome = {
            "status": "hold_current_v1",
            "reason": "no_promotable_candidate_selected",
            "selected_scenario_name": "checked_in_common_v1",
            "selected_policy_mode": "common",
        }

    selected_scenario = scenarios.get(outcome["selected_scenario_name"]) or {}
    scenario_paths = [str(path) for path in list(selected_scenario.get("paths") or [])]
    extra_selected_paths = [str(path) for path in _resolve_extra_paths(selection_payload=selection_payload)]
    merged_selected_paths: list[str] = []
    for raw in scenario_paths + extra_selected_paths:
        if raw not in merged_selected_paths:
            merged_selected_paths.append(raw)

    return {
        "schema_version": 1,
        "scope": "campaign_threshold_policy_gate",
        "policy_options_path": str(options_path.resolve()),
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()) if profile_path is not None else None,
            "allow_per_target_thresholds": allow_per_target,
            "require_matching_thresholds": require_matching_thresholds,
            "extra_comparison_paths": extra_selected_paths,
            "notes": selection_payload.get("notes"),
        },
        "policy_options_decision": {
            "recommended_policy": decision.get("recommended_policy"),
            "reason": decision.get("reason"),
        },
        "outcome": {
            **outcome,
            "selected_thresholds": _scenario_thresholds(selected_scenario),
            "scenario_paths": scenario_paths,
            "extra_selected_paths": extra_selected_paths,
            "selected_paths": merged_selected_paths,
            "selected_scenario_summary": dict(selected_scenario.get("scoreboard_summary") or {}),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-options-json", type=Path, default=DEFAULT_OPTIONS_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    options_path = args.policy_options_json.resolve()
    selection_path = args.selection_config.resolve()
    payload = build_gate(
        options_payload=_read_json(options_path),
        selection_payload=_read_json(selection_path),
        options_path=options_path,
        selection_path=selection_path,
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
