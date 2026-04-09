#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
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
FLOW_TOOL = ROOT_DIR / "src" / "tools" / "run_tlul_slice_host_gpu_flow.py"
PARITY_TOOL = ROOT_DIR / "src" / "tools" / "run_tlul_slice_handoff_parity_probe.py"
DEFAULT_MDIR = ROOT_DIR / "work" / "vl_ir_exp" / "tlul_fifo_sync_host_vl"
DEFAULT_TEMPLATE = ROOT_DIR / "config" / "slice_launch_templates" / "tlul_fifo_sync.json"
DEFAULT_JSON_OUT = ROOT_DIR / "output" / "validation" / "tlul_fifo_sync_stock_hybrid_validation.json"
EDGE_PARITY_GATE_NAME = "thin_top_edge_parity_v1"
FLOW_ARTIFACT_STEM = "tlul_fifo_sync_host"
PARITY_ARTIFACT_STEM = "tlul_fifo_sync_handoff"
SUPPORTED_OUTPUT_NAMES = [
    "done_o",
    "progress_cycle_count_o",
    "progress_signature_o",
    "toggle_bitmap_word0_o",
    "toggle_bitmap_word1_o",
    "toggle_bitmap_word2_o",
]


def _template_defaults(path: Path) -> tuple[int, int]:
    if not path.is_file():
        return (32, 56)
    payload = json.loads(path.read_text(encoding="utf-8"))
    args = dict(payload.get("runner_args_template") or {})
    return (int(args.get("gpu_nstates", 32)), int(args.get("gpu_sequential_steps", 56)))


def _parse_clock_sequence(raw: str) -> list[int]:
    parts = [part.strip() for part in raw.split(",")]
    if not parts or any(part not in {"0", "1"} for part in parts):
        raise ValueError("--host-clock-sequence must be a comma-separated list of 0/1")
    return [int(part) for part in parts]


def _read_output_int(mapping: dict[str, Any], name: str) -> int:
    return int(mapping.get(name, 0))


def _selected_outputs(mapping: dict[str, Any]) -> dict[str, int]:
    return {name: _read_output_int(mapping, name) for name in SUPPORTED_OUTPUT_NAMES}


