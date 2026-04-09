from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from program_hex_tools import load_program_hex


DEFAULT_VEER_GPU_COV_ENTRY_MAX = 16384


def ensure_runtime_program_entries(
    *,
    mdir: Path,
    program_hex: Path,
    output_name: str = "program_entries.bin",
    entry_max: int = DEFAULT_VEER_GPU_COV_ENTRY_MAX,
) -> dict[str, Any]:
    source = program_hex.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"runtime program.hex not found: {source}")
    memory = load_program_hex(source)
    entries = sorted(memory.items())
    if len(entries) > entry_max - 1:
        raise ValueError(
            f"VeeR gpu_cov sparse program image exceeds entry capacity: {len(entries)} > {entry_max - 1}"
        )

    payload = bytearray()
    payload.extend(int(len(entries) & 0xFFFF_FFFF).to_bytes(8, byteorder="little", signed=False))
    for addr, data in entries:
        word = ((int(data) & 0xFF) << 32) | (int(addr) & 0xFFFF_FFFF)
        payload.extend(int(word).to_bytes(8, byteorder="little", signed=False))

    output_path = (mdir / output_name).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(payload))
    return {
        "program_hex": source,
        "program_entries_bin": output_path,
        "program_entry_count": len(entries),
        "entry_max": int(entry_max),
    }


def veer_program_entries_probe_defines(top_module: str) -> list[str]:
    return [f"-DPROGRAM_ENTRIES_ARRAY={top_module}__DOT__dut__DOT__gpu_cov_program_entries"]
