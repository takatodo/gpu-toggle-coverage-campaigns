#!/usr/bin/env python3
"""
Resolve the current checkpoint/seed acceptance profile against the current
checkpoint-readiness and non-OpenTitan seed-status artifacts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_CHECKPOINT_JSON = REPO_ROOT / "work" / "campaign_checkpoint_readiness.json"
DEFAULT_SEED_STATUS_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_seed_status.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_real_goal_acceptance" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_real_goal_acceptance_gate.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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
        raise FileNotFoundError(f"campaign real-goal acceptance profile not found: {profile_path}")
    return normalized_name, profile_path, _read_json(profile_path)


def _build_outcome(
    *,
    profile_payload: dict[str, Any],
    checkpoint_payload: dict[str, Any],
    seed_payload: dict[str, Any],
) -> dict[str, Any]:
    accept_checkpoint = bool(profile_payload.get("accept_checkpoint"))
    accept_selected_seed = bool(profile_payload.get("accept_selected_seed"))
    checkpoint_decision = dict(checkpoint_payload.get("decision") or {})
    checkpoint_summary = dict(checkpoint_payload.get("summary") or {})
    seed_decision = dict(seed_payload.get("decision") or {})
    selected_entry = dict(seed_payload.get("selected_entry") or {})

    checkpoint_status = str(checkpoint_decision.get("readiness") or "")
    seed_status = str(seed_decision.get("status") or "")

    if accept_selected_seed and not accept_checkpoint:
        return {
            "status": "blocked_invalid_profile",
            "reason": "seed_acceptance_requires_checkpoint_acceptance",
            "next_action": "fix_campaign_real_goal_acceptance_profile",
        }

    if not accept_checkpoint:
        return {
            "status": "hold_checkpoint_and_seed",
            "reason": "selected_profile_keeps_the_checkpoint_and_seed_in_pre_acceptance_state",
            "next_action": "accept_first_checkpoint_or_keep_holding",
        }

    if checkpoint_status != "cross_family_checkpoint_ready":
        return {
            "status": "blocked_checkpoint_not_ready",
            "reason": checkpoint_decision.get("reason")
            or "checkpoint_artifact_has_not_reached_cross_family_checkpoint_ready",
            "next_action": checkpoint_decision.get("recommended_next_task")
            or "stabilize_current_checkpoint",
        }

    if not accept_selected_seed:
        next_action = "accept_selected_non_opentitan_seed"
        if seed_status != "ready_to_accept_selected_seed":
            next_action = seed_decision.get("recommended_next_task") or "repair_selected_non_opentitan_seed"
        return {
            "status": "checkpoint_accepted_seed_pending",
            "reason": "selected_profile_accepts_the_checkpoint_but_keeps_the_selected_seed_pending",
            "next_action": next_action,
            "selected_seed_status": seed_status or None,
        }

    if seed_status != "ready_to_accept_selected_seed":
        return {
            "status": "blocked_selected_seed_not_ready",
            "reason": seed_decision.get("reason")
            or "selected_non_opentitan_seed_is_not_ready_for_acceptance",
            "next_action": seed_decision.get("recommended_next_task")
            or "repair_selected_non_opentitan_seed",
            "selected_seed_status": seed_status or None,
        }

    return {
        "status": "accepted_checkpoint_and_seed",
        "reason": "current_checkpoint_and_selected_non_opentitan_seed_are_both_ready_and_now_checked_in_as_the_campaign_baseline",
        "next_action": "decide_next_xuantie_breadth_step",
        "active_surface_count": checkpoint_summary.get("active_surface_count"),
        "selected_seed_design": selected_entry.get("design"),
        "selected_seed_profile_name": selected_entry.get("profile_name"),
        "selected_seed_comparison_path": selected_entry.get("comparison_path"),
        "selected_seed_speedup_ratio": selected_entry.get("speedup_ratio"),
    }


def build_gate(
    *,
    checkpoint_payload: dict[str, Any],
    seed_payload: dict[str, Any],
    selection_payload: dict[str, Any],
    selection_path: Path,
) -> dict[str, Any]:
    profile_name, profile_path, profile_payload = _resolve_profile_payload(
        selection_payload=selection_payload,
        selection_path=selection_path,
    )
    if profile_payload is None or profile_path is None:
        raise ValueError("selection.json must specify a valid profile_name")

    outcome = _build_outcome(
        profile_payload=profile_payload,
        checkpoint_payload=checkpoint_payload,
        seed_payload=seed_payload,
    )
    checkpoint_decision = dict(checkpoint_payload.get("decision") or {})
    checkpoint_summary = dict(checkpoint_payload.get("summary") or {})
    seed_decision = dict(seed_payload.get("decision") or {})
    selected_entry = dict(seed_payload.get("selected_entry") or {})
    return {
        "schema_version": 1,
        "scope": "campaign_real_goal_acceptance_gate",
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()),
            "notes": selection_payload.get("notes"),
        },
        "context": {
            "checkpoint_readiness": checkpoint_decision.get("readiness"),
            "checkpoint_active_surface_count": checkpoint_summary.get("active_surface_count"),
            "seed_status": seed_decision.get("status"),
            "selected_seed_profile_name": selected_entry.get("profile_name"),
            "selected_seed_design": selected_entry.get("design"),
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-json", type=Path, default=DEFAULT_CHECKPOINT_JSON)
    parser.add_argument("--seed-status-json", type=Path, default=DEFAULT_SEED_STATUS_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_gate(
        checkpoint_payload=_read_json(args.checkpoint_json.resolve()),
        seed_payload=_read_json(args.seed_status_json.resolve()),
        selection_payload=_read_json(args.selection_config.resolve()),
        selection_path=args.selection_config.resolve(),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