def _build_validation_payload(
    *,
    args: argparse.Namespace,
    flow_cmd: list[str],
    parity_cmd: list[str],
    flow_json: dict[str, Any] | None,
    host_report: dict[str, Any] | None,
    parity_json: dict[str, Any] | None,
    flow_proc: subprocess.CompletedProcess[str],
    parity_proc: subprocess.CompletedProcess[str],
    flow_wall_time_ms: float,
) -> dict[str, Any]:
    metrics = parse_gpu_metrics(flow_proc.stdout)
    flow_timing = dict((flow_json or {}).get("campaign_timing") or {})
    campaign_wall_time_ms = flow_timing.get("wall_time_ms")
    if not isinstance(campaign_wall_time_ms, (int, float)):
        campaign_wall_time_ms = metrics.get("wall_time_ms")
    if not isinstance(campaign_wall_time_ms, (int, float)):
        campaign_wall_time_ms = flow_wall_time_ms
    outputs = _selected_outputs(dict((flow_json or {}).get("outputs") or {}))
    toggle_words = [
        outputs["toggle_bitmap_word0_o"],
        outputs["toggle_bitmap_word1_o"],
        outputs["toggle_bitmap_word2_o"],
    ]
    toggle_summary = toggle_coverage_summary(toggle_words)
    status = (
        "ok"
        if flow_proc.returncode == 0
        and parity_proc.returncode == 0
        and flow_json is not None
        and host_report is not None
        and parity_json is not None
        else "error"
    )
    host_edge_runs = list((flow_json or {}).get("host_edge_runs") or [])
    last_host_edge = dict(host_edge_runs[-1]) if host_edge_runs else {}
    host_outputs = _selected_outputs(last_host_edge)
    flow_edge_parity = dict((flow_json or {}).get("edge_parity") or {})
    cpu_edge_parity = dict((parity_json or {}).get("edge_parity") or {})
    fake_syms_edge_parity = dict((parity_json or {}).get("fake_syms_edge_parity") or {})
    raw_import_edge_parity = dict((parity_json or {}).get("raw_import_edge_parity") or {})
    host_progress = _read_output_int(host_report or {}, "progress_cycle_count_o")
    host_signature = _read_output_int(host_report or {}, "progress_signature_o")
    host_toggle_words = [
        _read_output_int(host_report or {}, "toggle_bitmap_word0_o"),
        _read_output_int(host_report or {}, "toggle_bitmap_word1_o"),
        _read_output_int(host_report or {}, "toggle_bitmap_word2_o"),
    ]
    host_toggle_summary = toggle_coverage_summary(host_toggle_words)
    expected_edges = len(args.host_clock_sequence)
    host_edge_has_design_visible_progress = (
        outputs["progress_cycle_count_o"] > host_progress
        or outputs["progress_signature_o"] != host_signature
        or toggle_summary["any_hit"] != host_toggle_summary["any_hit"]
        or toggle_summary["bits_hit"] != host_toggle_summary["bits_hit"]
    )
    gate_checks = {
        "host_clock_control": bool((host_report or {}).get("host_clock_control")),
        "host_reset_control": bool((host_report or {}).get("host_reset_control")),
        "edge_count_matches_sequence": int(flow_edge_parity.get("compared_edge_count", 0)) == expected_edges,
        "gpu_edge_parity_internal_only": bool(flow_edge_parity.get("all_edges_internal_only")),
        "cpu_edge_parity_internal_only": bool(cpu_edge_parity.get("all_edges_internal_only")),
        "fake_syms_edge_parity_internal_only": bool(fake_syms_edge_parity.get("all_edges_internal_only")),
        "raw_import_edge_parity_internal_only": bool(raw_import_edge_parity.get("all_edges_internal_only")),
        "final_outputs_match_last_host_edge": outputs == host_outputs,
        "host_edge_has_design_visible_progress": host_edge_has_design_visible_progress,
    }
    parity_gate = {
        "name": EDGE_PARITY_GATE_NAME,
        "target_support_tier": "thin_top_reference_design",
        "description": (
            "A tlul_fifo_sync thin-top reference run passes when host-owned clk/reset are proven, "
            "the checked-in host edge sequence (1,0) is replayed with matching edge count, CPU and GPU "
            "parity residuals are internal-only, and the GPU final outputs match the last host edge."
        ),
        "passed": all(gate_checks.values()),
        "blocked_by": [name for name, passed in gate_checks.items() if not passed],
        "criteria": {
            "host_clock_control": True,
            "host_reset_control": True,
            "edge_count_matches_sequence": expected_edges,
            "gpu_edge_parity_internal_only": True,
            "cpu_edge_parity_internal_only": True,
            "fake_syms_edge_parity_internal_only": True,
            "raw_import_edge_parity_internal_only": True,
            "final_outputs_match_last_host_edge": True,
            "host_edge_has_design_visible_progress": True,
        },
        "observed": {
            "host_clock_control": bool((host_report or {}).get("host_clock_control")),
            "host_reset_control": bool((host_report or {}).get("host_reset_control")),
            "flow_edge_parity_compared_edge_count": int(flow_edge_parity.get("compared_edge_count", 0)),
            "cpu_edge_parity_compared_edge_count": int(cpu_edge_parity.get("compared_edge_count", 0)),
            "flow_edge_role_summary": dict(flow_edge_parity.get("role_summary") or {}),
            "cpu_edge_role_summary": dict(cpu_edge_parity.get("role_summary") or {}),
            "fake_syms_edge_role_summary": dict(fake_syms_edge_parity.get("role_summary") or {}),
            "raw_import_edge_role_summary": dict(raw_import_edge_parity.get("role_summary") or {}),
            "final_outputs": outputs,
            "last_host_edge_outputs": host_outputs,
            "host_probe_progress_cycle_count_o": host_progress,
            "gpu_flow_progress_cycle_count_o": outputs["progress_cycle_count_o"],
            "host_probe_progress_signature_o": host_signature,
            "gpu_flow_progress_signature_o": outputs["progress_signature_o"],
            "host_probe_toggle_bits_hit": int(host_toggle_summary["bits_hit"]),
            "gpu_flow_toggle_bits_hit": int(toggle_summary["bits_hit"]),
        },
    }
    campaign_threshold = campaign_threshold_toggle_bits_hit(args.campaign_threshold_bits)
    gpu_runs = list((flow_json or {}).get("gpu_runs") or [])
    steps_executed = sum(int(run.get("steps", 0)) for run in gpu_runs)
    if steps_executed == 0:
        if args.host_clock_sequence:
            steps_executed = len(args.host_clock_sequence) * args.host_clock_sequence_steps
        else:
            steps_executed = args.steps
    campaign_measurement = {
        "bits_hit": int(toggle_summary["bits_hit"]),
        "threshold_satisfied": (
            status == "ok"
            and bool(parity_gate["passed"])
            and int(toggle_summary["bits_hit"]) >= campaign_threshold["value"]
        ),
        "wall_time_ms": float(campaign_wall_time_ms) if isinstance(campaign_wall_time_ms, (int, float)) else None,
        "steps_executed": steps_executed,
    }
    if isinstance(metrics, dict):
        metrics = dict(metrics)
        metrics["flow_wall_time_ms"] = flow_wall_time_ms
        metrics["campaign_wall_time_ms"] = campaign_measurement["wall_time_ms"]
        if flow_timing:
            metrics["campaign_timing"] = flow_timing
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "target": "tlul_fifo_sync",
        "backend": "stock_verilator_hybrid",
        "support_tier": "thin_top_reference_design",
        "clock_ownership": str((flow_json or {}).get("clock_ownership") or (host_report or {}).get("clock_ownership") or "host_direct_ports"),
        "acceptance_gate": EDGE_PARITY_GATE_NAME,
        "inputs": {
            "mdir": str(args.mdir.resolve()),
            "template": str(args.template.resolve()),
            "nstates": args.nstates,
            "steps": args.steps,
            "block_size": args.block_size,
            "host_reset_cycles": args.host_reset_cycles,
            "host_post_reset_cycles": args.host_post_reset_cycles,
            "host_clock_sequence": list(args.host_clock_sequence),
            "host_clock_sequence_steps": args.host_clock_sequence_steps,
            "campaign_threshold_bits": args.campaign_threshold_bits,
        },
        "artifacts": {
            "runner_json": str(args.json_out.resolve()),
            "flow_json": str(args.flow_json_out.resolve()),
            "parity_json": str(args.parity_json_out.resolve()),
            "host_report": str(args.host_report_out.resolve()),
            "host_state": str(args.host_state_out.resolve()),
            "final_state": str(args.final_state_out.resolve()),
            "classifier_report": str((args.mdir.resolve() / "vl_classifier_report.json")),
        },
        "commands": {
            "flow": flow_cmd,
            "parity": parity_cmd,
        },
        "flow_returncode": flow_proc.returncode,
        "parity_returncode": parity_proc.returncode,
        "host_probe": host_report,
        "flow_summary": flow_json,
        "parity_summary": parity_json,
        "edge_parity_gate": parity_gate,
        "outputs": outputs,
        "toggle_coverage": toggle_summary,
        "campaign_threshold": campaign_threshold,
        "campaign_measurement": campaign_measurement,
        "performance": metrics,
        "caveats": [
            "this runner pins tlul_fifo_sync at a thin-top reference tier, not a supported target",
            "the checked-in gate is same-edge parity on the host-driven 1,0 clk_i replay sequence",
            "campaign_measurement.wall_time_ms sums the per-run run_vl_hybrid host wall times from the checked-in GPU replay and excludes host-probe/parity diagnostics",
        ],
    }
    if flow_proc.returncode != 0:
        payload["flow_stdout_tail"] = "\n".join(flow_proc.stdout.splitlines()[-40:])
        payload["flow_stderr_tail"] = "\n".join(flow_proc.stderr.splitlines()[-40:])
    if parity_proc.returncode != 0:
        payload["parity_stdout_tail"] = "\n".join(parity_proc.stdout.splitlines()[-40:])
        payload["parity_stderr_tail"] = "\n".join(parity_proc.stderr.splitlines()[-40:])
    return payload


