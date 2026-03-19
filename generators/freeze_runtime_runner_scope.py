#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_OUT = SCRIPT_DIR / "runtime_runner_scope.json"
DEFAULT_MD_OUT = SCRIPT_DIR / "runtime_runner_scope.md"


MAINLINE_RUNNERS = [
    {
        "runner": "run_rtlmeter_gpu_toggle_baseline.py",
        "classification": "mainline_default",
        "reason": "Shared GPU baseline runner that now defaults to direct bench reuse and underpins late-family gate reruns.",
        "evidence": [
            "/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/summary_auto.json",
            "/tmp/veer_el2_gpu_cov_gate_reuse_validation_v1/reuse_compare.json",
        ],
    },
    {
        "runner": "run_rtlmeter_design_rule_guided_sweep.py",
        "classification": "mainline_default",
        "reason": "Rule-guided GPU orchestrator in the frozen packet; defaults to reuse and device-aware batching.",
        "evidence": [
            "/tmp/device_aware_rule_slice_v1/run.json",
        ],
    },
    {
        "runner": "run_tier2_vortex_abc.py",
        "classification": "mainline_default",
        "reason": "Tier-2 A/B/C medium-design runner retained as part of the frozen rule evidence; flows B/C default to reuse.",
        "evidence": [
            "/tmp/metrics_driven_t2_exec_v2/B_gpu_metrics_only/summary.json",
            "/tmp/runtime_log_job/vortex_t2_B_reuse_v1/runtime_summary.json",
        ],
    },
    {
        "runner": "run_veer_family_gpu_toggle_validation.py",
        "classification": "mainline_default",
        "reason": "VeeR late-family gate runner retained in final packet scope and now defaults to reuse for gpu_cov_gate.",
        "evidence": [
            "/tmp/veer_eh1_gpu_cov_gate_reuse_validation_v1/reuse_compare.json",
            "/tmp/veer_el2_gpu_cov_gate_reuse_validation_v1/reuse_compare.json",
        ],
    },
    {
        "runner": "run_xuantie_family_gpu_toggle_validation.py",
        "classification": "mainline_default",
        "reason": "XuanTie late-family gate runner retained in final packet scope and now reaches direct_bench_kernel on warm reruns.",
        "evidence": [
            "/tmp/xuantie_family_gpu_cov_gate_baseline_v5/reuse_compare.json",
        ],
    },
    {
        "runner": "run_opentitan_tlul_slice_gpu_baseline.py",
        "classification": "mainline_default",
        "reason": "OpenTitan slice baseline family is part of the frozen packet and lands on cached_bundle_kernel with warm cache hits.",
        "evidence": [
            "/tmp/opentitan_slice_bundle_cache_validation_v1/bundle_reuse_compare.json",
        ],
    },
    {
        "runner": "run_opentitan_tlul_slice_trace_gpu_sweep.py",
        "classification": "mainline_default",
        "reason": "Low-level OpenTitan slice sweep chokepoint now carries device-aware batching policy.",
        "evidence": [
            "/tmp/slice_sweep_policy_validate_v1/summary.json",
        ],
    },
    {
        "runner": "run_opentitan_tlul_slice_trace_gpu_sweep_campaign.py",
        "classification": "mainline_default",
        "reason": "Low-level OpenTitan slice campaign chokepoint now carries device-aware batching policy.",
        "evidence": [
            "/tmp/slice_campaign_policy_validate_v1/campaign_manifest.json",
            "/tmp/slice_campaign_policy_validate_v1/summary.json",
        ],
    },
    {
        "runner": "run_opentitan_tlul_slice_backend_compare.py",
        "classification": "mainline_default",
        "reason": "Backend-compare runner now reuses cached bundles and remains part of the OpenTitan control-plane selection flow.",
        "evidence": [
            "/tmp/backend_compare_run_v3/backend_cache_compare.json",
            "/tmp/backend_compare_run_v3/backend_compare_run.json",
        ],
    },
    {
        "runner": "prepare_opentitan_tlul_slice_backend_compare.py",
        "classification": "mainline_support",
        "reason": "Plan generator for backend compare; kept because the compare runner depends on its cached-bundle plan outputs.",
        "evidence": [
            "/tmp/backend_compare_plan_v1/backend_compare_plan.json",
        ],
    },
]


SCOPED_OUT_RUNNERS = [
    {
        "runner": "run_veer_gpu_cov_cpu_debug.py",
        "classification": "debug_raw_debt",
        "reason": "Directly reruns an existing _execute/cmd with extra debug plusargs; it does not participate in the frozen packet or runtime-default stack.",
        "packet_required": False,
    },
    {
        "runner": "run_veer_direct_vsim.py",
        "classification": "debug_raw_debt",
        "reason": "Raw simulator bring-up/debug helper for obj_dir/Vsim execution; intentionally outside the mainline baseline/cached-bundle path.",
        "packet_required": False,
    },
    {
        "runner": "run_example_cpu_baseline.py",
        "classification": "tier0_cpu_harness",
        "reason": "Tier-0 CPU-only harness artifact used to anchor the smallest repeatable RTLMeter case, not part of the GPU runtime rollout.",
        "packet_required": False,
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the runtime runner scope into mainline defaults versus scoped-out debug/raw debt."
    )
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args()


def main() -> int:
    ns = parse_args()
    payload = {
        "schema_version": "runtime-runner-scope-v1",
        "status": "mainline_runtime_rollout_complete_scope_limited",
        "decision": "scope_out_debug_raw_runners",
        "mainline_runtime_runners": MAINLINE_RUNNERS,
        "scoped_out_runners": SCOPED_OUT_RUNNERS,
        "residual_mainline_rollout_runners": [],
        "rationale": [
            "The frozen rule packet already includes reuse, cached-bundle, and device-aware batching evidence for the runners that affect mainline validation.",
            "The remaining direct paths are debug/raw helpers or Tier-0 CPU-only artifacts and do not block the scope-limited frozen rule family.",
        ],
        "follow_on_debt": [
            "Only revisit scoped-out runners if the freeze scope later expands to require raw debug/runtime parity.",
        ],
    }
    ns.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Runtime Runner Scope",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']}`",
        "",
        "## Mainline Runtime Runners",
        "",
        "| Runner | Classification | Reason | Evidence |",
        "|---|---|---|---|",
    ]
    for row in MAINLINE_RUNNERS:
        evidence_text = "<br>".join(row["evidence"])
        lines.append(
            "| {runner} | {classification} | {reason} | {evidence} |".format(
                runner=row["runner"],
                classification=row["classification"],
                reason=row["reason"],
                evidence=evidence_text,
            )
        )
    lines.extend(
        [
            "",
            "## Scoped-Out Runners",
            "",
            "| Runner | Classification | Packet Required | Reason |",
            "|---|---|---|---|",
        ]
    )
    for row in SCOPED_OUT_RUNNERS:
        lines.append(
            "| {runner} | {classification} | {packet_required} | {reason} |".format(
                **row,
            )
        )
    lines.extend(["", "## Follow-On Debt", ""])
    for item in payload["follow_on_debt"]:
        lines.append(f"- {item}")
    ns.md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(ns.json_out)
    print(ns.md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
