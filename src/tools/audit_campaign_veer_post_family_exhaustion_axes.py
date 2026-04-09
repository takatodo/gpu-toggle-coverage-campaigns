#!/usr/bin/env python3
"""
Summarize the next non-VeeR expansion axis after the final VeeR same-family
step has been accepted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_VEER_ACCEPTANCE_JSON = REPO_ROOT / "work" / "campaign_veer_final_same_family_acceptance_gate.json"
DEFAULT_DESIGNS_ROOT = REPO_ROOT / "third_party" / "rtlmeter" / "designs"
DEFAULT_RUNNERS_DIR = REPO_ROOT / "src" / "runners"
DEFAULT_READINESS_DIR = REPO_ROOT / "output" / "family_readiness"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_veer_post_family_exhaustion_axes.json"


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
    family_runner = runners_dir / f"run_{slug}_family_gpu_toggle_validation.py"
    single_runner = runners_dir / f"run_{slug}_gpu_toggle_validation.py"
    if family_runner.exists():
        return {"kind": "family_runner", "path": str(family_runner.resolve()), "score": 2}
    if single_runner.exists():
        return {"kind": "single_runner", "path": str(single_runner.resolve()), "score": 1}
    return {"kind": "none", "path": None, "score": 0}


def _readiness_support_for_family(readiness_dir: Path, family_name: str) -> dict[str, Any]:
    slug = _family_slug(family_name)
    md_path = readiness_dir / f"{slug}_gpu_toggle_readiness.md"
    json_path = readiness_dir / f"{slug}_gpu_toggle_readiness.json"
    plan_path = readiness_dir / f"{slug}_gpu_toggle_enablement_plan.md"
    md_text = md_path.read_text(encoding="utf-8", errors="replace").lower() if md_path.is_file() else ""
    readiness_score = 0
    readiness_kind = "none"
    if "actual_gpu_validated" in md_text or "actual-gpu validated" in md_text:
        readiness_score = 2
        readiness_kind = "actual_gpu_validated"
    elif md_path.is_file() or json_path.is_file() or plan_path.is_file():
        readiness_score = 1
        readiness_kind = "readiness_artifact_only"
    return {
        "kind": readiness_kind,
        "score": readiness_score,
        "readiness_md_path": str(md_path.resolve()) if md_path.is_file() else None,
        "readiness_json_path": str(json_path.resolve()) if json_path.is_file() else None,
        "enablement_plan_path": str(plan_path.resolve()) if plan_path.is_file() else None,
    }


def _family_rows(*, designs_root: Path, runners_dir: Path, readiness_dir: Path) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for tb_path in sorted(designs_root.glob("*/**/*_gpu_cov_tb.sv")):
        relative = tb_path.relative_to(designs_root)
        raw_family = relative.parts[0]
        family_name = _normalize_inventory_family(raw_family)
        if family_name in {"OpenTitan", "XuanTie", "VeeR"}:
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
        raw_dirs = sorted(row["raw_family_dirs"])
        tb_paths = sorted(row["tb_paths"])
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
                "readiness_support": {
                    "kind": readiness_support["kind"],
                    "readiness_md_path": readiness_support["readiness_md_path"],
                    "readiness_json_path": readiness_support["readiness_json_path"],
                    "enablement_plan_path": readiness_support["enablement_plan_path"],
                },
                "_sort_key": (
                    runner_support["score"],
                    readiness_support["score"],
                    len(tb_paths),
                    family_name,
                ),
            }
        )
    rows.sort(key=lambda item: (-item["_sort_key"][0], -item["_sort_key"][1], -item["_sort_key"][2], item["_sort_key"][3]))
    for row in rows:
        row.pop("_sort_key", None)
    return rows


def build_axes(
    *,
    veer_final_same_family_acceptance_payload: dict[str, Any],
    designs_root: Path,
    runners_dir: Path,
    readiness_dir: Path,
) -> dict[str, Any]:
    acceptance_outcome = dict(veer_final_same_family_acceptance_payload.get("outcome") or {})
    rows = _family_rows(designs_root=designs_root, runners_dir=runners_dir, readiness_dir=readiness_dir)
    recommended_family = rows[0]["repo_family"] if rows else None
    fallback_family = rows[1]["repo_family"] if len(rows) > 1 else None

    if str(acceptance_outcome.get("status") or "") != "accepted_selected_veer_final_same_family_step":
        decision = {
            "status": "blocked_veer_family_not_yet_exhausted",
            "reason": "the_next_non_veer_family_decision_requires_the_final_VeeR_same-family_step_to_be_accepted_first",
            "recommended_next_task": acceptance_outcome.get("next_action") or "accept_selected_veer_final_same_family_step",
        }
    elif rows:
        decision = {
            "status": "decide_open_next_non_veer_family_after_veer_exhaustion",
            "reason": "the_known_VeeR_ready_candidates_are_exhausted_under_the_current_accepted_line_so_the_next_question_is_the_next_non_VeeR_family",
            "recommended_next_task": "open_the_next_non_veer_family",
            "recommended_family": recommended_family,
            "fallback_family": fallback_family,
        }
    else:
        decision = {
            "status": "decide_revisit_blocked_debug_branches_after_veer_exhaustion",
            "reason": "no_additional_non_veer_gpu_cov_inventory_is_detected_after_the_final_VeeR_step",
            "recommended_next_task": "revisit_blocked_debug_branches",
        }

    return {
        "schema_version": 1,
        "scope": "campaign_veer_post_family_exhaustion_axes",
        "accepted_veer_final_same_family_step": {
            "status": acceptance_outcome.get("status"),
            "selected_design": acceptance_outcome.get("selected_design"),
            "selected_veer_final_same_family_profile_name": acceptance_outcome.get(
                "selected_veer_final_same_family_profile_name"
            ),
            "comparison_path": acceptance_outcome.get("comparison_path"),
            "speedup_ratio": acceptance_outcome.get("speedup_ratio"),
            "candidate_threshold_value": acceptance_outcome.get("candidate_threshold_value"),
        },
        "non_veer_family_candidates": rows,
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--veer-final-same-family-acceptance-json",
        type=Path,
        default=DEFAULT_VEER_ACCEPTANCE_JSON,
    )
    parser.add_argument("--designs-root", type=Path, default=DEFAULT_DESIGNS_ROOT)
    parser.add_argument("--runners-dir", type=Path, default=DEFAULT_RUNNERS_DIR)
    parser.add_argument("--readiness-dir", type=Path, default=DEFAULT_READINESS_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_axes(
        veer_final_same_family_acceptance_payload=_read_json(args.veer_final_same_family_acceptance_json.resolve()),
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