def main(argv: list[str]) -> int:
    default_nstates, default_steps = _template_defaults(DEFAULT_TEMPLATE)
    parser = argparse.ArgumentParser(
        description="Run the thin-top stock-Verilator reference validation for tlul_fifo_sync."
    )
    parser.add_argument("--mdir", type=Path, default=DEFAULT_MDIR)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--nstates", type=int, default=default_nstates)
    parser.add_argument("--steps", type=int, default=default_steps)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--host-reset-cycles", type=int, default=4)
    parser.add_argument("--host-post-reset-cycles", type=int, default=2)
    parser.add_argument("--host-clock-sequence", default="1,0")
    parser.add_argument("--host-clock-sequence-steps", type=int, default=1)
    parser.add_argument("--campaign-threshold-bits", type=int, default=3)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--flow-json-out", type=Path)
    parser.add_argument("--parity-json-out", type=Path)
    parser.add_argument("--host-report-out", type=Path)
    parser.add_argument("--host-state-out", type=Path)
    parser.add_argument("--final-state-out", type=Path)
    args = parser.parse_args(argv)

    mdir = args.mdir.resolve()
    args.template = args.template.resolve()
    args.json_out = args.json_out.resolve()
    args.host_clock_sequence = _parse_clock_sequence(args.host_clock_sequence)
    clock_sequence_arg = ",".join(str(value) for value in args.host_clock_sequence)
    args.flow_json_out = (
        args.flow_json_out or (mdir / f"{FLOW_ARTIFACT_STEM}_gpu_flow_watch_summary.json")
    ).resolve()
    args.parity_json_out = (
        args.parity_json_out or (mdir / f"{PARITY_ARTIFACT_STEM}_parity_summary.json")
    ).resolve()
    args.host_report_out = (
        args.host_report_out or (mdir / f"{FLOW_ARTIFACT_STEM}_probe_report.json")
    ).resolve()
    args.host_state_out = (
        args.host_state_out or (mdir / f"{FLOW_ARTIFACT_STEM}_init_state.bin")
    ).resolve()
    args.final_state_out = (
        args.final_state_out or (mdir / f"{FLOW_ARTIFACT_STEM}_gpu_final_state.bin")
    ).resolve()

    flow_cmd = [
        sys.executable,
        str(FLOW_TOOL),
        "--mdir",
        str(mdir),
        "--template",
        str(args.template),
        "--target",
        "tlul_fifo_sync",
        "--support-tier",
        "thin_top_reference_design",
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
        "--host-clock-sequence",
        clock_sequence_arg,
        "--host-clock-sequence-steps",
        str(args.host_clock_sequence_steps),
        "--json-out",
        str(args.flow_json_out),
        "--host-report-out",
        str(args.host_report_out),
        "--host-state-out",
        str(args.host_state_out),
        "--final-state-out",
        str(args.final_state_out),
    ]
    parity_cmd = [
        sys.executable,
        str(PARITY_TOOL),
        "--mdir",
        str(mdir),
        "--template",
        str(args.template),
        "--clock-sequence",
        clock_sequence_arg,
        "--reset-cycles",
        str(args.host_reset_cycles),
        "--post-reset-cycles",
        str(args.host_post_reset_cycles),
        "--json-out",
        str(args.parity_json_out),
    ]

    flow_start = time.perf_counter()
    flow_proc = subprocess.run(flow_cmd, text=True, capture_output=True, check=False)
    flow_wall_time_ms = (time.perf_counter() - flow_start) * 1000.0
    if flow_proc.stdout:
        sys.stdout.write(flow_proc.stdout)
    if flow_proc.stderr:
        sys.stderr.write(flow_proc.stderr)

    parity_proc = subprocess.run(parity_cmd, text=True, capture_output=True, check=False)
    if parity_proc.stdout:
        sys.stdout.write(parity_proc.stdout)
    if parity_proc.stderr:
        sys.stderr.write(parity_proc.stderr)

    flow_json = read_json_if_exists(args.flow_json_out)
    host_report = read_json_if_exists(args.host_report_out)
    parity_json = read_json_if_exists(args.parity_json_out)
    payload = _build_validation_payload(
        args=args,
        flow_cmd=flow_cmd,
        parity_cmd=parity_cmd,
        flow_json=flow_json,
        host_report=host_report,
        parity_json=parity_json,
        flow_proc=flow_proc,
        parity_proc=parity_proc,
        flow_wall_time_ms=flow_wall_time_ms,
    )
    write_json(args.json_out, payload)
    if flow_proc.returncode != 0:
        return flow_proc.returncode
    return parity_proc.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
