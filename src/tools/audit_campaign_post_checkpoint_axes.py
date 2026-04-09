#!/usr/bin/env python3
"""
Recommend the next expansion axis once the current active campaign line reaches
checkpoint readiness.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_CHECKPOINT_JSON = REPO_ROOT / "work" / "campaign_checkpoint_readiness.json"
DEFAULT_ACTIVE_SCOREBOARD_JSON = REPO_ROOT / "work" / "campaign_speed_scoreboard_active.json"
DEFAULT_ACTIVE_NEXT_KPI_JSON = REPO_ROOT / "work" / "campaign_next_kpi_active.json"
DEFAULT_DESIGNS_ROOT = REPO_ROOT / "third_party" / "rtlmeter" / "designs"
DEFAULT_RUNNERS_DIR = REPO_ROOT / "src" / "runners"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_post_checkpoint_axes.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_inventory_family(raw_family: str) -> str:
    if raw_family.startswith("XuanTie-"):
        return "XuanTie"
    if raw_family.startswith("VeeR-"):
        return "VeeR"
    return raw_family


def _repo_family_for_target(target: str) -> str:
    if target.startswith("tlul_") or target.startswith("xbar_"):
        return "OpenTitan"
    if target.startswith("xuantie_"):
        return "XuanTie"
    if target.startswith("veer_"):
        return "VeeR"
    if target.startswith("xiangshan"):
        return "XiangShan"
    if target.startswith("openpiton"):
        return "OpenPiton"
    if target.startswith("blackparrot") or target.startswith("bp_"):
        return "BlackParrot"
    if target.startswith("caliptra"):
        return "Caliptra"
    if target.startswith("vortex"):
        return "Vortex"
    if target.startswith("example"):
        return "Example"
    return target.split("_", 1)[0]


def _family_slug(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch.isalnum())


def _runner_support_for_family(runners_dir: Path, family_name: str) -> dict[str, Any]:
    slug = _family_slug(family_name)
    family_runner = runners_dir / f"run_{slug}_family_gpu_toggle_validation.py"
    single_runner = runners_dir / f"run_{slug}_gpu_toggle_validation.py"
    if family_runner.exists():
        return {
            "kind": "family_runner",
            "path": str(family_runner.resolve()),
            "score": 2,
        }
    if single_runner.exists():
        return {
            "kind": "single_runner",
            "path": str(single_runner.resolve()),
            "score": 1,
        }
    return {
        "kind": "none",
        "path": None,
        "score": 0,
    }


def _inventory_rows(
    *,
    designs_root: Path,
    runners_dir: Path,
    active_repo_families: set[str],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for tb_path in sorted(designs_root.glob("*/**/*_gpu_cov_tb.sv")):
        relative = tb_path.relative_to(designs_root)
        raw_family = relative.parts[0]
        family_name = _normalize_inventory_family(raw_family)
        row = grouped.setdefault(
            family_name,
            {
                "repo_family": family_name,
                "raw_family_dirs": set(),
                "tb_paths": [],
            },
        )
        row["raw_family_dirs"].add(raw_family)
        row["tb_paths"].append(str(tb_path.resolve()))

    rows: list[dict[str, Any]] = []
    for family_name, row in sorted(grouped.items()):
        runner_support = _runner_support_for_family(runners_dir, family_name)
        raw_dirs = sorted(row["raw_family_dirs"])
        tb_paths = sorted(row["tb_paths"])
        is_active_repo_family = family_name in active_repo_families
        rows.append(
            {
                "repo_family": family_name,
                "design_count": len(tb_paths),
                "raw_family_dirs": raw_dirs,
                "example_tb_paths": tb_paths[:3],
                "runner_support": {
                    "kind": runner_support["kind"],
                    "path": runner_support["path"],
                },
                "is_active_repo_family": is_active_repo_family,
                "is_opentitan": family_name == "OpenTitan",
                "_sort_key": (
                    0 if is_active_repo_family else 1,
                    runner_support["score"],
                    len(tb_paths),
                    family_name,
                ),
            }
        )

    rows.sort(key=lambda item: (-item["_sort_key"][0], -item["_sort_key"][1], -item["_sort_key"][2], item["_sort_key"][3]))
    for row in rows:
        row.pop("_sort_key", None)
    return rows


def build_post_checkpoint_axes(
    *,
    checkpoint_readiness: dict[str, Any],
    active_scoreboard: dict[str, Any],
    active_next_kpi: dict[str, Any],
    designs_root: Path,
    runners_dir: Path,
) -> dict[str, Any]:
    checkpoint_summary = dict(checkpoint_readiness.get("summary") or {})
    checkpoint_decision = dict(checkpoint_readiness.get("decision") or {})
    next_kpi_decision = dict(active_next_kpi.get("decision") or {})
    active_rows = list(active_scoreboard.get("rows") or [])
    active_targets = [str(row.get("target")) for row in active_rows if row.get("target")]
    active_repo_families = sorted({_repo_family_for_target(target) for target in active_targets})
    inventory_rows = _inventory_rows(
        designs_root=designs_root,
        runners_dir=runners_dir,
        active_repo_families=set(active_repo_families),
    )
    non_opentitan_candidates = [
        row for row in inventory_rows if not row["is_active_repo_family"] and not row["is_opentitan"]
    ]
    ready_pool_exhausted = float(checkpoint_summary.get("active_fraction_of_ready_pool") or 0.0) >= 1.0
    checkpoint_status = str(checkpoint_decision.get("readiness") or "")
    next_kpi = str(next_kpi_decision.get("recommended_next_kpi") or "")

    axis_rows = [
        {
            "axis": "broaden_non_opentitan_family",
            "status": (
                "recommended"
                if checkpoint_status == "cross_family_checkpoint_ready"
                and ready_pool_exhausted
                and next_kpi == "broader_design_count"
                and bool(non_opentitan_candidates)
                else "available" if bool(non_opentitan_candidates) else "blocked"
            ),
            "reason": (
                "current_ready_pool_exhausted_and_active_line_is_still_opentitan_only"
                if ready_pool_exhausted and bool(non_opentitan_candidates)
                else "no_non_opentitan_inventory_detected"
            ),
            "top_candidate_family": non_opentitan_candidates[0]["repo_family"] if non_opentitan_candidates else None,
        },
        {
            "axis": "strengthen_thresholds",
            "status": "deferred" if next_kpi == "broader_design_count" else "active",
            "reason": (
                "current_active_kpi_already_requests_broader_design_count"
                if next_kpi == "broader_design_count"
                else "current_active_kpi_not_broader_design_count"
            ),
        },
        {
            "axis": "reopen_supported_promotion",
            "status": "deferred",
            "reason": "campaign_speed_checkpoint_is_now_ahead_of_supported_promotion_work",
        },
    ]

    if checkpoint_status != "cross_family_checkpoint_ready":
        decision = {
            "recommended_next_axis": "stabilize_current_checkpoint",
            "reason": "checkpoint_not_ready_for_post_checkpoint_axes",
            "recommended_next_tasks": [
                "Keep the current active line stable until checkpoint_readiness reaches cross_family_checkpoint_ready.",
                "Do not reopen broader design search before the checkpoint is accepted.",
            ],
        }
    elif next_kpi != "broader_design_count":
        decision = {
            "recommended_next_axis": "follow_current_active_kpi",
            "reason": "active_kpi_does_not_yet_request_broader_design_count",
            "recommended_next_tasks": [
                f"Keep the current active line stable while the active KPI remains `{next_kpi}`.",
                "Only choose a post-checkpoint expansion axis after the active KPI changes to broader_design_count.",
            ],
        }
    elif not ready_pool_exhausted:
        decision = {
            "recommended_next_axis": "finish_current_ready_pool",
            "reason": "active_line_does_not_yet_cover_the_current_ready_pool",
            "recommended_next_tasks": [
                "Keep broadening inside the current ready_for_campaign pool.",
                "Do not open a new family until active_fraction_of_ready_pool reaches 1.0.",
            ],
        }
    elif non_opentitan_candidates:
        top = non_opentitan_candidates[0]
        decision = {
            "recommended_next_axis": "broaden_non_opentitan_family",
            "reason": "current_ready_pool_exhausted_and_active_line_is_still_opentitan_only",
            "recommended_family": top["repo_family"],
            "recommended_next_tasks": [
                f"Start the next expansion wave with `{top['repo_family']}`.",
                "Decide whether the first non-OpenTitan deliverable should be one comparison surface or a family pilot.",
                "Keep the current 9-surface active line frozen as the first checkpoint baseline while opening that family.",
            ],
        }
    else:
        decision = {
            "recommended_next_axis": "choose_between_thresholds_and_promotion",
            "reason": "no_new_non_opentitan_family_candidates_detected",
            "recommended_next_tasks": [
                "Define a stronger common campaign threshold or reopen supported-promotion work.",
                "Do not resume open-ended design search without a new breadth target.",
            ],
        }

    return {
        "schema_version": 1,
        "scope": "campaign_post_checkpoint_axes",
        "inputs": {
            "checkpoint_readiness": checkpoint_readiness.get("scope"),
            "active_scoreboard": active_scoreboard.get("scope"),
            "active_next_kpi": active_next_kpi.get("scope"),
        },
        "current_active_line": {
            "targets": active_targets,
            "repo_families": active_repo_families,
            "repo_family_count": len(active_repo_families),
            "subfamily_count": checkpoint_summary.get("family_diversity_count"),
        },
        "inventory_summary": {
            "repo_family_count_with_gpu_cov_tb": len(inventory_rows),
            "non_opentitan_family_count_with_gpu_cov_tb": len(non_opentitan_candidates),
            "ready_pool_exhausted": ready_pool_exhausted,
        },
        "policy_context": {
            "selected_profile_name": active_scoreboard.get("selected_profile_name"),
            "selected_policy_mode": active_scoreboard.get("selected_policy_mode"),
            "selected_scenario_name": active_scoreboard.get("selected_scenario_name"),
            "policy_gate_status": active_scoreboard.get("policy_gate_status"),
            "active_next_kpi": next_kpi,
        },
        "checkpoint_summary": checkpoint_summary,
        "inventory_rows": inventory_rows,
        "decision": decision,
        "axes": axis_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-json", type=Path, default=DEFAULT_CHECKPOINT_JSON)
    parser.add_argument("--active-scoreboard-json", type=Path, default=DEFAULT_ACTIVE_SCOREBOARD_JSON)
    parser.add_argument("--active-next-kpi-json", type=Path, default=DEFAULT_ACTIVE_NEXT_KPI_JSON)
    parser.add_argument("--designs-root", type=Path, default=DEFAULT_DESIGNS_ROOT)
    parser.add_argument("--runners-dir", type=Path, default=DEFAULT_RUNNERS_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_post_checkpoint_axes(
        checkpoint_readiness=_read_json(args.checkpoint_json.resolve()),
        active_scoreboard=_read_json(args.active_scoreboard_json.resolve()),
        active_next_kpi=_read_json(args.active_next_kpi_json.resolve()),
        designs_root=args.designs_root.resolve(),
        runners_dir=args.runners_dir.resolve(),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
