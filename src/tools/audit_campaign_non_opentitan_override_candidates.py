#!/usr/bin/env python3
"""
Rank concrete single-surface override candidates for the current non-OpenTitan
entry recommendation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_ENTRY_READINESS_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_entry_readiness.json"
DEFAULT_VALIDATION_DIR = REPO_ROOT / "output" / "validation"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_non_opentitan_override_candidates.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _family_matches_design(family: str, design: str) -> bool:
    normalized_family = (family or "").strip().lower()
    normalized_design = (design or "").strip().lower()
    if not normalized_family or not normalized_design:
        return False
    return normalized_design == normalized_family or normalized_design.startswith(f"{normalized_family}-")


def _slug(text: str) -> str:
    slug = []
    for ch in text:
        if ch.isalnum():
            slug.append(ch.lower())
        else:
            slug.append("_")
    collapsed = "".join(slug)
    while "__" in collapsed:
        collapsed = collapsed.replace("__", "_")
    return collapsed.strip("_")


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return _read_json(path)
    except json.JSONDecodeError:
        return None


def _coerce_threshold_value(payload: dict[str, Any] | None) -> int | None:
    if not payload:
        return None
    threshold = dict(payload.get("campaign_threshold") or {})
    raw_value = threshold.get("value")
    if isinstance(raw_value, bool):
        return int(raw_value)
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, float):
        return int(raw_value)
    return None


def _best_candidate_variant(*, slug: str, validation_dir: Path) -> dict[str, Any]:
    variants: list[dict[str, Any]] = []
    pattern = f"{slug}_time_to_threshold_comparison_threshold*.json"
    for comparison_path in sorted(validation_dir.glob(pattern)):
        payload = _read_json_if_exists(comparison_path)
        if not payload:
            continue
        comparison_ready = bool(payload.get("comparison_ready"))
        hybrid_wins = bool(comparison_ready and payload.get("winner") == "hybrid")
        speedup_ratio = payload.get("speedup_ratio")
        if not isinstance(speedup_ratio, (int, float)):
            speedup_ratio = None
        threshold_value = _coerce_threshold_value(payload)
        variants.append(
            {
                "comparison_path": str(comparison_path.resolve()),
                "comparison_ready": comparison_ready,
                "hybrid_wins": hybrid_wins,
                "speedup_ratio": float(speedup_ratio) if speedup_ratio is not None else None,
                "threshold_value": threshold_value,
            }
        )

    if not variants:
        return {
            "candidate_variant_count": 0,
            "candidate_ready_variant_count": 0,
            "best_candidate_variant_path": None,
            "best_candidate_threshold_value": None,
            "best_candidate_speedup_ratio": None,
            "best_candidate_hybrid_wins": False,
            "best_candidate_comparison_ready": False,
        }

    variants.sort(
        key=lambda row: (
            0 if row["hybrid_wins"] else 1,
            0 if row["comparison_ready"] else 1,
            -(row["threshold_value"] if isinstance(row["threshold_value"], int) else -1),
            -(row["speedup_ratio"] if isinstance(row["speedup_ratio"], float) else -1.0),
            row["comparison_path"],
        )
    )
    best = variants[0]
    return {
        "candidate_variant_count": len(variants),
        "candidate_ready_variant_count": sum(1 for row in variants if row["comparison_ready"]),
        "best_candidate_variant_path": best["comparison_path"],
        "best_candidate_threshold_value": best["threshold_value"],
        "best_candidate_speedup_ratio": best["speedup_ratio"],
        "best_candidate_hybrid_wins": best["hybrid_wins"],
        "best_candidate_comparison_ready": best["comparison_ready"],
    }


def _summarize_trio(*, design: str, validation_dir: Path) -> dict[str, Any]:
    slug = _slug(design)
    stock_path = validation_dir / f"{slug}_stock_hybrid_validation.json"
    baseline_path = validation_dir / f"{slug}_cpu_baseline_validation.json"
    comparison_path = validation_dir / f"{slug}_time_to_threshold_comparison.json"
    stock_payload = _read_json_if_exists(stock_path)
    baseline_payload = _read_json_if_exists(baseline_path)
    comparison_payload = _read_json_if_exists(comparison_path)
    stock_ok = bool(stock_payload and stock_payload.get("status") == "ok")
    baseline_ok = bool(baseline_payload and baseline_payload.get("status") == "ok")
    comparison_status_ok = bool(comparison_payload and comparison_payload.get("status") == "ok")
    comparison_ready = bool(comparison_status_ok and comparison_payload.get("comparison_ready"))
    hybrid_wins = bool(comparison_ready and comparison_payload.get("winner") == "hybrid")
    speedup_ratio = comparison_payload.get("speedup_ratio") if comparison_payload else None
    if not isinstance(speedup_ratio, (int, float)):
        speedup_ratio = None
    return {
        "stock_hybrid_path": str(stock_path.resolve()),
        "stock_hybrid_ok": stock_ok,
        "cpu_baseline_path": str(baseline_path.resolve()),
        "cpu_baseline_ok": baseline_ok,
        "comparison_path": str(comparison_path.resolve()),
        "comparison_status_ok": comparison_status_ok,
        "comparison_ready": comparison_ready,
        "hybrid_wins": hybrid_wins,
        "speedup_ratio": float(speedup_ratio) if speedup_ratio is not None else None,
        "validated_trio_ready": stock_ok and baseline_ok and comparison_ready,
        **_best_candidate_variant(slug=slug, validation_dir=validation_dir),
    }


def build_override_candidates(*, readiness_payload: dict[str, Any], validation_dir: Path = DEFAULT_VALIDATION_DIR) -> dict[str, Any]:
    family = str(readiness_payload.get("recommended_family") or "")
    entry_mode = str(readiness_payload.get("recommended_entry_mode") or "")
    readiness = str((readiness_payload.get("decision") or {}).get("readiness") or "")
    bootstrap_summary = dict(readiness_payload.get("single_surface_bootstrap_summary") or {})

    raw_candidates = list(bootstrap_summary.get("candidates") or [])
    ranked: list[dict[str, Any]] = []
    for candidate in raw_candidates:
        path = Path(str(candidate.get("path") or "")).expanduser()
        payload: dict[str, Any] = {}
        if path.is_file():
            try:
                payload = _read_json(path)
            except json.JSONDecodeError:
                payload = {}
        design = str(candidate.get("design") or payload.get("design") or "")
        if family and not _family_matches_design(family, design):
            continue
        row = {
            "design": design,
            "config": str(candidate.get("config") or payload.get("config") or ""),
            "path": str(path.resolve()) if path else str(path),
            "ready": bool(candidate.get("ready")),
            "status": str(candidate.get("status") or payload.get("status") or ""),
            "returncode": int(candidate.get("returncode") or payload.get("returncode") or 0),
            "verilog_source_count": int(payload.get("verilog_source_count") or 0),
            "verilog_include_count": int(payload.get("verilog_include_count") or 0),
            "top_module": str(payload.get("top_module") or ""),
        }
        row.update(_summarize_trio(design=design, validation_dir=validation_dir))
        ranked.append(row)

    ranked.sort(
        key=lambda row: (
            0 if row["hybrid_wins"] else 1,
            0 if row["best_candidate_hybrid_wins"] else 1,
            0 if row["comparison_ready"] else 1,
            0 if row["best_candidate_comparison_ready"] else 1,
            0 if row["ready"] else 1,
            row["verilog_source_count"] if row["verilog_source_count"] else 10**9,
            row["design"],
        )
    )

    if not family or entry_mode != "family_pilot":
        decision = {
            "status": "no_family_override_context",
            "reason": "entry_readiness_does_not_point_to_a_family_pilot_context",
            "recommended_design": None,
            "fallback_design": None,
        }
    elif readiness not in {
        "legacy_family_pilot_failed_but_single_surface_override_ready",
        "family_pilot_blocked_but_single_surface_override_ready",
    }:
        decision = {
            "status": "override_not_currently_recommended",
            "reason": "entry_readiness_does_not_report_a_ready_single_surface_override_path",
            "recommended_design": None,
            "fallback_design": None,
        }
    elif not ranked:
        decision = {
            "status": "no_ready_override_candidates",
            "reason": "no_bootstrap_summary_candidates_match_the_recommended_family",
            "recommended_design": None,
            "fallback_design": None,
        }
    else:
        recommended = ranked[0]
        fallback = ranked[1] if len(ranked) > 1 else None
        if recommended["hybrid_wins"]:
            decision = {
                "status": "recommend_validated_single_surface_candidate",
                "reason": "checked_in_comparison_ready_hybrid_win_exists_for_the_recommended_design",
                "recommended_design": recommended["design"],
                "fallback_design": fallback["design"] if fallback else None,
            }
        else:
            decision = {
                "status": "recommend_single_surface_override_candidate",
                "reason": "ready_bootstrap_candidates_exist_and_the_smallest_ready_compile_should_go_first",
                "recommended_design": recommended["design"],
                "fallback_design": fallback["design"] if fallback else None,
            }

    return {
        "schema_version": 1,
        "scope": "campaign_non_opentitan_override_candidates",
        "recommended_family": family or None,
        "recommended_entry_mode": entry_mode or None,
        "entry_readiness": readiness or None,
        "ranked_candidates": ranked,
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry-readiness-json", type=Path, default=DEFAULT_ENTRY_READINESS_JSON)
    parser.add_argument("--validation-dir", type=Path, default=DEFAULT_VALIDATION_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_override_candidates(
        readiness_payload=_read_json(args.entry_readiness_json.resolve()),
        validation_dir=args.validation_dir.resolve(),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
