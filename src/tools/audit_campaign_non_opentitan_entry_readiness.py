#!/usr/bin/env python3
"""
Check whether the recommended first non-OpenTitan entry can be executed in the
current environment, or whether the entry shape must be overridden.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_ENTRY_JSON = REPO_ROOT / "work" / "campaign_non_opentitan_entry.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_non_opentitan_entry_readiness.json"
DEFAULT_LEGACY_OUTPUT_DIR = REPO_ROOT / "output" / "legacy_validation"
DEFAULT_LEGACY_BENCH = REPO_ROOT / "third_party" / "verilator" / "bin" / "verilator_sim_accel_bench"
DEFAULT_LEGACY_VERILATOR = REPO_ROOT / "third_party" / "verilator" / "bin" / "verilator"
DEFAULT_RTLMETER_VENV = REPO_ROOT / "rtlmeter" / "venv" / "bin" / "python"
DEFAULT_BOOTSTRAP_SUMMARY_DIR = REPO_ROOT / "work"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _slug(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch.isalnum())


def _summarize_legacy_family_artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "readable": False,
            "result_count": 0,
            "failed_result_count": 0,
            "all_results_success": False,
            "failed_due_to_missing_legacy_bench": False,
        }
    try:
        payload = _read_json(path)
    except json.JSONDecodeError:
        return {
            "exists": True,
            "readable": False,
            "result_count": 0,
            "failed_result_count": 0,
            "all_results_success": False,
            "failed_due_to_missing_legacy_bench": False,
        }

    results = list(payload.get("results") or [])
    failed_results = [
        result
        for result in results
        if result.get("execute_status") != "success" or int(result.get("returncode") or 0) != 0
    ]
    missing_bench = any(
        "verilator_sim_accel_bench" in str(result.get("stderr_tail") or "")
        for result in failed_results
    )
    return {
        "exists": True,
        "readable": True,
        "result_count": len(results),
        "failed_result_count": len(failed_results),
        "all_results_success": bool(results) and not failed_results,
        "failed_due_to_missing_legacy_bench": missing_bench,
    }


def _family_matches_design(family: str, design: str) -> bool:
    normalized_family = (family or "").strip().lower()
    normalized_design = (design or "").strip().lower()
    if not normalized_family or not normalized_design:
        return False
    return normalized_design == normalized_family or normalized_design.startswith(f"{normalized_family}-")


def _summarize_bootstrap_candidates(family: str, summary_dir: Path) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for path in sorted(summary_dir.glob("*_stock_verilator_cc_bootstrap.json")):
        try:
            payload = _read_json(path)
        except json.JSONDecodeError:
            continue
        design = str(payload.get("design") or str(payload.get("compile_case") or "").split(":", 1)[0])
        if not _family_matches_design(family, design):
            continue
        status = str(payload.get("status") or "")
        classes_mk = str(payload.get("classes_mk") or "")
        ready = status == "ok" and bool(classes_mk)
        candidates.append(
            {
                "path": str(path.resolve()),
                "design": design,
                "config": str(payload.get("config") or ""),
                "compile_case": str(payload.get("compile_case") or ""),
                "status": status,
                "returncode": int(payload.get("returncode") or 0),
                "ready": ready,
            }
        )
    ready_candidates = [candidate for candidate in candidates if candidate["ready"]]
    return {
        "candidate_count": len(candidates),
        "ready_count": len(ready_candidates),
        "ready_designs": [candidate["design"] for candidate in ready_candidates],
        "candidates": candidates,
    }


def build_entry_readiness(
    *,
    entry_payload: dict[str, Any],
    legacy_output_dir: Path,
    legacy_bench_path: Path,
    legacy_verilator_path: Path,
    rtlmeter_venv_python: Path,
    bootstrap_summary_dir: Path,
) -> dict[str, Any]:
    decision = dict(entry_payload.get("decision") or {})
    family = str(decision.get("recommended_family") or "")
    entry_mode = str(decision.get("recommended_entry_mode") or "")
    slug = _slug(family)
    legacy_artifact = legacy_output_dir / f"{slug}_family_gpu_toggle_validation.json"
    legacy_artifact_summary = _summarize_legacy_family_artifact(legacy_artifact)
    bootstrap_summary = _summarize_bootstrap_candidates(family, bootstrap_summary_dir)

    prerequisites = {
        "legacy_bench_exists": legacy_bench_path.exists(),
        "legacy_verilator_exists": legacy_verilator_path.exists(),
        "rtlmeter_venv_python_exists": rtlmeter_venv_python.exists(),
        "legacy_family_artifact_exists": legacy_artifact.exists(),
        "single_surface_bootstrap_ready_count": bootstrap_summary["ready_count"],
    }

    if not family or not entry_mode:
        readiness = "no_recommended_entry"
        reason = "campaign_non_opentitan_entry_has_no_recommended_family_or_mode"
        recommended_next_tasks = [
            "Do not start a non-OpenTitan wave until campaign_non_opentitan_entry.json provides a family and entry mode.",
        ]
    elif entry_mode == "family_pilot":
        if legacy_artifact_summary["exists"] and not legacy_artifact_summary["readable"]:
            readiness = "legacy_family_artifact_unreadable"
            reason = "legacy_family_pilot_artifact_exists_but_is_not_valid_json"
            recommended_next_tasks = [
                f"Repair or remove the unreadable legacy pilot artifact at `{legacy_artifact}` before treating it as source of truth.",
                "After that, rerun the readiness audit to decide whether the family pilot is genuinely usable.",
            ]
        elif legacy_artifact_summary["exists"] and legacy_artifact_summary["all_results_success"]:
            readiness = "pilot_artifact_already_present"
            reason = "legacy_family_pilot_artifact_exists"
            recommended_next_tasks = [
                f"Read `{legacy_artifact}` as the current family-pilot source of truth.",
                "Decide whether to keep it as the first non-OpenTitan checkpoint or refresh it intentionally.",
            ]
        elif legacy_artifact_summary["exists"]:
            if (
                legacy_artifact_summary["failed_due_to_missing_legacy_bench"]
                and bootstrap_summary["ready_count"] > 0
            ):
                readiness = "legacy_family_pilot_failed_but_single_surface_override_ready"
                reason = "legacy_family_pilot_failed_but_stock_verilator_single_surface_bootstrap_exists"
                recommended_next_tasks = [
                    "Decide whether to keep `family_pilot` or explicitly override to `single_surface`.",
                    "If `family_pilot` remains preferred, restore `third_party/verilator/bin/verilator_sim_accel_bench`.",
                    f"If you override, promote one of the ready bootstrap candidates in `{bootstrap_summary_dir}` into the first stock-hybrid non-OpenTitan surface.",
                ]
            else:
                readiness = "legacy_family_pilot_failed"
                if legacy_artifact_summary["failed_due_to_missing_legacy_bench"]:
                    reason = "legacy_family_pilot_artifact_records_missing_legacy_bench"
                    recommended_next_tasks = [
                        "Restore `third_party/verilator/bin/verilator_sim_accel_bench` if family_pilot remains the chosen entry shape.",
                        f"Use `{legacy_artifact}` as the negative source of truth until that blocker is fixed or the entry shape is overridden.",
                    ]
                else:
                    reason = "legacy_family_pilot_artifact_records_failed_execution"
                    recommended_next_tasks = [
                        f"Inspect `{legacy_artifact}` before claiming the family pilot is ready.",
                        "Fix the recorded legacy pilot failure or explicitly override the entry shape.",
                    ]
        elif not prerequisites["legacy_bench_exists"]:
            if bootstrap_summary["ready_count"] > 0:
                readiness = "family_pilot_blocked_but_single_surface_override_ready"
                reason = "family_pilot_requires_legacy_bench_but_stock_verilator_single_surface_bootstrap_exists"
                recommended_next_tasks = [
                    "Decide whether to restore `third_party/verilator/bin/verilator_sim_accel_bench` or explicitly override to `single_surface`.",
                    f"Use the ready bootstrap candidates in `{bootstrap_summary_dir}` if you choose the override path.",
                ]
            else:
                readiness = "blocked_by_missing_legacy_bench"
                reason = "family_pilot_requires_verilator_sim_accel_bench"
                recommended_next_tasks = [
                    "Restore `third_party/verilator/bin/verilator_sim_accel_bench` if family_pilot remains the chosen entry shape.",
                    "If that toolchain will stay unavailable, explicitly override the entry shape instead of pretending family_pilot is ready.",
                ]
        elif not prerequisites["legacy_verilator_exists"]:
            readiness = "blocked_by_missing_legacy_verilator"
            reason = "family_pilot_requires_legacy_verilator_binary"
            recommended_next_tasks = [
                "Restore `third_party/verilator/bin/verilator` for the legacy family pilot path.",
            ]
        elif not prerequisites["rtlmeter_venv_python_exists"]:
            readiness = "blocked_by_missing_rtlmeter_venv"
            reason = "family_pilot_requires_rtlmeter_python_environment"
            recommended_next_tasks = [
                "Restore `rtlmeter/venv/bin/python` before running the family pilot.",
            ]
        else:
            readiness = "ready_to_run_family_pilot"
            reason = "all_family_pilot_prerequisites_present"
            recommended_next_tasks = [
                f"Run the `{family}` family pilot and write `{legacy_artifact}`.",
                "Only after that pilot lands should the project choose the first comparison surface inside the family.",
            ]
    else:
        readiness = "needs_entry_mode_specific_runner"
        reason = "single_surface_entry_requires_surface_selection_before_readiness_check"
        recommended_next_tasks = [
            f"Choose the first concrete `{family}` design before trying to assess single-surface readiness.",
        ]

    return {
        "schema_version": 1,
        "scope": "campaign_non_opentitan_entry_readiness",
        "recommended_family": family or None,
        "recommended_entry_mode": entry_mode or None,
        "legacy_family_artifact_path": str(legacy_artifact.resolve()),
        "legacy_family_artifact_summary": legacy_artifact_summary,
        "single_surface_bootstrap_summary": bootstrap_summary,
        "prerequisites": prerequisites,
        "decision": {
            "readiness": readiness,
            "reason": reason,
            "recommended_next_tasks": recommended_next_tasks,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entry-json", type=Path, default=DEFAULT_ENTRY_JSON)
    parser.add_argument("--legacy-output-dir", type=Path, default=DEFAULT_LEGACY_OUTPUT_DIR)
    parser.add_argument("--legacy-bench", type=Path, default=DEFAULT_LEGACY_BENCH)
    parser.add_argument("--legacy-verilator", type=Path, default=DEFAULT_LEGACY_VERILATOR)
    parser.add_argument("--rtlmeter-venv-python", type=Path, default=DEFAULT_RTLMETER_VENV)
    parser.add_argument("--bootstrap-summary-dir", type=Path, default=DEFAULT_BOOTSTRAP_SUMMARY_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_entry_readiness(
        entry_payload=_read_json(args.entry_json.resolve()),
        legacy_output_dir=args.legacy_output_dir.resolve(),
        legacy_bench_path=args.legacy_bench.resolve(),
        legacy_verilator_path=args.legacy_verilator.resolve(),
        rtlmeter_venv_python=args.rtlmeter_venv_python.resolve(),
        bootstrap_summary_dir=args.bootstrap_summary_dir.resolve(),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
