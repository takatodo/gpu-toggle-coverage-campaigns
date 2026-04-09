#!/usr/bin/env python3
"""
Compare common-threshold and design-specific threshold policy candidates for campaign v2.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_campaign_speed_scoreboard import build_scoreboard


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_threshold_policy_options.json"
DEFAULT_CONFIG = REPO_ROOT / "config" / "campaign_threshold_policies" / "index.json"


def _scenario_summary(*, name: str, label: str, paths: list[Path]) -> dict[str, Any]:
    scoreboard = build_scoreboard(paths)
    summary = dict(scoreboard.get("summary") or {})
    return {
        "name": name,
        "label": label,
        "paths": [str(path.resolve()) for path in paths],
        "scoreboard_summary": summary,
    }


def _resolve_scenarios_from_config(path: Path) -> tuple[float | None, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenarios: list[dict[str, Any]] = []
    for raw in list(payload.get("scenarios") or []):
        scenarios.append(
            {
                "name": str(raw["name"]),
                "label": str(raw["label"]),
                "paths": [(REPO_ROOT / rel).resolve() for rel in list(raw.get("paths") or [])],
                "policy_mode": raw.get("policy_mode"),
            }
        )
    min_margin = payload.get("minimum_strong_margin")
    min_margin_f = float(min_margin) if isinstance(min_margin, (int, float)) else None
    return min_margin_f, scenarios


def _all_hybrid_wins(summary: dict[str, Any]) -> bool:
    ready = int(summary.get("comparison_ready_count") or 0)
    return ready > 0 and int(summary.get("hybrid_win_count") or 0) == ready


def _weakest_ratio(summary: dict[str, Any]) -> float | None:
    weakest = dict(summary.get("weakest_hybrid_win") or {})
    value = weakest.get("speedup_ratio")
    return float(value) if isinstance(value, (int, float)) else None


def build_audit_from_scenarios(
    *,
    scenario_specs: list[dict[str, Any]],
    minimum_strong_margin: float,
) -> dict[str, Any]:
    scenarios = [
        {
            **_scenario_summary(
                name=str(spec["name"]),
                label=str(spec["label"]),
                paths=list(spec["paths"]),
            ),
            "policy_mode": spec.get("policy_mode"),
        }
        for spec in scenario_specs
    ]
    by_name = {scenario["name"]: scenario for scenario in scenarios}

    common_candidate = by_name["candidate_common_threshold5"]["scoreboard_summary"]
    design_specific_candidate = by_name["candidate_design_specific_minimal_progress"]["scoreboard_summary"]

    common_candidate_strong = (
        bool(common_candidate.get("all_thresholds_match"))
        and _all_hybrid_wins(common_candidate)
        and (_weakest_ratio(common_candidate) or 0.0) >= minimum_strong_margin
    )
    design_specific_candidate_strong = (
        _all_hybrid_wins(design_specific_candidate)
        and (_weakest_ratio(design_specific_candidate) or 0.0) >= minimum_strong_margin
    )

    decision = {
        "recommended_policy": "keep_common_v1_and_define_new_common_candidate",
        "reason": "no_candidate_policy_is_both_strong_and_ready",
        "recommended_next_tasks": [
            "Keep the checked-in common threshold v1 while defining a stronger common candidate.",
        ],
    }

    if common_candidate_strong:
        decision = {
            "recommended_policy": "promote_common_threshold_v2",
            "reason": "common_candidate_is_strong_and_ready",
            "recommended_next_tasks": [
                "Promote the common threshold candidate to the checked-in v2 KPI.",
                "Keep design-specific semantics out of the checked-in policy for now.",
            ],
        }
    elif design_specific_candidate_strong:
        decision = {
            "recommended_policy": "decide_if_design_specific_thresholds_are_allowed",
            "reason": "design_specific_candidate_is_strong_but_common_candidate_is_not",
            "recommended_next_tasks": [
                "Decide whether campaign v2 may use per-target threshold semantics.",
                "If yes, formalize socket_m1 threshold5 + tlul_fifo_sync seq1 threshold24 as the next candidate v2.",
                "If no, keep the checked-in common v1 and define another stronger common candidate.",
            ],
        }

    return {
        "schema_version": 1,
        "scope": "campaign_threshold_policy_options",
        "policy": {
            "minimum_strong_margin": minimum_strong_margin,
        },
        "scenarios": scenarios,
        "decision": decision,
    }


def build_audit(
    *,
    common_v1_paths: list[Path],
    common_threshold5_paths: list[Path],
    design_specific_paths: list[Path],
    minimum_strong_margin: float,
) -> dict[str, Any]:
    scenario_specs = [
        {
            "name": "checked_in_common_v1",
            "label": "checked-in common threshold v1",
            "paths": common_v1_paths,
            "policy_mode": "common",
        },
        {
            "name": "candidate_common_threshold5",
            "label": "common raw-bits threshold=5 candidate",
            "paths": common_threshold5_paths,
            "policy_mode": "common",
        },
        {
            "name": "candidate_design_specific_minimal_progress",
            "label": "socket_m1 threshold5 + tlul_fifo_sync seq1 threshold24",
            "paths": design_specific_paths,
            "policy_mode": "per_target",
        },
    ]
    return build_audit_from_scenarios(
        scenario_specs=scenario_specs,
        minimum_strong_margin=minimum_strong_margin,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--common-v1-socket",
        type=Path,
        default=REPO_ROOT / "output" / "validation" / "socket_m1_time_to_threshold_comparison.json",
    )
    parser.add_argument(
        "--common-v1-fifo",
        type=Path,
        default=REPO_ROOT / "output" / "validation" / "tlul_fifo_sync_time_to_threshold_comparison.json",
    )
    parser.add_argument(
        "--common-threshold5-socket",
        type=Path,
        default=REPO_ROOT / "output" / "validation" / "socket_m1_time_to_threshold_comparison_threshold5.json",
    )
    parser.add_argument(
        "--common-threshold5-fifo",
        type=Path,
        default=REPO_ROOT / "output" / "validation" / "tlul_fifo_sync_time_to_threshold_comparison_threshold5.json",
    )
    parser.add_argument(
        "--design-specific-socket",
        type=Path,
        default=REPO_ROOT / "output" / "validation" / "socket_m1_time_to_threshold_comparison_threshold5.json",
    )
    parser.add_argument(
        "--design-specific-fifo",
        type=Path,
        default=REPO_ROOT / "output" / "validation" / "tlul_fifo_sync_time_to_threshold_comparison_seq1_threshold24.json",
    )
    parser.add_argument("--minimum-strong-margin", type=float, default=2.0)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    if args.config is not None:
        config_path = args.config.resolve()
        config_min_margin, scenario_specs = _resolve_scenarios_from_config(config_path)
        payload = build_audit_from_scenarios(
            scenario_specs=scenario_specs,
            minimum_strong_margin=(
                config_min_margin if config_min_margin is not None else args.minimum_strong_margin
            ),
        )
        payload["config_path"] = str(config_path)
    else:
        payload = build_audit(
            common_v1_paths=[args.common_v1_socket.resolve(), args.common_v1_fifo.resolve()],
            common_threshold5_paths=[
                args.common_threshold5_socket.resolve(),
                args.common_threshold5_fifo.resolve(),
            ],
            design_specific_paths=[
                args.design_specific_socket.resolve(),
                args.design_specific_fifo.resolve(),
            ],
            minimum_strong_margin=args.minimum_strong_margin,
        )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
