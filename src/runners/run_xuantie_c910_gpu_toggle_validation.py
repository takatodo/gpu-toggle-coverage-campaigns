#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BASELINE_RUNNER = SCRIPT_DIR / "run_rtlmeter_gpu_toggle_baseline.py"
DEFAULT_TESTS = ("hello", "memcpy")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(
    cmd: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd or SCRIPT_DIR,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def _tail(path: Path, limit: int = 40) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-limit:])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Run gpu_cov baseline validation for XuanTie-C910."
    )
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument(
        "--configuration",
        default="gpu_cov_gate",
        help="RTLMeter configuration to validate; defaults to gpu_cov_gate.",
    )
    parser.add_argument("--test", dest="tests", action="append")
    parser.add_argument("--nstates", type=int)
    parser.add_argument("--gpu-reps", type=int, default=1)
    parser.add_argument("--gpu-warmup-reps", type=int, default=0)
    parser.add_argument("--cpu-reps", type=int, default=0)
    parser.add_argument("--summary-mode", default="prefilter")
    parser.add_argument("--compile-cache-dir", type=Path)
    parser.add_argument("--skip-cpu-reference-build", action="store_true", default=True)
    parser.add_argument(
        "--reuse-bench-kernel-if-present",
        dest="reuse_bench_kernel_if_present",
        action="store_true",
        help="Reuse bench_kernel directly when present. Defaults to enabled for gpu_cov_gate.",
    )
    parser.add_argument(
        "--no-reuse-bench-kernel-if-present",
        dest="reuse_bench_kernel_if_present",
        action="store_false",
        help="Force wrapper execution even when direct bench reuse is available.",
    )
    parser.add_argument("--compile-full-all-only", dest="compile_full_all_only", action="store_true")
    parser.add_argument("--no-compile-full-all-only", dest="compile_full_all_only", action="store_false")
    parser.set_defaults(compile_full_all_only=None)
    parser.add_argument(
        "--bench-extra-arg",
        dest="bench_extra_args",
        action="append",
        default=[],
        help="Extra argument forwarded to run_rtlmeter_gpu_toggle_baseline.py.",
    )
    parser.set_defaults(reuse_bench_kernel_if_present=None)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--nvcc-flags", default="-O0 -std=c++17 -Xptxas -O0")
    parser.add_argument("--nvcc-object-jobs", type=int)
    args = parser.parse_args(argv)

    tests = args.tests or list(DEFAULT_TESTS)
    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    json_out = (args.json_out or (work_dir / "xuantie_c910_gpu_toggle_validation.json")).resolve()
    nstates = args.nstates
    if nstates is None:
        nstates = 1 if args.configuration == "gpu_cov_gate" else 4
    reuse_bench_kernel_if_present = args.reuse_bench_kernel_if_present
    if reuse_bench_kernel_if_present is None:
        reuse_bench_kernel_if_present = args.configuration == "gpu_cov_gate"
    compile_full_all_only = args.compile_full_all_only
    if compile_full_all_only is None:
        compile_full_all_only = args.configuration != "gpu_cov_gate"
    bench_extra_args = list(args.bench_extra_args or [])
    if not bench_extra_args and args.configuration == "gpu_cov_gate":
        bench_extra_args = ["--assigns-per-kernel", "1000"]
    nvcc_object_jobs = args.nvcc_object_jobs
    if nvcc_object_jobs is None and args.configuration == "gpu_cov_gate":
        nvcc_object_jobs = 2

    results: list[dict[str, Any]] = []
    overall_rc = 0
    for test in tests:
        case = f"XuanTie-C910:{args.configuration}:{test}"
        build_dir = work_dir / args.configuration / test
        build_dir.mkdir(parents=True, exist_ok=True)
        run_json = build_dir / "summary.json"

        entry: dict[str, Any] = {
            "design": "XuanTie-C910",
            "configuration": args.configuration,
            "test": test,
            "case": case,
            "build_dir": str(build_dir),
            "summary_json": str(run_json),
            "nstates": int(nstates),
            "reuse_bench_kernel_if_present": bool(reuse_bench_kernel_if_present),
            "compile_full_all_only": bool(compile_full_all_only),
            "bench_extra_args": list(bench_extra_args),
            "nvcc_flags": args.nvcc_flags,
            "gpu_warmup_reps": int(args.gpu_warmup_reps),
            "nvcc_object_jobs": int(nvcc_object_jobs or 0),
        }

        cmd = [
            sys.executable,
            str(BASELINE_RUNNER),
            "--case",
            case,
            "--build-dir",
            str(build_dir),
            "--json-out",
            str(run_json),
            "--nstates",
            str(nstates),
            "--gpu-reps",
            str(args.gpu_reps),
            "--gpu-warmup-reps",
            str(args.gpu_warmup_reps),
            "--cpu-reps",
            str(args.cpu_reps),
            "--summary-mode",
            args.summary_mode,
        ]
        if args.skip_cpu_reference_build:
            cmd.append("--skip-cpu-reference-build")
        if reuse_bench_kernel_if_present:
            cmd.append("--reuse-bench-kernel-if-present")
        if compile_full_all_only:
            cmd.append("--compile-full-all-only")
        else:
            cmd.append("--no-compile-full-all-only")
        for extra_arg in bench_extra_args:
            cmd.append(f"--bench-extra-arg={extra_arg}")
        if args.compile_cache_dir:
            cmd.extend(["--compile-cache-dir", str(args.compile_cache_dir.resolve())])
        if args.rebuild:
            cmd.append("--rebuild")

        run_env = dict(os.environ)
        run_env["SIM_ACCEL_NVCC_FLAGS"] = args.nvcc_flags
        run_env["SIM_ACCEL_COMPILE_FULL_ALL_ONLY"] = "1" if compile_full_all_only else "0"
        run_env["SIM_ACCEL_ENABLE_FULL_KERNEL_FUSER"] = "1" if compile_full_all_only else "0"
        if nvcc_object_jobs:
            run_env["SIM_ACCEL_NVCC_OBJECT_JOBS"] = str(nvcc_object_jobs)

        proc = _run(cmd, env=run_env)
        entry["returncode"] = proc.returncode
        overall_rc = max(overall_rc, proc.returncode)

        summary: dict[str, Any] = {}
        if run_json.exists():
            try:
                summary = json.loads(run_json.read_text(encoding="utf-8"))
                entry["summary"] = summary
            except json.JSONDecodeError:
                entry["summary_parse_error"] = True
        else:
            entry["stderr_tail"] = "\n".join(proc.stderr.splitlines()[-40:])

        stdout_log = Path(str(summary.get("artifacts", {}).get("stdout_log") or build_dir / "baseline_stdout.log"))
        entry["stdout_log"] = str(stdout_log)
        entry["stdout_tail"] = _tail(stdout_log)
        entry["execute_status"] = "success" if proc.returncode == 0 else "failed"
        if summary:
            entry["bench_runtime_mode"] = str(summary.get("bench_runtime_mode") or "")
            entry["bench_runtime_reused"] = bool(summary.get("bench_runtime_reused"))
            entry["pre_gpu_gate"] = dict(summary.get("pre_gpu_gate") or {})
            entry["collector"] = dict(summary.get("collector") or {})
            entry["coverage_regions"] = dict(summary.get("coverage_regions") or {})
            entry["real_toggle_subset"] = dict(summary.get("real_toggle_subset") or {})

        results.append(entry)

    payload = {
        "design": "XuanTie-C910",
        "configuration": args.configuration,
        "tests": tests,
        "results": results,
        "work_dir": str(work_dir),
    }
    _write_json(json_out, payload)
    return overall_rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
