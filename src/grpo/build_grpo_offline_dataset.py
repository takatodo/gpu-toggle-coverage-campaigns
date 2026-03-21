#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import math
from pathlib import Path
from typing import Any

from grpo_coverage_common import (
    GRPO_REWARD_PROFILES,
    action_patch_from_case,
    canonical_action_key,
    context_key,
    frontier_from_summary,
    group_id,
    load_json,
    missing_region_context_key,
    missing_regions_from_summary,
    maybe_gpro_run_payload,
    reward_from_terms,
    reward_terms_from_case,
    slice_only_context_key,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build an offline GRPO dataset from existing GPRO/OpenTitan slice summaries."
    )
    parser.add_argument("--summary-json", action="append", default=[])
    parser.add_argument("--summary-glob", action="append", default=[])
    parser.add_argument("--jsonl-out", required=True)
    parser.add_argument("--json-out", default="")
    parser.add_argument("--top-k-per-group", type=int, default=0)
    parser.add_argument(
        "--reward-profile",
        choices=tuple(sorted(GRPO_REWARD_PROFILES)),
        default="balanced",
    )
    return parser.parse_args(argv)


def _discover_summary_paths(ns: argparse.Namespace) -> list[Path]:
    discovered: list[Path] = []
    for raw_path in list(ns.summary_json or []):
        path = Path(raw_path).expanduser().resolve()
        if path.exists():
            discovered.append(path)
    for raw_glob in list(ns.summary_glob or []):
        for raw_match in sorted(glob.glob(str(raw_glob), recursive=True)):
            resolved = Path(raw_match).expanduser().resolve()
            if resolved.is_file():
                discovered.append(resolved)
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in discovered:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _case_sort_key(case_summary: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(case_summary.get("real_subset_points_hit") or 0.0),
        float(case_summary.get("dead_region_count") or 0.0),
        float(case_summary.get("dead_output_word_count") or 0.0),
        -float(case_summary.get("real_subset_coverage_per_second") or 0.0),
        int(case_summary.get("case_index") or 0),
    )


def _maybe_trim_cases(cases: list[dict[str, Any]], top_k_per_group: int) -> list[dict[str, Any]]:
    if top_k_per_group <= 0:
        return list(cases)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for case_summary in cases:
        grouped.setdefault(str(case_summary.get("target_region") or ""), []).append(case_summary)
    kept: list[dict[str, Any]] = []
    for region_cases in grouped.values():
        kept.extend(sorted(region_cases, key=_case_sort_key)[:top_k_per_group])
    return kept


def _case_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list):
        return []
    cases: list[dict[str, Any]] = []
    for case_summary in raw_cases:
        if isinstance(case_summary, dict):
            cases.append(case_summary)
    return cases


def _campaign_frontier_cases(summary_payload: dict[str, Any]) -> list[dict[str, Any]]:
    frontier_cases: list[dict[str, Any]] = []
    best_case = summary_payload.get("best_case")
    if isinstance(best_case, dict):
        frontier_cases.append(best_case)
    best_by_target_region = summary_payload.get("best_by_target_region")
    if isinstance(best_by_target_region, dict):
        for case_summary in best_by_target_region.values():
            if isinstance(case_summary, dict):
                frontier_cases.append(case_summary)
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for case_summary in frontier_cases:
        key = (
            str(case_summary.get("target_region") or ""),
            int(case_summary.get("case_index") or 0),
            int(case_summary.get("seed") or 0),
            int(case_summary.get("seed_slot") or 0),
            str(case_summary.get("variant_name") or ""),
            str(case_summary.get("batch_json") or ""),
        )
        incumbent = deduped.get(key)
        if incumbent is None or _case_sort_key(case_summary) < _case_sort_key(incumbent):
            deduped[key] = case_summary
    return sorted(deduped.values(), key=_case_sort_key)


