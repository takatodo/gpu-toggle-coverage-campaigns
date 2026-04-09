#!/usr/bin/env python3
"""
Summarize the split-phase PTX/module-first trial for XuanTie-C910.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_META_JSON = (
    REPO_ROOT
    / "work"
    / "vl_ir_exp"
    / "xuantie_c910_gpu_cov_gate_split_vl"
    / "vl_batch_gpu.meta.json"
)
DEFAULT_MANIFEST_JSON = (
    REPO_ROOT
    / "work"
    / "vl_ir_exp"
    / "xuantie_c910_gpu_cov_gate_split_vl"
    / "vl_kernel_manifest.json"
)
DEFAULT_TRACE_LOG = REPO_ROOT / "work" / "c910_split_timeout_trace.log"
DEFAULT_RETURNCODE_TXT = REPO_ROOT / "work" / "c910_split_timeout_rc.txt"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xuantie_c910_split_phase_trial.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text_if_exists(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _extract_last_stage(trace_text: str | None) -> str | None:
    if not trace_text:
        return None
    prefix = "run_vl_hybrid: stage="
    last_stage = None
    for raw_line in trace_text.splitlines():
        if raw_line.startswith(prefix):
            last_stage = raw_line[len(prefix):].strip() or None
    return last_stage


def _parse_returncode(returncode_text: str | None) -> int | None:
    if not returncode_text:
        return None
    raw = returncode_text.strip()
    if not raw:
        return None
    return int(raw)


def build_trial(
    *,
    meta_payload: dict[str, Any] | None,
    manifest_payload: dict[str, Any] | None,
    trace_log_text: str | None,
    returncode_text: str | None,
) -> dict[str, Any]:
    launch_sequence = list(
        (manifest_payload or {}).get("launch_sequence")
        or (meta_payload or {}).get("launch_sequence")
        or []
    )
    kernels = list((manifest_payload or {}).get("kernels") or [])
    last_stage = _extract_last_stage(trace_log_text)
    returncode = _parse_returncode(returncode_text)
    if returncode == 0:
        runtime_status = "ok"
    elif returncode == 137:
        runtime_status = "timed_out"
    elif returncode is None:
        runtime_status = "unknown"
    else:
        runtime_status = "error"

    if runtime_status == "timed_out" and last_stage == "before_cuModuleLoad":
        decision = {
            "status": "timed_out_before_cuModuleLoad",
            "reason": (
                "the_split_phase_ptx_module_first_trial_still_times_out_before_"
                "cuModuleLoad_completes"
            ),
            "recommended_next_action": (
                "choose_between_open_veer_fallback_family_and_deeper_c910_cubin_debug"
            ),
        }
    elif runtime_status == "ok":
        decision = {
            "status": "split_phase_trial_progressed",
            "reason": "the_split_phase_trial_completed_without_a_timeout",
            "recommended_next_action": "re-run_the_c910_stock_hybrid_validation_with_split_phases",
        }
    else:
        decision = {
            "status": "split_phase_trial_inconclusive",
            "reason": "the_split_phase_trial_did_not_produce_a_clean_timeout_or_success_signal",
            "recommended_next_action": "inspect_split_phase_trial_logs_before_changing_branch",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_xuantie_c910_split_phase_trial",
        "split_phase_build": {
            "meta_present": meta_payload is not None,
            "manifest_present": manifest_payload is not None,
            "module_format": (meta_payload or {}).get("cuda_module_format"),
            "module_path": (meta_payload or {}).get("cubin"),
            "gpu_opt_level": (meta_payload or {}).get("gpu_opt_level"),
            "storage_size": (meta_payload or {}).get("storage_size"),
            "kernel_count": len(kernels),
            "launch_sequence": launch_sequence,
        },
        "split_phase_runtime": {
            "trace_present": trace_log_text is not None,
            "returncode": returncode,
            "status": runtime_status,
            "last_stage": last_stage,
        },
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meta-json", type=Path, default=DEFAULT_META_JSON)
    parser.add_argument("--manifest-json", type=Path, default=DEFAULT_MANIFEST_JSON)
    parser.add_argument("--trace-log", type=Path, default=DEFAULT_TRACE_LOG)
    parser.add_argument("--returncode-txt", type=Path, default=DEFAULT_RETURNCODE_TXT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    meta_payload = _read_json(args.meta_json.resolve()) if args.meta_json.resolve().is_file() else None
    manifest_payload = (
        _read_json(args.manifest_json.resolve()) if args.manifest_json.resolve().is_file() else None
    )
    payload = build_trial(
        meta_payload=meta_payload,
        manifest_payload=manifest_payload,
        trace_log_text=_read_text_if_exists(args.trace_log.resolve()),
        returncode_text=_read_text_if_exists(args.returncode_txt.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
