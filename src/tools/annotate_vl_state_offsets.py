#!/usr/bin/env python3
"""
Annotate raw state offsets against a Verilator root layout.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import compare_vl_hybrid_modes as cmp


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _offsets_from_summary(
    summary_path: Path,
    *,
    gpu_run_index: int | None,
    delta_key: str,
) -> list[int]:
    payload = _read_json(summary_path)
    if gpu_run_index is None:
        source = dict(payload.get("state_delta") or {})
    else:
        runs = list(payload.get("gpu_runs") or [])
        if gpu_run_index < 1 or gpu_run_index > len(runs):
            raise IndexError(
                f"--gpu-run-index {gpu_run_index} out of range for {summary_path} (runs={len(runs)})"
            )
        source = dict(runs[gpu_run_index - 1].get(delta_key) or {})
    return [int(value) for value in list(source.get("first_changed_offsets") or [])]


def _annotate_offsets(mdir: Path, offsets: list[int]) -> dict[str, Any]:
    layout = cmp.probe_root_layout(mdir)
    annotations = []
    role_summary: dict[str, int] = {}
    all_internal = True
    all_annotated = True
    for offset in offsets:
        annotated = cmp.annotate_state_offset(layout, offset)
        if annotated is None:
            all_annotated = False
            all_internal = False
            annotations.append({"offset": offset, "annotation": None})
            continue
        role = cmp.classify_field_role(str(annotated["field_name"]))
        role_summary[role] = role_summary.get(role, 0) + 1
        if role != "verilator_internal":
            all_internal = False
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
        "offsets": offsets,
        "annotations": annotations,
        "role_summary": role_summary,
        "all_offsets_annotated": all_annotated,
        "all_offsets_internal_only": bool(offsets) and all_internal,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mdir", type=Path)
    p.add_argument("offsets", nargs="*", type=int)
    p.add_argument("--summary", type=Path)
    p.add_argument("--gpu-run-index", type=int)
    p.add_argument(
        "--delta-key",
        choices=["delta_from_host_probe", "delta_from_previous"],
        default="delta_from_host_probe",
    )
    p.add_argument("--json-out", type=Path)
    args = p.parse_args()

    offsets = list(args.offsets)
    summary_source: dict[str, Any] | None = None
    if args.summary is not None:
        if offsets:
            raise SystemExit("pass either positional offsets or --summary, not both")
        offsets = _offsets_from_summary(
            args.summary.resolve(),
            gpu_run_index=args.gpu_run_index,
            delta_key=args.delta_key,
        )
        summary_source = {
            "summary": str(args.summary.resolve()),
            "gpu_run_index": args.gpu_run_index,
            "delta_key": args.delta_key if args.gpu_run_index is not None else "state_delta",
        }
    if not offsets:
        raise SystemExit("no offsets provided")

    mdir = args.mdir.resolve()
    annotated = _annotate_offsets(mdir, offsets)
    payload = {
        "schema_version": 1,
        "mdir": str(mdir),
        "summary_source": summary_source,
        **annotated,
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        out = args.json_out.resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
