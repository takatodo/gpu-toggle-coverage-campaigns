#!/usr/bin/env python3
"""Helpers for reading and patching preload images."""

from __future__ import annotations

import pathlib


def load_program_hex(path: str | pathlib.Path) -> dict[int, int]:
    src = pathlib.Path(path).expanduser().resolve()
    memory: dict[int, int] = {}
    current_addr = 0
    for raw_line in src.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        for token in line.split():
            if token.startswith("@"):
                current_addr = int(token[1:], 16)
                continue
            value = int(token, 16)
            if value < 0 or value > 0xFF:
                raise ValueError(f"program.hex token out of byte range in {src}: {token}")
            memory[current_addr] = value
            current_addr += 1
    if not memory:
        raise ValueError(f"No memory data found in {src}")
    return memory


def load_memory_image(path: str | pathlib.Path, fmt: str = "auto") -> dict[int, int]:
    src = pathlib.Path(path).expanduser().resolve()
    cooked = fmt.lower()
    if cooked == "auto":
        cooked = "bin" if src.suffix.lower() in {".bin", ".img"} else "hex"
    if cooked == "bin":
        data = src.read_bytes()
        if not data:
            raise ValueError(f"No memory data found in {src}")
        return {idx: value for idx, value in enumerate(data)}
    if cooked == "hex":
        return load_program_hex(src)
    raise ValueError(f"Unsupported memory image format: {fmt}")


def load_program_hex_map(path: str | pathlib.Path) -> list[tuple[int, int, str]]:
    src = pathlib.Path(path).expanduser().resolve()
    entries: list[tuple[int, int, str]] = []
    for lineno, raw_line in enumerate(src.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        toks = line.split()
        if len(toks) == 2:
            addr_text, var_name = toks
            byte_count = 4
        elif len(toks) == 3:
            addr_text, byte_count_text, var_name = toks
            try:
                byte_count = int(byte_count_text, 0)
            except ValueError as exc:
                raise ValueError(
                    f"invalid byte count in program_hex_map {src}:{lineno}: {byte_count_text}"
                ) from exc
        else:
            raise ValueError(
                f"invalid program_hex_map line in {src}:{lineno}: expected 'addr var' or 'addr bytes var'"
            )
        try:
            addr = int(addr_text, 0)
        except ValueError as exc:
            raise ValueError(f"invalid address in program_hex_map {src}:{lineno}: {addr_text}") from exc
        if byte_count <= 0 or byte_count > 4:
            raise ValueError(f"program_hex_map byte count must be in 1..4 at {src}:{lineno}")
        entries.append((addr, byte_count, var_name))
    if not entries:
        raise ValueError(f"program_hex_map is empty: {src}")
    return entries


def load_visible_preload_map(path: str | pathlib.Path, label: str = "preload_map") -> list[tuple[int, int, str]]:
    src = pathlib.Path(path).expanduser().resolve()
    entries: list[tuple[int, int, str]] = []
    for lineno, raw_line in enumerate(src.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        toks = line.split()
        if len(toks) == 2:
            addr_text, var_name = toks
            byte_count = 4
        elif len(toks) == 3:
            addr_text, byte_count_text, var_name = toks
            try:
                byte_count = int(byte_count_text, 0)
            except ValueError as exc:
                raise ValueError(f"invalid byte count in {label} {src}:{lineno}: {byte_count_text}") from exc
        else:
            raise ValueError(
                f"invalid {label} line in {src}:{lineno}: expected 'addr var' or 'addr bytes var'"
            )
        try:
            addr = int(addr_text, 0)
        except ValueError as exc:
            raise ValueError(f"invalid address in {label} {src}:{lineno}: {addr_text}") from exc
        if byte_count <= 0 or byte_count > 4:
            raise ValueError(f"{label} byte count must be in 1..4 at {src}:{lineno}")
        entries.append((addr, byte_count, var_name))
    if not entries:
        raise ValueError(f"{label} is empty: {src}")
    return entries


def store_program_hex(path: str | pathlib.Path, memory: dict[int, int], bytes_per_line: int = 16) -> None:
    dst = pathlib.Path(path).expanduser().resolve()
    if not memory:
        raise ValueError("Cannot write empty program.hex memory image")
    addrs = sorted(memory.keys())
    lines: list[str] = []
    run_start = addrs[0]
    run_bytes = [memory[run_start]]
    last_addr = run_start

    def flush(start_addr: int, data: list[int]) -> None:
        lines.append(f"@{start_addr:08X}")
        for idx in range(0, len(data), bytes_per_line):
            chunk = data[idx: idx + bytes_per_line]
            lines.append(" ".join(f"{byte:02X}" for byte in chunk))

    for addr in addrs[1:]:
        if addr == last_addr + 1:
            run_bytes.append(memory[addr])
        else:
            flush(run_start, run_bytes)
            run_start = addr
            run_bytes = [memory[addr]]
        last_addr = addr
    flush(run_start, run_bytes)
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")


def store_memory_image(path: str | pathlib.Path, memory: dict[int, int], fmt: str = "bin") -> None:
    dst = pathlib.Path(path).expanduser().resolve()
    cooked = fmt.lower()
    if cooked == "bin":
        if not memory:
            raise ValueError("Cannot write empty memory image")
        addrs = sorted(memory.keys())
        if addrs[0] < 0:
            raise ValueError("Binary memory image requires non-negative offsets")
        buf = bytearray(addrs[-1] + 1)
        for addr, value in memory.items():
            buf[addr] = value & 0xFF
        dst.write_bytes(bytes(buf))
        return
    if cooked == "hex":
        store_program_hex(dst, memory)
        return
    raise ValueError(f"Unsupported memory image format: {fmt}")


def patch_iterations(memory: dict[int, int], iterations: int, base_addr: int = 0x10000000) -> dict[int, int]:
    if iterations < 0 or iterations > 0xFFFFFFFF:
        raise ValueError("iterations must fit in 32 bits")
    patched = dict(memory)
    for byte_idx in range(4):
        patched[base_addr + byte_idx] = (iterations >> (8 * byte_idx)) & 0xFF
    return patched
