#!/usr/bin/env python3
"""
Summarize XuanTie-E906 case.pat experiments for the current stock-Verilator
single-surface line.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_VALIDATION_DIR = REPO_ROOT / "output" / "validation"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "xuantie_e906_case_variants.json"
DEFAULT_CASES = ("cmark", "hello", "memcpy")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _variant_paths(*, validation_dir: Path, case_name: str) -> tuple[Path, Path]:
    if case_name == "cmark":
        return (
            validation_dir / "xuantie_e906_stock_hybrid_validation.json",
            validation_dir / "xuantie_e906_cpu_baseline_validation.json",
        )
    suffix = f"_{case_name}"
    return (
        validation_dir / f"xuantie_e906_stock_hybrid_validation{suffix}.json",
        validation_dir / f"xuantie_e906_cpu_baseline_validation{suffix}.json",
    )


def _comparison_threshold2_path(*, validation_dir: Path) -> Path:
    return validation_dir / "xuantie_e906_time_to_threshold_comparison_threshold2.json"


def _measurement_bits(payload: dict[str, Any] | None) -> int | None:
    if not payload:
        return None
    measurement = dict(payload.get("campaign_measurement") or {})
    raw = measurement.get("bits_hit")
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    return None


def _measurement_threshold_ok(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    return bool(dict(payload.get("campaign_measurement") or {}).get("threshold_satisfied"))


def _threshold_value(payload: dict[str, Any] | None) -> int | None:
    if not payload:
        return None
    raw = dict(payload.get("campaign_threshold") or {}).get("value")
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    return None


def build_case_variants(*, validation_dir: Path = DEFAULT_VALIDATION_DIR) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    hybrid_bits_values: list[int] = []
    baseline_bits_values: list[int] = []
    for case_name in DEFAULT_CASES:
        stock_path, baseline_path = _variant_paths(validation_dir=validation_dir, case_name=case_name)
        stock_payload = _read_json(stock_path)
        baseline_payload = _read_json(baseline_path)
        stock_bits = _measurement_bits(stock_payload)
        baseline_bits = _measurement_bits(baseline_payload)
        if stock_bits is not None:
            hybrid_bits_values.append(stock_bits)
        if baseline_bits is not None:
            baseline_bits_values.append(baseline_bits)
        rows.append(
            {
                "case_name": case_name,
                "stock_hybrid_path": str(stock_path.resolve()),
                "stock_hybrid_status": (stock_payload or {}).get("status"),
                "stock_hybrid_bits_hit": stock_bits,
                "stock_hybrid_threshold_satisfied": _measurement_threshold_ok(stock_payload),
                "cpu_baseline_path": str(baseline_path.resolve()),
                "cpu_baseline_status": (baseline_payload or {}).get("status"),
                "cpu_baseline_bits_hit": baseline_bits,
                "cpu_baseline_threshold_satisfied": _measurement_threshold_ok(baseline_payload),
                "default_threshold_value": _threshold_value(stock_payload) or _threshold_value(baseline_payload),
                "runtime_case_pat": (stock_payload or {}).get("inputs", {}).get("case_pat")
                or (baseline_payload or {}).get("inputs", {}).get("case_pat"),
            }
        )

    threshold2_path = _comparison_threshold2_path(validation_dir=validation_dir)
    threshold2_payload = _read_json(threshold2_path)
    default_threshold_values = {
        row["default_threshold_value"]
        for row in rows
        if isinstance(row.get("default_threshold_value"), int)
    }
    max_hybrid_bits = max(hybrid_bits_values) if hybrid_bits_values else None
    max_baseline_bits = max(baseline_bits_values) if baseline_bits_values else None
    all_default_blocked = bool(rows) and all(not row["stock_hybrid_threshold_satisfied"] for row in rows)
    all_same_hybrid_bits = bool(hybrid_bits_values) and len(set(hybrid_bits_values)) == 1
    all_same_baseline_bits = bool(baseline_bits_values) and len(set(baseline_bits_values)) == 1

    if all_default_blocked and max_hybrid_bits == max_baseline_bits == 2 and all_same_hybrid_bits and all_same_baseline_bits:
        decision = {
            "status": "default_gate_blocked_across_known_case_pats",
            "reason": "all_checked_case_pats_plateau_at_bits_hit_2_under_the_default_threshold",
            "recommended_next_task": "treat_xuantie_e906_as_candidate_only_or_define_a_new_default_gate",
        }
    elif all_default_blocked:
        decision = {
            "status": "default_gate_still_blocked",
            "reason": "no_checked_case_pat_reaches_the_default_threshold",
            "recommended_next_task": "inspect_case_specific_headroom_before_promoting_e906",
        }
    else:
        decision = {
            "status": "default_gate_reached_by_known_case_pat",
            "reason": "at_least_one_checked_case_pat_reaches_the_default_threshold",
            "recommended_next_task": "promote_the_best_case_pat_into_the_next_e906_default_candidate",
        }

    return {
        "schema_version": 1,
        "scope": "xuantie_e906_case_variants",
        "default_case_variants": rows,
        "summary": {
            "case_count": len(rows),
            "default_threshold_values": sorted(default_threshold_values),
            "max_stock_hybrid_bits_hit": max_hybrid_bits,
            "max_cpu_baseline_bits_hit": max_baseline_bits,
            "all_default_blocked": all_default_blocked,
            "all_same_stock_hybrid_bits_hit": all_same_hybrid_bits,
            "all_same_cpu_baseline_bits_hit": all_same_baseline_bits,
        },
        "threshold2_candidate": {
            "comparison_path": str(threshold2_path.resolve()),
            "status": (threshold2_payload or {}).get("status"),
            "comparison_ready": bool((threshold2_payload or {}).get("comparison_ready")),
            "winner": (threshold2_payload or {}).get("winner"),
            "speedup_ratio": (threshold2_payload or {}).get("speedup_ratio"),
        },
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-dir", type=Path, default=DEFAULT_VALIDATION_DIR)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_case_variants(validation_dir=args.validation_dir.resolve())
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