def _record_from_case(
    *,
    summary_json: Path,
    summary_payload: dict[str, Any],
    template_payload: dict[str, Any],
    gpro_payload: dict[str, Any],
    case_summary: dict[str, Any],
    reward_profile: str,
) -> dict[str, Any]:
    frontier = frontier_from_summary(
        case_summary=case_summary,
        summary_payload=summary_payload,
        template_payload=template_payload,
        gpro_payload=gpro_payload,
    )
    action_patch = action_patch_from_case(
        case_summary=case_summary,
        summary_payload=summary_payload,
        template_payload=template_payload,
        gpro_payload=gpro_payload,
    )
    reward_terms = reward_terms_from_case(
        case_summary,
        template_payload=template_payload,
        reward_profile=str(reward_profile),
    )
    reward = reward_from_terms(reward_terms)
    target_region = str(case_summary.get("target_region") or "")
    profile_family = str(summary_payload.get("profile_family") or frontier.get("profile_family") or "")
    slice_name = str(summary_payload.get("slice_name") or "")
    missing_regions = missing_regions_from_summary(
        summary_payload=summary_payload,
        template_payload=template_payload,
    )
    return {
        "schema_version": "grpo-coverage-dataset-v1",
        "source_summary_json": str(summary_json),
        "source_launch_template": str(summary_payload.get("launch_template") or ""),
        "group_id": group_id(summary_json=summary_json, target_region=target_region),
        "context_key": context_key(
            slice_name=slice_name,
            target_region=target_region,
            profile_family=profile_family,
        ),
        "slice_context_key": slice_only_context_key(
            slice_name=slice_name,
            profile_family=profile_family,
        ),
        "missing_region_context_key": missing_region_context_key(
            slice_name=slice_name,
            profile_family=profile_family,
            missing_regions=missing_regions,
        ),
        "frontier": frontier,
        "action_patch": action_patch,
        "action_key": canonical_action_key(action_patch),
        "reward_terms": reward_terms,
        "reward": reward,
        "case_summary": {
            "case_index": int(case_summary.get("case_index") or 0),
            "seed": int(case_summary.get("seed") or 0),
            "seed_slot": int(case_summary.get("seed_slot") or 0),
            "variant_name": str(case_summary.get("variant_name") or ""),
            "target_region": target_region,
            "points_hit": int(case_summary.get("real_subset_points_hit") or 0),
            "points_total": int(case_summary.get("real_subset_points_total") or 0),
            "dead_region_count": int(case_summary.get("dead_region_count") or 0),
            "dead_output_word_count": int(case_summary.get("dead_output_word_count") or 0),
            "coverage_per_second": float(case_summary.get("real_subset_coverage_per_second") or 0.0),
            "target_region_activated": int(case_summary.get("target_region_activated") or 0),
            "target_region_still_dead": int(case_summary.get("target_region_still_dead") or 0),
            "active_region_count": int(case_summary.get("active_region_count") or 0),
            "batch_json": str(case_summary.get("batch_json") or ""),
            "recommended_sequential_steps": int(case_summary.get("recommended_sequential_steps") or 0),
        },
    }


def _cases_for_summary(summary_json: Path, summary_payload: dict[str, Any]) -> list[dict[str, Any]]:
    merge_view_path = summary_json.with_name("summary.campaign_merge_view.json")
    if merge_view_path.exists():
        merge_view_payload = load_json(merge_view_path)
        if isinstance(merge_view_payload, dict):
            merge_cases = _case_entries(merge_view_payload)
            if merge_cases:
                return merge_cases
    summary_cases = _case_entries(summary_payload)
    if summary_cases:
        return summary_cases
    return _campaign_frontier_cases(summary_payload)


