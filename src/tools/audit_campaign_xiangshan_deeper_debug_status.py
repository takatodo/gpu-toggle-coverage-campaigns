#!/usr/bin/env python3
"""
Summarize the concrete next debug step for the current deeper XiangShan cubin-first
line after the reopen loop has been resolved.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_BRANCH_RESOLUTION_JSON = REPO_ROOT / "work" / "campaign_xiangshan_vortex_branch_resolution.json"
DEFAULT_PTXAS_PROBE_JSON = REPO_ROOT / "work" / "xiangshan_ptxas_probe.json"
DEFAULT_COMPILE_ONLY_PROBE_JSON = REPO_ROOT / "work" / "xiangshan_ptxas_compile_only_probe.json"
DEFAULT_NVCC_DEVICE_LINK_PROBE_JSON = REPO_ROOT / "work" / "xiangshan_nvcc_device_link_probe.json"
DEFAULT_COMPILE_ONLY_OBJECT = REPO_ROOT / "work" / "xiangshan_ptxas_compile_only_probe.o"
DEFAULT_NVLINK_CUBIN = REPO_ROOT / "work" / "xiangshan_nvlink_probe.cubin"
DEFAULT_NVCC_DLINK_FATBIN = REPO_ROOT / "work" / "xiangshan_nvcc_dlink.fatbin"
DEFAULT_FATBINARY_DEVICE_C_FATBIN = REPO_ROOT / "work" / "xiangshan_fatbinary_device_c_probe.fatbin"
DEFAULT_FATBINARY_DEVICE_C_LINK_FATBIN = REPO_ROOT / "work" / "xiangshan_fatbinary_device_c_link_probe.fatbin"
DEFAULT_PTX_FATBIN = REPO_ROOT / "work" / "xiangshan_ptx_fatbin_probe.fatbin"
DEFAULT_COMPILE_ONLY_SMOKE_LOG = REPO_ROOT / "work" / "xiangshan_compile_only_smoke_trace.log"
DEFAULT_NVLINK_SMOKE_LOG = REPO_ROOT / "work" / "xiangshan_nvlink_smoke_trace.log"
DEFAULT_FATBIN_SMOKE_LOG = REPO_ROOT / "work" / "xiangshan_fatbin_smoke_trace.log"
DEFAULT_NVCC_DLINK_SMOKE_LOG = REPO_ROOT / "work" / "xiangshan_nvcc_dlink_smoke_trace.log"
DEFAULT_FATBINARY_DEVICE_C_SMOKE_LOG = (
    REPO_ROOT / "work" / "xiangshan_fatbinary_device_c_probe_smoke_trace.log"
)
DEFAULT_FATBINARY_DEVICE_C_LINK_SMOKE_LOG = (
    REPO_ROOT / "work" / "xiangshan_fatbinary_device_c_link_probe_smoke_trace.log"
)
DEFAULT_PTX_FATBIN_SMOKE_LOG = REPO_ROOT / "work" / "xiangshan_ptx_fatbin_probe_smoke_trace.log"
DEFAULT_NVCC_DEVICE_LINK_SMOKE_LOG = (
    REPO_ROOT / "work" / "xiangshan_nvcc_device_link_from_ptx_smoke_trace.log"
)
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_xiangshan_deeper_debug_status.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text_if_exists(path: Path) -> str | None:
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _symbol_present(path: Path, symbol_name: str) -> bool | None:
    if not path.is_file():
        return None
    completed = subprocess.run(
        ["cuobjdump", "--dump-elf-symbols", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    haystack = "\n".join([completed.stdout or "", completed.stderr or ""])
    return symbol_name in haystack


def _file_size_if_exists(path: Path) -> int | None:
    if not path.is_file():
        return None
    return path.stat().st_size


def _smoke_status(log_text: str | None) -> dict[str, Any]:
    if not log_text:
        return {"status": None, "last_stage": None}
    last_stage = None
    for line in log_text.splitlines():
        prefix = "run_vl_hybrid: stage="
        if line.startswith(prefix):
            last_stage = line[len(prefix) :].strip()
    if "CUDA error 500: named symbol not found" in log_text:
        status = "named_symbol_not_found"
    elif "CUDA error 200: device kernel image is invalid" in log_text:
        status = "device_kernel_image_invalid"
    elif "CUDA error" in log_text:
        status = "cuda_error"
    elif last_stage == "before_cuModuleLoad":
        status = "stalled_before_cuModuleLoad"
    elif last_stage == "after_cuModuleLoad":
        status = "stalled_after_cuModuleLoad"
    elif "ok: steps=" in log_text:
        status = "ok"
    else:
        status = "unknown"
    return {"status": status, "last_stage": last_stage}


def build_status(
    *,
    branch_resolution_payload: dict[str, Any],
    ptxas_probe_payload: dict[str, Any],
    compile_only_probe_payload: dict[str, Any],
    nvcc_device_link_probe_payload: dict[str, Any] | None,
    compile_only_kernel_symbol_present: bool | None,
    nvlink_kernel_symbol_present: bool | None,
    nvcc_dlink_kernel_symbol_present: bool | None,
    fatbinary_device_c_kernel_symbol_present: bool | None,
    fatbinary_device_c_link_kernel_symbol_present: bool | None,
    compile_only_object_size_bytes: int | None,
    nvlink_cubin_size_bytes: int | None,
    nvcc_dlink_fatbin_size_bytes: int | None,
    fatbinary_device_c_fatbin_size_bytes: int | None,
    fatbinary_device_c_link_fatbin_size_bytes: int | None,
    ptx_fatbin_size_bytes: int | None,
    compile_only_smoke_payload: dict[str, Any],
    nvlink_smoke_payload: dict[str, Any],
    fatbin_smoke_payload: dict[str, Any],
    nvcc_dlink_smoke_payload: dict[str, Any],
    fatbinary_device_c_smoke_payload: dict[str, Any],
    fatbinary_device_c_link_smoke_payload: dict[str, Any],
    ptx_fatbin_smoke_payload: dict[str, Any],
    nvcc_device_link_smoke_payload: dict[str, Any],
) -> dict[str, Any]:
    resolution_decision = dict(branch_resolution_payload.get("decision") or {})
    ptxas_status = str(ptxas_probe_payload.get("status") or "")
    compile_only_status = str(compile_only_probe_payload.get("status") or "")
    compile_only_output_exists = bool(compile_only_probe_payload.get("output_exists"))
    nvcc_probe = dict(nvcc_device_link_probe_payload or {})
    nvcc_compile = dict(nvcc_probe.get("compile") or {})
    nvcc_link = dict(nvcc_probe.get("link") or {})
    nvcc_observations = dict(nvcc_probe.get("observations") or {})
    recommended_from_resolution = str(resolution_decision.get("recommended_next_tactic") or "")
    fallback_tactic = resolution_decision.get("fallback_tactic")

    if (
        recommended_from_resolution == "deeper_xiangshan_cubin_first_debug"
        and str(nvcc_compile.get("status") or "") == "ok"
        and str(nvcc_link.get("status") or "") == "ok"
        and bool(nvcc_observations.get("object_exists"))
        and bool(nvcc_observations.get("linked_exists"))
        and nvcc_observations.get("object_kernel_symbol_present") is True
        and nvcc_observations.get("linked_kernel_symbol_present") is True
        and isinstance(nvcc_observations.get("linked_size"), int)
        and int(nvcc_observations.get("linked_size")) > 4096
        and str(nvcc_device_link_smoke_payload.get("status") or "") == "ok"
    ):
        decision = {
            "status": "ready_to_finish_xiangshan_first_trio",
            "reason": (
                "official_nvcc_device-c_then_device-link_cubin_path_restores_a_non-empty_"
                "linked_kernel_image_and_the_minimal_runtime_smoke_is_ok"
            ),
            "recommended_next_tactic": "finish_xiangshan_stock_hybrid_validation_and_compare_gate_policy",
            "fallback_tactic": fallback_tactic,
        }
    elif (
        recommended_from_resolution == "deeper_xiangshan_cubin_first_debug"
        and ptxas_status == "timed_out"
        and compile_only_status == "ok"
        and compile_only_output_exists
        and compile_only_kernel_symbol_present is True
        and nvlink_kernel_symbol_present is False
        and nvlink_cubin_size_bytes is not None
        and nvlink_cubin_size_bytes <= 4096
        and nvcc_dlink_kernel_symbol_present is False
        and nvcc_dlink_fatbin_size_bytes is not None
        and nvcc_dlink_fatbin_size_bytes <= 4096
        and fatbinary_device_c_kernel_symbol_present is True
        and fatbinary_device_c_smoke_payload.get("status") == "device_kernel_image_invalid"
        and fatbinary_device_c_link_kernel_symbol_present is True
        and fatbinary_device_c_link_smoke_payload.get("status") == "device_kernel_image_invalid"
    ):
        reason = (
            "compile-only_and_device-c_fatbin_variants_keep_sto_entry_vl_eval_batch_gpu_but_"
            "current_nvlink_and_nvcc_dlink_outputs_collapse_to_tiny_symbol-less_images"
        )
        if ptx_fatbin_smoke_payload.get("status") == "stalled_before_cuModuleLoad":
            reason += "_and_ptx_fatbin_jit_still_stalls_before_cuModuleLoad"
        decision = {
            "status": "ready_for_xiangshan_executable_link_population_debug",
            "reason": reason,
            "recommended_next_tactic": "deeper_xiangshan_executable_link_population_debug",
            "fallback_tactic": fallback_tactic,
        }
    elif (
        recommended_from_resolution == "deeper_xiangshan_cubin_first_debug"
        and ptxas_status == "timed_out"
        and compile_only_status == "ok"
        and compile_only_output_exists
        and compile_only_kernel_symbol_present is True
        and compile_only_smoke_payload.get("status") == "device_kernel_image_invalid"
        and fatbin_smoke_payload.get("status") == "device_kernel_image_invalid"
        and nvlink_smoke_payload.get("status") == "named_symbol_not_found"
        and nvcc_dlink_smoke_payload.get("status") == "named_symbol_not_found"
    ):
        decision = {
            "status": "ready_for_xiangshan_device_link_symbol_export_debug",
            "reason": (
                "ptxas_compile-only_succeeds_and_retains_vl_eval_batch_gpu_but_current_packaging_variants_"
                "still_fail_as_invalid_images_or_drop_the_kernel_symbol"
            ),
            "recommended_next_tactic": "deeper_xiangshan_device_link_symbol_export_debug",
            "fallback_tactic": fallback_tactic,
        }
    elif recommended_from_resolution != "deeper_xiangshan_cubin_first_debug":
        decision = {
            "status": "follow_branch_resolution_first",
            "reason": "the_current_checked-in_branch_resolution_does_not_point_at_deeper_XiangShan_debug",
            "recommended_next_tactic": recommended_from_resolution or None,
            "fallback_tactic": fallback_tactic,
        }
    else:
        decision = {
            "status": "continue_collecting_xiangshan_packaging_evidence",
            "reason": "the_current_XiangShan_packaging probes do not yet match the stronger symbol-export diagnosis",
            "recommended_next_tactic": "deeper_xiangshan_cubin_first_debug",
            "fallback_tactic": fallback_tactic,
        }

    return {
        "schema_version": 1,
        "scope": "campaign_xiangshan_deeper_debug_status",
        "current_branch_resolution": {
            "status": resolution_decision.get("status"),
            "recommended_profile_name": resolution_decision.get("recommended_profile_name"),
            "recommended_next_tactic": recommended_from_resolution or None,
            "fallback_tactic": fallback_tactic,
        },
        "observations": {
            "ptxas_probe_status": ptxas_status or None,
            "compile_only_probe_status": compile_only_status or None,
            "compile_only_output_exists": compile_only_output_exists,
            "nvcc_device_c_status": nvcc_compile.get("status"),
            "nvcc_device_link_status": nvcc_link.get("status"),
            "nvcc_device_c_output_exists": nvcc_observations.get("object_exists"),
            "nvcc_device_c_kernel_symbol_present": nvcc_observations.get("object_kernel_symbol_present"),
            "nvcc_device_c_object_size_bytes": nvcc_observations.get("object_size"),
            "nvcc_device_link_output_exists": nvcc_observations.get("linked_exists"),
            "nvcc_device_link_kernel_symbol_present": nvcc_observations.get("linked_kernel_symbol_present"),
            "nvcc_device_link_cubin_size_bytes": nvcc_observations.get("linked_size"),
            "nvcc_device_link_smoke_status": nvcc_device_link_smoke_payload.get("status"),
            "nvcc_device_link_smoke_last_stage": nvcc_device_link_smoke_payload.get("last_stage"),
            "compile_only_kernel_symbol_present": compile_only_kernel_symbol_present,
            "compile_only_object_size_bytes": compile_only_object_size_bytes,
            "nvlink_kernel_symbol_present": nvlink_kernel_symbol_present,
            "nvlink_cubin_size_bytes": nvlink_cubin_size_bytes,
            "nvcc_dlink_kernel_symbol_present": nvcc_dlink_kernel_symbol_present,
            "nvcc_dlink_fatbin_size_bytes": nvcc_dlink_fatbin_size_bytes,
            "fatbinary_device_c_kernel_symbol_present": fatbinary_device_c_kernel_symbol_present,
            "fatbinary_device_c_fatbin_size_bytes": fatbinary_device_c_fatbin_size_bytes,
            "fatbinary_device_c_link_kernel_symbol_present": fatbinary_device_c_link_kernel_symbol_present,
            "fatbinary_device_c_link_fatbin_size_bytes": fatbinary_device_c_link_fatbin_size_bytes,
            "ptx_fatbin_size_bytes": ptx_fatbin_size_bytes,
            "compile_only_smoke_status": compile_only_smoke_payload.get("status"),
            "compile_only_smoke_last_stage": compile_only_smoke_payload.get("last_stage"),
            "fatbin_smoke_status": fatbin_smoke_payload.get("status"),
            "fatbin_smoke_last_stage": fatbin_smoke_payload.get("last_stage"),
            "fatbinary_device_c_smoke_status": fatbinary_device_c_smoke_payload.get("status"),
            "fatbinary_device_c_smoke_last_stage": fatbinary_device_c_smoke_payload.get("last_stage"),
            "fatbinary_device_c_link_smoke_status": fatbinary_device_c_link_smoke_payload.get("status"),
            "fatbinary_device_c_link_smoke_last_stage": fatbinary_device_c_link_smoke_payload.get("last_stage"),
            "ptx_fatbin_smoke_status": ptx_fatbin_smoke_payload.get("status"),
            "ptx_fatbin_smoke_last_stage": ptx_fatbin_smoke_payload.get("last_stage"),
            "nvlink_smoke_status": nvlink_smoke_payload.get("status"),
            "nvlink_smoke_last_stage": nvlink_smoke_payload.get("last_stage"),
            "nvcc_dlink_smoke_status": nvcc_dlink_smoke_payload.get("status"),
            "nvcc_dlink_smoke_last_stage": nvcc_dlink_smoke_payload.get("last_stage"),
        },
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch-resolution-json", type=Path, default=DEFAULT_BRANCH_RESOLUTION_JSON)
    parser.add_argument("--ptxas-probe-json", type=Path, default=DEFAULT_PTXAS_PROBE_JSON)
    parser.add_argument("--compile-only-probe-json", type=Path, default=DEFAULT_COMPILE_ONLY_PROBE_JSON)
    parser.add_argument("--nvcc-device-link-probe-json", type=Path, default=DEFAULT_NVCC_DEVICE_LINK_PROBE_JSON)
    parser.add_argument("--compile-only-object", type=Path, default=DEFAULT_COMPILE_ONLY_OBJECT)
    parser.add_argument("--nvlink-cubin", type=Path, default=DEFAULT_NVLINK_CUBIN)
    parser.add_argument("--nvcc-dlink-fatbin", type=Path, default=DEFAULT_NVCC_DLINK_FATBIN)
    parser.add_argument("--fatbinary-device-c-fatbin", type=Path, default=DEFAULT_FATBINARY_DEVICE_C_FATBIN)
    parser.add_argument(
        "--fatbinary-device-c-link-fatbin",
        type=Path,
        default=DEFAULT_FATBINARY_DEVICE_C_LINK_FATBIN,
    )
    parser.add_argument("--ptx-fatbin", type=Path, default=DEFAULT_PTX_FATBIN)
    parser.add_argument("--compile-only-smoke-log", type=Path, default=DEFAULT_COMPILE_ONLY_SMOKE_LOG)
    parser.add_argument("--nvlink-smoke-log", type=Path, default=DEFAULT_NVLINK_SMOKE_LOG)
    parser.add_argument("--fatbin-smoke-log", type=Path, default=DEFAULT_FATBIN_SMOKE_LOG)
    parser.add_argument("--nvcc-dlink-smoke-log", type=Path, default=DEFAULT_NVCC_DLINK_SMOKE_LOG)
    parser.add_argument(
        "--fatbinary-device-c-smoke-log",
        type=Path,
        default=DEFAULT_FATBINARY_DEVICE_C_SMOKE_LOG,
    )
    parser.add_argument(
        "--fatbinary-device-c-link-smoke-log",
        type=Path,
        default=DEFAULT_FATBINARY_DEVICE_C_LINK_SMOKE_LOG,
    )
    parser.add_argument("--ptx-fatbin-smoke-log", type=Path, default=DEFAULT_PTX_FATBIN_SMOKE_LOG)
    parser.add_argument("--nvcc-device-link-smoke-log", type=Path, default=DEFAULT_NVCC_DEVICE_LINK_SMOKE_LOG)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_status(
        branch_resolution_payload=_read_json(args.branch_resolution_json.resolve()),
        ptxas_probe_payload=_read_json(args.ptxas_probe_json.resolve()),
        compile_only_probe_payload=_read_json(args.compile_only_probe_json.resolve()),
        nvcc_device_link_probe_payload=(
            _read_json(args.nvcc_device_link_probe_json.resolve())
            if args.nvcc_device_link_probe_json.resolve().is_file()
            else None
        ),
        compile_only_kernel_symbol_present=_symbol_present(args.compile_only_object.resolve(), "vl_eval_batch_gpu"),
        nvlink_kernel_symbol_present=_symbol_present(args.nvlink_cubin.resolve(), "vl_eval_batch_gpu"),
        nvcc_dlink_kernel_symbol_present=_symbol_present(args.nvcc_dlink_fatbin.resolve(), "vl_eval_batch_gpu"),
        fatbinary_device_c_kernel_symbol_present=_symbol_present(
            args.fatbinary_device_c_fatbin.resolve(), "vl_eval_batch_gpu"
        ),
        fatbinary_device_c_link_kernel_symbol_present=_symbol_present(
            args.fatbinary_device_c_link_fatbin.resolve(), "vl_eval_batch_gpu"
        ),
        compile_only_object_size_bytes=_file_size_if_exists(args.compile_only_object.resolve()),
        nvlink_cubin_size_bytes=_file_size_if_exists(args.nvlink_cubin.resolve()),
        nvcc_dlink_fatbin_size_bytes=_file_size_if_exists(args.nvcc_dlink_fatbin.resolve()),
        fatbinary_device_c_fatbin_size_bytes=_file_size_if_exists(args.fatbinary_device_c_fatbin.resolve()),
        fatbinary_device_c_link_fatbin_size_bytes=_file_size_if_exists(
            args.fatbinary_device_c_link_fatbin.resolve()
        ),
        ptx_fatbin_size_bytes=_file_size_if_exists(args.ptx_fatbin.resolve()),
        compile_only_smoke_payload=_smoke_status(_read_text_if_exists(args.compile_only_smoke_log.resolve())),
        nvlink_smoke_payload=_smoke_status(_read_text_if_exists(args.nvlink_smoke_log.resolve())),
        fatbin_smoke_payload=_smoke_status(_read_text_if_exists(args.fatbin_smoke_log.resolve())),
        nvcc_dlink_smoke_payload=_smoke_status(_read_text_if_exists(args.nvcc_dlink_smoke_log.resolve())),
        fatbinary_device_c_smoke_payload=_smoke_status(
            _read_text_if_exists(args.fatbinary_device_c_smoke_log.resolve())
        ),
        fatbinary_device_c_link_smoke_payload=_smoke_status(
            _read_text_if_exists(args.fatbinary_device_c_link_smoke_log.resolve())
        ),
        ptx_fatbin_smoke_payload=_smoke_status(_read_text_if_exists(args.ptx_fatbin_smoke_log.resolve())),
        nvcc_device_link_smoke_payload=_smoke_status(
            _read_text_if_exists(args.nvcc_device_link_smoke_log.resolve())
        ),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
