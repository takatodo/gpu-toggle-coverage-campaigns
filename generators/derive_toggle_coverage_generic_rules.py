#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import median
from typing import Any

from opentitan_tlul_slice_search_tuning import DEFAULT_SEARCH_TUNING, resolve_slice_search_tuning


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROFILES_JSON = SCRIPT_DIR / "opentitan_tlul_slice_execution_profiles.json"
DEFAULT_CONVERGENCE_JSON = SCRIPT_DIR / "opentitan_tlul_slice_convergence_freeze.json"
DEFAULT_PRODUCTION_DEFAULTS_JSON = SCRIPT_DIR / "opentitan_tlul_slice_production_defaults.json"
DEFAULT_CPU_VS_GPU_JSON = SCRIPT_DIR / "opentitan_tlul_slice_cpu_vs_gpu_campaign_efficiency.json"
DEFAULT_RULES_JSON = SCRIPT_DIR / "toggle_coverage_generic_rules.json"
DEFAULT_RULES_MD = SCRIPT_DIR / "toggle_coverage_generic_rules.md"
DEFAULT_ASSIGNMENTS_JSON = SCRIPT_DIR / "toggle_coverage_rule_assignments.json"
DEFAULT_ASSIGNMENTS_MD = SCRIPT_DIR / "toggle_coverage_rule_assignments.md"


