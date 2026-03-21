#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import subprocess
from typing import Any

from grpo_coverage_common import (
    GRPO_POLICY_PROFILES,
    GRPO_REWARD_PROFILES,
    load_json,
    missing_regions_from_summary,
    recommended_grpo_policy_profile,
    recommended_grpo_reward_profile,
    recommended_grpo_selection_mode,
    recommended_grpo_target_region,
)


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
INDEX_JSON = ROOT_DIR / "slice_launch_templates" / "index.json"
SWEEP_RUNNER = ROOT_DIR / "opentitan_support" / "run_opentitan_tlul_slice_trace_gpu_sweep.py"
GRPO_PHASE0_PIPELINE = SCRIPT_DIR / "run_grpo_phase0_pipeline.py"
DEFAULT_GRPO_SUMMARIES = (
    str((ROOT_DIR / ".grpo_seed_summaries" / "tlul_socket_1n_small" / "summary.json").resolve()),
    str((ROOT_DIR / ".grpo_seed_summaries" / "tlul_socket_m1_small" / "summary.json").resolve()),
    str((ROOT_DIR / ".grpo_seed_summaries" / "tlul_request_loopback_small" / "summary.json").resolve()),
    "/tmp/gpro_tlul_socket_1n_gpro_runner_v1/summary.json",
    "/tmp/gpro_tlul_socket_m1_gpro_runner_v1/summary.json",
    "/tmp/gpro_xbar_peri_gpro_runner_v3/summary.json",
)
DEFAULT_GRPO_SUMMARY_GLOBS = (
    str((ROOT_DIR / ".grpo_seed_summaries" / "*" / "summary.json").resolve()),
)

SLICE_GRPO_SUMMARY_HINTS = {
    "tlul_fifo_async": (
        ROOT_DIR / ".slice_rollout_runs" / "tlul_fifo_async_pilot_v2" / "tlul_fifo_async" / "sweep" / "summary.json",
    ),
}

_SUBPROCESS_PYTHONPATH_ENTRIES = (
    ROOT_DIR / "archive",
    ROOT_DIR / "gpu_backend",
    SCRIPT_DIR,
)


def _subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    existing = [entry for entry in str(env.get("PYTHONPATH") or "").split(":") if entry]
    merged: list[str] = []
    for entry in [str(path) for path in _SUBPROCESS_PYTHONPATH_ENTRIES] + existing:
        if entry and entry not in merged:
            merged.append(entry)
    env["PYTHONPATH"] = ":".join(merged)
    return env


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an aggressive GPU-guided coverage-improvement preset for OpenTitan TL-UL slices."
    )
    parser.add_argument("--slice", required=True)
    parser.add_argument("--phase", choices=("sweep", "campaign"), default="campaign")
    parser.add_argument("--index-json", default=str(INDEX_JSON))
    parser.add_argument("--work-dir", default="")
    parser.add_argument("--cases", type=int, default=0)
    parser.add_argument("--execution-engine", choices=("gpu", "cpu"), default="gpu")
    parser.add_argument("--launch-backend", choices=("auto", "source", "circt-cubin"), default="auto")
    parser.add_argument(
        "--search-scope-policy",
        choices=("auto", "off"),
        default="auto",
        help="Forward deterministic search-scope runtime shaping to the underlying sweep runner.",
    )
    parser.add_argument(
        "--static-prior-mode",
        choices=("auto", "off"),
        default="auto",
        help="Apply conservative compile/elaboration-based priors or disable them for A/B comparison.",
    )
    parser.add_argument(
        "--grpo-default-mode",
        choices=("auto", "off", "force"),
        default="auto",
        help="Auto-apply the canonical socket GRPO mode, disable it, or force it.",
    )
    parser.add_argument("--grpo-summary-json", action="append", default=[])
    parser.add_argument("--grpo-summary-glob", action="append", default=[])
    parser.add_argument(
        "--grpo-policy-profile",
        choices=("auto",) + tuple(sorted(GRPO_POLICY_PROFILES)),
        default="auto",
    )
    parser.add_argument(
        "--grpo-reward-profile",
        choices=("auto",) + tuple(sorted(GRPO_REWARD_PROFILES)),
        default="auto",
    )
    parser.add_argument("--grpo-target-region", default="auto")
    parser.add_argument(
        "--grpo-selection-mode",
        choices=("auto", "exact", "blend", "slice", "missing", "closure"),
        default="auto",
    )
    parser.add_argument("--grpo-missing-region", action="append", default=[])
    parser.add_argument("--grpo-proposal-k", type=int, default=0)
    parser.add_argument("--json-out", default="")
    return parser.parse_args(argv)


