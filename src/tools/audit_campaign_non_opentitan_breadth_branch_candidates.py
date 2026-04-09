#!/usr/bin/env python3
"""
Compare the ready post-E906 non-OpenTitan breadth branches and recommend
whether to continue inside XuanTie or open the fallback family first.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_BREADTH_AXES_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_breadth_axes.json"
DEFAULT_BREADTH_PROFILES_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_breadth_profiles.json"
DEFAULT_DESIGNS_ROOT = REPO_ROOT / "third_party" / "rtlmeter" / "designs"
DEFAULT_RUNNERS_DIR = REPO_ROOT / "src" / "runners"
DEFAULT_VALIDATION_DIR = REPO_ROOT / "output" / "validation"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_non_opentitan_breadth_branch_candidates.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return _read_json(path)


def _normalize_design_name(name: str) -> str:
    normalized = []
    for char in name:
        if char.isalnum():
            normalized.append(char.lower())
        else:
            normalized.append("_")
    return "".join(normalized).strip("_")


def _read_line_count(path: Path) -> int | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def _extract_comparison_row(path: Path) -> dict[str, Any] | None:
    payload = _read_optional_json(path)
    if payload is None:
        return None
    threshold = dict(payload.get("campaign_threshold") or {})
    return {
        "path": str(path.resolve()),
        "comparison_ready": bool(payload.get("comparison_ready")),
        "winner": payload.get("winner"),
        "speedup_ratio": payload.get("speedup_ratio"),
        "threshold_kind": threshold.get("kind"),
        "threshold_value": threshold.get("value"),
        "status": payload.get("status"),
    }


def _build_design_validation_summary(*, stem: str, validation_dir: Path) -> dict[str, Any]:
    default_path = validation_dir / f"{stem}_time_to_threshold_comparison.json"
    comparison_candidates = sorted(validation_dir.glob(f"{stem}_time_to_threshold_comparison*.json"))
    comparison_rows = [
        row
        for row in (_extract_comparison_row(path) for path in comparison_candidates)
        if row is not None
    ]
    ready_hybrid_rows = [
        row
        for row in comparison_rows
        if bool(row.get("comparison_ready")) and str(row.get("winner")) == "hybrid"
    ]
    default_row = next((row for row in comparison_rows if row.get("path") == str(default_path.resolve())), None)
    best_ready_row = None
    if ready_hybrid_rows:
        best_ready_row = max(
            ready_hybrid_rows,
            key=lambda row: (
                row.get("path") != str(default_path.resolve()),
                float(row.get("speedup_ratio") or 0.0),
            ),
        )

    validated_line_kind = "no_comparison_artifact"
    if default_row and bool(default_row.get("comparison_ready")) and str(default_row.get("winner")) == "hybrid":
        validated_line_kind = "default_gate_hybrid_win"
    elif best_ready_row:
        validated_line_kind = "candidate_only_hybrid_win"
    elif comparison_rows:
        validated_line_kind = "comparison_exists_but_not_ready"

    return {
        "default_comparison_path": str(default_path.resolve()),
        "default_comparison_exists": default_row is not None,
        "default_comparison_ready": bool(default_row and default_row.get("comparison_ready")),
        "default_winner": default_row.get("winner") if default_row else None,
        "default_speedup_ratio": default_row.get("speedup_ratio") if default_row else None,
        "default_threshold_value": default_row.get("threshold_value") if default_row else None,
        "comparison_rows": comparison_rows,
        "comparison_count": len(comparison_rows),
        "ready_hybrid_win_count": len(ready_hybrid_rows),
        "best_ready_comparison_path": best_ready_row.get("path") if best_ready_row else None,
        "best_ready_speedup_ratio": best_ready_row.get("speedup_ratio") if best_ready_row else None,
        "best_ready_threshold_value": best_ready_row.get("threshold_value") if best_ready_row else None,
        "validated_line_kind": validated_line_kind,
    }


def _build_same_family_candidate(
    *,
    profile_name: str,
    family: str,
    candidate_designs: list[str],
    designs_root: Path,
    runners_dir: Path,
    validation_dir: Path,
) -> dict[str, Any]:
    design_rows: list[dict[str, Any]] = []
    for design in candidate_designs:
        stem = _normalize_design_name(design)
        runner_path = runners_dir / f"run_{stem}_gpu_toggle_validation.py"
        stock_hybrid_runner = runners_dir / f"run_{stem}_stock_hybrid_validation.py"
        cpu_baseline_runner = runners_dir / f"run_{stem}_cpu_baseline_validation.py"
        comparison_runner = runners_dir / f"run_{stem}_time_to_threshold_comparison.py"
        tb_path = designs_root / design / "src" / f"{stem}_gpu_cov_tb.sv"
        validation_summary = _build_design_validation_summary(stem=stem, validation_dir=validation_dir)
        design_rows.append(
            {
                "design": design,
                "runner_path": str(runner_path.resolve()),
                "runner_exists": runner_path.is_file(),
                "stock_hybrid_runner_path": str(stock_hybrid_runner.resolve()),
                "stock_hybrid_runner_exists": stock_hybrid_runner.is_file(),
                "cpu_baseline_runner_path": str(cpu_baseline_runner.resolve()),
                "cpu_baseline_runner_exists": cpu_baseline_runner.is_file(),
                "comparison_runner_path": str(comparison_runner.resolve()),
                "comparison_runner_exists": comparison_runner.is_file(),
                "gpu_cov_tb_path": str(tb_path.resolve()),
                "gpu_cov_tb_exists": tb_path.is_file(),
                "gpu_cov_tb_line_count": _read_line_count(tb_path),
                **validation_summary,
            }
        )

    family_runner = runners_dir / f"run_{family.lower()}_family_gpu_toggle_validation.py"
    ready_design_rows = [row for row in design_rows if row["runner_exists"] and row["gpu_cov_tb_exists"]]
    validated_default_rows = [
        row for row in ready_design_rows if row.get("validated_line_kind") == "default_gate_hybrid_win"
    ]
    validated_candidate_rows = [
        row for row in ready_design_rows if row.get("validated_line_kind") == "candidate_only_hybrid_win"
    ]
    recommended_first_design = None
    recommended_first_design_reason = None
    if validated_default_rows:
        sorted_rows = sorted(
            validated_default_rows,
            key=lambda row: (
                -(float(row.get("best_ready_speedup_ratio") or 0.0)),
                row["gpu_cov_tb_line_count"] is None,
                row["gpu_cov_tb_line_count"] or 0,
                str(row["design"]),
            ),
        )
        recommended_first_design = sorted_rows[0]["design"]
        recommended_first_design_reason = "default_gate_hybrid_win_already_exists"
    elif validated_candidate_rows:
        sorted_rows = sorted(
            validated_candidate_rows,
            key=lambda row: (
                -(float(row.get("best_ready_speedup_ratio") or 0.0)),
                row["gpu_cov_tb_line_count"] is None,
                row["gpu_cov_tb_line_count"] or 0,
                str(row["design"]),
            ),
        )
        recommended_first_design = sorted_rows[0]["design"]
        recommended_first_design_reason = "candidate_only_hybrid_win_already_exists"
    elif ready_design_rows:
        sorted_rows = sorted(
            ready_design_rows,
            key=lambda row: (
                row["gpu_cov_tb_line_count"] is None,
                row["gpu_cov_tb_line_count"] or 0,
                str(row["design"]),
            ),
        )
        recommended_first_design = sorted_rows[0]["design"]
        recommended_first_design_reason = "smallest_known_gpu_cov_tb_wrapper"

    if validated_default_rows or validated_candidate_rows:
        status = "same_family_validated_candidate_ready"
    elif ready_design_rows:
        status = "same_family_ready"
    else:
        status = "same_family_blocked"
    return {
        "profile_name": profile_name,
        "branch_mode": "continue_same_family",
        "family": family,
        "status": status,
        "candidate_designs": candidate_designs,
        "family_runner_path": str(family_runner.resolve()),
        "family_runner_exists": family_runner.is_file(),
        "design_rows": design_rows,
        "ready_design_count": len(ready_design_rows),
        "ready_designs": [str(row["design"]) for row in ready_design_rows],
        "validated_default_designs": [str(row["design"]) for row in validated_default_rows],
        "validated_candidate_designs": [str(row["design"]) for row in validated_candidate_rows],
        "recommended_first_design": recommended_first_design,
        "recommended_first_design_reason": recommended_first_design_reason,
    }


def _build_fallback_candidate(
    *,
    profile_name: str,
    family: str,
    designs_root: Path,
    runners_dir: Path,
) -> dict[str, Any]:
    family_designs = sorted(
        path.name
        for path in designs_root.iterdir()
        if path.is_dir() and path.name.startswith(f"{family}-")
    )
    family_runner = runners_dir / f"run_{family.lower()}_family_gpu_toggle_validation.py"
    design_runner_paths = sorted(
        path for path in runners_dir.glob(f"run_{family.lower()}_*_gpu_toggle_validation.py") if path.name != family_runner.name
    )
    status = "fallback_family_ready" if family_runner.is_file() else "fallback_family_blocked"
    return {
        "profile_name": profile_name,
        "branch_mode": "open_fallback_family",
        "family": family,
        "status": status,
        "family_designs": family_designs,
        "family_design_count": len(family_designs),
        "family_runner_path": str(family_runner.resolve()),
        "family_runner_exists": family_runner.is_file(),
        "design_runner_paths": [str(path.resolve()) for path in design_runner_paths],
        "design_runner_count": len(design_runner_paths),
        "legacy_family_runner_only": bool(family_runner.is_file() and not design_runner_paths),
    }


def build_branch_candidates(
    *,
    breadth_axes_payload: dict[str, Any],
    breadth_profiles_payload: dict[str, Any],
    designs_root: Path,
    runners_dir: Path,
    validation_dir: Path,
) -> dict[str, Any]:
    summary = dict(breadth_profiles_payload.get("summary") or {})
    ready_profile_names = [str(name) for name in summary.get("ready_profile_names") or [] if str(name)]
    accepted_baseline = dict(breadth_axes_payload.get("accepted_baseline") or {})
    family_axis = dict(breadth_axes_payload.get("recommended_family_axis") or {})

    candidate_rows: list[dict[str, Any]] = []
    same_family_candidate = None
    fallback_candidate = None

    if "xuantie_continue_same_family" in ready_profile_names:
        same_family_candidate = _build_same_family_candidate(
            profile_name="xuantie_continue_same_family",
            family=str(family_axis.get("recommended_family") or ""),
            candidate_designs=[
                str(design) for design in family_axis.get("remaining_same_family_designs") or [] if str(design)
            ],
            designs_root=designs_root,
            runners_dir=runners_dir,
            validation_dir=validation_dir,
        )
        candidate_rows.append(same_family_candidate)

    if "open_veer_fallback_family" in ready_profile_names:
        fallback_candidate = _build_fallback_candidate(
            profile_name="open_veer_fallback_family",
            family=str(family_axis.get("fallback_family") or ""),
            designs_root=designs_root,
            runners_dir=runners_dir,
        )
        candidate_rows.append(fallback_candidate)

    if same_family_candidate and same_family_candidate["status"] in {
        "same_family_ready",
        "same_family_validated_candidate_ready",
    }:
        if fallback_candidate and fallback_candidate["status"] == "fallback_family_ready":
            decision_reason = (
                "accepted_XuanTie_seed_and_breadth_exist_and_same_family_branch_already_has_a_validated_single_surface_candidate_while_the_fallback_family_is_only_family_runner_ready"
                if same_family_candidate["status"] == "same_family_validated_candidate_ready"
                else "accepted_XuanTie_seed_and_breadth_exist_and_same_family_design_specific_runners_are_ready_while_the_fallback_family_is_only_family_runner_ready"
            )
            decision = {
                "status": "recommend_same_family_first",
                "reason": decision_reason,
                "recommended_profile_name": "xuantie_continue_same_family",
                "fallback_profile_name": "open_veer_fallback_family",
                "recommended_first_design": same_family_candidate.get("recommended_first_design"),
            }
        else:
            decision = {
                "status": "recommend_same_family_only_ready_branch",
                "reason": "same_family_branch_is_ready_while_fallback_family_is_not_ready",
                "recommended_profile_name": "xuantie_continue_same_family",
                "recommended_first_design": same_family_candidate.get("recommended_first_design"),
            }
    elif fallback_candidate and fallback_candidate["status"] == "fallback_family_ready":
        decision = {
            "status": "recommend_fallback_family_first",
            "reason": "same_family_branch_is_not_ready_but_the_fallback_family_runner_is_available",
            "recommended_profile_name": "open_veer_fallback_family",
        }
    else:
        decision = {
            "status": "blocked_no_ready_post_e906_branch",
            "reason": "none_of_the_named_post_E906_non_OpenTitan_breadth_profiles_are_currently_ready",
            "recommended_profile_name": None,
        }

    return {
        "schema_version": 1,
        "scope": "campaign_non_opentitan_breadth_branch_candidates",
        "context": {
            "current_profile_name": summary.get("current_profile_name"),
            "selected_seed_design": accepted_baseline.get("selected_seed_design"),
            "selected_breadth_design": accepted_baseline.get("selected_breadth_design"),
            "selected_breadth_profile_name": accepted_baseline.get("selected_breadth_profile_name"),
        },
        "branch_candidates": candidate_rows,
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--breadth-axes-json", type=Path, default=DEFAULT_BREADTH_AXES_JSON)
    parser.add_argument("--breadth-profiles-json", type=Path, default=DEFAULT_BREADTH_PROFILES_JSON)
    parser.add_argument("--designs-root", type=Path, default=DEFAULT_DESIGNS_ROOT)
    parser.add_argument("--runners-dir", type=Path, default=DEFAULT_RUNNERS_DIR)
    parser.add_argument("--validation-dir", type=Path, default=DEFAULT_VALIDATION_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_branch_candidates(
        breadth_axes_payload=_read_json(args.breadth_axes_json.resolve()),
        breadth_profiles_payload=_read_json(args.breadth_profiles_json.resolve()),
        designs_root=args.designs_root.resolve(),
        runners_dir=args.runners_dir.resolve(),
        validation_dir=args.validation_dir.resolve(),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
