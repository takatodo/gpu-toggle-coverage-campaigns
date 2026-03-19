#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from derive_toggle_coverage_generic_rules import (
    DEFAULT_ASSIGNMENTS_JSON,
    DEFAULT_RULES_JSON,
    _classify_slice,
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select a generic toggle-coverage rule family from current evidence or explicit features."
    )
    parser.add_argument("--rules-json", default=str(DEFAULT_RULES_JSON))
    parser.add_argument("--assignments-json", default=str(DEFAULT_ASSIGNMENTS_JSON))
    parser.add_argument("--slice", default="")
    parser.add_argument("--best-case-hit", type=int, default=0)
    parser.add_argument("--candidate-count", type=int, default=0)
    parser.add_argument("--campaign-backend", default="")
    parser.add_argument("--single-step-backend", default="")
    parser.add_argument("--multi-step-backend", default="")
    parser.add_argument("--recommended-stop", action="store_true")
    parser.add_argument("--json-out", default="")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    rules_payload = _load_json(Path(ns.rules_json).expanduser().resolve())
    rules_lookup = {
        str(rule.get("rule_family")): dict(rule)
        for rule in list(rules_payload.get("rules") or [])
    }

    if ns.slice:
        assignments_payload = _load_json(Path(ns.assignments_json).expanduser().resolve())
        assignment_lookup = {
            str(row.get("slice_name")): dict(row)
            for row in list(assignments_payload.get("rows") or [])
        }
        if ns.slice not in assignment_lookup:
            raise SystemExit(f"Unknown slice in assignments: {ns.slice}")
        assignment = assignment_lookup[ns.slice]
        rule_family = str(assignment.get("rule_family"))
        payload = {
            "selection_source": "current_assignment",
            "slice_name": ns.slice,
            "rule_family": rule_family,
            "classification_reasons": assignment.get("classification_reasons") or [],
            "recommended_rule": rules_lookup.get(rule_family, {}),
            "features": assignment,
        }
    else:
        features = {
            "slice_name": "",
            "single_step_backend": ns.single_step_backend,
            "multi_step_backend": ns.multi_step_backend,
            "campaign_backend": ns.campaign_backend,
            "best_case_hit": int(ns.best_case_hit),
            "recommended_campaign_candidate_count": int(ns.candidate_count),
            "recommended_stop": bool(ns.recommended_stop),
        }
        rule_family, reasons = _classify_slice(features)
        payload = {
            "selection_source": "feature_classifier",
            "rule_family": rule_family,
            "classification_reasons": reasons,
            "recommended_rule": rules_lookup.get(rule_family, {}),
            "features": features,
        }

    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if ns.json_out:
        Path(ns.json_out).expanduser().resolve().write_text(text, encoding="utf-8")
        print(Path(ns.json_out).expanduser().resolve())
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
