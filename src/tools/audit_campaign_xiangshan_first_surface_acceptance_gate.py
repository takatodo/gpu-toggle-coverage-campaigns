#!/usr/bin/env python3
"""
Resolve the selected XiangShan first-surface acceptance profile against the
active Vortex gate and the active XiangShan first-surface gate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_VORTEX_GATE_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_gate.json"
DEFAULT_XIANGSHAN_GATE_JSON = REPO_ROOT / "work" / "campaign_xiangshan_first_surface_gate.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_xiangshan_first_surface_acceptance" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xiangshan_first_surface_acceptance_gate.json"


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
        raise FileNotFoundError(f"campaign XiangShan first-surface acceptance profile not found: {profile_path}")
    return normalized_name, profile_path, _read_json(profile_path)


def _build_outcome(
    *,
    profile_payload: dict[str, Any],
    vortex_gate_payload: dict[str, Any],
    xiangshan_gate_payload: dict[str, Any],
) -> dict[str, Any]:
    accept_selected_step = bool(profile_payload.get("accept_selected_xiangshan_first_surface_step"))
    vortex_outcome = dict(vortex_gate_payload.get("outcome") or {})
    vortex_selection = dict(vortex_gate_payload.get("selection") or {})
    xiangshan_outcome = dict(xiangshan_gate_payload.get("outcome") or {})
    xiangshan_selection = dict(xiangshan_gate_payload.get("selection") or {})

    vortex_status = str(vortex_outcome.get("status") or "")
    xiangshan_status = str(xiangshan_outcome.get("status") or "")

    if accept_selected_step and xiangshan_status in {"candidate_only_ready", "default_gate_ready"}:
        return {
            "status": "accepted_selected_xiangshan_first_surface_step",
            "reason": "the_selected_XiangShan_first-surface_step_is_ready_and_now_checked-in_as_the_reopened_fallback-family_breadth_evidence",
            "next_action": "reopen_vortex_tls_lowering_debug_after_accepting_xiangshan",
            "selected_vortex_profile_name": vortex_selection.get("profile_name"),
            "selected_xiangshan_profile_name": xiangshan_selection.get("profile_name"),
            "selected_design": xiangshan_outcome.get("selected_design"),
            "selected_xiangshan_status": xiangshan_status,
            "comparison_path": xiangshan_outcome.get("comparison_path"),
            "speedup_ratio": xiangshan_outcome.get("speedup_ratio"),
            "candidate_threshold_value": xiangshan_outcome.get("candidate_threshold_value"),
        }

    if vortex_status != "reopen_xiangshan_fallback_ready":
        return {
            "status": "blocked_xiangshan_fallback_not_active",
            "reason": "XiangShan first-surface acceptance requires the checked-in Vortex gate to point at the reopened XiangShan fallback branch",
            "next_action": vortex_outcome.get("next_action") or "restore_the_reopen_xiangshan_fallback_branch_context",
            "selected_vortex_status": vortex_status or None,
        }

    if not accept_selected_step:
        return {
            "status": "hold_selected_xiangshan_first_surface_step",
            "reason": "selected_profile_keeps_the_current_XiangShan_first-surface_step_in_pre-acceptance_state",
            "next_action": xiangshan_outcome.get("next_action") or "accept_selected_xiangshan_first_surface_step",
            "selected_xiangshan_status": xiangshan_status or None,
        }

    return {
        "status": "blocked_selected_xiangshan_first_surface_step_not_ready",
        "reason": xiangshan_outcome.get("reason")
        or "selected_xiangshan_first_surface_step_is_not_ready_for_acceptance",
        "next_action": xiangshan_outcome.get("next_action") or "repair_selected_xiangshan_first_surface_step",
        "selected_xiangshan_status": xiangshan_status or None,
    }


def build_gate(
    *,
    vortex_gate_payload: dict[str, Any],
    xiangshan_gate_payload: dict[str, Any],
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
        vortex_gate_payload=vortex_gate_payload,
        xiangshan_gate_payload=xiangshan_gate_payload,
    )
    vortex_selection = dict(vortex_gate_payload.get("selection") or {})
    vortex_outcome = dict(vortex_gate_payload.get("outcome") or {})
    xiangshan_selection = dict(xiangshan_gate_payload.get("selection") or {})
    xiangshan_outcome = dict(xiangshan_gate_payload.get("outcome") or {})

    return {
        "schema_version": 1,
        "scope": "campaign_xiangshan_first_surface_acceptance_gate",
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()),
            "notes": selection_payload.get("notes"),
        },
        "context": {
            "selected_vortex_profile_name": vortex_selection.get("profile_name"),
            "selected_vortex_status": vortex_outcome.get("status"),
            "selected_xiangshan_profile_name": xiangshan_selection.get("profile_name"),
            "selected_xiangshan_status": xiangshan_outcome.get("status"),
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vortex-gate-json", type=Path, default=DEFAULT_VORTEX_GATE_JSON)
    parser.add_argument("--xiangshan-gate-json", type=Path, default=DEFAULT_XIANGSHAN_GATE_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_gate(
        vortex_gate_payload=_read_json(args.vortex_gate_json.resolve()),
        xiangshan_gate_payload=_read_json(args.xiangshan_gate_json.resolve()),
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
