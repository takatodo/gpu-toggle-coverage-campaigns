#!/usr/bin/env python3
"""Lower a narrow zero-delay LLHD net subset into plain HW/Comb SSA.

This is a targeted bridge for CIRCT direct-import flows after the existing
`full -> arc-strip-sv -> llhd-* cleanup` pipeline. It only accepts:

- `llhd.constant_time <0ns, 0d, 1e>`
- `llhd.sig`
- `llhd.prb`
- `llhd.drv ... after %zero_delay [if %guard]`
- `llhd.sig.array_get` with constant integer indices
- `seq.compreg` with a constant non-zero reset value

The pass models signals as ordered SSA updates within each `hw.module`. It is
not a general LLHD lowering.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


SSA_RE = r"%[A-Za-z0-9_.$#-]+"
MODULE_HEADER_RE = re.compile(r"^\s*hw\.module\b")
ZERO_DELAY_RE = re.compile(
    rf"^(?P<indent>\s*)(?P<result>{SSA_RE}) = llhd\.constant_time <0ns, 0d, 1e>\s*$"
)
SIG_RE = re.compile(
    rf"^(?P<indent>\s*)(?P<result>{SSA_RE}) = llhd\.sig (?P<init>{SSA_RE}) : (?P<type>.+?)\s*$"
)
SIG_ARRAY_GET_RE = re.compile(
    rf"^(?P<indent>\s*)(?P<result>{SSA_RE}) = llhd\.sig\.array_get (?P<base>{SSA_RE})\[(?P<index>{SSA_RE})\] : <(?P<type>.+?)>\s*$"
)
PRB_RE = re.compile(
    rf"^(?P<indent>\s*)(?P<result>{SSA_RE}) = llhd\.prb (?P<ref>{SSA_RE}) : (?P<type>.+?)\s*$"
)
DRV_RE = re.compile(
    rf"^(?P<indent>\s*)llhd\.drv (?P<target>{SSA_RE}), (?P<value>{SSA_RE}) after (?P<delay>{SSA_RE})(?: if (?P<guard>{SSA_RE}))? : (?P<type>.+?)\s*$"
)
ARRAY_INJECT_RE = re.compile(
    rf"^(?P<indent>\s*)(?P<result>{SSA_RE}) = hw\.array_inject (?P<base>{SSA_RE})\[(?P<index>{SSA_RE})\], (?P<value>{SSA_RE}) : "
    rf"(?P<array_type>.+?), (?P<index_type>.+?)\s*$"
)
COMPREG_RESET_RE = re.compile(
    rf"^(?P<indent>\s*)(?P<result>{SSA_RE}) = seq\.compreg (?P<input>{SSA_RE}), (?P<clk>{SSA_RE}) "
    rf"reset (?P<reset>{SSA_RE}), (?P<reset_value>{SSA_RE}|true|false) : (?P<type>.+?)\s*$"
)
TOKEN_RE = re.compile(SSA_RE)
IDX_WIDTH_RE = re.compile(r"_i(?P<width>\d+)$")
RESULT_PREFIX_RE = re.compile(
    rf"^(?P<prefix>\s*(?:{SSA_RE}(?:\s*,\s*{SSA_RE})*)\s*=\s*)(?P<rest>.*)$"
)


@dataclass(frozen=True)
class ArrayType:
    length: int
    elem: "TypeNode"


TypeNode = str | ArrayType


@dataclass
class SignalRoot:
    type_node: TypeNode
    current_value: str


@dataclass(frozen=True)
class RefPath:
    root: str
    indices: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Input MLIR file")
    parser.add_argument("--output", type=Path, required=True, help="Output MLIR file")
    parser.add_argument(
        "--allow-remaining-llhd",
        action="store_true",
        help="Do not fail if unsupported LLHD ops remain after rewriting",
    )
    return parser.parse_args()


def _split_top_level_once(text: str, delim: str) -> tuple[str, str]:
    depth = 0
    for idx, char in enumerate(text):
        if char == "<":
            depth += 1
        elif char == ">":
            depth -= 1
        elif char == delim and depth == 0:
            return text[:idx], text[idx + 1 :]
    raise ValueError(f"Could not split type expression {text!r} at top-level {delim!r}")


def parse_type(text: str) -> TypeNode:
    stripped = text.strip()
    if stripped.startswith("!hw.array<"):
        inner = stripped[len("!hw.array<") : -1]
    elif stripped.startswith("array<"):
        inner = stripped[len("array<") : -1]
    else:
        return stripped
    length_text, elem_text = _split_top_level_once(inner, "x")
    return ArrayType(length=int(length_text), elem=parse_type(elem_text))


def render_type(node: TypeNode, *, nested: bool = False) -> str:
    if isinstance(node, str):
        return node
    prefix = "" if nested else "!hw."
    return f"{prefix}array<{node.length}x{render_type(node.elem, nested=True)}>"


def descend_type(node: TypeNode, depth: int) -> TypeNode:
    current = node
    for _ in range(depth):
        if not isinstance(current, ArrayType):
            raise ValueError("Attempted to index into a non-array LLHD signal")
        current = current.elem
    return current


def infer_index_type(index_name: str) -> str:
    match = IDX_WIDTH_RE.search(index_name)
    if match is None:
        raise ValueError(f"Could not infer index type from {index_name}")
    return f"i{match.group('width')}"


def is_zero_reset_value(token: str) -> bool:
    return token == "%false" or token.startswith("%c0_")


def substitute_tokens(text: str, replacements: dict[str, str]) -> str:
    if not replacements:
        return text
    result = text
    for old, new in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        result = re.sub(
            rf"(?<![A-Za-z0-9_.$#-]){re.escape(old)}(?![A-Za-z0-9_.$#-])",
            new,
            result,
        )
    return result


def substitute_line_tokens(line: str, replacements: dict[str, str]) -> str:
    match = RESULT_PREFIX_RE.match(line)
    if match is None:
        return substitute_tokens(line, replacements)
    return match.group("prefix") + substitute_tokens(match.group("rest"), replacements)


class Rewriter:
    def __init__(self, *, reserved_names: set[str] | None = None) -> None:
        self.counter = 0
        self.zero_delay_tokens: set[str] = set()
        self.roots: dict[str, SignalRoot] = {}
        self.root_order: list[str] = []
        self.refs: dict[str, RefPath] = {}
        self.replacements: dict[str, str] = {}
        self.reserved_names: set[str] = set(reserved_names or ())

    def fresh(self) -> str:
        while True:
            name = f"%llhd_zdn_{self.counter}"
            self.counter += 1
            if name in self.reserved_names:
                continue
            self.reserved_names.add(name)
            return name

    def shadow_defined_names(self, names: list[str]) -> None:
        for name in names:
            self.replacements.pop(name, None)
            self.refs.pop(name, None)
            self.roots.pop(name, None)
            self.zero_delay_tokens.discard(name)
            self.reserved_names.add(name)

    def fallback_self_inject_base(self, array_type: str, result_name: str) -> str | None:
        for root_name in reversed(self.root_order):
            root = self.roots.get(root_name)
            if root is None:
                continue
            if render_type(root.type_node) != array_type:
                continue
            if root.current_value == result_name:
                continue
            return root.current_value
        return None

    def resolve_ref(self, ref_name: str) -> RefPath:
        if ref_name in self.roots:
            return RefPath(root=ref_name, indices=())
        if ref_name in self.refs:
            return self.refs[ref_name]
        raise ValueError(f"Unknown LLHD ref {ref_name}")

    def emit_extract(
        self, root_value: str, root_type: TypeNode, indices: tuple[str, ...], indent: str
    ) -> tuple[list[str], str, TypeNode]:
        lines: list[str] = []
        value = root_value
        value_type = root_type
        for index in indices:
            if not isinstance(value_type, ArrayType):
                raise ValueError("Encountered non-array while lowering llhd.sig.array_get")
            next_value = self.fresh()
            lines.append(
                f"{indent}{next_value} = hw.array_get {value}[{index}] : "
                f"{render_type(value_type)}, {infer_index_type(index)}"
            )
            value = next_value
            value_type = value_type.elem
        return lines, value, value_type

    def emit_inject(
        self,
        current_root: str,
        root_type: TypeNode,
        indices: tuple[str, ...],
        new_leaf_value: str,
        indent: str,
    ) -> tuple[list[str], str]:
        if not indices:
            return [], new_leaf_value
        if not isinstance(root_type, ArrayType):
            raise ValueError("Encountered llhd.drv indexing into a non-array root")
        head, tail = indices[0], indices[1:]
        lines: list[str] = []
        element_ref = self.fresh()
        lines.append(
            f"{indent}{element_ref} = hw.array_get {current_root}[{head}] : "
            f"{render_type(root_type)}, {infer_index_type(head)}"
        )
        nested_lines, updated_element = self.emit_inject(
            element_ref,
            root_type.elem,
            tail,
            new_leaf_value,
            indent,
        )
        lines.extend(nested_lines)
        injected = self.fresh()
        lines.append(
            f"{indent}{injected} = hw.array_inject {current_root}[{head}], {updated_element} : "
            f"{render_type(root_type)}, {infer_index_type(head)}"
        )
        return lines, injected

    def lower_prb(self, ref_name: str, indent: str) -> tuple[list[str], str]:
        ref = self.resolve_ref(ref_name)
        root = self.roots[ref.root]
        return self.emit_extract(root.current_value, root.type_node, ref.indices, indent)[:2]

    def lower_drv(
        self,
        target_name: str,
        value_name: str,
        guard_name: str | None,
        indent: str,
    ) -> list[str]:
        target = self.resolve_ref(target_name)
        root = self.roots[target.root]
        if target.indices:
            lines, updated_root = self.emit_inject(
                root.current_value,
                root.type_node,
                target.indices,
                value_name,
                indent,
            )
        else:
            lines = []
            updated_root = value_name
        if guard_name is not None:
            muxed = self.fresh()
            lines.append(
                f"{indent}{muxed} = comb.mux {guard_name}, {updated_root}, {root.current_value} : "
                f"{render_type(root.type_node)}"
            )
            updated_root = muxed
        root.current_value = updated_root
        return lines


def rewrite_text(text: str, *, allow_remaining_llhd: bool) -> str:
    lines = text.splitlines()
    out_lines: list[str] = []
    reserved_names = set(TOKEN_RE.findall(text))
    rewriter = Rewriter(reserved_names=reserved_names)
    module_depth = 0

    for original_line in lines:
        defined_match = RESULT_PREFIX_RE.match(original_line)
        defined_names: list[str] = []
        if defined_match is not None:
            defined_names = TOKEN_RE.findall(defined_match.group("prefix"))
            rewriter.shadow_defined_names(defined_names)

        line = substitute_line_tokens(original_line, rewriter.replacements)

        if MODULE_HEADER_RE.match(line):
            rewriter = Rewriter(reserved_names=reserved_names)
            module_depth = 0
            module_depth += line.count("{") - line.count("}")
            out_lines.append(line)
            continue

        if module_depth > 0:
            constant_match = ZERO_DELAY_RE.match(line)
            if constant_match is not None:
                rewriter.zero_delay_tokens.add(constant_match.group("result"))
                module_depth += line.count("{") - line.count("}")
                continue

            sig_match = SIG_RE.match(line)
            if sig_match is not None:
                root_name = sig_match.group("result")
                rewriter.roots[root_name] = SignalRoot(
                    type_node=parse_type(sig_match.group("type")),
                    current_value=sig_match.group("init"),
                )
                rewriter.root_order.append(root_name)
                module_depth += line.count("{") - line.count("}")
                continue

            array_get_match = SIG_ARRAY_GET_RE.match(line)
            if array_get_match is not None:
                base_ref = rewriter.resolve_ref(array_get_match.group("base"))
                rewriter.refs[array_get_match.group("result")] = RefPath(
                    root=base_ref.root,
                    indices=base_ref.indices + (array_get_match.group("index"),),
                )
                module_depth += line.count("{") - line.count("}")
                continue

            prb_match = PRB_RE.match(line)
            if prb_match is not None:
                emitted, replacement = rewriter.lower_prb(prb_match.group("ref"), prb_match.group("indent"))
                out_lines.extend(emitted)
                rewriter.replacements[prb_match.group("result")] = replacement
                module_depth += line.count("{") - line.count("}")
                continue

            drv_match = DRV_RE.match(line)
            if drv_match is not None:
                delay_name = drv_match.group("delay")
                if delay_name not in rewriter.zero_delay_tokens:
                    if not allow_remaining_llhd:
                        raise ValueError(f"Unsupported non-zero-delay llhd.drv line: {line}")
                    out_lines.append(line)
                    module_depth += line.count("{") - line.count("}")
                    continue
                emitted = rewriter.lower_drv(
                    drv_match.group("target"),
                    drv_match.group("value"),
                    drv_match.group("guard"),
                    drv_match.group("indent"),
                )
                out_lines.extend(emitted)
                module_depth += line.count("{") - line.count("}")
                continue

            array_inject_match = ARRAY_INJECT_RE.match(line)
            if (
                array_inject_match is not None
                and array_inject_match.group("result") == array_inject_match.group("base")
            ):
                fallback_base = rewriter.fallback_self_inject_base(
                    array_inject_match.group("array_type"),
                    array_inject_match.group("result"),
                )
                if fallback_base is None:
                    if not allow_remaining_llhd:
                        raise ValueError(f"Unsupported self-referential hw.array_inject: {line}")
                    out_lines.append(line)
                    module_depth += line.count("{") - line.count("}")
                    continue
                out_lines.append(
                    f"{array_inject_match.group('indent')}{array_inject_match.group('result')} = "
                    f"hw.array_inject {fallback_base}[{array_inject_match.group('index')}], "
                    f"{array_inject_match.group('value')} : {array_inject_match.group('array_type')}, "
                    f"{array_inject_match.group('index_type')}"
                )
                module_depth += line.count("{") - line.count("}")
                continue

            compreg_match = COMPREG_RESET_RE.match(line)
            if compreg_match is not None and not is_zero_reset_value(
                compreg_match.group("reset_value")
            ):
                mux_value = rewriter.fresh()
                out_lines.append(
                    f"{compreg_match.group('indent')}{mux_value} = comb.mux "
                    f"{compreg_match.group('reset')}, {compreg_match.group('reset_value')}, "
                    f"{compreg_match.group('input')} : {compreg_match.group('type')}"
                )
                out_lines.append(
                    f"{compreg_match.group('indent')}{compreg_match.group('result')} = seq.compreg "
                    f"{mux_value}, {compreg_match.group('clk')} : {compreg_match.group('type')}"
                )
                module_depth += line.count("{") - line.count("}")
                continue

        out_lines.append(line)
        module_depth += line.count("{") - line.count("}")

    rewritten = "\n".join(out_lines) + "\n"
    if not allow_remaining_llhd:
        disallowed = re.findall(r"\bllhd\.(?:constant_time|sig|drv|prb)\b", rewritten)
        if disallowed:
            raise ValueError(
                "Unsupported LLHD net ops remain after zero-delay lowering: "
                + ", ".join(sorted(set(disallowed)))
            )
    return rewritten


def main() -> int:
    args = parse_args()
    rewritten = rewrite_text(
        args.input.read_text(encoding="utf-8"),
        allow_remaining_llhd=args.allow_remaining_llhd,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rewritten, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
