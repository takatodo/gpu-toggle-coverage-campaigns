#!/usr/bin/env python3
"""Summarize residual SSA cycles inside a single top-level hw.module body."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from pathlib import Path
import re


SSA_RE = re.compile(r"%[A-Za-z0-9_.$#-]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Input MLIR file")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON summary")
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


def extract_hw_module_body(text: str) -> tuple[list[str], set[str]]:
    marker = "hw.module @"
    start = text.find(marker)
    if start == -1:
        raise ValueError("Expected a top-level hw.module")
    paren_start = text.find("(", start)
    paren_end = find_matching(text, paren_start, "(", ")")
    port_list = text[paren_start + 1 : paren_end]
    module_inputs: set[str] = set()
    for chunk in port_list.split(","):
        chunk = chunk.strip()
        if not chunk.startswith("in %"):
            continue
        name = chunk.split(":", 1)[0].split()[-1]
        module_inputs.add(name)

    scan = paren_end + 1
    while scan < len(text) and text[scan].isspace():
        scan += 1
    if text.startswith("attributes", scan):
        attr_brace_start = text.find("{", scan)
        attr_brace_end = find_matching(text, attr_brace_start, "{", "}")
        scan = attr_brace_end + 1
    while scan < len(text) and text[scan].isspace():
        scan += 1

    body_start = scan
    if text[body_start] != "{":
        raise ValueError("Expected hw.module body")
    body_end = find_matching(text, body_start, "{", "}")
    body = text[body_start + 1 : body_end]

    output_pos = body.rfind("hw.output ")
    if output_pos == -1:
        raise ValueError("Expected hw.output terminator")
    body_ops = body[: body.rfind("\n", 0, output_pos) + 1]
    return [line for line in body_ops.splitlines() if line.strip()], module_inputs


def collect_reachable_inputs(
    start_nodes: set[int],
    reverse: list[set[int]],
    lines: list[str],
    module_inputs: set[str],
    component: set[int],
) -> set[str]:
    reachable_input_names: set[str] = set()
    worklist = list(start_nodes)
    seen_nodes: set[int] = set()
    while worklist:
        node = worklist.pop()
        if node in seen_nodes:
            continue
        seen_nodes.add(node)
        rhs = lines[node].split(" = ", 1)[1] if " = " in lines[node] else lines[node]
        for value in SSA_RE.findall(rhs):
            if value in module_inputs:
                reachable_input_names.add(value)
        for pred in reverse[node]:
            if pred not in component:
                worklist.append(pred)
    return reachable_input_names


def summarize(lines: list[str], module_inputs: set[str]) -> dict[str, object]:
    producers: dict[str, int] = {}
    adjacency: list[set[int]] = [set() for _ in lines]
    reverse: list[set[int]] = [set() for _ in lines]
    for idx, line in enumerate(lines):
        lhs = line.split(" = ", 1)[0] if " = " in line else ""
        for value in SSA_RE.findall(lhs):
            producers[value] = idx

    for idx, line in enumerate(lines):
        rhs = line.split(" = ", 1)[1] if " = " in line else line
        for value in SSA_RE.findall(rhs):
            producer = producers.get(value)
            if producer is None or producer == idx:
                continue
            adjacency[producer].add(idx)
            reverse[idx].add(producer)

    indegree = [len(deps) for deps in reverse]
    ready = deque(idx for idx, deg in enumerate(indegree) if deg == 0)
    scheduled: list[int] = []
    seen: set[int] = set()
    while ready:
        idx = ready.popleft()
        if idx in seen:
            continue
        seen.add(idx)
        scheduled.append(idx)
        for user in adjacency[idx]:
            indegree[user] -= 1
            if indegree[user] == 0:
                ready.append(user)

    remaining = [idx for idx in range(len(lines)) if idx not in seen]
    remaining_set = set(remaining)

    indices: dict[int, int] = {}
    lowlinks: dict[int, int] = {}
    stack: list[int] = []
    on_stack: set[int] = set()
    sccs: list[list[int]] = []

    def strongconnect(v: int) -> None:
        indices[v] = len(indices)
        lowlinks[v] = indices[v]
        stack.append(v)
        on_stack.add(v)
        for user in adjacency[v]:
            if user not in remaining_set:
                continue
            if user not in indices:
                strongconnect(user)
                lowlinks[v] = min(lowlinks[v], lowlinks[user])
            elif user in on_stack:
                lowlinks[v] = min(lowlinks[v], indices[user])
        if lowlinks[v] == indices[v]:
            component: list[int] = []
            while True:
                node = stack.pop()
                on_stack.remove(node)
                component.append(node)
                if node == v:
                    break
            sccs.append(component)

    for idx in remaining:
        if idx not in indices:
            strongconnect(idx)

    nontrivial = sorted((comp for comp in sccs if len(comp) > 1), key=len, reverse=True)

    def find_cycle(component: list[int]) -> list[int]:
        component_set = set(component)
        start = min(component)
        stack: list[int] = []
        on_path: set[int] = set()
        seen_local: set[int] = set()

        def dfs(node: int) -> list[int] | None:
            stack.append(node)
            on_path.add(node)
            seen_local.add(node)
            for user in adjacency[node]:
                if user not in component_set:
                    continue
                if user in on_path:
                    cycle_start = stack.index(user)
                    return stack[cycle_start:] + [user]
                if user in seen_local:
                    continue
                found = dfs(user)
                if found is not None:
                    return found
            stack.pop()
            on_path.remove(node)
            return None

        found = dfs(start)
        return found or []

    summary = {
        "op_count": len(lines),
        "acyclic_prefix_count": len(scheduled),
        "remaining_count": len(remaining),
        "nontrivial_scc_count": len(nontrivial),
        "largest_scc_size": len(nontrivial[0]) if nontrivial else 0,
        "largest_scc_sample": [],
        "largest_scc_cycle": [],
    }
    if nontrivial:
        sample = []
        for idx in sorted(nontrivial[0])[:12]:
            sample.append(
                {
                    "line_index_1based": idx + 1,
                    "text": lines[idx].strip(),
                }
            )
        summary["largest_scc_sample"] = sample
        cycle = []
        cycle_indices = find_cycle(nontrivial[0])
        component = set(nontrivial[0])
        cycle_input_names: set[str] = set()
        boundary_predecessors: set[int] = set()
        cycle_boundary_predecessors: set[int] = set()
        for idx in component:
            rhs = lines[idx].split(" = ", 1)[1] if " = " in lines[idx] else lines[idx]
            for value in SSA_RE.findall(rhs):
                if value in module_inputs:
                    cycle_input_names.add(value)
            for pred in reverse[idx]:
                if pred not in component:
                    boundary_predecessors.add(pred)
        for idx in cycle_indices:
            rhs = lines[idx].split(" = ", 1)[1] if " = " in lines[idx] else lines[idx]
            for value in SSA_RE.findall(rhs):
                if value in module_inputs:
                    cycle_input_names.add(value)
            for pred in reverse[idx]:
                if pred not in component:
                    cycle_boundary_predecessors.add(pred)
        for idx in cycle_indices:
            cycle.append(
                {
                    "line_index_1based": idx + 1,
                    "text": lines[idx].strip(),
                }
            )
        summary["largest_scc_cycle"] = cycle
        summary["largest_scc_external_inputs"] = sorted(cycle_input_names)
        summary["largest_scc_state_inputs"] = sorted(
            value for value in cycle_input_names if value.startswith("%dout_state")
        )
        summary["largest_scc_boundary_predecessors"] = [
            {
                "line_index_1based": idx + 1,
                "text": lines[idx].strip(),
            }
            for idx in sorted(boundary_predecessors)[:24]
        ]
        summary["largest_scc_cycle_boundary_predecessors"] = [
            {
                "line_index_1based": idx + 1,
                "text": lines[idx].strip(),
            }
            for idx in sorted(cycle_boundary_predecessors)[:24]
        ]
        reachable_input_names = collect_reachable_inputs(
            boundary_predecessors, reverse, lines, module_inputs, component
        )
        summary["largest_scc_reachable_external_inputs"] = sorted(reachable_input_names)
        summary["largest_scc_reachable_state_inputs"] = sorted(
            value for value in reachable_input_names if value.startswith("%dout_state")
        )
        cycle_reachable_input_names = collect_reachable_inputs(
            cycle_boundary_predecessors, reverse, lines, module_inputs, component
        )
        summary["largest_scc_cycle_boundary_reachable_external_inputs"] = sorted(
            cycle_reachable_input_names
        )
        summary["largest_scc_cycle_boundary_reachable_state_inputs"] = sorted(
            value for value in cycle_reachable_input_names if value.startswith("%dout_state")
        )
    return summary


def main() -> int:
    args = parse_args()
    lines, module_inputs = extract_hw_module_body(args.input.read_text(encoding="utf-8"))
    summary = summarize(lines, module_inputs)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
