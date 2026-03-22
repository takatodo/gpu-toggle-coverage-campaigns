#!/usr/bin/env python3
from __future__ import annotations

import argparse
from bisect import bisect_left
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import json
from collections import deque
import heapq
import math
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
REPO_SCRIPTS = ROOT_DIR / "src/scripts"
GPU_SWEEP_RUNNER = SCRIPT_DIR / "run_opentitan_tlul_slice_trace_gpu_sweep.py"

for path in (str(REPO_SCRIPTS),):
    if path not in sys.path:
        sys.path.insert(0, path)

from opentitan_tlul_trace_search_common import (  # noqa: E402
    TRACE_VARIANTS,
    score_prefilter_case as _score_prefilter_case_common,
)
from opentitan_tlul_slice_benchmark_profiles import (  # noqa: E402
    DEFAULT_FREEZE_JSON,
    load_benchmark_freeze,
    resolve_slice_profile,
)
from opentitan_tlul_slice_search_tuning import resolve_slice_search_tuning  # noqa: E402
from gpu_runtime_batch_policy import apply_runtime_batch_policy  # noqa: E402
from search_scope_runtime_policy import apply_search_scope_runtime_policy  # noqa: E402


_PREFILTER_SCORE_KEY = "_prefilter_score"
_INIT_FILE_METRIC_INT_FIELDS = (
    "global_line_count",
    "per_state_override_line_count",
    "per_state_override_state_count",
    "range_override_line_count",
    "range_override_state_count",
    "seed_override_line_count",
    "seed_override_state_count",
    "non_seed_override_line_count",
    "non_seed_override_state_count",
    "explicit_state_count",
    "packed_case_count",
    "driver_signal_count",
    "total_line_count",
    "naive_full_override_line_estimate",
    "line_reduction_vs_naive",
)

_TRAFFIC_COUNTER_KEYS = (
    "host_req_accepted_o",
    "device_req_accepted_o",
    "device_rsp_accepted_o",
    "host_rsp_accepted_o",
)


def _traffic_metric(case_summary: dict[str, Any], key: str) -> int:
    if case_summary.get(key) is not None:
        return int(case_summary.get(key) or 0)
    traffic = case_summary.get("traffic_counters") or {}
    return int(traffic.get(key) or 0)


def _trace_progress_metric(case_summary: dict[str, Any], key: str) -> int:
    if case_summary.get(key) is not None:
        return int(case_summary.get(key) or 0)
    trace_progress = case_summary.get("trace_progress") or {}
    return int(trace_progress.get(key) or 0)


def _execution_gate_values(case_summary: dict[str, Any]) -> dict[str, int]:
    progress_cycle_count = _trace_progress_metric(case_summary, "progress_cycle_count_o")
    debug_phase = _trace_progress_metric(case_summary, "debug_phase_o")
    debug_trace_live = _trace_progress_metric(case_summary, "debug_trace_live_o")
    debug_trace_req_active = _trace_progress_metric(case_summary, "debug_trace_req_active_o")
    explicit_accepted = case_summary.get("accepted_traffic_sum")
    if explicit_accepted is not None:
        accepted_traffic_sum = int(explicit_accepted or 0)
    else:
        accepted_traffic_sum = sum(_traffic_metric(case_summary, key) for key in _TRAFFIC_COUNTER_KEYS)
    return {
        "execution_has_handshake": int(accepted_traffic_sum > 0),
        "execution_progressed": int(progress_cycle_count > 0),
        "execution_left_reset": int((debug_phase & 0x7) != 0),
        "execution_live": int(
            debug_trace_live > 0 or debug_trace_req_active > 0 or progress_cycle_count > 0
        ),
        "accepted_traffic_sum": int(accepted_traffic_sum),
    }


def _scale_topk_value(value: int, scale: float) -> int:
    base = int(value)
    if base <= 0:
        return 0
    quantum = max(1, min(base, 4))
    scaled = max(1, int(round(base * float(scale))))
    return max(1, int(math.ceil(scaled / float(quantum))) * quantum)


def _normalize_region_budget(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, int] = {}
    for region, quota in raw.items():
        region_name = str(region or "").strip()
        if not region_name:
            continue
        quota_int = int(quota or 0)
        if quota_int <= 0:
            continue
        normalized[region_name] = quota_int
    return normalized


def _parse_region_budget_arg(raw: str) -> dict[str, int]:
    text = str(raw or "").strip()
    if not text:
        return {}
    candidate_path = Path(text).expanduser()
    if candidate_path.exists():
        return _normalize_region_budget(json.loads(candidate_path.read_text(encoding="utf-8")))
    return _normalize_region_budget(json.loads(text))


def _default_region_budget(cases: list[dict[str, Any]]) -> dict[str, int]:
    regions = sorted({str(case.get("target_region") or "") for case in cases if str(case.get("target_region") or "")})
    return {region: 1 for region in regions}


