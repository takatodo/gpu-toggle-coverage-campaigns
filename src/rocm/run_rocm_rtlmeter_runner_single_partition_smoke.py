#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER = SCRIPT_DIR / "run_rtlmeter_gpu_toggle_baseline.py"
DEFAULT_OUT_DIR = Path("/tmp/rocm_rtlmeter_runner_single_partition_smoke_v1")
DEFAULT_JSON = SCRIPT_DIR / "rocm_rtlmeter_runner_single_partition_smoke.json"
DEFAULT_MD = SCRIPT_DIR / "rocm_rtlmeter_runner_single_partition_smoke.md"
DEFAULT_CASE = "Example:gpu_cov_gate:hello"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run or summarize a ROCm RTLMeter single-partition runner smoke and write "
            "canonical artifacts."
        )
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--case", default=DEFAULT_CASE)
    parser.add_argument("--nstates", type=int, default=4)
    parser.add_argument("--gpu-reps", type=int, default=1)
    parser.add_argument("--cpu-reps", type=int, default=1)
    parser.add_argument("--gpu-warmup-reps", type=int, default=0)
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


def _parse_kv_text(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for raw_line in text.splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value.lstrip("-").isdigit():
            out[key] = int(value)
        else:
            try:
                out[key] = float(value)
            except ValueError:
                out[key] = value
    return out


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    smoke = payload.get("runner_summary") or {}
    collector = dict(smoke.get("collector") or {})
    status = dict(collector.get("status") or {})
    coverage = dict(collector.get("coverage") or {})
    metrics = dict(smoke.get("metrics") or {})
    lines = [
        "# ROCm RTLMeter Runner Single-Partition Smoke",
        "",
        f"- status: `{'pass' if payload['pass'] else 'fail'}`",
        f"- case: `{smoke.get('case', payload.get('requested_case', ''))}`",
        f"- gpu_execution_backend: `{((smoke.get('gpu_execution_backend') or {}).get('selected') or payload.get('requested_backend') or '')}`",
        f"- hybrid_mode: `{metrics.get('hybrid_mode')}`",
        f"- hybrid_partition_index: `{metrics.get('hybrid_partition_index')}`",
        f"- aggregate_pass: `{status.get('aggregate_pass')}`",
        f"- mismatch: `{status.get('mismatch')}`",
        f"- compact_mismatch: `{status.get('compact_mismatch')}`",
        f"- hybrid_mismatch: `{metrics.get('hybrid_mismatch')}`",
        f"- points_hit: `{coverage.get('coverage_points_hit')}`",
        f"- points_total: `{coverage.get('coverage_points_total')}`",
        f"- gpu_ms_per_rep: `{metrics.get('gpu_ms_per_rep')}`",
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
            "--gpu-warmup-reps",
            str(args.gpu_warmup_reps),
            "--bench-extra-arg=--hybrid-mode",
            "--bench-extra-arg=single-partition",
            "--bench-extra-arg=--hybrid-partition-index",
            f"--bench-extra-arg={args.hybrid_partition_index}",
            "--no-reuse-bench-kernel-if-present",
            "--no-compile-cache",
            "--rebuild",
        ]
        runner_run = _run(cmd, cwd=SCRIPT_DIR, env=env, log_path=runner_log)

    smoke_summary = _load_optional_json(summary_path)
    collector_status = dict(((smoke_summary.get("collector") or {}).get("status") or {}))
    coverage = dict(((smoke_summary.get("collector") or {}).get("coverage") or {}))
    bench_log = out_dir / "bench_run.log"
    metrics = dict(smoke_summary.get("metrics") or _parse_kv_text(bench_log.read_text(encoding="utf-8")) if bench_log.is_file() else {})
    pass_run = bool(
        runner_run.get("returncode") == 0
        and smoke_summary.get("gpu_execution_backend", {}).get("selected") == "rocm_llvm"
        and metrics.get("hybrid_mode") == "single-partition"
        and metrics.get("hybrid_mismatch", 0) == 0
        and collector_status.get("aggregate_pass") is True
        and collector_status.get("mismatch") == 0
        and collector_status.get("compact_mismatch") == 0
        and coverage.get("available") is True
    )
    payload: dict[str, Any] = {
        "schema_version": "rocm-rtlmeter-runner-single-partition-smoke-v1",
        "pass": pass_run,
        "next_blocker": "fix_rocm_rtlmeter_runner_single_partition_smoke",
        "environment": {
            "ROCM_PATH": env.get("ROCM_PATH", ""),
            "HSA_OVERRIDE_GFX_VERSION": env.get("HSA_OVERRIDE_GFX_VERSION", ""),
            "LD_PRELOAD": env.get("LD_PRELOAD", ""),
        },
        "requested_case": args.case,
        "requested_backend": "rocm_llvm",
        "runner_run": runner_run,
        "runner_summary": smoke_summary,
        "paths": {
            "runner_summary": str(summary_path),
            "runner_log": str(runner_log),
            "bench_log": str(out_dir / "baseline_stdout.log"),
            "build_log": str(out_dir / "build_nvcc.log"),
        },
    }
    if pass_run:
        payload["next_blocker"] = "promote_rocm_single_partition_into_mainline_runner_validation"
    elif metrics.get("hybrid_mismatch") not in (None, 0) and metrics.get("mismatch") == 0 and metrics.get("compact_mismatch") == 0:
        payload["next_blocker"] = "select_partition_sane_rtlmeter_target"
    args.summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_md(args.summary_md, payload)
    print(args.summary_json)
    print(args.summary_md)
    return 0 if pass_run else 1


if __name__ == "__main__":
    raise SystemExit(main())