def _apply_marginal_breadth_reward_shaping(records: list[dict[str, Any]]) -> None:
    target_support_by_slice: dict[str, dict[str, int]] = {}
    for record in records:
        slice_context = str(record.get("slice_context_key") or "")
        target_region = str(dict(record.get("frontier") or {}).get("target_region") or "")
        if not slice_context or not target_region:
            continue
        bucket = target_support_by_slice.setdefault(slice_context, {})
        bucket[target_region] = int(bucket.get(target_region) or 0) + 1

    for record in records:
        slice_context = str(record.get("slice_context_key") or "")
        target_region = str(dict(record.get("frontier") or {}).get("target_region") or "")
        support = int(target_support_by_slice.get(slice_context, {}).get(target_region) or 0)
        rarity_bonus = 0.0 if support <= 0 else 1.0 / math.sqrt(float(support))
        reward_terms = dict(record.get("reward_terms") or {})
        reward_terms["target_region_rarity_bonus"] = rarity_bonus
        reward_terms_for_eval = dict(reward_terms)
        reward_terms_for_eval.pop("reward", None)
        record["reward_terms"] = reward_terms
        record["reward"] = reward_from_terms(reward_terms_for_eval)
        record["reward_terms"]["reward"] = float(record["reward"])


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    summary_paths = _discover_summary_paths(ns)
    if not summary_paths:
        raise SystemExit("No summary.json inputs found")

    records: list[dict[str, Any]] = []
    slice_counts: dict[str, int] = {}
    group_counts: dict[str, int] = {}
    reward_min = None
    reward_max = None

    for summary_json in summary_paths:
        summary_payload = load_json(summary_json)
        template_path = Path(str(summary_payload.get("launch_template") or "")).expanduser().resolve()
        if not template_path.exists():
            raise SystemExit(f"Missing launch template for summary: {summary_json}")
        template_payload = load_json(template_path)
        gpro_payload = maybe_gpro_run_payload(summary_json)
        cases = _maybe_trim_cases(_cases_for_summary(summary_json, summary_payload), int(ns.top_k_per_group))
        for case_summary in cases:
            record = _record_from_case(
                summary_json=summary_json,
                summary_payload=summary_payload,
                template_payload=template_payload,
                gpro_payload=gpro_payload,
                case_summary=case_summary,
                reward_profile=str(ns.reward_profile),
            )
            records.append(record)
            slice_name = str(record["frontier"]["slice_name"])
            slice_counts[slice_name] = int(slice_counts.get(slice_name) or 0) + 1
            gid = str(record["group_id"])
            group_counts[gid] = int(group_counts.get(gid) or 0) + 1
            reward_value = float(record["reward"])
            reward_min = reward_value if reward_min is None else min(reward_min, reward_value)
            reward_max = reward_value if reward_max is None else max(reward_max, reward_value)

    if str(ns.reward_profile) in ("marginal_breadth", "closure"):
        _apply_marginal_breadth_reward_shaping(records)
        reward_values = [float(record.get("reward") or 0.0) for record in records]
        reward_min = min(reward_values) if reward_values else 0.0
        reward_max = max(reward_values) if reward_values else 0.0

    jsonl_out = Path(ns.jsonl_out).expanduser().resolve()
    jsonl_out.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_out.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    summary_payload = {
        "schema_version": "grpo-coverage-dataset-summary-v1",
        "record_count": len(records),
        "summary_count": len(summary_paths),
        "group_count": len(group_counts),
        "slice_counts": dict(sorted(slice_counts.items())),
        "group_size_stats": {
            "min": min(group_counts.values()) if group_counts else 0,
            "max": max(group_counts.values()) if group_counts else 0,
            "mean": (
                sum(group_counts.values()) / float(len(group_counts))
                if group_counts
                else 0.0
            ),
        },
        "reward_range": {
            "min": reward_min if reward_min is not None else 0.0,
            "max": reward_max if reward_max is not None else 0.0,
        },
        "reward_profile": str(ns.reward_profile),
        "source_summaries": [str(path) for path in summary_paths],
        "jsonl_path": str(jsonl_out),
    }
    json_out = (
        Path(ns.json_out).expanduser().resolve()
        if ns.json_out
        else jsonl_out.with_suffix(".summary.json")
    )
    json_out.write_text(json.dumps(summary_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
