#!/usr/bin/env python3
"""
Summarize the current XiangShan first-surface state.

This originally tracked XiangShan as the next non-VeeR family after VeeR family
exhaustion, but it also needs to represent the later "reopen XiangShan behind
Vortex" branch once the Vortex TLS-lowering path is deprioritized.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_AXES_JSON = REPO_ROOT / "work" / "campaign_veer_post_family_exhaustion_axes.json"
DEFAULT_VORTEX_GATE_JSON = REPO_ROOT / "work" / "campaign_vortex_first_surface_gate.json"
DEFAULT_BOOTSTRAP_JSON = REPO_ROOT / "work" / "xiangshan_gpu_cov_stock_verilator_cc_bootstrap.json"
DEFAULT_BASELINE_JSON = REPO_ROOT / "output" / "validation" / "xiangshan_cpu_baseline_validation.json"
DEFAULT_META_JSON = REPO_ROOT / "work" / "vl_ir_exp" / "xiangshan_gpu_cov_vl" / "vl_batch_gpu.meta.json"
DEFAULT_PTX_SMOKE_TRACE_LOG = REPO_ROOT / "work" / "xiangshan_ptx_smoke_trace.log"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xiangshan_first_surface_status.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text_if_exists(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _summarize_trace(trace_text: str | None) -> dict[str, Any]:
    if not trace_text:
        return {
            "present": False,
            "status": None,
            "last_stage": None,
            "device_name": None,
        }
    last_stage = None
    device_name = None
    for raw_line in trace_text.splitlines():
        line = raw_line.strip()
        stage_prefix = "run_vl_hybrid: stage="
        device_prefix = "device 0: "
        if line.startswith(stage_prefix):
            last_stage = line[len(stage_prefix) :].strip() or None
        elif line.startswith(device_prefix):
            device_name = line[len(device_prefix) :].strip() or None
    status = "unknown"
    if "ok: steps=" in trace_text:
        status = "completed_smoke_run"
    elif last_stage == "before_cuModuleLoad":
        status = "stalled_before_cuModuleLoad"
    elif last_stage == "after_cuModuleLoad":
        status = "module_loaded"
    elif last_stage == "after_first_kernel_launch":
        status = "kernel_launch_reached"
    elif last_stage in {"after_dump_state", "after_cleanup"}:
        status = "completed_smoke_run"
    return {
        "present": True,
        "status": status,
        "last_stage": last_stage,
        "device_name": device_name,
    }


def build_status(
    *,
    axes_payload: dict[str, Any] | None,
    vortex_gate_payload: dict[str, Any] | None,
    bootstrap_payload: dict[str, Any] | None,
    baseline_payload: dict[str, Any],
    meta_payload: dict[str, Any] | None,
    ptx_smoke_trace_text: str | None,
    ptx_smoke_timeout_seconds: int,
) -> dict[str, Any]:
    decision = dict((axes_payload or {}).get("decision") or {})
    vortex_outcome = dict((vortex_gate_payload or {}).get("outcome") or {})
    vortex_selection = dict((vortex_gate_payload or {}).get("selection") or {})
    baseline_status = str(baseline_payload.get("status") or "")
    bootstrap_status = str((bootstrap_payload or {}).get("status") or "")
    trace_summary = _summarize_trace(ptx_smoke_trace_text)
    module_format = str((meta_payload or {}).get("cuda_module_format") or "cubin")
    reopened_from_vortex = (
        str(vortex_outcome.get("status") or "") == "reopen_xiangshan_fallback_ready"
        and str(vortex_selection.get("profile_name") or "") == "reopen_xiangshan_fallback_family"
    )
    historical_xiangshan_open = str(decision.get("recommended_family") or "") == "XiangShan"
    stalled_before_module_load = trace_summary.get("status") == "stalled_before_cuModuleLoad"

    if reopened_from_vortex and baseline_status == "ok" and bootstrap_status == "ok" and stalled_before_module_load:
        outcome = {
            "status": "decide_xiangshan_cubin_first_debug_vs_reopen_vortex_tls_lowering_debug",
            "reason": (
                "xiangshan_is_the_current_reopened_fallback_branch_but_the_minimal_ptx_backed_"
                "hybrid_smoke_stalls_before_cuModuleLoad"
            ),
            "next_action": (
                "choose_between_offline_xiangshan_cubin_first_debug_and_reopening_"
                "vortex_tls_lowering_debug"
            ),
        }
        branch_context = {
            "source_scope": "campaign_vortex_first_surface_gate",
            "active_status": vortex_outcome.get("status"),
            "selected_profile_name": vortex_selection.get("profile_name"),
            "active_family": "XiangShan",
            "fallback_branch": "debug_vortex_tls_lowering",
        }
    elif historical_xiangshan_open and baseline_status == "ok" and bootstrap_status == "ok" and stalled_before_module_load:
        outcome = {
            "status": "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family",
            "reason": (
                "xiangshan_bootstrap_and_cpu_baseline_are_ready_but_the_minimal_ptx_backed_"
                "hybrid_smoke_stalls_before_cuModuleLoad"
            ),
            "next_action": (
                "choose_between_offline_xiangshan_cubin_first_debug_and_opening_"
                "openpiton_fallback_family"
            ),
        }
        branch_context = {
            "source_scope": "campaign_veer_post_family_exhaustion_axes",
            "active_status": decision.get("status"),
            "selected_profile_name": None,
            "active_family": decision.get("recommended_family"),
            "fallback_branch": "open_openpiton_fallback_family",
        }
    elif baseline_status == "ok" and trace_summary.get("status") in {
        "module_loaded",
        "kernel_launch_reached",
        "completed_smoke_run",
    }:
        outcome = {
            "status": "ready_to_finish_xiangshan_first_trio",
            "reason": "xiangshan_bootstrap_cpu_baseline_and_minimal_hybrid_runtime_are_ready",
            "next_action": "finish_xiangshan_stock_hybrid_validation_and_compare_gate_policy",
        }
        branch_context = {
            "source_scope": (
                "campaign_vortex_first_surface_gate"
                if reopened_from_vortex
                else "campaign_veer_post_family_exhaustion_axes"
            ),
            "active_status": (
                vortex_outcome.get("status") if reopened_from_vortex else decision.get("status")
            ),
            "selected_profile_name": vortex_selection.get("profile_name") if reopened_from_vortex else None,
            "active_family": "XiangShan",
            "fallback_branch": (
                "debug_vortex_tls_lowering" if reopened_from_vortex else "open_openpiton_fallback_family"
            ),
        }
    else:
        outcome = {
            "status": "bootstrap_or_repair_xiangshan_first_surface",
            "reason": "xiangshan_does_not_yet_have_the_expected_bootstrap_baseline_and_runtime_state",
            "next_action": "repair_the_missing_xiangshan_runtime_prerequisites",
        }
        branch_context = {
            "source_scope": (
                "campaign_vortex_first_surface_gate"
                if reopened_from_vortex
                else "campaign_veer_post_family_exhaustion_axes"
            ),
            "active_status": (
                vortex_outcome.get("status") if reopened_from_vortex else decision.get("status")
            ),
            "selected_profile_name": vortex_selection.get("profile_name") if reopened_from_vortex else None,
            "active_family": "XiangShan" if reopened_from_vortex else decision.get("recommended_family"),
            "fallback_branch": (
                "debug_vortex_tls_lowering" if reopened_from_vortex else "open_openpiton_fallback_family"
            ),
        }
    return {
        "schema_version": 1,
        "scope": "campaign_xiangshan_first_surface_status",
        "upstream_axes": {
            "recommended_family": decision.get("recommended_family"),
            "fallback_family": decision.get("fallback_family"),
            "status": decision.get("status"),
        },
        "current_branch": branch_context,
        "bootstrap": {
            "present": bootstrap_payload is not None,
            "status": bootstrap_status or None,
            "cpp_source_count": (bootstrap_payload or {}).get("cpp_source_count"),
            "cpp_include_count": (bootstrap_payload or {}).get("cpp_include_count"),
        },
        "cpu_baseline": {
            "status": baseline_status or None,
            "campaign_threshold": baseline_payload.get("campaign_threshold"),
            "campaign_measurement": baseline_payload.get("campaign_measurement"),
        },
        "gpu_module": {
            "meta_present": meta_payload is not None,
            "module_format": module_format,
            "module_path": (meta_payload or {}).get("cubin"),
            "storage_size": (meta_payload or {}).get("storage_size"),
            "incremental_mode": (meta_payload or {}).get("incremental_mode"),
        },
        "ptx_smoke": {
            **trace_summary,
            "timeout_seconds": ptx_smoke_timeout_seconds,
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--axes-json", type=Path, default=DEFAULT_AXES_JSON)
    parser.add_argument("--vortex-gate-json", type=Path, default=DEFAULT_VORTEX_GATE_JSON)
    parser.add_argument("--bootstrap-json", type=Path, default=DEFAULT_BOOTSTRAP_JSON)
    parser.add_argument("--baseline-json", type=Path, default=DEFAULT_BASELINE_JSON)
    parser.add_argument("--meta-json", type=Path, default=DEFAULT_META_JSON)
    parser.add_argument("--ptx-smoke-trace-log", type=Path, default=DEFAULT_PTX_SMOKE_TRACE_LOG)
    parser.add_argument("--ptx-smoke-timeout-seconds", type=int, default=20)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    axes_payload = _read_json(args.axes_json.resolve()) if args.axes_json.resolve().is_file() else None
    bootstrap_payload = (
        _read_json(args.bootstrap_json.resolve()) if args.bootstrap_json.resolve().is_file() else None
    )
    meta_payload = _read_json(args.meta_json.resolve()) if args.meta_json.resolve().is_file() else None
    payload = build_status(
        axes_payload=axes_payload,
        vortex_gate_payload=(
            _read_json(args.vortex_gate_json.resolve()) if args.vortex_gate_json.resolve().is_file() else None
        ),
        bootstrap_payload=bootstrap_payload,
        baseline_payload=_read_json(args.baseline_json.resolve()),
        meta_payload=meta_payload,
        ptx_smoke_trace_text=_read_text_if_exists(args.ptx_smoke_trace_log.resolve()),
        ptx_smoke_timeout_seconds=args.ptx_smoke_timeout_seconds,
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
