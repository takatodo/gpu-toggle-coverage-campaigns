#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
INDEX_JSON = SCRIPT_DIR / "slice_launch_templates" / "index.json"
RULES_JSON = ROOT_DIR / "config/rules/toggle_coverage_generic_rules.json"
ASSIGNMENTS_JSON = ROOT_DIR / "config/rules/toggle_coverage_rule_assignments.json"
SWEEP_RUNNER = SCRIPT_DIR / "run_opentitan_tlul_slice_trace_gpu_sweep.py"

from gpu_runtime_batch_policy import apply_runtime_batch_policy


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a rule-guided toggle-coverage sweep using the current generic rule families."
    )
    parser.add_argument("--slice", required=True)
    parser.add_argument("--index-json", default=str(INDEX_JSON))
    parser.add_argument("--rules-json", default=str(RULES_JSON))
    parser.add_argument("--assignments-json", default=str(ASSIGNMENTS_JSON))
    parser.add_argument("--rule-family", default="")
    parser.add_argument("--work-dir", default="")
    parser.add_argument("--cases", type=int, default=0)
    parser.add_argument("--phase", choices=("sweep", "campaign"), default="sweep")
    parser.add_argument("--execution-engine", choices=("gpu", "cpu"), default="gpu")
    parser.add_argument(
        "--gpu-runtime-policy",
        choices=("auto", "off"),
        default="auto",
        help="Scale batching defaults from the frozen rule using detected GPU memory tier.",
    )
    parser.add_argument(
        "--gpu-memory-total-mib",
        type=int,
        default=0,
        help="Override detected GPU memory for runtime batching policy validation.",
    )
    parser.add_argument("--json-out", default="")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    index_payload = _load_json(Path(ns.index_json).expanduser().resolve())
    template_lookup = {
        str(entry.get("slice_name")): dict(entry)
        for entry in list(index_payload.get("index") or [])
    }
    if ns.slice not in template_lookup:
        raise SystemExit(f"Unknown slice: {ns.slice}")

    rules_payload = _load_json(Path(ns.rules_json).expanduser().resolve())
    rules_lookup = {
        str(rule.get("rule_family")): dict(rule)
        for rule in list(rules_payload.get("rules") or [])
    }
    assignments_payload = _load_json(Path(ns.assignments_json).expanduser().resolve())
    assignment_lookup = {
        str(entry.get("slice_name")): dict(entry)
        for entry in list(assignments_payload.get("rows") or [])
    }
    assignment = assignment_lookup.get(ns.slice, {})
    rule_family = ns.rule_family or str(assignment.get("rule_family") or "")
    if not rule_family or rule_family not in rules_lookup:
        raise SystemExit(f"Missing rule family for slice {ns.slice}")
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
    launch_policy = dict(rule.get("recommended_defaults", {}).get("launch_backend_policy") or {})

    template_path = Path(
        str(template_lookup[ns.slice].get("launch_template_path") or template_lookup[ns.slice].get("template_json"))
    ).expanduser().resolve()
    work_dir = (
        Path(ns.work_dir).expanduser().resolve()
        if ns.work_dir
        else SCRIPT_DIR / "rule_guided_sweeps" / ns.slice / rule_family
    )
    work_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python3",
        str(SWEEP_RUNNER),
        "--launch-template",
        str(template_path),
        "--work-dir",
        str(work_dir),
        "--phase",
        ns.phase,
        "--execution-engine",
        ns.execution_engine,
        "--profile-family",
        str(search_defaults.get("profile_family") or "mixed"),
        "--variants-per-case",
        str(int(search_defaults.get("variants_per_case") or 4)),
        "--seed-fanout",
        str(int(search_defaults.get("seed_fanout") or 1)),
        "--trace-length",
        str(int(search_defaults.get("trace_length") or 12)),
        "--batch-length",
        str(int(search_defaults.get("batch_length") or 12)),
        "--gpu-nstates",
        str(int(search_defaults.get("gpu_nstates") or 32)),
        "--states-per-case",
        str(int(search_defaults.get("states_per_case") or 4)),
        "--keep-top-k",
        str(int(search_defaults.get("keep_top_k") or 16)),
        "--launch-backend",
        str(launch_policy.get("sweep") or launch_policy.get("campaign") or "auto"),
    ]
    graph_mode = str(search_defaults.get("campaign_sequential_rep_graph_mode") or "").strip()
    if graph_mode:
        cmd.extend(["--sequential-rep-graph-mode", graph_mode])
    region_budget = dict(search_defaults.get("region_budget") or {})
    if region_budget:
        cmd.extend(["--region-budget-json", json.dumps(region_budget, sort_keys=True)])
    if int(ns.cases) > 0:
        cmd.extend(["--cases", str(int(ns.cases))])
    else:
        default_cases = (
            int(search_defaults.get("pilot_campaign_candidate_count") or 256)
            if ns.phase == "campaign"
            else int(search_defaults.get("pilot_sweep_cases") or 256)
        )
        cmd.extend(["--cases", str(default_cases)])
    if ns.execution_engine == "gpu":
        cmd.append("--dead-word-bias")
    subprocess.run(cmd, cwd=SCRIPT_DIR, check=True)

    payload = {
        "schema_version": "toggle-coverage-rule-guided-sweep-v1",
        "slice_name": ns.slice,
        "rule_family": rule_family,
        "rule": rule,
        "gpu_runtime_policy": policy_result["policy"],
        "effective_search_defaults": search_defaults,
        "work_dir": str(work_dir),
        "command": cmd,
    }
    json_out = (
        Path(ns.json_out).expanduser().resolve()
        if ns.json_out
        else work_dir / "rule_guided_sweep.json"
    )
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
