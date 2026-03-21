#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_int(value: Any) -> int:
    return int(value or 0)


def _safe_float(value: Any) -> float:
    return float(value or 0.0)


def _safe_div(num: float, den: float) -> float:
    return 0.0 if den == 0.0 else float(num) / float(den)


def _frontier_rows(summary_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(summary_payload.get("cases") or [])
    if rows:
        return rows
    return list(summary_payload.get("ranking") or [])


def _mean(values: list[float]) -> float:
    return _safe_div(sum(values), float(len(values)))


def _truth_alive(row: dict[str, Any]) -> int:
    return int(str(row.get("truth_gate_status") or "") == "truth_alive")


def _unique_nonempty(values: list[str]) -> list[str]:
    return sorted({value for value in values if str(value or "").strip()})


def _campaign_union_count(summary_payload: dict[str, Any]) -> int:
    path = Path(str(summary_payload.get("campaign_merge_view_json") or "")).expanduser()
    if not path.exists():
        return 0
    payload = _load_json(path)
    return len(list(payload.get("active_region_union") or []))


def _mode_axes(summary_payload: dict[str, Any]) -> dict[str, Any]:
    best = dict(summary_payload.get("best_case") or {})
    execution = dict(summary_payload.get("execution") or {})
    frontier = _frontier_rows(summary_payload)

    points_total = max(1, _safe_int(best.get("real_subset_points_total") or best.get("points_total")))
    best_hit = _safe_int(best.get("real_subset_points_hit") or best.get("points_hit"))
    best_active_regions = _safe_int(best.get("active_region_count"))
    best_dead_regions = _safe_int(best.get("dead_region_count"))
    best_target_activated = _safe_int(best.get("target_region_activated"))
    best_cps = _safe_float(best.get("real_subset_coverage_per_second") or best.get("coverage_per_second"))
    wall_clock = _safe_float(execution.get("wall_clock_s"))
    total_candidate_space = _safe_int(summary_payload.get("total_candidate_space"))
    evaluated_case_count = _safe_int(summary_payload.get("evaluated_case_count"))

    frontier_hit_frac = [
        _safe_div(float(_safe_int(row.get("real_subset_points_hit") or row.get("points_hit"))), float(points_total))
        for row in frontier
    ]
    frontier_active_regions = [_safe_float(row.get("active_region_count")) for row in frontier]
    frontier_dead_regions = [_safe_float(row.get("dead_region_count")) for row in frontier]
    frontier_target_activated = [_safe_float(row.get("target_region_activated")) for row in frontier]
    frontier_truth_alive = [_truth_alive(row) for row in frontier]
    frontier_cps = [
        _safe_float(row.get("real_subset_coverage_per_second") or row.get("coverage_per_second"))
        for row in frontier
    ]
    frontier_target_regions = _unique_nonempty([str(row.get("target_region") or "") for row in frontier])
    frontier_variants = _unique_nonempty([str(row.get("variant_name") or "") for row in frontier])

    return {
        "slice_name": str(summary_payload.get("slice_name") or ""),
        "total_candidate_space": total_candidate_space,
        "evaluated_case_count": evaluated_case_count,
        "launch_count": _safe_int(execution.get("launch_count")),
        "wall_clock_s": wall_clock,
        "candidates_per_second": _safe_div(float(total_candidate_space), wall_clock),
        "best_hit": best_hit,
        "best_points_total": points_total,
        "best_hit_fraction": _safe_div(float(best_hit), float(points_total)),
        "best_active_region_count": best_active_regions,
        "best_dead_region_count": best_dead_regions,
        "best_target_region_activated": best_target_activated,
        "campaign_active_region_union_count": _campaign_union_count(summary_payload),
        "best_case_coverage_per_second": best_cps,
        "frontier_size": len(frontier),
        "frontier_mean_hit_fraction": _mean(frontier_hit_frac),
        "frontier_mean_active_region_count": _mean(frontier_active_regions),
        "frontier_mean_dead_region_count": _mean(frontier_dead_regions),
        "frontier_target_activation_rate": _mean(frontier_target_activated),
        "frontier_truth_alive_rate": _mean([float(v) for v in frontier_truth_alive]),
        "frontier_mean_coverage_per_second": _mean(frontier_cps),
        "frontier_unique_target_regions": frontier_target_regions,
        "frontier_unique_variant_count": len(frontier_variants),
        "frontier_unique_target_region_count": len(frontier_target_regions),
    }


def _delta_axes(plain: dict[str, Any], grpo: dict[str, Any]) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    for key in (
        "wall_clock_s",
        "candidates_per_second",
        "best_hit_fraction",
        "best_active_region_count",
        "best_dead_region_count",
        "best_target_region_activated",
        "campaign_active_region_union_count",
        "best_case_coverage_per_second",
        "frontier_mean_hit_fraction",
        "frontier_mean_active_region_count",
        "frontier_mean_dead_region_count",
        "frontier_target_activation_rate",
        "frontier_truth_alive_rate",
        "frontier_mean_coverage_per_second",
        "frontier_unique_variant_count",
        "frontier_unique_target_region_count",
    ):
        delta[f"{key}_delta"] = _safe_float(grpo.get(key)) - _safe_float(plain.get(key))
    return delta


def _verdict(plain: dict[str, Any], grpo: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    diversity_regression = (
        grpo["frontier_unique_target_region_count"] < plain["frontier_unique_target_region_count"]
        or grpo["frontier_unique_variant_count"] < plain["frontier_unique_variant_count"]
    )
    target_focus_without_breadth = (
        diversity_regression
        and (
            grpo["frontier_mean_hit_fraction"] >= plain["frontier_mean_hit_fraction"]
            or grpo["frontier_mean_active_region_count"] >= plain["frontier_mean_active_region_count"]
            or grpo["frontier_target_activation_rate"] >= plain["frontier_target_activation_rate"]
        )
    )
    ceiling_gain = (
        grpo["best_hit_fraction"] > plain["best_hit_fraction"]
        or grpo["campaign_active_region_union_count"] > plain["campaign_active_region_union_count"]
        or grpo["best_target_region_activated"] > plain["best_target_region_activated"]
    )
    frontier_gain = (
        not diversity_regression
        and (
            grpo["frontier_mean_hit_fraction"] > plain["frontier_mean_hit_fraction"]
            or grpo["frontier_mean_active_region_count"] > plain["frontier_mean_active_region_count"]
            or grpo["frontier_target_activation_rate"] > plain["frontier_target_activation_rate"]
            or grpo["frontier_unique_target_region_count"] > plain["frontier_unique_target_region_count"]
        )
    )
    efficiency_gain = grpo["wall_clock_s"] < plain["wall_clock_s"] or grpo["candidates_per_second"] > plain["candidates_per_second"]
    throughput_only = (
        not ceiling_gain
        and not frontier_gain
        and efficiency_gain
    )
    if ceiling_gain:
        class_label = "ceiling_gain"
    elif frontier_gain:
        class_label = "frontier_quality_gain"
    elif throughput_only:
        class_label = "throughput_only_gain"
    else:
        class_label = "no_meaningful_gain"
    return {
        "ceiling_gain": ceiling_gain,
        "frontier_gain": frontier_gain,
        "efficiency_gain": efficiency_gain,
        "throughput_only_gain": throughput_only,
        "target_focus_without_breadth": target_focus_without_breadth,
        "classification": class_label,
        "same_total_candidate_space": plain["total_candidate_space"] == grpo["total_candidate_space"],
        "same_evaluated_case_count": plain["evaluated_case_count"] == grpo["evaluated_case_count"],
    }


def build_payload(*, plain_summary: Path, grpo_summary: Path) -> dict[str, Any]:
    plain_summary_payload = _load_json(plain_summary)
    grpo_summary_payload = _load_json(grpo_summary)
    plain_axes = _mode_axes(plain_summary_payload)
    grpo_axes = _mode_axes(grpo_summary_payload)
    delta_axes = _delta_axes(plain_axes, grpo_axes)
    verdict = _verdict(plain_axes, grpo_axes, delta_axes)
    return {
        "schema_version": "grpo-ab-evaluation-axes-v1",
        "slice_name": str(plain_axes.get("slice_name") or grpo_axes.get("slice_name") or ""),
        "plain_summary_json": str(plain_summary),
        "grpo_summary_json": str(grpo_summary),
        "plain": plain_axes,
        "grpo": grpo_axes,
        "delta": delta_axes,
        "verdict": verdict,
    }


def _markdown(payload: dict[str, Any]) -> str:
    plain = payload["plain"]
    grpo = payload["grpo"]
    verdict = payload["verdict"]
    lines = [
        f"# GRPO A/B Evaluation Axes: {payload['slice_name']}",
        "",
        "## Summary",
        "",
        f"- classification: `{verdict['classification']}`",
        f"- same total candidate space: `{verdict['same_total_candidate_space']}`",
        f"- same evaluated case count: `{verdict['same_evaluated_case_count']}`",
        "",
        "## Axes",
        "",
        "| mode | wall clock (s) | cand/s | best hit frac | union count | target activated | frontier mean hit frac | frontier mean active regions | frontier target activation rate | best cps |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| plain | {plain['wall_clock_s']:.4f} | {plain['candidates_per_second']:.4f} | {plain['best_hit_fraction']:.4f} | {plain['campaign_active_region_union_count']} | {plain['best_target_region_activated']} | {plain['frontier_mean_hit_fraction']:.4f} | {plain['frontier_mean_active_region_count']:.4f} | {plain['frontier_target_activation_rate']:.4f} | {plain['best_case_coverage_per_second']:.4f} |",
        f"| GRPO | {grpo['wall_clock_s']:.4f} | {grpo['candidates_per_second']:.4f} | {grpo['best_hit_fraction']:.4f} | {grpo['campaign_active_region_union_count']} | {grpo['best_target_region_activated']} | {grpo['frontier_mean_hit_fraction']:.4f} | {grpo['frontier_mean_active_region_count']:.4f} | {grpo['frontier_target_activation_rate']:.4f} | {grpo['best_case_coverage_per_second']:.4f} |",
        "",
        "## Verdict",
        "",
        f"- ceiling gain: `{verdict['ceiling_gain']}`",
        f"- frontier gain: `{verdict['frontier_gain']}`",
        f"- efficiency gain: `{verdict['efficiency_gain']}`",
        f"- throughput-only gain: `{verdict['throughput_only_gain']}`",
        f"- target focus without breadth: `{verdict['target_focus_without_breadth']}`",
    ]
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Re-evaluate GRPO A/B with richer axes than final best hit only.")
    parser.add_argument("--plain-summary", required=True)
    parser.add_argument("--grpo-summary", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    return parser.parse_args()


def main() -> int:
    ns = parse_args()
    payload = build_payload(
        plain_summary=Path(ns.plain_summary).expanduser().resolve(),
        grpo_summary=Path(ns.grpo_summary).expanduser().resolve(),
    )
    json_out = Path(ns.json_out).expanduser().resolve()
    md_out = Path(ns.md_out).expanduser().resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_out.write_text(_markdown(payload), encoding="utf-8")
    print(json_out)
    print(md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
