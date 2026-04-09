#!/usr/bin/env python3
"""
Rank the next campaign-surface candidates from the ready-scoreboard and current
active campaign line.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_READY_SCOREBOARD = REPO_ROOT / "work" / "rtlmeter_ready_scoreboard.json"
DEFAULT_ACTIVE_SCOREBOARD = REPO_ROOT / "work" / "campaign_speed_scoreboard_active.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_third_surface_candidates.json"
VALIDATION_DIR = REPO_ROOT / "output" / "validation"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _watch_summary(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    watch_path = Path(path)
    if not watch_path.is_file():
        return {}
    return _read_json(watch_path)


def _validation_payload(row: dict[str, Any]) -> dict[str, Any]:
    validation = dict(row.get("validation") or {})
    validation_path = validation.get("path")
    if not validation_path:
        return {}
    path = Path(str(validation_path))
    if not path.is_file():
        return {}
    return _read_json(path)


def _comparison_payload(row: dict[str, Any], *, target: str) -> dict[str, Any]:
    comparison = dict(row.get("comparison") or {})
    comparison_path = comparison.get("path")
    if comparison_path:
        path = Path(str(comparison_path))
    else:
        path = VALIDATION_DIR / f"{target}_time_to_threshold_comparison.json"
    if not path.is_file():
        return {}
    payload = _read_json(path)
    payload["_path"] = str(path.resolve())
    return payload


def _active_targets(active_scoreboard: dict[str, Any]) -> set[str]:
    return {str(row.get("target")) for row in list(active_scoreboard.get("rows") or []) if row.get("target")}


def _candidate_row(*, row: dict[str, Any], is_active: bool) -> dict[str, Any]:
    target = str(row.get("slice_name") or "")
    tier = str(row.get("tier") or "")
    watch_payload = _watch_summary(row.get("watch_summary_path"))
    validation_payload = _validation_payload(row)
    comparison_payload = _comparison_payload(row, target=target)
    changed_watch_field_count = watch_payload.get("changed_watch_field_count")
    promotion_assessment = dict(validation_payload.get("promotion_assessment") or {})
    promotion_decision = str(promotion_assessment.get("decision") or "")

    if is_active:
        return {
            "target": target,
            "tier": tier,
            "candidate_state": "already_active_campaign_surface",
            "score": -1,
            "blocking_reason": "already_selected_in_active_campaign_line",
            "next_step": "maintain_current_active_surface",
        }

    comparison_ready = bool(comparison_payload.get("comparison_ready"))
    comparison_winner = str(comparison_payload.get("winner") or "")
    comparison_speedup_ratio = comparison_payload.get("speedup_ratio")
    if comparison_ready and comparison_winner == "hybrid":
        return {
            "target": target,
            "tier": tier,
            "candidate_state": (
                "comparison_ready_frozen_reference_surface"
                if promotion_decision == "freeze_at_phase_b_reference_design"
                else "comparison_ready_hybrid_win"
            ),
            "score": 95 if promotion_decision == "freeze_at_phase_b_reference_design" else 100,
            "blocking_reason": (
                promotion_assessment.get("reason")
                if promotion_decision == "freeze_at_phase_b_reference_design"
                else None
            ),
            "next_step": (
                "decide_whether_to_add_frozen_reference_surface_to_active_campaign_line"
                if promotion_decision == "freeze_at_phase_b_reference_design"
                else "add_to_active_campaign_line"
            ),
            "comparison_path": comparison_payload.get("_path"),
            "comparison_winner": comparison_winner,
            "comparison_speedup_ratio": comparison_speedup_ratio,
        }
    if comparison_ready and comparison_winner == "baseline":
        return {
            "target": target,
            "tier": tier,
            "candidate_state": "comparison_ready_but_baseline_win",
            "score": 25,
            "blocking_reason": "baseline_currently_reaches_threshold_faster_than_hybrid",
            "next_step": "choose_different_third_surface_or_redefine_target_specific_threshold",
            "comparison_path": comparison_payload.get("_path"),
            "comparison_winner": comparison_winner,
            "comparison_speedup_ratio": comparison_speedup_ratio,
        }
    if comparison_payload and comparison_winner == "unresolved":
        return {
            "target": target,
            "tier": tier,
            "candidate_state": "comparison_artifact_unresolved",
            "score": 35,
            "blocking_reason": "comparison_threshold_not_satisfied_on_both_sides",
            "next_step": "retune_or_redefine_campaign_threshold_before_using_as_third_surface",
            "comparison_path": comparison_payload.get("_path"),
            "comparison_winner": comparison_winner,
            "comparison_speedup_ratio": comparison_speedup_ratio,
        }
    if comparison_payload and comparison_winner == "rejected":
        return {
            "target": target,
            "tier": tier,
            "candidate_state": "comparison_artifact_rejected",
            "score": 20,
            "blocking_reason": comparison_payload.get("reject_reason") or "comparison_artifact_rejected",
            "next_step": "fix_threshold_schema_or_artifact_contract_before_using_as_third_surface",
            "comparison_path": comparison_payload.get("_path"),
            "comparison_winner": comparison_winner,
            "comparison_speedup_ratio": comparison_speedup_ratio,
        }

    if tier == "Tier R":
        if promotion_decision == "freeze_at_phase_b_reference_design":
            return {
                "target": target,
                "tier": tier,
                "candidate_state": "frozen_reference_surface",
                "score": 80,
                "blocking_reason": promotion_assessment.get("reason")
                or "reference surface is stable but promotion is frozen",
                "next_step": "decide_whether_a_frozen_reference_surface_is_acceptable_for_campaign_comparison",
            }
        return {
            "target": target,
            "tier": tier,
            "candidate_state": "reference_surface_ready_for_campaign_extension",
            "score": 90,
            "blocking_reason": None,
            "next_step": "add_cpu_baseline_and_time_to_threshold_comparison",
        }

    if tier == "Tier B":
        if isinstance(changed_watch_field_count, int) and changed_watch_field_count > 0:
            return {
                "target": target,
                "tier": tier,
                "candidate_state": "build_probe_with_design_visible_delta",
                "score": 70,
                "blocking_reason": None,
                "next_step": "add_stable_validation_then_campaign_baseline_and_comparison",
            }
        return {
            "target": target,
            "tier": tier,
            "candidate_state": "build_probe_no_design_visible_delta",
            "score": 60,
            "blocking_reason": "checked_in_watch_summary_has_no_design_visible_delta",
            "next_step": "define_target_specific_progress_semantics_or_switch_mechanism_before_campaign_comparison",
        }

    if tier == "Tier T":
        return {
            "target": target,
            "tier": tier,
            "candidate_state": "template_ready_only",
            "score": 40,
            "blocking_reason": "no_build_and_probe_artifacts_yet",
            "next_step": "bootstrap_build_and_host_probe_before_campaign_comparison",
        }

    return {
        "target": target,
        "tier": tier,
        "candidate_state": "not_prioritized",
        "score": 0,
        "blocking_reason": "outside_current_campaign_expansion_line",
        "next_step": "ignore_for_now",
    }


def build_candidate_audit(*, ready_scoreboard: dict[str, Any], active_scoreboard: dict[str, Any]) -> dict[str, Any]:
    active_targets = _active_targets(active_scoreboard)
    candidates = [
        _candidate_row(row=dict(row), is_active=str(row.get("slice_name") or "") in active_targets)
        for row in list(ready_scoreboard.get("rows") or [])
    ]
    ranked = sorted(
        [row for row in candidates if row.get("candidate_state") != "already_active_campaign_surface"],
        key=lambda row: (-int(row.get("score") or 0), str(row.get("target") or "")),
    )
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index

    recommended = ranked[0] if ranked else None
    return {
        "schema_version": 1,
        "scope": "campaign_third_surface_candidates",
        "ready_scoreboard_path": str(DEFAULT_READY_SCOREBOARD.resolve()),
        "active_scoreboard_path": str(DEFAULT_ACTIVE_SCOREBOARD.resolve()),
        "selected_profile_name": active_scoreboard.get("selected_profile_name"),
        "active_targets": sorted(active_targets),
        "summary": {
            "candidate_count": len(ranked),
            "recommended_next_target": recommended.get("target") if recommended else None,
            "recommended_next_state": recommended.get("candidate_state") if recommended else None,
            "recommended_next_step": recommended.get("next_step") if recommended else None,
        },
        "rows": ranked,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ready-scoreboard-json", type=Path, default=DEFAULT_READY_SCOREBOARD)
    parser.add_argument("--active-scoreboard-json", type=Path, default=DEFAULT_ACTIVE_SCOREBOARD)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    ready_path = args.ready_scoreboard_json.resolve()
    active_path = args.active_scoreboard_json.resolve()
    payload = build_candidate_audit(
        ready_scoreboard=_read_json(ready_path),
        active_scoreboard=_read_json(active_path),
    )
    payload["ready_scoreboard_path"] = str(ready_path)
    payload["active_scoreboard_path"] = str(active_path)

    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
