#!/usr/bin/env python3
"""
Build and run a generic TL-UL thin-top handoff parity probe.

This compares host eval_step() against direct root___eval() on the same host-owned
clock sequence and annotates per-edge raw state deltas.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import compare_vl_hybrid_modes as cmp
import run_tlul_slice_host_probe as host_probe


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
PARITY_SOURCE = REPO_ROOT / "src" / "hybrid" / "tlul_slice_handoff_parity_probe.cpp"
DEFAULT_BINARY = "tlul_slice_handoff_parity_probe"
DEFAULT_TEMPLATE_DIR = REPO_ROOT / "config" / "slice_launch_templates"
DEFAULT_MDIR = REPO_ROOT / "work" / "vl_ir_exp" / "tlul_fifo_sync_host_vl"


def _all_changed_offsets(before: bytes, after: bytes) -> list[int]:
    return [idx for idx, (lhs, rhs) in enumerate(zip(before, after)) if lhs != rhs]


def _read_field_bytes(blob: bytes, report: dict[str, Any], name: str) -> bytes:
    offsets = dict(report.get("field_offsets") or {})
    sizes = dict(report.get("field_sizes") or {})
    offset = int(offsets[name])
    size = int(sizes[name])
    return blob[offset : offset + size]


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
    payload: dict[str, Any] = {
        "changed_byte_count": len(offsets),
        "first_changed_offsets": offsets[:16],
    }
    payload.update(_known_field_delta_summary(before, after, report))
    payload.update(_annotate_changed_offsets(layout, offsets))
    return payload


def _build_edge_parity_payload(
    edge_runs: list[dict[str, Any]],
    *,
    root_size: int,
    layout: list[dict[str, int | str]],
    report: dict[str, Any],
    lhs_key: str,
    rhs_key: str,
    rhs_dump_label: str,
) -> dict[str, Any]:
    parity_edges = []
    aggregate_role_summary: dict[str, int] = {}
    all_edges_internal_only = bool(edge_runs)
    all_edges_match_exact = True
    for edge in edge_runs:
        lhs_dump = Path(str(edge[lhs_key]["dump_state"]))
        rhs_dump = Path(str(edge[rhs_key]["dump_state"]))
        lhs_blob = lhs_dump.read_bytes()[:root_size]
        rhs_blob = rhs_dump.read_bytes()[:root_size]
        parity = _edge_parity_summary(lhs_blob, rhs_blob, report, layout=layout)
        for role, count in dict(parity.get("role_summary") or {}).items():
            aggregate_role_summary[role] = aggregate_role_summary.get(role, 0) + int(count)
        if not parity.get("all_offsets_internal_only", False):
            all_edges_internal_only = False
        if int(parity.get("changed_byte_count", 0)) != 0:
            all_edges_match_exact = False
        parity_edges.append(
            {
                "index": edge["index"],
                "clock_level": edge["clock_level"],
                "host_dump_state": str(lhs_dump),
                rhs_dump_label: str(rhs_dump),
                "parity": parity,
            }
        )
    return {
        "compared_edge_count": len(parity_edges),
        "all_edges_internal_only": all_edges_internal_only,
        "all_edges_match_exact": all_edges_match_exact,
        "role_summary": aggregate_role_summary,
        "edges": parity_edges,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mdir", type=Path, default=DEFAULT_MDIR)
    p.add_argument("--binary-out", type=Path)
    p.add_argument("--json-out", type=Path)
    p.add_argument("--template", type=Path)
    p.add_argument("--clock-sequence", required=True)
    p.add_argument("--host-edge-state-dir", type=Path)
    p.add_argument("--root-eval-edge-state-dir", type=Path)
    p.add_argument("--watch-field", action="append", default=[], metavar="FIELD_NAME")
    p.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    p.add_argument("--cfg-valid", type=int, choices=(0, 1), default=1)
    p.add_argument("--reset-cycles", type=int, default=4)
    p.add_argument("--post-reset-cycles", type=int, default=2)
    p.add_argument("--build-only", action="store_true")
    args = p.parse_args()

    mdir = args.mdir.resolve()
    prefix = host_probe.find_prefix(mdir)
    target = host_probe._derive_target(prefix)
    template_path = (
        args.template.resolve()
        if args.template is not None
        else (DEFAULT_TEMPLATE_DIR / f"{target}.json").resolve()
    )
    watch_fields = host_probe._load_template_watch_fields(template_path if template_path.is_file() else None)
    watch_fields = host_probe._rewrite_top_module_watch_fields(prefix, target, watch_fields)
    for raw_name in args.watch_field:
        name = str(raw_name)
        if name not in watch_fields:
            watch_fields.append(name)

    binary_out = (args.binary_out or (mdir / DEFAULT_BINARY)).resolve()
    binary_path, _, target, control_meta = host_probe.build_probe_binary(
        mdir,
        binary_out,
        watch_fields=watch_fields,
        probe_source=PARITY_SOURCE,
        extra_defines=[f"-DROOT_EVAL_FN={prefix}___024root___eval"],
    )
    if args.build_only:
        print(binary_path)
        return

    settings = host_probe._load_template_settings(template_path if template_path.is_file() else None)
    settings["cfg_valid_i"] = int(args.cfg_valid)
    settings = host_probe._apply_overrides(settings, list(args.set))

    host_edge_state_dir = (
        args.host_edge_state_dir or (mdir / "host_handoff_parity_trace" / "host_eval")
    ).resolve()
    root_eval_edge_state_dir = (
        args.root_eval_edge_state_dir or (mdir / "host_handoff_parity_trace" / "root_eval")
    ).resolve()
    host_edge_state_dir.mkdir(parents=True, exist_ok=True)
    root_eval_edge_state_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(binary_path),
        "--reset-cycles",
        str(args.reset_cycles),
        "--post-reset-cycles",
        str(args.post_reset_cycles),
        "--clock-sequence",
        args.clock_sequence,
        "--host-edge-state-dir",
        str(host_edge_state_dir),
        "--root-eval-edge-state-dir",
        str(root_eval_edge_state_dir),
    ]
    for name in sorted(settings):
        cmd.extend(["--set", f"{name}={settings[name]}"])

    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    payload = json.loads(result.stdout)
    payload["configured_inputs"] = settings
    payload["host_clock_control"] = bool(control_meta["host_clock_control"])
    payload["host_reset_control"] = bool(control_meta["host_reset_control"])
    payload["clock_field_name"] = str(control_meta["clock_field_name"])
    payload["reset_field_name"] = payload.get("reset_field_name") or str(
        control_meta["reset_report_name"]
    )
    payload["clock_ownership"] = (
        "host_direct_ports" if payload["host_clock_control"] else "tb_timed_coroutine"
    )
    payload["template_path"] = str(template_path) if template_path.is_file() else None
    payload["probe_binary"] = str(binary_path)
    payload["mdir"] = str(mdir)
    payload["watch_field_names"] = watch_fields
    payload["host_edge_state_dir"] = str(host_edge_state_dir)
    payload["root_eval_edge_state_dir"] = str(root_eval_edge_state_dir)

    layout = cmp.probe_root_layout(mdir)
    root_size = int(payload["root_size"])
    edge_runs = list(payload.get("edge_runs") or [])
    payload["edge_parity"] = _build_edge_parity_payload(
        edge_runs,
        root_size=root_size,
        layout=layout,
        report=payload,
        lhs_key="host_eval",
        rhs_key="root_eval",
        rhs_dump_label="root_eval_dump_state",
    )
    payload["fake_syms_edge_parity"] = _build_edge_parity_payload(
        edge_runs,
        root_size=root_size,
        layout=layout,
        report=payload,
        lhs_key="host_eval",
        rhs_key="fake_syms_eval",
        rhs_dump_label="fake_syms_eval_dump_state",
    )
    payload["raw_import_edge_parity"] = _build_edge_parity_payload(
        edge_runs,
        root_size=root_size,
        layout=layout,
        report=payload,
        lhs_key="host_eval",
        rhs_key="raw_import_eval",
        rhs_dump_label="raw_import_eval_dump_state",
    )

    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        host_probe._write_json(args.json_out.resolve(), payload)
    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
