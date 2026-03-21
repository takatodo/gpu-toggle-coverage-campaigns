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
ROOT = Path("/home/takatodo/GEM_try")
DEFAULT_BENCH_DIR = (
    ROOT
    / "verilator"
    / "test_regress"
    / "obj_vlt"
    / "t_sim_accel_bench_exec"
    / "sim_accel_bench"
)
DEFAULT_OUT_DIR = Path("/tmp/rocm_sim_accel_launch_all_smoke_v1")
DEFAULT_JSON = SCRIPT_DIR / "rocm_sim_accel_launch_all_smoke.json"
DEFAULT_MD = SCRIPT_DIR / "rocm_sim_accel_launch_all_smoke.md"
DEFAULT_ROCM_PATH = Path("/opt/rocm")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Hipify and run the smallest legacy sim-accel launch_all bench under ROCm/HIP, "
            "then write canonical smoke artifacts."
        )
    )
    parser.add_argument("--bench-dir", type=Path, default=DEFAULT_BENCH_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--gfx-arch", default="")
    parser.add_argument("--hipcc", default=shutil.which("hipcc") or "hipcc")
    parser.add_argument(
        "--hipify-perl",
        default=shutil.which("hipify-perl") or str(DEFAULT_ROCM_PATH / "bin" / "hipify-perl"),
    )
    return parser.parse_args()


def _derive_gfx_arch(explicit: str) -> str:
    if explicit:
        return explicit
    override = os.getenv("HSA_OVERRIDE_GFX_VERSION", "").strip()
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", override)
    if match:
        return f"gfx{match.group(1)}{match.group(2)}{match.group(3)}"
    raise RuntimeError(
        "Could not derive gfx arch. Pass --gfx-arch explicitly or set HSA_OVERRIDE_GFX_VERSION."
    )


def _gfx_to_hsa_override(gfx_arch: str) -> str:
    match = re.fullmatch(r"gfx(\d+)(\d)(\d)", gfx_arch)
    if not match:
        return ""
    return f"{match.group(1)}.{match.group(2)}.{match.group(3)}"


def _rocm_env(gfx_arch: str) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("ROCM_PATH", str(DEFAULT_ROCM_PATH))
    hip_preload = str(DEFAULT_ROCM_PATH / "lib" / "libamdhip64.so")
    if Path(hip_preload).is_file():
        preload = env.get("LD_PRELOAD", "")
        if "libamdhip64.so" not in preload:
            env["LD_PRELOAD"] = hip_preload if not preload else f"{hip_preload}:{preload}"
    if not env.get("HSA_OVERRIDE_GFX_VERSION"):
        override = _gfx_to_hsa_override(gfx_arch)
        if override:
            env["HSA_OVERRIDE_GFX_VERSION"] = override
    return env


def _run(
    cmd: list[str], *, cwd: Path, env: dict[str, str], log_path: Path, allow_failure: bool = False
) -> dict[str, Any]:
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - t0
    log_path.write_text(
        f"$ {' '.join(cmd)}\n\n[stdout]\n{proc.stdout}\n[stderr]\n{proc.stderr}\n",
        encoding="utf-8",
    )
    if proc.returncode != 0 and not allow_failure:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\nSee {log_path}"
        )
    return {
        "cmd": cmd,
        "elapsed_s": elapsed,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "log_path": str(log_path),
    }


def _hipify(source_path: Path, dest_path: Path, *, hipify_perl: str, cwd: Path, env: dict[str, str]) -> dict[str, Any]:
    log_path = cwd / f"{source_path.stem}.hipify.log"
    step = _run([hipify_perl, str(source_path)], cwd=cwd, env=env, log_path=log_path)
    dest_path.write_text(step["stdout"], encoding="utf-8")
    return step


