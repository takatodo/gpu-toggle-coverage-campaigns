#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from grpo_coverage_common import (
    GRPO_REWARD_PROFILES,
    action_patch_diversity_score,
    safe_group_advantages,
    stable_softmax,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train a minimal offline GRPO-style policy from the coverage dataset."
    )
    parser.add_argument("--dataset-jsonl", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--top-actions-per-context", type=int, default=8)
    parser.add_argument("--min-samples-per-action", type=int, default=1)
    parser.add_argument("--diversity-weight", type=float, default=0.25)
    parser.add_argument("--rarity-weight", type=float, default=0.10)
    parser.add_argument("--frequency-novelty-weight", type=float, default=0.08)
    parser.add_argument(
        "--reward-profile",
        choices=tuple(sorted(GRPO_REWARD_PROFILES)),
        default="balanced",
    )
    return parser.parse_args(argv)


def _load_records(dataset_jsonl: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with dataset_jsonl.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            records.append(json.loads(text))
    return records


def _group_records(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        groups.setdefault(str(record.get("group_id") or ""), []).append(record)
    return groups


def _frequency_novelty_score(count: int) -> float:
    count_value = max(1, int(count))
    return 1.0 / float(count_value) ** 0.5


def _region_rarity_score(
    target_regions: list[str],
    region_support_counts: dict[str, int],
) -> float:
    filtered = [str(region or "") for region in target_regions if str(region or "").strip()]
    if not filtered:
        return 0.0
    rarity_values = [
        1.0 / float(max(1, int(region_support_counts.get(region) or 1)))
        for region in filtered
    ]
    return sum(rarity_values) / float(len(rarity_values))


def _target_family_diversity_score(
    target_regions: list[str],
    selected_target_regions: set[str],
) -> float:
    filtered = [str(region or "") for region in target_regions if str(region or "").strip()]
    if not filtered:
        return 0.0
    if not selected_target_regions:
        return 1.0
    unseen = [
        region
        for region in filtered
        if region not in selected_target_regions
    ]
    return float(len(unseen)) / float(len(filtered))


def _base_selection_score(
    *,
    reward_profile: str,
    mean_advantage: float,
    mean_reward: float,
    mean_coverage_per_second: float,
    max_coverage_per_second: float,
) -> float:
    normalized = str(reward_profile or "balanced").strip() or "balanced"
    if normalized in ("breadth", "marginal_breadth", "closure"):
        return mean_advantage + 0.02 * mean_reward
    if normalized == "throughput":
        return (
            mean_advantage
            + 0.01 * mean_reward
            + 0.001 * mean_coverage_per_second
            + 0.0005 * max_coverage_per_second
        )
    return (
        mean_advantage
        + 0.01 * mean_reward
        + 0.00025 * mean_coverage_per_second
        + 0.0001 * max_coverage_per_second
    )


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    dataset_jsonl = Path(ns.dataset_jsonl).expanduser().resolve()
    records = _load_records(dataset_jsonl)
    if not records:
        raise SystemExit("Dataset is empty")

    grouped = _group_records(records)
    action_stats_by_context: dict[str, dict[str, dict[str, Any]]] = {}
    action_stats_by_slice: dict[str, dict[str, dict[str, Any]]] = {}
    action_stats_by_missing_region: dict[str, dict[str, dict[str, Any]]] = {}

    for group_records in grouped.values():
        rewards = [float(record.get("reward") or 0.0) for record in group_records]
        advantages = safe_group_advantages(rewards)
        for record, advantage in zip(group_records, advantages):
            context = str(record.get("context_key") or "")
            slice_context = str(record.get("slice_context_key") or "")
            missing_region_context = str(record.get("missing_region_context_key") or "")
            action_key = str(record.get("action_key") or "")
            for container_key, container in (
                (context, action_stats_by_context),
                (slice_context, action_stats_by_slice),
                (missing_region_context, action_stats_by_missing_region),
            ):
                if not container_key:
                    continue
                context_bucket = container.setdefault(container_key, {})
                stats = context_bucket.setdefault(
                    action_key,
                    {
                        "action_patch": dict(record.get("action_patch") or {}),
                        "count": 0,
                        "reward_sum": 0.0,
                        "advantage_sum": 0.0,
                        "coverage_per_second_sum": 0.0,
                        "max_coverage_per_second": 0.0,
                        "best_reward": None,
                        "target_regions": set(),
                    },
                )
                stats["count"] = int(stats["count"]) + 1
                stats["reward_sum"] = float(stats["reward_sum"]) + float(record.get("reward") or 0.0)
                stats["advantage_sum"] = float(stats["advantage_sum"]) + float(advantage)
                coverage_per_second = float(
                    dict(record.get("case_summary") or {}).get("coverage_per_second") or 0.0
                )
                stats["coverage_per_second_sum"] = float(stats["coverage_per_second_sum"]) + coverage_per_second
                stats["max_coverage_per_second"] = max(float(stats["max_coverage_per_second"]), coverage_per_second)
                reward_value = float(record.get("reward") or 0.0)
                stats["best_reward"] = reward_value if stats["best_reward"] is None else max(float(stats["best_reward"]), reward_value)
                frontier = dict(record.get("frontier") or {})
                stats["target_regions"].add(str(frontier.get("target_region") or ""))

    def finalize(container: dict[str, dict[str, dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        finalized: dict[str, list[dict[str, Any]]] = {}
        for context_name, action_map in sorted(container.items()):
            pool: list[dict[str, Any]] = []
            for action_key, stats in action_map.items():
                count = int(stats["count"])
                if count < int(ns.min_samples_per_action):
                    continue
                mean_reward = float(stats["reward_sum"]) / float(count)
                mean_advantage = float(stats["advantage_sum"]) / float(count)
                mean_coverage_per_second = float(stats["coverage_per_second_sum"]) / float(count)
                max_coverage_per_second = float(stats["max_coverage_per_second"] or 0.0)
                base_selection_score = _base_selection_score(
                    reward_profile=str(ns.reward_profile),
                    mean_advantage=mean_advantage,
                    mean_reward=mean_reward,
                    mean_coverage_per_second=mean_coverage_per_second,
                    max_coverage_per_second=max_coverage_per_second,
                )
                pool.append(
                    {
                        "action_key": action_key,
                        "action_patch": dict(stats["action_patch"]),
                        "count": count,
                        "mean_reward": mean_reward,
                        "mean_advantage": mean_advantage,
                        "mean_coverage_per_second": mean_coverage_per_second,
                        "max_coverage_per_second": max_coverage_per_second,
                        "base_selection_score": base_selection_score,
                        "best_reward": float(stats["best_reward"] or 0.0),
                        "target_regions": sorted({region for region in stats["target_regions"] if region}),
                        "frequency_novelty_score": _frequency_novelty_score(count),
                    }
                )
            pool.sort(
                key=lambda item: (
                    -float(item["base_selection_score"]),
                    -float(item["mean_reward"]),
                    -int(item["count"]),
                    item["action_key"],
                )
            )
            region_support_counts: dict[str, int] = {}
            for item in pool:
                for region in item["target_regions"]:
                    region_support_counts[region] = int(region_support_counts.get(region) or 0) + 1
            for item in pool:
                item["region_rarity_score"] = _region_rarity_score(
                    list(item["target_regions"]),
                    region_support_counts,
                )
            actions: list[dict[str, Any]] = []
            remaining = list(pool)
            limit = max(1, int(ns.top_actions_per_context))
            while remaining and len(actions) < limit:
                selected_patches = [dict(item["action_patch"]) for item in actions]
                selected_target_regions = {
                    region
                    for action in actions
                    for region in list(action.get("target_regions") or [])
                    if str(region or "").strip()
                }
                for item in remaining:
                    diversity_score = action_patch_diversity_score(
                        dict(item["action_patch"]),
                        selected_patches,
                    )
                    target_family_diversity_score = _target_family_diversity_score(
                        list(item.get("target_regions") or []),
                        selected_target_regions,
                    )
                    target_family_diversity_weight = (
                        float(ns.diversity_weight) * 1.5
                        if str(ns.reward_profile) == "closure"
                        else 0.0
                    )
                    item["diversity_score"] = diversity_score
                    item["target_family_diversity_score"] = target_family_diversity_score
                    item["selection_score"] = (
                        float(item["base_selection_score"])
                        + float(ns.rarity_weight) * float(item["region_rarity_score"])
                        + float(ns.frequency_novelty_weight) * float(item["frequency_novelty_score"])
                        + float(ns.diversity_weight) * float(diversity_score)
                        + target_family_diversity_weight * float(target_family_diversity_score)
                    )
                remaining.sort(
                    key=lambda item: (
                        -float(item["selection_score"]),
                        -float(item["base_selection_score"]),
                        -float(item["mean_reward"]),
                        item["action_key"],
                    )
                )
                actions.append(remaining.pop(0))
            probs = stable_softmax([float(item["selection_score"]) for item in actions])
            for rank, (item, prob) in enumerate(zip(actions, probs), start=1):
                item["policy_probability"] = prob
                item["selection_rank"] = rank
            finalized[context_name] = actions
        return finalized

    policy_payload = {
        "schema_version": "minimal-grpo-policy-v1",
        "selection_rule": (
            "group_advantage_plus_reward_with_diversity_and_rarity"
            if str(ns.reward_profile) in ("breadth", "marginal_breadth", "closure")
            else "group_advantage_plus_reward_plus_throughput_with_diversity_and_rarity"
        ),
        "dataset_jsonl": str(dataset_jsonl),
        "record_count": len(records),
        "group_count": len(grouped),
        "selection_hyperparams": {
            "diversity_weight": float(ns.diversity_weight),
            "rarity_weight": float(ns.rarity_weight),
            "frequency_novelty_weight": float(ns.frequency_novelty_weight),
            "reward_profile": str(ns.reward_profile),
            "top_actions_per_context": int(ns.top_actions_per_context),
            "min_samples_per_action": int(ns.min_samples_per_action),
        },
        "contexts": finalize(action_stats_by_context),
        "slice_contexts": finalize(action_stats_by_slice),
        "missing_region_contexts": finalize(action_stats_by_missing_region),
    }
    json_out = Path(ns.json_out).expanduser().resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(policy_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
