#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_HYBRID_BIN = REPO_ROOT / "src" / "hybrid" / "run_vl_hybrid"


def _parse_candidates(raw: str) -> list[int]:
    values: list[int] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        values.append(int(item, 0))
    if not values:
        raise ValueError("at least one stack candidate is required")
    return values


def _parse_trace(text: str) -> dict[str, Any]:
    last_stage = None
    updated_limit = None
    set_failed_target = None
    for line in text.splitlines():
        prefix = "run_vl_hybrid: stage="
        if line.startswith(prefix):
            last_stage = line[len(prefix) :].strip()
        if "run_vl_hybrid: ctx_limit STACK_SIZE updated=" in line:
            try:
                updated_limit = int(line.rsplit("=", 1)[1].strip())
            except ValueError:
                pass
        if "run_vl_hybrid: ctx_limit STACK_SIZE set_failed target=" in line:
            try:
                tail = line.split("target=", 1)[1]
                set_failed_target = int(tail.split()[0].strip())
            except ValueError:
                pass

    if "set_failed target=" in text:
        status = "stack_limit_invalid_argument"
    elif "CUDA error 1: invalid argument" in text:
        status = "invalid_argument"
    elif "ok: steps=" in text:
        status = "ok"
    elif updated_limit is not None:
        status = "stack_limit_updated"
    else:
        status = "unknown"

    return {
        "status": status,
        "last_stage": last_stage,
        "updated_limit": updated_limit,
        "set_failed_target": set_failed_target,
    }


def _run_once(
    *,
    hybrid_bin: Path,
    cubin: Path,
    storage_bytes: int,
    nstates: int,
    block_size: int,
    steps: int,
    stack_limit_override: int,
    probe_only: bool,
) -> dict[str, Any]:
    cmd = [
        str(hybrid_bin),
        str(cubin),
        str(storage_bytes),
        str(nstates),
        str(block_size),
        str(steps),
    ]
    env = dict(os.environ)
    env["RUN_VL_HYBRID_TRACE_STAGES"] = "1"
    env["RUN_VL_HYBRID_STACK_LIMIT_OVERRIDE"] = str(stack_limit_override)
    if probe_only:
        env["RUN_VL_HYBRID_STACK_LIMIT_PROBE_ONLY"] = "1"
    else:
        env.pop("RUN_VL_HYBRID_STACK_LIMIT_PROBE_ONLY", None)

    completed = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    text = "\n".join(part for part in [completed.stdout or "", completed.stderr or ""] if part)
    parsed = _parse_trace(text)
    return {
        "command": cmd,
        "probe_only": probe_only,
        "stack_limit_override": stack_limit_override,
        "returncode": completed.returncode,
        "status": parsed["status"],
        "last_stage": parsed["last_stage"],
        "updated_limit": parsed["updated_limit"],
        "set_failed_target": parsed["set_failed_target"],
        "stdout_tail": "\n".join((completed.stdout or "").splitlines()[-40:]),
        "stderr_tail": "\n".join((completed.stderr or "").splitlines()[-40:]),
    }


def build_payload(
    *,
    hybrid_bin: Path,
    cubin: Path,
    storage_bytes: int,
    nstates: int,
    block_size: int,
    steps: int,
    candidate_results: list[dict[str, Any]],
    launch_at_max: dict[str, Any] | None,
) -> dict[str, Any]:
    accepted = [
        result
        for result in candidate_results
        if result["probe_only"] and result["returncode"] == 0 and result["updated_limit"] is not None
    ]
    rejected = [
        result
        for result in candidate_results
        if result["probe_only"] and result["status"] == "stack_limit_invalid_argument"
    ]
    max_accepted = max((int(result["updated_limit"]) for result in accepted), default=None)
    min_rejected = min((int(result["stack_limit_override"]) for result in rejected), default=None)

    return {
        "schema_version": 1,
        "scope": "probe_vl_hybrid_stack_limit",
        "hybrid_bin": str(hybrid_bin),
        "cubin": str(cubin),
        "storage_bytes": storage_bytes,
        "nstates": nstates,
        "block_size": block_size,
        "steps": steps,
        "candidate_results": candidate_results,
        "accepted_stack_limits": [int(result["updated_limit"]) for result in accepted],
        "rejected_stack_limit_targets": [int(result["stack_limit_override"]) for result in rejected],
        "max_accepted_stack_limit": max_accepted,
        "min_rejected_stack_limit_target": min_rejected,
        "launch_at_max_result": launch_at_max,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe which CUDA stack-limit values run_vl_hybrid accepts for a given cubin."
    )
    parser.add_argument("--hybrid-bin", type=Path, default=DEFAULT_HYBRID_BIN)
    parser.add_argument("--cubin", type=Path, required=True)
    parser.add_argument("--storage-bytes", type=int, required=True)
    parser.add_argument("--nstates", type=int, default=1)
    parser.add_argument("--block-size", type=int, default=32)
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--candidates", required=True, help="Comma-separated stack-limit probe targets in bytes.")
    parser.add_argument(
        "--launch-at-max",
        action="store_true",
        help="After probe-only runs, launch once using the largest accepted stack limit.",
    )
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()

    hybrid_bin = args.hybrid_bin.resolve()
    cubin = args.cubin.resolve()
    json_out = args.json_out.resolve()
    if not hybrid_bin.is_file():
        raise FileNotFoundError(f"run_vl_hybrid not found: {hybrid_bin}")
    if not cubin.is_file():
        raise FileNotFoundError(f"cubin not found: {cubin}")

    candidates = _parse_candidates(args.candidates)
    candidate_results = [
        _run_once(
            hybrid_bin=hybrid_bin,
            cubin=cubin,
            storage_bytes=args.storage_bytes,
            nstates=args.nstates,
            block_size=args.block_size,
            steps=args.steps,
            stack_limit_override=value,
            probe_only=True,
        )
        for value in candidates
    ]

    accepted_limits = [
        int(result["updated_limit"])
        for result in candidate_results
        if result["returncode"] == 0 and result["updated_limit"] is not None
    ]
    launch_at_max = None
    if args.launch_at_max and accepted_limits:
        launch_at_max = _run_once(
            hybrid_bin=hybrid_bin,
            cubin=cubin,
            storage_bytes=args.storage_bytes,
            nstates=args.nstates,
            block_size=args.block_size,
            steps=args.steps,
            stack_limit_override=max(accepted_limits),
            probe_only=False,
        )

    payload = build_payload(
        hybrid_bin=hybrid_bin,
        cubin=cubin,
        storage_bytes=args.storage_bytes,
        nstates=args.nstates,
        block_size=args.block_size,
        steps=args.steps,
        candidate_results=candidate_results,
        launch_at_max=launch_at_max,
    )
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
