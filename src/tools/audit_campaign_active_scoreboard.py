#!/usr/bin/env python3
"""
Build the active campaign scoreboard from the resolved policy gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from audit_campaign_speed_scoreboard import build_scoreboard


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_POLICY_GATE = REPO_ROOT / "work" / "campaign_threshold_policy_gate.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_speed_scoreboard_active.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_active_scoreboard_from_gate_payload(
    gate: dict[str, Any],
    *,
    policy_gate_path: Path | None = None,
) -> dict[str, Any]:
    outcome = dict(gate.get("outcome") or {})
    selected_paths = [Path(raw).resolve() for raw in list(outcome.get("selected_paths") or [])]
    payload = build_scoreboard(selected_paths)
    payload["scope"] = "campaign_speed_scoreboard_active"
    payload["policy_gate_path"] = str(policy_gate_path.resolve()) if policy_gate_path is not None else None
    payload["policy_gate_status"] = outcome.get("status")
    payload["selected_policy_mode"] = outcome.get("selected_policy_mode")
    payload["selected_scenario_name"] = outcome.get("selected_scenario_name")
    payload["selected_profile_name"] = (gate.get("selection") or {}).get("profile_name")
    payload["selected_thresholds"] = list(outcome.get("selected_thresholds") or [])
    payload["selected_paths"] = [str(path) for path in selected_paths]
    return payload


def build_active_scoreboard(*, policy_gate_path: Path) -> dict[str, Any]:
    gate = _read_json(policy_gate_path)
    return build_active_scoreboard_from_gate_payload(gate, policy_gate_path=policy_gate_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-gate", type=Path, default=DEFAULT_POLICY_GATE)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_active_scoreboard(policy_gate_path=args.policy_gate.resolve())
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
