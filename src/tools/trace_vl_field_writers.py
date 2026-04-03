#!/usr/bin/env python3
"""
Locate writer sites for selected Verilator root fields in generated C++.

This is a Phase B debugging aid: given an mdir and one or more field names from
vl_hybrid_compare.json, report which generated phase functions write those
fields directly or through Verilator delayed-state temporaries.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


FUNCTION_RE = re.compile(
    r"^\s*(?:inline\s+)?(?:[\w:<>~*&]+\s+)+(?P<name>[A-Za-z_]\w*)\s*\([^;]*\)\s*\{"
)


def classify_phase(function_name: str | None) -> str | None:
    if function_name is None:
        return None
    if "___nba_comb__" in function_name:
        return "nba_comb"
    if "___nba_sequent__" in function_name:
        return "nba_sequent"
    if "___ico_sequent__" in function_name:
        return "ico"
    if "___eval" in function_name:
        return "eval"
    return None


def iter_cpp_functions(path: Path):
    current_name: str | None = None
    brace_depth = 0
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if current_name is None:
            match = FUNCTION_RE.match(raw_line)
            if match:
                current_name = match.group("name")
                brace_depth = raw_line.count("{") - raw_line.count("}")
                yield lineno, raw_line, current_name
                if brace_depth <= 0:
                    current_name = None
                    brace_depth = 0
                continue
        else:
            yield lineno, raw_line, current_name
            brace_depth += raw_line.count("{") - raw_line.count("}")
            if brace_depth <= 0:
                current_name = None
                brace_depth = 0


def assignment_lhs(line: str) -> str | None:
    if "=" not in line:
        return None
    lhs = line.split("=", 1)[0].strip()
    if not lhs:
        return None
    if lhs.startswith(("if ", "while ", "for ", "return ")):
        return None
    return lhs


def classify_assignment_kind(lhs: str, field_name: str) -> str:
    if lhs.startswith("__Vdly") and field_name in lhs:
        return "delayed"
    if field_name in lhs:
        return "direct"
    return "other"


def line_mentions_field(line: str, field_name: str) -> bool:
    return (
        field_name in line
        or f"__Vdly__{field_name}" in line
        or f"__VdlyVal__{field_name}" in line
    )


def trace_field_writers(mdir: Path, field_names: list[str]) -> dict[str, object]:
    cpp_files = sorted(mdir.glob("*.cpp"))
    field_results: dict[str, list[dict[str, object]]] = {field: [] for field in field_names}
    for cpp in cpp_files:
        pending_lhs: tuple[int, str, str | None] | None = None
        for lineno, raw_line, function_name in iter_cpp_functions(cpp):
            stripped = raw_line.strip()
            if pending_lhs is not None and stripped and not stripped.startswith("="):
                pending_lhs = None
            lhs = assignment_lhs(raw_line)
            lhs_lineno = lineno
            lhs_function = function_name
            if lhs is None and pending_lhs is not None and stripped.startswith("="):
                lhs_lineno, lhs, lhs_function = pending_lhs
                pending_lhs = None
            if lhs is None:
                if any(line_mentions_field(stripped, field_name) for field_name in field_names):
                    pending_lhs = (lineno, stripped, function_name)
                continue
            for field_name in field_names:
                if not line_mentions_field(lhs, field_name):
                    continue
                field_results[field_name].append(
                    {
                        "path": str(cpp),
                        "line": lhs_lineno,
                        "function": lhs_function,
                        "phase": classify_phase(lhs_function),
                        "kind": classify_assignment_kind(lhs, field_name),
                        "lhs": lhs,
                        "text": stripped,
                    }
                )

    summary: dict[str, object] = {"mdir": str(mdir), "fields": {}}
    for field_name in field_names:
        writers = field_results[field_name]
        function_summary: dict[str, int] = {}
        phase_summary: dict[str, int] = {}
        for entry in writers:
            function = str(entry.get("function"))
            function_summary[function] = function_summary.get(function, 0) + 1
            phase = entry.get("phase")
            if phase is not None:
                phase_key = str(phase)
                phase_summary[phase_key] = phase_summary.get(phase_key, 0) + 1
        summary["fields"][field_name] = {
            "writer_count": len(writers),
            "function_summary": function_summary,
            "phase_summary": phase_summary,
            "writers": writers,
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Trace Verilator-generated writer sites for root fields")
    parser.add_argument("mdir", type=Path, help="Verilator --cc output directory")
    parser.add_argument("fields", nargs="+", help="Root field names from vl_hybrid_compare.json")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional JSON output path")
    args = parser.parse_args()

    summary = trace_field_writers(args.mdir.resolve(), list(args.fields))
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"wrote: {args.json_out}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
