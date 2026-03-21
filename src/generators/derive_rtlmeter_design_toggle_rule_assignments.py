#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from derive_toggle_coverage_generic_rules import _classify_slice
from extract_rtlmeter_design_toggle_features import (
    DEFAULT_JSON_OUT as DEFAULT_FEATURES_JSON,
)


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CANDIDATES_JSON = SCRIPT_DIR / "rtlmeter_design_gpu_toggle_candidates.json"
DEFAULT_FEATURES_JSON = Path(DEFAULT_FEATURES_JSON)
DEFAULT_ASSIGNMENTS_JSON = SCRIPT_DIR / "rtlmeter_design_toggle_rule_assignments.json"
DEFAULT_ASSIGNMENTS_MD = SCRIPT_DIR / "rtlmeter_design_toggle_rule_assignments.md"
DESIGNS_ROOT = SCRIPT_DIR.parents[1] / "rtlmeter" / "designs"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_descriptor(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _select_tests(descriptor: dict[str, Any], configuration: str) -> tuple[list[str], list[str]]:
    config_node = dict(((descriptor.get("configurations") or {}).get(configuration)) or {})
    execute_node = dict(config_node.get("execute") or {})
    tests_node = dict(execute_node.get("tests") or {})
    if not tests_node:
        return [], []

    ordered_names = list(tests_node.keys())
    def _tags(name: str) -> list[str]:
        return list((tests_node.get(name) or {}).get("tags") or [])

    def _has_args(name: str) -> bool:
        return bool((tests_node.get(name) or {}).get("args") or [])

    sanity = [name for name in ordered_names if "sanity" in _tags(name)]
    standard = [name for name in ordered_names if "standard" in _tags(name)]
    zero_arg = [name for name in ordered_names if not _has_args(name)]
    zero_arg_sanity = [name for name in sanity if not _has_args(name)]
    zero_arg_standard = [name for name in standard if not _has_args(name)]

    if standard:
        sweep_tests = standard[:1]
    elif zero_arg_sanity:
        sweep_tests = zero_arg_sanity[:1]
    elif sanity:
        sweep_tests = sanity[:1]
    elif zero_arg:
        sweep_tests = zero_arg[:1]
    else:
        sweep_tests = ordered_names[:1]
    if standard:
        campaign_tests = standard[:1]
    elif zero_arg_standard:
        campaign_tests = zero_arg_standard[:1]
    elif zero_arg_sanity:
        campaign_tests = zero_arg_sanity[:1]
    elif zero_arg:
        campaign_tests = zero_arg[:1]
    elif sanity:
        campaign_tests = sanity[:1]
    else:
        campaign_tests = ordered_names[:1]
    return sweep_tests, campaign_tests


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Derive design-level generic rule assignments for RTLMeter gpu_cov-ready designs."
    )
    parser.add_argument("--candidates-json", default=str(DEFAULT_CANDIDATES_JSON))
    parser.add_argument("--features-json", default=str(DEFAULT_FEATURES_JSON))
    parser.add_argument("--json-out", default=str(DEFAULT_ASSIGNMENTS_JSON))
    parser.add_argument("--md-out", default=str(DEFAULT_ASSIGNMENTS_MD))
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    candidates_payload = _load_json(Path(ns.candidates_json).expanduser().resolve())
    features_payload = _load_json(Path(ns.features_json).expanduser().resolve())
    features_lookup = {
        str(row.get("design") or ""): dict(row)
        for row in list(features_payload.get("rows") or [])
    }
    rows: list[dict[str, Any]] = []

    for candidate in list(candidates_payload.get("candidates") or []):
        if str(candidate.get("readiness") or "") != "ready_for_gpu_toggle":
            continue
        design = str(candidate.get("design") or "")
        if not design or design == "OpenTitan":
            continue

        readiness_json = SCRIPT_DIR / f"{design.lower().replace('-', '_')}_gpu_toggle_readiness.json"
        readiness: dict[str, Any] = {}
        if readiness_json.exists():
            readiness = _load_json(readiness_json)
        descriptor_path = Path(
            str(((readiness.get("artifacts") or {}).get("descriptor")) or (DESIGNS_ROOT / design / "descriptor.yaml"))
        ).expanduser().resolve()
        if not descriptor_path.exists():
            continue

        configuration = str(readiness.get("configuration") or "gpu_cov")
        descriptor = _load_descriptor(descriptor_path)
        if configuration not in (descriptor.get("configurations") or {}):
            continue
        sweep_tests, campaign_tests = _select_tests(descriptor, configuration)
        feature_row = features_lookup.get(design, {})
        features = {
            "slice_name": design,
            "single_step_backend": "source",
            "multi_step_backend": "source",
            "campaign_backend": "source",
            "best_case_hit": 0,
            "recommended_campaign_candidate_count": 256,
            "recommended_stop": False,
        }
        rule_family, reasons = _classify_slice(features)
        classification_reasons = [
            "ready_for_gpu_toggle",
            *(feature_row.get("feature_reasons") or []),
            *reasons,
        ]
        rows.append(
            {
                "design": design,
                "configuration": configuration,
                "rule_family": rule_family,
                "classification_reasons": classification_reasons,
                "priority": str(candidate.get("priority") or ""),
                "candidate_score": int(candidate.get("score") or 0),
                "descriptor_path": str(descriptor_path),
                "readiness_json": str(readiness_json),
                "feature_family": str(feature_row.get("feature_family") or ""),
                "feature_readiness": str(feature_row.get("readiness") or ""),
                "verilog_source_count": int(feature_row.get("verilog_source_count") or 0),
                "test_count": int(feature_row.get("test_count") or 0),
                "standard_test_count": int(feature_row.get("standard_test_count") or 0),
                "sweep_tests": sweep_tests,
                "campaign_tests": campaign_tests,
                "default_execution_engine": "gpu",
                "workdir_hint": str(
                    SCRIPT_DIR / "rtlmeter_rule_guided_runs" / design / configuration
                ),
            }
        )

    payload = {
        "schema_version": "rtlmeter-design-toggle-rule-assignments-v1",
        "rows": rows,
    }
    json_out = Path(ns.json_out).expanduser().resolve()
    md_out = Path(ns.md_out).expanduser().resolve()
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# RTLMeter Design Toggle Rule Assignments",
        "",
        "| Design | Config | Rule | Feature Family | Priority | Score | Sweep Tests | Campaign Tests |",
        "|---|---|---|---|---|---:|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {design} | {configuration} | {rule_family} | {feature_family} | {priority} | {candidate_score} | {sweep} | {campaign} |".format(
                sweep=", ".join(row.get("sweep_tests") or []),
                campaign=", ".join(row.get("campaign_tests") or []),
                **row,
            )
        )
    md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json_out)
    print(md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
