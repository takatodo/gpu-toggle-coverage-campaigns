#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            rows.append(json.loads(text))
    return rows


def _safe_float(value: Any) -> float:
    return float(value or 0.0)


def _mean(values: list[float]) -> float:
    return 0.0 if not values else sum(values) / float(len(values))


def _variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean_value = _mean(values)
    return sum((value - mean_value) ** 2 for value in values) / float(len(values))


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = _mean(xs)
    mean_y = _mean(ys)
    dx = [value - mean_x for value in xs]
    dy = [value - mean_y for value in ys]
    norm_x = math.sqrt(sum(value * value for value in dx))
    norm_y = math.sqrt(sum(value * value for value in dy))
    if norm_x == 0.0 or norm_y == 0.0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / (norm_x * norm_y)


def _case_metric(row: dict[str, Any], key: str) -> float:
    case_summary = dict(row.get("case_summary") or {})
    if key == "points_hit":
        return _safe_float(
            case_summary.get("real_subset_points_hit")
            or case_summary.get("points_hit")
        )
    if key == "points_total":
        return _safe_float(
            case_summary.get("real_subset_points_total")
            or case_summary.get("points_total")
        )
    return _safe_float(case_summary.get(key))


def _quartile_gap(rows: list[dict[str, Any]], metric_key: str) -> float | None:
    if len(rows) < 2:
        return None
    ordered = sorted(rows, key=lambda row: _safe_float(row.get("reward")))
    quartile_size = max(1, len(ordered) // 4)
    low_rows = ordered[:quartile_size]
    high_rows = ordered[-quartile_size:]
    low_mean = _mean([_case_metric(row, metric_key) for row in low_rows])
    high_mean = _mean([_case_metric(row, metric_key) for row in high_rows])
    return high_mean - low_mean


def _alignment_classification(
    *,
    reward_variance: float,
    hit_corr: float | None,
    active_corr: float | None,
    target_corr: float | None,
    dead_corr: float | None,
) -> str:
    if reward_variance == 0.0:
        return "constant_reward"
    if hit_corr is None and active_corr is None and target_corr is None and dead_corr is None:
        return "saturated_or_constant_dataset"
    if (
        hit_corr is not None and hit_corr >= 0.70
        and active_corr is not None and active_corr >= 0.70
        and dead_corr is not None and dead_corr <= -0.70
    ):
        return "breadth_aligned"
    if (
        target_corr is not None and target_corr >= 0.70
        and (hit_corr is None or hit_corr < 0.50)
        and (active_corr is None or active_corr < 0.50)
    ):
        return "target_only_aligned"
    return "weak_or_mixed_alignment"


def _dataset_payload(label: str, dataset_jsonl: Path) -> dict[str, Any]:
    rows = _load_rows(dataset_jsonl)
    rewards = [_safe_float(row.get("reward")) for row in rows]
    points_hit = [_case_metric(row, "points_hit") for row in rows]
    active_regions = [_case_metric(row, "active_region_count") for row in rows]
    target_activated = [_case_metric(row, "target_region_activated") for row in rows]
    dead_regions = [_case_metric(row, "dead_region_count") for row in rows]

    reward_variance = _variance(rewards)
    payload = {
        "label": label,
        "dataset_jsonl": str(dataset_jsonl),
        "record_count": len(rows),
        "reward_stats": {
            "min": min(rewards) if rewards else 0.0,
            "max": max(rewards) if rewards else 0.0,
            "mean": _mean(rewards),
            "variance": reward_variance,
        },
        "metric_stats": {
            "points_hit_min": min(points_hit) if points_hit else 0.0,
            "points_hit_max": max(points_hit) if points_hit else 0.0,
            "active_region_min": min(active_regions) if active_regions else 0.0,
            "active_region_max": max(active_regions) if active_regions else 0.0,
            "target_activated_min": min(target_activated) if target_activated else 0.0,
            "target_activated_max": max(target_activated) if target_activated else 0.0,
            "dead_region_min": min(dead_regions) if dead_regions else 0.0,
            "dead_region_max": max(dead_regions) if dead_regions else 0.0,
        },
        "correlations": {
            "reward_vs_points_hit": _pearson(rewards, points_hit),
            "reward_vs_active_region_count": _pearson(rewards, active_regions),
            "reward_vs_target_region_activated": _pearson(rewards, target_activated),
            "reward_vs_dead_region_count": _pearson(rewards, dead_regions),
        },
        "quartile_gap": {
            "points_hit": _quartile_gap(rows, "points_hit"),
            "active_region_count": _quartile_gap(rows, "active_region_count"),
            "target_region_activated": _quartile_gap(rows, "target_region_activated"),
            "dead_region_count": _quartile_gap(rows, "dead_region_count"),
        },
    }
    correlations = dict(payload["correlations"])
    payload["alignment_classification"] = _alignment_classification(
        reward_variance=reward_variance,
        hit_corr=correlations["reward_vs_points_hit"],
        active_corr=correlations["reward_vs_active_region_count"],
        target_corr=correlations["reward_vs_target_region_activated"],
        dead_corr=correlations["reward_vs_dead_region_count"],
    )
    return payload


def build_payload(dataset_jsonls: list[Path]) -> dict[str, Any]:
    datasets = [_dataset_payload(path.stem, path) for path in dataset_jsonls]
    class_counts: dict[str, int] = {}
    for dataset in datasets:
        label = str(dataset.get("alignment_classification") or "")
        class_counts[label] = int(class_counts.get(label) or 0) + 1
    return {
        "schema_version": "grpo-reward-alignment-v1",
        "dataset_count": len(datasets),
        "datasets": datasets,
        "classification_counts": class_counts,
    }


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.4f}"


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# GRPO Reward Alignment",
        "",
        "## Summary",
        "",
        f"- dataset count: `{payload.get('dataset_count')}`",
        f"- classification counts: `{dict(payload.get('classification_counts') or {})}`",
        "",
        "## Datasets",
        "",
        "| dataset | class | reward-hit | reward-active | reward-target | reward-dead | hit gap | active gap | dead gap |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for dataset in list(payload.get("datasets") or []):
        correlations = dict(dataset.get("correlations") or {})
        gaps = dict(dataset.get("quartile_gap") or {})
        lines.append(
            f"| {dataset.get('label')} | {dataset.get('alignment_classification')} | "
            f"{_fmt(correlations.get('reward_vs_points_hit'))} | "
            f"{_fmt(correlations.get('reward_vs_active_region_count'))} | "
            f"{_fmt(correlations.get('reward_vs_target_region_activated'))} | "
            f"{_fmt(correlations.get('reward_vs_dead_region_count'))} | "
            f"{_fmt(gaps.get('points_hit'))} | "
            f"{_fmt(gaps.get('active_region_count'))} | "
            f"{_fmt(gaps.get('dead_region_count'))} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report reward/behavior alignment from GRPO offline datasets.")
    parser.add_argument("--dataset-jsonl", action="append", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    return parser.parse_args()


def main() -> int:
    ns = parse_args()
    dataset_jsonls = [Path(item).expanduser().resolve() for item in list(ns.dataset_jsonl or [])]
    payload = build_payload(dataset_jsonls)
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
