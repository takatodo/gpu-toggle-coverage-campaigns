#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from stock_hybrid_validation_common import (
    campaign_threshold_toggle_bits_hit,
    parse_gpu_metrics,
    read_json_if_exists,
    toggle_coverage_summary,
    write_json,
)


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
FLOW_TOOL = ROOT_DIR / "src" / "tools" / "run_tlul_request_loopback_host_gpu_flow.py"
DEFAULT_MDIR = ROOT_DIR / "work" / "vl_ir_exp" / "tlul_request_loopback_vl"
DEFAULT_TEMPLATE = ROOT_DIR / "config" / "slice_launch_templates" / "tlul_request_loopback.json"
DEFAULT_JSON_OUT = ROOT_DIR / "output" / "validation" / "tlul_request_loopback_stock_hybrid_validation.json"
PROMOTION_GATE_NAME = "loopback_supported_slice_v1"
HANDOFF_GATE_NAME = "loopback_hybrid_handoff_v1"


def _template_defaults(path: Path) -> tuple[int, int]:
    if not path.is_file():
        return (32, 56)
    payload = json.loads(path.read_text(encoding="utf-8"))
    args = dict(payload.get("runner_args_template") or {})
    return (int(args.get("gpu_nstates", 32)), int(args.get("gpu_sequential_steps", 56)))


