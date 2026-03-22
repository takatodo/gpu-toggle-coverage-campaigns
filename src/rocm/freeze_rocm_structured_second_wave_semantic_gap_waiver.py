#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_WORK_DIR = Path("/tmp/freeze_rocm_structured_second_wave_semantic_gap_waiver")
CLUSTER = DEFAULT_WORK_DIR / "rocm_mainline_runner_single_cluster_smoke.json"
PARTITION = DEFAULT_WORK_DIR / "rocm_mainline_runner_single_partition_smoke.json"
JSON_OUT = DEFAULT_WORK_DIR / "rocm_structured_second_wave_semantic_gap_waiver.json"
MD_OUT = DEFAULT_WORK_DIR / "rocm_structured_second_wave_semantic_gap_waiver.md"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_case(summary: dict[str, Any], mode: str) -> dict[str, Any]:
    runner_summary = dict(summary.get("runner_summary") or {})
    collector_status = dict(((runner_summary.get("collector") or {}).get("status") or {}))
    metrics = dict(runner_summary.get("metrics") or {})
    structured_gap = dict(runner_summary.get("structured_semantic_gap") or {})
    baseline_metrics = dict(summary.get("baseline_metrics") or {})
    return {
        "hybrid_mode": mode,
        "pass": bool(summary.get("pass")),
        "next_blocker": str(summary.get("next_blocker") or ""),
        "semantic_gap_classification": str(summary.get("semantic_gap_classification") or ""),
        "structured_semantic_gap": structured_gap,
        "aggregate_pass": collector_status.get("aggregate_pass"),
        "mismatch": collector_status.get("mismatch"),
        "compact_mismatch": collector_status.get("compact_mismatch"),
        "cpu_reference_checked": collector_status.get("cpu_reference_checked"),
        "hybrid_mismatch": metrics.get("hybrid_mismatch"),
        "runtime_gpu_api": metrics.get("runtime_gpu_api") or baseline_metrics.get("runtime_gpu_api"),
        "runtime_gpu_device_name": metrics.get("runtime_gpu_device_name")
        or baseline_metrics.get("runtime_gpu_device_name"),
        "runtime_gpu_arch_name": metrics.get("runtime_gpu_arch_name")
        or baseline_metrics.get("runtime_gpu_arch_name"),
        "hybrid_first_state": baseline_metrics.get("hybrid_first_state"),
        "hybrid_first_var": baseline_metrics.get("hybrid_first_var"),
        "hybrid_first_expected": baseline_metrics.get("hybrid_first_expected"),
        "hybrid_first_actual": baseline_metrics.get("hybrid_first_actual"),
        "runner_summary_path": str(summary.get("paths", {}).get("runner_summary") or ""),
        "bench_log_path": str(summary.get("paths", {}).get("bench_log") or ""),
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    cluster = payload["cases"]["single_cluster"]
    partition = payload["cases"]["single_partition"]
    lines = [
        "# ROCm Structured Second-Wave Semantic Gap Waiver",
        "",
        f"- waiver_canonicalized: `{payload['waiver_canonicalized']}`",
        f"- target: `{payload['target']}`",
        f"- next_blocker: `{payload['next_blocker']}`",
        f"- root_cause: `{payload['generated_semantic_gap']['root_cause']}`",
        "",
        "## Acceptance Rule",
        "",
        "- Accept the structured second-wave proof for this target only when:",
        "  - `aggregate_pass=true`",
        "  - `mismatch=0`",
        "  - `compact_mismatch=0`",
        "  - `structured_semantic_gap.soft_accepted=true`",
        "  - the first divergent variable remains the known `seq commit` gap",
        "",
        "## Single-Cluster",
        "",
        f"- pass: `{cluster['pass']}`",
        f"- hybrid_mismatch: `{cluster['hybrid_mismatch']}`",
        f"- runtime_gpu_api: `{cluster['runtime_gpu_api']}`",
        f"- runtime_gpu_device_name: `{cluster['runtime_gpu_device_name']}`",
        f"- first_diff: `state={cluster['hybrid_first_state']} var={cluster['hybrid_first_var']} expected={cluster['hybrid_first_expected']} actual={cluster['hybrid_first_actual']}`",
        f"- [runner summary]({cluster['runner_summary_path']})",
        f"- [bench log]({cluster['bench_log_path']})",
        "",
        "## Single-Partition",
        "",
        f"- pass: `{partition['pass']}`",
        f"- hybrid_mismatch: `{partition['hybrid_mismatch']}`",
        f"- runtime_gpu_api: `{partition['runtime_gpu_api']}`",
        f"- runtime_gpu_device_name: `{partition['runtime_gpu_device_name']}`",
        f"- first_diff: `state={partition['hybrid_first_state']} var={partition['hybrid_first_var']} expected={partition['hybrid_first_expected']} actual={partition['hybrid_first_actual']}`",
        f"- [runner summary]({partition['runner_summary_path']})",
        f"- [bench log]({partition['bench_log_path']})",
        "",
        "## Evidence",
        "",
        f"- [cluster smoke]({CLUSTER})",
        f"- [partition smoke]({PARTITION})",
        f"- [waiver json]({JSON_OUT})",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    cluster_summary = _load_json(CLUSTER)
    partition_summary = _load_json(PARTITION)
    cluster = _extract_case(cluster_summary, "single-cluster")
    partition = _extract_case(partition_summary, "single-partition")
    waiver_canonicalized = all(
        [
            cluster["pass"],
            partition["pass"],
            bool(cluster["structured_semantic_gap"].get("soft_accepted")),
            bool(partition["structured_semantic_gap"].get("soft_accepted")),
            cluster["mismatch"] == 0,
            cluster["compact_mismatch"] == 0,
            partition["mismatch"] == 0,
            partition["compact_mismatch"] == 0,
            cluster["hybrid_first_var"] == 1,
            partition["hybrid_first_var"] == 1,
        ]
    )
    payload = {
        "schema_version": "rocm-structured-second-wave-semantic-gap-waiver-v1",
        "target": "OpenTitan.tlul_fifo_sync",
        "waiver_canonicalized": waiver_canonicalized,
        "generated_semantic_gap": {
            "classification": "structured_interface_missing_seq_commit",
            "root_cause": "exported structured interface has no seq-partition commit and leaves cycle_count_q divergent",
            "known_first_divergent_state": 0,
            "known_first_divergent_var": 1,
            "applies_to_hybrid_modes": ["single-cluster", "single-partition"],
        },
        "acceptance_rule": {
            "aggregate_pass_required": True,
            "mismatch_must_be_zero": True,
            "compact_mismatch_must_be_zero": True,
            "structured_semantic_gap_soft_accepted_required": True,
            "known_first_divergent_var": 1,
        },
        "cases": {
            "single_cluster": cluster,
            "single_partition": partition,
        },
        "next_blocker": (
            "promote_true_hsaco_mainline"
            if waiver_canonicalized
            else "canonicalize_structured_second_wave_semantic_gap_waiver"
        ),
    }
    JSON_OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_md(MD_OUT, payload)
    print(JSON_OUT)
    print(MD_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
