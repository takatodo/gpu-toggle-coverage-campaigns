#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import yaml


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
DESIGNS_ROOT = REPO_ROOT / "rtlmeter" / "designs"
DEFAULT_JSON = SCRIPT_DIR / "rtlmeter_design_gpu_toggle_candidates.json"
DEFAULT_MD = SCRIPT_DIR / "rtlmeter_design_gpu_toggle_candidates.md"

PREFERRED_CPU_DESIGNS = {
    "VeeR-EL2",
    "VeeR-EH1",
    "VeeR-EH2",
    "XuanTie-E902",
    "XuanTie-E906",
}

HEAVY_DESIGNS = {
    "BlackParrot",
    "Caliptra",
    "NVDLA",
    "OpenPiton",
    "OpenTitan",
    "XiangShan",
    "XuanTie-C906",
    "XuanTie-C910",
}

MEDIUM_COMPLEXITY_DESIGNS = {"Vortex"}


@dataclass
class CandidateAssessment:
    design: str
    top_module: str
    verilog_source_count: int
    test_count: int
    config_count: int
    has_standard_test: bool
    has_sanity_test: bool
    has_gpu_cov_tb: bool
    has_coverage_manifest: bool
    score: int
    priority: str
    readiness: str
    rationale: list[str]
    next_step: str


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text()) or {}


def _collect_tags(data: dict[str, Any]) -> tuple[set[str], set[str]]:
    sanity: set[str] = set()
    standard: set[str] = set()

    top_level_tests = ((data.get("execute") or {}).get("tests") or {})
    for test_name, test_data in top_level_tests.items():
        tags = set((test_data or {}).get("tags") or [])
        if "sanity" in tags:
            sanity.add(f"default:{test_name}")
        if "standard" in tags:
            standard.add(f"default:{test_name}")

    for config_name, config in (data.get("configurations") or {}).items():
        tests = ((config.get("execute") or {}).get("tests") or {})
        for test_name, test_data in tests.items():
            tags = set((test_data or {}).get("tags") or [])
            if "sanity" in tags:
                sanity.add(f"{config_name}:{test_name}")
            if "standard" in tags:
                standard.add(f"{config_name}:{test_name}")
    return sanity, standard


def _gpu_cov_contract(
    data: dict[str, Any],
    *,
    src_dir: Path,
    tests_dir: Path,
) -> tuple[str, bool, bool]:
    configurations = dict(data.get("configurations") or {})
    gpu_cov_node = dict(configurations.get("gpu_cov") or {})
    gpu_cov_compile = dict(gpu_cov_node.get("compile") or {})
    gpu_cov_execute = dict(gpu_cov_node.get("execute") or {})

    top_module = str(
        gpu_cov_compile.get("topModule")
        or (data.get("compile") or {}).get("topModule")
        or ""
    )

    config_sources = list(gpu_cov_compile.get("verilogSourceFiles") or [])
    config_common_files = list((gpu_cov_execute.get("common") or {}).get("files") or [])
    has_gpu_cov_tb = any(str(path).endswith("_gpu_cov_tb.sv") for path in config_sources) or any(
        src_dir.glob("*gpu_cov_tb.sv")
    )
    has_manifest = any(str(path).endswith("_coverage_regions.json") for path in config_common_files) or any(
        tests_dir.glob("*coverage_regions.json")
    )
    return top_module, has_gpu_cov_tb, has_manifest


def _score_design(
    design: str,
    n_src: int,
    has_standard: bool,
    has_sanity: bool,
    has_gpu_cov_tb: bool,
    has_manifest: bool,
) -> tuple[int, list[str]]:
    score = 0
    rationale: list[str] = []

    if n_src <= 80:
        score += 4
        rationale.append("source_count_small")
    elif n_src <= 160:
        score += 3
        rationale.append("source_count_medium_small")
    elif n_src <= 320:
        score += 1
        rationale.append("source_count_medium")
    elif n_src > 500:
        score -= 2
        rationale.append("source_count_large")

    if has_standard:
        score += 2
        rationale.append("has_standard_test")
    if has_sanity:
        score += 1
        rationale.append("has_sanity_test")

    if design in PREFERRED_CPU_DESIGNS:
        score += 3
        rationale.append("preferred_single_core_cpu_family")
    if design in MEDIUM_COMPLEXITY_DESIGNS:
        score -= 1
        rationale.append("medium_complexity_accelerator_style")
    if design in HEAVY_DESIGNS:
        score -= 3
        rationale.append("heavy_soc_style")

    if has_gpu_cov_tb and has_manifest:
        score += 4
        rationale.append("already_gpu_toggle_ready")
    elif has_gpu_cov_tb or has_manifest:
        score += 1
        rationale.append("partial_gpu_toggle_artifacts")
    else:
        rationale.append("missing_gpu_toggle_artifacts")

    return score, rationale


