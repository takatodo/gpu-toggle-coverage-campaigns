#!/usr/bin/env python3
"""Rewrite a single flattened hw.module into a func.func wrapper.

This is a narrow bridge for the direct LLVM path after `direct-llvm-clean`.
It expects:

- one top-level `module { ... }`
- one inner `hw.module @name(...) ... { ... hw.output ... }`
- no remaining instances, LLHD ops, or seq state

The rewrite keeps the body ops intact, converts the port list into function
arguments and result types, and rewrites `hw.output` into `func.return`.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re


SSA_RE = re.compile(r"%[A-Za-z0-9_.$#-]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Input MLIR file")
    parser.add_argument("--output", type=Path, required=True, help="Output MLIR file")
    return parser.parse_args()


def find_matching(text: str, start: int, open_char: str, close_char: str) -> int:
    depth = 0
    for idx in range(start, len(text)):
        ch = text[idx]
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return idx
    raise ValueError(f"Could not find matching {close_char!r} for {open_char!r}")


def split_top_level_commas(text: str) -> list[str]:
    parts: list[str] = []
    depth_angle = 0
    depth_paren = 0
    start = 0
    for idx, ch in enumerate(text):
        if ch == "<":
            depth_angle += 1
        elif ch == ">":
            depth_angle -= 1
        elif ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren -= 1
        elif ch == "," and depth_angle == 0 and depth_paren == 0:
            parts.append(text[start:idx].strip())
            start = idx + 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def parse_port(port: str) -> tuple[str, str, str]:
    direction, rest = port.split(" ", 1)
    name, typ = rest.split(":", 1)
    return direction.strip(), name.strip(), typ.strip()


def format_func_signature(
    module_name: str, port_list: str, attr_suffix: str, body_indent: str
) -> tuple[str, list[str], list[str]]:
    inputs: list[str] = []
    output_types: list[str] = []
    for port in split_top_level_commas(port_list):
        direction, name, typ = parse_port(port)
        if direction == "in":
            inputs.append(f"{name}: {typ}")
        elif direction == "out":
            output_types.append(typ)
        else:
            raise ValueError(f"Unsupported port direction in {port!r}")
    if not output_types:
        result_sig = ""
    elif len(output_types) == 1:
        result_sig = f" -> {output_types[0]}"
    else:
        result_sig = " -> (" + ", ".join(output_types) + ")"
    suffix = attr_suffix.rstrip()
    if suffix:
        suffix = " " + suffix
    header = (
        f"{body_indent}func.func @{module_name}("
        + ", ".join(inputs)
        + f"){result_sig}{suffix} {{"
    )
    return header, inputs, output_types


def extract_defs(line: str) -> list[str]:
    if " = " not in line:
        return []
    lhs = line.split(" = ", 1)[0]
    return SSA_RE.findall(lhs)


def extract_uses(line: str) -> list[str]:
    if " = " in line:
        rhs = line.split(" = ", 1)[1]
    else:
        rhs = line
    return SSA_RE.findall(rhs)


def topologically_sort_ops(lines: list[str]) -> list[str]:
    producers: dict[str, int] = {}
    defs_per_op: list[list[str]] = []
    deps_per_op: list[set[int]] = []
    users_per_op: list[list[int]] = [[] for _ in lines]

    for idx, line in enumerate(lines):
        defs = extract_defs(line)
        defs_per_op.append(defs)
        for value in defs:
            producers[value] = idx

    for idx, line in enumerate(lines):
        deps: set[int] = set()
        for value in extract_uses(line):
            producer = producers.get(value)
            if producer is None or producer == idx:
                continue
            deps.add(producer)
        deps_per_op.append(deps)

    for idx, deps in enumerate(deps_per_op):
        for dep in deps:
            users_per_op[dep].append(idx)

    ready = [idx for idx, deps in enumerate(deps_per_op) if not deps]
    ordered: list[int] = []
    seen = [False] * len(lines)
    next_unscheduled = 0
    while ready:
        ready.sort()
        idx = ready.pop(0)
        if seen[idx]:
            continue
        seen[idx] = True
        ordered.append(idx)
        for user in users_per_op[idx]:
            deps_per_op[user].discard(idx)
            if not deps_per_op[user]:
                ready.append(user)

    while len(ordered) != len(lines):
        while next_unscheduled < len(lines) and seen[next_unscheduled]:
            next_unscheduled += 1
        if next_unscheduled >= len(lines):
            break
        idx = next_unscheduled
        seen[idx] = True
        ordered.append(idx)
        for user in users_per_op[idx]:
            deps_per_op[user].discard(idx)
            if not deps_per_op[user] and not seen[user]:
                ready.append(user)
        while ready:
            ready.sort()
            idx = ready.pop(0)
            if seen[idx]:
                continue
            seen[idx] = True
            ordered.append(idx)
            for user in users_per_op[idx]:
                deps_per_op[user].discard(idx)
                if not deps_per_op[user] and not seen[user]:
                    ready.append(user)

    if len(ordered) != len(lines):
        raise ValueError("Could not schedule all function body operations")
    return [lines[idx] for idx in ordered]


def rewrite(text: str) -> str:
    marker = "hw.module @"
    start = text.find(marker)
    if start == -1:
        raise ValueError("Expected a top-level hw.module")
    name_start = start + len("hw.module @")
    paren_start = text.find("(", name_start)
    if paren_start == -1:
        raise ValueError("Could not find hw.module port list")
    module_name = text[name_start:paren_start].strip()
    paren_end = find_matching(text, paren_start, "(", ")")
    port_list = text[paren_start + 1 : paren_end]

    scan = paren_end + 1
    while scan < len(text) and text[scan].isspace():
        scan += 1
    attr_suffix = ""
    if text.startswith("attributes", scan):
        attr_kw_start = scan
        attr_brace_start = text.find("{", attr_kw_start)
        if attr_brace_start == -1:
            raise ValueError("Could not find hw.module attribute dictionary")
        attr_brace_end = find_matching(text, attr_brace_start, "{", "}")
        attr_suffix = text[attr_kw_start : attr_brace_end + 1].strip()
        scan = attr_brace_end + 1
    body_start = text.find("{", scan)
    if body_start == -1:
        raise ValueError("Could not find hw.module body start")
    body_end = find_matching(text, body_start, "{", "}")

    line_start = text.rfind("\n", 0, start) + 1
    body_indent = text[line_start:start]
    header, _, output_types = format_func_signature(
        module_name, port_list, attr_suffix, body_indent
    )

    body_text = text[body_start + 1 : body_end]
    output_pos = body_text.rfind("hw.output ")
    if output_pos == -1:
        raise ValueError("Could not find hw.output terminator in hw.module body")
    output_line_start = body_text.rfind("\n", 0, output_pos) + 1
    output_line_end = body_text.find("\n", output_pos)
    if output_line_end == -1:
        output_line_end = len(body_text)
    output_line = body_text[output_line_start:output_line_end]
    if not output_line.strip().startswith("hw.output "):
        raise ValueError("Expected single-line hw.output terminator")
    return_line = output_line.replace("hw.output", "func.return", 1)
    op_lines = [line for line in body_text[:output_line_start].splitlines() if line.strip()]
    sorted_ops = topologically_sort_ops(op_lines)
    new_body = "\n" + "\n".join(sorted_ops) + "\n" + return_line + body_text[output_line_end:]

    rewritten = (
        text[:line_start]
        + header
        + new_body
        + text[body_end:]
    )
    return rewritten


def main() -> int:
    args = parse_args()
    rewritten = rewrite(args.input.read_text(encoding="utf-8"))
    args.output.write_text(rewritten, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
