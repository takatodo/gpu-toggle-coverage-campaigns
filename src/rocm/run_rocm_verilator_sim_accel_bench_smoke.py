#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
VERILATOR_SIM_ACCEL_BENCH = ROOT_DIR / "third_party/verilator/bin/verilator_sim_accel_bench"
VERILATOR_BIN = ROOT_DIR / "third_party/verilator/bin/verilator"
RTL_SOURCE = ROOT_DIR / "third_party/verilator/test_regress" / "t" / "t_sim_accel_bench_exec.v"
DEFAULT_OUT_DIR = Path("/tmp/rocm_verilator_sim_accel_bench_smoke_v2")
DEFAULT_JSON = SCRIPT_DIR / "rocm_verilator_sim_accel_bench_smoke.json"
DEFAULT_MD = SCRIPT_DIR / "rocm_verilator_sim_accel_bench_smoke.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run or summarize a ROCm-bridge verilator_sim_accel_bench wrapper smoke and "
            "write canonical artifacts."
        )
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--reuse-existing", action="store_true")
    parser.add_argument("--nstates", type=int, default=4)
    parser.add_argument("--gpu-reps", type=int, default=1)
    parser.add_argument("--gpu-warmup-reps", type=int, default=0)
    parser.add_argument("--cpu-reps", type=int, default=1)
    parser.add_argument("--assigns-per-kernel", type=int, default=0)
    return parser.parse_args()


def _derive_gfx_arch() -> str:
    override = os.getenv("HSA_OVERRIDE_GFX_VERSION", "").strip()
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", override)
    if not match:
        return ""
    return f"gfx{match.group(1)}{match.group(2)}{match.group(3)}"


def _rocm_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("ROCM_PATH", "/opt/rocm")
    hip_preload = Path(env["ROCM_PATH"]) / "lib" / "libamdhip64.so"
    preload = env.get("LD_PRELOAD", "")
    if hip_preload.is_file() and "libamdhip64.so" not in preload:
        env["LD_PRELOAD"] = str(hip_preload) if not preload else f"{hip_preload}:{preload}"
    env.setdefault("HSA_OVERRIDE_GFX_VERSION", "12.0.1")
    return env


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> dict[str, Any]:
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.perf_counter() - t0
    log_path.write_text(
        f"$ {' '.join(cmd)}\n\n[stdout]\n{proc.stdout}\n[stderr]\n{proc.stderr}\n",
        encoding="utf-8",
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "elapsed_s": elapsed,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "log_path": str(log_path),
    }


