#!/usr/bin/env python3
"""
Run a generic TL-UL slice host-probe -> GPU flow and summarize watched-field deltas.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import compare_vl_hybrid_modes as cmp


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
RUNNER_DIR = REPO_ROOT / "src" / "runners"
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))

from stock_hybrid_validation_common import parse_gpu_metrics

HOST_PROBE = SCRIPT_DIR / "run_tlul_slice_host_probe.py"
RUN_GPU = SCRIPT_DIR / "run_vl_hybrid.py"

DEFAULT_MDIR = REPO_ROOT / "work" / "vl_ir_exp" / "tlul_socket_1n_vl"
DEFAULT_TEMPLATE = REPO_ROOT / "config" / "slice_launch_templates" / "tlul_socket_1n.json"

STANDARD_OUTPUT_FIELDS = [
    "done_o",
    "cfg_signature_o",
    "host_req_accepted_o",
    "device_req_accepted_o",
    "device_rsp_accepted_o",
    "host_rsp_accepted_o",
    "rsp_queue_overflow_o",
    "progress_cycle_count_o",
    "progress_signature_o",
    "toggle_bitmap_word0_o",
    "toggle_bitmap_word1_o",
    "toggle_bitmap_word2_o",
]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_field_bytes(blob: bytes, report: dict[str, Any], name: str) -> bytes:
    offsets = dict(report.get("field_offsets") or {})
    sizes = dict(report.get("field_sizes") or {})
    offset = int(offsets[name])
    size = int(sizes[name])
    return blob[offset : offset + size]


def _read_u_le(blob: bytes, report: dict[str, Any], name: str) -> int:
    return int.from_bytes(_read_field_bytes(blob, report, name), "little", signed=False)


def _format_bytes_hex(blob: bytes) -> str:
    return "0x" + blob.hex()


def _raw_delta_summary(before: bytes, after: bytes, limit: int = 16) -> dict[str, Any]:
    changed_offsets = _all_changed_offsets(before, after)
    return {
        "changed_byte_count": len(changed_offsets),
        "first_changed_offsets": changed_offsets[:limit],
    }


def _all_changed_offsets(before: bytes, after: bytes) -> list[int]:
    return [idx for idx, (lhs, rhs) in enumerate(zip(before, after)) if lhs != rhs]


def _known_field_delta_summary(
    before: bytes,
    after: bytes,
    report: dict[str, Any],
    *,
    limit: int = 16,
) -> dict[str, Any]:
    changed_fields = []
    offsets = dict(report.get("field_offsets") or {})
    for name in sorted(offsets):
        if _read_field_bytes(before, report, name) != _read_field_bytes(after, report, name):
            changed_fields.append(name)
    return {
        "changed_known_field_count": len(changed_fields),
        "first_changed_known_fields": changed_fields[:limit],
    }


def _state_delta_summary(before: bytes, after: bytes, report: dict[str, Any]) -> dict[str, Any]:
    payload = _raw_delta_summary(before, after)
    payload.update(_known_field_delta_summary(before, after, report))
    return payload


def _annotate_changed_offsets(
    layout: list[dict[str, int | str]], offsets: list[int], *, limit: int = 16
) -> dict[str, Any]:
    role_summary: dict[str, int] = {}
    annotations = []
    all_annotated = True
    all_internal_only = bool(offsets)
    for offset in offsets:
        annotated = cmp.annotate_state_offset(layout, offset)
        if annotated is None:
            all_annotated = False
            all_internal_only = False
            if len(annotations) < limit:
                annotations.append({"offset": offset, "annotation": None})
            continue
        role = cmp.classify_field_role(str(annotated["field_name"]))
        role_summary[role] = role_summary.get(role, 0) + 1
        if role != "verilator_internal":
            all_internal_only = False
        if len(annotations) < limit:
            annotations.append(
                {
                    "offset": offset,
                    "annotation": {
                        **annotated,
                        "field_role": role,
                    },
                }
            )
    return {
        "role_summary": role_summary,
        "all_offsets_annotated": all_annotated,
        "all_offsets_internal_only": all_internal_only,
        "first_changed_annotations": annotations,
    }


def _edge_parity_summary(
    before: bytes,
    after: bytes,
    report: dict[str, Any],
    *,
    layout: list[dict[str, int | str]],
) -> dict[str, Any]:
    offsets = _all_changed_offsets(before, after)
    payload = _state_delta_summary(before, after, report)
    payload.update(_annotate_changed_offsets(layout, offsets))
    return payload


def _template_defaults(path: Path) -> tuple[int, int]:
    if not path.is_file():
        return (32, 56)
    payload = json.loads(path.read_text(encoding="utf-8"))
    args = dict(payload.get("runner_args_template") or {})
    return (int(args.get("gpu_nstates", 32)), int(args.get("gpu_sequential_steps", 56)))


def _parse_clock_sequence(raw: str | None) -> list[int]:
    if raw is None:
        return []
    parts = [part.strip() for part in raw.split(",")]
    if not parts or any(part not in {"0", "1"} for part in parts):
        raise ValueError("--host-clock-sequence must be a comma-separated list of 0/1")
    return [int(part) for part in parts]


def _patch_arg(offset: int, value: int) -> str:
    return f"{offset}:0x{value:02x}"


def _run_gpu_once(
    *,
    mdir: Path,
    nstates: int,
    steps: int,
    block_size: int,
    init_state: Path,
    dump_state: Path,
    patches: list[str],
    sanitize_host_only_internals: bool,
) -> dict[str, Any]:
    gpu_cmd = [
        sys.executable,
        str(RUN_GPU),
        "--mdir",
        str(mdir),
        "--nstates",
        str(nstates),
        "--steps",
        str(steps),
        "--block-size",
        str(block_size),
        "--init-state",
        str(init_state),
        "--dump-state",
        str(dump_state),
    ]
    if sanitize_host_only_internals:
        gpu_cmd.append("--sanitize-host-only-internals")
    for patch in patches:
        gpu_cmd.extend(["--patch", patch])
    proc = subprocess.run(gpu_cmd, check=True, text=True, capture_output=True)
    if proc.stdout:
        sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return {
        "command": gpu_cmd,
        "metrics": parse_gpu_metrics(proc.stdout),
    }


def _campaign_timing_from_runs(gpu_runs: list[dict[str, Any]]) -> dict[str, Any]:
    per_run_wall_time_ms: list[float | None] = []
    per_run_kernel_time_ms: list[float | None] = []
    wall_time_ms_total = 0.0
    kernel_time_ms_total = 0.0
    wall_time_complete = True
    kernel_time_complete = True
    for run in gpu_runs:
        metrics = dict(run.get("performance") or {})
        wall_time_ms = metrics.get("wall_time_ms")
        if isinstance(wall_time_ms, (int, float)):
            wall_time_ms_total += float(wall_time_ms)
            per_run_wall_time_ms.append(float(wall_time_ms))
        else:
            wall_time_complete = False
            per_run_wall_time_ms.append(None)
        kernel_metrics = metrics.get("gpu_kernel_time_ms")
        kernel_total = kernel_metrics.get("total") if isinstance(kernel_metrics, dict) else None
        if isinstance(kernel_total, (int, float)):
            kernel_time_ms_total += float(kernel_total)
            per_run_kernel_time_ms.append(float(kernel_total))
        else:
            kernel_time_complete = False
            per_run_kernel_time_ms.append(None)
    return {
        "run_count": len(gpu_runs),
        "timing_complete": wall_time_complete,
        "wall_time_ms": wall_time_ms_total if wall_time_complete else None,
        "per_run_wall_time_ms": per_run_wall_time_ms,
        "gpu_kernel_time_complete": kernel_time_complete,
        "gpu_kernel_time_ms_total": kernel_time_ms_total if kernel_time_complete else None,
        "per_run_gpu_kernel_time_ms": per_run_kernel_time_ms,
    }


def main() -> None:
    default_nstates, default_steps = _template_defaults(DEFAULT_TEMPLATE)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mdir", type=Path, default=DEFAULT_MDIR)
    p.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    p.add_argument("--target")
    p.add_argument("--support-tier", default="candidate_second_supported_target")
    p.add_argument("--nstates", type=int, default=default_nstates)
    p.add_argument("--steps", type=int, default=default_steps)
    p.add_argument("--block-size", type=int, default=256)
    p.add_argument(
        "--sanitize-host-only-internals",
        action="store_true",
        help="Pass --sanitize-host-only-internals through to run_vl_hybrid.py.",
    )
    p.add_argument("--host-reset-cycles", type=int, default=4)
    p.add_argument("--host-post-reset-cycles", type=int, default=2)
    p.add_argument(
        "--host-clock-sequence",
        help="Comma-separated 0/1 levels for host-owned clk_i replay, for example 1,0",
    )
    p.add_argument(
        "--host-clock-sequence-steps",
        type=int,
        default=1,
        help="GPU steps per host clock level when --host-clock-sequence is used (default: 1)",
    )
    p.add_argument("--host-set", action="append", default=[], metavar="FIELD=VALUE")
    p.add_argument("--host-watch-field", action="append", default=[], metavar="FIELD_NAME")
    p.add_argument("--host-probe-extra-define", action="append", default=[], metavar="DEFINE")
    p.add_argument("--program-entries-bin", type=Path)
    p.add_argument("--memory-image", type=Path)
    p.add_argument("--memory-image-target", type=Path)
    p.add_argument("--json-out", type=Path)
    p.add_argument("--host-report-out", type=Path)
    p.add_argument("--host-state-out", type=Path)
    p.add_argument("--final-state-out", type=Path)
    args = p.parse_args()
    if args.memory_image is not None and args.memory_image_target is None:
        p.error("--memory-image requires --memory-image-target")
    if args.memory_image_target is not None and args.memory_image is None:
        p.error("--memory-image-target requires --memory-image")

    mdir = args.mdir.resolve()
    host_report = (
        args.host_report_out or (mdir / f"{mdir.name.removesuffix('_vl')}_host_probe_report.json")
    ).resolve()
    host_state = (
        args.host_state_out or (mdir / f"{mdir.name.removesuffix('_vl')}_host_init_state.bin")
    ).resolve()
    final_state = (
        args.final_state_out or (mdir / f"{mdir.name.removesuffix('_vl')}_gpu_final_state.bin")
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
    for watch_name in args.host_watch_field:
        probe_cmd.extend(["--watch-field", watch_name])
    for raw_define in args.host_probe_extra_define:
        probe_cmd.append(f"--extra-define={raw_define}")
    if args.program_entries_bin is not None:
        probe_cmd.extend(["--program-entries-bin", str(args.program_entries_bin.resolve())])
    if args.memory_image_target is not None:
        probe_cmd.extend(["--memory-image-target", str(args.memory_image_target.resolve())])
    if args.memory_image is not None:
        probe_cmd.extend(["--memory-image", str(args.memory_image.resolve())])
    subprocess.run(probe_cmd, check=True)

    host_payload = _read_json(host_report)
    host_clock_sequence = _parse_clock_sequence(args.host_clock_sequence)
    host_edge_payload: dict[str, Any] | None = None
    host_edge_report: Path | None = None
    host_edge_state_dir: Path | None = None
    if host_payload.get("host_clock_control") and host_clock_sequence:
        host_edge_report = (
            mdir / f"{mdir.name.removesuffix('_vl')}_host_edge_trace.json"
        ).resolve()
        host_edge_state_dir = (mdir / "host_edge_trace").resolve()
        host_edge_cmd = [
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
            str(host_edge_report),
            "--clock-sequence",
            args.host_clock_sequence,
            "--edge-state-dir",
            str(host_edge_state_dir),
        ]
        for host_set in args.host_set:
            host_edge_cmd.extend(["--set", host_set])
        for watch_name in args.host_watch_field:
            host_edge_cmd.extend(["--watch-field", watch_name])
        for raw_define in args.host_probe_extra_define:
            host_edge_cmd.append(f"--extra-define={raw_define}")
        if args.program_entries_bin is not None:
            host_edge_cmd.extend(["--program-entries-bin", str(args.program_entries_bin.resolve())])
        if args.memory_image_target is not None:
            host_edge_cmd.extend(["--memory-image-target", str(args.memory_image_target.resolve())])
        if args.memory_image is not None:
            host_edge_cmd.extend(["--memory-image", str(args.memory_image.resolve())])
        subprocess.run(host_edge_cmd, check=True)
        host_edge_payload = _read_json(host_edge_report)

    gpu_runs: list[dict[str, Any]] = []
    gpu_run_state_blobs: list[bytes] = []
    if host_payload.get("host_clock_control") and host_clock_sequence:
        field_offsets = dict(host_payload.get("field_offsets") or {})
        reset_field_name = str(host_payload.get("reset_field_name") or "rst_ni")
        clk_offset = int(field_offsets["clk_i"])
        reset_offset = int(field_offsets[reset_field_name])
        reset_deasserted_value = int(host_payload.get("reset_deasserted_value", 1))
        current_state = host_state
        previous_state0 = host_state.read_bytes()[: int(host_payload["root_size"])]
        with tempfile.TemporaryDirectory(prefix="host_clock_gpu_flow_") as tmpdir:
            tmp_root = Path(tmpdir)
            for index, clock_level in enumerate(host_clock_sequence):
                dump_path = (
                    final_state
                    if index + 1 == len(host_clock_sequence)
                    else tmp_root / f"edge_{index + 1}.bin"
                )
                patches = [
                    _patch_arg(clk_offset, clock_level),
                    _patch_arg(reset_offset, reset_deasserted_value),
                ]
                gpu_result = _run_gpu_once(
                    mdir=mdir,
                    nstates=args.nstates,
                    steps=args.host_clock_sequence_steps,
                    block_size=args.block_size,
                    init_state=current_state,
                    dump_state=dump_path,
                    patches=patches,
                    sanitize_host_only_internals=args.sanitize_host_only_internals,
                )
                current_blob = dump_path.read_bytes()[: int(host_payload["root_size"])]
                gpu_runs.append(
                    {
                        "index": index + 1,
                        "clock_level": clock_level,
                        "steps": args.host_clock_sequence_steps,
                        "patches": patches,
                        "init_state": str(current_state),
                        "dump_state": str(dump_path),
                        "performance": gpu_result["metrics"],
                        "delta_from_previous": _state_delta_summary(
                            previous_state0, current_blob, host_payload
                        ),
                        "delta_from_host_probe": _state_delta_summary(
                            host_state.read_bytes()[: int(host_payload["root_size"])],
                            current_blob,
                            host_payload,
                        ),
                    }
                )
                gpu_run_state_blobs.append(current_blob)
                previous_state0 = current_blob
                current_state = dump_path
    else:
        gpu_result = _run_gpu_once(
            mdir=mdir,
            nstates=args.nstates,
            steps=args.steps,
            block_size=args.block_size,
            init_state=host_state,
            dump_state=final_state,
            patches=[],
            sanitize_host_only_internals=args.sanitize_host_only_internals,
        )
        gpu_runs.append(
            {
                "index": 1,
                "clock_level": None,
                "steps": args.steps,
                "patches": [],
                "init_state": str(host_state),
                "dump_state": str(final_state),
                "performance": gpu_result["metrics"],
            }
        )
        gpu_run_state_blobs.append(final_state.read_bytes()[: int(host_payload["root_size"])])

    storage_size = int(host_payload["root_size"])
    host_blob = host_state.read_bytes()
    final_blob = final_state.read_bytes()
    if len(host_blob) < storage_size:
        raise RuntimeError(f"{host_state} shorter than one state: {len(host_blob)} < {storage_size}")
    if len(final_blob) < storage_size:
        raise RuntimeError(f"{final_state} shorter than one state: {len(final_blob)} < {storage_size}")
    host_state0 = host_blob[:storage_size]
    final_state0 = final_blob[:storage_size]

    outputs = {
        name: _read_u_le(final_state0, host_payload, name)
        for name in STANDARD_OUTPUT_FIELDS
        if name in dict(host_payload.get("field_offsets") or {})
    }
    watch_field_names = list(host_payload.get("watch_field_names") or [])
    watched_fields = {}
    changed_watch_field_count = 0
    for name in watch_field_names:
        host_bytes = _read_field_bytes(host_state0, host_payload, name)
        final_bytes = _read_field_bytes(final_state0, host_payload, name)
        changed = host_bytes != final_bytes
        if changed:
            changed_watch_field_count += 1
        watched_fields[name] = {
            "size": len(final_bytes),
            "host_probe_hex": _format_bytes_hex(host_bytes),
            "gpu_final_hex": _format_bytes_hex(final_bytes),
            "changed": changed,
        }
    state_delta = _state_delta_summary(host_state0, final_state0, host_payload)
    if gpu_runs and "delta_from_host_probe" not in gpu_runs[-1]:
        gpu_runs[-1]["delta_from_host_probe"] = dict(state_delta)
        gpu_runs[-1]["delta_from_previous"] = dict(state_delta)

    edge_parity: dict[str, Any] | None = None
    if host_edge_payload is not None:
        layout = cmp.probe_root_layout(mdir)
        host_edge_runs = list(host_edge_payload.get("edge_runs") or [])
        compared_edge_count = min(len(host_edge_runs), len(gpu_runs))
        parity_edges = []
        aggregate_role_summary: dict[str, int] = {}
        all_edges_internal_only = compared_edge_count > 0
        for index in range(compared_edge_count):
            host_run = dict(host_edge_runs[index])
            gpu_run = dict(gpu_runs[index])
            host_dump = Path(str(host_run["dump_state"]))
            host_edge_blob = host_dump.read_bytes()[:storage_size]
            gpu_edge_blob = gpu_run_state_blobs[index]
            parity = _edge_parity_summary(host_edge_blob, gpu_edge_blob, host_payload, layout=layout)
            for role, count in dict(parity.get("role_summary") or {}).items():
                aggregate_role_summary[role] = aggregate_role_summary.get(role, 0) + int(count)
            if not parity.get("all_offsets_internal_only", False):
                all_edges_internal_only = False
            parity_edges.append(
                {
                    "index": index + 1,
                    "clock_level": host_run.get("clock_level"),
                    "host_dump_state": str(host_dump),
                    "gpu_dump_state": str(gpu_run["dump_state"]),
                    "parity": parity,
                }
            )
        edge_parity = {
            "compared_edge_count": compared_edge_count,
            "host_edge_count": len(host_edge_runs),
            "gpu_edge_count": len(gpu_runs),
            "all_edges_internal_only": all_edges_internal_only,
            "role_summary": aggregate_role_summary,
            "edges": parity_edges,
        }
    else:
        host_edge_runs = []

    summary = {
        "target": args.target or host_payload.get("target") or mdir.name.removesuffix("_vl"),
        "clock_ownership": host_payload.get("clock_ownership")
        or ("host_direct_ports" if host_payload.get("host_clock_control") else "tb_timed_coroutine"),
        "support_tier": args.support_tier,
        "mdir": str(mdir),
        "template": str(args.template.resolve()),
        "nstates": args.nstates,
        "steps": args.steps,
        "block_size": args.block_size,
        "sanitize_host_only_internals": bool(args.sanitize_host_only_internals),
        "host_reset_cycles": args.host_reset_cycles,
        "host_post_reset_cycles": args.host_post_reset_cycles,
        "host_clock_sequence": host_clock_sequence,
        "host_clock_sequence_steps": args.host_clock_sequence_steps,
        "host_overrides": list(args.host_set),
        "host_watch_fields": list(args.host_watch_field),
        "host_probe_extra_defines": list(args.host_probe_extra_define),
        "program_entries_bin": str(args.program_entries_bin.resolve()) if args.program_entries_bin else None,
        "memory_image": str(args.memory_image.resolve()) if args.memory_image else None,
        "memory_image_target": (
            str(args.memory_image_target.resolve()) if args.memory_image_target else None
        ),
        "gpu_runs": gpu_runs,
        "campaign_timing": _campaign_timing_from_runs(gpu_runs),
        "host_report": str(host_report),
        "host_edge_trace_report": str(host_edge_report) if host_edge_report else None,
        "host_edge_state_dir": str(host_edge_state_dir) if host_edge_state_dir else None,
        "host_state": str(host_state),
        "final_state": str(final_state),
        "storage_size": storage_size,
        "outputs": outputs,
        "watched_fields": watched_fields,
        "changed_watch_field_count": changed_watch_field_count,
        "state_delta": state_delta,
        "host_edge_runs": host_edge_runs,
        "edge_parity": edge_parity,
        "configured_inputs": dict(host_payload.get("configured_inputs") or {}),
    }
    payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        json_out = args.json_out.resolve()
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(payload, encoding="utf-8")
    sys.stdout.write(payload)


if __name__ == "__main__":
    main()