def _gpro_defaults(slice_name: str, phase: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "profile_family": "mixed",
        "variants_per_case": 13,
        "seed_fanout": 4,
        "keep_top_k": 64,
        "trace_length": 32,
        "batch_length": 64,
        "gpu_nstates": 96,
        "states_per_case": 4,
        "cases": 96 if phase == "campaign" else 128,
        "dead_word_bias": True,
        "cleanup_non_topk": True,
    }
    if slice_name in ("xbar_main", "xbar_peri"):
        base.update(
            {
                "keep_top_k": 96,
                "trace_length": 40,
                "batch_length": 72,
                "gpu_nstates": 128,
                "cases": 128 if phase == "campaign" else 192,
            }
        )
    elif slice_name in ("tlul_socket_1n", "tlul_socket_m1"):
        base.update(
            {
                "variants_per_case": 10,
                "seed_fanout": 3,
                "trace_length": 28,
                "batch_length": 56,
                "gpu_nstates": 96,
                "cases": 96 if phase == "campaign" else 160,
            }
        )
    return base


def _template_gpro_defaults(template_payload: dict[str, Any], phase: str) -> dict[str, Any]:
    runner_args = dict(template_payload.get("runner_args_template") or {})
    if not runner_args:
        return {}

    defaults: dict[str, Any] = {}
    for key in (
        "profile_family",
        "variants_per_case",
        "seed_fanout",
        "keep_top_k",
        "trace_length",
        "batch_length",
        "states_per_case",
        "dead_word_bias",
    ):
        if key in runner_args:
            defaults[key] = runner_args[key]

    if phase == "campaign" and "campaign_gpu_nstates" in runner_args:
        defaults["gpu_nstates"] = runner_args["campaign_gpu_nstates"]
    elif "gpu_nstates" in runner_args:
        defaults["gpu_nstates"] = runner_args["gpu_nstates"]

    # Use the template's pilot sweep budget as the default GPRO budget unless the
    # caller explicitly overrides --cases.
    if "pilot_sweep_cases" in runner_args:
        defaults["cases"] = runner_args["pilot_sweep_cases"]
    elif "cases" in runner_args:
        defaults["cases"] = runner_args["cases"]

    return defaults


def _existing_summary_inputs(paths: list[str]) -> list[str]:
    resolved: list[str] = []
    for raw in paths:
        path = Path(str(raw)).expanduser().resolve()
        if path.exists():
            resolved.append(str(path))
    return resolved


def _existing_summary_glob_inputs(patterns: list[str]) -> list[str]:
    import glob

    resolved: list[str] = []
    for raw in patterns:
        for match in sorted(glob.glob(str(raw), recursive=True)):
            path = Path(str(match)).expanduser().resolve()
            if path.exists():
                resolved.append(str(path))
    unique: list[str] = []
    seen: set[str] = set()
    for item in resolved:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json(path)
    return dict(payload) if isinstance(payload, dict) else {}


def _resolve_wrapper_json_out(*, work_dir: Path, requested: str) -> Path:
    if not requested:
        return work_dir / "gpro_run.json"
    requested_path = Path(requested).expanduser().resolve()
    runner_summary_json = (work_dir / "summary.json").resolve()
    if requested_path == runner_summary_json:
        return work_dir / "gpro_run.json"
    return requested_path


