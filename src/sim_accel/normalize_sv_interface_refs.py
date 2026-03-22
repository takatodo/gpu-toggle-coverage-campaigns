#!/usr/bin/env python3
"""Rewrite a specific SystemVerilog interface usage into explicit signals."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re


PREFIX_SEP = "__"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize one SystemVerilog interface definition/usage surface into "
            "explicit wires and ports using a manifest extracted from the interface."
        )
    )
    parser.add_argument(
        "--interface-manifest",
        type=Path,
        required=True,
        help="JSON manifest produced by extract_sv_interface_manifest.py",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Output root for rewritten source files and manifest",
    )
    parser.add_argument(
        "--extra-file",
        action="append",
        default=[],
        help="Additional file to rewrite/copy into the output tree without listing it as a primary source",
    )
    parser.add_argument(
        "sources",
        nargs="+",
        help="Source files to rewrite or copy into the output tree",
    )
    return parser.parse_args()


def _common_root(paths: list[Path]) -> Path:
    return Path(os.path.commonpath([str(path) for path in paths]))


def _load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _port_decl_re(interface_name: str, modports: list[str]) -> re.Pattern[str]:
    joined = "|".join(re.escape(name) for name in sorted(modports, key=len, reverse=True))
    return re.compile(
        rf"(?m)^(?P<indent>\s*){re.escape(interface_name)}\.(?P<modport>{joined})\s+"
        rf"(?P<name>[A-Za-z_]\w*)\s*(?P<trailer>,?)\s*(?P<comment>//[^\n]*)?$"
    )


def _local_decl_re(interface_name: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?m)^(?P<indent>\s*){re.escape(interface_name)}\s+"
        rf"(?P<name>[A-Za-z_]\w*)\s*\(\s*\)\s*;\s*(?P<comment>//[^\n]*)?$"
    )


def _conn_re(modports: list[str]) -> re.Pattern[str]:
    joined = "|".join(re.escape(name) for name in sorted(modports, key=len, reverse=True))
    return re.compile(
        rf"(?m)^(?P<indent>\s*)\.(?P<formal>[A-Za-z_]\w*)\s*\(\s*"
        rf"(?P<actual>[A-Za-z_]\w*)\s*\.\s*(?P<modport>{joined})\s*\)\s*(?P<trailer>,?)\s*$"
    )


def _named_arg_re() -> re.Pattern[str]:
    return re.compile(
        r"^(?P<indent>\s*)\.(?P<formal>[A-Za-z_]\w*)\s*\(\s*"
        r"(?P<actual>[A-Za-z_]\w*)(?:\s*\.\s*(?P<actual_modport>[A-Za-z_]\w*))?\s*\)"
        r"\s*(?P<trailer>,?)\s*$"
    )


def _signal_decl(prefix: str, signal: dict[str, str], *, direction: str | None = None, indent: str = "") -> str:
    kind = signal["kind"]
    type_part = f" {signal['type']}" if signal["type"] else ""
    if direction is None:
        return f"{indent}{kind}{type_part} {prefix}{PREFIX_SEP}{signal['name']};"
    return f"{indent}{direction} {kind}{type_part} {prefix}{PREFIX_SEP}{signal['name']}"


def _augment_signal_map(
    signals: list[dict[str, str]],
    *,
    modports: dict[str, list[dict[str, str]]],
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    augmented = list(signals)
    signal_map = {signal["name"]: signal for signal in augmented}
    for entries in modports.values():
        for entry in entries:
            if entry["name"] in signal_map:
                continue
            synthesized = {
                "kind": "logic",
                "type": "",
                "name": entry["name"],
            }
            augmented.append(synthesized)
            signal_map[entry["name"]] = synthesized
    return augmented, signal_map


def _expand_port_decl(match: re.Match[str], *, signal_map: dict[str, dict[str, str]], modports: dict[str, list[dict[str, str]]]) -> str:
    indent = match.group("indent")
    name = match.group("name")
    trailer = match.group("trailer")
    comment = match.group("comment") or ""
    entries = modports[match.group("modport")]
    lines: list[str] = []
    for idx, entry in enumerate(entries):
        signal = signal_map[entry["name"]]
        suffix = "," if idx < len(entries) - 1 or trailer == "," else ""
        line = _signal_decl(name, signal, direction=entry["direction"], indent=indent) + suffix
        if idx == len(entries) - 1 and comment:
            line += f" {comment}"
        lines.append(line)
    return "\n".join(lines)


def _expand_local_decl(match: re.Match[str], *, signals: list[dict[str, str]]) -> str:
    indent = match.group("indent")
    name = match.group("name")
    comment = match.group("comment") or ""
    lines = [_signal_decl(name, signal, indent=indent) for signal in signals]
    if comment and lines:
        lines[-1] += f" {comment}"
    return "\n".join(lines)


def _expand_named_conn(match: re.Match[str], *, modports: dict[str, list[dict[str, str]]]) -> str:
    indent = match.group("indent")
    formal = match.group("formal")
    actual = match.group("actual")
    trailer = match.group("trailer")
    entries = modports[match.group("modport")]
    lines: list[str] = []
    for idx, entry in enumerate(entries):
        suffix = "," if idx < len(entries) - 1 or trailer == "," else ""
        sig = entry["name"]
        lines.append(
            f"{indent}.{formal}{PREFIX_SEP}{sig}({actual}{PREFIX_SEP}{sig}){suffix}"
        )
    return "\n".join(lines)


def _scan_module_interface_ports(source_texts: dict[Path, str], *, interface_name: str, modports: list[str]) -> dict[str, dict[str, str]]:
    module_ports: dict[str, dict[str, str]] = {}
    port_re = _port_decl_re(interface_name, modports)
    current_module: str | None = None
    for text in source_texts.values():
        for line in text.splitlines():
            module_match = re.match(r"^\s*module\s+([A-Za-z_]\w*)\b", line)
            if module_match:
                current_module = module_match.group(1)
                module_ports.setdefault(current_module, {})
                continue
            if current_module is None:
                continue
            if re.match(r"^\s*endmodule\b", line):
                current_module = None
                continue
            port_match = port_re.match(line)
            if port_match is None:
                continue
            module_ports[current_module][port_match.group("name")] = port_match.group("modport")
    return module_ports


def _collect_interface_names(text: str, *, interface_name: str, modports: list[str]) -> set[str]:
    names = set()
    decl_re = re.compile(
        rf"\b{re.escape(interface_name)}(?:\.(?:{'|'.join(re.escape(name) for name in modports)}))?"
        rf"\s+([A-Za-z_]\w*)\s*(?:\(\s*\)|[,;])"
    )
    for match in decl_re.finditer(text):
        names.add(match.group(1))
    return names


def _expand_interface_connections(
    text: str,
    *,
    module_interface_ports: dict[str, dict[str, str]],
    modports: dict[str, list[dict[str, str]]],
    interface_names: set[str],
) -> str:
    inst_modules = [name for name, ports in module_interface_ports.items() if ports]
    if not inst_modules:
        return text

    joined = "|".join(re.escape(name) for name in sorted(inst_modules, key=len, reverse=True))
    inst_re = re.compile(
        rf"(?ms)^(?P<indent>\s*)(?P<module>{joined})\b"
        rf"(?:\s*#\s*\(.*?\))?\s+(?P<instance>[A-Za-z_]\w*)\s*\((?P<body>.*?)^\s*\)\s*;"
    )
    named_arg_re = _named_arg_re()

    def replace_inst(match: re.Match[str]) -> str:
        module_name = match.group("module")
        body = match.group("body")
        replaced_lines: list[str] = []
        for line in body.splitlines():
            arg_match = named_arg_re.match(line)
            if arg_match is None:
                replaced_lines.append(line)
                continue
            formal = arg_match.group("formal")
            actual = arg_match.group("actual")
            actual_modport = arg_match.group("actual_modport")
            if formal not in module_interface_ports[module_name]:
                replaced_lines.append(line)
                continue
            if actual_modport is None and actual not in interface_names:
                replaced_lines.append(line)
                continue
            modport_name = module_interface_ports[module_name][formal]
            trailer = arg_match.group("trailer")
            indent = arg_match.group("indent")
            entries = modports[modport_name]
            expanded: list[str] = []
            for idx, entry in enumerate(entries):
                sig = entry["name"]
                suffix = "," if idx < len(entries) - 1 or trailer == "," else ""
                expanded.append(
                    f"{indent}.{formal}{PREFIX_SEP}{sig}({actual}{PREFIX_SEP}{sig}){suffix}"
                )
            replaced_lines.append("\n".join(expanded))
        body_out = "\n".join(replaced_lines)
        return match.group(0).replace(body, body_out, 1)

    return inst_re.sub(replace_inst, text)


def _replace_field_accesses(text: str, *, interface_names: set[str], signal_names: list[str]) -> str:
    for name in sorted(interface_names, key=len, reverse=True):
        for signal_name in signal_names:
            text = re.sub(
                rf"\b{re.escape(name)}\s*\.\s*{re.escape(signal_name)}\b",
                f"{name}{PREFIX_SEP}{signal_name}",
                text,
            )
    return text


def _rewrite_text(
    text: str,
    *,
    manifest: dict,
    module_interface_ports: dict[str, dict[str, str]],
    global_interface_names: set[str],
) -> str:
    interface_name = manifest["interface"]
    modports = manifest["modports"]
    signals, signal_map = _augment_signal_map(manifest["signals"], modports=modports)
    modport_names = list(modports)

    interface_names = _collect_interface_names(text, interface_name=interface_name, modports=modport_names)
    known_interface_names = interface_names | global_interface_names
    text = _port_decl_re(interface_name, modport_names).sub(
        lambda match: _expand_port_decl(match, signal_map=signal_map, modports=modports),
        text,
    )
    text = _local_decl_re(interface_name).sub(
        lambda match: _expand_local_decl(match, signals=signals),
        text,
    )
    text = _expand_interface_connections(
        text,
        module_interface_ports=module_interface_ports,
        modports=modports,
        interface_names=known_interface_names,
    )
    text = _replace_field_accesses(
        text,
        interface_names=known_interface_names,
        signal_names=[signal["name"] for signal in signals],
    )
    return text


def main() -> int:
    args = parse_args()
    manifest = _load_manifest(args.interface_manifest)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    source_paths = [Path(source).resolve() for source in args.sources]
    extra_paths = [Path(path).resolve() for path in args.extra_file]
    all_paths = source_paths + [path for path in extra_paths if path not in source_paths]
    source_texts = {source: source.read_text(encoding="utf-8") for source in all_paths}
    root = _common_root(all_paths)
    module_interface_ports = _scan_module_interface_ports(
        source_texts,
        interface_name=manifest["interface"],
        modports=list(manifest["modports"]),
    )
    global_interface_names: set[str] = set()
    for text in source_texts.values():
        global_interface_names.update(
            _collect_interface_names(
                text,
                interface_name=manifest["interface"],
                modports=list(manifest["modports"]),
            )
        )
    rewritten_sources: list[str] = []
    rewrite_manifest: dict[str, object] = {
        "interface_manifest": str(args.interface_manifest.resolve()),
        "interface": manifest["interface"],
        "source_root": str(root),
        "rewritten_sources": [],
        "rewritten_support_files": [],
        "dropped_sources": [],
    }

    interface_source = Path(manifest["source"]).resolve()
    primary_sources = set(source_paths)
    for source in all_paths:
        rel = source.relative_to(root)
        out_path = args.out_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if source == interface_source:
            out_path.write_text(
                f"// normalized away unsupported interface {manifest['interface']}\n",
                encoding="utf-8",
            )
            rewrite_manifest["dropped_sources"].append(str(source))
            continue
        text = source_texts[source]
        rewritten = _rewrite_text(
            text,
            manifest=manifest,
            module_interface_ports=module_interface_ports,
            global_interface_names=global_interface_names,
        )
        out_path.write_text(rewritten, encoding="utf-8")
        record = {
            "source": str(source),
            "output": str(out_path),
            "changed": rewritten != text,
        }
        if source in primary_sources:
            rewritten_sources.append(str(out_path))
            rewrite_manifest["rewritten_sources"].append(record)
        else:
            rewrite_manifest["rewritten_support_files"].append(record)

    manifest_path = args.out_dir / "normalized_interface_manifest.json"
    manifest_path.write_text(json.dumps(rewrite_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sources_path = args.out_dir / "normalized_sources.txt"
    sources_path.write_text("".join(path + "\n" for path in rewritten_sources), encoding="utf-8")
    print(f"wrote {manifest_path}")
    print(f"wrote {sources_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