def _priority_from_score(score: int) -> str:
    if score >= 7:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def _readiness(has_gpu_cov_tb: bool, has_manifest: bool, top_module: str) -> str:
    if has_gpu_cov_tb and has_manifest and top_module.endswith("_gpu_cov_tb"):
        return "ready_for_gpu_toggle"
    if has_gpu_cov_tb and has_manifest:
        return "gpu_toggle_contract_ready"
    if has_gpu_cov_tb or has_manifest:
        return "partial_gpu_toggle_contract"
    return "needs_gpu_cov_tb_and_manifest"


def _next_step(design: str, readiness: str) -> str:
    if readiness == "ready_for_gpu_toggle":
        if design == "OpenTitan":
            return f"run rule-guided sweep/campaign pilot for {design}"
        return f"integrate {design} gpu_cov flow with generic baseline/pilot runner"
    if readiness == "partial_gpu_toggle_contract":
        return f"complete missing GPU toggle contract artifact for {design}"
    return f"add {design} gpu_cov_tb and coverage_regions manifest"


def assess_design(descriptor_path: Path) -> CandidateAssessment:
    data = _load_yaml(descriptor_path)
    design = descriptor_path.parent.name
    compile_cfg = data.get("compile") or {}
    execute_cfg = data.get("execute") or {}
    sanity, standard = _collect_tags(data)

    src_dir = descriptor_path.parent / "src"
    tests_dir = descriptor_path.parent / "tests"
    top_module, has_gpu_cov_tb, has_manifest = _gpu_cov_contract(
        data,
        src_dir=src_dir,
        tests_dir=tests_dir,
    )

    score, rationale = _score_design(
        design=design,
        n_src=len(compile_cfg.get("verilogSourceFiles") or []),
        has_standard=bool(standard),
        has_sanity=bool(sanity),
        has_gpu_cov_tb=has_gpu_cov_tb,
        has_manifest=has_manifest,
    )
    readiness = _readiness(has_gpu_cov_tb, has_manifest, top_module)
    return CandidateAssessment(
        design=design,
        top_module=top_module,
        verilog_source_count=len(compile_cfg.get("verilogSourceFiles") or []),
        test_count=len(execute_cfg.get("tests") or {}),
        config_count=len(data.get("configurations") or {}),
        has_standard_test=bool(standard),
        has_sanity_test=bool(sanity),
        has_gpu_cov_tb=has_gpu_cov_tb,
        has_coverage_manifest=has_manifest,
        score=score,
        priority=_priority_from_score(score),
        readiness=readiness,
        rationale=rationale,
        next_step=_next_step(design, readiness),
    )


def render_markdown(rows: list[CandidateAssessment]) -> str:
    lines = [
        "# RTLMeter GPU Toggle Candidate Ranking",
        "",
        "| Design | Priority | Score | Sources | Standard | Sanity | GPU TB | Manifest | Readiness | Next step |",
        "|---|---|---:|---:|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {design} | {priority} | {score} | {verilog_source_count} | {has_standard_test} | {has_sanity_test} | {has_gpu_cov_tb} | {has_coverage_manifest} | {readiness} | {next_step} |".format(
                **asdict(row)
            )
        )
    lines.extend(
        [
            "",
            "## Recommended Next Designs",
            "",
        ]
    )
    for row in rows[:5]:
        lines.append(f"- `{row.design}`: {row.priority}, {row.readiness}, {', '.join(row.rationale)}")
    return "\n".join(lines) + "\n"


def main() -> int:
    descriptor_paths = sorted(DESIGNS_ROOT.glob("*/descriptor.yaml"))
    rows = [assess_design(path) for path in descriptor_paths]
    rows.sort(key=lambda row: (-row.score, row.verilog_source_count, row.design.lower()))
    payload = {
        "schema_version": "rtlmeter-design-gpu-toggle-candidates-v1",
        "designs_root": str(DESIGNS_ROOT),
        "descriptor_count": len(descriptor_paths),
        "candidates": [asdict(row) for row in rows],
        "recommended_next_designs": [row.design for row in rows[:5]],
    }
    DEFAULT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    DEFAULT_MD.write_text(render_markdown(rows))
    print(DEFAULT_JSON)
    print(DEFAULT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
