#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

from grpo_coverage_common import (
    GRPO_POLICY_PROFILES,
    recommended_grpo_selection_mode,
    recommended_grpo_target_region,
)


SCRIPT_DIR = Path(__file__).resolve().parent
PHASE0_PIPELINE = SCRIPT_DIR / "run_grpo_phase0_pipeline.py"
POLICY_COMPARE = SCRIPT_DIR / "run_grpo_policy_compare.py"


DEFAULT_SOCKET_SUMMARIES = (
    "/tmp/gpro_tlul_socket_1n_gpro_runner_v1/summary.json",
    "/tmp/gpro_tlul_socket_m1_gpro_runner_v1/summary.json",
    "/tmp/gpro_xbar_peri_gpro_runner_v3/summary.json",
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sweep GRPO policy presets on a socket slice and compare rollout quality."
    )
    parser.add_argument("--slice", required=True)
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--summary-json", action="append", default=[])
    parser.add_argument("--summary-glob", action="append", default=[])
    parser.add_argument("--profile", action="append", default=[])
    parser.add_argument("--target-region", default="auto")
    parser.add_argument("--selection-mode", default="auto")
    parser.add_argument("--cases", type=int, default=32)
    parser.add_argument("--proposal-k", type=int, default=2)
    parser.add_argument("--top-k-per-group", type=int, default=8)
    parser.add_argument("--top-actions-per-context", type=int, default=6)
    parser.add_argument("--json-out", default="")
    return parser.parse_args(argv)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=SCRIPT_DIR, check=True)


def _resolve_target_region(slice_name: str, requested: str) -> str:
    if str(requested).strip() and str(requested).strip() != "auto":
        return str(requested).strip()
    target_region = recommended_grpo_target_region(slice_name)
    if not target_region:
        raise SystemExit(f"No default GRPO target region is known for slice: {slice_name}")
    return target_region


def _resolve_selection_mode(slice_name: str, requested: str) -> str:
    if str(requested).strip() and str(requested).strip() != "auto":
        return str(requested).strip()
    return recommended_grpo_selection_mode(slice_name)


def _summary_inputs(ns: argparse.Namespace) -> list[str]:
    inputs = [str(item) for item in list(ns.summary_json or []) if str(item).strip()]
    if inputs:
        return inputs
    return list(DEFAULT_SOCKET_SUMMARIES)


def _profile_list(ns: argparse.Namespace) -> list[str]:
    profiles = [str(item).strip() for item in list(ns.profile or []) if str(item).strip()]
    if not profiles:
        profiles = ["throughput", "balanced", "diversity"]
    for profile in profiles:
        if profile not in GRPO_POLICY_PROFILES:
            raise SystemExit(f"Unknown profile: {profile}")
    return profiles


