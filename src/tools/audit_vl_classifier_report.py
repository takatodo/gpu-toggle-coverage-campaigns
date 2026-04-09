#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _find_entry(functions: list[dict[str, Any]], expected: dict[str, Any]) -> dict[str, Any] | None:
    name_contains = expected.get("name_contains")
    detail_contains = expected.get("detail_contains")
    placement = expected.get("placement")
    reason = expected.get("reason")

    for entry in functions:
        if name_contains and name_contains not in str(entry.get("name", "")):
            continue
        if detail_contains and detail_contains not in str(entry.get("detail", "")):
            continue
        if placement and str(entry.get("placement")) != placement:
            continue
        if reason and str(entry.get("reason")) != reason:
            continue
        return entry
    return None


def audit_report(report: dict[str, Any], expectation: dict[str, Any]) -> dict[str, Any]:
    functions = list(report.get("functions") or [])
    counts = dict(report.get("counts") or {})

    expected_counts = dict(expectation.get("expected_counts") or {})
    count_mismatches: dict[str, dict[str, int]] = {}
    for key, expected_value in expected_counts.items():
        actual_value = int(counts.get(key, -1))
        if actual_value != int(expected_value):
            count_mismatches[key] = {
                "expected": int(expected_value),
                "actual": actual_value,
            }

    required_reasons = [str(item) for item in expectation.get("required_reasons") or []]
    present_reasons = {str(entry.get("reason")) for entry in functions}
    missing_reasons = [reason for reason in required_reasons if reason not in present_reasons]

    required_entries = list(expectation.get("required_entries") or [])
    matched_entries: list[dict[str, Any]] = []
    missing_entries: list[dict[str, Any]] = []
    for expected_entry in required_entries:
        matched = _find_entry(functions, expected_entry)
        if matched is None:
            missing_entries.append(expected_entry)
        else:
            matched_entries.append(
                {
                    "expected": expected_entry,
                    "matched_name": matched.get("name"),
                    "matched_reason": matched.get("reason"),
                    "matched_placement": matched.get("placement"),
                    "matched_detail": matched.get("detail"),
                }
            )

    passed = not count_mismatches and not missing_reasons and not missing_entries
    return {
        "schema_version": 1,
        "passed": passed,
        "target": expectation.get("target"),
        "report_eval_function": report.get("eval_function"),
        "report_path": expectation.get("report_path"),
        "expectation_path": expectation.get("expectation_path"),
        "counts": counts,
        "expected_counts": expected_counts,
        "count_mismatches": count_mismatches,
        "required_reasons": required_reasons,
        "missing_reasons": missing_reasons,
        "matched_entries": matched_entries,
        "missing_entries": missing_entries,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Audit a vl_classifier_report.json against a checked-in expectation file."
    )
    parser.add_argument("report", type=Path)
    parser.add_argument("--expect", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    report = _load_json(args.report.resolve())
    expectation = _load_json(args.expect.resolve())
    expectation["report_path"] = str(args.report.resolve())
    expectation["expectation_path"] = str(args.expect.resolve())
    summary = audit_report(report, expectation)

    if args.json_out:
        _write_json(args.json_out.resolve(), summary)

    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
