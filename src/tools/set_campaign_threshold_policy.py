#!/usr/bin/env python3
"""
Apply a named campaign-threshold policy profile and regenerate active artifacts.
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
DEFAULT_PROFILES_DIR = REPO_ROOT / "config" / "campaign_threshold_policies" / "profiles"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_threshold_policies" / "selection.json"
DEFAULT_GATE_JSON = REPO_ROOT / "work" / "campaign_threshold_policy_gate.json"
DEFAULT_SCOREBOARD_JSON = REPO_ROOT / "work" / "campaign_speed_scoreboard_active.json"
DEFAULT_NEXT_KPI_JSON = REPO_ROOT / "work" / "campaign_next_kpi_active.json"
DEFAULT_MIN_READY_SURFACES = 2
DEFAULT_MIN_STRONG_MARGIN = 2.0


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_profile(*, profiles_dir: Path, profile_name: str) -> tuple[Path, dict[str, Any]]:
    profile_path = (profiles_dir / f"{profile_name}.json").resolve()
    if not profile_path.is_file():
        raise FileNotFoundError(f"campaign threshold profile not found: {profile_path}")
    return profile_path, _read_json(profile_path)


def _selection_from_profile(*, profile_name: str, profile_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "profile_name": profile_name,
        "allow_per_target_thresholds": bool(profile_payload.get("allow_per_target_thresholds")),
        "require_matching_thresholds": bool(profile_payload.get("require_matching_thresholds", True)),
        "extra_comparison_paths": [],
        "notes": profile_payload.get("notes"),
    }


def apply_policy_profile(
    *,
    profile_name: str,
    profiles_dir: Path,
    options_path: Path,
    selection_path: Path,
    gate_json_path: Path,
    scoreboard_json_path: Path,
    next_kpi_json_path: Path,
    minimum_ready_surfaces: int,
    minimum_strong_margin: float,
) -> dict[str, Any]:
    profile_path, profile_payload = _load_profile(profiles_dir=profiles_dir, profile_name=profile_name)
    selection_payload = _selection_from_profile(profile_name=profile_name, profile_payload=profile_payload)
    if selection_path.is_file():
        existing_selection = _read_json(selection_path)
        selection_payload["extra_comparison_paths"] = list(existing_selection.get("extra_comparison_paths") or [])
    options_payload = _read_json(options_path)

    gate_payload = build_gate(
        options_payload=options_payload,
        selection_payload=selection_payload,
        options_path=options_path,
        selection_path=selection_path,
    )
    scoreboard_payload = build_active_scoreboard_from_gate_payload(
        gate_payload,
        policy_gate_path=gate_json_path,
    )
    next_kpi_payload = build_audit_from_scoreboard_payload(
        scoreboard_payload,
        minimum_ready_surfaces=minimum_ready_surfaces,
        minimum_strong_margin=minimum_strong_margin,
        require_matching_thresholds=bool(selection_payload.get("require_matching_thresholds", True)),
        scoreboard_path=None,
        policy_gate_path=gate_json_path,
    )

    selection_path.parent.mkdir(parents=True, exist_ok=True)
    gate_json_path.parent.mkdir(parents=True, exist_ok=True)
    scoreboard_json_path.parent.mkdir(parents=True, exist_ok=True)
    next_kpi_json_path.parent.mkdir(parents=True, exist_ok=True)

    selection_path.write_text(json.dumps(selection_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gate_json_path.write_text(json.dumps(gate_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scoreboard_json_path.write_text(json.dumps(scoreboard_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_kpi_json_path.write_text(json.dumps(next_kpi_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "schema_version": 1,
        "scope": "set_campaign_threshold_policy",
        "applied_profile_name": profile_name,
        "profile_path": str(profile_path),
        "selection_path": str(selection_path.resolve()),
        "gate_json_path": str(gate_json_path.resolve()),
        "scoreboard_json_path": str(scoreboard_json_path.resolve()),
        "next_kpi_json_path": str(next_kpi_json_path.resolve()),
        "policy_gate_status": gate_payload.get("outcome", {}).get("status"),
        "selected_scenario_name": gate_payload.get("outcome", {}).get("selected_scenario_name"),
        "recommended_next_kpi": next_kpi_payload.get("decision", {}).get("recommended_next_kpi"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--profiles-dir", type=Path, default=DEFAULT_PROFILES_DIR)
    parser.add_argument("--policy-options-json", type=Path, default=DEFAULT_OPTIONS_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--gate-json-out", type=Path, default=DEFAULT_GATE_JSON)
    parser.add_argument("--scoreboard-json-out", type=Path, default=DEFAULT_SCOREBOARD_JSON)
    parser.add_argument("--next-kpi-json-out", type=Path, default=DEFAULT_NEXT_KPI_JSON)
    parser.add_argument("--minimum-ready-surfaces", type=int, default=DEFAULT_MIN_READY_SURFACES)
    parser.add_argument("--minimum-strong-margin", type=float, default=DEFAULT_MIN_STRONG_MARGIN)
    args = parser.parse_args()

    payload = apply_policy_profile(
        profile_name=args.profile_name,
        profiles_dir=args.profiles_dir.resolve(),
        options_path=args.policy_options_json.resolve(),
        selection_path=args.selection_config.resolve(),
        gate_json_path=args.gate_json_out.resolve(),
        scoreboard_json_path=args.scoreboard_json_out.resolve(),
        next_kpi_json_path=args.next_kpi_json_out.resolve(),
        minimum_ready_surfaces=args.minimum_ready_surfaces,
        minimum_strong_margin=args.minimum_strong_margin,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