def _md_for_payload(payload: dict[str, Any]) -> str:
    lines = [
        "# GRPO Socket Profile Sweep",
        "",
        f"- slice: `{payload.get('slice_name')}`",
        f"- target region: `{payload.get('target_region')}`",
        f"- selection mode: `{payload.get('selection_mode')}`",
        f"- proposal k: `{payload.get('proposal_k')}`",
        "",
        "## Results",
        "",
    ]
    for result in list(payload.get("results") or []):
        compare = dict(result.get("comparison") or {})
        policy_on = dict(compare.get("policy_on") or {})
        policy_off = dict(compare.get("policy_off") or {})
        lines.extend(
            [
                f"### `{result.get('profile')}`",
                "",
                f"- policy-on: `{policy_on.get('best_points_hit')}/{policy_on.get('best_points_total')}`, dead `{policy_on.get('dead_region_count')}`, cps `{float(policy_on.get('coverage_per_second') or 0.0):.2f}`",
                f"- baseline: `{policy_off.get('best_points_hit')}/{policy_off.get('best_points_total')}`, dead `{policy_off.get('dead_region_count')}`, cps `{float(policy_off.get('coverage_per_second') or 0.0):.2f}`",
                f"- delta cps: `{float(dict(compare.get('delta') or {}).get('coverage_per_second') or 0.0):.2f}`",
                f"- evidence: [{result.get('comparison_json')}]({result.get('comparison_json')})",
                "",
            ]
        )
    lines.extend(
        [
            "## Best Profiles",
            "",
            f"- throughput winner: `{dict(payload.get('best_by_throughput') or {}).get('profile', '')}`",
            f"- quality winner: `{dict(payload.get('best_by_quality') or {}).get('profile', '')}`",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    work_dir = Path(ns.work_dir).expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    slice_name = str(ns.slice).strip()
    target_region = _resolve_target_region(slice_name, str(ns.target_region))
    selection_mode = _resolve_selection_mode(slice_name, str(ns.selection_mode))
    profiles = _profile_list(ns)
    summary_inputs = _summary_inputs(ns)

    results: list[dict[str, Any]] = []
    for profile in profiles:
        profile_dir = work_dir / profile
        pipeline_dir = profile_dir / "pipeline"
        compare_dir = profile_dir / "compare"
        pipeline_cmd = [
            "python3",
            str(PHASE0_PIPELINE),
            "--work-dir",
            str(pipeline_dir),
            "--policy-profile",
            str(profile),
            "--proposal-k",
            str(int(ns.proposal_k)),
            "--top-k-per-group",
            str(int(ns.top_k_per_group)),
            "--top-actions-per-context",
            str(int(ns.top_actions_per_context)),
            "--slice-name",
            str(slice_name),
            "--profile-family",
            "dead-region",
            "--target-region",
            str(target_region),
        ]
        for summary_json in summary_inputs:
            pipeline_cmd.extend(["--summary-json", str(summary_json)])
        for summary_glob in list(ns.summary_glob or []):
            pipeline_cmd.extend(["--summary-glob", str(summary_glob)])
        _run(pipeline_cmd)

        policy_json = pipeline_dir / "policy.json"
        compare_cmd = [
            "python3",
            str(POLICY_COMPARE),
            "--slice",
            str(slice_name),
            "--policy-json",
            str(policy_json),
            "--target-region",
            str(target_region),
            "--work-dir",
            str(compare_dir),
            "--cases",
            str(int(ns.cases)),
            "--proposal-k",
            str(int(ns.proposal_k)),
            "--selection-mode",
            str(selection_mode),
        ]
        _run(compare_cmd)

        comparison_json = compare_dir / "comparison.json"
        comparison_payload = _load_json(comparison_json)
        results.append(
            {
                "profile": profile,
                "policy_json": str(policy_json),
                "comparison_json": str(comparison_json),
                "comparison": comparison_payload,
            }
        )

    def _throughput_key(item: dict[str, Any]) -> tuple[float, float]:
        comparison = dict(item.get("comparison") or {})
        delta = float(dict(comparison.get("delta") or {}).get("coverage_per_second") or 0.0)
        quality = (
            int(dict(comparison.get("policy_on") or {}).get("best_points_hit") or 0),
            -int(dict(comparison.get("policy_on") or {}).get("dead_region_count") or 0),
        )
        return (delta, float(quality[0]) + 0.01 * float(quality[1]))

    def _quality_key(item: dict[str, Any]) -> tuple[int, int, float]:
        comparison = dict(item.get("comparison") or {})
        policy_on = dict(comparison.get("policy_on") or {})
        delta = float(dict(comparison.get("delta") or {}).get("coverage_per_second") or 0.0)
        return (
            int(policy_on.get("best_points_hit") or 0),
            -int(policy_on.get("dead_region_count") or 0),
            delta,
        )

    best_by_throughput = max(results, key=_throughput_key) if results else {}
    best_by_quality = max(results, key=_quality_key) if results else {}

    payload = {
        "schema_version": "grpo-socket-profile-sweep-v1",
        "slice_name": slice_name,
        "target_region": target_region,
        "selection_mode": selection_mode,
        "proposal_k": int(ns.proposal_k),
        "results": results,
        "best_by_throughput": {
            "profile": str(best_by_throughput.get("profile") or ""),
            "comparison_json": str(best_by_throughput.get("comparison_json") or ""),
        },
        "best_by_quality": {
            "profile": str(best_by_quality.get("profile") or ""),
            "comparison_json": str(best_by_quality.get("comparison_json") or ""),
        },
    }

    json_out = (
        Path(ns.json_out).expanduser().resolve()
        if ns.json_out
        else work_dir / "profile_sweep.json"
    )
    md_out = json_out.with_suffix(".md")
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_out.write_text(_md_for_payload(payload), encoding="utf-8")
    print(json_out)
    print(md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
