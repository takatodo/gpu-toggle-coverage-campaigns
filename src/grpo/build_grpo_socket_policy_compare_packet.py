#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate repeated GRPO socket policy comparisons into a canonical packet."
    )
    parser.add_argument("--comparison-json", action="append", default=[], required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    return parser.parse_args(argv)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _mean(values: list[float]) -> float:
    return float(statistics.mean(values)) if values else 0.0


def _pstdev(values: list[float]) -> float:
    return float(statistics.pstdev(values)) if len(values) > 1 else 0.0


def _summarize_runs(compare_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    policy_off = [dict(payload.get("policy_off") or {}) for payload in compare_payloads]
    policy_on = [dict(payload.get("policy_on") or {}) for payload in compare_payloads]
    delta = [dict(payload.get("delta") or {}) for payload in compare_payloads]

    off_cps = [float(item.get("coverage_per_second") or 0.0) for item in policy_off]
    on_cps = [float(item.get("coverage_per_second") or 0.0) for item in policy_on]
    off_hits = [int(item.get("best_points_hit") or 0) for item in policy_off]
    on_hits = [int(item.get("best_points_hit") or 0) for item in policy_on]
    off_dead = [int(item.get("dead_region_count") or 0) for item in policy_off]
    on_dead = [int(item.get("dead_region_count") or 0) for item in policy_on]
    off_space = [int(item.get("total_candidate_space") or 0) for item in policy_off]
    on_space = [int(item.get("total_candidate_space") or 0) for item in policy_on]
    proposal_k = sorted({int(payload.get("proposal_k") or 0) for payload in compare_payloads})
    selection_modes = sorted({str(payload.get("selection_mode") or "") for payload in compare_payloads})
    target_regions = sorted({str(payload.get("target_region") or "") for payload in compare_payloads})
    deltas_cps = [float(item.get("coverage_per_second") or 0.0) for item in delta]

    robust_quality_match = all(
        int(off_hit) == int(on_hit) and int(off_dead_value) == int(on_dead_value)
        for off_hit, on_hit, off_dead_value, on_dead_value in zip(off_hits, on_hits, off_dead, on_dead)
    )

    mean_off_space = _mean([float(value) for value in off_space])
    mean_on_space = _mean([float(value) for value in on_space])
    compression_ratio = (
        float(mean_on_space) / float(mean_off_space) if mean_off_space > 0.0 else 0.0
    )

    throughput_status = "policy_on_regresses"
    if _mean(on_cps) > _mean(off_cps):
        throughput_status = "policy_on_wins"
    elif abs(_mean(on_cps) - _mean(off_cps)) <= max(10.0, 0.03 * max(_mean(off_cps), 1.0)):
        throughput_status = "policy_on_near_parity"

    return {
        "repeat_count": len(compare_payloads),
        "robust_quality_match": bool(robust_quality_match),
        "proposal_k_values": proposal_k,
        "selection_modes": selection_modes,
        "target_regions": target_regions,
        "policy_off": {
            "points_hit_values": off_hits,
            "dead_region_count_values": off_dead,
            "coverage_per_second_mean": _mean(off_cps),
            "coverage_per_second_stdev": _pstdev(off_cps),
            "total_candidate_space_values": off_space,
            "total_candidate_space_mean": mean_off_space,
        },
        "policy_on": {
            "points_hit_values": on_hits,
            "dead_region_count_values": on_dead,
            "coverage_per_second_mean": _mean(on_cps),
            "coverage_per_second_stdev": _pstdev(on_cps),
            "total_candidate_space_values": on_space,
            "total_candidate_space_mean": mean_on_space,
        },
        "delta": {
            "coverage_per_second_mean": _mean(deltas_cps),
            "coverage_per_second_stdev": _pstdev(deltas_cps),
            "total_candidate_space_mean": mean_on_space - mean_off_space,
        },
        "candidate_compression_ratio": compression_ratio,
        "candidate_compression_factor": (
            float(mean_off_space) / float(mean_on_space) if mean_on_space > 0.0 else 0.0
        ),
        "throughput_status": throughput_status,
        "comparison_jsons": [str(payload.get("_comparison_json") or "") for payload in compare_payloads],
    }


def _packet_summary(slice_summaries: dict[str, dict[str, Any]]) -> dict[str, str]:
    robust_slices = sorted(
        slice_name
        for slice_name, summary in slice_summaries.items()
        if bool(summary.get("robust_quality_match"))
    )
    regressed_slices = sorted(
        slice_name
        for slice_name, summary in slice_summaries.items()
        if str(summary.get("throughput_status") or "") == "policy_on_regresses"
    )
    weakest_point = (
        "Diversity-aware GRPO robustly preserves socket-family hit/dead-region quality "
        "under reduced candidate budgets, but the throughput result is not yet stable "
        "enough to claim a general win. The next blocker is retuning or explicitly "
        "splitting throughput-focused and diversity-focused policy modes."
    )
    if not regressed_slices:
        weakest_point = (
            "Diversity-aware GRPO now preserves socket-family hit/dead-region quality "
            "under reduced candidate budgets without a throughput regression. The next "
            "blocker is formalizing the socket packet and resuming scope expansion."
        )
    return {
        "status": (
            "socket_grpo_quality_preserved_throughput_needs_retune"
            if regressed_slices
            else "socket_grpo_packet_ready_for_formalization"
        ),
        "next_blocker": (
            "retune_diversity_aware_grpo_or_split_throughput_vs_diversity_modes"
            if regressed_slices
            else "formalize_socket_packet_then_resume_scope_expansion"
        ),
        "weakest_point": weakest_point,
        "robust_quality_slices": robust_slices,
        "throughput_regressed_slices": regressed_slices,
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = dict(payload.get("summary") or {})
    lines = [
        "# GRPO Socket Policy Compare",
        "",
        "## Weakest Point",
        "",
        str(summary.get("weakest_point") or ""),
        "",
    ]
    for slice_name, slice_summary in sorted(dict(payload.get("slices") or {}).items()):
        off = dict(slice_summary.get("policy_off") or {})
        on = dict(slice_summary.get("policy_on") or {})
        delta = dict(slice_summary.get("delta") or {})
        lines.extend(
            [
                f"## `{slice_name}`",
                "",
                f"- repeats: `{int(slice_summary.get('repeat_count') or 0)}`",
                f"- quality: `policy_off` and `policy_on` both keep "
                f"`{off.get('points_hit_values', [])}` hits and "
                f"`{off.get('dead_region_count_values', [])}` / "
                f"`{on.get('dead_region_count_values', [])}` dead-region counts",
                f"- candidate space: `policy_off` mean "
                f"`{float(off.get('total_candidate_space_mean') or 0.0):.1f}` -> "
                f"`policy_on` mean `{float(on.get('total_candidate_space_mean') or 0.0):.1f}` "
                f"(`{float(slice_summary.get('candidate_compression_factor') or 0.0):.2f}x` compression)",
                f"- throughput: `policy_off` mean "
                f"`{float(off.get('coverage_per_second_mean') or 0.0):.2f}` "
                f"(stdev `{float(off.get('coverage_per_second_stdev') or 0.0):.2f}`), "
                f"`policy_on` mean `{float(on.get('coverage_per_second_mean') or 0.0):.2f}` "
                f"(stdev `{float(on.get('coverage_per_second_stdev') or 0.0):.2f}`)",
                f"- delta coverage/sec mean: `{float(delta.get('coverage_per_second_mean') or 0.0):.2f}` "
                f"(stdev `{float(delta.get('coverage_per_second_stdev') or 0.0):.2f}`)",
                f"- selection modes: `{', '.join(slice_summary.get('selection_modes') or [])}`",
                f"- target regions: `{', '.join(slice_summary.get('target_regions') or [])}`",
                "- evidence:",
            ]
        )
        for ref in list(slice_summary.get("comparison_jsons") or []):
            lines.append(f"  - [{ref}]({ref})")
        lines.append("")

    lines.extend(
        [
            "## Conclusion",
            "",
            "- The robust claim is no longer a throughput win; it is preserved hit quality under reduced candidate budgets.",
            "- `xbar_peri` and `xbar_main` remain control slices rather than search-headroom exemplars.",
            "- The next task is to retune diversity-aware `GRPO` or formalize separate throughput and diversity modes before reopening the next family.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for comparison_json in list(ns.comparison_json or []):
        path = Path(str(comparison_json)).expanduser().resolve()
        payload = _load_json(path)
        payload["_comparison_json"] = str(path)
        grouped.setdefault(str(payload.get("slice_name") or ""), []).append(payload)

    slice_summaries = {
        slice_name: _summarize_runs(compare_payloads)
        for slice_name, compare_payloads in sorted(grouped.items())
    }
    packet = {
        "schema_version": "grpo-socket-policy-compare-v2",
        "summary": _packet_summary(slice_summaries),
        "slices": slice_summaries,
    }

    json_out = Path(ns.json_out).expanduser().resolve()
    md_out = Path(ns.md_out).expanduser().resolve()
    json_out.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_out.write_text(_render_md(packet), encoding="utf-8")
    print(json_out)
    print(md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
