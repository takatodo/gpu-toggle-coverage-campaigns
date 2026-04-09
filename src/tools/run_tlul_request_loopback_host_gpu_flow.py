#!/usr/bin/env python3
"""
Run tlul_request_loopback host-probe -> GPU flow using the generic TL-UL slice host probe.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_MDIR = REPO_ROOT / "work" / "vl_ir_exp" / "tlul_request_loopback_vl"
DEFAULT_TEMPLATE = REPO_ROOT / "config" / "slice_launch_templates" / "tlul_request_loopback.json"
HOST_PROBE = SCRIPT_DIR / "run_tlul_slice_host_probe.py"
RUN_GPU = SCRIPT_DIR / "run_vl_hybrid.py"
SUPPORTED_TARGET = "tlul_request_loopback"
CLOCK_OWNERSHIP = "tb_timed_coroutine"


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_u_le(blob: bytes, offset: int, size: int) -> int:
    return int.from_bytes(blob[offset : offset + size], "little", signed=False)


def _read_field(blob: bytes, report: dict[str, object], name: str) -> int:
    offsets = dict(report.get("field_offsets") or {})
    sizes = dict(report.get("field_sizes") or {})
    return _read_u_le(blob, int(offsets[name]), int(sizes[name]))


def _template_defaults(path: Path) -> tuple[int, int]:
    if not path.is_file():
        return (32, 56)
    payload = json.loads(path.read_text(encoding="utf-8"))
    args = dict(payload.get("runner_args_template") or {})
    return (int(args.get("gpu_nstates", 32)), int(args.get("gpu_sequential_steps", 56)))


def main() -> None:
    default_nstates, default_steps = _template_defaults(DEFAULT_TEMPLATE)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mdir", type=Path, default=DEFAULT_MDIR)
    p.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    p.add_argument("--nstates", type=int, default=default_nstates)
    p.add_argument("--steps", type=int, default=default_steps)
    p.add_argument("--block-size", type=int, default=256)
    p.add_argument("--host-reset-cycles", type=int, default=4)
    p.add_argument("--host-post-reset-cycles", type=int, default=2)
    p.add_argument("--host-set", action="append", default=[], metavar="FIELD=VALUE")
    p.add_argument("--json-out", type=Path)
    p.add_argument("--host-report-out", type=Path)
    p.add_argument("--host-state-out", type=Path)
    p.add_argument("--final-state-out", type=Path)
    args = p.parse_args()

    mdir = args.mdir.resolve()
    host_report = (
        args.host_report_out or (mdir / "tlul_request_loopback_host_probe_report.json")
    ).resolve()
    host_state = (
        args.host_state_out or (mdir / "tlul_request_loopback_host_init_state.bin")
    ).resolve()
    final_state = (
        args.final_state_out or (mdir / "tlul_request_loopback_gpu_final_state.bin")
    ).resolve()

    probe_cmd = [
        sys.executable,
        str(HOST_PROBE),
        "--mdir",
        str(mdir),
        "--template",
        str(args.template.resolve()),
        "--reset-cycles",
        str(args.host_reset_cycles),
        "--post-reset-cycles",
        str(args.host_post_reset_cycles),
        "--json-out",
        str(host_report),
        "--state-out",
        str(host_state),
    ]
    for host_set in args.host_set:
        probe_cmd.extend(["--set", host_set])
    subprocess.run(probe_cmd, check=True)

    gpu_cmd = [
        sys.executable,
        str(RUN_GPU),
        "--mdir",
        str(mdir),
        "--nstates",
        str(args.nstates),
        "--steps",
        str(args.steps),
        "--block-size",
        str(args.block_size),
        "--init-state",
        str(host_state),
        "--dump-state",
        str(final_state),
    ]
    subprocess.run(gpu_cmd, check=True)

    host_payload = _read_json(host_report)
    storage_size = int(host_payload["root_size"])
    blob = final_state.read_bytes()
    if len(blob) < storage_size:
        raise RuntimeError(f"{final_state} shorter than one state: {len(blob)} < {storage_size}")
    state0 = blob[:storage_size]

    summary = {
        "target": SUPPORTED_TARGET,
        "clock_ownership": CLOCK_OWNERSHIP,
        "support_tier": "phase_b_reference_design",
        "mdir": str(mdir),
        "template": str(args.template.resolve()),
        "nstates": args.nstates,
        "steps": args.steps,
        "block_size": args.block_size,
        "host_reset_cycles": args.host_reset_cycles,
        "host_post_reset_cycles": args.host_post_reset_cycles,
        "host_overrides": list(args.host_set),
        "host_report": str(host_report),
        "host_state": str(host_state),
        "final_state": str(final_state),
        "storage_size": storage_size,
        "done_o": _read_field(state0, host_payload, "done_o"),
        "cfg_signature_o": _read_field(state0, host_payload, "cfg_signature_o"),
        "host_req_accepted_o": _read_field(state0, host_payload, "host_req_accepted_o"),
        "device_req_accepted_o": _read_field(state0, host_payload, "device_req_accepted_o"),
        "device_rsp_accepted_o": _read_field(state0, host_payload, "device_rsp_accepted_o"),
        "host_rsp_accepted_o": _read_field(state0, host_payload, "host_rsp_accepted_o"),
        "rsp_queue_overflow_o": _read_field(state0, host_payload, "rsp_queue_overflow_o"),
        "progress_cycle_count_o": _read_field(state0, host_payload, "progress_cycle_count_o"),
        "progress_signature_o": _read_field(state0, host_payload, "progress_signature_o"),
        "toggle_bitmap_word0_o": _read_field(state0, host_payload, "toggle_bitmap_word0_o"),
        "toggle_bitmap_word1_o": _read_field(state0, host_payload, "toggle_bitmap_word1_o"),
        "toggle_bitmap_word2_o": _read_field(state0, host_payload, "toggle_bitmap_word2_o"),
        "configured_inputs": dict(host_payload.get("configured_inputs") or {}),
    }
    payload = json.dumps(summary, indent=2) + "\n"
    if args.json_out:
        json_out = args.json_out.resolve()
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)


if __name__ == "__main__":
    main()
