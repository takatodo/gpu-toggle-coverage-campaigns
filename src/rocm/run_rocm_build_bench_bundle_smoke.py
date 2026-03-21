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
BUILD_BUNDLE = ROOT / "verilator" / "opt" / "gpu" / "cuda" / "build_bench_bundle.py"
DEFAULT_SOURCE_BUNDLE = (
    ROOT
    / "verilator"
    / "test_regress"
    / "obj_vlt"
    / "t_sim_accel_bench_exec"
    / "sim_accel_bench_hit"
)
DEFAULT_OUT_DIR = Path("/tmp/rocm_build_bench_bundle_smoke_v1")
DEFAULT_JSON = SCRIPT_DIR / "rocm_build_bench_bundle_smoke.json"
DEFAULT_MD = SCRIPT_DIR / "rocm_build_bench_bundle_smoke.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy a small sim-accel bundle, build it through build_bench_bundle.py using the "
            "temporary ROCm bridge, execute the off smoke, and write canonical artifacts."
        )
    )
    parser.add_argument("--source-bundle", type=Path, default=DEFAULT_SOURCE_BUNDLE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--gfx-arch", default="")
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
    env.setdefault("ROCM_PATH", "/opt/rocm")
    hip_preload = Path(env["ROCM_PATH"]) / "lib" / "libamdhip64.so"
    preload = env.get("LD_PRELOAD", "")
    if hip_preload.is_file() and "libamdhip64.so" not in preload:
        env["LD_PRELOAD"] = str(hip_preload) if not preload else f"{hip_preload}:{preload}"
    env.setdefault("HSA_OVERRIDE_GFX_VERSION", _gfx_to_hsa_override(gfx_arch))
    return env


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> dict[str, Any]:
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
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\nSee {log_path}"
        )
    return {
        "cmd": cmd,
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


def _load_reference_metrics(source_bundle: Path) -> dict[str, Any]:
    ref_log = source_bundle / "bench_run.log"
    if not ref_log.is_file():
        return {}
    return _parse_kv(ref_log.read_text(encoding="utf-8"))


def _write_summary_md(path: Path, payload: dict[str, Any]) -> None:
    build = payload["build"]
    smoke = payload["smoke_off"]
    cluster = payload["smoke_single_cluster"]
    ref = payload.get("reference_cuda_run", {})
    lines = [
        "# ROCm build_bench_bundle Smoke",
        "",
        f"- status: `{'pass' if payload['pass'] else 'fail'}`",
        f"- gfx_arch: `{payload['gfx_arch']}`",
        f"- source_bundle: `{payload['source_bundle']}`",
        f"- temp_bundle: `{payload['temp_bundle']}`",
        f"- build_log: `{build.get('build_log')}`",
        f"- smoke_off_log: `{build.get('smoke_off_log')}`",
        f"- mismatch: `{smoke.get('mismatch')}`",
        f"- compact_mismatch: `{smoke.get('compact_mismatch')}`",
        f"- gpu_ms_per_rep: `{smoke.get('gpu_ms_per_rep')}`",
        f"- cpu_ms_per_rep: `{smoke.get('cpu_ms_per_rep')}`",
        f"- speedup_gpu_over_cpu: `{smoke.get('speedup_gpu_over_cpu')}`",
        f"- auto_engine_recommendation: `{smoke.get('auto_engine_recommendation')}`",
        f"- single_cluster_pass: `{payload['single_cluster_pass']}`",
        f"- single_cluster_mismatch: `{cluster.get('mismatch')}`",
        f"- single_cluster_compact_mismatch: `{cluster.get('compact_mismatch')}`",
        f"- single_cluster_hybrid_mismatch: `{cluster.get('hybrid_mismatch')}`",
        f"- single_cluster_speedup_gpu_over_cpu: `{cluster.get('speedup_gpu_over_cpu')}`",
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
            f"- [build_bench_bundle.log]({payload['steps']['build_bench_bundle']['log_path']})",
            f"- [build_hipcc.log]({build.get('build_log')})",
            f"- [smoke_off.log]({build.get('smoke_off_log')})",
            f"- [smoke_single_cluster.log]({build.get('smoke_single_cluster_log')})",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    source_bundle = args.source_bundle.resolve()
    gfx_arch = _derive_gfx_arch(args.gfx_arch)
    env = _rocm_env(gfx_arch)

    if args.out_dir.exists():
        shutil.rmtree(args.out_dir)
    shutil.copytree(source_bundle, args.out_dir)
    temp_bundle = args.out_dir.resolve()

    build_step = _run(
        [
            "python3",
            str(BUILD_BUNDLE),
            "--bundle-dir",
            str(temp_bundle),
            "--execution-backend",
            "rocm_llvm",
            "--run-smoke",
            "--smoke-nstates",
            "4",
            "--smoke-gpu-reps",
            "1",
            "--smoke-cpu-reps",
            "1",
            "--gfx-arch",
            gfx_arch,
        ],
        cwd=SCRIPT_DIR,
        env=env,
        log_path=temp_bundle / "build_bench_bundle.log",
    )
    build_metrics = _parse_kv(build_step["stdout"])
    smoke_off_log = Path(str(build_metrics["smoke_off_log"]))
    smoke_metrics = _parse_kv(smoke_off_log.read_text(encoding="utf-8"))
    cluster_log = Path(str(build_metrics["smoke_single_cluster_log"]))
    cluster_metrics = _parse_kv(cluster_log.read_text(encoding="utf-8"))
    single_cluster_pass = (
        cluster_metrics.get("mismatch") == 0
        and cluster_metrics.get("compact_mismatch") == 0
        and cluster_metrics.get("hybrid_mismatch") == 0
    )

    payload: dict[str, Any] = {
        "schema_version": "rocm-build-bench-bundle-smoke-v2",
        "pass": (
            smoke_metrics.get("mismatch") == 0
            and smoke_metrics.get("compact_mismatch") == 0
            and build_metrics.get("execution_backend") == "rocm_llvm"
            and single_cluster_pass
        ),
        "single_cluster_pass": single_cluster_pass,
        "gfx_arch": gfx_arch,
        "source_bundle": str(source_bundle),
        "temp_bundle": str(temp_bundle),
        "environment": {
            "ROCM_PATH": env.get("ROCM_PATH", ""),
            "HSA_OVERRIDE_GFX_VERSION": env.get("HSA_OVERRIDE_GFX_VERSION", ""),
            "LD_PRELOAD": env.get("LD_PRELOAD", ""),
        },
        "steps": {
            "build_bench_bundle": build_step,
        },
        "build": build_metrics,
        "smoke_off": smoke_metrics,
        "smoke_single_cluster": cluster_metrics,
        "reference_cuda_run": _load_reference_metrics(source_bundle),
        "resource_leak_warning": "Resource leak detected by SharedSignalPool"
        in (
            smoke_off_log.read_text(encoding="utf-8")
            + cluster_log.read_text(encoding="utf-8")
        ),
    }

    args.summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_summary_md(args.summary_md, payload)
    print(args.summary_json)
    print(args.summary_md)
    return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
