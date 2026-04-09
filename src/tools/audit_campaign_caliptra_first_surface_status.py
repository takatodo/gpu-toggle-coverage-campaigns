#!/usr/bin/env python3
"""
Summarize the current Caliptra first-surface state after Vortex acceptance
selects Caliptra as the next family to open.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_AXES_JSON = REPO_ROOT / "work" / "campaign_post_vortex_axes.json"
DEFAULT_BOOTSTRAP_JSON = REPO_ROOT / "work" / "caliptra_gpu_cov_stock_verilator_cc_bootstrap.json"
DEFAULT_BASELINE_JSON = REPO_ROOT / "output" / "validation" / "caliptra_cpu_baseline_validation.json"
DEFAULT_HYBRID_JSON = REPO_ROOT / "output" / "validation" / "caliptra_stock_hybrid_validation.json"
DEFAULT_BUILD_LOG = REPO_ROOT / "work" / "caliptra_build_vl_gpu.log"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_caliptra_first_surface_status.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text_if_exists(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _summarize_build_log(build_log_text: str | None) -> dict[str, Any]:
    if not build_log_text:
        return {
            "present": False,
            "status": None,
            "blocker_kind": None,
            "contains_verilated_tls": False,
            "saw_global_tls_address": False,
            "storage_size_bytes": None,
            "failing_command": None,
            "failing_function": None,
        }

    storage_size_match = re.search(r"storage_size = (\d+) bytes", build_log_text)
    function_match = re.search(r"In function: ([^\n]+)", build_log_text)
    failing_command = None
    for raw_line in build_log_text.splitlines():
        line = raw_line.strip()
        if line.startswith("llc-18 "):
            failing_command = line
            break

    contains_verilated_tls = "_ZN9Verilated3t_sE" in build_log_text
    saw_global_tls_address = "GlobalTLSAddress" in build_log_text
    saw_llvm_error = "LLVM ERROR:" in build_log_text
    saw_sigabrt = "Signals.SIGABRT" in build_log_text or "died with <Signals.SIGABRT: 6>" in build_log_text

    if saw_llvm_error and contains_verilated_tls and saw_global_tls_address:
        status = "llc_tls_global_blocked"
        blocker_kind = "nvptx_tls_lowering"
    elif saw_llvm_error:
        status = "llc_failed"
        blocker_kind = "llvm_codegen_failure"
    elif saw_sigabrt:
        status = "gpu_build_aborted"
        blocker_kind = "subprocess_sigabrt"
    else:
        status = "unknown_failure"
        blocker_kind = "unclassified_build_failure"

    return {
        "present": True,
        "status": status,
        "blocker_kind": blocker_kind,
        "contains_verilated_tls": contains_verilated_tls,
        "saw_global_tls_address": saw_global_tls_address,
        "storage_size_bytes": int(storage_size_match.group(1)) if storage_size_match else None,
        "failing_command": failing_command,
        "failing_function": function_match.group(1) if function_match else None,
    }


def build_status(
    *,
    axes_payload: dict[str, Any] | None,
    bootstrap_payload: dict[str, Any] | None,
    baseline_payload: dict[str, Any],
    hybrid_payload: dict[str, Any] | None,
    build_log_text: str | None,
) -> dict[str, Any]:
    decision = dict((axes_payload or {}).get("decision") or {})
    bootstrap_status = str((bootstrap_payload or {}).get("status") or "")
    baseline_status = str(baseline_payload.get("status") or "")
    hybrid_status = str((hybrid_payload or {}).get("status") or "")
    build_summary = _summarize_build_log(build_log_text)

    if (
        decision.get("recommended_family") == "Caliptra"
        and bootstrap_status == "ok"
        and baseline_status == "ok"
        and hybrid_status == "ok"
    ):
        outcome = {
            "status": "ready_to_finish_caliptra_first_trio",
            "reason": "caliptra_bootstrap_cpu_baseline_and_stock_hybrid_validation_are_ready",
            "next_action": "finish_caliptra_time_to_threshold_comparison_and_compare_gate_policy",
        }
    elif (
        decision.get("recommended_family") == "Caliptra"
        and bootstrap_status == "ok"
        and baseline_status == "ok"
        and build_summary.get("status") == "llc_tls_global_blocked"
    ):
        outcome = {
            "status": "decide_caliptra_tls_lowering_debug_vs_open_example_fallback",
            "reason": (
                "caliptra_bootstrap_and_cpu_baseline_are_ready_but_gpu_codegen_fails_inside_llc_"
                "while_lowering_the_verilated_thread_local_state_symbol"
            ),
            "next_action": "choose_between_offline_caliptra_tls_lowering_debug_and_opening_example_fallback_family",
        }
    else:
        outcome = {
            "status": "bootstrap_or_repair_caliptra_first_surface",
            "reason": "caliptra_does_not_yet_have_the_expected_bootstrap_baseline_and_gpu_build_state",
            "next_action": "repair_the_missing_caliptra_runtime_or_build_prerequisites",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_caliptra_first_surface_status",
        "upstream_axes": {
            "recommended_family": decision.get("recommended_family"),
            "fallback_family": decision.get("fallback_family"),
            "status": decision.get("status"),
        },
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
        "stock_hybrid": {
            "present": hybrid_payload is not None,
            "status": hybrid_status or None,
            "campaign_threshold": (hybrid_payload or {}).get("campaign_threshold"),
            "campaign_measurement": (hybrid_payload or {}).get("campaign_measurement"),
        },
        "gpu_build": build_summary,
        "outcome": outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--axes-json", type=Path, default=DEFAULT_AXES_JSON)
    parser.add_argument("--bootstrap-json", type=Path, default=DEFAULT_BOOTSTRAP_JSON)
    parser.add_argument("--baseline-json", type=Path, default=DEFAULT_BASELINE_JSON)
    parser.add_argument("--hybrid-json", type=Path, default=DEFAULT_HYBRID_JSON)
    parser.add_argument("--build-log", type=Path, default=DEFAULT_BUILD_LOG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    axes_payload = _read_json(args.axes_json.resolve()) if args.axes_json.resolve().is_file() else None
    bootstrap_payload = (
        _read_json(args.bootstrap_json.resolve()) if args.bootstrap_json.resolve().is_file() else None
    )
    hybrid_payload = _read_json(args.hybrid_json.resolve()) if args.hybrid_json.resolve().is_file() else None
    payload = build_status(
        axes_payload=axes_payload,
        bootstrap_payload=bootstrap_payload,
        baseline_payload=_read_json(args.baseline_json.resolve()),
        hybrid_payload=hybrid_payload,
        build_log_text=_read_text_if_exists(args.build_log.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
