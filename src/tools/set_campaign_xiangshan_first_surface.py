#!/usr/bin/env python3
"""
Apply a named XiangShan first-surface profile and regenerate the active gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_campaign_xiangshan_first_surface_gate import build_gate


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_STEP_JSON = REPO_ROOT / "work" / "campaign_xiangshan_first_surface_step.json"
DEFAULT_PROFILES_DIR = REPO_ROOT / "config" / "campaign_xiangshan_first_surface" / "profiles"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_xiangshan_first_surface" / "selection.json"
DEFAULT_GATE_JSON = REPO_ROOT / "work" / "campaign_xiangshan_first_surface_gate.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_profile(*, profiles_dir: Path, profile_name: str) -> tuple[Path, dict[str, Any]]:
    profile_path = (profiles_dir / f"{profile_name}.json").resolve()
    if not profile_path.is_file():
        raise FileNotFoundError(f"campaign XiangShan first-surface profile not found: {profile_path}")
    return profile_path, _read_json(profile_path)


def _selection_from_profile(*, profile_name: str, profile_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "profile_name": profile_name,
        "notes": profile_payload.get("notes"),
    }


def apply_profile(
    *,
    profile_name: str,
    profiles_dir: Path,
    step_json: Path,
    selection_path: Path,
    gate_json_path: Path,
) -> dict[str, Any]:
    profile_path, profile_payload = _load_profile(profiles_dir=profiles_dir, profile_name=profile_name)
    selection_payload = _selection_from_profile(profile_name=profile_name, profile_payload=profile_payload)
    gate_payload = build_gate(
        step_payload=_read_json(step_json),
        selection_payload=selection_payload,
        selection_path=selection_path,
    )

    selection_path.parent.mkdir(parents=True, exist_ok=True)
    gate_json_path.parent.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(json.dumps(selection_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gate_json_path.write_text(json.dumps(gate_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "schema_version": 1,
        "scope": "set_campaign_xiangshan_first_surface",
        "applied_profile_name": profile_name,
        "profile_path": str(profile_path),
        "selection_path": str(selection_path.resolve()),
        "gate_json_path": str(gate_json_path.resolve()),
        "outcome_status": gate_payload.get("outcome", {}).get("status"),
        "next_action": gate_payload.get("outcome", {}).get("next_action"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--profiles-dir", type=Path, default=DEFAULT_PROFILES_DIR)
    parser.add_argument("--step-json", type=Path, default=DEFAULT_STEP_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--gate-json-out", type=Path, default=DEFAULT_GATE_JSON)
    args = parser.parse_args()

    payload = apply_profile(
        profile_name=args.profile_name,
        profiles_dir=args.profiles_dir.resolve(),
        step_json=args.step_json.resolve(),
        selection_path=args.selection_config.resolve(),
        gate_json_path=args.gate_json_out.resolve(),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
