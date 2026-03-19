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
ROOT_DIR = SCRIPT_DIR.parent.parent
RTLMETER_ROOT = ROOT_DIR / "rtlmeter"
BASELINE_RUNNER = SCRIPT_DIR / "run_rtlmeter_gpu_toggle_baseline.py"
DEFAULT_DESIGNS = ("VeeR-EL2", "VeeR-EH1", "VeeR-EH2")


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


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run gpu_cov baseline validation across the VeeR family.")
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--case-name", default="hello")
    parser.add_argument("--design", dest="designs", action="append")
    parser.add_argument(
        "--configuration",
        default="gpu_cov_gate",
        help="RTLMeter configuration to validate; defaults to the clean-termination late-family gate",
    )
    parser.add_argument("--nstates", type=int, default=4)
    parser.add_argument("--gpu-reps", type=int, default=1)
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
    parser.set_defaults(compile_full_all_only=True)
    parser.set_defaults(reuse_bench_kernel_if_present=None)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--nvcc-flags", default="-O1 -std=c++17")
    parser.add_argument(
        "--skip-standard-precheck",
        action="store_true",
        help="Skip a standard Verilator run before gpu_cov validation",
    )
    args = parser.parse_args(argv)

    designs = args.designs or list(DEFAULT_DESIGNS)
    work_dir = args.work_dir.resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    json_out = (args.json_out or (work_dir / "veer_family_gpu_toggle_validation.json")).resolve()
    reuse_bench_kernel_if_present = args.reuse_bench_kernel_if_present
    if reuse_bench_kernel_if_present is None:
        reuse_bench_kernel_if_present = args.configuration == "gpu_cov_gate"

    results: list[dict[str, Any]] = []
    overall_rc = 0
    for design in designs:
        case = f"{design}:{args.configuration}:{args.case_name}"
        build_dir = work_dir / design / args.configuration
        build_dir.mkdir(parents=True, exist_ok=True)
        run_json = build_dir / "baseline.json"
        entry: dict[str, Any] = {
            "design": design,
            "case": case,
            "build_dir": str(build_dir),
            "json_out": str(run_json),
            "stdout_log": str(build_dir / "baseline_stdout.log"),
            "nvcc_flags": args.nvcc_flags,
            "reuse_bench_kernel_if_present": bool(reuse_bench_kernel_if_present),
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
            str(args.nstates),
            "--gpu-reps",
            str(args.gpu_reps),
            "--cpu-reps",
            str(args.cpu_reps),
            "--summary-mode",
            args.summary_mode,
            "--include-focused-wave-prefilter",
        ]
        cmd.extend(["--pre-gpu-gate", "never" if args.skip_standard_precheck else "always"])
        if args.skip_cpu_reference_build:
            cmd.append("--skip-cpu-reference-build")
        if reuse_bench_kernel_if_present:
            cmd.append("--reuse-bench-kernel-if-present")
        if args.compile_full_all_only:
            cmd.append("--compile-full-all-only")
        if args.compile_cache_dir:
            cmd.extend(["--compile-cache-dir", str(args.compile_cache_dir.resolve())])
        if args.rebuild:
            cmd.append("--rebuild")

        run_env = dict(os.environ)
        run_env.setdefault("SIM_ACCEL_NVCC_FLAGS", args.nvcc_flags)
        run_env.setdefault("SIM_ACCEL_COMPILE_FULL_ALL_ONLY", "1" if args.compile_full_all_only else "0")
        run_env.setdefault("SIM_ACCEL_ENABLE_FULL_KERNEL_FUSER", "1" if args.compile_full_all_only else "0")

        proc = _run(cmd, env=run_env)
        entry["returncode"] = proc.returncode
        if run_json.exists():
            try:
                entry["summary"] = json.loads(run_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                entry["summary_parse_error"] = True
        else:
            entry["stderr_tail"] = "\n".join(proc.stderr.splitlines()[-40:])
        results.append(entry)
        overall_rc = max(overall_rc, proc.returncode)

    payload = {
        "case_name": args.case_name,
        "designs": designs,
        "results": results,
    }
    _write_json(json_out, payload)
    return overall_rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
