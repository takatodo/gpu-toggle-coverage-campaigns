#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER = SCRIPT_DIR.parent / "runners" / "run_opentitan_tlul_slice_gpu_baseline.py"
TEMPLATE = SCRIPT_DIR / "slice_launch_templates" / "tlul_fifo_sync.json"
DEFAULT_OUT_DIR = Path("/tmp/rocm_tlul_fifo_sync_runner_single_partition_smoke_v1")
DEFAULT_JSON = SCRIPT_DIR / "rocm_mainline_runner_single_partition_smoke.json"
DEFAULT_MD = SCRIPT_DIR / "rocm_mainline_runner_single_partition_smoke.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run or summarize a ROCm mainline OpenTitan slice single-partition smoke and "
            "write canonical artifacts."
        )
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--nstates", type=int, default=4)
    parser.add_argument("--gpu-reps", type=int, default=1)
    parser.add_argument("--cpu-reps", type=int, default=1)
    parser.add_argument("--gpu-warmup-reps", type=int, default=0)
    parser.add_argument("--launch-backend", default="source")
    parser.add_argument("--hybrid-partition-index", type=int, default=0)
    return parser.parse_args()


def _rocm_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("ROCM_PATH", "/opt/rocm")
    env.setdefault("HSA_OVERRIDE_GFX_VERSION", "12.0.1")
    hip_preload = Path(env["ROCM_PATH"]) / "lib" / "libamdhip64.so"
    preload = env.get("LD_PRELOAD", "")
    if hip_preload.is_file() and "libamdhip64.so" not in preload:
        env["LD_PRELOAD"] = str(hip_preload) if not preload else f"{hip_preload}:{preload}"
    return env


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    log_path.write_text(
        f"$ {' '.join(cmd)}\n\n[stdout]\n{proc.stdout}\n[stderr]\n{proc.stderr}\n",
        encoding="utf-8",
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "log_path": str(log_path),
    }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return _load_json(path)
    except json.JSONDecodeError:
        return {}


