#!/usr/bin/env python3
"""
Resolve the XiangShan/Vortex fallback loop into one stable next tactic.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_VORTEX_GATE_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_gate.json"
DEFAULT_VORTEX_ACCEPTANCE_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_acceptance_gate.json"
DEFAULT_POST_VORTEX_AXES_JSON = REPO_ROOT / "work" / "campaign_post_vortex_axes.json"
DEFAULT_XIANGSHAN_STATUS_JSON = REPO_ROOT / "work" / "campaign_xiangshan_first_surface_status.json"
DEFAULT_XIANGSHAN_TACTICS_JSON = REPO_ROOT / "work" / "campaign_xiangshan_debug_tactics.json"
DEFAULT_VORTEX_TACTICS_JSON = REPO_ROOT / "work" / "campaign_vortex_debug_tactics.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xiangshan_vortex_branch_resolution.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _branch_profile_for_tactic(tactic_name: str | None) -> str | None:
    if tactic_name == "reopen_vortex_tls_lowering_debug":
        return "debug_vortex_tls_lowering"
    if tactic_name == "deeper_vortex_tls_lowering_debug":
        return "debug_vortex_tls_lowering"
    if tactic_name == "reopen_xiangshan_fallback_family":
        return "reopen_xiangshan_fallback_family"
    if tactic_name == "deeper_xiangshan_cubin_first_debug":
        return "reopen_xiangshan_fallback_family"
    return None


def build_resolution(
    *,
    vortex_gate_payload: dict[str, Any],
    vortex_acceptance_payload: dict[str, Any] | None,
    post_vortex_axes_payload: dict[str, Any] | None,
    xiangshan_status_payload: dict[str, Any],
    xiangshan_tactics_payload: dict[str, Any],
    vortex_tactics_payload: dict[str, Any],
) -> dict[str, Any]:
    gate_selection = dict(vortex_gate_payload.get("selection") or {})
    gate_outcome = dict(vortex_gate_payload.get("outcome") or {})
    acceptance_outcome = dict((vortex_acceptance_payload or {}).get("outcome") or {})
    post_vortex_decision = dict((post_vortex_axes_payload or {}).get("decision") or {})
    xiangshan_outcome = dict(xiangshan_status_payload.get("outcome") or {})
    xiangshan_decision = dict(xiangshan_tactics_payload.get("decision") or {})
    vortex_decision = dict(vortex_tactics_payload.get("decision") or {})

    selected_profile_name = str(gate_selection.get("profile_name") or "")
    gate_status = str(gate_outcome.get("status") or "")
    acceptance_status = str(acceptance_outcome.get("status") or "")
    xiangshan_status = str(xiangshan_outcome.get("status") or "")
    xiangshan_recommended = str(xiangshan_decision.get("recommended_next_tactic") or "")
    xiangshan_fallback = str(xiangshan_decision.get("fallback_tactic") or "")
    vortex_recommended = str(vortex_decision.get("recommended_next_tactic") or "")
    vortex_fallback = str(vortex_decision.get("fallback_tactic") or "")

    xiangshan_reopens_vortex = xiangshan_recommended == "reopen_vortex_tls_lowering_debug"
    vortex_reopens_xiangshan = vortex_recommended == "reopen_xiangshan_fallback_family"
    oscillation_detected = xiangshan_reopens_vortex and vortex_reopens_xiangshan

    if acceptance_status == "accepted_selected_vortex_first_surface_step":
        decision = {
            "status": "follow_post_vortex_axes_after_accepting_vortex",
            "reason": "the_Vortex_first_surface_is_already_accepted_so_cross-branch_reopen_arbitration_is_no_longer_the_main_line",
            "recommended_profile_name": selected_profile_name or "debug_vortex_tls_lowering",
            "recommended_next_tactic": post_vortex_decision.get("recommended_next_task")
            or acceptance_outcome.get("next_action")
            or "decide_post_vortex_family_axes_after_accepting_vortex",
            "fallback_profile_name": None,
            "fallback_tactic": None,
        }
    elif selected_profile_name == "reopen_xiangshan_fallback_family" and oscillation_detected:
        decision = {
            "status": "avoid_xiangshan_vortex_reopen_loop_keep_current_xiangshan_branch",
            "reason": (
                "the_current_checked-in_branch_already_points_at_XiangShan_but_the_XiangShan_cheap_cubin-first_"
                "line_now_points_back_to_Vortex_while_the_Vortex_debug_branch_still_points_back_to_XiangShan"
            ),
            "recommended_profile_name": "reopen_xiangshan_fallback_family",
            "recommended_next_tactic": "deeper_xiangshan_cubin_first_debug",
            "fallback_profile_name": "debug_vortex_tls_lowering",
            "fallback_tactic": "deeper_vortex_tls_lowering_debug",
        }
    elif selected_profile_name == "debug_vortex_tls_lowering" and oscillation_detected:
        decision = {
            "status": "avoid_xiangshan_vortex_reopen_loop_keep_current_vortex_branch",
            "reason": (
                "the_current_checked-in_branch_already_points_at_Vortex_but_the_Vortex_low-cost_debug_path_"
                "points_back_to_XiangShan_while_the_XiangShan_cheap_cubin-first_line_points_back_to_Vortex"
            ),
            "recommended_profile_name": "debug_vortex_tls_lowering",
            "recommended_next_tactic": "deeper_vortex_tls_lowering_debug",
            "fallback_profile_name": "reopen_xiangshan_fallback_family",
            "fallback_tactic": "deeper_xiangshan_cubin_first_debug",
        }
    elif selected_profile_name == "reopen_xiangshan_fallback_family":
        decision = {
            "status": "follow_current_xiangshan_branch_tactic",
            "reason": xiangshan_decision.get("reason")
            or "the_current_checked-in_branch_already_points_at_XiangShan_and_does_not_need_cross-branch_arbitration",
            "recommended_profile_name": "reopen_xiangshan_fallback_family",
            "recommended_next_tactic": xiangshan_recommended
            or xiangshan_outcome.get("next_action")
            or "offline_xiangshan_cubin_first_debug",
            "fallback_profile_name": _branch_profile_for_tactic(xiangshan_fallback) or "debug_vortex_tls_lowering",
            "fallback_tactic": xiangshan_fallback or "reopen_vortex_tls_lowering_debug",
        }
    elif selected_profile_name == "debug_vortex_tls_lowering":
        decision = {
            "status": "follow_current_vortex_branch_tactic",
            "reason": vortex_decision.get("reason")
            or "the_current_checked-in_branch_already_points_at_Vortex_and_does_not_need_cross-branch_arbitration",
            "recommended_profile_name": "debug_vortex_tls_lowering",
            "recommended_next_tactic": vortex_recommended
            or gate_outcome.get("next_action")
            or "offline_vortex_tls_lowering_debug",
            "fallback_profile_name": _branch_profile_for_tactic(vortex_fallback) or "reopen_xiangshan_fallback_family",
            "fallback_tactic": vortex_fallback or "reopen_xiangshan_fallback_family",
        }
    else:
        decision = {
            "status": "repair_vortex_xiangshan_branch_context",
            "reason": "the_current_checked-in_Vortex/XiangShan_branch_context_is_missing_or_unknown",
            "recommended_profile_name": selected_profile_name or None,
            "recommended_next_tactic": gate_outcome.get("next_action") or "repair_the_current_branch_context",
            "fallback_profile_name": None,
            "fallback_tactic": None,
        }

    return {
        "schema_version": 1,
        "scope": "campaign_xiangshan_vortex_branch_resolution",
        "current_branch": {
            "selected_profile_name": selected_profile_name or None,
            "gate_status": gate_status or None,
            "acceptance_status": acceptance_status or None,
            "active_family": "XiangShan" if selected_profile_name == "reopen_xiangshan_fallback_family" else "Vortex" if selected_profile_name == "debug_vortex_tls_lowering" else None,
        },
        "observations": {
            "xiangshan_status": xiangshan_status or None,
            "xiangshan_recommended_next_tactic": xiangshan_recommended or None,
            "xiangshan_fallback_tactic": xiangshan_fallback or None,
            "vortex_recommended_next_tactic": vortex_recommended or None,
            "vortex_fallback_tactic": vortex_fallback or None,
            "oscillation_detected": oscillation_detected,
        },
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vortex-gate-json", type=Path, default=DEFAULT_VORTEX_GATE_JSON)
    parser.add_argument("--vortex-acceptance-json", type=Path, default=DEFAULT_VORTEX_ACCEPTANCE_JSON)
    parser.add_argument("--post-vortex-axes-json", type=Path, default=DEFAULT_POST_VORTEX_AXES_JSON)
    parser.add_argument("--xiangshan-status-json", type=Path, default=DEFAULT_XIANGSHAN_STATUS_JSON)
    parser.add_argument("--xiangshan-tactics-json", type=Path, default=DEFAULT_XIANGSHAN_TACTICS_JSON)
    parser.add_argument("--vortex-tactics-json", type=Path, default=DEFAULT_VORTEX_TACTICS_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_resolution(
        vortex_gate_payload=_read_json(args.vortex_gate_json.resolve()),
        vortex_acceptance_payload=_read_json(args.vortex_acceptance_json.resolve())
        if args.vortex_acceptance_json.resolve().is_file()
        else None,
        post_vortex_axes_payload=_read_json(args.post_vortex_axes_json.resolve())
        if args.post_vortex_axes_json.resolve().is_file()
        else None,
        xiangshan_status_payload=_read_json(args.xiangshan_status_json.resolve()),
        xiangshan_tactics_payload=_read_json(args.xiangshan_tactics_json.resolve()),
        vortex_tactics_payload=_read_json(args.vortex_tactics_json.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
