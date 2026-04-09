#!/usr/bin/env python3
"""
Resolve the selected Vortex first-surface branch profile against the
post-BlackParrot axes and the current Vortex blocker state.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_VORTEX_STATUS_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_status.json"
DEFAULT_POST_BLACKPARROT_AXES_JSON = REPO_ROOT / "work" / "campaign_post_blackparrot_axes.json"
DEFAULT_XIANGSHAN_STATUS_JSON = REPO_ROOT / "work" / "campaign_xiangshan_first_surface_status.json"
DEFAULT_SELECTION_CONFIG = REPO_ROOT / "config" / "campaign_vortex_first_surface" / "selection.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_vortex_first_surface_gate.json"


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
        raise FileNotFoundError(f"campaign Vortex first-surface profile not found: {profile_path}")
    return normalized_name, profile_path, _read_json(profile_path)


def _build_outcome(
    *,
    profile_payload: dict[str, Any],
    vortex_status_payload: dict[str, Any],
    post_blackparrot_axes_payload: dict[str, Any],
    xiangshan_status_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    branch_mode = str(profile_payload.get("branch_mode") or "")
    axes_decision = dict(post_blackparrot_axes_payload.get("decision") or {})
    vortex_outcome = dict(vortex_status_payload.get("outcome") or {})
    vortex_build = dict(vortex_status_payload.get("gpu_build") or {})
    xiangshan_outcome = dict((xiangshan_status_payload or {}).get("outcome") or {})

    axes_status = str(axes_decision.get("status") or "")
    recommended_family = str(axes_decision.get("recommended_family") or "")
    fallback_family = str(axes_decision.get("fallback_family") or "")
    vortex_status = str(vortex_outcome.get("status") or "")
    xiangshan_status = str(xiangshan_outcome.get("status") or "")

    if axes_status != "decide_open_next_family_after_blackparrot_baseline_loss":
        return {
            "status": "blocked_vortex_branch_not_active",
            "reason": "the_Vortex_first-surface decision only applies after the post-BlackParrot axes select the next family after baseline loss",
            "next_action": axes_decision.get("recommended_next_task") or "refresh_post_blackparrot_axes",
        }

    if recommended_family != "Vortex":
        return {
            "status": "blocked_selected_family_is_not_vortex",
            "reason": "the_current_post-BlackParrot axes artifact does not point at Vortex",
            "next_action": "refresh_the_post_blackparrot_axes_artifact_before_selecting_a_Vortex_profile",
        }

    if branch_mode == "hold_vortex_first_surface_branch":
        return {
            "status": "hold_vortex_first_surface_branch",
            "reason": "the_selected_profile_keeps_the_Vortex branch in pre-selection state",
            "next_action": vortex_outcome.get("next_action") or "choose_between_Vortex_debug_and_XiangShan_fallback",
            "vortex_status": vortex_status or None,
        }

    if branch_mode == "debug_vortex_tls_lowering":
        if vortex_status == "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback":
            return {
                "status": "debug_vortex_tls_lowering_ready",
                "reason": vortex_outcome.get("reason")
                or "Vortex bootstrap and CPU baseline are ready but llc still fails while lowering Verilated TLS",
                "next_action": vortex_outcome.get("next_action")
                or "offline_vortex_tls_lowering_debug",
                "selected_family": "Vortex",
                "gpu_build_status": vortex_build.get("status"),
                "gpu_blocker_kind": vortex_build.get("blocker_kind"),
                "failing_function": vortex_build.get("failing_function"),
            }
        if vortex_status == "ready_to_finish_vortex_first_trio":
            return {
                "status": "vortex_gpu_build_recovered_ready_to_finish_trio",
                "reason": "the_Vortex_gpu_build_is_no_longer_the_blocker_for_the_first_surface",
                "next_action": "finish_the_Vortex_first_campaign_trio",
                "selected_family": "Vortex",
            }
        return {
            "status": "blocked_vortex_debug_not_ready",
            "reason": vortex_outcome.get("reason")
            or "the_current_Vortex_state_does_not_support_the_TLS-lowering debug branch",
            "next_action": vortex_outcome.get("next_action") or "repair_the_Vortex_build_prerequisites",
        }

    if branch_mode == "reopen_xiangshan_fallback_family":
        if fallback_family == "XiangShan":
            return {
                "status": "reopen_xiangshan_fallback_ready",
                "reason": "the_post-BlackParrot axes artifact exposes blocked XiangShan as the fallback family behind Vortex",
                "next_action": xiangshan_outcome.get("next_action")
                or "reopen_the_XiangShan_fallback_family",
                "fallback_family": fallback_family,
                "fallback_status": xiangshan_status or None,
            }
        return {
            "status": "blocked_xiangshan_fallback_not_ready",
            "reason": "the_current_post-BlackParrot axes artifact does not expose XiangShan as the fallback family",
            "next_action": "refresh_the_post_blackparrot_axes_artifact_before_switching_to_XiangShan",
        }

    return {
        "status": "blocked_unknown_vortex_branch_mode",
        "reason": f"unknown Vortex first-surface branch mode: {branch_mode}",
        "next_action": "repair_the_Vortex_profile_selection",
    }


def build_gate(
    *,
    vortex_status_payload: dict[str, Any],
    post_blackparrot_axes_payload: dict[str, Any],
    xiangshan_status_payload: dict[str, Any] | None,
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
        vortex_status_payload=vortex_status_payload,
        post_blackparrot_axes_payload=post_blackparrot_axes_payload,
        xiangshan_status_payload=xiangshan_status_payload,
    )
    axes_decision = dict(post_blackparrot_axes_payload.get("decision") or {})
    vortex_outcome = dict(vortex_status_payload.get("outcome") or {})
    xiangshan_outcome = dict((xiangshan_status_payload or {}).get("outcome") or {})

    return {
        "schema_version": 1,
        "scope": "campaign_vortex_first_surface_gate",
        "selection_config_path": str(selection_path.resolve()),
        "selection": {
            "profile_name": profile_name,
            "profile_path": str(profile_path.resolve()),
            "notes": selection_payload.get("notes"),
        },
        "context": {
            "recommended_family": axes_decision.get("recommended_family"),
            "fallback_family": axes_decision.get("fallback_family"),
            "post_blackparrot_status": axes_decision.get("status"),
            "vortex_status": vortex_outcome.get("status"),
            "xiangshan_status": xiangshan_outcome.get("status"),
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vortex-status-json", type=Path, default=DEFAULT_VORTEX_STATUS_JSON)
    parser.add_argument("--post-blackparrot-axes-json", type=Path, default=DEFAULT_POST_BLACKPARROT_AXES_JSON)
    parser.add_argument("--xiangshan-status-json", type=Path, default=DEFAULT_XIANGSHAN_STATUS_JSON)
    parser.add_argument("--selection-config", type=Path, default=DEFAULT_SELECTION_CONFIG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    xiangshan_path = args.xiangshan_status_json.resolve()
    payload = build_gate(
        vortex_status_payload=_read_json(args.vortex_status_json.resolve()),
        post_blackparrot_axes_payload=_read_json(args.post_blackparrot_axes_json.resolve()),
        xiangshan_status_payload=_read_json(xiangshan_path) if xiangshan_path.is_file() else None,
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