def _build_wrapper_payload(
    *,
    ns: argparse.Namespace,
    defaults: dict[str, Any],
    static_feature_adjustments: dict[str, Any],
    grpo_defaults: dict[str, Any],
    work_dir: Path,
    cmd: list[str],
) -> dict[str, Any]:
    runner_summary_json = work_dir / "summary.json"
    campaign_merge_view_json = work_dir / "summary.campaign_merge_view.json"
    runner_summary = _load_optional_json(runner_summary_json)
    merge_view = _load_optional_json(campaign_merge_view_json)
    best_case = dict(runner_summary.get("best_case") or merge_view.get("best_case") or {})
    cases = list(runner_summary.get("cases") or merge_view.get("cases") or [])
    ranking = list(runner_summary.get("ranking") or [])
    execution = dict(runner_summary.get("execution") or {})
    if not execution:
        launch_generation = dict(merge_view.get("launch_generation") or {})
        if launch_generation:
            execution = {"launch_count": int(launch_generation.get("launch_count") or 0)}
    return {
        "schema_version": "gpro-coverage-improvement-v2",
        "slice_name": ns.slice,
        "phase": ns.phase,
        "execution_engine": ns.execution_engine,
        "launch_backend": ns.launch_backend,
        "search_scope_policy": ns.search_scope_policy,
        "static_prior_mode": ns.static_prior_mode,
        "gpro_defaults": defaults,
        "static_feature_adjustments": static_feature_adjustments,
        "grpo_defaults": grpo_defaults,
        "work_dir": str(work_dir),
        "command": cmd,
        "summary_json": str(runner_summary_json),
        "campaign_merge_view_json": str(campaign_merge_view_json) if campaign_merge_view_json.exists() else "",
        "execution": execution,
        "best_case": best_case,
        "cases": cases,
        "ranking": ranking,
        "evaluated_case_count": int(
            runner_summary.get("evaluated_case_count")
            or merge_view.get("evaluated_case_count")
            or len(cases)
            or 0
        ),
        "total_candidate_space": int(
            runner_summary.get("total_candidate_space")
            or merge_view.get("total_candidate_space")
            or len(cases)
            or 0
        ),
    }


def _scale_positive_int(value: int, scale: float) -> int:
    return max(1, int(math.ceil(float(value) * float(scale))))


def _apply_static_feature_priors(
    *,
    template_payload: dict[str, Any],
    defaults: dict[str, Any],
    mode: str = "auto",
) -> tuple[dict[str, Any], dict[str, Any]]:
    adjusted = dict(defaults)
    features = dict(template_payload.get("static_features") or {})
    if str(mode) == "off":
        return adjusted, {
            "applied": False,
            "reason": "disabled_by_flag",
            "prior_class": str(features.get("search_prior_class") or "unknown"),
            "multi_clock": bool(features.get("multi_clock")),
        }
    if not features:
        return adjusted, {"applied": False, "reason": "missing_static_features"}

    budget_scale = dict(features.get("recommended_budget_scale") or {})
    cases_scale = float(budget_scale.get("cases") or 1.0)
    keep_top_k_scale = float(budget_scale.get("keep_top_k") or 1.0)
    prior_class = str(features.get("search_prior_class") or "standard")
    changed: dict[str, dict[str, Any]] = {}

    if "cases" in adjusted and cases_scale != 1.0:
        original = int(adjusted["cases"])
        updated = _scale_positive_int(original, cases_scale)
        if updated != original:
            adjusted["cases"] = updated
            changed["cases"] = {"before": original, "after": updated, "scale": cases_scale}
    if "keep_top_k" in adjusted and keep_top_k_scale != 1.0:
        original = int(adjusted["keep_top_k"])
        updated = _scale_positive_int(original, keep_top_k_scale)
        if updated != original:
            adjusted["keep_top_k"] = updated
            changed["keep_top_k"] = {"before": original, "after": updated, "scale": keep_top_k_scale}

    return adjusted, {
        "applied": bool(changed),
        "prior_class": prior_class,
        "multi_clock": bool(features.get("multi_clock")),
        "exclusive_word_fraction": features.get("exclusive_word_fraction"),
        "singleton_region_count": features.get("singleton_region_count"),
        "structural_connectivity_class": dict(features.get("structural_connectivity") or {}).get("structural_connectivity_class"),
        "reachable_output_fraction": dict(features.get("structural_connectivity") or {}).get("reachable_output_fraction"),
        "avg_input_reach_fraction": dict(features.get("structural_connectivity") or {}).get("avg_input_reach_fraction"),
        "budget_scale": {
            "cases": cases_scale,
            "keep_top_k": keep_top_k_scale,
        },
        "changed": changed,
    }


def _slice_specific_summary_inputs(slice_name: str) -> list[str]:
    normalized = str(slice_name or "").strip()
    if not normalized:
        return []
    candidates = list(SLICE_GRPO_SUMMARY_HINTS.get(normalized, ())) + [
        ROOT_DIR / ".grpo_seed_summaries" / f"{normalized}_small" / "summary.json",
        ROOT_DIR / ".grpo_seed_summaries" / normalized / "summary.json",
    ]
    resolved: list[str] = []
    for candidate in candidates:
        path = Path(candidate).expanduser().resolve()
        if path.exists():
            resolved.append(str(path))
    return resolved


