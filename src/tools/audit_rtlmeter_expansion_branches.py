#!/usr/bin/env python3
"""
Combine the ready-scoreboard and second-target feasibility audit into
objective-oriented branch recommendations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_SCOREBOARD = REPO_ROOT / "work" / "rtlmeter_ready_scoreboard.json"
DEFAULT_FEASIBILITY = REPO_ROOT / "work" / "second_target_feasibility_audit.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "rtlmeter_expansion_branch_audit.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows_by_name(scoreboard: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["slice_name"]): dict(row) for row in scoreboard.get("rows") or []}


def _build_objectives(
    scoreboard: dict[str, Any],
    feasibility: dict[str, Any],
) -> dict[str, Any]:
    rows = _rows_by_name(scoreboard)
    tier_counts = dict((scoreboard.get("summary") or {}).get("tier_counts") or {})
    recommendation = dict(feasibility.get("recommendation") or {})
    feasibility_rows = [dict(row) for row in feasibility.get("candidates") or []]

    thin_top_seed = (
        recommendation.get("if_promote_thinner_host_driven_top", {}) or {}
    ).get("recommended_seed")
    current_model_blocked = list(
        (recommendation.get("if_keep_current_tb_timed_model", {}) or {}).get("blocked_candidates") or []
    )
    current_model_ready = sorted(
        str(row.get("slice_name"))
        for row in feasibility_rows
        if row.get("current_blocker") == "ready_for_next_experiment"
    )

    thin_top_row = rows.get(str(thin_top_seed)) if thin_top_seed else None
    thin_top_branch = "thinner_host_driven_top"
    thin_top_actions: list[str] = []
    thin_top_reason = "no thin-top seed was identified"
    thin_top_objective_met = False
    if thin_top_row is not None:
        thin_top_tier = str(thin_top_row["tier"])
        if thin_top_tier in {"Tier R", "Tier S"}:
            thin_top_branch = "defer_second_target"
            thin_top_reason = (
                f"{thin_top_seed} is already {thin_top_tier}, so the scoreboard already has a second Tier R/S candidate"
            )
            thin_top_objective_met = True
        else:
            thin_top_reason = (
                f"{thin_top_seed} is already {thin_top_tier} with build/probe artifacts and has a concrete replay seam"
            )
            thin_top_actions = [
                f"implement_true_host_driven_top_for_{thin_top_seed}",
                f"re-run_host_probe_and_gpu_handoff_for_{thin_top_seed}",
            ]

    current_model_branch = "current_tb_timed_coroutine_model"
    if current_model_blocked:
        current_model_reason = (
            "current-model branch can raise raw coverage counts fastest because "
            f"{len(current_model_blocked)} ready slices are blocked only by missing coverage TB sources"
        )
        current_model_first_actions = [
            "restore_or_generate_coverage_tb_source_for_tlul_err",
            "restore_or_generate_coverage_tb_source_for_tlul_sink",
        ]
        current_model_expected_moves = [
            {"slice_name": name, "from_tier": "Tier M", "to_tier": "Tier T"}
            for name in current_model_blocked
        ]
    elif current_model_ready:
        joined = ", ".join(current_model_ready)
        current_model_reason = (
            "current-model branch no longer has source-restoration work; "
            f"the next concrete action is a first pilot on {joined}"
        )
        current_model_first_actions = [
            f"run_initial_host_gpu_flow_for_{name}" for name in current_model_ready
        ]
        current_model_expected_moves = []
    else:
        current_model_branch = "defer_second_target"
        current_model_reason = (
            "current-model branch has no source-restoration or pilot-ready targets left, "
            "so there is no near-term raw tier-count gain on that path"
        )
        current_model_first_actions = []
        current_model_expected_moves = []

    defer_reason = (
        "minimum goal is already met via socket_m1, so the lowest-risk option is to keep coverage expansion out of the current line"
    )

    return {
        "maximize_ready_tier_count_quickly": {
            "recommended_branch": current_model_branch,
            "reason": current_model_reason,
            "first_actions": current_model_first_actions,
            "expected_near_term_tier_moves": current_model_expected_moves,
        },
        "maximize_second_r_or_s_candidate": {
            "recommended_branch": thin_top_branch,
            "reason": thin_top_reason,
            "first_actions": thin_top_actions,
            "seed_candidate": thin_top_seed,
            "current_seed_tier": thin_top_row["tier"] if thin_top_row else None,
            "objective_already_met": thin_top_objective_met,
        },
        "minimize_delivery_risk": {
            "recommended_branch": "defer_second_target",
            "reason": defer_reason,
            "first_actions": [
                "keep_socket_m1_as_only_supported_target",
                "treat_second_target_expansion_as_next_milestone_work",
            ],
        },
        "current_counts": tier_counts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scoreboard", type=Path, default=DEFAULT_SCOREBOARD)
    parser.add_argument("--feasibility", type=Path, default=DEFAULT_FEASIBILITY)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args(argv)

    scoreboard = _read_json(args.scoreboard.resolve())
    feasibility = _read_json(args.feasibility.resolve())
    payload = {
        "schema_version": 1,
        "scoreboard_path": str(args.scoreboard.resolve()),
        "feasibility_path": str(args.feasibility.resolve()),
        "objectives": _build_objectives(scoreboard, feasibility),
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.json_out)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
