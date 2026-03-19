#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
RULES_JSON = SCRIPT_DIR / "toggle_coverage_generic_rules.json"
ASSIGNMENTS_JSON = SCRIPT_DIR / "rtlmeter_design_toggle_rule_assignments.json"
BASELINE_RUNNER = SCRIPT_DIR / "run_rtlmeter_gpu_toggle_baseline.py"

from gpu_runtime_batch_policy import apply_runtime_batch_policy


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a rule-guided RTLMeter gpu_cov sweep/campaign smoke for ready external designs."
    )
    parser.add_argument("--design", required=True)
    parser.add_argument("--configuration", default="gpu_cov")
    parser.add_argument("--rules-json", default=str(RULES_JSON))
    parser.add_argument("--assignments-json", default=str(ASSIGNMENTS_JSON))
    parser.add_argument("--rule-family", default="")
    parser.add_argument("--phase", choices=("sweep", "campaign"), default="sweep")
    parser.add_argument("--execution-engine", choices=("gpu", "cpu"), default="gpu")
    parser.add_argument(
        "--gpu-runtime-policy",
        choices=("auto", "off"),
        default="auto",
        help="Scale nstate/batching defaults from the frozen rule using detected GPU memory tier.",
    )
    parser.add_argument(
        "--gpu-memory-total-mib",
        type=int,
        default=0,
        help="Override detected GPU memory for runtime batching policy validation.",
    )
    parser.add_argument("--tests", nargs="*", default=[])
    parser.add_argument("--work-dir", default="")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument(
        "--reuse-bench-kernel-if-present",
        dest="reuse_bench_kernel_if_present",
        action="store_true",
        help="Reuse bench_kernel directly when present. Defaults to enabled for GPU execution.",
    )
    parser.add_argument(
        "--no-reuse-bench-kernel-if-present",
        dest="reuse_bench_kernel_if_present",
        action="store_false",
        help="Force wrapper execution even when direct bench reuse is available.",
    )
    parser.set_defaults(reuse_bench_kernel_if_present=None)
    return parser.parse_args(argv)


