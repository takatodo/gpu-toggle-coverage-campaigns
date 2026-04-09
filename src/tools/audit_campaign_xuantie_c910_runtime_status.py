#!/usr/bin/env python3
"""
Summarize the current C910 runtime state after the XuanTie same-family branch
selects C910 as the next design.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_HYBRID_JSON = REPO_ROOT / "output" / "validation" / "xuantie_c910_stock_hybrid_validation.json"
DEFAULT_BASELINE_JSON = REPO_ROOT / "output" / "validation" / "xuantie_c910_cpu_baseline_validation.json"
DEFAULT_META_JSON = REPO_ROOT / "work" / "vl_ir_exp" / "xuantie_c910_gpu_cov_gate_vl" / "vl_batch_gpu.meta.json"
DEFAULT_RUNTIME_SMOKE_JSON = REPO_ROOT / "work" / "xuantie_c910_runtime_smoke.json"
DEFAULT_O0_BUILD_LOG = REPO_ROOT / "work" / "c910_o0_build.log"
DEFAULT_O1_TRACE_LOG = REPO_ROOT / "work" / "c910_o1_trace.log"
DEFAULT_CUBIN_PROBE_JSON = REPO_ROOT / "work" / "c910_ptxas_o1_probe.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xuantie_c910_runtime_status.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text_if_exists(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _summarize_o0_build(log_text: str | None) -> dict[str, Any]:
    if not log_text:
        return {
            "present": False,
            "status": None,
        }
    if "LLVM ERROR: Cannot select:" in log_text and "AtomicLoad" in log_text:
        return {
            "present": True,
            "status": "llc_sigabrt_on_atomicload_acquire_i64",
        }
    if "Done:" in log_text and "vl_batch_gpu.ptx" in log_text:
        return {
            "present": True,
            "status": "ptx_ready",
        }
    return {
        "present": True,
        "status": "unknown",
    }


def _summarize_o1_trace(trace_text: str | None) -> dict[str, Any]:
    if not trace_text:
        return {
            "present": False,
            "status": None,
            "last_stage": None,
        }
    last_stage = None
    for raw_line in trace_text.splitlines():
        prefix = "run_vl_hybrid: stage="
        if raw_line.startswith(prefix):
            last_stage = raw_line[len(prefix):].strip() or None
    status = "unknown"
    if last_stage == "before_cuModuleLoad":
        status = "stalled_before_cuModuleLoad"
    elif last_stage == "after_cuModuleLoad":
        status = "module_loaded"
    elif last_stage == "after_first_kernel_launch":
        status = "kernel_launch_reached"
    return {
        "present": True,
        "status": status,
        "last_stage": last_stage,
    }


def build_status(
    *,
    hybrid_payload: dict[str, Any],
    baseline_payload: dict[str, Any],
    meta_payload: dict[str, Any] | None,
    runtime_smoke_payload: dict[str, Any] | None,
    o0_build_log_text: str | None,
    o1_trace_log_text: str | None,
    cubin_probe_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    hybrid_status = str(hybrid_payload.get("status") or "")
    baseline_status = str(baseline_payload.get("status") or "")
    module_format = str((meta_payload or {}).get("cuda_module_format") or "cubin")
    stderr_tail = str(hybrid_payload.get("stderr_tail") or "")
    smoke_decision = dict((runtime_smoke_payload or {}).get("decision") or {})
    smoke_runs = list((runtime_smoke_payload or {}).get("runs") or [])
    o0_build = _summarize_o0_build(o0_build_log_text)
    o1_trace = _summarize_o1_trace(o1_trace_log_text)
    cubin_probe = dict(cubin_probe_payload or {})
    hybrid_runtime_killed = (
        "died with <Signals.SIGKILL: 9>" in stderr_tail
        or str(smoke_decision.get("status") or "") == "hybrid_runtime_killed_even_at_minimal_shapes"
        or any(str(row.get("outcome") or "") == "sigkill" for row in smoke_runs)
    )

    if baseline_status == "ok" and hybrid_runtime_killed:
        reason = (
            "xuantie_c910_cpu_baseline_is_ok_but_the_ptx_backed_hybrid_runtime_is_still_"
            "killed_before_a_ready_comparison_line_exists"
        )
        next_action = (
            "choose_between_debugging_the_c910_hybrid_runtime_and_opening_the_veer_"
            "fallback_family"
        )
        if o1_trace.get("status") == "stalled_before_cuModuleLoad":
            reason = (
                "xuantie_c910_cpu_baseline_is_ok_but_the_ptx_backed_hybrid_runtime_still_"
                "stalls_before_cuModuleLoad_even_after_an_O1_rebuild"
            )
            next_action = (
                "choose_between_offline_cubin_assembly_for_c910_and_opening_the_veer_"
                "fallback_family"
            )
        if str(cubin_probe.get("status") or "") in {"killed", "timed_out"}:
            reason = (
                "xuantie_c910_cpu_baseline_is_ok_but_both_the_ptx_backed_runtime_and_the_"
                "current_offline_cubin_attempts_remain_unready"
            )
            next_action = (
                "choose_between_deeper_c910_cubin_debug_and_opening_the_veer_fallback_family"
            )
        outcome = {
            "status": "decide_hybrid_runtime_debug_vs_open_veer_fallback_family",
            "reason": reason,
            "next_action": next_action,
        }
    elif baseline_status == "ok" and hybrid_status == "ok":
        outcome = {
            "status": "ready_to_compare_c910_gate_policy",
            "reason": "xuantie_c910_has_both_hybrid_and_cpu_baseline_artifacts",
            "next_action": "compare_candidate_only_vs_default_gate_for_c910",
        }
    else:
        outcome = {
            "status": "bootstrap_or_repair_c910_runtime",
            "reason": "xuantie_c910_does_not_yet_have_the_expected_baseline_plus_hybrid_runtime_state",
            "next_action": "repair_the_missing_c910_runtime_prerequisites",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_xuantie_c910_runtime_status",
        "hybrid": {
            "status": hybrid_status or None,
            "flow_returncode": hybrid_payload.get("flow_returncode"),
            "campaign_threshold": hybrid_payload.get("campaign_threshold"),
            "campaign_measurement": hybrid_payload.get("campaign_measurement"),
            "runtime_killed": hybrid_runtime_killed,
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
            "incremental_mode": (meta_payload or {}).get("incremental_mode"),
            "gpu_opt_level": (meta_payload or {}).get("gpu_opt_level"),
        },
        "runtime_smoke": {
            "present": runtime_smoke_payload is not None,
            "status": smoke_decision.get("status"),
            "run_count": len(smoke_runs),
        },
        "low_opt_runtime_debug": {
            "o0_rebuild": o0_build,
            "o1_trace": o1_trace,
            "cubin_probe": {
                "present": bool(cubin_probe),
                "status": cubin_probe.get("status"),
                "opt_level": cubin_probe.get("opt_level"),
                "timeout_seconds": cubin_probe.get("timeout_seconds"),
                "cubin_exists": cubin_probe.get("cubin_exists"),
            },
        },
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hybrid-json", type=Path, default=DEFAULT_HYBRID_JSON)
    parser.add_argument("--baseline-json", type=Path, default=DEFAULT_BASELINE_JSON)
    parser.add_argument("--meta-json", type=Path, default=DEFAULT_META_JSON)
    parser.add_argument("--runtime-smoke-json", type=Path, default=DEFAULT_RUNTIME_SMOKE_JSON)
    parser.add_argument("--o0-build-log", type=Path, default=DEFAULT_O0_BUILD_LOG)
    parser.add_argument("--o1-trace-log", type=Path, default=DEFAULT_O1_TRACE_LOG)
    parser.add_argument("--cubin-probe-json", type=Path, default=DEFAULT_CUBIN_PROBE_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    meta_payload = _read_json(args.meta_json.resolve()) if args.meta_json.resolve().is_file() else None
    runtime_smoke_payload = (
        _read_json(args.runtime_smoke_json.resolve())
        if args.runtime_smoke_json.resolve().is_file()
        else None
    )
    cubin_probe_payload = (
        _read_json(args.cubin_probe_json.resolve())
        if args.cubin_probe_json.resolve().is_file()
        else None
    )
    payload = build_status(
        hybrid_payload=_read_json(args.hybrid_json.resolve()),
        baseline_payload=_read_json(args.baseline_json.resolve()),
        meta_payload=meta_payload,
        runtime_smoke_payload=runtime_smoke_payload,
        o0_build_log_text=_read_text_if_exists(args.o0_build_log.resolve()),
        o1_trace_log_text=_read_text_if_exists(args.o1_trace_log.resolve()),
        cubin_probe_payload=cubin_probe_payload,
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
