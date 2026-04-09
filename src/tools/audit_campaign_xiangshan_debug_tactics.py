#!/usr/bin/env python3
"""
Summarize the next concrete debug tactic for the current XiangShan first-surface
branch after Vortex reopens XiangShan as the active fallback family.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_XIANGSHAN_STATUS_JSON = REPO_ROOT / "work" / "campaign_xiangshan_first_surface_status.json"
DEFAULT_VORTEX_PROFILES_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_profiles.json"
DEFAULT_PTXAS_PROBE_JSON = REPO_ROOT / "work" / "xiangshan_ptxas_probe.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xiangshan_debug_tactics.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_tactics(
    *,
    xiangshan_status_payload: dict[str, Any],
    vortex_profiles_payload: dict[str, Any] | None,
    ptxas_probe_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    current_branch = dict(xiangshan_status_payload.get("current_branch") or {})
    outcome = dict(xiangshan_status_payload.get("outcome") or {})
    ptx_smoke = dict(xiangshan_status_payload.get("ptx_smoke") or {})
    gpu_module = dict(xiangshan_status_payload.get("gpu_module") or {})
    probe = dict(ptxas_probe_payload or {})
    profiles_summary = dict((vortex_profiles_payload or {}).get("summary") or {})

    branch_source = str(current_branch.get("source_scope") or "")
    selected_profile_name = str(current_branch.get("selected_profile_name") or "")
    fallback_branch = str(current_branch.get("fallback_branch") or "")
    xiangshan_status = str(outcome.get("status") or "")
    ptx_smoke_status = str(ptx_smoke.get("status") or "")
    ptxas_status = str(probe.get("status") or "")
    ready_profiles = list(profiles_summary.get("ready_profiles") or [])
    fallback_ready = fallback_branch in ready_profiles if fallback_branch else False

    if (
        branch_source != "campaign_vortex_first_surface_gate"
        or selected_profile_name != "reopen_xiangshan_fallback_family"
    ):
        decision = {
            "status": "select_xiangshan_reopen_branch_first",
            "reason": "the_current_checked_in_branch_is_not_the_reopened_XiangShan_fallback_branch",
            "recommended_next_tactic": "reopen_xiangshan_fallback_family",
            "fallback_tactic": "debug_vortex_tls_lowering",
        }
    elif xiangshan_status == "ready_to_finish_xiangshan_first_trio":
        decision = {
            "status": "ready_to_finish_xiangshan_first_trio",
            "reason": "xiangshan_bootstrap_cpu_baseline_and_minimal_hybrid_runtime_are_ready",
            "recommended_next_tactic": "finish_xiangshan_stock_hybrid_validation_and_compare_gate_policy",
            "fallback_tactic": None,
        }
    elif (
        xiangshan_status == "decide_xiangshan_cubin_first_debug_vs_reopen_vortex_tls_lowering_debug"
        and ptx_smoke_status == "stalled_before_cuModuleLoad"
        and ptxas_status in {"timed_out", "error", "killed"}
    ):
        decision = {
            "status": "prefer_reopen_vortex_after_xiangshan_ptxas_probe_failed",
            "reason": (
                "the_minimal_ptx_backed_smoke_stalls_before_cuModuleLoad_and_the_offline_ptxas_"
                "probe_does_not_produce_a_cubin"
            ),
            "recommended_next_tactic": "reopen_vortex_tls_lowering_debug",
            "fallback_tactic": "deeper_xiangshan_cubin_first_debug",
        }
    elif xiangshan_status == "decide_xiangshan_cubin_first_debug_vs_reopen_vortex_tls_lowering_debug":
        decision = {
            "status": "continue_xiangshan_cubin_first_debug",
            "reason": outcome.get("reason")
            or "xiangshan_is_the_active_reopened_branch_and_still_needs_cubin-first_debug",
            "recommended_next_tactic": "offline_xiangshan_cubin_first_debug",
            "fallback_tactic": "reopen_vortex_tls_lowering_debug",
        }
    else:
        decision = {
            "status": "repair_xiangshan_branch_state",
            "reason": outcome.get("reason")
            or "the_current_XiangShan_state_does_not_match_a_more_specific_debug_tactic",
            "recommended_next_tactic": outcome.get("next_action")
            or "repair_the_missing_xiangshan_runtime_prerequisites",
            "fallback_tactic": "reopen_vortex_tls_lowering_debug",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_xiangshan_debug_tactics",
        "current_branch": {
            "source_scope": branch_source or None,
            "selected_profile_name": selected_profile_name or None,
            "fallback_branch": fallback_branch or None,
            "fallback_branch_ready": fallback_ready,
        },
        "observations": {
            "xiangshan_status": xiangshan_status or None,
            "ptx_smoke_status": ptx_smoke_status or None,
            "ptx_smoke_last_stage": ptx_smoke.get("last_stage"),
            "gpu_module_format": gpu_module.get("module_format"),
            "gpu_module_path": gpu_module.get("module_path"),
            "ptxas_probe_status": ptxas_status or None,
            "ptxas_probe_elapsed_ms": probe.get("elapsed_ms"),
            "ptxas_probe_cubin_exists": probe.get("cubin_exists"),
        },
        "capabilities": {
            "offline_ptxas_probe_present": bool(ptxas_probe_payload),
            "fallback_vortex_profile_ready": fallback_ready,
            "gpu_module_format": gpu_module.get("module_format"),
        },
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xiangshan-status-json", type=Path, default=DEFAULT_XIANGSHAN_STATUS_JSON)
    parser.add_argument("--vortex-profiles-json", type=Path, default=DEFAULT_VORTEX_PROFILES_JSON)
    parser.add_argument("--ptxas-probe-json", type=Path, default=DEFAULT_PTXAS_PROBE_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    profiles_path = args.vortex_profiles_json.resolve()
    probe_path = args.ptxas_probe_json.resolve()
    payload = build_tactics(
        xiangshan_status_payload=_read_json(args.xiangshan_status_json.resolve()),
        vortex_profiles_payload=_read_json(profiles_path) if profiles_path.is_file() else None,
        ptxas_probe_payload=_read_json(probe_path) if probe_path.is_file() else None,
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