FAMILY_METADATA: dict[str, dict[str, Any]] = {
    "deep_fifo_source": {
        "description": "Deep sequential FIFO/control slices with large candidate budgets, early plateau, and source backend kept end-to-end.",
        "predicates": [
            "recommended_campaign_candidate_count >= 512",
            "recommended_stop == true",
            "campaign_backend == source",
            "best_case_hit <= 8",
        ],
    },
    "compact_socket_source": {
        "description": "Compact socket-style routing slices with high hit density and small candidate budgets; source backend kept for all phases.",
        "predicates": [
            "campaign_backend == source",
            "recommended_campaign_candidate_count <= 96",
            "best_case_hit >= 10",
        ],
    },
    "mixed_source_campaign_circt_multistep": {
        "description": "Routing slices where source wins sweep/campaign but CIRCT remains useful for multi-step benchmark shape.",
        "predicates": [
            "campaign_backend == source",
            "multi_step_backend == circt-cubin",
            "recommended_campaign_candidate_count <= 160",
            "best_case_hit between 6 and 10",
        ],
    },
    "dense_xbar_circt": {
        "description": "Dense xbar-like slices where CIRCT wins across single/multi/campaign and candidate budget remains moderate.",
        "predicates": [
            "campaign_backend == circt-cubin",
            "single_step_backend == circt-cubin",
            "multi_step_backend == circt-cubin",
        ],
    },
    "balanced_source_general": {
        "description": "Fallback source-oriented rule for unseen balanced routing slices when no stronger family matches.",
        "predicates": [
            "fallback",
        ],
    },
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _speedup(profile: dict[str, Any]) -> float:
    cpu = float(profile.get("median_cpu_ms_per_rep") or 0.0)
    gpu = float(profile.get("median_gpu_ms_per_rep") or 0.0)
    if cpu <= 0.0 or gpu <= 0.0:
        return 0.0
    return cpu / gpu


def _classify_slice(features: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    candidate_count = int(features.get("recommended_campaign_candidate_count") or 0)
    best_case_hit = int(features.get("best_case_hit") or 0)
    recommended_stop = bool(features.get("recommended_stop"))
    campaign_backend = str(features.get("campaign_backend") or "")
    single_backend = str(features.get("single_step_backend") or "")
    multi_backend = str(features.get("multi_step_backend") or "")

    if candidate_count >= 512 and recommended_stop and campaign_backend == "source" and best_case_hit <= 8:
        reasons.extend(
            [
                "large candidate budget",
                "early plateau stop enabled",
                "source campaign backend",
                "best hit remains compact",
            ]
        )
        return "deep_fifo_source", reasons

    if (
        campaign_backend == "source"
        and candidate_count <= 96
        and best_case_hit >= 10
    ):
        reasons.extend(
            [
                "small candidate budget",
                "high hit density",
                "source kept for campaign",
            ]
        )
        return "compact_socket_source", reasons

    if (
        campaign_backend == "circt-cubin"
        and single_backend == "circt-cubin"
        and multi_backend == "circt-cubin"
    ):
        reasons.extend(
            [
                "CIRCT wins across single/multi/campaign",
                "dense xbar-like routing shape",
            ]
        )
        return "dense_xbar_circt", reasons

    if (
        campaign_backend == "source"
        and multi_backend == "circt-cubin"
        and candidate_count <= 160
    ):
        reasons.extend(
            [
                "source campaign backend",
                "CIRCT still useful for multi-step",
                "moderate routing candidate budget",
            ]
        )
        return "mixed_source_campaign_circt_multistep", reasons

    reasons.append("fallback balanced source rule")
    return "balanced_source_general", reasons


def _family_defaults(
    family: str,
    evidence_rows: list[dict[str, Any]],
    search_tuning_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not evidence_rows:
        tuning = dict(DEFAULT_SEARCH_TUNING)
        return {
            "launch_backend_policy": {
                "single_step": "source",
                "multi_step": "source",
                "sweep": "source",
                "campaign": "source",
            },
            "search_defaults": {
                "profile_family": tuning.get("profile_family"),
                "variants_per_case": tuning.get("variants_per_case"),
                "seed_fanout": tuning.get("seed_fanout"),
                "batch_length": tuning.get("batch_length"),
                "trace_length": tuning.get("trace_length"),
                "gpu_nstates": tuning.get("gpu_nstates"),
                "campaign_gpu_nstates": tuning.get("campaign_gpu_nstates"),
                "campaign_sequential_rep_graph_mode": tuning.get("campaign_sequential_rep_graph_mode"),
                "states_per_case": tuning.get("states_per_case"),
                "keep_top_k": tuning.get("keep_top_k"),
                "pilot_sweep_cases": tuning.get("pilot_sweep_cases"),
                "pilot_campaign_candidate_count": tuning.get("pilot_campaign_candidate_count"),
                "region_budget": dict(tuning.get("region_budget") or {}),
                "driver_defaults": dict(tuning.get("driver_defaults") or {}),
            },
            "convergence_defaults": {
                "recommended_campaign_candidate_count": 256,
                "recommended_campaign_shard_count": 2,
                "recommended_stop": False,
            },
        }

    representative = evidence_rows[0]
    rep_tuning = dict(search_tuning_lookup[representative["slice_name"]])
    campaign_backend = representative["campaign_backend"]
    single_backend = representative["single_step_backend"]
    multi_backend = representative["multi_step_backend"]

    candidate_counts = [int(row["recommended_campaign_candidate_count"]) for row in evidence_rows]
    shard_counts = [int(row["recommended_campaign_shard_count"]) for row in evidence_rows]
    campaign_gpu_nstates = [int(search_tuning_lookup[row["slice_name"]]["campaign_gpu_nstates"]) for row in evidence_rows]
    keep_top_k = [int(search_tuning_lookup[row["slice_name"]]["keep_top_k"]) for row in evidence_rows]
    variants_per_case = [int(search_tuning_lookup[row["slice_name"]]["variants_per_case"]) for row in evidence_rows]
    batch_lengths = [int(search_tuning_lookup[row["slice_name"]]["batch_length"]) for row in evidence_rows]
    trace_lengths = [int(search_tuning_lookup[row["slice_name"]]["trace_length"]) for row in evidence_rows]

    return {
        "launch_backend_policy": {
            "single_step": single_backend,
            "multi_step": multi_backend,
            "sweep": campaign_backend if family != "mixed_source_campaign_circt_multistep" else "source",
            "campaign": campaign_backend,
        },
        "search_defaults": {
            "profile_family": rep_tuning.get("profile_family"),
            "variants_per_case": int(round(median(variants_per_case))),
            "seed_fanout": int(rep_tuning.get("seed_fanout") or 1),
            "batch_length": int(round(median(batch_lengths))),
            "trace_length": int(round(median(trace_lengths))),
            "gpu_nstates": int(rep_tuning.get("gpu_nstates") or 32),
            "campaign_gpu_nstates": int(round(median(campaign_gpu_nstates))),
            "campaign_sequential_rep_graph_mode": rep_tuning.get("campaign_sequential_rep_graph_mode", "auto"),
            "states_per_case": int(rep_tuning.get("states_per_case") or 4),
            "keep_top_k": int(round(median(keep_top_k))),
            "pilot_sweep_cases": int(rep_tuning.get("pilot_sweep_cases") or 256),
            "pilot_campaign_candidate_count": int(max(candidate_counts)),
            "region_budget": dict(rep_tuning.get("region_budget") or {}),
            "driver_defaults": dict(rep_tuning.get("driver_defaults") or {}),
        },
        "convergence_defaults": {
            "recommended_campaign_candidate_count": int(max(candidate_counts)),
            "recommended_campaign_shard_count": int(round(median(shard_counts))),
            "recommended_stop": any(bool(row["recommended_stop"]) for row in evidence_rows),
        },
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive generic toggle-coverage acceleration rules from the current OpenTitan slice evidence."
    )
    parser.add_argument("--profiles-json", default=str(DEFAULT_PROFILES_JSON))
    parser.add_argument("--convergence-json", default=str(DEFAULT_CONVERGENCE_JSON))
    parser.add_argument("--production-defaults-json", default=str(DEFAULT_PRODUCTION_DEFAULTS_JSON))
    parser.add_argument("--cpu-vs-gpu-json", default=str(DEFAULT_CPU_VS_GPU_JSON))
    parser.add_argument("--rules-json-out", default=str(DEFAULT_RULES_JSON))
    parser.add_argument("--rules-md-out", default=str(DEFAULT_RULES_MD))
    parser.add_argument("--assignments-json-out", default=str(DEFAULT_ASSIGNMENTS_JSON))
    parser.add_argument("--assignments-md-out", default=str(DEFAULT_ASSIGNMENTS_MD))
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    profiles_payload = _load_json(Path(ns.profiles_json).expanduser().resolve())
    convergence_payload = _load_json(Path(ns.convergence_json).expanduser().resolve())
    production_defaults_payload = _load_json(Path(ns.production_defaults_json).expanduser().resolve())
    cpu_vs_gpu_path = Path(ns.cpu_vs_gpu_json).expanduser().resolve()
    cpu_vs_gpu_payload = _load_json(cpu_vs_gpu_path) if cpu_vs_gpu_path.exists() else {"rows": []}

    profiles_lookup = {
        str(entry.get("slice_name")): dict(entry)
        for entry in list(profiles_payload.get("slices") or [])
    }
    convergence_lookup = {
        str(entry.get("slice_name")): dict(entry)
        for entry in list(convergence_payload.get("slices") or [])
    }
    production_lookup = {
        str(entry.get("slice_name")): dict(entry)
        for entry in list(production_defaults_payload.get("rows") or [])
    }
    cpu_vs_gpu_lookup = {
        str(entry.get("slice_name")): dict(entry)
        for entry in list(cpu_vs_gpu_payload.get("rows") or [])
    }

    slice_names = sorted(set(profiles_lookup) & set(convergence_lookup) & set(production_lookup))
    search_tuning_lookup = {
        slice_name: resolve_slice_search_tuning(slice_name, {})
        for slice_name in slice_names
    }

    assignments: list[dict[str, Any]] = []
    family_evidence: dict[str, list[dict[str, Any]]] = {name: [] for name in FAMILY_METADATA}
    for slice_name in slice_names:
        profile = profiles_lookup[slice_name]
        convergence = convergence_lookup[slice_name]
        production = production_lookup[slice_name]
        cpu_vs_gpu = cpu_vs_gpu_lookup.get(slice_name, {})
        single_profile = dict(profile.get("profiles", {}).get("single_step") or {})
        multi_profile = dict(profile.get("profiles", {}).get("multi_step") or {})
        features = {
            "slice_name": slice_name,
            "single_step_backend": production.get("single_step_backend"),
            "multi_step_backend": production.get("multi_step_backend"),
            "campaign_backend": production.get("campaign_backend"),
            "best_case_hit": int(production.get("best_case_hit") or 0),
            "recommended_campaign_candidate_count": int(
                production.get("recommended_campaign_candidate_count") or 0
            ),
            "recommended_campaign_shard_count": int(
                production.get("recommended_campaign_shard_count") or 0
            ),
            "recommended_stop": bool(production.get("recommended_stop")),
            "hit_per_wall_s": float(production.get("hit_per_wall_s") or 0.0),
            "single_step_gpu_speedup": _speedup(single_profile),
            "multi_step_gpu_speedup": _speedup(multi_profile),
            "campaign_gpu_vs_cpu_hit_ratio": float(cpu_vs_gpu.get("gpu_vs_cpu_hit_per_s") or 0.0),
            "campaign_gpu_nstates": int(search_tuning_lookup[slice_name].get("campaign_gpu_nstates") or 0),
            "gpu_nstates": int(search_tuning_lookup[slice_name].get("gpu_nstates") or 0),
        }
        family, reasons = _classify_slice(features)
        assignment = {
            **features,
            "rule_family": family,
            "classification_reasons": reasons,
        }
        assignments.append(assignment)
        family_evidence.setdefault(family, []).append(assignment)

    rules: list[dict[str, Any]] = []
    for family_name, metadata in FAMILY_METADATA.items():
        evidence_rows = sorted(
            family_evidence.get(family_name, []),
            key=lambda row: float(row.get("hit_per_wall_s") or 0.0),
            reverse=True,
        )
        defaults = _family_defaults(family_name, evidence_rows, search_tuning_lookup)
        rules.append(
            {
                "rule_family": family_name,
                "description": metadata["description"],
                "feature_predicates": list(metadata["predicates"]),
                "recommended_defaults": defaults,
                "evidence_slices": [row["slice_name"] for row in evidence_rows],
                "evidence_summary": {
                    "count": len(evidence_rows),
                    "best_hit_per_wall_s": float(evidence_rows[0]["hit_per_wall_s"]) if evidence_rows else 0.0,
                    "campaign_gpu_nstates_values": sorted(
                        {int(row["campaign_gpu_nstates"]) for row in evidence_rows}
                    ),
                    "campaign_backends": sorted({str(row["campaign_backend"]) for row in evidence_rows}),
                },
            }
        )

    rules_payload = {
        "schema_version": "toggle-coverage-generic-rules-v1",
        "source_profiles_json": str(Path(ns.profiles_json).expanduser().resolve()),
        "source_convergence_json": str(Path(ns.convergence_json).expanduser().resolve()),
        "source_production_defaults_json": str(Path(ns.production_defaults_json).expanduser().resolve()),
        "source_cpu_vs_gpu_json": str(cpu_vs_gpu_path) if cpu_vs_gpu_path.exists() else "",
        "rules": rules,
    }
    assignments_payload = {
        "schema_version": "toggle-coverage-rule-assignments-v1",
        "source_rules_json": str(Path(ns.rules_json_out).expanduser().resolve()),
        "rows": assignments,
    }

    rules_json_out = Path(ns.rules_json_out).expanduser().resolve()
    rules_md_out = Path(ns.rules_md_out).expanduser().resolve()
    assignments_json_out = Path(ns.assignments_json_out).expanduser().resolve()
    assignments_md_out = Path(ns.assignments_md_out).expanduser().resolve()
    rules_json_out.write_text(json.dumps(rules_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assignments_json_out.write_text(
        json.dumps(assignments_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    rule_lines = [
        "# Toggle Coverage Generic Rules",
        "",
        "| Rule | Evidence | Campaign backend | Campaign nstates | Candidate count | Region budget | Notes |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for rule in rules:
        defaults = dict(rule.get("recommended_defaults") or {})
        search_defaults = dict(defaults.get("search_defaults") or {})
        convergence_defaults = dict(defaults.get("convergence_defaults") or {})
        launch_policy = dict(defaults.get("launch_backend_policy") or {})
        notes = "; ".join(rule.get("feature_predicates") or [])
        region_budget = dict(search_defaults.get("region_budget") or {})
        region_budget_text = ", ".join(
            f"{region}={int(quota)}"
            for region, quota in sorted(region_budget.items())
        ) or "-"
        rule_lines.append(
            f"| {rule['rule_family']} | {', '.join(rule['evidence_slices']) or '-'} | "
            f"{launch_policy.get('campaign','')} | "
            f"{int(search_defaults.get('campaign_gpu_nstates') or 0)} | "
            f"{int(convergence_defaults.get('recommended_campaign_candidate_count') or 0)} | "
            f"{region_budget_text} | "
            f"{notes} |"
        )
    rules_md_out.write_text("\n".join(rule_lines) + "\n", encoding="utf-8")

    assignment_lines = [
        "# Toggle Coverage Rule Assignments",
        "",
        "| Slice | Rule | Campaign backend | Campaign nstates | Hit/s | GPU/CPU hit/s | Reasons |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in assignments:
        assignment_lines.append(
            f"| {row['slice_name']} | {row['rule_family']} | {row['campaign_backend']} | "
            f"{int(row['campaign_gpu_nstates'])} | {float(row['hit_per_wall_s']):.4f} | "
            f"{float(row['campaign_gpu_vs_cpu_hit_ratio']):.3f} | "
            f"{'; '.join(row['classification_reasons'])} |"
        )
    assignments_md_out.write_text("\n".join(assignment_lines) + "\n", encoding="utf-8")

    print(rules_json_out)
    print(rules_md_out)
    print(assignments_json_out)
    print(assignments_md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
