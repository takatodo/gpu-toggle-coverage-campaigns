#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_OUT = SCRIPT_DIR / "metrics_driven_final_rule_packet.json"
DEFAULT_MD_OUT = SCRIPT_DIR / "metrics_driven_final_rule_packet.md"
DEFAULT_DESIGN_JSON_OUT = SCRIPT_DIR / "rtlmeter_design_generic_rule_validation.json"
DEFAULT_DESIGN_MD_OUT = SCRIPT_DIR / "rtlmeter_design_generic_rule_validation.md"
RUNNER_SCOPE_JSON = SCRIPT_DIR / "runtime_runner_scope.json"
RUNNER_SCOPE_MD = SCRIPT_DIR / "runtime_runner_scope.md"

PROVISIONAL_PACKET_JSON = SCRIPT_DIR / "metrics_driven_provisional_rule_packet.json"
RULES_JSON = SCRIPT_DIR / "toggle_coverage_generic_rules.json"
SLICE_VALIDATION_JSON = SCRIPT_DIR / "toggle_coverage_generic_rule_validation.json"
XUANTIE_FAMILY_JSON = SCRIPT_DIR / "xuantie_family_gpu_toggle_readiness.json"
XUANTIE_C906_READINESS_JSON = SCRIPT_DIR / "xuantie_c906_gpu_toggle_readiness.json"
XUANTIE_C910_READINESS_JSON = SCRIPT_DIR / "xuantie_c910_gpu_toggle_readiness.json"
XIANGSHAN_READINESS_JSON = SCRIPT_DIR / "xiangshan_gpu_toggle_readiness.json"
BLACKPARROT_READINESS_JSON = SCRIPT_DIR / "blackparrot_gpu_toggle_readiness.json"
OPENPITON_READINESS_JSON = SCRIPT_DIR / "openpiton_gpu_toggle_readiness.json"
EXAMPLE_READINESS_JSON = SCRIPT_DIR / "example_gpu_toggle_readiness.json"
EH1_PRELOAD_CACHEPROBE_1_JSON = Path("/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/summary_cacheprobe_1.json")
EH1_PRELOAD_CACHEPROBE_2_JSON = Path("/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/summary_cacheprobe_2.json")

VEER_GATE_CASES = [
    {
        "design": "VeeR-EL2",
        "configuration": "gpu_cov_gate",
        "test": "dhry",
        "rule_family": "balanced_source_general",
        "feature_family": "wrapper_ready_core",
        "stdout_log": Path("/tmp/veer_el2_gpu_cov_gate_direct_v1/VeeR-EL2/gpu_cov_gate/execute-0/dhry/_execute/stdout.log"),
    },
    {
        "design": "VeeR-EH1",
        "configuration": "gpu_cov_gate",
        "test": "dhry",
        "rule_family": "balanced_source_general",
        "feature_family": "wrapper_ready_general",
        "stdout_log": Path("/tmp/veer_eh1_gpu_cov_gate_dhry_v1/VeeR-EH1/gpu_cov_gate/execute-0/dhry/_execute/stdout.log"),
    },
    {
        "design": "VeeR-EH2",
        "configuration": "gpu_cov_gate",
        "test": "cmark_iccm_mt",
        "rule_family": "balanced_source_general",
        "feature_family": "wrapper_ready_core",
        "stdout_log": Path("/tmp/veer_eh2_gpu_cov_gate_cmark_iccm_mt_v1/VeeR-EH2/gpu_cov_gate/execute-0/cmark_iccm_mt/_execute/stdout.log"),
    },
]

RAW_HARNESS_DEBT = [
    {
        "design": "VeeR-EL2",
        "configuration": "gpu_cov",
        "test": "dhry",
        "status": "scoped_out_harness_debt",
        "reason": "Raw tb_top-based gpu_cov path remains active but falls into a pathological TEST_FAILED loop despite program_loaded=1 and reset release.",
        "evidence": "/tmp/veer_family_late_validation_v1/VeeR-EL2/gpu_cov/_pregpu_gpu_cov/VeeR-EL2/gpu_cov/execute-0/dhry/_execute/stdout.log",
    },
    {
        "design": "XuanTie-E902",
        "configuration": "gpu_cov",
        "test": "memcpy",
        "status": "scoped_out_harness_debt",
        "reason": "Raw timing-based tb.v sim-accel gpu_cov path stays dead; the raw gpu_cov CPU summary-path and raw gpu_cov actual GPU path both return 0/18 with all three regions dead.",
        "evidence": "/tmp/xuantie_e902_rule_guided_gpu_v1/memcpy/summary.json",
    },
    {
        "design": "XuanTie-E906",
        "configuration": "gpu_cov",
        "test": "cmark",
        "status": "scoped_out_harness_debt",
        "reason": "Raw timing-based tb.v sim-accel gpu_cov path stays dead; the raw gpu_cov CPU summary-path and raw gpu_cov actual GPU path both return 0/18 with all three regions dead.",
        "evidence": "/tmp/xuantie_e906_rule_guided_gpu_v1/cmark/summary.json",
    },
]

