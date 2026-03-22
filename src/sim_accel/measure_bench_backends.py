#!/usr/bin/env python3
"""Build and benchmark source/CIRCT sim-accel bench bundles under one driver."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shlex
import shutil
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
CUDA_OPT_DIR = SCRIPT_PATH.parent
PREPARE_SCRIPT = CUDA_OPT_DIR / "prepare_bench_bundle.py"
BUILD_SCRIPT = CUDA_OPT_DIR / "build_bench_bundle.py"
DEFAULT_BUNDLE_CACHE_ROOT = Path("/tmp/opentitan_tlul_slice_backend_bundle_cache")
BUNDLE_CACHE_ABI_VERSION = "v1-generated-dir-signature"
DEFAULT_CASES = (
    "name=single_step_small,nstates=4,gpu_reps=1,cpu_reps=1,sequential_steps=1",
    "name=single_step_medium,nstates=256,gpu_reps=1,cpu_reps=1,sequential_steps=1",
    "name=multi_step_medium,nstates=256,gpu_reps=20,cpu_reps=1,sequential_steps=56",
)
METRIC_NAMES = (
    "gpu_ms_per_rep",
    "cpu_ms_per_rep",
    "speedup_gpu_over_cpu",
    "mismatch",
    "compact_mismatch",
    "partition_cpu_mismatch",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare/build both source and circt-cubin bench bundles from one "
            "generated directory and benchmark them under identical case matrices."
        )
    )
    parser.add_argument(
        "--generated-dir",
        type=Path,
        required=True,
        help="Directory containing fused kernel_generated.* outputs",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Directory used for staged bundles, logs, and benchmark results",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Remove an existing --out-dir before benchmarking",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help=(
            "Benchmark case spec such as "
            "'name=single_step,nstates=256,gpu_reps=1,cpu_reps=1,sequential_steps=1'. "
            "May be passed multiple times."
        ),
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=7,
        help="Number of repeated runs per backend/case",
    )
    parser.add_argument(
        "--compare-compact",
        action="store_true",
        help="Emit compact dumps for every run and compare source vs circt bytes",
    )
    parser.add_argument(
        "--init-seed",
        type=int,
        default=1,
        help="Initialization seed passed to every bench invocation",
    )
    parser.add_argument(
        "--bench-arg",
        action="append",
        default=[],
        help="Extra argument appended to every bench invocation",
    )
    parser.add_argument(
        "--nvcc",
        default="nvcc",
        help="CUDA compiler executable passed through to build_bench_bundle.py",
    )
    parser.add_argument(
        "--cxx",
        default="g++",
        help="Host C++ compiler executable passed through to build_bench_bundle.py",
    )
    parser.add_argument(
        "--nvcc-flag",
        action="append",
        default=[],
        help="Extra flag forwarded to build_bench_bundle.py",
    )
    parser.add_argument(
        "--cxx-flag",
        action="append",
        default=[],
        help="Extra flag forwarded to build_bench_bundle.py",
    )
    parser.add_argument(
        "--bundle-cache-root",
        type=Path,
        default=DEFAULT_BUNDLE_CACHE_ROOT,
        help="Shared bundle cache root used to reuse prepared/built bundles across compare runs",
    )
    return parser.parse_args()


def _run_logged(
    cmd: list[str],
    *,
    cwd: Path,
    log_path: Path,
    env: dict[str, str] | None = None,
    allow_failure: bool = False,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
        env=merged_env,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"$ {shlex.join(cmd)}\n")
        if env:
            for key in sorted(env):
                fh.write(f"[env] {key}={env[key]}\n")
        if result.stdout:
            fh.write(result.stdout)
            if not result.stdout.endswith("\n"):
                fh.write("\n")
        if result.stderr:
            fh.write(result.stderr)
            if not result.stderr.endswith("\n"):
                fh.write("\n")
        fh.write(f"[exit={result.returncode}]\n\n")
    if result.returncode != 0 and not allow_failure:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {shlex.join(cmd)}\n"
            f"See log: {log_path}"
        )
    return result


def _parse_case_spec(spec: str, *, index: int) -> dict[str, Any]:
    raw: dict[str, str] = {}
    for part in spec.split(","):
        piece = part.strip()
        if not piece:
            continue
        if "=" not in piece:
            raise ValueError(f"Invalid --case entry without key=value: {spec!r}")
        key, value = piece.split("=", 1)
        raw[key.strip()] = value.strip()
    required = ("nstates", "gpu_reps", "cpu_reps", "sequential_steps")
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"Missing {', '.join(missing)} in --case {spec!r}")
    case = {
        "name": raw.get("name", f"case_{index:02d}"),
        "nstates": int(raw["nstates"]),
        "gpu_reps": int(raw["gpu_reps"]),
        "cpu_reps": int(raw["cpu_reps"]),
        "sequential_steps": int(raw["sequential_steps"]),
        "extra_args": raw.get("extra_args", ""),
    }
    if case["nstates"] <= 0 or case["gpu_reps"] <= 0 or case["cpu_reps"] <= 0:
        raise ValueError(f"All repetition/state values must be positive in --case {spec!r}")
    return case


def _load_cases(case_specs: list[str]) -> list[dict[str, Any]]:
    specs = case_specs or list(DEFAULT_CASES)
    cases = [_parse_case_spec(spec, index=i) for i, spec in enumerate(specs)]
    seen = set()
    for case in cases:
        name = case["name"]
        if name in seen:
            raise ValueError(f"Duplicate case name: {name}")
        seen.add(name)
    return cases


def _prepare_bundle(
    generated_dir: Path,
    bundle_dir: Path,
    *,
    launch_backend: str,
    log_path: Path,
) -> None:
    cmd = [
        sys.executable,
        str(PREPARE_SCRIPT),
        "--generated-dir",
        str(generated_dir),
        "--out-dir",
        str(bundle_dir),
        "--force",
        "--launch-backend",
        launch_backend,
    ]
    _run_logged(cmd, cwd=CUDA_OPT_DIR, log_path=log_path)


def _build_bundle(args: argparse.Namespace, bundle_dir: Path, *, log_path: Path) -> None:
    cmd = [
        sys.executable,
        str(BUILD_SCRIPT),
        "--bundle-dir",
        str(bundle_dir),
        "--clean-obj-dir",
        "--nvcc",
        args.nvcc,
        "--cxx",
        args.cxx,
    ]
    for flag in args.nvcc_flag:
        cmd.extend(["--nvcc-flag", flag])
    for flag in args.cxx_flag:
        cmd.extend(["--cxx-flag", flag])
    _run_logged(cmd, cwd=CUDA_OPT_DIR, log_path=log_path)


def _bundle_cache_meta_path(bundle_dir: Path) -> Path:
    return bundle_dir / ".measure_bench_backends_bundle_cache.json"


def _generated_dir_signature(generated_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in generated_dir.rglob("*") if p.is_file()):
        rel = path.relative_to(generated_dir)
        stat = path.stat()
        digest.update(str(rel).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _bundle_cache_key(generated_dir: Path, generated_signature: str) -> str:
    parent_name = generated_dir.parent.name or generated_dir.name
    return f"{parent_name}-{generated_signature[:16]}"


def _expected_bundle_cache_meta(
    args: argparse.Namespace,
    *,
    generated_dir: Path,
    generated_signature: str,
    launch_backend: str,
) -> dict[str, Any]:
    return {
        "schema_version": "measure-bench-backends-bundle-cache-v1",
        "abi_version": BUNDLE_CACHE_ABI_VERSION,
        "generated_dir": str(generated_dir),
        "generated_signature": generated_signature,
        "launch_backend": launch_backend,
        "nvcc": args.nvcc,
        "cxx": args.cxx,
        "nvcc_flags": list(args.nvcc_flag),
        "cxx_flags": list(args.cxx_flag),
    }


def _load_bundle_cache_meta(bundle_dir: Path) -> dict[str, Any]:
    meta_path = _bundle_cache_meta_path(bundle_dir)
    if not meta_path.is_file():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _bundle_cache_matches(bundle_dir: Path, expected: dict[str, Any]) -> bool:
    binary_path = bundle_dir / "bench_kernel"
    config_path = bundle_dir / "sim_accel_bundle_config.json"
    if not binary_path.is_file() or not config_path.is_file():
        return False
    current = _load_bundle_cache_meta(bundle_dir)
    return current == expected


def _write_bundle_cache_meta(bundle_dir: Path, payload: dict[str, Any]) -> None:
    _bundle_cache_meta_path(bundle_dir).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _ensure_cached_bundle(
    args: argparse.Namespace,
    *,
    generated_dir: Path,
    generated_signature: str,
    launch_backend: str,
    bundle_cache_root: Path,
    prepare_log_path: Path,
    build_log_path: Path,
) -> dict[str, Any]:
    cache_key = _bundle_cache_key(generated_dir, generated_signature)
    bundle_dir = bundle_cache_root / cache_key / launch_backend
    expected_meta = _expected_bundle_cache_meta(
        args,
        generated_dir=generated_dir,
        generated_signature=generated_signature,
        launch_backend=launch_backend,
    )
    cache_hit = _bundle_cache_matches(bundle_dir, expected_meta)
    cache_rebuilt = False
    if not cache_hit:
        cache_rebuilt = True
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir)
        _prepare_bundle(generated_dir, bundle_dir, launch_backend=launch_backend, log_path=prepare_log_path)
        _build_bundle(args, bundle_dir, log_path=build_log_path)
        _write_bundle_cache_meta(bundle_dir, expected_meta)
    return {
        "bundle_dir": bundle_dir,
        "cache_key": cache_key,
        "cache_hit": cache_hit,
        "cache_rebuilt": cache_rebuilt,
        "meta": expected_meta,
    }


def _metric_from_output(text: str, name: str) -> str | None:
    match = re.search(rf"\b{name}=([^\s]+)", text)
    return match.group(1) if match else None


def _parse_bench_result(text: str, *, returncode: int) -> dict[str, Any]:
    metrics: dict[str, Any] = {"returncode": returncode}
    found_any = False
    for name in METRIC_NAMES:
        raw = _metric_from_output(text, name)
        if raw is None:
            continue
        found_any = True
        if name.endswith("_ms_per_rep"):
            metrics[name] = float(raw)
        elif name == "speedup_gpu_over_cpu":
            metrics[name] = raw
        else:
            metrics[name] = int(raw)
    for name in ("mismatch_first_state", "mismatch_first_var"):
        raw = _metric_from_output(text, name)
        if raw is not None:
            metrics[name] = int(raw)
    for name in ("mismatch_first_expected", "mismatch_first_actual"):
        raw = _metric_from_output(text, name)
        if raw is not None:
            metrics[name] = raw
    if not found_any:
        raise RuntimeError("Bench output did not contain expected metrics")
    return metrics


def _load_bundle_config(bundle_dir: Path) -> dict[str, Any]:
    config_path = bundle_dir / "sim_accel_bundle_config.json"
    if not config_path.is_file():
        return {
            "launch_backend": "cuda",
            "gpu_binary_kind": "embedded_cuda",
            "gpu_binary_relpath": "",
            "gpu_binary_env_var": "",
            "gpu_binary_required": False,
        }
    return json.loads(config_path.read_text(encoding="utf-8"))


def _backend_env(bundle_dir: Path) -> dict[str, str]:
    config = _load_bundle_config(bundle_dir)
    env: dict[str, str] = {}
    env_var = str(config.get("gpu_binary_env_var") or "").strip()
    relpath = str(config.get("gpu_binary_relpath") or "").strip()
    if env_var and relpath:
        binary_path = str((bundle_dir / relpath).resolve())
        env[env_var] = binary_path
        legacy_env_var = str(config.get("gpu_binary_legacy_env_var") or "").strip()
        if legacy_env_var and legacy_env_var != env_var:
            env[legacy_env_var] = binary_path
    return env


def _compare_files(left: Path, right: Path) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as lhs, right.open("rb") as rhs:
        while True:
            left_chunk = lhs.read(1024 * 1024)
            right_chunk = rhs.read(1024 * 1024)
            if left_chunk != right_chunk:
                return False
            if not left_chunk:
                return True


def _run_case(
    bundle_dir: Path,
    *,
    backend: str,
    case: dict[str, Any],
    repeats: int,
    init_seed: int,
    bench_args: list[str],
    compare_compact: bool,
    artifact_dir: Path,
    log_path: Path,
) -> dict[str, Any]:
    binary_path = bundle_dir / "bench_kernel"
    env = _backend_env(bundle_dir)
    runs: list[dict[str, Any]] = []
    compact_paths: list[str] = []
    for repeat in range(repeats):
        cmd = [
            str(binary_path),
            "--nstates",
            str(case["nstates"]),
            "--gpu-reps",
            str(case["gpu_reps"]),
            "--cpu-reps",
            str(case["cpu_reps"]),
            "--sequential-steps",
            str(case["sequential_steps"]),
            "--init-seed",
            str(init_seed),
            *bench_args,
        ]
        extra_args = str(case.get("extra_args", "")).strip()
        if extra_args:
            cmd.extend(shlex.split(extra_args))
        compact_path: Path | None = None
        if compare_compact:
            compact_path = artifact_dir / f"{case['name']}.{backend}.run{repeat}.compact.bin"
            cmd.extend(["--dump-output-compact", str(compact_path)])
        result = _run_logged(cmd, cwd=bundle_dir, log_path=log_path, env=env, allow_failure=True)
        parsed = _parse_bench_result(result.stdout + result.stderr, returncode=result.returncode)
        parsed["repeat"] = repeat
        if compact_path is not None:
            parsed["compact_dump_path"] = str(compact_path)
            compact_paths.append(str(compact_path))
        runs.append(parsed)
    gpu_values = [run["gpu_ms_per_rep"] for run in runs]
    cpu_values = [run["cpu_ms_per_rep"] for run in runs]
    mismatches = [run.get("mismatch") for run in runs]
    compact_mismatches = [run.get("compact_mismatch") for run in runs]
    return {
        "backend": backend,
        "case_name": case["name"],
        "case": case,
        "runs": runs,
        "gpu_ms_per_rep_median": statistics.median(gpu_values),
        "gpu_ms_per_rep_min": min(gpu_values),
        "gpu_ms_per_rep_max": max(gpu_values),
        "cpu_ms_per_rep_median": statistics.median(cpu_values),
        "returncodes": [run["returncode"] for run in runs],
        "mismatch_values": mismatches,
        "compact_mismatch_values": compact_mismatches,
        "all_returncode_zero": all(code == 0 for code in (run["returncode"] for run in runs)),
        "all_mismatch_zero": all(value == 0 for value in mismatches if value is not None),
        "all_compact_mismatch_zero": all(value == 0 for value in compact_mismatches if value is not None),
        "compact_dump_paths": compact_paths,
    }


def _write_csv(rows: list[dict[str, Any]], csv_path: Path) -> None:
    fieldnames = [
        "case_name",
        "backend",
        "nstates",
        "gpu_reps",
        "cpu_reps",
        "sequential_steps",
        "gpu_ms_per_rep_median",
        "gpu_ms_per_rep_min",
        "gpu_ms_per_rep_max",
        "cpu_ms_per_rep_median",
        "all_returncode_zero",
        "all_mismatch_zero",
        "all_compact_mismatch_zero",
        "compact_identical",
        "circt_vs_source_speedup",
        "circt_delta_pct_vs_source",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def _write_summary(summary_rows: list[dict[str, Any]], summary_path: Path) -> None:
    lines = [
        "# Bench Backend Benchmark Summary",
        "",
        "| Case | Source GPU median (ms) | CIRCT GPU median (ms) | CIRCT vs source | Compact identical |",
        "|---|---:|---:|---:|---|",
    ]
    for row in summary_rows:
        ratio = row.get("circt_vs_source_speedup")
        delta_pct = row.get("circt_delta_pct_vs_source")
        if ratio is None or delta_pct is None:
            delta_text = "n/a"
        else:
            delta_text = f"{ratio:.3f}x / {delta_pct:+.1f}%"
        lines.append(
            "| {case_name} | {source_gpu:.6f} | {circt_gpu:.6f} | {delta} | {compact} |".format(
                case_name=row["case_name"],
                source_gpu=row["source_gpu_ms_per_rep_median"],
                circt_gpu=row["circt_gpu_ms_per_rep_median"],
                delta=delta_text,
                compact=row.get("compact_identical", "n/a"),
            )
        )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    generated_dir = args.generated_dir.resolve()
    out_dir = args.out_dir.resolve()
    bundle_cache_root = args.bundle_cache_root.resolve()
    cases = _load_cases(args.case)

    if args.force and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = out_dir / "logs"
    artifacts_dir = out_dir / "artifacts"
    logs_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    bundle_cache_root.mkdir(parents=True, exist_ok=True)

    generated_signature = _generated_dir_signature(generated_dir)
    bundle_infos = {
        "source": _ensure_cached_bundle(
            args,
            generated_dir=generated_dir,
            generated_signature=generated_signature,
            launch_backend="cuda",
            bundle_cache_root=bundle_cache_root,
            prepare_log_path=logs_dir / "prepare_source.log",
            build_log_path=logs_dir / "build_source.log",
        ),
        "circt-cubin": _ensure_cached_bundle(
            args,
            generated_dir=generated_dir,
            generated_signature=generated_signature,
            launch_backend="circt-cubin",
            bundle_cache_root=bundle_cache_root,
            prepare_log_path=logs_dir / "prepare_circt.log",
            build_log_path=logs_dir / "build_circt.log",
        ),
    }
    bundles = {name: Path(str(info["bundle_dir"])).resolve() for name, info in bundle_infos.items()}

    per_case_results: dict[str, dict[str, Any]] = {}
    for case in cases:
        case_name = case["name"]
        case_dir = artifacts_dir / case_name
        case_dir.mkdir(parents=True, exist_ok=True)
        per_case_results[case_name] = {}
        for backend, bundle_dir in bundles.items():
            per_case_results[case_name][backend] = _run_case(
                bundle_dir,
                backend=backend,
                case=case,
                repeats=args.repeats,
                init_seed=args.init_seed,
                bench_args=args.bench_arg,
                compare_compact=args.compare_compact,
                artifact_dir=case_dir,
                log_path=logs_dir / f"{case_name}.{backend}.log",
            )

    summary_rows: list[dict[str, Any]] = []
    detailed_rows: list[dict[str, Any]] = []
    for case in cases:
        case_name = case["name"]
        source_result = per_case_results[case_name]["source"]
        circt_result = per_case_results[case_name]["circt-cubin"]
        compact_identical: str | None = None
        if args.compare_compact and source_result["compact_dump_paths"] and circt_result["compact_dump_paths"]:
            compare_count = min(len(source_result["compact_dump_paths"]), len(circt_result["compact_dump_paths"]))
            compact_identical = str(
                all(
                    _compare_files(Path(source_result["compact_dump_paths"][i]), Path(circt_result["compact_dump_paths"][i]))
                    for i in range(compare_count)
                )
            ).lower()
        source_gpu = source_result["gpu_ms_per_rep_median"]
        circt_gpu = circt_result["gpu_ms_per_rep_median"]
        speedup = source_gpu / circt_gpu if circt_gpu else None
        delta_pct = ((source_gpu - circt_gpu) / source_gpu * 100.0) if source_gpu else None
        summary = {
            "case_name": case_name,
            "source_gpu_ms_per_rep_median": source_gpu,
            "circt_gpu_ms_per_rep_median": circt_gpu,
            "source_cpu_ms_per_rep_median": source_result["cpu_ms_per_rep_median"],
            "circt_cpu_ms_per_rep_median": circt_result["cpu_ms_per_rep_median"],
            "circt_vs_source_speedup": speedup,
            "circt_delta_pct_vs_source": delta_pct,
            "compact_identical": compact_identical if compact_identical is not None else "n/a",
            "source_all_returncode_zero": source_result["all_returncode_zero"],
            "circt_all_returncode_zero": circt_result["all_returncode_zero"],
            "source_all_mismatch_zero": source_result["all_mismatch_zero"],
            "circt_all_mismatch_zero": circt_result["all_mismatch_zero"],
        }
        summary_rows.append(summary)
        for backend_result in (source_result, circt_result):
            detailed_rows.append(
                {
                    "case_name": case_name,
                    "backend": backend_result["backend"],
                    "nstates": case["nstates"],
                    "gpu_reps": case["gpu_reps"],
                    "cpu_reps": case["cpu_reps"],
                    "sequential_steps": case["sequential_steps"],
                    "gpu_ms_per_rep_median": backend_result["gpu_ms_per_rep_median"],
                    "gpu_ms_per_rep_min": backend_result["gpu_ms_per_rep_min"],
                    "gpu_ms_per_rep_max": backend_result["gpu_ms_per_rep_max"],
                    "cpu_ms_per_rep_median": backend_result["cpu_ms_per_rep_median"],
                    "all_returncode_zero": backend_result["all_returncode_zero"],
                    "all_mismatch_zero": backend_result["all_mismatch_zero"],
                    "all_compact_mismatch_zero": backend_result["all_compact_mismatch_zero"],
                    "compact_identical": summary["compact_identical"],
                    "circt_vs_source_speedup": speedup,
                    "circt_delta_pct_vs_source": delta_pct,
                }
            )

    results = {
        "generated_dir": str(generated_dir),
        "generated_dir_signature": generated_signature,
        "out_dir": str(out_dir),
        "bundle_cache_root": str(bundle_cache_root),
        "repeats": args.repeats,
        "compare_compact": args.compare_compact,
        "init_seed": args.init_seed,
        "cases": cases,
        "bundles": {name: str(path) for name, path in bundles.items()},
        "bundle_infos": {
            name: {
                "bundle_dir": str(info["bundle_dir"]),
                "cache_key": str(info["cache_key"]),
                "cache_hit": bool(info["cache_hit"]),
                "cache_rebuilt": bool(info["cache_rebuilt"]),
                "meta": dict(info["meta"]),
            }
            for name, info in bundle_infos.items()
        },
        "summary_rows": summary_rows,
        "per_case_results": per_case_results,
    }
    json_path = out_dir / "benchmark_results.json"
    csv_path = out_dir / "benchmark_results.csv"
    summary_path = out_dir / "benchmark_summary.md"
    json_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(detailed_rows, csv_path)
    _write_summary(summary_rows, summary_path)

    print(f"json={json_path}")
    print(f"csv={csv_path}")
    print(f"summary={summary_path}")
    for row in summary_rows:
        speedup = row["circt_vs_source_speedup"]
        delta_pct = row["circt_delta_pct_vs_source"]
        compact = row["compact_identical"]
        if speedup is None or delta_pct is None:
            speedup_text = "n/a"
        else:
            speedup_text = f"{speedup:.3f}x ({delta_pct:+.1f}%)"
        print(
            "case={case_name} source_gpu={source:.6f} circt_gpu={circt:.6f} "
            "circt_vs_source={speedup} compact_identical={compact}".format(
                case_name=row["case_name"],
                source=row["source_gpu_ms_per_rep_median"],
                circt=row["circt_gpu_ms_per_rep_median"],
                speedup=speedup_text,
                compact=compact,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
