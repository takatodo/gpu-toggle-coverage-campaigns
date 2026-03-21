#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Any

from grpo_coverage_common import (
    GRPO_POLICY_PROFILES,
    GRPO_REWARD_PROFILES,
    resolve_grpo_policy_profile,
)


SCRIPT_DIR = Path(__file__).resolve().parent
DATASET_BUILDER = SCRIPT_DIR / "build_grpo_offline_dataset.py"
TRAINER = SCRIPT_DIR / "train_grpo_policy_minimal.py"
PROPOSER = SCRIPT_DIR / "propose_grpo_candidates.py"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the phase-0 GRPO pipeline: dataset -> policy -> proposals."
    )
    parser.add_argument("--summary-json", action="append", default=[])
    parser.add_argument("--summary-glob", action="append", default=[])
    parser.add_argument("--work-dir", required=True)
    parser.add_argument("--top-k-per-group", type=int, default=8)
    parser.add_argument("--top-actions-per-context", type=int, default=6)
    parser.add_argument("--proposal-k", type=int, default=4)
    parser.add_argument("--slice-name", default="")
    parser.add_argument("--profile-family", default="")
    parser.add_argument("--target-region", default="")
    parser.add_argument("--missing-region", action="append", default=[])
    parser.add_argument(
        "--selection-mode",
        choices=("exact", "blend", "slice", "missing", "closure"),
        default="exact",
    )
    parser.add_argument(
        "--policy-profile",
        choices=tuple(sorted(GRPO_POLICY_PROFILES)),
        default="diversity",
    )
    parser.add_argument(
        "--reward-profile",
        choices=tuple(sorted(GRPO_REWARD_PROFILES)),
        default="balanced",
    )
    parser.add_argument("--diversity-weight", type=float, default=None)
    parser.add_argument("--rarity-weight", type=float, default=None)
    parser.add_argument("--frequency-novelty-weight", type=float, default=None)
    return parser.parse_args(argv)


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=SCRIPT_DIR, check=True)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    work_dir = Path(ns.work_dir).expanduser().resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    resolved_profile = resolve_grpo_policy_profile(
        str(ns.policy_profile),
        diversity_weight=ns.diversity_weight,
        rarity_weight=ns.rarity_weight,
        frequency_novelty_weight=ns.frequency_novelty_weight,
    )

    dataset_jsonl = work_dir / "dataset.jsonl"
    dataset_summary = work_dir / "dataset_summary.json"
    policy_json = work_dir / "policy.json"
    pipeline_summary = work_dir / "pipeline_summary.json"

    dataset_cmd = [
        "python3",
        str(DATASET_BUILDER),
        "--jsonl-out",
        str(dataset_jsonl),
        "--json-out",
        str(dataset_summary),
        "--top-k-per-group",
        str(int(ns.top_k_per_group)),
        "--reward-profile",
        str(ns.reward_profile),
    ]
    for summary_json in list(ns.summary_json or []):
        dataset_cmd.extend(["--summary-json", str(summary_json)])
    for summary_glob in list(ns.summary_glob or []):
        dataset_cmd.extend(["--summary-glob", str(summary_glob)])
    _run(dataset_cmd)

    trainer_cmd = [
        "python3",
        str(TRAINER),
        "--dataset-jsonl",
        str(dataset_jsonl),
        "--json-out",
        str(policy_json),
        "--top-actions-per-context",
        str(int(ns.top_actions_per_context)),
        "--reward-profile",
        str(ns.reward_profile),
        "--diversity-weight",
        str(float(resolved_profile["diversity_weight"])),
        "--rarity-weight",
        str(float(resolved_profile["rarity_weight"])),
        "--frequency-novelty-weight",
        str(float(resolved_profile["frequency_novelty_weight"])),
    ]
    _run(trainer_cmd)

    proposal_json = None
    if ns.slice_name and ns.profile_family:
        proposal_json = work_dir / "proposals.json"
        proposer_cmd = [
            "python3",
            str(PROPOSER),
            "--policy-json",
            str(policy_json),
            "--slice-name",
            str(ns.slice_name),
            "--profile-family",
            str(ns.profile_family),
            "--target-region",
            str(ns.target_region),
            "--selection-mode",
            str(ns.selection_mode),
            "--k",
            str(int(ns.proposal_k)),
            "--json-out",
            str(proposal_json),
        ]
        for missing_region in list(ns.missing_region or []):
            proposer_cmd.extend(["--missing-region", str(missing_region)])
        _run(proposer_cmd)

    proposal_overview: dict[str, Any] = {}
    if proposal_json is not None and proposal_json.exists():
        proposal_payload = _load_json(proposal_json)
        proposal_overview = {
            "selection_mode": str(proposal_payload.get("selection_mode") or ""),
            "selection_source": str(proposal_payload.get("selection_source") or ""),
            "primary_source": str(proposal_payload.get("primary_source") or ""),
            "context_pool_sizes": dict(proposal_payload.get("context_pool_sizes") or {}),
            "selected_from_counts": dict(proposal_payload.get("selected_from_counts") or {}),
            "candidate_count": len(list(proposal_payload.get("candidates") or [])),
        }

    payload = {
        "schema_version": "grpo-phase0-pipeline-v1",
        "dataset_summary_json": str(dataset_summary),
        "policy_json": str(policy_json),
        "proposal_json": str(proposal_json) if proposal_json is not None else "",
        "dataset_summary": _load_json(dataset_summary),
        "policy_overview": {
            "selection_rule": _load_json(policy_json).get("selection_rule", ""),
            "selection_hyperparams": dict(_load_json(policy_json).get("selection_hyperparams") or {}),
            "policy_profile": str(resolved_profile["policy_profile"]),
            "reward_profile": str(ns.reward_profile),
            "selection_mode": str(ns.selection_mode),
        },
        "proposal_overview": proposal_overview,
    }
    pipeline_summary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(pipeline_summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
