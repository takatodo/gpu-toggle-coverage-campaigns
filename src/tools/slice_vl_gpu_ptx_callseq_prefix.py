#!/usr/bin/env python3
"""
Emit a PTX variant whose target entry kernel keeps only a prefix of its callseq
blocks. This is useful for runtime bisection when a large split kernel faults
but the failing internal callee range is unknown.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ENTRY_RE_TEMPLATE = r"^\.visible \.entry {kernel}\($"
CALLSEQ_START_RE = re.compile(r"^\s*\{ // callseq (\d+),")
CALLSEQ_END_RE = re.compile(r"^\s*\} // callseq (\d+)")


def _find_kernel_entry(lines: list[str], kernel_name: str) -> int:
    entry_re = re.compile(ENTRY_RE_TEMPLATE.format(kernel=re.escape(kernel_name)))
    for idx, line in enumerate(lines):
        if entry_re.match(line):
            return idx
    raise ValueError(f"kernel entry not found: {kernel_name}")


def _find_function_bounds(lines: list[str], entry_idx: int) -> tuple[int, int]:
    open_idx = None
    depth = 0
    for idx in range(entry_idx, len(lines)):
        stripped = lines[idx].strip()
        if open_idx is None:
            if stripped == "{":
                open_idx = idx
                depth = 1
            continue
        depth += lines[idx].count("{")
        depth -= lines[idx].count("}")
        if depth == 0:
            return open_idx, idx
    raise ValueError("unterminated PTX entry function")


def slice_kernel_callseq_prefix(
    ptx_text: str,
    *,
    kernel_name: str,
    max_callseq: int,
) -> tuple[str, dict[str, object]]:
    lines = ptx_text.splitlines()
    entry_idx = _find_kernel_entry(lines, kernel_name)
    open_idx, close_idx = _find_function_bounds(lines, entry_idx)

    seen_callseqs: list[int] = []
    keep_through_idx = None
    call_depth = 0

    for idx in range(open_idx + 1, close_idx):
        line = lines[idx]
        start_match = CALLSEQ_START_RE.match(line)
        end_match = CALLSEQ_END_RE.match(line)
        if start_match:
            call_depth += 1
            callseq = int(start_match.group(1))
            seen_callseqs.append(callseq)
        if end_match:
            callseq = int(end_match.group(1))
            if call_depth <= 0:
                raise ValueError(f"malformed callseq nesting near line {idx + 1}")
            if callseq <= max_callseq:
                keep_through_idx = idx
            call_depth -= 1

    if call_depth != 0:
        raise ValueError("unterminated callseq block in PTX entry")
    if not seen_callseqs:
        raise ValueError(f"no callseq blocks found in kernel: {kernel_name}")
    if keep_through_idx is None and max_callseq >= min(seen_callseqs):
        raise ValueError(f"requested max_callseq {max_callseq} was not found in kernel")

    first_callseq_start_idx = None
    for idx in range(open_idx + 1, close_idx):
        if CALLSEQ_START_RE.match(lines[idx]):
            first_callseq_start_idx = idx
            break
    assert first_callseq_start_idx is not None

    kept_callseqs = [value for value in seen_callseqs if value <= max_callseq]
    dropped_callseqs = [value for value in seen_callseqs if value > max_callseq]

    if kept_callseqs:
        out_lines = lines[: keep_through_idx + 1]
    else:
        out_lines = lines[:first_callseq_start_idx]
    out_lines.extend(
        [
            "\t// truncated by slice_vl_gpu_ptx_callseq_prefix.py",
            "\tret;",
            "}",
        ]
    )
    out_lines.extend(lines[close_idx + 1 :])

    summary: dict[str, object] = {
        "schema_version": 1,
        "scope": "slice_vl_gpu_ptx_callseq_prefix",
        "kernel_name": kernel_name,
        "requested_max_callseq": max_callseq,
        "function_line_start": entry_idx + 1,
        "function_line_end": close_idx + 1,
        "kept_callseq_count": len(kept_callseqs),
        "kept_callseq_min": min(kept_callseqs) if kept_callseqs else None,
        "kept_callseq_max": max(kept_callseqs) if kept_callseqs else None,
        "dropped_callseq_count": len(dropped_callseqs),
        "dropped_callseq_min": min(dropped_callseqs) if dropped_callseqs else None,
        "dropped_callseq_max": max(dropped_callseqs) if dropped_callseqs else None,
    }
    return "\n".join(out_lines) + "\n", summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Truncate a PTX entry kernel after a callseq prefix.")
    parser.add_argument("--ptx", type=Path, required=True, help="Input PTX file")
    parser.add_argument("--kernel", required=True, help="Target .entry kernel name")
    parser.add_argument(
        "--max-callseq",
        type=int,
        required=True,
        help="Largest callseq number to keep in the target kernel",
    )
    parser.add_argument("--out", type=Path, required=True, help="Output PTX path")
    parser.add_argument("--json-out", type=Path, help="Optional summary JSON path")
    args = parser.parse_args()

    sliced_text, summary = slice_kernel_callseq_prefix(
        args.ptx.read_text(encoding="utf-8"),
        kernel_name=args.kernel,
        max_callseq=args.max_callseq,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(sliced_text, encoding="utf-8")
    summary["input_ptx"] = str(args.ptx.resolve())
    summary["output_ptx"] = str(args.out.resolve())
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