def _build_validation_payload(
    *,
    args: argparse.Namespace,
    flow_cmd: list[str],
    flow_json: dict[str, Any] | None,
    host_report: dict[str, Any] | None,
    proc: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    metrics = parse_gpu_metrics(proc.stdout)
    toggle_words = [
        int(flow_json.get("toggle_bitmap_word0_o", 0)) if flow_json else 0,
        int(flow_json.get("toggle_bitmap_word1_o", 0)) if flow_json else 0,
        int(flow_json.get("toggle_bitmap_word2_o", 0)) if flow_json else 0,
    ]
    toggle_summary = toggle_coverage_summary(toggle_words)
    status = "ok" if proc.returncode == 0 and flow_json is not None else "error"
    campaign_threshold = campaign_threshold_toggle_bits_hit(args.campaign_threshold_bits)
    done_o = int(flow_json.get("done_o", 0)) if flow_json else 0
    rsp_queue_overflow_o = int(flow_json.get("rsp_queue_overflow_o", 0)) if flow_json else 0
    host_done_o = int(host_report.get("done_o", 0)) if host_report else 0
    host_progress_cycle_count_o = int(host_report.get("progress_cycle_count_o", 0)) if host_report else 0
    flow_progress_cycle_count_o = int(flow_json.get("progress_cycle_count_o", 0)) if flow_json else 0
    host_progress_signature_o = int(host_report.get("progress_signature_o", 0)) if host_report else 0
    flow_progress_signature_o = int(flow_json.get("progress_signature_o", 0)) if flow_json else 0
    progress_advanced_since_host_probe = flow_progress_cycle_count_o > host_progress_cycle_count_o
    progress_signature_changed_since_host_probe = flow_progress_signature_o != host_progress_signature_o
    gpu_replay_made_progress = (
        progress_advanced_since_host_probe
        or progress_signature_changed_since_host_probe
        or (host_done_o == 0 and done_o == 1)
    )
    promotion_checks = {
        "done_o": done_o == 1,
        "rsp_queue_overflow_o": rsp_queue_overflow_o == 0,
        "toggle_coverage_any_hit": bool(toggle_summary["any_hit"]),
    }
    promotion_gate = {
        "name": PROMOTION_GATE_NAME,
        "target_support_tier": "first_supported_target",
        "description": (
            "Promotion beyond phase_b_reference_design requires done_o==1, "
            "rsp_queue_overflow_o==0, and at least one toggle bitmap hit under the evaluated configuration."
        ),
        "passed": all(promotion_checks.values()),
        "blocked_by": [name for name, passed in promotion_checks.items() if not passed],
        "criteria": {
            "done_o": 1,
            "rsp_queue_overflow_o": 0,
            "toggle_coverage_any_hit": True,
        },
        "observed": {
            "done_o": done_o,
            "rsp_queue_overflow_o": rsp_queue_overflow_o,
            "toggle_coverage_any_hit": bool(toggle_summary["any_hit"]),
            "toggle_bits_hit": int(toggle_summary["bits_hit"]),
            "host_probe_done_o": host_done_o,
            "host_probe_progress_cycle_count_o": host_progress_cycle_count_o,
            "gpu_flow_progress_cycle_count_o": flow_progress_cycle_count_o,
            "progress_advanced_since_host_probe": progress_advanced_since_host_probe,
            "host_probe_progress_signature_o": host_progress_signature_o,
            "gpu_flow_progress_signature_o": flow_progress_signature_o,
            "progress_signature_changed_since_host_probe": progress_signature_changed_since_host_probe,
        },
        "alternative_progress_contract_defined": False,
    }
    handoff_checks = {
        "host_probe_not_already_done": host_done_o == 0,
        "rsp_queue_overflow_o": rsp_queue_overflow_o == 0,
        "gpu_replay_made_progress": gpu_replay_made_progress,
    }
    handoff_gate = {
        "name": HANDOFF_GATE_NAME,
        "description": (
            "Hybrid handoff is only proven when the host probe leaves tlul_request_loopback incomplete, "
            "GPU replay keeps rsp_queue_overflow_o at zero, and the GPU replay changes observable progress "
            "(cycle count, progress signature, or done_o transition)."
        ),
        "passed": all(handoff_checks.values()),
        "blocked_by": [name for name, passed in handoff_checks.items() if not passed],
        "criteria": {
            "host_probe_not_already_done": True,
            "rsp_queue_overflow_o": 0,
            "gpu_replay_made_progress": True,
        },
        "observed": {
            "host_probe_done_o": host_done_o,
            "gpu_flow_done_o": done_o,
            "rsp_queue_overflow_o": rsp_queue_overflow_o,
            "host_probe_progress_cycle_count_o": host_progress_cycle_count_o,
            "gpu_flow_progress_cycle_count_o": flow_progress_cycle_count_o,
            "progress_advanced_since_host_probe": progress_advanced_since_host_probe,
            "host_probe_progress_signature_o": host_progress_signature_o,
            "gpu_flow_progress_signature_o": flow_progress_signature_o,
            "progress_signature_changed_since_host_probe": progress_signature_changed_since_host_probe,
            "gpu_replay_made_progress": gpu_replay_made_progress,
        },
    }
    if promotion_gate["passed"] and handoff_gate["passed"]:
        promotion_assessment = {
            "decision": "eligible_for_first_supported_target",
            "reason": "promotion_gate and handoff_gate both passed under the evaluated configuration",
            "next_requirement": None,
        }
    elif promotion_gate["passed"]:
        promotion_assessment = {
            "decision": "promotion_gate_only_not_handoff_proven",
            "reason": (
                "promotion_gate passed, but the evaluated run did not prove a GPU-driven handoff "
                "beyond the host-probe baseline"
            ),
            "next_requirement": "prove_gpu_driven_handoff",
        }
    elif not progress_advanced_since_host_probe:
        promotion_assessment = {
            "decision": "freeze_at_phase_b_reference_design",
            "reason": (
                "gpu replay did not advance progress_cycle_count_o beyond the host-probe baseline "
                "under the current tb_timed_coroutine ownership model"
            ),
            "next_requirement": "change_clock_or_step_ownership_or_define_alternative_progress_contract",
        }
    else:
        promotion_assessment = {
            "decision": "blocked_pending_template_or_contract",
            "reason": "promotion_gate failed, but the current run still showed progress beyond the host-probe baseline",
            "next_requirement": "retune_template_or_define_alternative_progress_contract",
        }
    campaign_measurement = {
        "bits_hit": int(toggle_summary["bits_hit"]),
        "threshold_satisfied": status == "ok" and int(toggle_summary["bits_hit"]) >= campaign_threshold["value"],
        "wall_time_ms": metrics.get("wall_time_ms"),
        "steps_executed": args.steps,
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "target": "tlul_request_loopback",
        "backend": "stock_verilator_hybrid",
        "support_tier": "phase_b_reference_design",
        "clock_ownership": "tb_timed_coroutine",
        "acceptance_gate": "phase_b_endpoint",
        "inputs": {
            "mdir": str(args.mdir.resolve()),
            "template": str(args.template.resolve()),
            "nstates": args.nstates,
            "steps": args.steps,
            "block_size": args.block_size,
            "host_reset_cycles": args.host_reset_cycles,
            "host_post_reset_cycles": args.host_post_reset_cycles,
            "host_overrides": list(args.host_set),
            "campaign_threshold_bits": args.campaign_threshold_bits,
        },
        "artifacts": {
            "runner_json": str(args.json_out.resolve()),
            "flow_json": str(args.flow_json_out.resolve()),
            "host_report": str(args.host_report_out.resolve()),
            "host_state": str(args.host_state_out.resolve()),
            "final_state": str(args.final_state_out.resolve()),
            "classifier_report": str((args.mdir.resolve() / "vl_classifier_report.json")),
        },
        "commands": {
            "flow": flow_cmd,
        },
        "flow_returncode": proc.returncode,
        "host_probe": host_report,
        "flow_summary": flow_json,
        "promotion_gate": promotion_gate,
        "handoff_gate": handoff_gate,
        "promotion_assessment": promotion_assessment,
        "outputs": {
            "done_o": done_o if flow_json else None,
            "cfg_signature_o": int(flow_json.get("cfg_signature_o", 0)) if flow_json else None,
            "toggle_bitmap_words": toggle_words,
            "progress_cycle_count_o": int(flow_json.get("progress_cycle_count_o", 0)) if flow_json else None,
            "progress_signature_o": int(flow_json.get("progress_signature_o", 0)) if flow_json else None,
            "rsp_queue_overflow_o": rsp_queue_overflow_o if flow_json else None,
        },
        "toggle_coverage": toggle_summary,
        "campaign_threshold": campaign_threshold,
        "campaign_measurement": campaign_measurement,
        "performance": metrics,
        "caveats": [
            "reference-design validation uses the generic tlul_slice host probe to initialize timed TB state",
            "this runner reuses the stable stock-hybrid schema but does not promote tlul_request_loopback to the first supported CPU slice until promotion_gate passes",
            "campaign_measurement uses the frozen reference-design surface and does not imply GPU-driven handoff proof",
        ],
    }
    if flow_json is not None and host_report is not None and not progress_advanced_since_host_probe:
        payload["caveats"].append(
            "progress_cycle_count_o did not advance beyond the host-probe baseline under the current GPU replay"
        )
    if handoff_gate["passed"] is False and host_done_o == 1:
        payload["caveats"].append(
            "host probe already reached done_o before GPU replay, so this artifact does not prove a GPU-driven handoff"
        )
    if proc.returncode != 0:
        payload["stdout_tail"] = "\n".join(proc.stdout.splitlines()[-40:])
        payload["stderr_tail"] = "\n".join(proc.stderr.splitlines()[-40:])
    return payload


def main(argv: list[str]) -> int:
    default_nstates, default_steps = _template_defaults(DEFAULT_TEMPLATE)
    parser = argparse.ArgumentParser(
        description="Run the stock-Verilator hybrid reference-design validation for tlul_request_loopback."
    )
    parser.add_argument("--mdir", type=Path, default=DEFAULT_MDIR)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--nstates", type=int, default=default_nstates)
    parser.add_argument("--steps", type=int, default=default_steps)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--host-reset-cycles", type=int, default=4)
    parser.add_argument("--host-post-reset-cycles", type=int, default=2)
    parser.add_argument("--host-set", action="append", default=[], metavar="FIELD=VALUE")
    parser.add_argument("--campaign-threshold-bits", type=int, default=2)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--flow-json-out", type=Path)
    parser.add_argument("--host-report-out", type=Path)
    parser.add_argument("--host-state-out", type=Path)
    parser.add_argument("--final-state-out", type=Path)
    args = parser.parse_args(argv)

    mdir = args.mdir.resolve()
    args.json_out = args.json_out.resolve()
    args.flow_json_out = (
        args.flow_json_out or (mdir / "tlul_request_loopback_host_gpu_flow_summary.json")
    ).resolve()
    args.host_report_out = (
        args.host_report_out or (mdir / "tlul_request_loopback_host_probe_report.json")
    ).resolve()
    args.host_state_out = (
        args.host_state_out or (mdir / "tlul_request_loopback_host_init_state.bin")
    ).resolve()
    args.final_state_out = (
        args.final_state_out or (mdir / "tlul_request_loopback_gpu_final_state.bin")
    ).resolve()

    flow_cmd = [
        sys.executable,
        str(FLOW_TOOL),
        "--mdir",
        str(mdir),
        "--template",
        str(args.template.resolve()),
        "--nstates",
        str(args.nstates),
        "--steps",
        str(args.steps),
        "--block-size",
        str(args.block_size),
        "--host-reset-cycles",
        str(args.host_reset_cycles),
        "--host-post-reset-cycles",
        str(args.host_post_reset_cycles),
        "--json-out",
        str(args.flow_json_out),
        "--host-report-out",
        str(args.host_report_out),
        "--host-state-out",
        str(args.host_state_out),
        "--final-state-out",
        str(args.final_state_out),
    ]
    for host_set in args.host_set:
        flow_cmd.extend(["--host-set", host_set])

    proc = subprocess.run(flow_cmd, text=True, capture_output=True, check=False)
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)

    flow_json = read_json_if_exists(args.flow_json_out)
    host_report = read_json_if_exists(args.host_report_out)
    payload = _build_validation_payload(
        args=args,
        flow_cmd=flow_cmd,
        flow_json=flow_json,
        host_report=host_report,
        proc=proc,
    )
    write_json(args.json_out, payload)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
