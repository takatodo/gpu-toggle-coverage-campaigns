#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
DESIGNS_ROOT = SCRIPT_DIR.parents[1] / "rtlmeter" / "designs"
DEFAULT_CANDIDATES_JSON = SCRIPT_DIR / "rtlmeter_design_gpu_toggle_candidates.json"
DEFAULT_JSON_OUT = SCRIPT_DIR / "rtlmeter_design_toggle_features.json"
DEFAULT_MD_OUT = SCRIPT_DIR / "rtlmeter_design_toggle_features.md"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _count_tests(descriptor: dict[str, Any], configuration: str) -> tuple[int, int, int]:
    config_node = dict(((descriptor.get("configurations") or {}).get(configuration)) or {})
    execute_node = dict(config_node.get("execute") or {})
    if not execute_node:
        execute_node = dict(descriptor.get("execute") or {})
    tests_node = dict(execute_node.get("tests") or {})
    sanity = 0
    standard = 0
    for test_cfg in tests_node.values():
        tags = set((test_cfg or {}).get("tags") or [])
        if "sanity" in tags:
            sanity += 1
        if "standard" in tags:
            standard += 1
    return len(tests_node), sanity, standard


def _feature_family(row: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    source_count = int(row.get("verilog_source_count") or 0)
    standard_tests = int(row.get("standard_test_count") or 0)
    top_module = str(row.get("top_module") or "")
    has_gpu_cov_tb = bool(row.get("has_gpu_cov_tb"))
    has_manifest = bool(row.get("has_coverage_manifest"))
    score = int(row.get("candidate_score") or 0)
    readiness = str(row.get("readiness") or "")

    if has_gpu_cov_tb and has_manifest and top_module.endswith("_gpu_cov_tb") and source_count >= 45:
        reasons.extend(
            [
                "gpu_cov wrapper present",
                "coverage manifest present",
                "top module already points at gpu_cov wrapper",
                "medium-to-large core source footprint",
            ]
        )
        if standard_tests > 0:
            reasons.append("standard test available")
        if readiness:
            reasons.append(f"readiness={readiness}")
        return "wrapper_ready_core", reasons

    if has_gpu_cov_tb and has_manifest:
        reasons.extend(
            [
                "gpu_cov wrapper present",
                "coverage manifest present",
            ]
        )
        if readiness:
            reasons.append(f"readiness={readiness}")
        return "wrapper_ready_general", reasons

    reasons.append("fallback generic external design")
    if score > 0:
        reasons.append(f"candidate_score={score}")
    return "generic_external_fallback", reasons


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract feature rows for RTLMeter gpu-toggle candidate designs."
    )
    parser.add_argument("--candidates-json", default=str(DEFAULT_CANDIDATES_JSON))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--md-out", default=str(DEFAULT_MD_OUT))
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    candidates_payload = _load_json(Path(ns.candidates_json).expanduser().resolve())

    rows: list[dict[str, Any]] = []
    for candidate in list(candidates_payload.get("candidates") or []):
        design = str(candidate.get("design") or "")
        if not design or design == "OpenTitan":
            continue

        descriptor_path = (DESIGNS_ROOT / design / "descriptor.yaml").resolve()
        if not descriptor_path.exists():
            continue
        descriptor = _load_yaml(descriptor_path)
        configuration = "gpu_cov"
        config_node = dict(((descriptor.get("configurations") or {}).get(configuration)) or {})
        compile_node = dict(config_node.get("compile") or {})
        execute_node = dict(config_node.get("execute") or {})
        top_module = str(compile_node.get("topModule") or descriptor.get("compile", {}).get("topModule") or "")
        config_source_files = list(compile_node.get("verilogSourceFiles") or [])
        config_common_files = list((execute_node.get("common") or {}).get("files") or [])
        has_gpu_cov_tb = any(str(path).endswith("_gpu_cov_tb.sv") for path in config_source_files)
        has_coverage_manifest = any(str(path).endswith("_coverage_regions.json") for path in config_common_files)
        test_count, sanity_count, standard_count = _count_tests(descriptor, configuration)
        feature_row = {
            "design": design,
            "configuration": configuration,
            "descriptor_path": str(descriptor_path),
            "candidate_score": int(candidate.get("score") or 0),
            "priority": str(candidate.get("priority") or ""),
            "readiness": str(candidate.get("readiness") or ""),
            "top_module": top_module,
            "verilog_source_count": int(candidate.get("verilog_source_count") or 0),
            "config_source_count": len(config_source_files),
            "has_gpu_cov_tb": has_gpu_cov_tb,
            "has_coverage_manifest": has_coverage_manifest,
            "test_count": test_count,
            "sanity_test_count": sanity_count,
            "standard_test_count": standard_count,
            "has_standard_test": standard_count > 0,
            "has_sanity_test": sanity_count > 0,
        }
        feature_family, reasons = _feature_family(feature_row)
        feature_row["feature_family"] = feature_family
        feature_row["feature_reasons"] = reasons
        rows.append(feature_row)

    payload = {
        "schema_version": "rtlmeter-design-toggle-features-v1",
        "rows": rows,
    }
    json_out = Path(ns.json_out).expanduser().resolve()
    md_out = Path(ns.md_out).expanduser().resolve()
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# RTLMeter Design Toggle Features",
        "",
        "| Design | Feature Family | Readiness | Top | Srcs | Tests | Sanity | Standard | Wrapper | Manifest | Reasons |",
        "|---|---|---|---|---:|---:|---:|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['design']} | {row['feature_family']} | {row['readiness']} | "
            f"{row['top_module']} | {row['verilog_source_count']} | {row['test_count']} | "
            f"{row['sanity_test_count']} | {row['standard_test_count']} | "
            f"{'yes' if row['has_gpu_cov_tb'] else 'no'} | "
            f"{'yes' if row['has_coverage_manifest'] else 'no'} | "
            f"{'; '.join(row['feature_reasons'])} |"
        )
    md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json_out)
    print(md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
