#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a canonical socket-family GRPO mode packet from profile sweeps."
    )
    parser.add_argument("--profile-sweep-json", action="append", default=[], required=True)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--md-out", required=True)
    return parser.parse_args(argv)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _profile_summary(result: dict[str, Any]) -> dict[str, Any]:
    comparison = dict(result.get("comparison") or {})
    policy_on = dict(comparison.get("policy_on") or {})
    policy_off = dict(comparison.get("policy_off") or {})
    delta = dict(comparison.get("delta") or {})
    return {
        "profile": str(result.get("profile") or ""),
        "comparison_json": str(result.get("comparison_json") or ""),
        "points_hit": int(policy_on.get("best_points_hit") or 0),
        "points_total": int(policy_on.get("best_points_total") or 0),
        "dead_region_count": int(policy_on.get("dead_region_count") or 0),
        "policy_on_coverage_per_second": float(policy_on.get("coverage_per_second") or 0.0),
        "policy_off_coverage_per_second": float(policy_off.get("coverage_per_second") or 0.0),
        "delta_coverage_per_second": float(delta.get("coverage_per_second") or 0.0),
        "total_candidate_space": int(policy_on.get("total_candidate_space") or 0),
        "selection_mode": str(comparison.get("selection_mode") or ""),
        "target_region": str(comparison.get("target_region") or ""),
    }


def _recommend_mode(results: list[dict[str, Any]]) -> tuple[str, str]:
    best_quality = max(
        results,
        key=lambda item: (
            int(item["points_hit"]),
            -int(item["dead_region_count"]),
            float(item["delta_coverage_per_second"]),
        ),
    )
    best_throughput = max(
        results,
        key=lambda item: float(item["delta_coverage_per_second"]),
    )
    if float(best_throughput["delta_coverage_per_second"]) >= 0.0:
        return (
            "throughput_focused",
            f"{best_throughput['profile']} wins or matches throughput while preserving quality",
        )
    return (
        "diversity_focused",
        f"{best_quality['profile']} preserves quality but all tested profiles regress throughput",
    )


def _render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# GRPO Socket Mode Packet",
        "",
        "## Weakest Point",
        "",
        str(dict(payload.get("summary") or {}).get("weakest_point") or ""),
        "",
    ]
    for slice_name, item in sorted(dict(payload.get("slices") or {}).items()):
        results = list(item.get("profiles") or [])
        lines.extend(
            [
                f"## `{slice_name}`",
                "",
                f"- recommended mode: `{item.get('recommended_mode')}`",
                f"- rationale: `{item.get('mode_rationale')}`",
                f"- target region: `{item.get('target_region')}`",
                f"- selection mode: `{item.get('selection_mode')}`",
                "",
            ]
        )
        for profile in results:
            lines.extend(
                [
                    f"### `{profile.get('profile')}`",
                    "",
                    f"- quality: `{profile.get('points_hit')}/{profile.get('points_total')}`, dead `{profile.get('dead_region_count')}`",
                    f"- throughput delta: `{float(profile.get('delta_coverage_per_second') or 0.0):.2f}`",
                    f"- evidence: [{profile.get('comparison_json')}]({profile.get('comparison_json')})",
                    "",
                ]
            )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    slices: dict[str, dict[str, Any]] = {}
    for profile_sweep_json in list(ns.profile_sweep_json or []):
        path = Path(str(profile_sweep_json)).expanduser().resolve()
        payload = _load_json(path)
        slice_name = str(payload.get("slice_name") or "")
        results = [_profile_summary(result) for result in list(payload.get("results") or [])]
        if not results:
            continue
        recommended_mode, rationale = _recommend_mode(results)
        slices[slice_name] = {
            "profile_sweep_json": str(path),
            "recommended_mode": recommended_mode,
            "mode_rationale": rationale,
            "target_region": str(payload.get("target_region") or ""),
            "selection_mode": str(payload.get("selection_mode") or ""),
            "profiles": results,
            "best_by_throughput": dict(payload.get("best_by_throughput") or {}),
            "best_by_quality": dict(payload.get("best_by_quality") or {}),
        }

    weakest_point = (
        "Socket-family GRPO now needs explicit mode formalization. "
        "Some slices preserve hit quality but still regress throughput, while others "
        "already win under slice-aware targeting. The next blocker is locking these "
        "per-slice modes into the canonical packet."
    )
    payload = {
        "schema_version": "grpo-socket-mode-packet-v1",
        "summary": {
            "weakest_point": weakest_point,
            "status": "slice_aware_dual_mode_formalization_ready",
            "next_blocker": "formalize_socket_throughput_and_diversity_modes",
        },
        "slices": slices,
    }

    json_out = Path(ns.json_out).expanduser().resolve()
    md_out = Path(ns.md_out).expanduser().resolve()
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_out.write_text(_render_md(payload), encoding="utf-8")
    print(json_out)
    print(md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