def _read_optional(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _extract_int_metric(text: str, key: str) -> int | None:
    match = re.search(rf"^{re.escape(key)}=(-?\d+)$", text, re.MULTILINE)
    if not match:
        return None
    return int(match.group(1))


def _extract_str_metric(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}=(.+)$", text, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def _baseline_metric_map(text: str) -> dict[str, Any]:
    if not text:
        return {}
    int_keys = (
        "hybrid_partition_index",
        "hybrid_mismatch",
        "mismatch",
        "compact_mismatch",
        "hybrid_first_state",
        "hybrid_first_var",
        "kernel_clusters",
        "kernel_partitions",
    )
    str_keys = (
        "hybrid_mode",
        "runtime_gpu_api",
        "runtime_gpu_platform",
        "runtime_gpu_device_name",
        "runtime_gpu_arch_name",
        "hybrid_first_expected",
        "hybrid_first_actual",
    )
    out: dict[str, Any] = {}
    for key in int_keys:
        value = _extract_int_metric(text, key)
        if value is not None:
            out[key] = value
    for key in str_keys:
        value = _extract_str_metric(text, key)
        if value is not None:
            out[key] = value
    return out


def _detect_seq_partition_gap_from_stdout(stdout: str) -> bool:
    raw_dir_match = re.search(r"^raw_dir=(.+)$", stdout or "", re.MULTILINE)
    if not raw_dir_match:
        return False
    raw_dir = Path(raw_dir_match.group(1).strip())
    kernel_name = f"{TEMPLATE.stem}_gpu_cov_tb.sim_accel.kernel.cu"
    raw_kernel = raw_dir / kernel_name
    if not raw_kernel.is_file():
        return False
    text = raw_kernel.read_text(encoding="utf-8")
    return "extern \"C\" __host__ uint32_t sim_accel_eval_seq_partition_count() {\n    return 0U;\n}" in text


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    smoke = payload.get("runner_summary") or {}
    collector_status = dict(((smoke.get("collector") or {}).get("status") or {}))
    coverage = dict(((smoke.get("collector") or {}).get("coverage") or {}))
    metrics = dict(smoke.get("metrics") or {})
    fallback_metrics = dict(payload.get("baseline_metrics") or {})
    hybrid_mode = metrics.get("hybrid_mode", fallback_metrics.get("hybrid_mode"))
    hybrid_partition_index = metrics.get(
        "hybrid_partition_index", fallback_metrics.get("hybrid_partition_index")
    )
    aggregate_pass = collector_status.get("aggregate_pass")
    mismatch = collector_status.get("mismatch", fallback_metrics.get("mismatch"))
    compact_mismatch = collector_status.get(
        "compact_mismatch", fallback_metrics.get("compact_mismatch")
    )
    hybrid_mismatch = metrics.get("hybrid_mismatch", fallback_metrics.get("hybrid_mismatch"))
    points_hit = coverage.get("coverage_points_hit")
    points_total = coverage.get("coverage_points_total")
    gpu_ms_per_rep = metrics.get("gpu_ms_per_rep", fallback_metrics.get("gpu_ms_per_rep"))
    lines = [
        "# ROCm Mainline Runner Single-Partition Smoke",
        "",
        f"- status: `{'pass' if payload['pass'] else 'fail'}`",
        f"- target: `{smoke.get('target', payload.get('requested_target', ''))}`",
        f"- gpu_execution_backend: `{((smoke.get('gpu_execution_backend') or {}).get('selected') or payload.get('requested_backend') or '')}`",
        f"- hybrid_mode: `{hybrid_mode}`",
        f"- hybrid_partition_index: `{hybrid_partition_index}`",
        f"- aggregate_pass: `{aggregate_pass}`",
        f"- mismatch: `{mismatch}`",
        f"- compact_mismatch: `{compact_mismatch}`",
        f"- hybrid_mismatch: `{hybrid_mismatch}`",
        f"- points_hit: `{points_hit}`",
        f"- points_total: `{points_total}`",
        f"- gpu_ms_per_rep: `{gpu_ms_per_rep}`",
        f"- runtime_gpu_api: `{fallback_metrics.get('runtime_gpu_api')}`",
        f"- runtime_gpu_device_name: `{fallback_metrics.get('runtime_gpu_device_name')}`",
        f"- hybrid_first_state: `{fallback_metrics.get('hybrid_first_state')}`",
        f"- hybrid_first_var: `{fallback_metrics.get('hybrid_first_var')}`",
        f"- semantic_gap_classification: `{payload.get('semantic_gap_classification', '')}`",
        f"- next_blocker: `{payload['next_blocker']}`",
        "",
        "## Evidence",
        "",
        f"- [summary.json]({path.with_suffix('.json')})",
        f"- [runner summary]({payload['paths']['runner_summary']})",
        f"- [runner log]({payload['paths']['runner_log']})",
        f"- [bench log]({payload['paths']['bench_log']})",
        f"- [build log]({payload['paths']['build_log']})",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir.resolve()
    summary_path = out_dir / "summary.json"
    runner_log = out_dir / "runner_single_partition_smoke.log"
    generated_dir_cache_root = out_dir / "generated_dir_cache"
    bundle_cache_root = out_dir / "bundle_cache"
    env = _rocm_env()

    runner_run: dict[str, Any]
    if args.reuse_existing:
        runner_run = {
            "cmd": [],
            "returncode": 0 if summary_path.is_file() else 1,
            "stdout": runner_log.read_text(encoding="utf-8") if runner_log.is_file() else "",
            "stderr": "",
            "log_path": str(runner_log),
        }
    else:
        if out_dir.exists():
            shutil.rmtree(out_dir)
        cmd = [
            "python3",
            str(RUNNER),
            "--launch-template",
            str(TEMPLATE),
            "--build-dir",
            str(out_dir),
            "--json-out",
            str(summary_path),
            "--gpu-execution-backend",
            "rocm_llvm",
            "--launch-backend",
            args.launch_backend,
            "--hybrid-mode",
            "single-partition",
            "--hybrid-partition-index",
            str(args.hybrid_partition_index),
            "--nstates",
            str(args.nstates),
            "--gpu-reps",
            str(args.gpu_reps),
            "--cpu-reps",
            str(args.cpu_reps),
            "--gpu-warmup-reps",
            str(args.gpu_warmup_reps),
            "--summary-mode",
            "full",
            "--generated-dir-cache-root",
            str(generated_dir_cache_root),
            "--bundle-cache-root",
            str(bundle_cache_root),
            "--no-compile-cache",
            "--rebuild",
        ]
        runner_run = _run(cmd, cwd=SCRIPT_DIR, env=env, log_path=runner_log)

    smoke_summary = _load_optional_json(summary_path)
    baseline_log = out_dir / "baseline_stdout.log"
    baseline_text = _read_optional(baseline_log)
    baseline_metrics = _baseline_metric_map(baseline_text)
    collector_status = dict(((smoke_summary.get("collector") or {}).get("status") or {}))
    coverage = dict(((smoke_summary.get("collector") or {}).get("coverage") or {}))
    metrics = dict(smoke_summary.get("metrics") or {})
    structured_gap = dict(smoke_summary.get("structured_semantic_gap") or {})
    pass_run = bool(
        runner_run.get("returncode") == 0
        and smoke_summary.get("gpu_execution_backend", {}).get("selected") == "rocm_llvm"
        and metrics.get("hybrid_mode") == "single-partition"
        and collector_status.get("aggregate_pass") is True
        and collector_status.get("mismatch") == 0
        and collector_status.get("compact_mismatch") == 0
        and coverage.get("available") is True
        and (
            metrics.get("hybrid_mismatch", 0) == 0
            or bool(structured_gap.get("soft_accepted"))
        )
    )
    semantic_gap_classification = ""
    if (baseline_metrics.get("hybrid_mismatch") or 0) != 0 and _detect_seq_partition_gap_from_stdout(
        str(runner_run.get("stdout") or "")
    ):
        semantic_gap_classification = "partition_interface_missing_seq_commit"
    structured_gap_soft_accepted = bool(structured_gap.get("soft_accepted"))
    next_blocker = "fix_rocm_mainline_runner_single_partition_smoke"
    if pass_run and structured_gap_soft_accepted:
        next_blocker = "canonicalize_structured_second_wave_semantic_gap_waiver"
    elif pass_run:
        next_blocker = "open_partition_second_wave_or_promote_true_hsaco_mainline"
    elif (
        semantic_gap_classification == "partition_interface_missing_seq_commit"
        or structured_gap_soft_accepted
    ):
        next_blocker = "single_partition_semantic_gap_missing_seq_commit"
    payload: dict[str, Any] = {
        "schema_version": "rocm-mainline-runner-single-partition-smoke-v1",
        "pass": pass_run,
        "next_blocker": next_blocker,
        "requested_target": TEMPLATE.stem,
        "requested_backend": "rocm_llvm",
        "semantic_gap_classification": semantic_gap_classification,
        "baseline_metrics": baseline_metrics,
        "environment": {
            "ROCM_PATH": env.get("ROCM_PATH", ""),
            "HSA_OVERRIDE_GFX_VERSION": env.get("HSA_OVERRIDE_GFX_VERSION", ""),
            "LD_PRELOAD": env.get("LD_PRELOAD", ""),
        },
        "runner_run": runner_run,
        "runner_summary": smoke_summary,
        "paths": {
            "runner_summary": str(summary_path),
            "runner_log": str(runner_log),
            "bench_log": str(baseline_log),
            "build_log": str(out_dir / "build_hipcc.log"),
        },
    }
    args.summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_md(args.summary_md, payload)
    print(args.summary_json)
    print(args.summary_md)
    return 0 if pass_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
