#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROLE_BY_SLICE = {
    "alert_handler_ping_timer": "history_export_breadth_case",
    "aes_cipher_control": "harder_live_medium_block",
    "entropy_src_main_sm": "history_export_breadth_case",
    "lc_ctrl_fsm": "shared_tb_contract_proof_point",
    "pwrmgr_fsm": "shared_tb_contract_proof_point",
    "rom_ctrl_fsm": "shared_tb_contract_proof_point",
    "tlul_request_loopback": "positive_reference",
    "tlul_fifo_async": "canonical_hard_lane",
    "tlul_socket_m1": "operational_backup_hard_lane",
    "edn_main_sm": "live_medium_block_frontier",
    "csrng_main_sm": "harder_live_medium_block",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _slice_entry(payload: dict[str, Any]) -> dict[str, Any]:
    verdict = dict(payload.get("verdict") or {})
    plain = dict(payload.get("plain") or {})
    grpo = dict(payload.get("grpo") or {})
    slice_name = str(payload.get("slice_name") or "")
    return {
        "slice_name": slice_name,
        "role": ROLE_BY_SLICE.get(slice_name, "unassigned"),
        "classification": str(verdict.get("classification") or ""),
        "ceiling_gain": bool(verdict.get("ceiling_gain")),
        "frontier_gain": bool(verdict.get("frontier_gain")),
        "efficiency_gain": bool(verdict.get("efficiency_gain")),
        "throughput_only_gain": bool(verdict.get("throughput_only_gain")),
        "same_total_candidate_space": bool(verdict.get("same_total_candidate_space")),
        "same_evaluated_case_count": bool(verdict.get("same_evaluated_case_count")),
        "plain_best_hit_fraction": float(plain.get("best_hit_fraction") or 0.0),
        "grpo_best_hit_fraction": float(grpo.get("best_hit_fraction") or 0.0),
        "plain_union_count": int(plain.get("campaign_active_region_union_count") or 0),
        "grpo_union_count": int(grpo.get("campaign_active_region_union_count") or 0),
        "plain_frontier_mean_active_region_count": float(plain.get("frontier_mean_active_region_count") or 0.0),
        "grpo_frontier_mean_active_region_count": float(grpo.get("frontier_mean_active_region_count") or 0.0),
        "plain_frontier_target_activation_rate": float(plain.get("frontier_target_activation_rate") or 0.0),
        "grpo_frontier_target_activation_rate": float(grpo.get("frontier_target_activation_rate") or 0.0),
    }


def _aggregate(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "slice_count": len(entries),
        "all_same_total_candidate_space": all(entry["same_total_candidate_space"] for entry in entries),
        "all_same_evaluated_case_count": all(entry["same_evaluated_case_count"] for entry in entries),
        "ceiling_gain_slices": [entry["slice_name"] for entry in entries if entry["ceiling_gain"]],
        "frontier_gain_slices": [entry["slice_name"] for entry in entries if entry["frontier_gain"]],
        "efficiency_gain_slices": [entry["slice_name"] for entry in entries if entry["efficiency_gain"]],
        "throughput_only_slices": [entry["slice_name"] for entry in entries if entry["throughput_only_gain"]],
    }


