#!/usr/bin/env python3
"""Extract a simple signal/modport manifest from a SystemVerilog interface."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


INTERFACE_RE = re.compile(
    r"(?ms)\binterface\s+(?P<name>[A-Za-z_]\w*)\b.*?\)\s*\(\s*\)\s*;(?P<body>.*?)\bendinterface\b"
)
SIGNAL_RE = re.compile(
    r"^(?P<kind>logic|wire|bit|reg)(?:\s+(?P<type>.+?))?\s+(?P<name>[A-Za-z_]\w*)\s*$",
    flags=re.DOTALL,
)
MODPORT_RE = re.compile(r"(?ms)\bmodport\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<body>.*?)\)\s*;")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract signal/modport metadata from a SystemVerilog interface definition."
    )
    parser.add_argument("source", type=Path, help="SystemVerilog file containing the interface")
    parser.add_argument(
        "--interface-name",
        default=None,
        help="Explicit interface name when the file contains multiple interfaces",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output JSON manifest path",
    )
    return parser.parse_args()


def _strip_comments(text: str) -> str:
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text


def _normalize_space(text: str) -> str:
    return " ".join(text.replace("\n", " ").split())


def _collect_signals(body: str) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    for stmt in body.split(";"):
        line = _normalize_space(stmt)
        if not line or line.startswith("modport "):
            continue
        match = SIGNAL_RE.match(line)
        if match is None:
            continue
        type_text = (match.group("type") or "").strip()
        name = match.group("name")
        signals.append(
            {
                "kind": match.group("kind"),
                "type": type_text,
                "name": name,
            }
        )
    return signals


def _collect_modports(body: str) -> dict[str, list[dict[str, str]]]:
    modports: dict[str, list[dict[str, str]]] = {}
    for match in MODPORT_RE.finditer(body):
        modport_name = match.group("name")
        entries: list[dict[str, str]] = []
        current_direction: str | None = None
        for token in match.group("body").replace("\n", " ").split(","):
            item = " ".join(token.split())
            if not item:
                continue
            words = item.split()
            if words[0] in {"input", "output", "inout", "ref"}:
                current_direction = words[0]
                names = words[1:]
            else:
                names = words
            if current_direction is None:
                raise ValueError(f"Could not infer modport direction in {modport_name}: {item}")
            for name in names:
                entries.append({"direction": current_direction, "name": name})
        modports[modport_name] = entries
    return modports


def _augment_signals_from_modports(
    signals: list[dict[str, str]],
    modports: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    augmented = list(signals)
    known = {signal["name"] for signal in augmented}
    for entries in modports.values():
        for entry in entries:
            if entry["name"] in known:
                continue
            augmented.append(
                {
                    "kind": "logic",
                    "type": "",
                    "name": entry["name"],
                }
            )
            known.add(entry["name"])
    return augmented


def main() -> int:
    args = parse_args()
    text = _strip_comments(args.source.read_text(encoding="utf-8"))
    matches = list(INTERFACE_RE.finditer(text))
    if not matches:
        raise SystemExit(f"No interface definition found in {args.source}")

    selected = None
    if args.interface_name is None:
        if len(matches) != 1:
            names = ", ".join(match.group("name") for match in matches)
            raise SystemExit(
                f"Multiple interfaces found in {args.source}; pass --interface-name. Found: {names}"
            )
        selected = matches[0]
    else:
        for match in matches:
            if match.group("name") == args.interface_name:
                selected = match
                break
        if selected is None:
            raise SystemExit(
                f"Interface {args.interface_name} not found in {args.source}"
            )

    body = selected.group("body")
    modports = _collect_modports(body)
    manifest = {
        "source": str(args.source.resolve()),
        "interface": selected.group("name"),
        "signals": _augment_signals_from_modports(_collect_signals(body), modports),
        "modports": modports,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