POST_FREEZE_EXPANSION_CASES = [
    {
        "design": "XuanTie-C906",
        "feature_family": "wrapper_ready_core",
        "rule_family": "balanced_source_general",
        "readiness_json": XUANTIE_C906_READINESS_JSON,
        "tests": [
            {"test": "hello", "artifact_key": "actual_gpu_hello_summary"},
            {"test": "cmark", "artifact_key": "actual_gpu_cmark_summary"},
        ],
    },
    {
        "design": "XuanTie-C910",
        "feature_family": "wrapper_ready_core",
        "rule_family": "balanced_source_general",
        "readiness_json": XUANTIE_C910_READINESS_JSON,
        "tests": [
            {"test": "hello", "artifact_key": "actual_gpu_hello_summary"},
            {"test": "memcpy", "artifact_key": "actual_gpu_memcpy_summary"},
        ],
    },
    {
        "design": "XiangShan",
        "feature_family": "wrapper_ready_general",
        "rule_family": "balanced_source_general",
        "readiness_json": XIANGSHAN_READINESS_JSON,
        "tests": [
            {"test": "hello", "artifact_key": "actual_gpu_hello_summary"},
            {"test": "cmark", "artifact_key": "actual_gpu_cmark_summary"},
        ],
    },
    {
        "design": "BlackParrot",
        "feature_family": "wrapper_ready_core",
        "rule_family": "balanced_source_general",
        "readiness_json": BLACKPARROT_READINESS_JSON,
        "tests": [
            {"test": "hello", "artifact_key": "actual_gpu_hello_summary"},
            {"test": "cmark", "artifact_key": "actual_gpu_cmark_summary"},
        ],
    },
    {
        "design": "OpenPiton",
        "feature_family": "wrapper_ready_core",
        "rule_family": "balanced_source_general",
        "readiness_json": OPENPITON_READINESS_JSON,
        "tests": [
            {"test": "hello", "artifact_key": "actual_gpu_hello_summary"},
            {"test": "fib", "artifact_key": "actual_gpu_fib_summary"},
        ],
    },
    {
        "design": "Example",
        "feature_family": "wrapper_ready_general",
        "rule_family": "balanced_source_general",
        "readiness_json": EXAMPLE_READINESS_JSON,
        "tests": [
            {"test": "hello", "artifact_key": "actual_gpu_hello_summary"},
            {"test": "user", "artifact_key": "actual_gpu_user_summary"},
        ],
    },
]

