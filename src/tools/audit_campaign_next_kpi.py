#!/usr/bin/env python3
"""
Recommend the next campaign KPI branch from the checked-in comparison scoreboard.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_campaign_active_scoreboard import build_active_scoreboard


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_SCOREBOARD = REPO_ROOT / "work" / "campaign_speed_scoreboard.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_next_kpi_audit.json"
DEFAULT_POLICY_GATE = REPO_ROOT / "work" / "campaign_threshold_policy_gate.json"
DEFAULT_MIN_READY_SURFACES = 2
DEFAULT_MIN_STRONG_MARGIN = 2.0


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _decision_from_scoreboard(
    scoreboard: dict[str, Any],
    *,
    minimum_ready_surfaces: int,
    minimum_strong_margin: float,
    require_matching_thresholds: bool,
) -> dict[str, Any]:
    summary = dict(scoreboard.get("summary") or {})
    comparison_ready_count = int(summary.get("comparison_ready_count") or 0)
    hybrid_win_count = int(summary.get("hybrid_win_count") or 0)
    all_thresholds_match = bool(summary.get("all_thresholds_match"))
    weakest_hybrid_win = dict(summary.get("weakest_hybrid_win") or {})
    weakest_ratio_raw = weakest_hybrid_win.get("speedup_ratio")
    weakest_ratio = float(weakest_ratio_raw) if isinstance(weakest_ratio_raw, (int, float)) else None

    if comparison_ready_count < minimum_ready_surfaces:
        return {
            "recommended_next_kpi": "stabilize_existing_surfaces",
            "reason": "insufficient_ready_comparisons",
            "recommended_next_tasks": [
                "Bring at least two comparison surfaces to comparison_ready=true.",
                "Keep threshold schema aligned before choosing the next KPI.",
            ],
        }
    if require_matching_thresholds and not all_thresholds_match:
        return {
            "recommended_next_kpi": "stabilize_existing_surfaces",
            "reason": "threshold_schema_mismatch",
            "recommended_next_tasks": [
                "Make campaign_threshold identical across checked-in comparison artifacts.",
                "Regenerate the scoreboard only after all_thresholds_match=true.",
            ],
        }
    if hybrid_win_count < comparison_ready_count:
        return {
            "recommended_next_kpi": "repair_existing_surfaces",
            "reason": "not_all_checked_in_surfaces_are_hybrid_wins",
            "recommended_next_tasks": [
                "Explain or repair the losing comparison surfaces before broadening the campaign line.",
                "Keep the current threshold fixed until the existing surfaces are trustworthy.",
            ],
        }
    if weakest_ratio is None:
        return {
            "recommended_next_kpi": "stabilize_existing_surfaces",
            "reason": "missing_weakest_hybrid_win_ratio",
            "recommended_next_tasks": [
                "Regenerate the scoreboard with explicit speedup_ratio fields.",
            ],
        }
    if weakest_ratio < minimum_strong_margin:
        return {
            "recommended_next_kpi": "stronger_thresholds",
            "reason": "weakest_hybrid_win_below_margin",
            "recommended_next_tasks": [
                "Define a stronger checked-in threshold for the current comparison surfaces.",
                "Regenerate socket_m1 and tlul_fifo_sync baseline/hybrid/comparison artifacts at that threshold.",
                "Only add another design after the stronger-threshold result is stable.",
            ],
        }
    return {
        "recommended_next_kpi": "broader_design_count",
        "reason": "current_surfaces_have_strong_hybrid_margin",
        "recommended_next_tasks": [
            "Choose the next comparison surface intentionally.",
            "Keep the existing threshold fixed while widening design count.",
        ],
    }


def build_audit(
    scoreboard_path: Path,
    *,
    minimum_ready_surfaces: int,
    minimum_strong_margin: float,
    require_matching_thresholds: bool = True,
) -> dict[str, Any]:
    scoreboard = _read_json(scoreboard_path)
    return build_audit_from_scoreboard_payload(
        scoreboard,
        minimum_ready_surfaces=minimum_ready_surfaces,
        minimum_strong_margin=minimum_strong_margin,
        require_matching_thresholds=require_matching_thresholds,
        scoreboard_path=scoreboard_path,
    )


def build_audit_from_scoreboard_payload(
    scoreboard: dict[str, Any],
    *,
    minimum_ready_surfaces: int,
    minimum_strong_margin: float,
    require_matching_thresholds: bool,
    scoreboard_path: Path | None = None,
    policy_gate_path: Path | None = None,
) -> dict[str, Any]:
    decision = _decision_from_scoreboard(
        scoreboard,
        minimum_ready_surfaces=minimum_ready_surfaces,
        minimum_strong_margin=minimum_strong_margin,
        require_matching_thresholds=require_matching_thresholds,
    )
    payload = {
        "schema_version": 1,
        "scope": "campaign_next_kpi_audit",
        "scoreboard_path": str(scoreboard_path.resolve()) if scoreboard_path is not None else None,
        "policy": {
            "minimum_ready_surfaces": minimum_ready_surfaces,
            "minimum_strong_margin": minimum_strong_margin,
            "require_matching_thresholds": require_matching_thresholds,
        },
        "scoreboard_summary": dict(scoreboard.get("summary") or {}),
        "decision": decision,
    }
    if policy_gate_path is not None:
        payload["policy_gate_path"] = str(policy_gate_path.resolve())
    if "policy_gate_status" in scoreboard:
        payload["policy_gate_status"] = scoreboard.get("policy_gate_status")
    if "selected_policy_mode" in scoreboard:
        payload["selected_policy_mode"] = scoreboard.get("selected_policy_mode")
    if "selected_scenario_name" in scoreboard:
        payload["selected_scenario_name"] = scoreboard.get("selected_scenario_name")
    return payload


def build_audit_from_policy_gate(
    policy_gate_path: Path,
    *,
    minimum_ready_surfaces: int,
    minimum_strong_margin: float,
) -> dict[str, Any]:
    scoreboard = build_active_scoreboard(policy_gate_path=policy_gate_path)
    policy_gate = _read_json(policy_gate_path)
    selection = dict(policy_gate.get("selection") or {})
    require_matching_thresholds = bool(selection.get("require_matching_thresholds", True))
    return build_audit_from_scoreboard_payload(
        scoreboard,
        minimum_ready_surfaces=minimum_ready_surfaces,
        minimum_strong_margin=minimum_strong_margin,
        require_matching_thresholds=require_matching_thresholds,
        scoreboard_path=None,
        policy_gate_path=policy_gate_path,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scoreboard", type=Path, default=DEFAULT_SCOREBOARD)
    parser.add_argument("--policy-gate", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument(
        "--minimum-ready-surfaces",
        type=int,
        default=DEFAULT_MIN_READY_SURFACES,
    )
    parser.add_argument(
        "--minimum-strong-margin",
        type=float,
        default=DEFAULT_MIN_STRONG_MARGIN,
    )
    parser.add_argument(
        "--allow-threshold-mismatch",
        action="store_true",
        help="For direct --scoreboard use only: do not require all_thresholds_match.",
    )
    args = parser.parse_args()

    if args.policy_gate is not None:
        payload = build_audit_from_policy_gate(
            args.policy_gate.resolve(),
            minimum_ready_surfaces=args.minimum_ready_surfaces,
            minimum_strong_margin=args.minimum_strong_margin,
        )
    else:
        payload = build_audit(
            args.scoreboard.resolve(),
            minimum_ready_surfaces=args.minimum_ready_surfaces,
            minimum_strong_margin=args.minimum_strong_margin,
            require_matching_thresholds=not args.allow_threshold_mismatch,
        )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
