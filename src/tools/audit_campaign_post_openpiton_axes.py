#!/usr/bin/env python3
"""
Summarize the next family-expansion axis after the OpenPiton first surface has
been accepted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_OPENPITON_ACCEPTANCE_JSON = REPO_ROOT / "work" / "campaign_openpiton_first_surface_acceptance_gate.json"
DEFAULT_XIANGSHAN_STATUS_JSON = REPO_ROOT / "work" / "campaign_xiangshan_first_surface_status.json"
DEFAULT_DESIGNS_ROOT = REPO_ROOT / "third_party" / "rtlmeter" / "designs"
DEFAULT_RUNNERS_DIR = REPO_ROOT / "src" / "runners"
DEFAULT_READINESS_DIR = REPO_ROOT / "output" / "family_readiness"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_post_openpiton_axes.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_inventory_family(raw_family: str) -> str:
    if raw_family.startswith("XuanTie-"):
        return "XuanTie"
    if raw_family.startswith("VeeR-"):
        return "VeeR"
    return raw_family


def _family_slug(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch.isalnum())


def _runner_support_for_family(runners_dir: Path, family_name: str) -> dict[str, Any]:
    slug = _family_slug(family_name)
    stock_runner = runners_dir / f"run_{slug}_stock_hybrid_validation.py"
    baseline_runner = runners_dir / f"run_{slug}_cpu_baseline_validation.py"
    comparison_runner = runners_dir / f"run_{slug}_time_to_threshold_comparison.py"
    family_runner = runners_dir / f"run_{slug}_gpu_toggle_validation.py"
    trio_count = sum(
        int(path.exists()) for path in (stock_runner, baseline_runner, comparison_runner)
    )
    if trio_count == 3:
        return {
            "kind": "campaign_trio",
            "score": 3,
            "paths": [str(path.resolve()) for path in (stock_runner, baseline_runner, comparison_runner)],
        }
    if family_runner.exists():
        return {"kind": "family_runner", "score": 2, "paths": [str(family_runner.resolve())]}
    if trio_count > 0:
        return {
            "kind": "partial_campaign_trio",
            "score": 1,
            "paths": [
                str(path.resolve())
                for path in (stock_runner, baseline_runner, comparison_runner)
                if path.exists()
            ],
        }
    return {"kind": "none", "score": 0, "paths": []}


def _readiness_support_for_family(readiness_dir: Path, family_name: str) -> dict[str, Any]:
    slug = _family_slug(family_name)
    md_path = readiness_dir / f"{slug}_gpu_toggle_readiness.md"
    json_path = readiness_dir / f"{slug}_gpu_toggle_readiness.json"
    plan_path = readiness_dir / f"{slug}_gpu_toggle_enablement_plan.md"
    md_text = md_path.read_text(encoding="utf-8", errors="replace").lower() if md_path.is_file() else ""
    readiness_score = 0
    readiness_kind = "none"
    if "actual_gpu_validated" in md_text or "actual-gpu validated" in md_text:
        readiness_score = 3
        readiness_kind = "actual_gpu_validated"
    elif "tier2_abc_completed" in md_text or "ready_for_gpu_toggle" in md_text or md_path.is_file():
        readiness_score = 1
        readiness_kind = "readiness_artifact_only"
    return {
        "kind": readiness_kind,
        "score": readiness_score,
        "readiness_md_path": str(md_path.resolve()) if md_path.is_file() else None,
        "readiness_json_path": str(json_path.resolve()) if json_path.is_file() else None,
        "enablement_plan_path": str(plan_path.resolve()) if plan_path.is_file() else None,
    }


def _candidate_rows(*, designs_root: Path, runners_dir: Path, readiness_dir: Path, blocked_family: str | None) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for tb_path in sorted(designs_root.glob("*/**/*_gpu_cov_tb.sv")):
        relative = tb_path.relative_to(designs_root)
        raw_family = relative.parts[0]
        family_name = _normalize_inventory_family(raw_family)
        if family_name in {"OpenTitan", "XuanTie", "VeeR", "OpenPiton"}:
            continue
        row = grouped.setdefault(
            family_name,
            {"repo_family": family_name, "raw_family_dirs": set(), "tb_paths": []},
        )
        row["raw_family_dirs"].add(raw_family)
        row["tb_paths"].append(str(tb_path.resolve()))

    rows: list[dict[str, Any]] = []
    for family_name, row in sorted(grouped.items()):
        runner_support = _runner_support_for_family(runners_dir, family_name)
        readiness_support = _readiness_support_for_family(readiness_dir, family_name)
        blocked_current_branch = blocked_family == family_name
        rows.append(
            {
                "repo_family": family_name,
                "design_count": len(row["tb_paths"]),
                "raw_family_dirs": sorted(row["raw_family_dirs"]),
                "example_tb_paths": sorted(row["tb_paths"])[:3],
                "blocked_current_branch": blocked_current_branch,
                "runner_support": {
                    "kind": runner_support["kind"],
                    "paths": runner_support["paths"],
                },
                "readiness_support": {
                    "kind": readiness_support["kind"],
                    "readiness_md_path": readiness_support["readiness_md_path"],
                    "readiness_json_path": readiness_support["readiness_json_path"],
                    "enablement_plan_path": readiness_support["enablement_plan_path"],
                },
                "_sort_key": (
                    0 if blocked_current_branch else 1,
                    readiness_support["score"],
                    runner_support["score"],
                    len(row["tb_paths"]),
                    family_name,
                ),
            }
        )
    rows.sort(
        key=lambda item: (
            -item["_sort_key"][0],
            -item["_sort_key"][1],
            -item["_sort_key"][2],
            -item["_sort_key"][3],
            item["_sort_key"][4],
        )
    )
    for row in rows:
        row.pop("_sort_key", None)
    return rows


def build_axes(
    *,
    openpiton_acceptance_payload: dict[str, Any],
    xiangshan_status_payload: dict[str, Any] | None,
    designs_root: Path,
    runners_dir: Path,
    readiness_dir: Path,
) -> dict[str, Any]:
    acceptance_outcome = dict(openpiton_acceptance_payload.get("outcome") or {})
    xiangshan_outcome = dict((xiangshan_status_payload or {}).get("outcome") or {})
    blocked_family = None
    if str(xiangshan_outcome.get("status") or "") == "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family":
        blocked_family = "XiangShan"

    rows = _candidate_rows(
        designs_root=designs_root,
        runners_dir=runners_dir,
        readiness_dir=readiness_dir,
        blocked_family=blocked_family,
    )
    recommended_family = next((row["repo_family"] for row in rows if not row["blocked_current_branch"]), None)
    fallback_family = blocked_family or next(
        (
            row["repo_family"]
            for row in rows
            if row["repo_family"] != recommended_family
        ),
        None,
    )

    if str(acceptance_outcome.get("status") or "") != "accepted_selected_openpiton_first_surface_step":
        decision = {
            "status": "blocked_openpiton_not_yet_accepted",
            "reason": "the_next_post_openpiton_family_decision_requires_the_OpenPiton_default_gate_line_to_be_accepted_first",
            "recommended_next_task": acceptance_outcome.get("next_action") or "accept_selected_openpiton_first_surface_step",
        }
    elif recommended_family:
        decision = {
            "status": "decide_open_next_family_after_openpiton_acceptance",
            "reason": "OpenPiton_is_now_accepted_so_the_next_question_is_the_next_non_OpenPiton_family_to_open",
            "recommended_next_task": "open_the_next_post_openpiton_family",
            "recommended_family": recommended_family,
            "fallback_family": fallback_family,
        }
    else:
        decision = {
            "status": "revisit_blocked_or_historical_branches_after_openpiton_acceptance",
            "reason": "no_additional_post_openpiton_family_candidates_are_available_in_the_current_inventory",
            "recommended_next_task": "revisit_blocked_or_historical_branches",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_post_openpiton_axes",
        "accepted_openpiton_first_surface": {
            "status": acceptance_outcome.get("status"),
            "selected_family": acceptance_outcome.get("selected_family"),
            "selected_openpiton_profile_name": acceptance_outcome.get("selected_openpiton_profile_name"),
            "comparison_path": acceptance_outcome.get("comparison_path"),
            "speedup_ratio": acceptance_outcome.get("speedup_ratio"),
            "threshold_value": acceptance_outcome.get("threshold_value"),
        },
        "blocked_historical_family": {
            "family": blocked_family,
            "status": xiangshan_outcome.get("status"),
            "next_action": xiangshan_outcome.get("next_action"),
        },
        "candidate_families": rows,
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--openpiton-acceptance-json", type=Path, default=DEFAULT_OPENPITON_ACCEPTANCE_JSON)
    parser.add_argument("--xiangshan-status-json", type=Path, default=DEFAULT_XIANGSHAN_STATUS_JSON)
    parser.add_argument("--designs-root", type=Path, default=DEFAULT_DESIGNS_ROOT)
    parser.add_argument("--runners-dir", type=Path, default=DEFAULT_RUNNERS_DIR)
    parser.add_argument("--readiness-dir", type=Path, default=DEFAULT_READINESS_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    xiangshan_status_payload = (
        _read_json(args.xiangshan_status_json.resolve()) if args.xiangshan_status_json.resolve().is_file() else None
    )
    payload = build_axes(
        openpiton_acceptance_payload=_read_json(args.openpiton_acceptance_json.resolve()),
        xiangshan_status_payload=xiangshan_status_payload,
        designs_root=args.designs_root.resolve(),
        runners_dir=args.runners_dir.resolve(),
        readiness_dir=args.readiness_dir.resolve(),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
