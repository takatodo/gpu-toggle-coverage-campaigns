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
RUNNER = SCRIPT_DIR / "run_rtlmeter_gpu_toggle_baseline.py"
DEFAULT_OUT_DIR = Path("/tmp/rocm_rtlmeter_runner_smoke_v2")
DEFAULT_JSON = SCRIPT_DIR / "rocm_rtlmeter_runner_smoke.json"
DEFAULT_MD = SCRIPT_DIR / "rocm_rtlmeter_runner_smoke.md"
DEFAULT_CASE = "Example:gpu_cov_gate:hello"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run or summarize a ROCm RTLMeter runner smoke and write canonical artifacts."
        )
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--nstates", type=int, default=4)
    parser.add_argument("--gpu-reps", type=int, default=1)
    parser.add_argument("--cpu-reps", type=int, default=0)
    parser.add_argument("--gpu-warmup-reps", type=int, default=0)
    parser.add_argument(
        "--rocm-launch-mode",
        choices=("auto", "source-bridge", "native-hsaco"),
        default="native-hsaco",
    )
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


def _load_json_optional(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return _load_json(path)


def _read_optional(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_metric(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}=(.+)$", text, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    smoke = payload.get("runner_summary") or {}
    collector = dict(smoke.get("collector") or {})
    status = dict(collector.get("status") or {})
    coverage = dict(collector.get("coverage") or {})
    metrics = dict(smoke.get("metrics") or {})
    fallback_metrics = dict(payload.get("bench_log_metrics") or {})
    mismatch_value = status.get("mismatch")
    if mismatch_value is None:
        mismatch_value = fallback_metrics.get("mismatch")
    compact_mismatch_value = status.get("compact_mismatch")
    if compact_mismatch_value is None:
        compact_mismatch_value = fallback_metrics.get("compact_mismatch")
    lines = [
        "# ROCm RTLMeter Runner Smoke",
        "",
        f"- status: `{'pass' if payload['pass'] else 'fail'}`",
        f"- case: `{smoke.get('case', '')}`",
        f"- gpu_execution_backend: `{((smoke.get('gpu_execution_backend') or {}).get('selected') or '')}`",
        f"- native_hsaco_mode: `{payload.get('native_hsaco_mode')}`",
        f"- rocm_launch_mode: `{metrics.get('rocm_launch_mode') or fallback_metrics.get('rocm_launch_mode')}`",
        f"- aggregate_pass: `{status.get('aggregate_pass')}`",
        f"- mismatch: `{mismatch_value}`",
        f"- compact_mismatch: `{compact_mismatch_value}`",
        f"- points_hit: `{coverage.get('coverage_points_hit')}`",
        f"- points_total: `{coverage.get('coverage_points_total')}`",
        f"- gpu_ms_per_rep: `{((smoke.get('metrics') or {}).get('gpu_ms_per_rep'))}`",
        f"- runtime_gpu_api: `{metrics.get('runtime_gpu_api') or fallback_metrics.get('runtime_gpu_api')}`",
        f"- runtime_gpu_device_name: `{metrics.get('runtime_gpu_device_name') or fallback_metrics.get('runtime_gpu_device_name')}`",
        f"- next_blocker: `{payload['next_blocker']}`",
        "",
        "## Evidence",
        "",
        f"- [summary.json]({path.with_suffix('.json')})",
        f"- [runner summary]({payload['paths']['runner_summary']})",
        f"- [runner log]({payload['paths']['runner_log']})",
        f"- [bench log]({payload['paths']['bench_log']})",
        f"- [baseline stdout]({payload['paths']['baseline_stdout']})",
        f"- [build log]({payload['paths']['build_log']})",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir.resolve()
    summary_path = out_dir / "summary.json"
    runner_log = out_dir / "runner_smoke.log"
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
            "--case",
            args.case,
            "--build-dir",
            str(out_dir),
            "--json-out",
            str(summary_path),
            "--gpu-execution-backend",
            "rocm_llvm",
            "--nstates",
            str(args.nstates),
            "--gpu-reps",
            str(args.gpu_reps),
            "--cpu-reps",
            str(args.cpu_reps),
            "--skip-cpu-reference-build",
            "--gpu-warmup-reps",
            str(args.gpu_warmup_reps),
            "--rocm-launch-mode",
            str(args.rocm_launch_mode),
            "--no-compile-cache",
            "--rebuild",
        ]
        runner_run = _run(cmd, cwd=SCRIPT_DIR, env=env, log_path=runner_log)

    smoke_summary = _load_json_optional(summary_path)
    collector_status = dict(((smoke_summary.get("collector") or {}).get("status") or {}))
    coverage = dict(((smoke_summary.get("collector") or {}).get("coverage") or {}))
    metrics = dict(smoke_summary.get("metrics") or {})
    bench_log_path = out_dir / "bench_run.log"
    baseline_stdout_path = out_dir / "baseline_stdout.log"
    build_hipcc_log = out_dir / "build_hipcc.log"
    build_nvcc_log = out_dir / "build_nvcc.log"
    build_log_path = build_hipcc_log if build_hipcc_log.is_file() else build_nvcc_log
    bench_log_text = _read_optional(bench_log_path)
    baseline_stdout_text = _read_optional(baseline_stdout_path)
    runner_stdout_text = str(runner_run.get("stdout") or "")
    runner_cmd = " ".join(str(part) for part in (runner_run.get("cmd") or []))
    baseline_has_metrics = (
        _extract_metric(baseline_stdout_text, "mismatch") is not None
        or _extract_metric(baseline_stdout_text, "compact_mismatch") is not None
        or _extract_metric(baseline_stdout_text, "runtime_gpu_api") is not None
    )
    metrics_text = baseline_stdout_text if baseline_has_metrics else (
        bench_log_text if bench_log_text.strip() else baseline_stdout_text
    )
    bench_log_metrics = {
        "runtime_gpu_api": _extract_metric(metrics_text, "runtime_gpu_api"),
        "runtime_gpu_device_name": _extract_metric(metrics_text, "runtime_gpu_device_name"),
        "rocm_launch_mode": _extract_metric(metrics_text, "rocm_launch_mode"),
        "mismatch": _extract_metric(metrics_text, "mismatch"),
        "compact_mismatch": _extract_metric(metrics_text, "compact_mismatch"),
        "mismatch_first_var": _extract_metric(metrics_text, "mismatch_first_var"),
        "error_line": metrics_text.splitlines()[0] if metrics_text.strip() else "",
    }
    native_hsaco_mode = bool(smoke_summary.get("native_hsaco_mode")) or (
        str(metrics.get("rocm_launch_mode") or "") == "native-hsaco"
    ) or ("rocm_launch_mode=native-hsaco" in runner_stdout_text) or (
        "--rocm-launch-mode native-hsaco" in runner_cmd
    ) or ("[2.5/4] Generating native ROCm hsaco artifacts..." in baseline_stdout_text)
    pass_run = bool(
        runner_run.get("returncode") == 0
        and smoke_summary.get("gpu_execution_backend", {}).get("selected") == "rocm_llvm"
        and collector_status.get("aggregate_pass") is True
        and collector_status.get("mismatch") == 0
        and collector_status.get("compact_mismatch") == 0
        and coverage.get("available") is True
    )
    mismatch_metric = bench_log_metrics.get("mismatch")
    compact_mismatch_metric = bench_log_metrics.get("compact_mismatch")
    semantic_mismatch_present = (
        mismatch_metric not in (None, "", "0")
        or compact_mismatch_metric not in (None, "", "0")
    )
    payload: dict[str, Any] = {
        "schema_version": "rocm-rtlmeter-runner-smoke-v2",
        "pass": pass_run,
        "next_blocker": (
            (
                "promote_native_hsaco_into_general_bundle_flows"
                if native_hsaco_mode
                else "open_partition_cluster_second_wave_or_promote_true_hsaco_mainline"
            )
            if pass_run
            else (
                "fix_native_hsaco_rtlmeter_launch_all_illegal_state"
                if native_hsaco_mode and "CUDA error at launch_all sequential timed" in metrics_text
                else (
                    "fix_native_hsaco_rtlmeter_semantic_mismatch"
                    if native_hsaco_mode and semantic_mismatch_present
                    else "fix_rocm_rtlmeter_runner_smoke"
                )
            )
        ),
        "environment": {
            "ROCM_PATH": env.get("ROCM_PATH", ""),
            "HSA_OVERRIDE_GFX_VERSION": env.get("HSA_OVERRIDE_GFX_VERSION", ""),
            "LD_PRELOAD": env.get("LD_PRELOAD", ""),
        },
        "bench_log_metrics": bench_log_metrics,
        "native_hsaco_mode": native_hsaco_mode,
        "runner_run": runner_run,
        "runner_summary": smoke_summary,
        "paths": {
            "runner_summary": str(summary_path),
            "runner_log": str(runner_log),
            "bench_log": str(bench_log_path),
            "baseline_stdout": str(baseline_stdout_path),
            "build_log": str(build_log_path),
        },
    }
    args.summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_md(args.summary_md, payload)
    print(args.summary_json)
    print(args.summary_md)
    return 0 if pass_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
