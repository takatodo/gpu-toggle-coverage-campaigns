#!/usr/bin/env python3
"""
Resolve the selected OpenPiton first-surface acceptance profile against the
active XiangShan blocker state and the active OpenPiton first-surface gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_XIANGSHAN_STATUS_JSON = REPO_ROOT / "work" / "campaign_xiangshan_first_surface_status.json"
DEFAULT_OPENPITON_GATE_JSON = REPO_ROOT / "work" / "campaign_openpiton_first_surface_gate.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_openpiton_first_surface_acceptance" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_openpiton_first_surface_acceptance_gate.json"


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
        raise FileNotFoundError(f"campaign OpenPiton first-surface acceptance profile not found: {profile_path}")
    return normalized_name, profile_path, _read_json(profile_path)


def _build_outcome(
    *,
    profile_payload: dict[str, Any],
    xiangshan_status_payload: dict[str, Any],
    openpiton_gate_payload: dict[str, Any],
) -> dict[str, Any]:
    accept_selected_step = bool(profile_payload.get("accept_selected_openpiton_first_surface_step"))
    xiangshan_outcome = dict(xiangshan_status_payload.get("outcome") or {})
    openpiton_outcome = dict(openpiton_gate_payload.get("outcome") or {})
    openpiton_selection = dict(openpiton_gate_payload.get("selection") or {})

    xiangshan_status = str(xiangshan_outcome.get("status") or "")
    openpiton_status = str(openpiton_outcome.get("status") or "")

    if accept_selected_step and openpiton_status == "default_gate_ready":
        return {
            "status": "accepted_selected_openpiton_first_surface_step",
            "reason": "the_selected_OpenPiton_default_gate_line_is_ready_and_now_checked_in_as_the_next_non_veer_family_surface",
            "next_action": "decide_next_post_openpiton_family",
            "selected_openpiton_profile_name": openpiton_selection.get("profile_name"),
            "selected_family": openpiton_outcome.get("selected_family"),
            "selected_openpiton_status": openpiton_status,
            "comparison_path": openpiton_outcome.get("comparison_path"),
            "speedup_ratio": openpiton_outcome.get("speedup_ratio"),
            "threshold_value": openpiton_outcome.get("threshold_value"),
        }

    if xiangshan_status != "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family":
        return {
            "status": "blocked_openpiton_fallback_not_active",
            "reason": "OpenPiton first-surface acceptance requires the XiangShan fallback branch to be the active upstream state before acceptance is checked in",
            "next_action": xiangshan_outcome.get("next_action") or "restore_the_openpiton_fallback_branch_context",
        }

    if not accept_selected_step:
        return {
            "status": "hold_selected_openpiton_first_surface_step",
            "reason": "selected_profile_keeps_the_current_OpenPiton_default_gate_line_in_pre_acceptance_state",
            "next_action": openpiton_outcome.get("next_action") or "accept_selected_openpiton_first_surface_step",
            "selected_openpiton_status": openpiton_status or None,
        }

    return {
        "status": "blocked_selected_openpiton_first_surface_step_not_ready",
        "reason": openpiton_outcome.get("reason") or "selected_openpiton_first_surface_step_is_not_ready_for_acceptance",
        "next_action": openpiton_outcome.get("next_action") or "repair_selected_openpiton_first_surface_step",
        "selected_openpiton_status": openpiton_status or None,
    }


def build_gate(
    *,
    xiangshan_status_payload: dict[str, Any],
    openpiton_gate_payload: dict[str, Any],
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
        xiangshan_status_payload=xiangshan_status_payload,
        openpiton_gate_payload=openpiton_gate_payload,
    )
    xiangshan_upstream = dict(xiangshan_status_payload.get("upstream_axes") or {})
    openpiton_selection = dict(openpiton_gate_payload.get("selection") or {})
    openpiton_outcome = dict(openpiton_gate_payload.get("outcome") or {})

    return {
        "schema_version": 1,
        "scope": "campaign_openpiton_first_surface_acceptance_gate",
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()),
            "notes": selection_payload.get("notes"),
        },
        "context": {
            "active_xiangshan_status": dict(xiangshan_status_payload.get("outcome") or {}).get("status"),
            "xiangshan_recommended_family": xiangshan_upstream.get("recommended_family"),
            "selected_openpiton_profile_name": openpiton_selection.get("profile_name"),
            "selected_openpiton_status": openpiton_outcome.get("status"),
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xiangshan-status-json", type=Path, default=DEFAULT_XIANGSHAN_STATUS_JSON)
    parser.add_argument("--openpiton-gate-json", type=Path, default=DEFAULT_OPENPITON_GATE_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_gate(
        xiangshan_status_payload=_read_json(args.xiangshan_status_json.resolve()),
        openpiton_gate_payload=_read_json(args.openpiton_gate_json.resolve()),
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