def _patch_bench_include(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace('#include "kernel_generated.cu"', '#include "kernel_generated.hip.cpp"')
    path.write_text(text, encoding="utf-8")


def _parse_kv_metrics(stdout: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for line in stdout.splitlines():
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
            metrics[key] = int(value)
            continue
        if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", value):
            metrics[key] = float(value)
            continue
        metrics[key] = value
    return metrics


def _load_reference_metrics(bench_dir: Path) -> dict[str, Any]:
    ref_log = bench_dir / "bench_run.log"
    if not ref_log.is_file():
        return {}
    return _parse_kv_metrics(ref_log.read_text(encoding="utf-8"))


def _write_summary_md(path: Path, payload: dict[str, Any]) -> None:
    run = payload["run"]
    ref = payload.get("reference_cuda_run", {})
    lines = [
        "# ROCm sim-accel launch_all Smoke",
        "",
        f"- status: `{'pass' if payload['pass'] else 'fail'}`",
        f"- gfx_arch: `{payload['gfx_arch']}`",
        f"- bench_source: `{payload['bench_source']}`",
        f"- hipified_bench: `{payload['artifacts']['bench_hip']}`",
        f"- mismatch: `{run.get('mismatch')}`",
        f"- compact_mismatch: `{run.get('compact_mismatch')}`",
        f"- gpu_ms_per_rep: `{run.get('gpu_ms_per_rep')}`",
        f"- cpu_ms_per_rep: `{run.get('cpu_ms_per_rep')}`",
        f"- speedup_gpu_over_cpu: `{run.get('speedup_gpu_over_cpu')}`",
        f"- resource_leak_warning: `{payload['resource_leak_warning']}`",
    ]
    if ref:
        lines.extend(
            [
                "",
                "## CUDA Reference",
                "",
                f"- reference_gpu_ms_per_rep: `{ref.get('gpu_ms_per_rep')}`",
                f"- reference_cpu_ms_per_rep: `{ref.get('cpu_ms_per_rep')}`",
                f"- reference_speedup_gpu_over_cpu: `{ref.get('speedup_gpu_over_cpu')}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- [summary.json]({path.with_suffix('.json')})",
            f"- [hipify_bench.log]({payload['steps']['hipify_bench']['log_path']})",
            f"- [hipify_kernel.log]({payload['steps']['hipify_kernel']['log_path']})",
            f"- [compile.log]({payload['steps']['compile']['log_path']})",
            f"- [run.log]({payload['steps']['run']['log_path']})",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    bench_dir = args.bench_dir.resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    required = [
        "bench_kernel.cu",
        "kernel_generated.cu",
        "cpu_body.inc",
        "kernel_generated.vars.tsv",
        "kernel_generated.comm.tsv",
    ]
    missing = [name for name in required if not (bench_dir / name).is_file()]
    if missing:
        raise RuntimeError(f"Missing required bench files: {missing}")

    gfx_arch = _derive_gfx_arch(args.gfx_arch)
    env = _rocm_env(gfx_arch)

    for name in required:
        shutil.copy2(bench_dir / name, out_dir / name)

    bench_hip = out_dir / "bench_kernel.hip.cpp"
    kernel_hip = out_dir / "kernel_generated.hip.cpp"

    steps: dict[str, Any] = {}
    steps["hipify_bench"] = _hipify(
        out_dir / "bench_kernel.cu",
        bench_hip,
        hipify_perl=args.hipify_perl,
        cwd=out_dir,
        env=env,
    )
    steps["hipify_kernel"] = _hipify(
        out_dir / "kernel_generated.cu",
        kernel_hip,
        hipify_perl=args.hipify_perl,
        cwd=out_dir,
        env=env,
    )
    _patch_bench_include(bench_hip)

    bench_bin = out_dir / "bench_kernel_hip"
    steps["compile"] = _run(
        [
            args.hipcc,
            "-std=c++17",
            "-O2",
            f"--offload-arch={gfx_arch}",
            str(bench_hip),
            "-o",
            str(bench_bin),
        ],
        cwd=out_dir,
        env=env,
        log_path=out_dir / "compile.log",
    )
    steps["run"] = _run(
        [str(bench_bin)],
        cwd=out_dir,
        env=env,
        log_path=out_dir / "run.log",
    )

    run_metrics = _parse_kv_metrics(steps["run"]["stdout"])
    payload: dict[str, Any] = {
        "schema_version": "rocm-sim-accel-launch-all-smoke-v1",
        "pass": (
            steps["compile"]["returncode"] == 0
            and steps["run"]["returncode"] == 0
            and run_metrics.get("mismatch") == 0
            and run_metrics.get("compact_mismatch") == 0
        ),
        "gfx_arch": gfx_arch,
        "bench_source": str(bench_dir),
        "artifacts": {
            "out_dir": str(out_dir),
            "bench_hip": str(bench_hip),
            "kernel_hip": str(kernel_hip),
            "bench_binary": str(bench_bin),
        },
        "environment": {
            "ROCM_PATH": env.get("ROCM_PATH", ""),
            "HSA_OVERRIDE_GFX_VERSION": env.get("HSA_OVERRIDE_GFX_VERSION", ""),
            "LD_PRELOAD": env.get("LD_PRELOAD", ""),
        },
        "steps": steps,
        "run": run_metrics,
        "reference_cuda_run": _load_reference_metrics(bench_dir),
        "resource_leak_warning": "Resource leak detected by SharedSignalPool" in steps["run"]["stderr"],
    }

    args.summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_summary_md(args.summary_md, payload)
    print(args.summary_json)
    print(args.summary_md)
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