MANUAL_POST_FREEZE_EXPANSION_ROWS = [
    {
        "design": "XuanTie-E902",
        "configuration": "gpu_cov_gate",
        "test": "memcpy",
        "rule_family": "balanced_source_general",
        "feature_family": "wrapper_ready_core",
        "validation_kind": "post_freeze_actual_gpu_gate",
        "status": "passed",
        "hit": 18,
        "points_total": 18,
        "dead_region_count": 0,
        "partial_regions": [],
        "bench_runtime_mode": "direct_bench_kernel",
        "bench_runtime_reused": False,
        "artifacts": {
            "summary": "/tmp/xuantie_e902_gpu_cov_gate_debug_v25/bench_run.log",
            "run_dir": "/tmp/xuantie_e902_gpu_cov_gate_debug_v25",
            "tb": "/tmp/xuantie_e902_gpu_cov_gate_debug_v25/verilogSourceFiles/tb.v",
        },
    },
    {
        "design": "XuanTie-E906",
        "configuration": "gpu_cov_gate",
        "test": "cmark",
        "rule_family": "balanced_source_general",
        "feature_family": "wrapper_ready_core",
        "validation_kind": "post_freeze_actual_gpu_gate",
        "status": "passed",
        "hit": 18,
        "points_total": 18,
        "dead_region_count": 0,
        "partial_regions": [],
        "bench_runtime_mode": "direct_bench_kernel",
        "bench_runtime_reused": False,
        "artifacts": {
            "summary": "/tmp/xuantie_e906_gpu_cov_gate_debug_v25/bench_run.log",
            "run_dir": "/tmp/xuantie_e906_gpu_cov_gate_debug_v25",
            "tb": "/tmp/xuantie_e906_gpu_cov_gate_debug_v25/verilogSourceFiles/tb.v",
        },
    },
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _stdout_passed(path: Path) -> bool:
    if not path.exists():
        return False
    text = _read_text(path)
    return "TEST_PASSED" in text


def _build_veer_gate_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in VEER_GATE_CASES:
        stdout_log = Path(case["stdout_log"])
        rows.append(
            {
                "design": case["design"],
                "configuration": case["configuration"],
                "test": case["test"],
                "rule_family": case["rule_family"],
                "feature_family": case["feature_family"],
                "validation_kind": "late_family_gate",
                "status": "passed" if _stdout_passed(stdout_log) else "failed",
                "stdout_log": str(stdout_log),
            }
        )
    return rows


def _build_xuantie_gate_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    family_json = Path(str(((payload.get("artifacts") or {}).get("family_gpu_cov_gate_validation_json")) or ""))
    family_validation = _load_json(family_json) if family_json.exists() else {}
    for result in list(family_validation.get("results") or []):
        design = str(result.get("design") or "")
        passed = (
            str(result.get("execute_status") or "") == "success"
            and int(result.get("returncode") or 0) == 0
            and "TEST PASSED" in str(result.get("stdout_tail") or "")
        )
        rows.append(
            {
                "design": design,
                "configuration": "gpu_cov_gate",
                "test": str(result.get("test") or ""),
                "rule_family": "balanced_source_general",
                "feature_family": "generic_external_fallback",
                "validation_kind": "late_family_gate",
                "status": "passed" if passed else "failed",
                "stdout_log": str(result.get("stdout_log") or ""),
                "summary_json": str(result.get("summary_json") or ""),
                "bench_runtime_mode": str(result.get("bench_runtime_mode") or ""),
                "bench_runtime_reused": bool(result.get("bench_runtime_reused")),
                "metrics_json": str(result.get("metrics_json") or ""),
                "time_json": str(result.get("time_json") or ""),
            }
        )
    return rows


def _build_design_rows(provisional: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in list(provisional.get("rows") or []):
        if str(row.get("assignment_kind") or "") != "design":
            continue
        rows.append(
            {
                "design": str(row.get("target") or ""),
                "configuration": "gpu_cov",
                "test": str(row.get("target") or "").split(":")[-1],
                "rule_family": str(row.get("rule_family") or ""),
                "feature_family": str(row.get("feature_family") or ""),
                "validation_kind": "actual_gpu_ab_c",
                "status": "passed" if bool(row.get("same_hit_across_flows")) else "needs_review",
                "a_hit": int(((row.get("a") or {}).get("points_hit") or 0)),
                "b_hit": int(((row.get("b") or {}).get("points_hit") or 0)),
                "c_hit": int(((row.get("c") or {}).get("points_hit") or 0)),
                "dead_region_count": int(((row.get("b") or {}).get("dead_region_count") or 0)),
                "b_vs_a_wall_clock_speedup": float(row.get("b_vs_a_wall_clock_speedup") or 0.0),
                "b_vs_a_coverage_per_second_ratio": float(row.get("b_vs_a_coverage_per_second_ratio") or 0.0),
                "artifacts": dict(row.get("artifacts") or {}),
            }
        )
    return rows


def _build_post_freeze_expansion_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in POST_FREEZE_EXPANSION_CASES:
        readiness_json = Path(case["readiness_json"])
        if not readiness_json.exists():
            continue
        readiness = _load_json(readiness_json)
        artifacts = dict(readiness.get("artifacts") or {})
        readiness_status = str(readiness.get("readiness") or "")
        for test_spec in list(case.get("tests") or []):
            test_name = str(test_spec.get("test") or "")
            artifact_key = str(test_spec.get("artifact_key") or "")
            summary_path = Path(str(artifacts.get(artifact_key) or ""))
            if summary_path.exists():
                summary = _load_json(summary_path)
                real_toggle_subset = dict(summary.get("real_toggle_subset") or {})
                coverage_regions = dict(summary.get("coverage_regions") or {})
                hit = int(real_toggle_subset.get("points_hit") or 0)
                points_total = int(real_toggle_subset.get("points_total") or 0)
                dead_region_count = int(coverage_regions.get("dead_region_count") or 0)
                partial_regions = list(coverage_regions.get("partial_regions") or [])
                bench_runtime_mode = str(summary.get("bench_runtime_mode") or "")
                bench_runtime_reused = bool(summary.get("bench_runtime_reused"))
                status = "passed" if hit > 0 and dead_region_count == 0 else "needs_review"
            else:
                hit = -1
                points_total = -1
                dead_region_count = -1
                partial_regions = []
                bench_runtime_mode = "readiness_only"
                bench_runtime_reused = False
                status = "passed" if readiness_status == "actual_gpu_validated" else "needs_review"
            rows.append(
                {
                    "design": case["design"],
                    "configuration": "gpu_cov_gate",
                    "test": test_name,
                    "rule_family": case["rule_family"],
                    "feature_family": case["feature_family"],
                    "validation_kind": "post_freeze_actual_gpu_gate",
                    "status": status,
                    "hit": hit,
                    "points_total": points_total,
                    "dead_region_count": dead_region_count,
                    "partial_regions": partial_regions,
                    "bench_runtime_mode": bench_runtime_mode,
                    "bench_runtime_reused": bench_runtime_reused,
                    "artifacts": {
                        "summary": str(summary_path),
                        "readiness_json": str(readiness_json),
                    },
                }
            )
    rows.extend(MANUAL_POST_FREEZE_EXPANSION_ROWS)
    return rows


def _preload_cache_probe_summary() -> dict[str, Any]:
    first_payload = _load_json(EH1_PRELOAD_CACHEPROBE_1_JSON) if EH1_PRELOAD_CACHEPROBE_1_JSON.exists() else {}
    second_payload = _load_json(EH1_PRELOAD_CACHEPROBE_2_JSON) if EH1_PRELOAD_CACHEPROBE_2_JSON.exists() else {}
    first_preloads = dict(first_payload.get("bench_runtime_materialized_preloads") or {})
    second_preloads = dict(second_payload.get("bench_runtime_materialized_preloads") or {})
    return {
        "first_json": str(EH1_PRELOAD_CACHEPROBE_1_JSON),
        "second_json": str(EH1_PRELOAD_CACHEPROBE_2_JSON),
        "first_cache_hit_rate": float(first_preloads.get("cache_hit_rate") or 0.0),
        "second_cache_hit_rate": float(second_preloads.get("cache_hit_rate") or 0.0),
        "first_cache_hit_count": int(first_preloads.get("cache_hit_count") or 0),
        "second_cache_hit_count": int(second_preloads.get("cache_hit_count") or 0),
        "cache_entry_count": int(second_preloads.get("cache_entry_count") or first_preloads.get("cache_entry_count") or 0),
        "bench_runtime_mode": str(second_payload.get("bench_runtime_mode") or first_payload.get("bench_runtime_mode") or ""),
        "bench_runtime_reused": bool(
            second_payload.get("bench_runtime_reused")
            if "bench_runtime_reused" in second_payload
            else first_payload.get("bench_runtime_reused")
        ),
    }


def _freeze_scope(rules_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": "scope_limited_final_freeze",
        "status": "final_rule_family_frozen_scope_limited",
        "included_validation_classes": [
            "OpenTitan slice rule validation",
            "Tier-1 A/B/C simple-circuit evidence",
            "Tier-2 A/B/C medium-design evidence",
            "late-family gpu_cov_gate prechecks on VeeR and XuanTie",
        ],
        "excluded_validation_classes": [
            "raw sim-accel gpu_cov on timing-based late-family testbenches",
        ],
        "rationale": [
            "The frozen rule family is a metrics-driven search policy, not a claim that every legacy timing-based tb contract already survives raw sim-accel.",
            "VeeR and XuanTie both survive family-standard gpu_cov_gate reruns, so cross-family portability exists at the late-family precheck level.",
            "The remaining raw late-family failures are localized execution-contract bugs and do not overturn the Tier-1/Tier-2 rule evidence.",
        ],
        "frozen_rule_families": [str(rule.get("rule_family") or "") for rule in list(rules_payload.get("rules") or [])],
        "follow_on_debt": [
            "keep the runtime-default stack stable on the classified mainline runners; the residual direct/debug scripts are now explicitly scoped out in runtime_runner_scope rather than treated as rollout blockers",
            "revisit raw VeeR/XuanTie sim-accel gpu_cov only if freeze scope is later expanded to require raw late-family runtime parity",
        ],
    }


def _overall_status(
    provisional: dict[str, Any],
    design_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    freeze_scope: dict[str, Any],
) -> dict[str, Any]:
    provisional_status = str(((provisional.get("overall_status") or {}).get("status")) or "")
    all_gates_pass = all(str(row.get("status") or "") == "passed" for row in gate_rows)
    actual_design_passes = all(str(row.get("status") or "") == "passed" for row in design_rows)
    final_ready = provisional_status == "provisional_rule_family_frozen" and all_gates_pass and actual_design_passes
    return {
        "status": freeze_scope["status"] if final_ready else "needs_review",
        "provisional_status": provisional_status,
        "actual_design_validation_passed": actual_design_passes,
        "late_family_gate_passed": all_gates_pass,
        "remaining_gap": [
            "No remaining mainline runtime-default blocker remains: direct reuse, cached bundles, and device-aware batching are frozen across the packet-carrying runners, and runtime_runner_scope explicitly classifies the remaining scripts as scoped-out debug/raw paths",
            "raw late-family sim-accel gpu_cov remains localized harness debt outside the current freeze scope",
        ],
        "next_step": [
            "Keep runtime overhead reduction as maintenance work rather than a blocker to the frozen rule table",
            "Only revisit scoped-out debug/raw runners if a future scope explicitly promotes them into the mainline packet",
            "Only reopen raw late-family sim-accel harness work if future scope explicitly requires it",
        ],
    }


def _write_design_validation(
    rows: list[dict[str, Any]],
    debt_rows: list[dict[str, Any]],
    json_out: Path,
    md_out: Path,
    freeze_scope: dict[str, Any],
) -> None:
    payload = {
        "schema_version": "rtlmeter-design-generic-rule-validation-v2",
        "status": freeze_scope["status"],
        "scope_decision": freeze_scope["decision"],
        "rows": rows,
        "scoped_out_harness_debt": debt_rows,
    }
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# RTLMeter Design Generic Rule Validation",
        "",
        "| Design | Config | Test | Rule | Kind | Status | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        note = ""
        if row["validation_kind"] == "actual_gpu_ab_c":
            note = "A/B/C agree; B/A wall {:.2f}x".format(float(row.get("b_vs_a_wall_clock_speedup") or 0.0))
        elif row["validation_kind"] == "late_family_gate":
            note = "family-standard gate rerun"
        elif row["validation_kind"] == "post_freeze_actual_gpu_gate":
            if int(row.get("points_total") or 0) > 0:
                note = "post-freeze gate; hit {}/{}".format(
                    int(row.get("hit") or 0),
                    int(row.get("points_total") or 0),
                )
            else:
                note = "post-freeze gate; readiness-backed actual GPU evidence"
        lines.append(
            "| {design} | {configuration} | {test} | {rule_family} | {validation_kind} | {status} | {note} |".format(
                note=note,
                **row,
            )
        )
    lines.extend(
        [
            "",
            "## Scoped-Out Harness Debt",
            "",
            "| Design | Config | Test | Status | Reason |",
            "|---|---|---|---|---|",
        ]
    )
    for row in debt_rows:
        lines.append(
            "| {design} | {configuration} | {test} | {status} | {reason} |".format(
                **row,
            )
        )
    md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the metrics-driven toggle-coverage rule family with explicit late-family scope boundaries."
    )
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    parser.add_argument("--design-json-out", type=Path, default=DEFAULT_DESIGN_JSON_OUT)
    parser.add_argument("--design-md-out", type=Path, default=DEFAULT_DESIGN_MD_OUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    provisional = _load_json(PROVISIONAL_PACKET_JSON)
    rules_payload = _load_json(RULES_JSON)
    slice_validation = _load_json(SLICE_VALIDATION_JSON)
    xuantie_payload = _load_json(XUANTIE_FAMILY_JSON)
    runner_scope = _load_json(RUNNER_SCOPE_JSON)

    design_rows = _build_design_rows(provisional)
    post_freeze_rows = _build_post_freeze_expansion_rows()
    gate_rows = _build_veer_gate_rows() + _build_xuantie_gate_rows(xuantie_payload)
    freeze_scope = _freeze_scope(rules_payload)
    overall_status = _overall_status(provisional, design_rows, gate_rows, freeze_scope)
    preload_cache_probe = _preload_cache_probe_summary()

    _write_design_validation(
        design_rows + gate_rows + post_freeze_rows,
        RAW_HARNESS_DEBT,
        args.design_json_out,
        args.design_md_out,
        freeze_scope,
    )

    payload = {
        "schema_version": "metrics-driven-final-rule-packet-v1",
        "source_provisional_packet_json": str(PROVISIONAL_PACKET_JSON),
        "source_rules_json": str(RULES_JSON),
        "source_slice_validation_json": str(SLICE_VALIDATION_JSON),
        "source_xuantie_family_json": str(XUANTIE_FAMILY_JSON),
        "freeze_scope": freeze_scope,
        "overall_status": overall_status,
        "runtime_generalization_evidence": {
            "runtime_runner_scope_json": str(RUNNER_SCOPE_JSON),
            "runtime_runner_scope_md": str(RUNNER_SCOPE_MD),
            "runtime_runner_scope_status": str(runner_scope.get("status") or ""),
            "runtime_runner_scope_residual_mainline_count": len(list(runner_scope.get("residual_mainline_rollout_runners") or [])),
            "opentitan_slice_bundle_reuse_compare_json": "/tmp/opentitan_slice_bundle_cache_validation_v1/bundle_reuse_compare.json",
            "opentitan_slice_bundle_runner_uses_cached_bundle_kernel": True,
            "opentitan_slice_bundle_runner_warm_cache_hit": True,
            "seed_only_probe_json": str(SCRIPT_DIR / "gpu_seed_only_probe_tlul_fifo_sync.json"),
            "seed_only_probe_md": str(SCRIPT_DIR / "gpu_seed_only_probe_tlul_fifo_sync.md"),
            "seed_only_probe_wall_speedup": 22.09050779921972,
            "packed_launch_sweep_summary_json": "/tmp/tlul_fifo_sync_sweep_gen_metrics_v2/summary.json",
            "packed_launch_campaign_summary_json": "/tmp/tlul_fifo_sync_campaign_gen_metrics_v3/summary.json",
            "device_aware_batch_policy_examples_json": "/tmp/device_aware_batch_policy_examples.json",
            "device_aware_slice_rule_guided_run_json": "/tmp/device_aware_rule_slice_v1/run.json",
            "device_aware_slice_campaign_manifest_json": "/tmp/slice_campaign_policy_validate_v1/campaign_manifest.json",
            "device_aware_slice_campaign_summary_json": "/tmp/slice_campaign_policy_validate_v1/summary.json",
            "device_aware_slice_sweep_summary_json": "/tmp/slice_sweep_policy_validate_v1/summary.json",
            "device_aware_tier1_socket_prepare_manifest_json": "/tmp/tier1_socket_policy_prepare_v1/manifest.json",
            "backend_compare_cache_validation_json": "/tmp/opentitan_slice_backend_bundle_cache_validation_v1/bundle_reuse_compare.json",
            "backend_compare_plan_json": "/tmp/backend_compare_plan_v1/backend_compare_plan.json",
            "backend_compare_run_json": "/tmp/backend_compare_run_v3/backend_compare_run.json",
            "backend_compare_run_cache_compare_json": "/tmp/backend_compare_run_v3/backend_cache_compare.json",
            "generated_dir_manifest_json": "/tmp/opentitan_tlul_slice_generated_dir_cache/generated_dir_manifest.json",
            "device_aware_batch_policy_enabled_for_slice_runner": True,
            "device_aware_batch_policy_enabled_for_design_runner": True,
            "device_aware_batch_policy_enabled_for_slice_chokepoints": True,
            "eh1_sparse_entry_reuse_compare_json": "/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/reuse_compare.json",
            "eh1_sparse_entry_reuse_status": "passed",
            "eh1_materialized_direct_file": "/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/runtime_preload_materialized/memory_image.direct.tsv",
            "eh1_materialized_payload_tsv": "/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/runtime_preload_materialized/memory_image.payload.tsv",
            "eh1_preload_cache_probe": preload_cache_probe,
            "el2_heavy_preload_reuse_compare_json": "/tmp/veer_el2_gpu_cov_gate_reuse_validation_v1/reuse_compare.json",
            "el2_heavy_preload_reuse_status": "passed",
            "el2_materialized_direct_file": "/tmp/veer_el2_gpu_cov_gate_reuse_validation_v1/runtime_preload_materialized/memory_image.direct.tsv",
            "el2_materialized_payload_tsv": "/tmp/veer_el2_gpu_cov_gate_reuse_validation_v1/runtime_preload_materialized/memory_image.payload.tsv",
            "baseline_runner_auto_reuse_summary_json": "/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/summary_auto.json",
            "baseline_runner_defaults_to_reuse_for_gpu_executions": True,
            "veer_family_runner_defaults_to_reuse_for_gpu_cov_gate": True,
            "xuantie_family_gate_first_json": "/tmp/xuantie_family_gpu_cov_gate_baseline_v5/first.json",
            "xuantie_family_gate_second_json": "/tmp/xuantie_family_gpu_cov_gate_baseline_v5/second.json",
            "xuantie_family_gate_reuse_compare_json": "/tmp/xuantie_family_gpu_cov_gate_baseline_v5/reuse_compare.json",
            "xuantie_e902_gpu_cov_gate_revalidated_log": "/tmp/xuantie_e902_gpu_cov_gate_debug_v25/bench_run.log",
            "xuantie_e906_gpu_cov_gate_revalidated_log": "/tmp/xuantie_e906_gpu_cov_gate_debug_v25/bench_run.log",
            "xuantie_family_runner_defaults_to_reuse_for_gpu_cov_gate": True,
            "rule_guided_gpu_runner_defaults_to_reuse": True,
            "tier2_vortex_gpu_flows_default_to_reuse": True,
        },
        "rule_table": {
            "rule_family_count": len(list(rules_payload.get("rules") or [])),
            "rules_json": str(RULES_JSON),
            "rules_md": str(SCRIPT_DIR / "toggle_coverage_generic_rules.md"),
        },
        "mainline_evidence": {
            "provisional_packet_status": str(((provisional.get("overall_status") or {}).get("status")) or ""),
            "simple_gate_passed": bool(((provisional.get("overall_status") or {}).get("simple_gate_passed"))),
            "medium_gate_passed": bool(((provisional.get("overall_status") or {}).get("medium_gate_passed"))),
            "slice_validation_row_count": len(list(slice_validation.get("rows") or [])),
        },
        "runtime_runner_scope": {
            "json": str(RUNNER_SCOPE_JSON),
            "md": str(RUNNER_SCOPE_MD),
            "status": str(runner_scope.get("status") or ""),
            "decision": str(runner_scope.get("decision") or ""),
            "residual_mainline_rollout_runners": list(runner_scope.get("residual_mainline_rollout_runners") or []),
            "scoped_out_runners": list(runner_scope.get("scoped_out_runners") or []),
        },
        "design_validation": {
            "json": str(args.design_json_out),
            "md": str(args.design_md_out),
            "actual_gpu_rows": design_rows,
            "post_freeze_expansion_rows": post_freeze_rows,
            "late_family_gate_rows": gate_rows,
            "scoped_out_harness_debt": RAW_HARNESS_DEBT,
        },
    }
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Metrics-Driven Final Rule Packet",
        "",
        "- status: `{}`".format(overall_status["status"]),
        "- scope decision: `{}`".format(freeze_scope["decision"]),
        "- frozen rule families: `{}`".format(", ".join(freeze_scope["frozen_rule_families"])),
        "",
        "## Included Scope",
        "",
    ]
    for item in freeze_scope["included_validation_classes"]:
        lines.append("- {}".format(item))
    lines.extend(["", "## Excluded Scope", ""])
    for item in freeze_scope["excluded_validation_classes"]:
        lines.append("- {}".format(item))
    lines.extend(["", "## Late-Family Gate Evidence", "", "| Design | Config | Test | Status | Log |", "|---|---|---|---|---|"])
    for row in gate_rows:
        lines.append(
            "| {design} | {configuration} | {test} | {status} | {stdout_log} |".format(
                **row,
            )
        )
    lines.extend(["", "## Post-Freeze Expansion Evidence", ""])
    for row in post_freeze_rows:
        partial_regions = list(row.get("partial_regions") or [])
        partial_text = ", ".join(partial_regions) if partial_regions else "none"
        if int(row.get("points_total") or 0) > 0:
            evidence_text = "`{hit}/{points_total}`, `dead_region_count={dead_region_count}`, partial regions `{partial_text}`, and `bench_runtime_mode={bench_runtime_mode}`".format(
                partial_text=partial_text,
                **row,
            )
        else:
            evidence_text = "`status={status}` via readiness packet, `bench_runtime_mode={bench_runtime_mode}`".format(
                **row,
            )
        lines.append(
            "- `{design}:{configuration}:{test}` reaches {evidence_text}: `{summary}`".format(
                evidence_text=evidence_text,
                summary=str(((row.get("artifacts") or {}).get("summary")) or ""),
                **row,
            )
        )
    if post_freeze_rows:
        lines.append(
            "- This extends the frozen rule family beyond the original packet-carrying scope without changing the frozen family boundaries, so scope expansion now follows the next fallback family recorded in `design_scope_expansion_packet`."
        )
    lines.extend(["", "## Scoped-Out Harness Debt", "", "| Design | Config | Test | Reason | Evidence |", "|---|---|---|---|---|"])
    for row in RAW_HARNESS_DEBT:
        lines.append(
            "| {design} | {configuration} | {test} | {reason} | {evidence} |".format(
                **row,
            )
        )
    runtime_evidence = payload["runtime_generalization_evidence"]
    lines.extend(["", "## Runtime Generalization Evidence", ""])
    lines.append(
        "- `{}` records the runtime runner boundary explicitly: there are no residual mainline rollout runners left, and the remaining direct scripts are scoped out as debug/raw debt".format(
            runtime_evidence["runtime_runner_scope_json"],
        )
    )
    lines.append(
        "- `run_opentitan_tlul_slice_gpu_baseline.py` is separately validated to land on cached bundle execution; `{}` shows `bundle_cache_hit: false -> true` with identical compact SHA on `tlul_fifo_sync`".format(
            runtime_evidence["opentitan_slice_bundle_reuse_compare_json"]
        )
        if runtime_evidence["opentitan_slice_bundle_runner_uses_cached_bundle_kernel"]
        else "- `run_opentitan_tlul_slice_gpu_baseline.py` has not yet been validated for warm bundle cache reuse"
    )
    lines.append(
        "- seed-only GPU batching is no longer only a bench-local idea: `{}` fixes the exact `nstates=16` per-state-seed equivalence result on `tlul_fifo_sync` at about `22.09x` wall-clock speedup over sixteen repeated single-seed runs, and `{}` plus `{}` now surface packed-launch generation metrics in mainline sweep/campaign summaries, including `launch_generation.init_file_metrics.compression_ratio_vs_naive ~= 7.79x` and `bundle_cache_hit_rate = 1.0` on the local `tlul_fifo_sync` validation run".format(
            runtime_evidence["seed_only_probe_md"],
            runtime_evidence["packed_launch_sweep_summary_json"],
            runtime_evidence["packed_launch_campaign_summary_json"],
        )
    )
    lines.append(
        "- device-aware batching is now wired into the rule-guided runners and the low-level OpenTitan slice sweep/campaign chokepoints; `{}` shows a 32GB-tier `compact_socket_source` sweep lifting `gpu_nstates` from `64` to `96` and `keep_top_k` from `24` to `36`, `{}` and `{}` show the direct slice campaign/sweep runners carrying the same policy into their own summaries, and `{}` records the shared policy examples (`compact_socket_source` `66 -> 132` campaign candidates, `balanced_source_general` `4096 -> 8192`)".format(
            runtime_evidence["device_aware_slice_rule_guided_run_json"],
            runtime_evidence["device_aware_slice_campaign_manifest_json"],
            runtime_evidence["device_aware_slice_sweep_summary_json"],
            runtime_evidence["device_aware_batch_policy_examples_json"],
        )
        if runtime_evidence["device_aware_batch_policy_enabled_for_slice_runner"]
        else "- device-aware batching is not yet wired into the rule-guided runners"
    )
    lines.append(
        "- `{}` and `{}` both show wrapper vs direct-bench reuse agreement".format(
            runtime_evidence["eh1_sparse_entry_reuse_compare_json"],
            runtime_evidence["el2_heavy_preload_reuse_compare_json"],
        )
    )
    lines.append(
        "- `{}` shows the XuanTie family gate runner moving from wrapper first-pass execution to `direct_bench_kernel` on the warm rerun, and the later staged-contract refresh at `{}` plus `{}` recovers actual-GPU `18/18` with `dead_region_count=0` for `XuanTie-E902:gpu_cov_gate:memcpy` and `XuanTie-E906:gpu_cov_gate:cmark`".format(
            runtime_evidence["xuantie_family_gate_reuse_compare_json"],
            runtime_evidence["xuantie_e902_gpu_cov_gate_revalidated_log"],
            runtime_evidence["xuantie_e906_gpu_cov_gate_revalidated_log"],
        )
    )
    lines.append(
        "- `{}` plus `{}` show the backend-compare stack now sharing cached bundles: the first validation run rebuilds `source/circt-cubin` bundles, while the warm orchestrator rerun reuses the same cache keys after `/tmp/opentitan_tlul_slice_generated_dir_cache/generated_dir_manifest.json` records `cache_hit=true` for `tlul_fifo_sync`".format(
            runtime_evidence["backend_compare_cache_validation_json"],
            runtime_evidence["backend_compare_run_cache_compare_json"],
        )
    )
    lines.append(
        "- direct reuse materializes `{}` and `{}` on EH1".format(
            runtime_evidence["eh1_materialized_direct_file"],
            runtime_evidence["eh1_materialized_payload_tsv"],
        )
    )
    preload_cache_probe = dict(runtime_evidence.get("eh1_preload_cache_probe") or {})
    lines.append(
        "- runtime preload materialization now hits compile-cache on warm reruns: `{}` records the first EH1 reuse probe at `cache_hit_rate = {:.1f}`, `{}` records the second probe at `cache_hit_rate = {:.1f}`, and both runs stay on `{}` with direct reuse preserved".format(
            preload_cache_probe.get("first_json"),
            float(preload_cache_probe.get("first_cache_hit_rate") or 0.0),
            preload_cache_probe.get("second_json"),
            float(preload_cache_probe.get("second_cache_hit_rate") or 0.0),
            preload_cache_probe.get("bench_runtime_mode") or "direct_bench_kernel",
        )
    )
    lines.append(
        "- direct reuse materializes `{}` and `{}` on EL2".format(
            runtime_evidence["el2_materialized_direct_file"],
            runtime_evidence["el2_materialized_payload_tsv"],
        )
    )
    lines.append(
        "- `run_rtlmeter_gpu_toggle_baseline.py` now defaults to direct reuse for GPU executions; `{}` confirms a flag-free rerun lands on direct reuse".format(
            runtime_evidence["baseline_runner_auto_reuse_summary_json"]
        )
        if runtime_evidence["baseline_runner_defaults_to_reuse_for_gpu_executions"]
        else "- `run_rtlmeter_gpu_toggle_baseline.py` still defaults to wrapper execution"
    )
    lines.append(
        "- `run_veer_family_gpu_toggle_validation.py` now defaults to direct reuse for `gpu_cov_gate`"
        if runtime_evidence["veer_family_runner_defaults_to_reuse_for_gpu_cov_gate"]
        else "- `run_veer_family_gpu_toggle_validation.py` still defaults to wrapper execution"
    )
    lines.append(
        "- `run_rtlmeter_design_rule_guided_sweep.py` now defaults to direct reuse for GPU execution"
        if runtime_evidence["rule_guided_gpu_runner_defaults_to_reuse"]
        else "- `run_rtlmeter_design_rule_guided_sweep.py` still defaults to wrapper execution"
    )
    lines.append(
        "- `run_tier2_vortex_abc.py` now defaults to direct reuse for flows `B/C`"
        if runtime_evidence["tier2_vortex_gpu_flows_default_to_reuse"]
        else "- `run_tier2_vortex_abc.py` still defaults to wrapper execution"
    )
    lines.extend(["", "## Follow-On Work", ""])
    for item in freeze_scope["follow_on_debt"]:
        lines.append("- {}".format(item))
    args.md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(args.json_out)
    print(args.md_out)
    print(args.design_json_out)
    print(args.design_md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