def _derive_missing_regions_from_summaries(
    *,
    template_payload: dict[str, Any],
    summary_inputs: list[str],
) -> list[str]:
    if not summary_inputs:
        return []
    missing_sets: list[list[str]] = []
    for summary_json in summary_inputs:
        path = Path(str(summary_json)).expanduser().resolve()
        if not path.exists():
            continue
        summary_payload = load_json(path)
        missing_regions = missing_regions_from_summary(
            summary_payload=summary_payload,
            template_payload=template_payload,
        )
        if missing_regions:
            missing_sets.append(list(missing_regions))
    if not missing_sets:
        return []
    baseline = set(missing_sets[0])
    for item in missing_sets[1:]:
        baseline &= set(item)
    return sorted(baseline)


def _resolve_grpo_socket_defaults(
    *,
    slice_name: str,
    ns: argparse.Namespace,
    work_dir: Path,
    template_payload: dict[str, Any],
    defaults: dict[str, Any],
) -> dict[str, Any]:
    mode = str(ns.grpo_default_mode or "auto").strip() or "auto"
    if mode == "off" or str(ns.execution_engine) != "gpu":
        return {}

    profile = str(ns.grpo_policy_profile or "auto").strip() or "auto"
    if profile == "auto":
        profile = recommended_grpo_policy_profile(slice_name)
    if not profile:
        if mode == "force":
            raise SystemExit(f"No canonical GRPO profile is known for slice: {slice_name}")
        return {}

    target_region = str(ns.grpo_target_region or "auto").strip() or "auto"
    if target_region == "auto":
        target_region = recommended_grpo_target_region(slice_name)
    if not target_region:
        raise SystemExit(f"No canonical GRPO target region is known for slice: {slice_name}")

    selection_mode = str(ns.grpo_selection_mode or "auto").strip() or "auto"
    if selection_mode == "auto":
        selection_mode = recommended_grpo_selection_mode(slice_name)
    reward_profile = str(ns.grpo_reward_profile or "auto").strip() or "auto"
    if reward_profile == "auto":
        reward_profile = recommended_grpo_reward_profile(slice_name)

    summary_inputs = _existing_summary_inputs(list(ns.grpo_summary_json or []))
    if not summary_inputs:
        summary_inputs = _existing_summary_glob_inputs(list(ns.grpo_summary_glob or []))
    if not summary_inputs:
        summary_inputs = _slice_specific_summary_inputs(slice_name)
    if not summary_inputs:
        summary_inputs = _existing_summary_glob_inputs(list(DEFAULT_GRPO_SUMMARY_GLOBS))
    if not summary_inputs:
        summary_inputs = _existing_summary_inputs(list(DEFAULT_GRPO_SUMMARIES))
    if not summary_inputs:
        if mode == "force":
            raise SystemExit("No GRPO summary inputs exist for canonical socket defaults")
        return {}

    missing_regions = [str(region).strip() for region in list(ns.grpo_missing_region or []) if str(region).strip()]
    if not missing_regions:
        missing_regions = _derive_missing_regions_from_summaries(
            template_payload=template_payload,
            summary_inputs=summary_inputs,
        )

    profile_family = str(defaults.get("profile_family") or "dead-region")
    proposal_k = int(ns.grpo_proposal_k) if int(ns.grpo_proposal_k) > 0 else 2
    pipeline_dir = work_dir / "_grpo_default_policy"
    pipeline_cmd = [
        "python3",
        str(GRPO_PHASE0_PIPELINE),
        "--work-dir",
        str(pipeline_dir),
        "--policy-profile",
        str(profile),
        "--reward-profile",
        str(reward_profile),
        "--proposal-k",
        str(proposal_k),
        "--slice-name",
        str(slice_name),
        "--profile-family",
        str(profile_family),
        "--target-region",
        str(target_region),
        "--selection-mode",
        str(selection_mode),
    ]
    for missing_region in missing_regions:
        pipeline_cmd.extend(["--missing-region", str(missing_region)])
    for summary_json in summary_inputs:
        pipeline_cmd.extend(["--summary-json", str(summary_json)])
    subprocess.run(pipeline_cmd, cwd=SCRIPT_DIR, check=True, env=_subprocess_env())

    policy_json = pipeline_dir / "policy.json"
    if not policy_json.exists():
        raise SystemExit(f"GRPO policy generation did not produce: {policy_json}")
    return {
        "enabled": True,
        "policy_json": str(policy_json),
        "policy_profile": str(profile),
        "reward_profile": str(reward_profile),
        "target_region": str(target_region),
        "selection_mode": str(selection_mode),
        "proposal_k": proposal_k,
        "missing_regions": missing_regions,
        "summary_inputs": summary_inputs,
        "pipeline_summary_json": str(pipeline_dir / "pipeline_summary.json"),
    }


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    index_payload = load_json(Path(ns.index_json).expanduser().resolve())
    template_lookup = {
        str(entry.get("slice_name")): dict(entry)
        for entry in list(index_payload.get("index") or [])
    }
    template_entry = template_lookup.get(ns.slice)
    if not template_entry:
        raise SystemExit(f"Unknown slice: {ns.slice}")

    template_path = Path(str(template_entry.get("launch_template_path"))).expanduser().resolve()
    template_payload = load_json(template_path)
    defaults = _gpro_defaults(ns.slice, ns.phase)
    defaults.update(_template_gpro_defaults(template_payload, ns.phase))
    defaults, static_feature_adjustments = _apply_static_feature_priors(
        template_payload=template_payload,
        defaults=defaults,
        mode=str(ns.static_prior_mode),
    )
    work_dir = (
        Path(ns.work_dir).expanduser().resolve()
        if ns.work_dir
        else SCRIPT_DIR / "gpro_validation" / ns.slice / ns.phase
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    grpo_defaults = _resolve_grpo_socket_defaults(
        slice_name=str(ns.slice),
        ns=ns,
        work_dir=work_dir,
        template_payload=template_payload,
        defaults=defaults,
    )

    cmd = [
        "python3",
        str(SWEEP_RUNNER),
        "--launch-template",
        str(template_path),
        "--work-dir",
        str(work_dir),
        "--phase",
        str(ns.phase),
        "--execution-engine",
        str(ns.execution_engine),
        "--profile-family",
        str(defaults["profile_family"]),
        "--variants-per-case",
        str(int(defaults["variants_per_case"])),
        "--seed-fanout",
        str(int(defaults["seed_fanout"])),
        "--keep-top-k",
        str(int(defaults["keep_top_k"])),
        "--trace-length",
        str(int(defaults["trace_length"])),
        "--batch-length",
        str(int(defaults["batch_length"])),
        "--gpu-nstates",
        str(int(defaults["gpu_nstates"])),
        "--states-per-case",
        str(int(defaults["states_per_case"])),
        "--cases",
        str(int(ns.cases) if int(ns.cases) > 0 else int(defaults["cases"])),
        "--launch-backend",
        str(ns.launch_backend),
        "--search-scope-policy",
        str(ns.search_scope_policy),
    ]
    if bool(defaults.get("dead_word_bias")) and str(ns.execution_engine) == "gpu":
        cmd.append("--dead-word-bias")
    if bool(defaults.get("cleanup_non_topk")):
        cmd.append("--cleanup-non-topk")
    if bool(grpo_defaults.get("enabled")):
        cmd.extend(
            [
                "--grpo-policy-json",
                str(grpo_defaults["policy_json"]),
                "--grpo-target-region",
                str(grpo_defaults["target_region"]),
                "--grpo-proposal-k",
                str(int(grpo_defaults["proposal_k"])),
                "--grpo-selection-mode",
                str(grpo_defaults["selection_mode"]),
            ]
        )
        for missing_region in list(grpo_defaults.get("missing_regions") or []):
            cmd.extend(["--grpo-missing-region", str(missing_region)])

    subprocess.run(cmd, cwd=SCRIPT_DIR, check=True, env=_subprocess_env())

    payload = _build_wrapper_payload(
        ns=ns,
        defaults=defaults,
        static_feature_adjustments=static_feature_adjustments,
        grpo_defaults=grpo_defaults,
        work_dir=work_dir,
        cmd=cmd,
    )
    json_out = _resolve_wrapper_json_out(work_dir=work_dir, requested=str(ns.json_out or ""))
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