def _summary_fields(summary: dict[str, Any]) -> dict[str, Any]:
    coverage_regions = dict(summary.get("coverage_regions") or {})
    collector = dict(summary.get("collector") or {})
    coverage = dict(collector.get("coverage") or {})
    runtime_preloads = dict(summary.get("bench_runtime_materialized_preloads") or {})
    return {
        "best_case_hit": int(((summary.get("real_toggle_subset") or {}).get("points_hit")) or 0),
        "dead_region_count": int(
            coverage_regions.get("dead_region_count")
            or len(list(coverage_regions.get("dead_regions") or []))
        ),
        "dead_output_word_count": int(
            coverage_regions.get("dead_output_word_count")
            or len(list(((summary.get("real_toggle_subset") or {}).get("dead_words")) or []))
        ),
        "gpu_cps": float(coverage.get("gpu_coverage_per_second") or 0.0),
        "bench_runtime_mode": str(summary.get("bench_runtime_mode") or ""),
        "bench_runtime_reused": bool(summary.get("bench_runtime_reused")),
        "preload_cache_hit_rate": float(runtime_preloads.get("cache_hit_rate") or 0.0),
        "preload_cache_entry_count": int(runtime_preloads.get("cache_entry_count") or 0),
        "preload_cache_hit_count": int(runtime_preloads.get("cache_hit_count") or 0),
    }


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    rules_payload = _load_json(Path(ns.rules_json).expanduser().resolve())
    rules_lookup = {
        str(rule.get("rule_family")): dict(rule)
        for rule in list(rules_payload.get("rules") or [])
    }
    assignments_payload = _load_json(Path(ns.assignments_json).expanduser().resolve())
    assignment_lookup = {
        (str(row.get("design") or ""), str(row.get("configuration") or "")): dict(row)
        for row in list(assignments_payload.get("rows") or [])
    }
    key = (ns.design, ns.configuration)
    if key not in assignment_lookup:
        raise SystemExit(f"Missing rule assignment for {ns.design}:{ns.configuration}")
    assignment = assignment_lookup[key]
    rule_family = ns.rule_family or str(assignment.get("rule_family") or "")
    if not rule_family or rule_family not in rules_lookup:
        raise SystemExit(f"Missing rule family for {ns.design}:{ns.configuration}")
    rule = rules_lookup[rule_family]
    search_defaults = dict(rule.get("recommended_defaults", {}).get("search_defaults") or {})
    policy_result = apply_runtime_batch_policy(
        search_defaults=search_defaults,
        execution_engine=ns.execution_engine,
        phase=ns.phase,
        policy_mode=str(ns.gpu_runtime_policy),
        memory_total_mib_override=(int(ns.gpu_memory_total_mib) if int(ns.gpu_memory_total_mib) > 0 else None),
    )
    search_defaults = dict(policy_result["adjusted_search_defaults"])

    tests = list(ns.tests) if ns.tests else list(assignment.get(f"{ns.phase}_tests") or [])
    if not tests:
        raise SystemExit(f"No tests configured for {ns.design}:{ns.configuration} phase {ns.phase}")

    work_dir = (
        Path(ns.work_dir).expanduser().resolve()
        if ns.work_dir
        else SCRIPT_DIR / "rtlmeter_rule_guided_runs" / ns.design / ns.configuration / ns.phase / rule_family
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    reuse_bench_kernel_if_present = ns.reuse_bench_kernel_if_present
    if reuse_bench_kernel_if_present is None:
        reuse_bench_kernel_if_present = ns.execution_engine == "gpu"
    nstates = int(
        search_defaults.get("campaign_gpu_nstates" if ns.phase == "campaign" else "gpu_nstates")
        or 32
    )
    driver_defaults = dict(search_defaults.get("driver_defaults") or {})

    case_rows: list[dict[str, Any]] = []
    for test_name in tests:
        build_dir = work_dir / test_name
        run_json = build_dir / "summary.json"
        cmd = [
            "python3",
            str(BASELINE_RUNNER),
            "--case",
            f"{ns.design}:{ns.configuration}:{test_name}",
            "--build-dir",
            str(build_dir),
            "--json-out",
            str(run_json),
            "--nstates",
            str(nstates),
            "--summary-mode",
            "prefilter",
        ]
        if ns.rebuild:
            cmd.append("--rebuild")
        if reuse_bench_kernel_if_present:
            cmd.append("--reuse-bench-kernel-if-present")
        if ns.execution_engine == "gpu":
            cmd.extend(["--gpu-reps", "1", "--cpu-reps", "0", "--skip-cpu-reference-build"])
        else:
            cmd.extend(["--gpu-reps", "0", "--cpu-reps", "1"])
        for key_name, value in sorted(driver_defaults.items()):
            cmd.extend([f"--{key_name.replace('_', '-')}", str(value)])
        subprocess.run(cmd, cwd=SCRIPT_DIR, check=True)
        summary = _load_json(run_json)
        case_rows.append(
            {
                "test": test_name,
                "summary_json": str(run_json.resolve()),
                **_summary_fields(summary),
            }
        )

    best_case = max(
        case_rows,
        key=lambda row: (
            int(row.get("best_case_hit") or 0),
            -int(row.get("dead_region_count") or 0),
            float(row.get("gpu_cps") or 0.0),
        ),
    )
    summary_payload = {
        "schema_version": "rtlmeter-design-rule-guided-sweep-v1",
        "design": ns.design,
        "configuration": ns.configuration,
        "phase": ns.phase,
        "execution_engine": ns.execution_engine,
        "rule_family": rule_family,
        "rule": rule,
        "selected_case_count": len(case_rows),
        "best_case": best_case,
        "cases": case_rows,
    }
    summary_json = work_dir / "summary.json"
    summary_json.write_text(json.dumps(summary_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    run_payload = {
        "schema_version": "rtlmeter-design-rule-guided-run-v1",
        "design": ns.design,
        "configuration": ns.configuration,
        "phase": ns.phase,
        "execution_engine": ns.execution_engine,
        "rule_family": rule_family,
        "assignment": assignment,
        "gpu_runtime_policy": policy_result["policy"],
        "effective_search_defaults": search_defaults,
        "work_dir": str(work_dir),
        "summary_json": str(summary_json),
        "tests": tests,
        "nstates": nstates,
        "rebuild": bool(ns.rebuild),
        "reuse_bench_kernel_if_present": bool(reuse_bench_kernel_if_present),
    }
    json_out = (
        Path(ns.json_out).expanduser().resolve()
        if ns.json_out
        else work_dir / "run.json"
    )
    json_out.write_text(json.dumps(run_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