def _region_budget_cases(cases: list[dict[str, Any]], region_budget: dict[str, int]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_case_index: set[int] = set()
    for region, quota in sorted(region_budget.items()):
        if int(quota) <= 0:
            continue
        region_cases = [case for case in cases if str(case.get("target_region") or "") == region]
        for case in heapq.nlargest(int(quota), region_cases, key=score_prefilter_case):
            case_index = int(case["case_index"])
            if case_index in seen_case_index:
                continue
            selected.append(case)
            seen_case_index.add(case_index)
    return selected


def score_prefilter_case(case_summary: dict[str, Any]) -> tuple[Any, ...]:
    cached = case_summary.get(_PREFILTER_SCORE_KEY)
    if cached is not None:
        return cached
    execution_gate = _execution_gate_values(case_summary)
    precomputed = case_summary.get("prefilter_score")
    if precomputed is not None:
        score = tuple(precomputed)
        if len(score) < 14:
            score = (
                execution_gate["execution_has_handshake"],
                execution_gate["execution_progressed"],
                execution_gate["execution_left_reset"],
                execution_gate["execution_live"],
                execution_gate["accepted_traffic_sum"],
                *score,
            )
        case_summary[_PREFILTER_SCORE_KEY] = score
        return score
    score = (
        execution_gate["execution_has_handshake"],
        execution_gate["execution_progressed"],
        execution_gate["execution_left_reset"],
        execution_gate["execution_live"],
        execution_gate["accepted_traffic_sum"],
        *_score_prefilter_case_common(case_summary),
    )
    case_summary[_PREFILTER_SCORE_KEY] = score
    return score


def rank_prefilter_cases(
    cases: list[dict[str, Any]],
    keep_top_k: int,
    region_budget: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    effective_region_budget = _normalize_region_budget(region_budget)
    if not effective_region_budget:
        effective_region_budget = _default_region_budget(cases)
    if keep_top_k <= 0 and not effective_region_budget:
        return sorted(cases, key=score_prefilter_case, reverse=True)

    selected = list(heapq.nlargest(max(0, keep_top_k), cases, key=score_prefilter_case))
    seen_case_index = {int(case["case_index"]) for case in selected}
    for region_case in _region_budget_cases(cases, effective_region_budget):
        case_index_int = int(region_case["case_index"])
        if case_index_int in seen_case_index:
            continue
        selected.append(region_case)
        seen_case_index.add(case_index_int)
    return sorted(selected, key=score_prefilter_case, reverse=True)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_init_file_metrics(raw: Any) -> dict[str, Any]:
    payload = dict(raw or {})
    normalized = {
        field: int(payload.get(field) or 0)
        for field in _INIT_FILE_METRIC_INT_FIELDS
    }
    normalized["uniform_states"] = bool(payload.get("uniform_states"))
    total_line_count = int(normalized["total_line_count"])
    naive_line_estimate = int(normalized["naive_full_override_line_estimate"])
    normalized["compression_ratio_vs_naive"] = (
        float(naive_line_estimate) / float(total_line_count)
        if total_line_count > 0
        else 1.0
    )
    normalized["compression_savings_fraction"] = (
        float(normalized["line_reduction_vs_naive"]) / float(naive_line_estimate)
        if naive_line_estimate > 0
        else 0.0
    )
    return normalized


def _merge_launch_generation_rollups(rollups: list[dict[str, Any]]) -> dict[str, Any]:
    if not rollups:
        return {
            "launch_count": 0,
            "bundle_cache_hit_count": 0,
            "bundle_cache_hit_rate": 0.0,
            "init_file_metrics": _normalize_init_file_metrics({}),
        }
    launch_count = 0
    bundle_cache_hit_count = 0
    init_totals = {field: 0 for field in _INIT_FILE_METRIC_INT_FIELDS}
    for rollup in rollups:
        launch_count += int(rollup.get("launch_count") or 0)
        bundle_cache_hit_count += int(rollup.get("bundle_cache_hit_count") or 0)
        init_metrics = _normalize_init_file_metrics((rollup.get("init_file_metrics") or {}))
        for field in _INIT_FILE_METRIC_INT_FIELDS:
            init_totals[field] += int(init_metrics.get(field) or 0)
    return {
        "launch_count": launch_count,
        "bundle_cache_hit_count": bundle_cache_hit_count,
        "bundle_cache_hit_rate": (
            float(bundle_cache_hit_count) / float(launch_count)
            if launch_count > 0
            else 0.0
        ),
        "init_file_metrics": _normalize_init_file_metrics(init_totals),
    }


def _merge_best_cases_by_target_region(
    best_by_region: dict[str, dict[str, Any]],
    cases: list[dict[str, Any]],
) -> None:
    for case in cases:
        region = str(case.get("target_region") or "")
        if not region:
            continue
        current = best_by_region.get(region)
        if current is None or score_prefilter_case(case) > score_prefilter_case(current):
            best_by_region[region] = case


def _update_incremental_topk(
    current_topk: list[dict[str, Any]],
    new_cases: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return list(current_topk) + list(new_cases)
    if not current_topk:
        return list(heapq.nlargest(limit, new_cases, key=score_prefilter_case))
    return list(heapq.nlargest(limit, list(current_topk) + list(new_cases), key=score_prefilter_case))


def _selected_prefilter_cases(
    topk_cases: list[dict[str, Any]],
    best_by_region: dict[str, dict[str, Any]],
    region_budget: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    selected = list(topk_cases)
    seen_case_index = {
        int(case["case_index"]) for case in selected if case.get("case_index") is not None
    }
    effective_region_budget = _normalize_region_budget(region_budget)
    if not effective_region_budget:
        effective_region_budget = {region: 1 for region in best_by_region}
    for region_case in _region_budget_cases(list(best_by_region.values()), effective_region_budget):
        case_index = region_case.get("case_index")
        if case_index is None:
            continue
        case_index_int = int(case_index)
        if case_index_int in seen_case_index:
            continue
        selected.append(region_case)
        seen_case_index.add(case_index_int)
    return sorted(selected, key=score_prefilter_case, reverse=True)


def _selected_case_index_set(
    topk_cases: list[dict[str, Any]],
    best_by_region: dict[str, dict[str, Any]],
    region_budget: dict[str, int] | None = None,
) -> set[int]:
    selected = {int(case["case_index"]) for case in topk_cases if case.get("case_index") is not None}
    effective_region_budget = _normalize_region_budget(region_budget)
    if not effective_region_budget:
        effective_region_budget = {region: 1 for region in best_by_region}
    for region_case in _region_budget_cases(list(best_by_region.values()), effective_region_budget):
        case_index = region_case.get("case_index")
        if case_index is not None:
            selected.add(int(case_index))
    return selected


def _template_work_dir(template: dict[str, Any]) -> Path:
    template_args = dict(template.get("runner_args_template") or {})
    default = template_args.get("work_dir") or (SCRIPT_DIR / "slice_pilots" / template["slice_name"])
    return Path(str(default)).expanduser().resolve()


def _template_int(template: dict[str, Any], key: str, fallback: int) -> int:
    template_args = dict(template.get("runner_args_template") or {})
    value = template_args.get(key)
    if value is None:
        return int(fallback)
    return int(value)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare and optionally run a sharded TL-UL slice GPU sweep campaign."
    )
    parser.add_argument("--launch-template", required=True)
    parser.add_argument("--work-dir", default="")
    parser.add_argument("--candidate-count", type=int, default=0)
    parser.add_argument("--cases", type=int, default=0)
    parser.add_argument("--variants-per-case", type=int, default=0)
    parser.add_argument("--seed-fanout", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=0)
    parser.add_argument("--keep-top-k-per-shard", type=int, default=0)
    parser.add_argument("--global-top-k", type=int, default=0)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--trace-length", type=int, default=0)
    parser.add_argument("--batch-length", type=int, default=0)
    parser.add_argument("--profile-family", default="")
    parser.add_argument("--region-budget-json", default="")
    parser.add_argument("--gpu-sequential-steps", type=int, default=0)
    parser.add_argument("--gpu-nstates", type=int, default=0)
    parser.add_argument("--states-per-case", type=int, default=0)
    parser.add_argument("--cases-per-launch", type=int, default=0)
    parser.add_argument("--gpu-reps", type=int, default=0)
    parser.add_argument("--cpu-reps", type=int, default=0)
    parser.add_argument("--benchmark-freeze-json", default=str(DEFAULT_FREEZE_JSON))
    parser.add_argument(
        "--profile-scenario",
        choices=("auto", "single_step_small", "multi_step_medium"),
        default="auto",
    )
    parser.add_argument("--execution-engine", choices=("gpu", "cpu"), default="gpu")
    parser.add_argument(
        "--gpu-runtime-policy",
        choices=("auto", "off"),
        default="off",
        help="Optionally scale candidate/state batching from the direct campaign runner using detected GPU memory tier.",
    )
    parser.add_argument(
        "--gpu-memory-total-mib",
        type=int,
        default=0,
        help="Override detected GPU memory for direct-run batching policy validation.",
    )
    parser.add_argument(
        "--search-scope-policy",
        choices=("auto", "off"),
        default="auto",
        help="Shape campaign candidate budget from the evaluated search-scope estimator.",
    )
    parser.add_argument(
        "--search-scope-json",
        default=str(ROOT_DIR / "config/opentitan_tlul_search_scope_estimate.json"),
    )
    parser.add_argument(
        "--search-scope-graph-json",
        default=str(ROOT_DIR / "config/opentitan_tlul_search_scope_graph.json"),
    )
    parser.add_argument("--launch-backend", choices=("auto", "source", "circt-cubin"), default="auto")
    parser.add_argument("--generated-dir-cache-root", default="/tmp/opentitan_tlul_slice_generated_dir_cache")
    parser.add_argument("--dead-word-bias", action="store_true", default=None)
    parser.add_argument("--uniform-states", action="store_true", default=None)
    parser.add_argument("--cleanup-non-topk", action="store_true")
    parser.add_argument("--rebuild-first", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--run-local", action="store_true")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--merge-only", action="store_true")
    parser.add_argument("--convergence-min-new-regions-per-1k", type=float, default=0.05)
    parser.add_argument("--convergence-min-hit-gain-per-1k", type=float, default=0.25)
    parser.add_argument("--convergence-max-topk-churn", type=float, default=0.20)
    parser.add_argument("--convergence-min-completed-shards", type=int, default=4)
    parser.add_argument("--convergence-stable-shards", type=int, default=3)
    parser.add_argument("--json-out", default="")
    return parser.parse_args(argv)


def _bool_with_template(cli_value: bool | None, template_value: Any) -> bool:
    if cli_value is None:
        return bool(template_value)
    return bool(cli_value)


def _derived_case_count(ns: argparse.Namespace) -> int:
    if int(ns.cases) > 0:
        return int(ns.cases)
    variants_per_case = max(1, int(ns.variants_per_case))
    seed_fanout = max(1, int(ns.seed_fanout))
    candidate_count = max(1, int(ns.candidate_count))
    return max(1, math.ceil(candidate_count / (variants_per_case * seed_fanout)))


def _summary_path_for(work_dir: Path, shard_index: int) -> Path:
    return work_dir / "shards" / f"shard_{shard_index:04d}" / "summary.json"


def _campaign_merge_view_path_for(work_dir: Path, shard_index: int) -> Path:
    return work_dir / "shards" / f"shard_{shard_index:04d}" / "summary.campaign_merge_view.json"


def _jsonl_path_for(work_dir: Path, shard_index: int) -> Path:
    return work_dir / "shards" / f"shard_{shard_index:04d}" / "cases.jsonl"


def _log_path_for(work_dir: Path, shard_index: int) -> Path:
    return work_dir / "logs" / f"shard_{shard_index:04d}.log"


def build_shard_command(
    ns: argparse.Namespace,
    work_dir: Path,
    total_cases: int,
    shard_index: int,
) -> list[str]:
    shard_work_dir = _summary_path_for(work_dir, shard_index).parent
    cmd = [
        "python3",
        str(GPU_SWEEP_RUNNER),
        "--launch-template",
        str(ns.launch_template),
        "--phase",
        "campaign",
        "--launch-backend",
        str(ns.launch_backend),
        "--generated-dir-cache-root",
        str(Path(ns.generated_dir_cache_root).expanduser().resolve()),
        "--work-dir",
        str(shard_work_dir),
        "--cases",
        str(total_cases),
        "--variants-per-case",
        str(ns.variants_per_case),
        "--seed-fanout",
        str(ns.seed_fanout),
        "--seed-start",
        str(ns.seed_start),
        "--shard-count",
        str(ns.shard_count),
        "--shard-index",
        str(shard_index),
        "--keep-top-k",
        str(ns.keep_top_k_per_shard),
        "--json-out",
        str(_summary_path_for(work_dir, shard_index)),
        "--trace-length",
        str(ns.trace_length),
        "--batch-length",
        str(ns.batch_length),
        "--profile-family",
        str(ns.profile_family),
        "--region-budget-json",
        json.dumps(dict(ns.region_budget), sort_keys=True),
        "--gpu-sequential-steps",
        str(ns.gpu_sequential_steps),
        "--gpu-nstates",
        str(ns.gpu_nstates),
        "--states-per-case",
        str(ns.states_per_case),
        "--cases-per-launch",
        str(int(ns.cases_per_launch) or max(1, int(ns.gpu_nstates) // max(1, int(ns.states_per_case)))),
        "--gpu-reps",
        str(ns.gpu_reps),
        "--cpu-reps",
        str(ns.cpu_reps),
        "--benchmark-freeze-json",
        str(Path(ns.benchmark_freeze_json).expanduser().resolve()),
        "--profile-scenario",
        str(ns.profile_scenario),
        "--execution-engine",
        str(ns.execution_engine),
        "--gpu-runtime-policy",
        "off",
        "--search-scope-policy",
        "off",
    ]
    if ns.dead_word_bias:
        cmd.append("--dead-word-bias")
    if ns.uniform_states:
        cmd.append("--uniform-states")
    if ns.cleanup_non_topk:
        cmd.append("--cleanup-non-topk")
    if ns.rebuild_first and shard_index == 0:
        cmd.append("--rebuild-first")
    return cmd


def write_launch_artifacts(ns: argparse.Namespace, work_dir: Path, total_cases: int) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "shards").mkdir(parents=True, exist_ok=True)
    (work_dir / "logs").mkdir(parents=True, exist_ok=True)

    shard_plans: list[dict[str, Any]] = []
    commands_txt = work_dir / "shard_commands.txt"
    launch_script = work_dir / "launch_shards.sh"
    with commands_txt.open("w", encoding="utf-8") as commands_handle:
        for shard_index in range(int(ns.shard_count)):
            cmd = build_shard_command(ns, work_dir, total_cases, shard_index)
            log_path = _log_path_for(work_dir, shard_index)
            shard_plans.append(
                {
                    "shard_index": shard_index,
                    "summary_json": str(_summary_path_for(work_dir, shard_index)),
                    "campaign_merge_view_json": str(_campaign_merge_view_path_for(work_dir, shard_index)),
                    "cases_jsonl": "",
                    "log_path": str(log_path),
                    "command": cmd,
                    "command_shell": shlex.join(cmd),
                }
            )
            commands_handle.write(shlex.join(cmd) + "\n")

    launch_lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f"WORK_DIR={shlex.quote(str(work_dir))}",
        'MAX_PARALLEL="${MAX_PARALLEL:-1}"',
        "mkdir -p \"$WORK_DIR/logs\"",
        "declare -a pids=()",
        "wait_one() {",
        "  local pid=\"$1\"",
        "  wait \"$pid\"",
        "}",
    ]
    for shard_plan in shard_plans:
        launch_lines.extend(
            [
                "while [ \"${#pids[@]}\" -ge \"$MAX_PARALLEL\" ]; do wait_one \"${pids[0]}\"; pids=(\"${pids[@]:1}\"); done",
                f"cd {shlex.quote(str(SCRIPT_DIR))} && {shard_plan['command_shell']} > {shlex.quote(shard_plan['log_path'])} 2>&1 &",
                "pids+=(\"$!\")",
            ]
        )
    launch_lines.append("for pid in \"${pids[@]}\"; do wait \"$pid\"; done")
    launch_script.write_text("\n".join(launch_lines) + "\n", encoding="utf-8")
    launch_script.chmod(0o755)

    candidate_space = (
        total_cases
        * max(1, int(ns.variants_per_case))
        * max(1, int(ns.seed_fanout))
    )
    manifest = {
        "target": ns.target,
        "slice_name": ns.slice_name,
        "launch_template": str(ns.launch_template),
        "benchmark_profile": getattr(ns, "benchmark_profile", None),
        "gpu_runtime_policy": getattr(ns, "gpu_runtime_policy_payload", {}),
        "search_scope_policy": getattr(ns, "search_scope_policy_payload", {}),
        "effective_search_defaults": dict(getattr(ns, "effective_search_defaults_payload", {})),
        "status": "prepared",
        "candidate_count_requested": int(ns.candidate_count),
        "cases": total_cases,
        "variants_per_case": int(ns.variants_per_case),
        "seed_fanout": int(ns.seed_fanout),
        "candidate_space_prepared": candidate_space,
        "shard_count": int(ns.shard_count),
        "keep_top_k_per_shard": int(ns.keep_top_k_per_shard),
        "global_top_k": int(ns.global_top_k),
        "seed_start": int(ns.seed_start),
        "trace_length": int(ns.trace_length),
        "batch_length": int(ns.batch_length),
        "profile_family": str(ns.profile_family),
        "region_budget": dict(ns.region_budget),
        "gpu_sequential_steps": int(ns.gpu_sequential_steps),
        "gpu_nstates": int(ns.gpu_nstates),
        "states_per_case": int(ns.states_per_case),
        "cases_per_launch": int(ns.cases_per_launch) or max(1, int(ns.gpu_nstates) // max(1, int(ns.states_per_case))),
        "gpu_reps": int(ns.gpu_reps),
        "cpu_reps": int(ns.cpu_reps),
        "dead_word_bias": bool(ns.dead_word_bias),
        "uniform_states": bool(ns.uniform_states),
        "cleanup_non_topk": bool(ns.cleanup_non_topk),
        "rebuild_first": bool(ns.rebuild_first),
        "convergence_min_new_regions_per_1k": float(ns.convergence_min_new_regions_per_1k),
        "convergence_min_hit_gain_per_1k": float(ns.convergence_min_hit_gain_per_1k),
        "convergence_max_topk_churn": float(ns.convergence_max_topk_churn),
        "convergence_min_completed_shards": int(ns.convergence_min_completed_shards),
        "convergence_stable_shards": int(ns.convergence_stable_shards),
        "commands_txt": str(commands_txt),
        "launch_script": str(launch_script),
        "shards": shard_plans,
    }
    manifest_path = work_dir / "campaign_manifest.json"
    manifest["campaign_manifest"] = str(manifest_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def run_shards_locally(
    manifest: dict[str, Any],
    max_workers: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    shard_plans = list(manifest.get("shards") or [])
    if not shard_plans:
        return (
            {
                "mode": "local",
                "completed_shard_indices": [],
                "failed_shard_indices": [],
                "early_stop_triggered": False,
                "recommended_stop_at_shard": None,
                "stop_reasons": [],
            },
            [],
        )

    def _run_one(shard_plan: dict[str, Any]) -> None:
        log_path = Path(str(shard_plan["log_path"]))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            list(shard_plan["command"]),
            cwd=SCRIPT_DIR,
            text=True,
            capture_output=True,
        )
        log_path.write_text(proc.stdout + proc.stderr, encoding="utf-8")
        if proc.returncode != 0:
            raise RuntimeError(f"shard {shard_plan['shard_index']} failed; see {log_path}")

    pending = deque(sorted(shard_plans, key=lambda item: int(item["shard_index"])))
    in_flight: dict[Any, dict[str, Any]] = {}
    completed: list[dict[str, Any]] = []
    loaded_completed_cache: dict[int, dict[str, Any]] = {}
    loaded_completed_indices: list[int] = []
    convergence_state = _new_convergence_state(
        manifest,
        int(manifest.get("global_top_k") or 0),
    )
    failed: list[int] = []
    early_stop_triggered = False
    recommended_stop_at_shard: int | None = None
    stop_reasons: list[str] = []
    worker_count = max(1, int(max_workers))

    def _maybe_schedule(executor: ThreadPoolExecutor) -> None:
        while pending and len(in_flight) < worker_count and not early_stop_triggered:
            shard_plan = pending.popleft()
            future = executor.submit(_run_one, shard_plan)
            in_flight[future] = shard_plan

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        _maybe_schedule(executor)
        while in_flight:
            done, _ = wait(set(in_flight.keys()), return_when=FIRST_COMPLETED)
            for future in done:
                shard_plan = in_flight.pop(future)
                try:
                    future.result()
                except Exception:
                    failed.append(int(shard_plan["shard_index"]))
                    raise
                completed.append(shard_plan)
                shard_index = int(shard_plan["shard_index"])
                shard_payload, source_path = _load_shard_campaign_payload(shard_plan)
                if shard_payload is not None and source_path is not None:
                    loaded_completed_cache[shard_index] = {
                        "shard_plan": shard_plan,
                        "payload": shard_payload,
                        "source_path": source_path,
                    }
                    insert_at = bisect_left(loaded_completed_indices, shard_index)
                    loaded_completed_indices.insert(insert_at, shard_index)
                    if insert_at == len(loaded_completed_indices) - 1:
                        _advance_convergence_state(
                            convergence_state,
                            shard_plan=shard_plan,
                            shard_payload=shard_payload,
                        )
                    else:
                        convergence_state = _rebuild_convergence_state(
                            manifest=manifest,
                            loaded_completed_cache=loaded_completed_cache,
                            ordered_indices=loaded_completed_indices,
                            global_top_k=int(manifest.get("global_top_k") or 0),
                        )
                    convergence = _convergence_summary_from_state(convergence_state)
                    if bool(convergence.get("recommended_stop")):
                        early_stop_triggered = True
                        recommended_stop_at_shard = convergence.get("recommended_stop_at_shard")
                        stop_reasons = list(convergence.get("stop_reasons") or [])
            if not failed and not early_stop_triggered:
                _maybe_schedule(executor)

    skipped = [int(item["shard_index"]) for item in pending]
    loaded_completed = [
        loaded_completed_cache[index]
        for index in loaded_completed_indices
    ]
    return (
        {
            "mode": "local",
            "completed_shard_indices": [int(item["shard_index"]) for item in completed],
            "failed_shard_indices": failed,
            "skipped_shard_indices": skipped,
            "early_stop_triggered": early_stop_triggered,
            "recommended_stop_at_shard": recommended_stop_at_shard,
            "stop_reasons": stop_reasons,
        },
        loaded_completed,
    )


def merge_shard_summaries(
    manifest: dict[str, Any],
    global_top_k: int,
    execution: dict[str, Any] | None = None,
    preloaded_shards: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    shard_plans = list(manifest.get("shards") or [])
    shard_summaries: list[dict[str, Any]] = []
    merged_cases: list[dict[str, Any]] = []
    merged_topk_cases: list[dict[str, Any]] = []
    best_by_target_region: dict[str, dict[str, Any]] = {}
    convergence_state = _new_convergence_state(manifest, global_top_k)
    evaluated_case_count = 0
    total_candidate_space = 0
    completed_shards = 0
    launch_generation_rollups: list[dict[str, Any]] = []
    if preloaded_shards is None:
        shard_entries: list[dict[str, Any]] = []
        for shard_plan in shard_plans:
            shard_payload, source_path = _load_shard_campaign_payload(shard_plan)
            if shard_payload is None or source_path is None:
                continue
            shard_entries.append(
                {
                    "shard_plan": shard_plan,
                    "payload": shard_payload,
                    "source_path": source_path,
                }
            )
    else:
        shard_entries = sorted(
            list(preloaded_shards),
            key=lambda entry: int(entry["shard_plan"]["shard_index"]),
        )

    for entry in shard_entries:
        shard_plan = entry["shard_plan"]
        shard_payload = entry["payload"]
        source_path = entry["source_path"]
        shard_summaries.append(
            {
                "shard_index": int(shard_plan["shard_index"]),
                "summary_json": str(source_path),
                "cases_jsonl": str(shard_plan["cases_jsonl"]),
                "evaluated_case_count": int(shard_payload.get("evaluated_case_count") or 0),
                "retained_case_count": len(shard_payload.get("cases") or []),
                "best_case": shard_payload.get("best_case"),
                "launch_generation": dict(shard_payload.get("launch_generation") or {}),
            }
        )
        shard_cases = list(shard_payload.get("cases") or [])
        launch_generation_rollups.append(dict(shard_payload.get("launch_generation") or {}))
        if global_top_k > 0:
            merged_topk_cases = _update_incremental_topk(merged_topk_cases, shard_cases, global_top_k)
            _merge_best_cases_by_target_region(best_by_target_region, shard_cases)
        else:
            merged_cases.extend(shard_cases)
        evaluated_case_count += int(shard_payload.get("evaluated_case_count") or 0)
        total_candidate_space += int(shard_payload.get("total_candidate_space") or 0)
        completed_shards += 1
        _advance_convergence_state(
            convergence_state,
            shard_plan=shard_plan,
            shard_payload=shard_payload,
        )

    if global_top_k > 0:
        ranked = _selected_prefilter_cases(
            merged_topk_cases,
            best_by_target_region,
            manifest.get("region_budget"),
        )
        best_by_target_region = {
            region: best_by_target_region[region] for region in sorted(best_by_target_region)
        }
    else:
        ranked = rank_prefilter_cases(
            merged_cases,
            global_top_k,
            manifest.get("region_budget"),
        )
        best_by_target_region = {}
        for case in ranked:
            region = str(case.get("target_region") or "")
            if not region or region in best_by_target_region:
                continue
            best_by_target_region[region] = case

    convergence = _convergence_summary_from_state(convergence_state)

    return {
        "target": manifest.get("target"),
        "slice_name": manifest.get("slice_name"),
        "launch_template": manifest.get("launch_template"),
        "status": "merged",
        "candidate_count_requested": manifest.get("candidate_count_requested"),
        "cases": manifest.get("cases"),
        "variants_per_case": manifest.get("variants_per_case"),
        "seed_fanout": manifest.get("seed_fanout"),
        "total_candidate_space": total_candidate_space or int(manifest.get("candidate_space_prepared") or 0),
        "evaluated_case_count": evaluated_case_count,
        "requested_shard_count": manifest.get("shard_count"),
        "completed_shard_count": completed_shards,
        "keep_top_k_per_shard": manifest.get("keep_top_k_per_shard"),
        "global_top_k": int(global_top_k),
        "cases_per_launch": manifest.get("cases_per_launch"),
        "states_per_case": manifest.get("states_per_case"),
        "shards": shard_summaries,
        "best_case": ranked[0] if ranked else None,
        "best_by_target_region": best_by_target_region,
        "ranked_case_indices": [int(case["case_index"]) for case in ranked],
        "convergence": convergence,
        "execution": dict(execution or {}),
        "launch_generation": _merge_launch_generation_rollups(launch_generation_rollups),
    }


def _active_region_union(cases: list[dict[str, Any]]) -> set[str]:
    active: set[str] = set()
    for case in cases:
        for region in list(case.get("active_regions") or []):
            active.add(str(region))
    return active


def _load_shard_campaign_payload(shard_plan: dict[str, Any]) -> tuple[dict[str, Any] | None, Path | None]:
    merge_view_json = str(shard_plan.get("campaign_merge_view_json") or "").strip()
    summary_path = Path(str(shard_plan["summary_json"]))
    if merge_view_json:
        merge_view_path = Path(merge_view_json)
        if merge_view_path.exists():
            payload = _load_json(merge_view_path)
            if "launch_generation" not in payload and summary_path.exists():
                try:
                    summary_payload = _load_json(summary_path)
                except json.JSONDecodeError:
                    summary_payload = {}
                if isinstance(summary_payload, dict) and "launch_generation" in summary_payload:
                    payload["launch_generation"] = dict(summary_payload.get("launch_generation") or {})
            return payload, merge_view_path
    if summary_path.exists():
        return _load_json(summary_path), summary_path
    return None, None


def _best_hit(cases: list[dict[str, Any]]) -> int:
    if not cases:
        return 0
    return max(int(case.get("real_subset_points_hit") or 0) for case in cases)


def _payload_best_hit(payload: dict[str, Any]) -> int:
    best_case = payload.get("best_case")
    if isinstance(best_case, dict):
        return int(best_case.get("real_subset_points_hit") or 0)
    return _best_hit(list(payload.get("cases") or []))


def _convergence_thresholds(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "min_new_regions_per_1k": float(manifest.get("convergence_min_new_regions_per_1k") or 0.0),
        "min_hit_gain_per_1k": float(manifest.get("convergence_min_hit_gain_per_1k") or 0.0),
        "max_topk_churn": float(manifest.get("convergence_max_topk_churn") or 0.0),
        "min_completed_shards": int(manifest.get("convergence_min_completed_shards") or 0),
        "stable_shards": int(manifest.get("convergence_stable_shards") or 0),
    }


def _new_convergence_state(
    manifest: dict[str, Any],
    global_top_k: int,
) -> dict[str, Any]:
    return {
        "thresholds": _convergence_thresholds(manifest),
        "global_top_k": int(global_top_k),
        "region_budget": _normalize_region_budget(manifest.get("region_budget")),
        "cumulative_regions": set(),
        "cumulative_topk_cases": [],
        "cumulative_best_by_region": {},
        "previous_topk": set(),
        "previous_best_hit": 0,
        "cumulative_evaluated_case_count": 0,
        "stable_streak": 0,
        "progression": [],
        "recommended_stop": False,
        "recommended_stop_at_shard": None,
        "stop_reasons": [],
    }


def _advance_convergence_state(
    state: dict[str, Any],
    *,
    shard_plan: dict[str, Any],
    shard_payload: dict[str, Any],
) -> None:
    global_top_k = int(state["global_top_k"])
    thresholds = dict(state["thresholds"])
    region_budget = dict(state["region_budget"])
    shard_cases = list(shard_payload.get("cases") or [])
    shard_evaluated = int(shard_payload.get("evaluated_case_count") or 0)

    cumulative_evaluated_case_count = int(state["cumulative_evaluated_case_count"]) + shard_evaluated
    cumulative_topk_cases = list(state["cumulative_topk_cases"])
    cumulative_best_by_region = dict(state["cumulative_best_by_region"])
    previous_topk = set(state["previous_topk"])
    previous_best_hit = int(state["previous_best_hit"])
    cumulative_regions = set(state["cumulative_regions"])
    progression = list(state["progression"])

    if global_top_k > 0:
        cumulative_topk_cases = _update_incremental_topk(cumulative_topk_cases, shard_cases, global_top_k)
        _merge_best_cases_by_target_region(cumulative_best_by_region, shard_cases)
        cumulative_topk = _selected_case_index_set(
            cumulative_topk_cases,
            cumulative_best_by_region,
            region_budget,
        )
    else:
        cumulative_topk = set()

    shard_region_union = {
        str(region) for region in list(shard_payload.get("active_region_union") or [])
    }
    if not shard_region_union:
        shard_region_union = _active_region_union(shard_cases)
    cumulative_region_union = cumulative_regions | shard_region_union
    cumulative_best_hit = max(previous_best_hit, _payload_best_hit(shard_payload))

    new_regions = cumulative_region_union - cumulative_regions
    new_region_count = len(new_regions)
    delta_best_hit = cumulative_best_hit - previous_best_hit
    topk_churn_ratio = (
        float(len(cumulative_topk ^ previous_topk)) / float(max(1, global_top_k))
        if previous_topk
        else 1.0
    )
    denom_k = max(1.0, float(shard_evaluated) / 1000.0)
    new_regions_per_1k = float(new_region_count) / denom_k
    hit_gain_per_1k = float(max(0, delta_best_hit)) / denom_k

    is_stable = (
        new_regions_per_1k <= thresholds["min_new_regions_per_1k"]
        and hit_gain_per_1k <= thresholds["min_hit_gain_per_1k"]
        and topk_churn_ratio <= thresholds["max_topk_churn"]
    )
    stable_streak = int(state["stable_streak"]) + 1 if is_stable else 0
    recommended_stop = bool(state["recommended_stop"])
    recommended_stop_at_shard = state["recommended_stop_at_shard"]
    stop_reasons = list(state["stop_reasons"])
    if (
        not recommended_stop
        and len(progression) + 1 >= thresholds["min_completed_shards"]
        and stable_streak >= thresholds["stable_shards"]
    ):
        recommended_stop = True
        recommended_stop_at_shard = int(shard_plan["shard_index"])
        stop_reasons = [
            "new_region_gain_below_threshold",
            "best_hit_gain_below_threshold",
            "topk_churn_below_threshold",
        ]

    progression.append(
        {
            "shard_index": int(shard_plan["shard_index"]),
            "evaluated_case_count": shard_evaluated,
            "cumulative_evaluated_case_count": cumulative_evaluated_case_count,
            "new_region_count": new_region_count,
            "new_regions_per_1k": new_regions_per_1k,
            "best_hit_gain": max(0, delta_best_hit),
            "best_hit_gain_per_1k": hit_gain_per_1k,
            "cumulative_best_hit": cumulative_best_hit,
            "topk_churn_ratio": topk_churn_ratio,
            "stable_streak": stable_streak,
            "is_stable": is_stable,
        }
    )

    state["cumulative_regions"] = cumulative_region_union
    state["cumulative_topk_cases"] = cumulative_topk_cases
    state["cumulative_best_by_region"] = cumulative_best_by_region
    state["previous_topk"] = cumulative_topk
    state["previous_best_hit"] = cumulative_best_hit
    state["cumulative_evaluated_case_count"] = cumulative_evaluated_case_count
    state["stable_streak"] = stable_streak
    state["progression"] = progression
    state["recommended_stop"] = recommended_stop
    state["recommended_stop_at_shard"] = recommended_stop_at_shard
    state["stop_reasons"] = stop_reasons


def _rebuild_convergence_state(
    *,
    manifest: dict[str, Any],
    loaded_completed_cache: dict[int, dict[str, Any]],
    ordered_indices: list[int],
    global_top_k: int,
) -> dict[str, Any]:
    state = _new_convergence_state(manifest, global_top_k)
    for shard_index in ordered_indices:
        entry = loaded_completed_cache[shard_index]
        _advance_convergence_state(
            state,
            shard_plan=entry["shard_plan"],
            shard_payload=entry["payload"],
        )
    return state


def _convergence_summary_from_state(state: dict[str, Any]) -> dict[str, Any]:
    progression = list(state["progression"])
    return {
        "thresholds": dict(state["thresholds"]),
        "completed_shards": len(progression),
        "recommended_stop": bool(state["recommended_stop"]),
        "recommended_stop_at_shard": state["recommended_stop_at_shard"],
        "stop_reasons": list(state["stop_reasons"]),
        "progression": progression,
    }


def _build_convergence_summary(
    *,
    manifest: dict[str, Any],
    loaded_shards: list[dict[str, Any]],
    global_top_k: int,
) -> dict[str, Any]:
    state = _new_convergence_state(manifest, global_top_k)
    for entry in loaded_shards:
        _advance_convergence_state(
            state,
            shard_plan=entry["shard_plan"],
            shard_payload=entry["payload"],
        )
    return _convergence_summary_from_state(state)


def main(argv: list[str]) -> int:
    wall_start = time.perf_counter()
    ns = parse_args(argv)
    template_path = Path(ns.launch_template).expanduser().resolve()
    template = _load_json(template_path)
    template_args = dict(template.get("runner_args_template") or {})
    benchmark_freeze = load_benchmark_freeze(ns.benchmark_freeze_json)
    benchmark_profile = resolve_slice_profile(
        benchmark_freeze,
        slice_name=str(template.get("slice_name")),
        phase="campaign",
        profile_scenario=str(ns.profile_scenario),
    )
    search_tuning = resolve_slice_search_tuning(str(template.get("slice_name")), template_args)
    ns.launch_template = template_path
    ns.target = template.get("target")
    ns.slice_name = template.get("slice_name")
    ns.benchmark_profile = benchmark_profile or None
    ns.work_dir = Path(
        ns.work_dir or str(_template_work_dir(template) / "campaign")
    ).expanduser().resolve()
    ns.variants_per_case = int(ns.variants_per_case) or _template_int(template, "variants_per_case", len(TRACE_VARIANTS))
    ns.seed_fanout = int(ns.seed_fanout) or _template_int(template, "seed_fanout", 1)
    ns.shard_count = int(ns.shard_count) or _template_int(template, "shard_count", 128)
    ns.keep_top_k_per_shard = int(ns.keep_top_k_per_shard) or _template_int(template, "keep_top_k", 16)
    ns.global_top_k = int(ns.global_top_k) or _template_int(template, "global_top_k", 128)
    ns.trace_length = int(ns.trace_length) or _template_int(template, "trace_length", 12)
    ns.batch_length = int(ns.batch_length) or _template_int(template, "batch_length", 12)
    ns.gpu_sequential_steps = int(ns.gpu_sequential_steps) or int(
        benchmark_profile.get("sequential_steps") or _template_int(template, "gpu_sequential_steps", 56)
    )
    campaign_gpu_nstates = template_args.get("campaign_gpu_nstates")
    ns.gpu_nstates = int(ns.gpu_nstates) or int(
        campaign_gpu_nstates
        or benchmark_profile.get("nstates")
        or _template_int(template, "gpu_nstates", 32)
    )
    ns.gpu_reps = int(ns.gpu_reps) or int(
        benchmark_profile.get("gpu_reps") or _template_int(template, "gpu_reps", 1)
    )
    ns.cpu_reps = int(ns.cpu_reps) or int(
        benchmark_profile.get("cpu_reps") or _template_int(template, "cpu_reps", 1)
    )
    ns.candidate_count = int(ns.candidate_count) or (
        _template_int(template, "cases", 1000)
        * max(1, int(ns.variants_per_case))
        * max(1, int(ns.seed_fanout))
    )
    ns.dead_word_bias = _bool_with_template(ns.dead_word_bias, template_args.get("dead_word_bias"))
    ns.uniform_states = _bool_with_template(ns.uniform_states, template_args.get("uniform_states"))
    ns.profile_family = str(ns.profile_family or template_args.get("profile_family") or search_tuning.get("profile_family") or "mixed")
    ns.region_budget = (
        _parse_region_budget_arg(ns.region_budget_json)
        if ns.region_budget_json
        else _normalize_region_budget(
            template_args.get("region_budget") or search_tuning.get("region_budget")
        )
    )
    if ns.profile_family not in ("default", "dead-region", "mixed"):
        raise SystemExit(f"Unsupported --profile-family value: {ns.profile_family}")
    if int(ns.states_per_case) <= 0:
        ns.states_per_case = int(template_args.get("states_per_case") or search_tuning.get("states_per_case") or 4)

    original_global_top_k = int(ns.global_top_k)
    original_keep_top_k_per_shard = int(ns.keep_top_k_per_shard)
    policy_input_defaults = {
        "pilot_campaign_candidate_count": int(ns.candidate_count),
        "gpu_nstates": int(ns.gpu_nstates),
        "campaign_gpu_nstates": int(ns.gpu_nstates),
        "keep_top_k": original_keep_top_k_per_shard,
    }
    policy_result = apply_runtime_batch_policy(
        search_defaults=policy_input_defaults,
        execution_engine=str(ns.execution_engine),
        phase="campaign",
        policy_mode=str(ns.gpu_runtime_policy),
        memory_total_mib_override=(int(ns.gpu_memory_total_mib) if int(ns.gpu_memory_total_mib) > 0 else None),
    )
    effective_search_defaults = dict(policy_result["adjusted_search_defaults"])
    scope_policy_result = apply_search_scope_runtime_policy(
        slice_name=str(template.get("slice_name") or ""),
        search_defaults=effective_search_defaults,
        phase="campaign",
        region_budget=dict(ns.region_budget),
        policy_mode=str(ns.search_scope_policy),
        scope_json=str(ns.search_scope_json),
        graph_json=str(ns.search_scope_graph_json),
    )
    effective_search_defaults = dict(scope_policy_result["adjusted_search_defaults"])
    ns.region_budget = dict(scope_policy_result["adjusted_region_budget"])
    ns.candidate_count = int(
        effective_search_defaults.get("pilot_campaign_candidate_count") or int(ns.candidate_count)
    )
    ns.gpu_nstates = int(
        effective_search_defaults.get("campaign_gpu_nstates")
        or effective_search_defaults.get("gpu_nstates")
        or int(ns.gpu_nstates)
    )
    ns.keep_top_k_per_shard = int(
        effective_search_defaults.get("keep_top_k") or original_keep_top_k_per_shard
    )
    topk_scale = float(policy_result["policy"].get("topk_scale") or 1.0)
    ns.global_top_k = (
        _scale_topk_value(original_global_top_k, topk_scale)
        if topk_scale != 1.0
        else original_global_top_k
    )
    ns.gpu_runtime_policy_payload = dict(policy_result["policy"])
    ns.search_scope_policy_payload = dict(scope_policy_result["policy"])
    ns.effective_search_defaults_payload = {
        **effective_search_defaults,
        "global_top_k": int(ns.global_top_k),
        "keep_top_k_per_shard": int(ns.keep_top_k_per_shard),
        "states_per_case": int(ns.states_per_case),
        "cases_per_launch": int(ns.cases_per_launch) or max(1, int(ns.gpu_nstates) // max(1, int(ns.states_per_case))),
    }

    total_cases = _derived_case_count(ns)
    manifest_path = ns.work_dir / "campaign_manifest.json"
    preloaded_shards: list[dict[str, Any]] | None = None
    if ns.merge_only:
        if not manifest_path.exists():
            raise SystemExit(f"Missing campaign manifest for --merge-only: {manifest_path}")
        manifest = _load_json(manifest_path)
    else:
        manifest = write_launch_artifacts(ns, ns.work_dir, total_cases)
        execution = {}
        if ns.run_local:
            execution, preloaded_shards = run_shards_locally(manifest, int(ns.max_workers))
        else:
            execution = {"mode": "prepare_only" if ns.prepare_only else "manual"}
            preloaded_shards = None
    if ns.merge_only:
        execution = {"mode": "merge_only"}
        preloaded_shards = None

    merged = merge_shard_summaries(
        manifest,
        int(ns.global_top_k),
        execution,
        preloaded_shards=preloaded_shards,
    )
    wall_elapsed = time.perf_counter() - wall_start
    merged_execution = dict(merged.get("execution") or {})
    merged_execution["wall_clock_s"] = wall_elapsed
    merged["execution"] = merged_execution
    merged["gpu_runtime_policy"] = dict(getattr(ns, "gpu_runtime_policy_payload", {}))
    merged["effective_search_defaults"] = dict(getattr(ns, "effective_search_defaults_payload", {}))
    json_out = Path(ns.json_out).expanduser().resolve() if ns.json_out else (ns.work_dir / "summary.json")
    json_out.write_text(
        json.dumps(merged, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"summary_json={json_out}")
    best = merged.get("best_case")
    if isinstance(best, dict):
        print(
            "best_case="
            f"{best['case_index']} seed={best['seed']} "
            f"gpu_hit={best['real_subset_points_hit']} "
            f"dead_regions={best['dead_region_count']} "
            f"dead_words={best['dead_output_word_count']} "
            f"gpu_cps={best['real_subset_coverage_per_second']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
