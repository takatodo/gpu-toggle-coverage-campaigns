#!/usr/bin/env python3
"""Cut a selected feedback edge in a single top-level hw.module for probing.

This is a narrow debugging tool for direct-LLVM experiments on flattened
single-module artifacts. It rewrites one or more specific uses of an SSA value
to a fresh hw.module input, which breaks a chosen graph-region cycle without
changing the rest of the module body.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re


VALUE_TOKEN_RE = re.compile(r"%[A-Za-z0-9_.$#-]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Input MLIR file")
    parser.add_argument("--output", type=Path, required=True, help="Output MLIR file")
    parser.add_argument(
        "--source-value",
        required=True,
        help="SSA value whose selected uses should be cut, for example %%15152",
    )
    parser.add_argument(
        "--replace-in-op",
        action="append",
        required=True,
        help="Replace only in ops defining this SSA value, for example %%14962",
    )
    parser.add_argument(
        "--new-input-name",
        default=None,
        help="Optional fresh input name; defaults to <source>_cut",
    )
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


def infer_value_type(lines: list[str], source_value: str) -> str:
    prefix = f"{source_value} = "
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith(prefix):
            continue
        type_part = stripped.rsplit(":", 1)[-1].strip()
        if "->" in type_part:
            type_part = type_part.rsplit("->", 1)[-1].strip()
        return type_part
    raise ValueError(f"Could not infer type for {source_value}")


def replace_selected_use(line: str, source_value: str, new_input_name: str) -> str:
    lhs, rhs = line.split(" = ", 1)
    rewritten_rhs = VALUE_TOKEN_RE.sub(
        lambda match: new_input_name if match.group(0) == source_value else match.group(0),
        rhs,
    )
    return lhs + " = " + rewritten_rhs


def rewrite(
    text: str,
    *,
    source_value: str,
    replace_in_ops: set[str],
    new_input_name: str,
) -> str:
    marker = "hw.module @"
    start = text.find(marker)
    if start == -1:
        raise ValueError("Expected a top-level hw.module")
    paren_start = text.find("(", start)
    if paren_start == -1:
        raise ValueError("Could not find hw.module port list")
    paren_end = find_matching(text, paren_start, "(", ")")
    port_list = text[paren_start + 1 : paren_end]
    port_items = split_top_level_commas(port_list)

    scan = paren_end + 1
    while scan < len(text) and text[scan].isspace():
        scan += 1
    if text.startswith("attributes", scan):
        attr_brace_start = text.find("{", scan)
        if attr_brace_start == -1:
            raise ValueError("Could not find hw.module attribute dictionary")
        attr_brace_end = find_matching(text, attr_brace_start, "{", "}")
        scan = attr_brace_end + 1
    while scan < len(text) and text[scan].isspace():
        scan += 1

    body_start = text.find("{", scan)
    if body_start == -1:
        raise ValueError("Could not find hw.module body start")
    body_end = find_matching(text, body_start, "{", "}")
    body_text = text[body_start + 1 : body_end]
    body_lines = body_text.splitlines()

    source_type = infer_value_type(body_lines, source_value)
    port_items.append(f"in {new_input_name} : {source_type}")

    updated_body_lines: list[str] = []
    replaced = False
    for line in body_lines:
        stripped = line.strip()
        lhs = stripped.split(" = ", 1)[0] if " = " in stripped else ""
        if lhs in replace_in_ops and source_value in stripped:
            line = replace_selected_use(line, source_value, new_input_name)
            replaced = True
        updated_body_lines.append(line)
    if not replaced:
        raise ValueError(
            f"Did not find any selected uses of {source_value} in {sorted(replace_in_ops)}"
        )

    new_text = (
        text[: paren_start + 1]
        + ", ".join(port_items)
        + text[paren_end: body_start + 1]
        + "\n".join(updated_body_lines)
        + text[body_end:]
    )
    return new_text


def main() -> int:
    args = parse_args()
    source_value = args.source_value.strip()
    if not source_value.startswith("%"):
        source_value = "%" + source_value
    replace_in_ops = set()
    for item in args.replace_in_op:
        item = item.strip()
        if not item.startswith("%"):
            item = "%" + item
        replace_in_ops.add(item)
    new_input_name = args.new_input_name.strip() if args.new_input_name else source_value + "_cut"
    if not new_input_name.startswith("%"):
        new_input_name = "%" + new_input_name

    rewritten = rewrite(
        args.input.read_text(encoding="utf-8"),
        source_value=source_value,
        replace_in_ops=replace_in_ops,
        new_input_name=new_input_name,
    )
    args.output.write_text(rewritten, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
