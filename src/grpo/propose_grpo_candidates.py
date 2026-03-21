#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from grpo_coverage_common import (
    context_key,
    load_json,
    missing_region_context_key,
    select_policy_candidates,
    slice_only_context_key,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Propose candidate action patches from the minimal GRPO policy."
    )
    parser.add_argument("--policy-json", required=True)
    parser.add_argument("--slice-name", required=True)
    parser.add_argument("--profile-family", required=True)
    parser.add_argument("--target-region", default="")
    parser.add_argument("--missing-region", action="append", default=[])
    parser.add_argument(
        "--selection-mode",
        choices=("exact", "blend", "slice", "missing", "closure"),
        default="exact",
    )
    parser.add_argument("--k", type=int, default=8)
    parser.add_argument("--json-out", default="")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    policy_payload = load_json(Path(ns.policy_json).expanduser().resolve())
    exact_key = context_key(
        slice_name=str(ns.slice_name),
        target_region=str(ns.target_region),
        profile_family=str(ns.profile_family),
    )
    slice_key = slice_only_context_key(
        slice_name=str(ns.slice_name),
        profile_family=str(ns.profile_family),
    )
    missing_key = missing_region_context_key(
        slice_name=str(ns.slice_name),
        profile_family=str(ns.profile_family),
        missing_regions=[str(region) for region in list(ns.missing_region or [])],
    )
    candidates = list((policy_payload.get("contexts") or {}).get(exact_key) or [])
    missing_candidates = list((policy_payload.get("missing_region_contexts") or {}).get(missing_key) or [])
    slice_candidates = list((policy_payload.get("slice_contexts") or {}).get(slice_key) or [])

    candidates, selection_meta = select_policy_candidates(
        exact_candidates=candidates,
        missing_candidates=missing_candidates,
        slice_candidates=slice_candidates,
        limit=max(1, int(ns.k)),
        selection_mode=str(ns.selection_mode or "exact"),
    )
    payload = {
        "schema_version": "minimal-grpo-proposals-v1",
        "policy_json": str(Path(ns.policy_json).expanduser().resolve()),
        "selection_rule": str(policy_payload.get("selection_rule") or ""),
        "selection_hyperparams": dict(policy_payload.get("selection_hyperparams") or {}),
        "slice_name": str(ns.slice_name),
        "profile_family": str(ns.profile_family),
        "target_region": str(ns.target_region),
        "missing_regions": [str(region) for region in list(ns.missing_region or []) if str(region).strip()],
        "selection_mode": str(selection_meta.get("selection_mode") or ""),
        "selection_source": str(selection_meta.get("selection_source") or ""),
        "primary_source": str(selection_meta.get("primary_source") or ""),
        "context_pool_sizes": dict(selection_meta.get("context_pool_sizes") or {}),
        "selected_from_counts": dict(selection_meta.get("selected_from_counts") or {}),
        "candidates": candidates,
    }
    if ns.json_out:
        json_out = Path(ns.json_out).expanduser().resolve()
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json_out)
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