def _verdict(entries: list[dict[str, Any]], aggregate: dict[str, Any]) -> dict[str, Any]:
    slice_count = aggregate["slice_count"]
    any_ceiling = bool(aggregate["ceiling_gain_slices"])
    any_frontier = bool(aggregate["frontier_gain_slices"])
    all_throughput_only = len(aggregate["throughput_only_slices"]) == slice_count and slice_count > 0
    all_efficiency = len(aggregate["efficiency_gain_slices"]) == slice_count and slice_count > 0

    if any_ceiling:
        classification = "ceiling_gain_present"
        status = "grpo_search_quality_positive"
        robust_claim = "At least one slice shows fixed-budget ceiling gain, so GRPO can no longer be treated as throughput-only."
        non_claim = "This does not imply that every slice benefits or that wall clock always improves."
        next_action = "Inspect the ceiling-positive slice and refit the objective around whatever produced the union/hit lift."
    elif any_frontier:
        classification = "frontier_gain_present"
        status = "grpo_frontier_positive_no_ceiling"
        robust_claim = "At least one slice shows frontier-quality gain at fixed budget, even if best-case ceiling is unchanged."
        non_claim = "This is not yet a generalized ceiling-improvement claim."
        next_action = "Promote frontier-quality metrics into the mainline A/B gate and collect one more hard-slice replication."
    elif all_throughput_only:
        classification = "three_slice_throughput_only_gain" if slice_count == 3 else "all_slice_throughput_only_gain"
        status = "grpo_throughput_generalizes_but_not_search_quality"
        robust_claim = "Across the evaluated slices, GRPO consistently improves local throughput or wall clock under equal budget."
        non_claim = "There is no fixed-budget evidence of ceiling gain, frontier gain, region-breadth gain, or target-activation gain."
        next_action = "Treat GRPO as an efficiency layer, not a coverage-closure improver, and refocus objectives and benches on breadth."
    else:
        classification = "mixed_or_inconclusive"
        status = "grpo_mixed_or_inconclusive"
        robust_claim = "The current slice set does not support a single clean GRPO verdict."
        non_claim = "No generalized throughput or search-quality claim is justified yet."
        next_action = "Add another medium-difficulty live slice or tighten the equal-budget setup."

    return {
        "status": status,
        "classification": classification,
        "all_efficiency_gain": all_efficiency,
        "any_ceiling_gain": any_ceiling,
        "any_frontier_gain": any_frontier,
        "all_throughput_only_gain": all_throughput_only,
        "robust_claim": robust_claim,
        "non_claim": non_claim,
        "next_action": next_action,
        "role_freeze": {entry["slice_name"]: entry["role"] for entry in entries if entry["role"] != "unassigned"},
    }


def build_payload(*, axes_paths: list[Path]) -> dict[str, Any]:
    entries = [_slice_entry(_load_json(path)) for path in axes_paths]
    aggregate = _aggregate(entries)
    verdict = _verdict(entries, aggregate)
    return {
        "schema_version": "grpo-multislice-verdict-v1",
        "axes_jsons": [str(path) for path in axes_paths],
        "slices": entries,
        "aggregate": aggregate,
        "verdict": verdict,
    }


def _markdown(payload: dict[str, Any]) -> str:
    verdict = payload["verdict"]
    lines = [
        "# GRPO Multi-Slice Verdict",
        "",
        "## Summary",
        "",
        f"- status: `{verdict['status']}`",
        f"- classification: `{verdict['classification']}`",
        f"- all efficiency gain: `{verdict['all_efficiency_gain']}`",
        f"- any ceiling gain: `{verdict['any_ceiling_gain']}`",
        f"- any frontier gain: `{verdict['any_frontier_gain']}`",
        "",
        "## Slice Table",
        "",
        "| slice | role | classification | plain hit frac | GRPO hit frac | plain union | GRPO union | frontier gain | ceiling gain | efficiency gain |",
        "|---|---|---|---:|---:|---:|---:|---|---|---|",
    ]
    for entry in payload["slices"]:
        lines.append(
            f"| {entry['slice_name']} | {entry['role']} | `{entry['classification']}` | "
            f"{entry['plain_best_hit_fraction']:.4f} | {entry['grpo_best_hit_fraction']:.4f} | "
            f"{entry['plain_union_count']} | {entry['grpo_union_count']} | "
            f"`{entry['frontier_gain']}` | `{entry['ceiling_gain']}` | `{entry['efficiency_gain']}` |"
        )
    lines.extend(
        [
            "",
            "## Verdict",
            "",
            f"- robust claim: {verdict['robust_claim']}",
            f"- non-claim: {verdict['non_claim']}",
            f"- next action: {verdict['next_action']}",
        ]
    )
    if verdict["role_freeze"]:
        lines.extend(["", "## Role Freeze", ""])
        for slice_name, role in verdict["role_freeze"].items():
            lines.append(f"- `{slice_name}`: `{role}`")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Integrate multiple GRPO A/B axes reports into one verdict.")
    parser.add_argument("--axes-json", action="append", required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    return parser.parse_args()


def main() -> int:
    ns = parse_args()
    axes_paths = [Path(item).expanduser().resolve() for item in ns.axes_json]
    payload = build_payload(axes_paths=axes_paths)
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
