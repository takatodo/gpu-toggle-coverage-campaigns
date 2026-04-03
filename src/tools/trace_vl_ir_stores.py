#!/usr/bin/env python3
"""
Trace LLVM IR store sites for selected Verilator root fields.

This is a Phase B debugging aid: given an mdir and one or more generated LLVM
function names, report which root fields those functions store to, using the
anonymous-struct layout from `*_root.h` to recover field names from GEP chains.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFINE_RE = re.compile(r"^define .* @(?P<name>[^(\s]+)\(")
ANON_TYPE_RE = re.compile(r"^(?P<name>%struct\.anon(?:\.\d+)?) = type\b")
GEP_RE = re.compile(
    r"^\s*(?P<lhs>%[-.\w]+)\s*=\s*getelementptr(?:\s+inbounds)?\s+"
    r"(?P<base_type>[^,]+),\s+ptr\s+(?P<base>%[-.\w]+),\s*(?P<indices>.+)$"
)
STORE_RE = re.compile(r"^\s*store\s+.+,\s+ptr\s+(?P<dest>%[-.\w]+),")
CAST_RE = re.compile(
    r"^\s*(?P<lhs>%[-.\w]+)\s*=\s*(?:bitcast|addrspacecast)\s+ptr\s+(?P<base>%[-.\w]+)\s+to\s+ptr"
)
INDEX_RE = re.compile(r"i\d+\s+([^,]+)")
FIELD_MACRO_RE = re.compile(r"^\s*VL_(?:IN|OUT)\d*\(\s*([A-Za-z_]\w*)\s*,")
FIELD_DECL_RE = re.compile(r"([A-Za-z_]\w*)\s*;\s*$")


def classify_field_role(field_name: str) -> str:
    if field_name.startswith("__V") or field_name in {"vlSymsp", "vlNamep", "__VdlySched"}:
        return "verilator_internal"
    if "__DOT__" in field_name:
        return "design_state"
    if field_name.endswith("_i") or field_name.endswith("_o"):
        return "top_level_io"
    return "other"


def extract_member_name(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith(("//", "#")):
        return None
    if stripped in {"public:", "private:", "protected:", "};"}:
        return None
    if stripped.startswith("class "):
        return None
    if stripped.startswith("struct ") and stripped.endswith("{"):
        return None
    macro_match = FIELD_MACRO_RE.match(stripped)
    if macro_match:
        return macro_match.group(1)
    if "(" in stripped or ")" in stripped:
        return None
    decl_match = FIELD_DECL_RE.search(stripped)
    if decl_match:
        return decl_match.group(1)
    return None


def parse_root_header_layout(root_h: Path) -> list[dict[str, object]]:
    top_fields: list[dict[str, object]] = []
    current_members: list[str] | None = None
    for raw_line in root_h.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped == "struct {":
            current_members = []
            continue
        if current_members is not None:
            if stripped == "};":
                top_fields.append({"kind": "struct", "members": list(current_members)})
                current_members = None
                continue
            member_name = extract_member_name(stripped)
            if member_name is not None:
                current_members.append(member_name)
            continue
        member_name = extract_member_name(stripped)
        if member_name is not None:
            top_fields.append({"kind": "field", "name": member_name})
    return top_fields


def preferred_ll_files(mdir: Path) -> list[Path]:
    direct = sorted(mdir.glob("*___024root__0.ll"))
    if direct:
        return direct
    merged = mdir / "merged.ll"
    if merged.exists():
        return [merged]
    return sorted(mdir.glob("*.ll"))


def parse_anon_struct_types(ll_path: Path, top_fields: list[dict[str, object]]) -> dict[str, list[str]]:
    struct_blocks = [list(entry["members"]) for entry in top_fields if entry["kind"] == "struct"]
    anon_types: list[str] = []
    for raw_line in ll_path.read_text(encoding="utf-8").splitlines():
        match = ANON_TYPE_RE.match(raw_line)
        if match:
            anon_types.append(match.group("name"))
        elif raw_line.startswith("define "):
            break
    return {type_name: members for type_name, members in zip(anon_types, struct_blocks)}


def parse_indices(raw_indices: str) -> list[str]:
    return [match.group(1).strip() for match in INDEX_RE.finditer(raw_indices)]


def normalize_extra_indices(indices: list[str]) -> tuple[list[str], bool]:
    dynamic = False
    normalized: list[str] = []
    for idx, token in enumerate(indices):
        if idx == 0 and token == "0":
            continue
        if token.startswith("%"):
            dynamic = True
            normalized.append(f"<dynamic:{token}>")
            continue
        normalized.append(token)
    return normalized, dynamic


def resolve_root_gep(
    *,
    top_fields: list[dict[str, object]],
    anon_struct_types: dict[str, list[str]],
    base_type: str,
    indices: list[str],
) -> dict[str, object] | None:
    base_type = base_type.strip()
    anon_members = anon_struct_types.get(base_type)
    if anon_members is not None:
        if len(indices) < 2 or indices[0] != "0" or not indices[1].isdigit():
            return None
        member_index = int(indices[1])
        if member_index >= len(anon_members):
            return None
        field_name = str(anon_members[member_index])
        extra_indices, dynamic = normalize_extra_indices(indices[2:])
        return {
            "field_name": field_name,
            "element_path": extra_indices,
            "dynamic_index": dynamic,
        }
    if len(indices) < 2 or indices[0] != "0" or not indices[1].isdigit():
        return None
    top_index = int(indices[1])
    if top_index >= len(top_fields):
        return None
    top_field = top_fields[top_index]
    if top_field["kind"] == "struct":
        members = list(top_field["members"])
        if len(indices) < 3 or not indices[2].isdigit():
            return None
        member_index = int(indices[2])
        if member_index >= len(members):
            return None
        field_name = str(members[member_index])
        extra_indices, dynamic = normalize_extra_indices(indices[3:])
        return {
            "field_name": field_name,
            "element_path": extra_indices,
            "dynamic_index": dynamic,
        }
    field_name = str(top_field["name"])
    extra_indices, dynamic = normalize_extra_indices(indices[2:])
    return {
        "field_name": field_name,
        "element_path": extra_indices,
        "dynamic_index": dynamic,
    }


def resolve_alias_gep(base_alias: dict[str, object], indices: list[str]) -> dict[str, object]:
    extra_indices, dynamic = normalize_extra_indices(indices)
    return {
        "field_name": str(base_alias["field_name"]),
        "element_path": list(base_alias.get("element_path", [])) + extra_indices,
        "dynamic_index": bool(base_alias.get("dynamic_index", False)) or dynamic,
    }


def format_element_path(path: list[str]) -> str:
    if not path:
        return ""
    return "".join(f"[{part}]" for part in path)


def summarize_store_entries(entries: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    summary: dict[str, dict[str, object]] = {}
    for entry in entries:
        field_name = str(entry["field_name"])
        bucket = summary.setdefault(
            field_name,
            {
                "field_role": classify_field_role(field_name),
                "store_count": 0,
                "first_line": int(entry["line"]),
                "first_element_path": str(entry["element_path"]),
                "dynamic_index": False,
            },
        )
        bucket["store_count"] = int(bucket["store_count"]) + 1
        bucket["dynamic_index"] = bool(bucket["dynamic_index"]) or bool(entry["dynamic_index"])
    return summary


def trace_function_stores(
    mdir: Path,
    function_names: list[str],
    *,
    field_names: list[str] | None = None,
) -> dict[str, object]:
    prefix = mdir.name
    matches: set[str] | None = set(field_names) if field_names else None
    root_headers = sorted(mdir.glob("*___024root.h"))
    if not root_headers:
        raise FileNotFoundError(f"no *_root.h found under {mdir}")
    top_fields = parse_root_header_layout(root_headers[0])
    ll_files = preferred_ll_files(mdir)

    results: dict[str, dict[str, object]] = {}
    wanted = set(function_names)
    for ll_path in ll_files:
        anon_struct_types = parse_anon_struct_types(ll_path, top_fields)
        current_function: str | None = None
        aliases: dict[str, dict[str, object]] = {}
        current_entries: list[dict[str, object]] = []
        for lineno, raw_line in enumerate(ll_path.read_text(encoding="utf-8").splitlines(), start=1):
            define_match = DEFINE_RE.match(raw_line)
            if define_match:
                current_function = define_match.group("name")
                aliases = {"%0": {"root": True}}
                current_entries = []
                continue

            if current_function is None or current_function not in wanted:
                continue

            if raw_line.strip() == "}":
                if current_function not in results:
                    results[current_function] = {
                        "path": str(ll_path),
                        "store_count": len(current_entries),
                        "field_summary": summarize_store_entries(current_entries),
                        "stores": current_entries,
                    }
                current_function = None
                aliases = {}
                current_entries = []
                continue

            cast_match = CAST_RE.match(raw_line)
            if cast_match:
                base = cast_match.group("base")
                if base in aliases:
                    aliases[cast_match.group("lhs")] = dict(aliases[base])
                continue

            gep_match = GEP_RE.match(raw_line)
            if gep_match:
                lhs = gep_match.group("lhs")
                base = gep_match.group("base")
                indices = parse_indices(gep_match.group("indices"))
                if base == "%0":
                    resolved = resolve_root_gep(
                        top_fields=top_fields,
                        anon_struct_types=anon_struct_types,
                        base_type=gep_match.group("base_type"),
                        indices=indices,
                    )
                    if resolved is not None:
                        aliases[lhs] = resolved
                        continue
                elif base in aliases and "field_name" in aliases[base]:
                    aliases[lhs] = resolve_alias_gep(aliases[base], indices)
                continue

            store_match = STORE_RE.match(raw_line)
            if store_match:
                dest = store_match.group("dest")
                alias = aliases.get(dest)
                if alias is None or "field_name" not in alias:
                    continue
                field_name = str(alias["field_name"])
                if matches is not None and field_name not in matches:
                    continue
                element_path = format_element_path(list(alias.get("element_path", [])))
                current_entries.append(
                    {
                        "line": lineno,
                        "field_name": field_name,
                        "field_role": classify_field_role(field_name),
                        "element_path": element_path,
                        "dynamic_index": bool(alias.get("dynamic_index", False)),
                        "text": raw_line.strip(),
                    }
                )

    payload = {"mdir": str(mdir), "function_count": len(results), "functions": results}
    if results:
        payload["source_prefix"] = prefix
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Trace LLVM store sites for selected Verilator functions")
    parser.add_argument("mdir", type=Path, help="Verilator --cc output directory")
    parser.add_argument("functions", nargs="+", help="Generated LLVM function names to inspect")
    parser.add_argument(
        "--fields",
        nargs="*",
        default=None,
        help="Optional field-name filter from compare/writer-trace output",
    )
    parser.add_argument("--json-out", type=Path, default=None, help="Optional JSON output path")
    args = parser.parse_args()

    payload = trace_function_stores(
        args.mdir.resolve(),
        list(args.functions),
        field_names=list(args.fields) if args.fields else None,
    )
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"wrote: {args.json_out}")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
