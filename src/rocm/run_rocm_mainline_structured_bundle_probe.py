#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_JSON = SCRIPT_DIR / "rocm_mainline_structured_bundle_probe.json"
DEFAULT_MD = SCRIPT_DIR / "rocm_mainline_structured_bundle_probe.md"
DEFAULT_BATCH_JSON = (
    SCRIPT_DIR / "shards" / "shard_0007" / "case_7175" / "batch.json"
)
DEFAULT_HISTORICAL_SUMMARY = (
    SCRIPT_DIR / "shards" / "shard_0007" / "case_7175" / "gpu_summary.json"
)
DEFAULT_SINGLE_CLUSTER_DIR = Path("/tmp/rocm_tlul_fifo_sync_shard_case7175_single_cluster_v2")
DEFAULT_SINGLE_PARTITION_DIR = Path("/tmp/rocm_tlul_fifo_sync_shard_case7175_single_partition_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize the OpenTitan structured-bundle ROCm probe that replays a "
            "historically structured shard case through the mainline bundle path."
        )
    )
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--batch-json", type=Path, default=DEFAULT_BATCH_JSON)
    parser.add_argument("--historical-summary", type=Path, default=DEFAULT_HISTORICAL_SUMMARY)
    parser.add_argument("--single-cluster-dir", type=Path, default=DEFAULT_SINGLE_CLUSTER_DIR)
    parser.add_argument("--single-partition-dir", type=Path, default=DEFAULT_SINGLE_PARTITION_DIR)
    return parser.parse_args()


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _probe_run(run_dir: Path) -> dict[str, Any]:
    summary_path = run_dir / "summary.json"
    baseline_path = run_dir / "baseline_stdout.log"
    summary = _load_optional_json(summary_path)
    baseline = _read_text(baseline_path)
    invalid_cluster = "Invalid --hybrid-cluster-index" in baseline and "cluster_count=0" in baseline
    invalid_partition = "Invalid --hybrid-partition-index" in baseline and "partition_count=0" in baseline
    metrics = dict(summary.get("metrics") or {})
    collector_status = dict(((summary.get("collector") or {}).get("status") or {}))
    return {
        "run_dir": str(run_dir),
        "summary_path": str(summary_path),
        "baseline_stdout_path": str(baseline_path),
        "summary_exists": summary_path.is_file(),
        "summary": summary,
        "hybrid_mode": metrics.get("hybrid_mode"),
        "kernel_partitions": metrics.get("kernel_partitions"),
        "kernel_clusters": metrics.get("kernel_clusters"),
        "hybrid_mismatch": metrics.get("hybrid_mismatch"),
        "mismatch": collector_status.get("mismatch"),
        "compact_mismatch": collector_status.get("compact_mismatch"),
        "invalid_cluster_count_zero": invalid_cluster,
        "invalid_partition_count_zero": invalid_partition,
        "baseline_excerpt": baseline.strip().splitlines()[-1] if baseline.strip() else "",
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    historical = dict(payload.get("historical_structured_case") or {})
    cluster = dict(payload.get("single_cluster_probe") or {})
    partition = dict(payload.get("single_partition_probe") or {})
    lines = [
        "# ROCm Mainline Structured Bundle Probe",
        "",
        f"- status: `{'pass' if payload.get('pass') else 'fail'}`",
        f"- next_blocker: `{payload.get('next_blocker')}`",
        f"- batch_json: `{payload.get('batch_json')}`",
        f"- historical_kernel_partitions: `{historical.get('kernel_partitions')}`",
        f"- historical_kernel_clusters: `{historical.get('kernel_clusters')}`",
        f"- single_cluster_invalid_zero: `{cluster.get('invalid_cluster_count_zero')}`",
        f"- single_partition_invalid_zero: `{partition.get('invalid_partition_count_zero')}`",
        "",
        "## Evidence",
        "",
        f"- [summary.json]({path.with_suffix('.json')})",
        f"- [historical gpu_summary]({payload['paths']['historical_summary']})",
        f"- [single-cluster baseline_stdout]({payload['paths']['single_cluster_baseline_stdout']})",
        f"- [single-partition baseline_stdout]({payload['paths']['single_partition_baseline_stdout']})",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    historical_summary = _load_optional_json(args.historical_summary)
    historical_metrics = dict(historical_summary.get("metrics") or {})
    if not historical_metrics:
        historical_metrics = dict(((historical_summary.get("sim_accel") or {}).get("metrics") or {}))
    if not historical_metrics:
        historical_metrics = dict(((historical_summary.get("collector") or {}).get("metrics") or {}))
    historical = {
        "target": historical_summary.get("target"),
        "kernel_partitions": historical_metrics.get("kernel_partitions"),
        "kernel_clusters": historical_metrics.get("kernel_clusters"),
        "hybrid_mode": historical_metrics.get("hybrid_mode"),
        "mismatch": historical_summary.get("status", {}).get("mismatch"),
        "compact_mismatch": historical_summary.get("status", {}).get("compact_mismatch"),
    }
    cluster_probe = _probe_run(args.single_cluster_dir)
    partition_probe = _probe_run(args.single_partition_dir)

    next_blocker = "review_mainline_structured_bundle_probe"
    if cluster_probe.get("invalid_cluster_count_zero") and partition_probe.get("invalid_partition_count_zero"):
        next_blocker = "structured_bundle_generation_missing_for_mainline_second_wave"

    payload = {
        "schema_version": "rocm-mainline-structured-bundle-probe-v1",
        "pass": False,
        "next_blocker": next_blocker,
        "batch_json": str(args.batch_json),
        "historical_structured_case": historical,
        "single_cluster_probe": cluster_probe,
        "single_partition_probe": partition_probe,
        "paths": {
            "historical_summary": str(args.historical_summary),
            "single_cluster_baseline_stdout": str(args.single_cluster_dir / "baseline_stdout.log"),
            "single_partition_baseline_stdout": str(args.single_partition_dir / "baseline_stdout.log"),
        },
    }
    args.summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_md(args.summary_md, payload)
    print(args.summary_json)
    print(args.summary_md)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