def _parse_kv(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value.endswith("x") and key.startswith("speedup_"):
            value = value[:-1]
        if re.fullmatch(r"-?\d+", value):
            out[key] = int(value)
        elif re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", value):
            out[key] = float(value)
        else:
            out[key] = value
    return out


def _read_if_exists(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _write_summary_md(path: Path, payload: dict[str, Any]) -> None:
    wrapper = payload.get("wrapper_run", {})
    bench = payload.get("bench_run", {})
    lines = [
        "# ROCm verilator_sim_accel_bench Smoke",
        "",
        f"- status: `{'pass' if payload['pass'] else 'fail'}`",
        f"- wrapper_reached_build: `{payload['wrapper_reached_build']}`",
        f"- wrapper_reached_run: `{payload['wrapper_reached_run']}`",
        f"- native_hsaco_mode: `{payload['native_hsaco_mode']}`",
        f"- rocm_launch_mode: `{bench.get('rocm_launch_mode')}`",
        f"- gfx_arch: `{payload['gfx_arch'] or 'unknown'}`",
        f"- runtime_gpu_api: `{bench.get('runtime_gpu_api')}`",
        f"- runtime_gpu_device_name: `{bench.get('runtime_gpu_device_name')}`",
        f"- mismatch: `{bench.get('mismatch')}`",
        f"- compact_mismatch: `{bench.get('compact_mismatch')}`",
        f"- gpu_ms_per_rep: `{bench.get('gpu_ms_per_rep')}`",
        f"- cpu_ms_per_rep: `{bench.get('cpu_ms_per_rep')}`",
        f"- speedup_gpu_over_cpu: `{bench.get('speedup_gpu_over_cpu')}`",
        f"- next_blocker: `{payload['next_blocker']}`",
        "",
        "## Evidence",
        "",
        f"- [summary.json]({path.with_suffix('.json')})",
        f"- [wrapper.log]({wrapper.get('log_path', '')})",
        f"- [build_nvcc.log]({payload['paths'].get('build_log', '')})",
        f"- [bench_run.log]({payload['paths'].get('bench_run_log', '')})",
        f"- [verilator_cuda.log]({payload['paths'].get('verilator_cuda_log', '')})",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir.resolve()
    env = _rocm_env()
    wrapper_log = out_dir / "wrapper_smoke.log"
    wrapper_run: dict[str, Any] = {}

    if not args.reuse_existing:
        if out_dir.exists():
            shutil.rmtree(out_dir)
        cmd = [
            str(VERILATOR_SIM_ACCEL_BENCH),
            "--verilator",
            str(VERILATOR_BIN),
            "--top-module",
            "t",
            "--outdir",
            str(out_dir),
            "--nstates",
            str(args.nstates),
            "--gpu-reps",
            str(args.gpu_reps),
            "--gpu-warmup-reps",
            str(args.gpu_warmup_reps),
            "--cpu-reps",
            str(args.cpu_reps),
            "--assigns-per-kernel",
            str(args.assigns_per_kernel),
            "--execution-backend",
            "rocm_llvm",
            "--no-compile-cache",
            "--",
            str(RTL_SOURCE),
        ]
        wrapper_run = _run(cmd, cwd=SCRIPT_DIR, env=env, log_path=wrapper_log)
    else:
        wrapper_run = {
            "cmd": [],
            "returncode": 1,
            "elapsed_s": 0.0,
            "stdout": "",
            "stderr": "",
            "log_path": str(wrapper_log),
        }
        if wrapper_log.is_file():
            wrapper_run["stdout"] = wrapper_log.read_text(encoding="utf-8")

    build_log = out_dir / "build_nvcc.log"
    bench_run_log = out_dir / "bench_run.log"
    verilator_cuda_log = out_dir / "verilator_cuda.log"

    bench_metrics = _parse_kv(_read_if_exists(bench_run_log))
    wrapper_stdout = wrapper_run.get("stdout", "")
    if not wrapper_stdout and wrapper_log.is_file():
        wrapper_stdout = wrapper_log.read_text(encoding="utf-8")

    wrapper_reached_build = "[3/4] Building HIP-bridged benchmark..." in wrapper_stdout or build_log.is_file()
    wrapper_reached_build = wrapper_reached_build or "[3/4] Building native hsaco benchmark..." in wrapper_stdout
    wrapper_reached_run = "[4/4] Running benchmark..." in wrapper_stdout or bench_run_log.is_file()
    pass_run = bench_metrics.get("mismatch") == 0 and bench_metrics.get("compact_mismatch") == 0
    rocm_launch_mode = str(bench_metrics.get("rocm_launch_mode") or "")
    native_hsaco_mode = rocm_launch_mode == "native-hsaco"

    payload: dict[str, Any] = {
        "schema_version": "rocm-verilator-sim-accel-bench-smoke-v1",
        "pass": bool(pass_run),
        "gfx_arch": _derive_gfx_arch(),
        "environment": {
            "ROCM_PATH": env.get("ROCM_PATH", ""),
            "HSA_OVERRIDE_GFX_VERSION": env.get("HSA_OVERRIDE_GFX_VERSION", ""),
            "LD_PRELOAD": env.get("LD_PRELOAD", ""),
        },
        "wrapper_reached_build": wrapper_reached_build,
        "wrapper_reached_run": wrapper_reached_run,
        "native_hsaco_mode": native_hsaco_mode,
        "next_blocker": (
            "promote_native_hsaco_into_wrapper_and_second_wave"
            if (pass_run and native_hsaco_mode)
            else (
                "promote_wrapper_rocm_bridge_into_mainline_runner_validation"
                if pass_run
                else (
                    "fix_wrapper_native_hsaco_functional_mismatch"
                    if (wrapper_reached_run and native_hsaco_mode)
                    else (
                        "fix_wrapper_generated_launch_all_functional_mismatch"
                        if wrapper_reached_run
                        else (
                            "run_wrapper_native_hsaco_to_benchmark"
                            if (wrapper_reached_build and native_hsaco_mode)
                            else (
                                "run_wrapper_smoke_to_benchmark"
                                if wrapper_reached_build
                                else "run_wrapper_rocm_bridge_build"
                            )
                        )
                    )
                )
            )
        ),
        "wrapper_run": wrapper_run,
        "bench_run": bench_metrics,
        "paths": {
            "out_dir": str(out_dir),
            "build_log": str(build_log),
            "bench_run_log": str(bench_run_log),
            "verilator_cuda_log": str(verilator_cuda_log),
        },
        "resource_leak_warning": "Resource leak detected by SharedSignalPool" in _read_if_exists(bench_run_log),
    }

    args.summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_summary_md(args.summary_md, payload)
    print(args.summary_json)
    print(args.summary_md)
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
