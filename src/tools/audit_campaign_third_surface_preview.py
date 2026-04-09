#!/usr/bin/env python3
"""
Preview the campaign scoreboard and next KPI if the recommended next surface is
added to the current active campaign line.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_campaign_next_kpi import build_audit_from_scoreboard_payload
from audit_campaign_speed_scoreboard import build_scoreboard


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_POLICY_GATE = REPO_ROOT / "work" / "campaign_threshold_policy_gate.json"
DEFAULT_ACTIVE_SCOREBOARD = REPO_ROOT / "work" / "campaign_speed_scoreboard_active.json"
DEFAULT_CANDIDATE_AUDIT = REPO_ROOT / "work" / "campaign_third_surface_candidates.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_third_surface_preview.json"
DEFAULT_MIN_READY_SURFACES = 2
DEFAULT_MIN_STRONG_MARGIN = 2.0


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _recommended_row(candidate_audit: dict[str, Any]) -> dict[str, Any]:
    target = ((candidate_audit.get("summary") or {}).get("recommended_next_target"))
    for row in list(candidate_audit.get("rows") or []):
        if row.get("target") == target:
            return dict(row)
    return {}


def build_preview(
    *,
    policy_gate: dict[str, Any],
    active_scoreboard: dict[str, Any],
    candidate_audit: dict[str, Any],
    minimum_ready_surfaces: int,
    minimum_strong_margin: float,
) -> dict[str, Any]:
    row = _recommended_row(candidate_audit)
    candidate_path = row.get("comparison_path")
    selected_paths = [Path(raw).resolve() for raw in list(active_scoreboard.get("selected_paths") or [])]
    if candidate_path:
        selected_paths.append(Path(str(candidate_path)).resolve())
    scoreboard = build_scoreboard(selected_paths)
    selection = dict(policy_gate.get("selection") or {})
    decision_payload = build_audit_from_scoreboard_payload(
        scoreboard,
        minimum_ready_surfaces=minimum_ready_surfaces,
        minimum_strong_margin=minimum_strong_margin,
        require_matching_thresholds=bool(selection.get("require_matching_thresholds", True)),
        scoreboard_path=None,
        policy_gate_path=None,
    )
    return {
        "schema_version": 1,
        "scope": "campaign_third_surface_preview",
        "selected_profile_name": selection.get("profile_name"),
        "candidate_target": row.get("target"),
        "candidate_state": row.get("candidate_state"),
        "candidate_next_step": row.get("next_step"),
        "candidate_comparison_path": candidate_path,
        "selected_paths": [str(path) for path in selected_paths],
        "scoreboard_summary": dict(scoreboard.get("summary") or {}),
        "decision": dict(decision_payload.get("decision") or {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-gate", type=Path, default=DEFAULT_POLICY_GATE)
    parser.add_argument("--active-scoreboard-json", type=Path, default=DEFAULT_ACTIVE_SCOREBOARD)
    parser.add_argument("--candidate-audit-json", type=Path, default=DEFAULT_CANDIDATE_AUDIT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--minimum-ready-surfaces", type=int, default=DEFAULT_MIN_READY_SURFACES)
    parser.add_argument("--minimum-strong-margin", type=float, default=DEFAULT_MIN_STRONG_MARGIN)
    args = parser.parse_args()

    payload = build_preview(
        policy_gate=_read_json(args.policy_gate.resolve()),
        active_scoreboard=_read_json(args.active_scoreboard_json.resolve()),
        candidate_audit=_read_json(args.candidate_audit_json.resolve()),
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
