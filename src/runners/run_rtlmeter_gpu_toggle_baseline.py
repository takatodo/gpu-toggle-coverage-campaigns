#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
REPO_SCRIPTS = ROOT_DIR / "src/scripts"
RTLMETER_ROOT = ROOT_DIR / "third_party/rtlmeter"
RTLMETER_SRC = RTLMETER_ROOT / "src"
RTLMETER_VENV = ROOT_DIR / "rtlmeter/venv"
RTLMETER_BIN = RTLMETER_ROOT / "rtlmeter"
DEFAULT_BENCH = ROOT_DIR / "third_party/verilator/bin/verilator_sim_accel_bench"
DEFAULT_VERILATOR = ROOT_DIR / "third_party/verilator/bin/verilator"
DEFAULT_PRELOAD_MATERIALIZE = ROOT_DIR / "third_party/verilator/bin/verilator_sim_accel_materialize_preload"
DEFAULT_COMPILE_CACHE = Path("/tmp/verilator-sim-accel-compile-cache")
PREGPU_VALIDATION_TIMEOUT_S = 90

for extra_path in (SCRIPT_DIR, REPO_SCRIPTS, RTLMETER_SRC):
    extra_text = str(extra_path)
    if extra_text not in sys.path:
        sys.path.insert(0, extra_text)

for site_packages in sorted((RTLMETER_VENV / "lib").glob("python*/site-packages")):
    site_text = str(site_packages)
    if site_text not in sys.path:
        sys.path.insert(0, site_text)

os.environ.setdefault("RTLMETER_ROOT", str(RTLMETER_ROOT))

from rtlmeter.descriptors import CompileDescriptor, ExecuteDescriptor  # noqa: E402
from opentitan_coverage_regions import load_region_manifest, summarize_regions  # noqa: E402
from opentitan_tlul_baseline_common import estimate_sync_sequential_steps  # noqa: E402
from opentitan_tlul_slice_contracts import (  # noqa: E402
    REQUIRED_OUTPUTS_FLAT,
    validate_slice_contract,
)
from program_hex_tools import load_program_hex, patch_iterations, store_program_hex  # noqa: E402
from rtlmeter_sim_accel_adapter import (  # noqa: E402
    build_collector_summary,
    extract_sim_accel_output_slot_values,
    parse_bench_log,
    populate_collector_coverage,
    sha256_hex_bytes,
)
from gpu_backend_selection import (  # noqa: E402
    ensure_gpu_execution_backend_supported,
    resolve_gpu_execution_backend,
)
from run_opentitan_tlul_slice_gpu_baseline import (  # noqa: E402
    DRIVER_DEFAULTS,
    FOCUSED_METRIC_OUTPUTS,
    FOCUSED_WAVE_OUTPUTS,
    REAL_TOGGLE_SUBSET_OUTPUTS,
    TRACE_PROGRESS_OUTPUTS,
    TRAFFIC_COUNTER_OUTPUTS,
    _build_focused_wave_artifact,
    _build_observability_summary,
    _constant_folded_outputs,
    _selected_output_names_for_summary_mode,
    _write_init_file,
    _write_output_filter_file,
)

VEER_PROGRAM_HEX_TARGET_CONFIGS = {
    "VeeR-EL2": RTLMETER_ROOT / "designs" / "VeeR-EL2" / "tests" / "veer_el2_program_hex_target_config.json",
    "VeeR-EH1": RTLMETER_ROOT / "designs" / "VeeR-EH1" / "tests" / "veer_eh1_program_hex_target_config.json",
    "VeeR-EH2": RTLMETER_ROOT / "designs" / "VeeR-EH2" / "tests" / "veer_eh2_program_hex_target_config.json",
}
VEER_GPU_COV_PROGRAM_ENTRY_MAX = {
    "VeeR-EL2": 16384,
    "VeeR-EH1": 16384,
    "VeeR-EH2": 16384,
}
CASE_PAT_ITERATION_TARGET_CONFIGS = {
    "XuanTie-E902": {
        "file_name": "case.pat",
        "word_index": 0x8000,
        "top_module": "xuantie_e902_gpu_cov_tb",
        "target_path": "xuantie_e902_gpu_cov_tb.dut.mem_inst_temp",
        "word_bits": 32,
        "depth": 65536,
        "base_addr": 0,
        "address_unit_bytes": 4,
        "endianness": "little",
    },
    "XuanTie-E906": {
        "file_name": "case.pat",
        "word_index": 0x8000,
        "top_module": "xuantie_e906_gpu_cov_tb",
        "target_path": "xuantie_e906_gpu_cov_tb.dut.mem_inst_temp",
        "word_bits": 32,
        "depth": 65536,
        "base_addr": 0,
        "address_unit_bytes": 4,
        "endianness": "little",
    },
}
XUANTIE_C9XX_PAT_TARGET_CONFIG = {
    "XuanTie-C906": {
        "top_module": "xuantie_c906_gpu_cov_tb",
        "inst_target_path": "xuantie_c906_gpu_cov_tb.mem_inst_temp",
        "data_target_path": "xuantie_c906_gpu_cov_tb.mem_data_temp",
        "word_bits": 32,
        "depth": 65536,
        "base_addr": 0,
        "address_unit_bytes": 4,
        "endianness": "little",
    },
    "XuanTie-C910": {
        "top_module": "xuantie_c910_gpu_cov_tb",
        "inst_target_path": "xuantie_c910_gpu_cov_tb.mem_inst_temp",
        "data_target_path": "xuantie_c910_gpu_cov_tb.mem_data_temp",
        "word_bits": 32,
        "depth": 65536,
        "base_addr": 0,
        "address_unit_bytes": 4,
        "endianness": "little",
    },
}
BLACKPARROT_INIT_MEM_TARGET_CONFIG = {
    "BlackParrot": {
        "top_module": "blackparrot_gpu_cov_tb",
        "target_path": "blackparrot_gpu_cov_tb.gpu_cov_program_words",
        "word_bits": 64,
        "depth": 32768,
        "base_addr": 0,
        "address_unit_bytes": 8,
        "endianness": "little",
        "iterations_byte_offset": 0x20000,
    }
}
OPENPITON_MEM_BIN_TARGET_CONFIG = {
    "OpenPiton": {
        "top_module": "openpiton_gpu_cov_tb",
        "target_path": "openpiton_gpu_cov_tb.dut.system.chipset.chipset_impl.fake_mem_ctrl.gpu_cov_visible_mem",
        "word_bits": 64,
        "depth": 2048,
        # mem.bin is byte-addressed from file offset 0; fake_mem_ctrl subtracts
        # 0x8000_0000 internally before indexing gpu_cov_visible_mem.
        "base_addr": 0,
        "address_unit_bytes": 8,
        "endianness": "little",
        "ncores_byte_offset": 0x680,
        "default_ncores": 1,
        "iterations_byte_offset": 0x688,
    }
}
XIANGSHAN_SIM_ACCEL_DIFFTEST_MEM1P_TEMPLATE = SCRIPT_DIR / "xiangshan_sim_accel_difftest_mem1p.sv"
XIANGSHAN_SIM_ACCEL_FLASH_HELPER_TEMPLATE = SCRIPT_DIR / "xiangshan_sim_accel_flash_helper.v"
XIANGSHAN_PROGRAM_BIN_TARGET_CONFIG = {
    "XiangShan": {
        "top_module": "xiangshan_gpu_cov_tb",
        "target_path": "xiangshan_gpu_cov_tb.dut.top.memory.ram.rdata_mem.ram",
        "word_bits": 64,
        "depth": 131072,
        "base_addr": 0,
        "address_unit_bytes": 8,
        "endianness": "little",
        "iterations_byte_offset": 0x200,
    }
}


def _sha256_path(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _replace_with_symlink(dst: Path, src: Path) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    try:
        dst.symlink_to(src)
    except OSError:
        shutil.copy2(src, dst)


def _stage_local_editable_copy(path: Path) -> Path:
    if path.is_symlink():
        src = path.resolve()
        path.unlink()
        shutil.copy2(src, path)
    return path


def _runtime_preload_cache_dir(base: Path) -> Path:
    return base / "runtime-preload-cache"


def _write_json(path: Path, payload: dict[str, Any], *, compact: bool = False) -> None:
    if compact:
        text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    else:
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _decode_debug_value(raw_value: str) -> int | str:
    text = str(raw_value).strip()
    if text.startswith(("0x", "0X")):
        try:
            return int(text, 16)
        except ValueError:
            return text
    if text.isdigit():
        try:
            return int(text, 10)
        except ValueError:
            return text
    return text


def _extract_debug_keyvals(line: str) -> dict[str, int | str]:
    fields: dict[str, int | str] = {}
    for key, raw_value in re.findall(r"([A-Za-z0-9_]+)=([^\s]+)", line):
        fields[key] = _decode_debug_value(raw_value)
    return fields


def _summarize_gpu_cov_debug(stdout_text: str) -> dict[str, Any]:
    lines = stdout_text.splitlines()
    flag_names = (
        "program_loaded",
        "rst_l",
        "porst_l",
        "halt_req",
        "halt_done",
        "halt_status",
        "halt_ack",
        "run_req",
        "run_done",
        "run_ack",
        "if_req",
        "if_rsp",
        "lsu_req",
        "lsu_rsp",
        "trace",
        "wb",
        "mailbox",
        "core_rst_l",
        "dbg_core_rst_l",
    )
    seen_flags = {f"{name}_seen": False for name in flag_names}
    status_count = 0
    bus_count = 0
    heartbeat_count = 0
    last_status_line = ""
    last_bus_line = ""
    last_heartbeat_line = ""
    last_status_fields: dict[str, int | str] = {}
    last_bus_fields: dict[str, int | str] = {}
    last_heartbeat_fields: dict[str, int | str] = {}
    first_ifu_req_line = ""
    first_ifu_rsp_line = ""
    for line in lines:
        if "[gpu_cov_dbg][status]" in line:
            status_count += 1
            last_status_line = line
            last_status_fields = _extract_debug_keyvals(line)
        elif "[gpu_cov_dbg][bus]" in line:
            bus_count += 1
            last_bus_line = line
            last_bus_fields = _extract_debug_keyvals(line)
        elif "[gpu_cov_dbg][heartbeat]" in line:
            heartbeat_count += 1
            last_heartbeat_line = line
            last_heartbeat_fields = _extract_debug_keyvals(line)
        elif "[gpu_cov_dbg][first_ifu_req]" in line and not first_ifu_req_line:
            first_ifu_req_line = line
        elif "[gpu_cov_dbg][first_ifu_rsp]" in line and not first_ifu_rsp_line:
            first_ifu_rsp_line = line
        for name in flag_names:
            if f"{name}=1" in line:
                seen_flags[f"{name}_seen"] = True

    activity_score = sum(
        1
        for key in (
            "if_req_seen",
            "if_rsp_seen",
            "lsu_req_seen",
            "lsu_rsp_seen",
            "trace_seen",
            "wb_seen",
            "mailbox_seen",
        )
        if seen_flags[key]
    )
    if activity_score > 0:
        likely_dead_reason = "activity_seen"
    elif not seen_flags["program_loaded_seen"]:
        likely_dead_reason = "program_not_loaded"
    elif not seen_flags["rst_l_seen"]:
        likely_dead_reason = "reset_not_released"
    elif not seen_flags["core_rst_l_seen"]:
        likely_dead_reason = "core_reset_held"
    elif not (seen_flags["if_req_seen"] or seen_flags["if_rsp_seen"]):
        likely_dead_reason = "no_fetch_activity"
    elif not (seen_flags["trace_seen"] or seen_flags["wb_seen"] or seen_flags["lsu_req_seen"]):
        likely_dead_reason = "fetch_without_retire_or_lsu"

    return {
        "status_line_count": status_count,
        "bus_line_count": bus_count,
        "heartbeat_line_count": heartbeat_count,
        "last_status_line": last_status_line,
        "last_status_fields": last_status_fields,
        "last_bus_line": last_bus_line,
        "last_bus_fields": last_bus_fields,
        "last_heartbeat_line": last_heartbeat_line,
        "last_heartbeat_fields": last_heartbeat_fields,
        "first_ifu_req_line": first_ifu_req_line,
        "first_ifu_rsp_line": first_ifu_rsp_line,
        "activity_score": activity_score,
        "likely_dead_reason": likely_dead_reason,
        **seen_flags,
    }


def _run_text_command_with_timeout(
    *,
    cmd: list[str],
    cwd: Path,
    timeout_s: int,
) -> tuple[subprocess.CompletedProcess[str], bool]:
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout_text, stderr_text = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout_text, stderr_text = proc.communicate()
    completed = subprocess.CompletedProcess(
        cmd,
        proc.returncode if proc.returncode is not None else 124,
        stdout_text,
        stderr_text,
    )
    return completed, timed_out


def _load_driver_from_args(ns: argparse.Namespace) -> dict[str, Any]:
    driver = dict(DRIVER_DEFAULTS)
    for key in DRIVER_DEFAULTS:
        value = getattr(ns, key, None)
        if value is not None:
            driver[key] = value
    return driver


def _summary_selected_output_names(
    summary_mode: str,
    *,
    include_focused_wave_prefilter: bool = False,
) -> set[str]:
    selected = _selected_output_names_for_summary_mode(summary_mode)
    if include_focused_wave_prefilter and summary_mode == "prefilter":
        selected.update(FOCUSED_WAVE_OUTPUTS)
        selected.update(FOCUSED_METRIC_OUTPUTS)
    return selected


def _symlink_by_basename(paths: list[str], dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    used_names: dict[str, Path] = {}
    for raw_path in paths:
        src = Path(raw_path).expanduser().resolve()
        if not src.exists():
            raise SystemExit(f"Missing descriptor file: {src}")
        basename = src.name
        previous = used_names.get(basename)
        if previous is not None and previous != src:
            raise SystemExit(
                f"Basename collision while staging descriptor files: {basename}\n"
                f"  {previous}\n"
                f"  {src}"
            )
        used_names[basename] = src
        dst = dest_dir / basename
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        dst.symlink_to(src)
        staged.append(dst)
    return staged


def _find_coverage_tb(source_files: list[str], top_module: str) -> Path:
    preferred = [Path(path) for path in source_files if Path(path).stem == top_module]
    if preferred:
        return preferred[0].resolve()
    candidates = [Path(path) for path in source_files if path.endswith("_gpu_cov_tb.sv")]
    if len(candidates) == 1:
        return candidates[0].resolve()
    raise SystemExit(
        f"Unable to identify gpu coverage TB for top module {top_module}: {candidates}"
    )


def _find_coverage_manifest(execute_files: list[str]) -> Path:
    candidates = [
        Path(path).resolve()
        for path in execute_files
        if path.endswith("_coverage_regions.json")
    ]
    if len(candidates) == 1:
        return candidates[0]
    raise SystemExit(
        f"Unable to identify coverage manifest from execute files: {execute_files}"
    )


def _stage_filelist(
    build_dir: Path,
    compile_desc: CompileDescriptor,
) -> tuple[Path, Path, Path, Path, Path]:
    source_dir = build_dir / "verilogSourceFiles"
    include_dir = build_dir / "verilogIncludeFiles"
    cpp_source_dir = build_dir / "cppSourceFiles"
    cpp_include_dir = build_dir / "cppIncludeFiles"
    _symlink_by_basename(compile_desc.verilogSourceFiles, source_dir)
    _symlink_by_basename(compile_desc.verilogIncludeFiles, include_dir)
    _symlink_by_basename(compile_desc.cppSourceFiles, cpp_source_dir)
    _symlink_by_basename(compile_desc.cppIncludeFiles, cpp_include_dir)
    filelist_path = build_dir / "filelist"
    filelist_lines = [f"verilogSourceFiles/{Path(path).name}" for path in compile_desc.verilogSourceFiles]
    filelist_lines.extend(f"cppSourceFiles/{Path(path).name}" for path in compile_desc.cppSourceFiles)
    filelist_path.write_text("\n".join(filelist_lines) + "\n", encoding="utf-8")
    return source_dir, include_dir, cpp_source_dir, cpp_include_dir, filelist_path


def _stage_execute_files(build_dir: Path, execute_desc: ExecuteDescriptor) -> list[Path]:
    staged: list[Path] = []
    for raw_path in execute_desc.files:
        src = Path(raw_path).expanduser().resolve()
        if not src.exists():
            raise SystemExit(f"Missing execute file: {src}")
        dst = build_dir / src.name
        if dst.exists() or dst.is_symlink():
            dst.unlink()
        dst.symlink_to(src)
        staged.append(dst)
    return staged


def _parse_execute_args(execute_desc: ExecuteDescriptor) -> dict[str, Any]:
    iterations: int | None = None
    init_mem: str | None = None
    ncores: int | None = None
    sim_args: list[str] = []
    unsupported: list[str] = []
    for raw_arg in execute_desc.args:
        arg = str(raw_arg).strip()
        if not arg:
            continue
        if arg.startswith("+iterations="):
            try:
                iterations = int(arg.split("=", 1)[1], 0)
            except ValueError as exc:
                raise SystemExit(f"Invalid +iterations arg in {execute_desc.case}: {arg}") from exc
            continue
        if arg.startswith("+init_mem="):
            init_mem = arg.split("=", 1)[1].strip() or None
            continue
        if arg.startswith("+nCores="):
            try:
                ncores = int(arg.split("=", 1)[1], 0)
            except ValueError as exc:
                raise SystemExit(f"Invalid +nCores arg in {execute_desc.case}: {arg}") from exc
            sim_args.append(arg)
            continue
        if arg.startswith("+"):
            sim_args.append(arg)
            continue
        unsupported.append(arg)
    if unsupported:
        raise SystemExit(
            "Unsupported execute args for run_rtlmeter_gpu_toggle_baseline.py: "
            + " ".join(unsupported)
        )
    return {
        "iterations": iterations,
        "init_mem": init_mem,
        "nCores": ncores,
        "sim_args": sim_args,
    }


def _load_json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Expected JSON object in {path}")
    return payload


def _load_readmemh_word_image(path: Path) -> dict[int, int]:
    memory: dict[int, int] = {}
    current_addr = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        for token in line.split():
            if token.startswith("@"):
                current_addr = int(token[1:], 16)
                continue
            value = int(token, 16)
            if value < 0 or value > 0xFFFFFFFF:
                raise ValueError(f"readmemh token out of 32-bit range in {path}: {token}")
            memory[current_addr] = value
            current_addr += 1
    if not memory:
        raise ValueError(f"No readmemh words found in {path}")
    return memory


def _load_readmemh_byte_image(path: Path) -> dict[int, int]:
    memory: dict[int, int] = {}
    current_addr = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        for token in line.split():
            if token.startswith("@"):
                current_addr = int(token[1:], 16)
                continue
            value = int(token, 16)
            if value < 0 or value > 0xFF:
                raise ValueError(f"readmemh byte token out of 8-bit range in {path}: {token}")
            memory[current_addr] = value
            current_addr += 1
    if not memory:
        raise ValueError(f"No readmemh bytes found in {path}")
    return memory


def _store_readmemh_word_image(path: Path, memory: dict[int, int], *, words_per_line: int = 4) -> None:
    if not memory:
        raise ValueError("Cannot write empty readmemh image")
    addrs = sorted(memory.keys())
    lines: list[str] = []
    run_start = addrs[0]
    run_words = [memory[run_start]]
    last_addr = run_start

    def flush(start_addr: int, words: list[int]) -> None:
        for idx in range(0, len(words), words_per_line):
            chunk = words[idx: idx + words_per_line]
            word_text = "  ".join(f"{word:08X}" for word in chunk)
            lines.append(f"@{start_addr + idx:08X}  {word_text}")

    for addr in addrs[1:]:
        if addr == last_addr + 1:
            run_words.append(memory[addr])
        else:
            flush(run_start, run_words)
            run_start = addr
            run_words = [memory[addr]]
        last_addr = addr
    flush(run_start, run_words)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _encode_iterations_word_little_endian(iterations: int) -> int:
    if iterations < 0 or iterations > 0xFFFFFFFF:
        raise ValueError("iterations must fit in 32 bits")
    return int.from_bytes(int(iterations).to_bytes(4, "little"), "big")


def _readmemh_word_image_to_byte_memory(memory: dict[int, int]) -> dict[int, int]:
    byte_memory: dict[int, int] = {}
    for word_index, word in memory.items():
        base_addr = int(word_index) * 4
        for byte_offset, byte_value in enumerate(int(word).to_bytes(4, byteorder="little")):
            byte_memory[base_addr + byte_offset] = int(byte_value)
    return byte_memory


def _tail_text(path: Path, *, max_lines: int = 40) -> str:
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-max_lines:])


def _run_standard_pregpu_validation(
    *,
    design: str,
    test: str,
    build_dir: Path,
    rebuild: bool,
) -> dict[str, Any]:
    work_root = build_dir / "_pregpu_standard"
    if rebuild and work_root.exists():
        shutil.rmtree(work_root)
    cmd = [
        str(RTLMETER_BIN),
        "run",
        "--cases",
        f"{design}:default:{test}",
        "--workRoot",
        str(work_root),
        "--nCompile",
        "1",
        "--nExecute",
        "1",
        "--verbose",
    ]
    proc, timed_out = _run_text_command_with_timeout(
        cmd=cmd,
        cwd=RTLMETER_ROOT,
        timeout_s=PREGPU_VALIDATION_TIMEOUT_S,
    )
    stdout_log = work_root / design / "default" / "execute-0" / test / "_execute" / "stdout.log"
    stdout_text = stdout_log.read_text(encoding="utf-8", errors="replace") if stdout_log.exists() else ""
    return {
        "enabled": True,
        "case": f"{design}:default:{test}",
        "work_root": str(work_root),
        "command": cmd,
        "returncode": proc.returncode,
        "timed_out": timed_out,
        "stdout_log": str(stdout_log) if stdout_log.exists() else "",
        "stdout_tail": _tail_text(stdout_log) if stdout_log.exists() else "\n".join(proc.stdout.splitlines()[-40:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-40:]),
        "test_passed_token": "TEST_PASSED" in stdout_text,
        "hello_token": "Hello World" in stdout_text,
        "status": "pass" if "TEST_PASSED" in stdout_text else "fail",
    }


def _run_gpu_cov_pregpu_validation(
    *,
    case: str,
    design: str,
    config: str,
    test: str,
    build_dir: Path,
    rebuild: bool,
) -> dict[str, Any]:
    work_root = build_dir / "_pregpu_gpu_cov"
    if rebuild and work_root.exists():
        shutil.rmtree(work_root)
    cmd = [
        str(RTLMETER_BIN),
        "run",
        "--cases",
        case,
        "--workRoot",
        str(work_root),
        "--nCompile",
        "1",
        "--nExecute",
        "1",
        "--executeArgs",
        "+iterations=1",
        "--executeArgs",
        "+gpu_cov_debug_log=1",
        "--timeout",
        "3",
        "--verbose",
    ]
    proc, timed_out = _run_text_command_with_timeout(
        cmd=cmd,
        cwd=RTLMETER_ROOT,
        timeout_s=PREGPU_VALIDATION_TIMEOUT_S,
    )
    stdout_log = work_root / design / config / "execute-0" / test / "_execute" / "stdout.log"
    stdout_text = stdout_log.read_text(encoding="utf-8", errors="replace") if stdout_log.exists() else ""
    debug_summary = _summarize_gpu_cov_debug(stdout_text)
    hello_token = "Hello World" in stdout_text
    test_passed_token = "TEST_PASSED" in stdout_text
    trace_like_token = any(
        [
            test_passed_token,
            hello_token,
            bool(debug_summary.get("trace_seen")),
            bool(debug_summary.get("wb_seen")),
            bool(debug_summary.get("lsu_req_seen")),
            bool(debug_summary.get("lsu_rsp_seen")),
        ]
    )
    return {
        "enabled": True,
        "case": case,
        "work_root": str(work_root),
        "command": cmd,
        "returncode": proc.returncode,
        "timed_out": timed_out,
        "stdout_log": str(stdout_log) if stdout_log.exists() else "",
        "stdout_tail": _tail_text(stdout_log) if stdout_log.exists() else "\n".join(proc.stdout.splitlines()[-40:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-40:]),
        "test_passed_token": test_passed_token,
        "hello_token": hello_token,
        "trace_like_token": trace_like_token,
        "debug_summary": debug_summary,
        "status": "pass" if trace_like_token else "fail",
    }


def _analyze_program_image(
    *,
    design: str,
    top_module: str,
    execute_runtime_inputs: dict[str, Any],
) -> dict[str, Any]:
    program_hex_text = str(
        execute_runtime_inputs.get("program_hex")
        or execute_runtime_inputs.get("program_hex_source")
        or ""
    ).strip()
    if not program_hex_text:
        return {"status": "not_applicable", "reason": "no_program_hex"}
    program_hex_path = Path(program_hex_text).expanduser().resolve()
    if not program_hex_path.exists():
        return {
            "status": "missing",
            "reason": "program_hex_missing",
            "program_hex": str(program_hex_path),
        }
    memory = load_program_hex(program_hex_path)
    addrs = sorted(memory)
    summary: dict[str, Any] = {
        "status": "ok",
        "program_hex": str(program_hex_path),
        "entry_count": len(addrs),
        "min_addr": int(addrs[0]),
        "max_addr": int(addrs[-1]),
        "sample_addrs": [int(addr) for addr in addrs[:8]],
    }
    config_path = VEER_PROGRAM_HEX_TARGET_CONFIGS.get(design)
    if config_path is None or not config_path.exists():
        return summary
    config = _load_json_file(config_path)
    iccm_lo = int(config["iccm_region_start_addr"])
    iccm_hi = int(config["iccm_region_end_addr"])
    dccm_lo = int(config["dccm_region_start_addr"])
    dccm_hi = int(config["dccm_region_end_addr"])
    iccm_hits = sum(1 for addr in addrs if iccm_lo <= addr <= iccm_hi)
    dccm_hits = sum(1 for addr in addrs if dccm_lo <= addr <= dccm_hi)
    external_hits = len(addrs) - iccm_hits - dccm_hits
    summary.update(
        {
            "iccm_region_start_addr": iccm_lo,
            "iccm_region_end_addr": iccm_hi,
            "dccm_region_start_addr": dccm_lo,
            "dccm_region_end_addr": dccm_hi,
            "iccm_overlap_count": iccm_hits,
            "dccm_overlap_count": dccm_hits,
            "external_overlap_count": external_hits,
            "external_only": iccm_hits == 0 and dccm_hits == 0,
        }
    )
    if top_module in {"veer_el2_gpu_cov_tb", "veer_eh1_gpu_cov_tb", "veer_eh2_gpu_cov_tb"} and summary["external_only"]:
        summary["status"] = "needs_review"
        summary["reason"] = "gpu_cov_sparse_entries_external_only"
    return summary


def _build_pregpu_gate(
    *,
    ns: argparse.Namespace,
    design: str,
    test: str,
    top_module: str,
    execute_runtime_inputs: dict[str, Any],
    build_dir: Path,
) -> dict[str, Any]:
    mode = str(ns.pre_gpu_gate)
    if mode == "auto":
        enabled = bool(design in VEER_PROGRAM_HEX_TARGET_CONFIGS and top_module.endswith("_gpu_cov_tb"))
    else:
        enabled = mode == "always"
    gpu_cov_enabled = bool(enabled and top_module.endswith("_gpu_cov_tb"))
    gate: dict[str, Any] = {
        "mode": mode,
        "enabled": enabled,
        "standard_precheck": {"enabled": False},
        "gpu_cov_precheck": {"enabled": False},
        "program_image": _analyze_program_image(
            design=design,
            top_module=top_module,
            execute_runtime_inputs=execute_runtime_inputs,
        ),
    }
    if enabled:
        gate["standard_precheck"] = _run_standard_pregpu_validation(
            design=design,
            test=test,
            build_dir=build_dir,
            rebuild=bool(ns.rebuild),
        )
    if gpu_cov_enabled:
        gate["gpu_cov_precheck"] = _run_gpu_cov_pregpu_validation(
            case=f"{design}:gpu_cov:{test}",
            design=design,
            config="gpu_cov",
            test=test,
            build_dir=build_dir,
            rebuild=bool(ns.rebuild),
        )
    gate["status"] = (
        "pass"
        if (
            not enabled
            or (
                gate["standard_precheck"].get("status") == "pass"
                and (not gpu_cov_enabled or gate["gpu_cov_precheck"].get("status") == "pass")
            )
        )
        else "fail"
    )
    return gate


def _materialize_veer_program_hex_target(
    *,
    build_dir: Path,
    top_module: str,
    design: str,
    program_hex_path: Path,
    iterations: int | None,
) -> dict[str, Any]:
    config_path = VEER_PROGRAM_HEX_TARGET_CONFIGS.get(design)
    if config_path is None or not config_path.exists():
        raise SystemExit(f"Missing VeeR program hex target config for {design}")
    config = _load_json_file(config_path)
    preload_targets_path = build_dir / f"{top_module}.sim_accel.kernel.cu.preload_targets.json"

    materialized_program_hex = program_hex_path
    if iterations is not None:
        memory = load_program_hex(program_hex_path)
        patched = patch_iterations(
            memory,
            int(iterations),
            int(config.get("iteration_base_addr", 0x10000000)),
        )
        materialized_program_hex = build_dir / "program.hex"
        if materialized_program_hex.exists() or materialized_program_hex.is_symlink():
            materialized_program_hex.unlink()
        store_program_hex(materialized_program_hex, patched)

    descriptor_path = build_dir / f"{top_module}.program_hex.target.json"
    descriptor_payload = {
        "kind": "veer-el2-program-hex-v1",
        "name": f"{top_module}_program_hex",
        "description": f"{design} hidden preload target",
        "preload_targets_json": str(preload_targets_path),
        "dccm_target_prefix": str(config["dccm_target_prefix"]),
        "dccm_target_suffixes": [str(item) for item in config.get("dccm_target_suffixes", [])],
        "iccm_target_prefix": str(config["iccm_target_prefix"]),
        "iccm_target_suffixes": [str(item) for item in config.get("iccm_target_suffixes", [])],
        "dccm_region_start_addr": int(config["dccm_region_start_addr"]),
        "dccm_region_end_addr": int(config["dccm_region_end_addr"]),
        "iccm_region_start_addr": int(config["iccm_region_start_addr"]),
        "iccm_region_end_addr": int(config["iccm_region_end_addr"]),
        "dccm_sentinel_start_addr": int(config.get("dccm_sentinel_start_addr", 0xFFFFFFF8)),
        "dccm_sentinel_end_addr": int(config.get("dccm_sentinel_end_addr", 0xFFFFFFFC)),
        "iccm_sentinel_start_addr": int(config.get("iccm_sentinel_start_addr", 0xFFFFFFF0)),
        "iccm_sentinel_end_addr": int(config.get("iccm_sentinel_end_addr", 0xFFFFFFF4)),
    }
    _write_json(descriptor_path, descriptor_payload)
    return {
        "program_hex": str(materialized_program_hex.resolve()),
        "program_hex_iterations": iterations,
        "materialized_program_hex": str(materialized_program_hex.resolve())
        if materialized_program_hex != program_hex_path
        else "",
        "program_hex_target": str(descriptor_path.resolve()),
        "program_hex_target_config": str(config_path.resolve()),
        "program_hex_hidden_preload": True,
    }


def _materialize_veer_gpu_cov_sparse_program_entries(
    *,
    build_dir: Path,
    top_module: str,
    design: str,
    program_hex_path: Path,
    iterations: int | None,
) -> dict[str, Any]:
    memory = load_program_hex(program_hex_path)
    if iterations is not None:
        memory = patch_iterations(memory, int(iterations), 0x10000000)
    entries = sorted(memory.items())
    entry_max = int(VEER_GPU_COV_PROGRAM_ENTRY_MAX.get(design, 0))
    if entry_max <= 0:
        raise SystemExit(f"Missing gpu_cov program entry limit for {design}")
    if len(entries) > entry_max - 1:
        raise SystemExit(
            f"{design} gpu_cov sparse program image exceeds entry capacity: "
            f"{len(entries)} > {entry_max - 1}"
        )

    image_path = build_dir / "program_entries.bin"
    payload = bytearray()
    # gpu_cov_program_entries[0] stores the sparse-entry count in its low 32 bits.
    payload.extend(int(len(entries) & 0xFFFF_FFFF).to_bytes(8, byteorder="little", signed=False))
    for addr, data in entries:
        word = ((int(data) & 0xFF) << 32) | (int(addr) & 0xFFFF_FFFF)
        payload.extend(int(word).to_bytes(8, byteorder="little", signed=False))
    image_path.write_bytes(bytes(payload))

    descriptor_path = build_dir / f"{top_module}.program_entries.target.json"
    descriptor_payload = {
        "kind": "memory-array-preload-v1",
        "name": f"{top_module}_gpu_cov_program_entries",
        "description": f"{design} gpu_cov sparse program entries",
        "target_path": f"{top_module}.dut.gpu_cov_program_entries",
        "word_bits": 64,
        "depth": len(entries) + 1,
        "base_addr": 0,
        "address_unit_bytes": 8,
        "endianness": "little",
    }
    _write_json(descriptor_path, descriptor_payload)
    return {
        "program_hex": "",
        "program_hex_source": str(program_hex_path.resolve()),
        "program_hex_iterations": iterations,
        "materialized_program_hex": "",
        "program_hex_target": "",
        "program_hex_target_config": "",
        "program_hex_hidden_preload": False,
        "memory_image": str(image_path.resolve()),
        "memory_image_target": str(descriptor_path.resolve()),
        "memory_image_format": "bin",
        "memory_image_sparse_program_entries": True,
        "memory_image_entry_count": len(entries),
        "extra_init_lines": [],
    }


def _materialize_case_pat_iteration_target(
    *,
    build_dir: Path,
    top_module: str,
    design: str,
    case_pat_path: Path,
    iterations: int,
) -> dict[str, Any]:
    config = CASE_PAT_ITERATION_TARGET_CONFIGS.get(design)
    if config is None:
        raise SystemExit(f"Missing case.pat iteration target config for {design}")
    configured_top = str(config.get("top_module") or "").strip()
    if configured_top and configured_top != top_module:
        raise SystemExit(f"Missing case.pat target config for {design}:{top_module}")
    memory = _load_readmemh_word_image(case_pat_path)
    patched = dict(memory)
    patched[int(config["word_index"])] = _encode_iterations_word_little_endian(int(iterations))
    materialized_case_pat = build_dir / str(config["file_name"])
    if materialized_case_pat.exists() or materialized_case_pat.is_symlink():
        materialized_case_pat.unlink()
    _store_readmemh_word_image(materialized_case_pat, patched)
    materialized_program_hex = build_dir / "case_pat_preload.hex"
    if materialized_program_hex.exists() or materialized_program_hex.is_symlink():
        materialized_program_hex.unlink()
    store_program_hex(materialized_program_hex, _readmemh_word_image_to_byte_memory(patched))
    descriptor_path = build_dir / f"{top_module}.mem_inst_temp.target.json"
    _write_json(
        descriptor_path,
        {
            "kind": "memory-array-preload-v1",
            "name": f"{top_module}_mem_inst_temp",
            "description": f"{design} staged case.pat preload target",
            "target_path": str(config["target_path"]),
            "word_bits": int(config["word_bits"]),
            "depth": int(config["depth"]),
            "base_addr": int(config["base_addr"]),
            "address_unit_bytes": int(config["address_unit_bytes"]),
            "endianness": str(config["endianness"]),
        },
    )
    return {
        "program_hex": str(materialized_program_hex.resolve()),
        "program_hex_source": str(case_pat_path.resolve()),
        "program_hex_iterations": iterations,
        "materialized_program_hex": str(materialized_program_hex.resolve()),
        "program_hex_target": str(descriptor_path.resolve()),
        "program_hex_target_config": "",
        "program_hex_hidden_preload": False,
        "memory_image": "",
        "memory_image_target": "",
        "memory_image_format": "",
        "memory_image_sparse_program_entries": False,
        "memory_image_entry_count": 0,
        "case_pat": str(materialized_case_pat.resolve()),
        "case_pat_source": str(case_pat_path.resolve()),
        "case_pat_iterations": iterations,
        "case_pat_word_index": int(config["word_index"]),
        "materialized_case_pat": str(materialized_case_pat.resolve()),
        "extra_init_lines": [],
    }


def _materialize_xuantie_c906_pat_targets(
    *,
    build_dir: Path,
    top_module: str,
    design: str,
    inst_pat_path: Path,
    data_pat_path: Path,
    iterations: int | None,
) -> dict[str, Any]:
    config = XUANTIE_C9XX_PAT_TARGET_CONFIG.get(design)
    if config is None or str(config.get("top_module")) != top_module:
        raise SystemExit(f"Missing XuanTie C9xx inst/data target config for {design}:{top_module}")

    inst_words = _load_readmemh_word_image(inst_pat_path)
    data_words = _load_readmemh_word_image(data_pat_path)
    if iterations is not None:
        data_words[0] = _encode_iterations_word_little_endian(int(iterations))

    inst_hex_path = build_dir / "inst_preload.hex"
    data_hex_path = build_dir / "data_preload.hex"
    store_program_hex(inst_hex_path, _readmemh_word_image_to_byte_memory(inst_words))
    store_program_hex(data_hex_path, _readmemh_word_image_to_byte_memory(data_words))

    inst_desc_path = build_dir / f"{top_module}.mem_inst_temp.target.json"
    data_desc_path = build_dir / f"{top_module}.mem_data_temp.target.json"
    common_descriptor = {
        "kind": "memory-array-preload-v1",
        "word_bits": int(config["word_bits"]),
        "depth": int(config["depth"]),
        "base_addr": int(config["base_addr"]),
        "address_unit_bytes": int(config["address_unit_bytes"]),
        "endianness": str(config["endianness"]),
    }
    _write_json(
        inst_desc_path,
        {
            **common_descriptor,
            "name": f"{top_module}_mem_inst_temp",
            "description": f"{design} staged inst.pat preload target",
            "target_path": str(config["inst_target_path"]),
        },
    )
    _write_json(
        data_desc_path,
        {
            **common_descriptor,
            "name": f"{top_module}_mem_data_temp",
            "description": f"{design} staged data.pat preload target",
            "target_path": str(config["data_target_path"]),
        },
    )
    return {
        "program_hex": str(inst_hex_path.resolve()),
        "program_hex_source": str(inst_pat_path.resolve()),
        "program_hex_iterations": iterations,
        "materialized_program_hex": str(inst_hex_path.resolve()),
        "program_hex_target": str(inst_desc_path.resolve()),
        "program_hex_target_config": "",
        "program_hex_hidden_preload": False,
        "memory_image": str(data_hex_path.resolve()),
        "memory_image_target": str(data_desc_path.resolve()),
        "memory_image_format": "hex",
        "memory_image_sparse_program_entries": False,
        "memory_image_entry_count": len(data_words),
        "case_pat": "",
        "case_pat_source": "",
        "case_pat_iterations": iterations,
        "case_pat_word_index": None,
        "materialized_case_pat": "",
        "extra_init_lines": [],
    }


def _materialize_xiangshan_program_bin_target(
    *,
    build_dir: Path,
    top_module: str,
    design: str,
    program_bin_path: Path,
    iterations: int | None,
) -> dict[str, Any]:
    config = XIANGSHAN_PROGRAM_BIN_TARGET_CONFIG.get(design)
    if config is None or str(config.get("top_module")) != top_module:
        raise SystemExit(f"Missing XiangShan program.bin target config for {design}:{top_module}")
    image_path = build_dir / "program.bin"
    program_bytes = bytearray(program_bin_path.read_bytes())
    if iterations is not None:
        offset = int(config["iterations_byte_offset"])
        required = offset + 8
        if len(program_bytes) < required:
            program_bytes.extend(b"\x00" * (required - len(program_bytes)))
        program_bytes[offset:required] = int(iterations).to_bytes(8, byteorder="little", signed=False)
    image_path.write_bytes(bytes(program_bytes))

    descriptor_path = build_dir / f"{top_module}.program_bin.target.json"
    descriptor_payload = {
        "kind": "memory-array-preload-v1",
        "name": f"{top_module}_program_bin",
        "description": f"{design} sim-accel visible RAM preload target",
        "target_path": str(config["target_path"]),
        "word_bits": int(config["word_bits"]),
        "depth": int(config["depth"]),
        "base_addr": int(config["base_addr"]),
        "address_unit_bytes": int(config["address_unit_bytes"]),
        "endianness": str(config["endianness"]),
    }


def _materialize_openpiton_mem_bin_target(
    *,
    build_dir: Path,
    top_module: str,
    design: str,
    mem_bin_path: Path,
    iterations: int | None,
    ncores: int | None,
) -> dict[str, Any]:
    config = OPENPITON_MEM_BIN_TARGET_CONFIG.get(design)
    if config is None or str(config.get("top_module")) != top_module:
        raise SystemExit(f"Missing OpenPiton mem.bin target config for {design}:{top_module}")
    program_bytes = bytearray(mem_bin_path.read_bytes())
    ncores_value = int(ncores if ncores is not None else config["default_ncores"])
    ncores_offset = int(config["ncores_byte_offset"])
    required = ncores_offset + 8
    if len(program_bytes) < required:
        program_bytes.extend(b"\x00" * (required - len(program_bytes)))
    program_bytes[ncores_offset:required] = int(ncores_value).to_bytes(
        8, byteorder="little", signed=False
    )
    if iterations is not None:
        iterations_offset = int(config["iterations_byte_offset"])
        required = iterations_offset + 8
        if len(program_bytes) < required:
            program_bytes.extend(b"\x00" * (required - len(program_bytes)))
        program_bytes[iterations_offset:required] = int(iterations).to_bytes(
            8, byteorder="little", signed=False
        )

    word_count = (len(program_bytes) + 7) // 8
    if word_count > int(config["depth"]):
        raise SystemExit(
            f"{design} mem.bin image exceeds visible-memory capacity: "
            f"{word_count} > {int(config['depth'])}"
        )
    image_path = build_dir / "openpiton_mem.bin"
    image_path.write_bytes(bytes(program_bytes))

    descriptor_path = build_dir / f"{top_module}.openpiton_mem.target.json"
    descriptor_payload = {
        "kind": "memory-array-preload-v1",
        "name": f"{top_module}_openpiton_mem",
        "description": f"{design} visible fake_mem_ctrl preload target",
        "target_path": str(config["target_path"]),
        "word_bits": int(config["word_bits"]),
        "depth": int(config["depth"]),
        "base_addr": int(config["base_addr"]),
        "address_unit_bytes": int(config["address_unit_bytes"]),
        "endianness": str(config["endianness"]),
    }
    _write_json(descriptor_path, descriptor_payload)
    return {
        "program_hex": "",
        "program_hex_source": "",
        "program_hex_iterations": iterations,
        "materialized_program_hex": "",
        "program_hex_target": "",
        "program_hex_target_config": "",
        "program_hex_hidden_preload": False,
        "memory_image": str(image_path.resolve()),
        "memory_image_target": str(descriptor_path.resolve()),
        "memory_image_format": "bin",
        "memory_image_sparse_program_entries": False,
        "memory_image_entry_count": word_count,
        "case_pat": "",
        "case_pat_source": "",
        "case_pat_iterations": iterations,
        "case_pat_word_index": None,
        "materialized_case_pat": "",
        "extra_init_lines": [],
    }


def _materialize_blackparrot_init_mem_target(
    *,
    build_dir: Path,
    top_module: str,
    design: str,
    prog_mem_path: Path,
    iterations: int | None,
) -> dict[str, Any]:
    config = BLACKPARROT_INIT_MEM_TARGET_CONFIG.get(design)
    if config is None or str(config.get("top_module")) != top_module:
        raise SystemExit(f"Missing BlackParrot init_mem target config for {design}:{top_module}")
    memory = _load_readmemh_byte_image(prog_mem_path)
    if iterations is not None:
        offset = int(config["iterations_byte_offset"])
        iteration_bytes = int(iterations).to_bytes(4, byteorder="little", signed=False)
        for index, byte in enumerate(iteration_bytes):
            memory[offset + index] = int(byte)
    max_addr = max(memory)
    word_count = (int(max_addr) // 8) + 1
    if word_count > int(config["depth"]) - 1:
        raise SystemExit(
            f"{design} init_mem image exceeds entry capacity: "
            f"{word_count} > {int(config['depth']) - 1}"
        )
    image_path = build_dir / "blackparrot_prog_mem_entries.bin"
    payload = bytearray()
    payload.extend(int(word_count & 0xFFFF_FFFF).to_bytes(8, byteorder="little", signed=False))
    for word_index in range(word_count):
        word = 0
        base_addr = word_index * 8
        for byte_index in range(8):
            word |= (int(memory.get(base_addr + byte_index, 0)) & 0xFF) << (8 * byte_index)
        payload.extend(int(word).to_bytes(8, byteorder="little", signed=False))
    image_path.write_bytes(bytes(payload))

    descriptor_path = build_dir / f"{top_module}.init_mem.target.json"
    descriptor_payload = {
        "kind": "memory-array-preload-v1",
        "name": f"{top_module}_init_mem_entries",
        "description": f"{design} init_mem sparse preload words",
        "target_path": str(config["target_path"]),
        "word_bits": int(config["word_bits"]),
        "depth": int(config["depth"]),
        "base_addr": int(config["base_addr"]),
        "address_unit_bytes": int(config["address_unit_bytes"]),
        "endianness": str(config["endianness"]),
    }
    _write_json(descriptor_path, descriptor_payload)
    return {
        "program_hex": "",
        "program_hex_source": "",
        "program_hex_iterations": iterations,
        "materialized_program_hex": "",
        "program_hex_target": "",
        "program_hex_target_config": "",
        "program_hex_hidden_preload": False,
        "memory_image": str(image_path.resolve()),
        "memory_image_target": str(descriptor_path.resolve()),
        "memory_image_format": "bin",
        "memory_image_sparse_program_entries": False,
        "memory_image_entry_count": word_count,
        "case_pat": "",
        "case_pat_source": "",
        "case_pat_iterations": iterations,
        "case_pat_word_index": None,
        "materialized_case_pat": "",
        "extra_init_lines": [],
    }
    _write_json(descriptor_path, descriptor_payload)
    return {
        "program_hex": "",
        "program_hex_source": "",
        "program_hex_iterations": iterations,
        "materialized_program_hex": "",
        "program_hex_target": "",
        "program_hex_target_config": "",
        "program_hex_hidden_preload": False,
        "memory_image": str(image_path.resolve()),
        "memory_image_target": str(descriptor_path.resolve()),
        "memory_image_format": "bin",
        "memory_image_sparse_program_entries": False,
        "memory_image_entry_count": 0,
        "case_pat": "",
        "case_pat_source": "",
        "case_pat_iterations": iterations,
        "case_pat_word_index": None,
        "materialized_case_pat": "",
        "extra_init_lines": [],
    }


def _materialize_execute_runtime_inputs(
    *,
    build_dir: Path,
    top_module: str,
    design: str,
    staged_execute_files: list[Path],
    execute_arg_overrides: dict[str, Any],
) -> dict[str, Any]:
    program_hex_path = next((path for path in staged_execute_files if path.name == "program.hex"), None)
    program_bin_path = next((path for path in staged_execute_files if path.name == "program.bin"), None)
    mem_bin_path = next((path for path in staged_execute_files if path.name == "mem.bin"), None)
    case_pat_path = next((path for path in staged_execute_files if path.name == "case.pat"), None)
    inst_pat_path = next((path for path in staged_execute_files if path.name == "inst.pat"), None)
    data_pat_path = next((path for path in staged_execute_files if path.name == "data.pat"), None)
    init_mem_name = str(execute_arg_overrides.get("init_mem") or "").strip()
    init_mem_path = next(
        (
            path
            for path in staged_execute_files
            if path.name == init_mem_name
        ),
        None,
    ) if init_mem_name else None
    iterations = execute_arg_overrides.get("iterations")
    ncores = execute_arg_overrides.get("nCores")
    materialized: dict[str, Any] = {
        "program_hex": str(program_hex_path.resolve()) if program_hex_path and program_hex_path.exists() else "",
        "program_hex_source": str(program_hex_path.resolve()) if program_hex_path and program_hex_path.exists() else "",
        "program_hex_iterations": iterations,
        "materialized_program_hex": "",
        "program_hex_target": "",
        "program_hex_target_config": "",
        "program_hex_hidden_preload": False,
        "memory_image": "",
        "memory_image_target": "",
        "memory_image_format": "",
        "memory_image_sparse_program_entries": False,
        "memory_image_entry_count": 0,
        "case_pat": str(case_pat_path.resolve()) if case_pat_path and case_pat_path.exists() else "",
        "case_pat_source": str(case_pat_path.resolve()) if case_pat_path and case_pat_path.exists() else "",
        "case_pat_iterations": iterations,
        "case_pat_word_index": None,
        "materialized_case_pat": "",
        "extra_init_lines": [],
    }
    if design == "Caliptra":
        # Caliptra's stock caliptra_top_tb_services loads program/mailbox/ICCM/DCCM
        # images directly from the staged execute directory via $readmemh basename
        # lookups. Keep the file-driven contract and avoid forcing the generic
        # hidden-preload program.hex path on this family.
        materialized["program_hex"] = ""
        return materialized
    if (
        design in VEER_GPU_COV_PROGRAM_ENTRY_MAX
        and top_module in {"veer_el2_gpu_cov_tb", "veer_eh1_gpu_cov_tb", "veer_eh2_gpu_cov_tb"}
        and program_hex_path is not None
        and program_hex_path.exists()
    ):
        return _materialize_veer_gpu_cov_sparse_program_entries(
            build_dir=build_dir,
            top_module=top_module,
            design=design,
            program_hex_path=program_hex_path,
            iterations=iterations,
        )
    if program_hex_path is not None and program_hex_path.exists() and design in VEER_PROGRAM_HEX_TARGET_CONFIGS:
        return _materialize_veer_program_hex_target(
            build_dir=build_dir,
            top_module=top_module,
            design=design,
            program_hex_path=program_hex_path,
            iterations=iterations,
        )
    if (
        inst_pat_path is not None
        and inst_pat_path.exists()
        and data_pat_path is not None
        and data_pat_path.exists()
        and design in XUANTIE_C9XX_PAT_TARGET_CONFIG
    ):
        return _materialize_xuantie_c906_pat_targets(
            build_dir=build_dir,
            top_module=top_module,
            design=design,
            inst_pat_path=inst_pat_path,
            data_pat_path=data_pat_path,
            iterations=iterations,
        )
    if (
        iterations is not None
        and case_pat_path is not None
        and case_pat_path.exists()
        and design in CASE_PAT_ITERATION_TARGET_CONFIGS
    ):
        return _materialize_case_pat_iteration_target(
            build_dir=build_dir,
            top_module=top_module,
            design=design,
            case_pat_path=case_pat_path,
            iterations=int(iterations),
        )
    if program_bin_path is not None and program_bin_path.exists() and design in XIANGSHAN_PROGRAM_BIN_TARGET_CONFIG:
        return _materialize_xiangshan_program_bin_target(
            build_dir=build_dir,
            top_module=top_module,
            design=design,
            program_bin_path=program_bin_path,
            iterations=iterations,
        )
    if mem_bin_path is not None and mem_bin_path.exists() and design in OPENPITON_MEM_BIN_TARGET_CONFIG:
        return _materialize_openpiton_mem_bin_target(
            build_dir=build_dir,
            top_module=top_module,
            design=design,
            mem_bin_path=mem_bin_path,
            iterations=iterations,
            ncores=ncores,
        )
    if init_mem_name:
        if init_mem_path is None or not init_mem_path.exists():
            raise SystemExit(
                f"+init_mem requires staged execute file '{init_mem_name}' in {build_dir}"
            )
        if design in BLACKPARROT_INIT_MEM_TARGET_CONFIG:
            return _materialize_blackparrot_init_mem_target(
                build_dir=build_dir,
                top_module=top_module,
                design=design,
                prog_mem_path=init_mem_path,
                iterations=iterations,
            )
        raise SystemExit(
            f"+init_mem lowering is not implemented for {design}:{top_module}"
        )
    if iterations is None:
        return materialized
    if iterations == 1 and (program_hex_path is None or not program_hex_path.exists()):
        # Some RTLMeter tests use +iterations=1 only to make the default explicit.
        # Keep those workloads runnable even when there is no staged program.hex to patch.
        return materialized
    if program_hex_path is None or not program_hex_path.exists():
        raise SystemExit(
            f"+iterations requires staged program.hex in execute files: {build_dir}"
        )
    memory = load_program_hex(program_hex_path)
    patched = patch_iterations(memory, int(iterations))
    materialized_path = build_dir / "program.hex"
    if materialized_path.exists() or materialized_path.is_symlink():
        materialized_path.unlink()
    store_program_hex(materialized_path, patched)
    materialized["program_hex"] = str(materialized_path)
    materialized["program_hex_source"] = str(program_hex_path.resolve())
    materialized["materialized_program_hex"] = str(materialized_path)
    return materialized


def _apply_xiangshan_sim_accel_staged_contract_patch(
    *,
    build_dir: Path,
    compile_desc: CompileDescriptor,
) -> dict[str, Any]:
    if compile_desc.design != "XiangShan" or compile_desc.topModule != "xiangshan_gpu_cov_tb":
        return {"applied": False}

    simtop_path = build_dir / "verilogSourceFiles" / "SimTop.v"
    flash_helper_path = build_dir / "verilogSourceFiles" / "FlashHelper.v"
    if not simtop_path.exists() or not flash_helper_path.exists():
        return {
            "applied": False,
            "reason": "missing_staged_sources",
            "simtop_exists": simtop_path.exists(),
            "flash_helper_exists": flash_helper_path.exists(),
        }

    template_mem = XIANGSHAN_SIM_ACCEL_DIFFTEST_MEM1P_TEMPLATE.read_text(encoding="utf-8")
    template_flash = XIANGSHAN_SIM_ACCEL_FLASH_HELPER_TEMPLATE.read_text(encoding="utf-8")

    simtop_local = _stage_local_editable_copy(simtop_path)
    simtop_text = simtop_local.read_text(encoding="utf-8")
    module_start = simtop_text.find("module DifftestMem1P(")
    module_end_marker = "\nmodule AXI4RAM("
    module_end = simtop_text.find(module_end_marker, module_start)
    if module_start < 0 or module_end < 0:
        return {
            "applied": False,
            "reason": "difftest_mem1p_not_found",
            "simtop_path": str(simtop_local),
        }
    simtop_local.write_text(
        simtop_text[:module_start] + template_mem + "\n\n" + simtop_text[module_end + 1 :],
        encoding="utf-8",
    )

    flash_local = _stage_local_editable_copy(flash_helper_path)
    flash_local.write_text(template_flash, encoding="utf-8")
    return {
        "applied": True,
        "design": compile_desc.design,
        "top_module": compile_desc.topModule,
        "simtop_path": str(simtop_local),
        "flash_helper_path": str(flash_local),
        "difftest_mem_template": str(XIANGSHAN_SIM_ACCEL_DIFFTEST_MEM1P_TEMPLATE),
        "flash_helper_template": str(XIANGSHAN_SIM_ACCEL_FLASH_HELPER_TEMPLATE),
    }


def _apply_xuantie_c906_sim_accel_staged_contract_patch(
    *,
    build_dir: Path,
    compile_desc: CompileDescriptor,
) -> dict[str, Any]:
    if compile_desc.design != "XuanTie-C906" or compile_desc.topModule != "xuantie_c906_gpu_cov_tb":
        return {"applied": False}

    tb_path = build_dir / "verilogSourceFiles" / "tb.v"
    if not tb_path.exists():
        return {
            "applied": False,
            "reason": "missing_staged_tb",
            "tb_path": str(tb_path),
        }

    tb_local = _stage_local_editable_copy(tb_path)
    original = tb_local.read_text(encoding="utf-8")
    patched = original.replace("reg clk = 0;", "logic clk;")
    patched = patched.replace("reg jclk = 0;", "logic jclk;")
    patched = patched.replace(
        "reg rst_b = 1;\nreg jrst_b = 1;",
        "reg rst_b = 0;\nreg jrst_b = 0;",
    )
    wrapper_path = build_dir / "verilogSourceFiles" / f"{compile_desc.topModule}.sv"
    wrapper_local: Path | None = None
    wrapper_clock_bridge_removed = False
    wrapper_clock_bridge_already_absent = False
    if wrapper_path.exists():
        wrapper_local = _stage_local_editable_copy(wrapper_path)
        wrapper_original = wrapper_local.read_text(encoding="utf-8")
        old_wrapper_clock = """  always_comb begin
    dut.clk = simaccel_clk_proxy;
    dut.jclk = simaccel_clk_proxy;
  end
"""
        new_wrapper_clock = """  // sim-accel staged tb.v consumes the wrapper-level proxy directly.
"""
        if old_wrapper_clock in wrapper_original:
            wrapper_local.write_text(
                wrapper_original.replace(old_wrapper_clock, new_wrapper_clock),
                encoding="utf-8",
            )
            wrapper_clock_bridge_removed = True
        else:
            wrapper_clock_bridge_already_absent = True

    old_clock = """  always #(`CLK_PERIOD/2) clk = ~clk;

  always #(`TCLK_PERIOD/2) jclk = ~jclk;
"""
    new_clock = """  // sim-accel drives the declared main clock through the wrapper-level
  // proxy; expose it as a local continuous-assignment net so posedge clk
  // sensitivity inside tb.v sees actual signal transitions.
  assign clk = $root.xuantie_c906_gpu_cov_tb.simaccel_clk_proxy;
  assign jclk = $root.xuantie_c906_gpu_cov_tb.simaccel_clk_proxy;
"""
    if old_clock not in patched:
        return {
            "applied": False,
            "reason": "timing_clock_block_not_found",
            "tb_path": str(tb_local),
        }
    patched = patched.replace(old_clock, new_clock)

    old_reset = """initial begin
  #100;
  rst_b = 0;
  #100;
  rst_b = 1;
end

initial begin
  #400;
  jrst_b = 0;
  #400;
  jrst_b = 1;
end
"""
    new_reset = """integer simaccel_mem_loaded = 0;

always @(posedge clk)
begin
  if(!simaccel_mem_loaded) begin
    i=0;
    for(j=0;i<32'h4000;i=j/4)
    begin
      `RTL_MEM.ram0.mem[i][7:0] = mem_inst_temp[j][31:24];
      `RTL_MEM.ram1.mem[i][7:0] = mem_inst_temp[j][23:16];
      `RTL_MEM.ram2.mem[i][7:0] = mem_inst_temp[j][15: 8];
      `RTL_MEM.ram3.mem[i][7:0] = mem_inst_temp[j][ 7: 0];
      j = j+1;
      `RTL_MEM.ram4.mem[i][7:0] = mem_inst_temp[j][31:24];
      `RTL_MEM.ram5.mem[i][7:0] = mem_inst_temp[j][23:16];
      `RTL_MEM.ram6.mem[i][7:0] = mem_inst_temp[j][15: 8];
      `RTL_MEM.ram7.mem[i][7:0] = mem_inst_temp[j][ 7: 0];
      j = j+1;
      `RTL_MEM.ram8.mem[i][7:0] = mem_inst_temp[j][31:24];
      `RTL_MEM.ram9.mem[i][7:0] = mem_inst_temp[j][23:16];
      `RTL_MEM.ram10.mem[i][7:0] = mem_inst_temp[j][15: 8];
      `RTL_MEM.ram11.mem[i][7:0] = mem_inst_temp[j][ 7: 0];
      j = j+1;
      `RTL_MEM.ram12.mem[i][7:0] = mem_inst_temp[j][31:24];
      `RTL_MEM.ram13.mem[i][7:0] = mem_inst_temp[j][23:16];
      `RTL_MEM.ram14.mem[i][7:0] = mem_inst_temp[j][15: 8];
      `RTL_MEM.ram15.mem[i][7:0] = mem_inst_temp[j][ 7: 0];
      j = j+1;
    end
    i=0;
    for(j=0;i<32'h4000;i=j/4)
    begin
      `RTL_MEM.ram0.mem[i+32'h4000][7:0]  = mem_data_temp[j][31:24];
      `RTL_MEM.ram1.mem[i+32'h4000][7:0]  = mem_data_temp[j][23:16];
      `RTL_MEM.ram2.mem[i+32'h4000][7:0]  = mem_data_temp[j][15: 8];
      `RTL_MEM.ram3.mem[i+32'h4000][7:0]  = mem_data_temp[j][ 7: 0];
      j = j+1;
      `RTL_MEM.ram4.mem[i+32'h4000][7:0]  = mem_data_temp[j][31:24];
      `RTL_MEM.ram5.mem[i+32'h4000][7:0]  = mem_data_temp[j][23:16];
      `RTL_MEM.ram6.mem[i+32'h4000][7:0]  = mem_data_temp[j][15: 8];
      `RTL_MEM.ram7.mem[i+32'h4000][7:0]  = mem_data_temp[j][ 7: 0];
      j = j+1;
      `RTL_MEM.ram8.mem[i+32'h4000][7:0]   = mem_data_temp[j][31:24];
      `RTL_MEM.ram9.mem[i+32'h4000][7:0]   = mem_data_temp[j][23:16];
      `RTL_MEM.ram10.mem[i+32'h4000][7:0]  = mem_data_temp[j][15: 8];
      `RTL_MEM.ram11.mem[i+32'h4000][7:0]  = mem_data_temp[j][ 7: 0];
      j = j+1;
      `RTL_MEM.ram12.mem[i+32'h4000][7:0]  = mem_data_temp[j][31:24];
      `RTL_MEM.ram13.mem[i+32'h4000][7:0]  = mem_data_temp[j][23:16];
      `RTL_MEM.ram14.mem[i+32'h4000][7:0]  = mem_data_temp[j][15: 8];
      `RTL_MEM.ram15.mem[i+32'h4000][7:0]  = mem_data_temp[j][ 7: 0];
      j = j+1;
    end
    simaccel_mem_loaded <= 1;
  end
end

always @(posedge clk)
begin
  rst_b <= (simaccel_mem_loaded != 0);
  jrst_b <= (simaccel_mem_loaded != 0);
end
"""
    if old_reset not in patched:
        return {
            "applied": False,
            "reason": "delayed_reset_block_not_found",
            "tb_path": str(tb_local),
        }
    patched = patched.replace(old_reset, new_reset)
    if patched == original:
        return {
            "applied": False,
            "reason": "no_changes",
            "tb_path": str(tb_local),
        }
    tb_local.write_text(patched, encoding="utf-8")
    return {
        "applied": True,
        "design": compile_desc.design,
        "top_module": compile_desc.topModule,
        "tb_path": str(tb_local),
        "reset_contract": "split_always_release_from_mem_loaded",
        "clock_contract": "tb_root_proxy_clock",
        "memory_copy_contract": "preloaded_temp_arrays_to_rtl_mem_on_first_clock",
        "runtime_memory_contract": "inst_data_pat_visible_preload",
        "wrapper_clock_bridge_removed": wrapper_clock_bridge_removed,
        "wrapper_clock_bridge_already_absent": wrapper_clock_bridge_already_absent,
        "wrapper_path": str(wrapper_local) if wrapper_local is not None else "",
    }


def _apply_xuantie_e90x_sim_accel_staged_contract_patch(
    *,
    build_dir: Path,
    compile_desc: CompileDescriptor,
) -> dict[str, Any]:
    reset_contracts = {
        ("XuanTie-E902", "xuantie_e902_gpu_cov_tb"): {
            "old_reset": """initial begin
  #100;
  rst_b = 0;
  #100;
  rst_b = 1;
end

initial begin
  #100;
  jrst_b = 0;
  #100;
  jrst_b = 1;
end
""",
            "new_reset": """// sim-accel runtime preloads mem_inst_temp directly; keep the
// original tb.v initial memory copy path and only remove delay-based reset.
logic [1:0] simaccel_mem_loaded = 2'b11;

assign rst_b = simaccel_mem_loaded[0];
assign jrst_b = simaccel_mem_loaded[0];
""",
        },
        ("XuanTie-E906", "xuantie_e906_gpu_cov_tb"): {
            "old_reset": """initial begin
  #100;
  rst_b = 0;
  #100;
  rst_b = 1;
end

initial begin
  #100;
  jrst_b = 0;
  #100;
  jrst_b = 1;
end

initial begin
  #100;
  nrst_b = 0;
  #100;
  nrst_b = 1;
end
""",
            "new_reset": """// sim-accel runtime preloads mem_inst_temp directly; keep the
// original tb.v initial memory copy path and only remove delay-based reset.
logic [1:0] simaccel_mem_loaded = 2'b11;

assign rst_b = simaccel_mem_loaded[0];
assign jrst_b = simaccel_mem_loaded[0];
assign nrst_b = simaccel_mem_loaded[0];
""",
        },
    }
    reset_config = reset_contracts.get((compile_desc.design, compile_desc.topModule))
    if reset_config is None:
        return {"applied": False}

    tb_path = build_dir / "verilogSourceFiles" / "tb.v"
    if not tb_path.exists():
        return {
            "applied": False,
            "reason": "missing_staged_tb",
            "tb_path": str(tb_path),
        }

    tb_local = _stage_local_editable_copy(tb_path)
    original = tb_local.read_text(encoding="utf-8")
    patched = original.replace("reg clk = 0;", "logic clk;")
    patched = patched.replace("reg jclk = 0;", "logic jclk;")
    patched = patched.replace("reg rst_b = 1;", "logic rst_b;")
    patched = patched.replace("reg jrst_b = 1;", "logic jrst_b;")
    patched = patched.replace("reg nrst_b = 1;", "logic nrst_b;")

    wrapper_path = build_dir / "verilogSourceFiles" / f"{compile_desc.topModule}.sv"
    wrapper_local: Path | None = None
    wrapper_clock_bridge_removed = False
    wrapper_clock_bridge_already_absent = False
    wrapper_clock_bridge_inserted = False
    main_clock_override = f"{compile_desc.topModule}.simaccel_main_clk"
    if wrapper_path.exists():
        wrapper_local = _stage_local_editable_copy(wrapper_path)
        wrapper_original = wrapper_local.read_text(encoding="utf-8")
        wrapper_patched = wrapper_original
        old_wrapper_clock = """  always_comb begin
    dut.clk = simaccel_clk_proxy;
    dut.jclk = simaccel_clk_proxy;
  end
"""
        new_wrapper_clock = """  // sim-accel staged tb.v consumes the wrapper-level proxy directly.
"""
        if old_wrapper_clock in wrapper_patched:
            wrapper_patched = wrapper_patched.replace(old_wrapper_clock, new_wrapper_clock)
            wrapper_clock_bridge_removed = True
        else:
            wrapper_clock_bridge_already_absent = True
        old_dut_inst = "  tb dut();\n"
        new_dut_inst = """  tb dut();

  logic simaccel_main_clk;

  always_comb begin
    dut.clk = simaccel_main_clk;
  end
"""
        if "logic simaccel_main_clk;" not in wrapper_patched:
            if old_dut_inst not in wrapper_patched:
                return {
                    "applied": False,
                    "reason": "wrapper_dut_instance_not_found",
                    "wrapper_path": str(wrapper_local),
                }
            wrapper_patched = wrapper_patched.replace(old_dut_inst, new_dut_inst, 1)
            wrapper_clock_bridge_inserted = True
        if wrapper_patched != wrapper_original:
            wrapper_local.write_text(wrapper_patched, encoding="utf-8")
        compile_desc.verilogDefines["__RTLMETER_MAIN_CLOCK"] = main_clock_override

    old_clock = """always #(`CLK_PERIOD/2) clk = ~clk;
always #(`TCLK_PERIOD/2) jclk = ~jclk;
"""
    new_clock = """// sim-accel drives tb.clk directly through the declared mainClock path.
// Keep jclk phase-aligned without creating an internal free-running oscillator.
assign jclk = clk;
"""
    if old_clock not in patched:
        return {
            "applied": False,
            "reason": "timing_clock_block_not_found",
            "tb_path": str(tb_local),
        }
    patched = patched.replace(old_clock, new_clock)

    old_reset = str(reset_config["old_reset"])
    new_reset = str(reset_config["new_reset"])
    if old_reset not in patched:
        return {
            "applied": False,
            "reason": "delayed_reset_block_not_found",
            "tb_path": str(tb_local),
        }
    patched = patched.replace(old_reset, new_reset)
    if patched == original:
        return {
            "applied": False,
            "reason": "no_changes",
            "tb_path": str(tb_local),
        }
    tb_local.write_text(patched, encoding="utf-8")
    return {
        "applied": True,
        "design": compile_desc.design,
        "top_module": compile_desc.topModule,
        "tb_path": str(tb_local),
        "reset_contract": "constant_visible_reset_release_from_hidden_preload_ready",
        "clock_contract": "wrapper_level_main_clock_proxy",
        "memory_copy_contract": "preloaded_case_pat_to_mem_inst_temp_then_original_tb_initial_copy",
        "runtime_memory_contract": "case_pat_hidden_preload",
        "wrapper_clock_bridge_removed": wrapper_clock_bridge_removed,
        "wrapper_clock_bridge_already_absent": wrapper_clock_bridge_already_absent,
        "wrapper_clock_bridge_inserted": wrapper_clock_bridge_inserted,
        "main_clock_override": main_clock_override,
        "wrapper_path": str(wrapper_local) if wrapper_local is not None else "",
    }


def _bench_command(
    *,
    ns: argparse.Namespace,
    compile_desc: CompileDescriptor,
    filelist_path: Path,
    include_dir: Path,
    cpp_include_dir: Path,
    build_dir: Path,
    init_file: Path,
    execute_runtime_inputs: dict[str, Any],
    nstates: int,
    gpu_reps: int,
    cpu_reps: int,
    sequential_steps: int,
    execution_backend: str,
) -> list[str]:
    requested_hybrid_mode = _requested_hybrid_mode(list(getattr(ns, "bench_extra_args", []) or []))
    rocm_launch_mode = str(getattr(ns, "rocm_launch_mode", "auto") or "auto")
    rocm_native_cpu_ref_required = execution_backend == "rocm_llvm" and rocm_launch_mode != "source-bridge"
    native_block_args = _native_hsaco_safe_block_size_args(
        execution_backend=execution_backend,
        rocm_launch_mode=rocm_launch_mode,
        extra_args=list(getattr(ns, "bench_extra_args", []) or []),
    )
    cmd = [
        str(Path(ns.bench).expanduser().resolve()),
        "--verilator",
        str(Path(ns.verilator).expanduser().resolve()),
        "--top-module",
        compile_desc.topModule,
        "--outdir",
        str(build_dir),
        "--nstates",
        str(nstates),
        "--gpu-reps",
        str(gpu_reps),
        "--gpu-warmup-reps",
        str(int(ns.gpu_warmup_reps)),
        "--cpu-reps",
        str(cpu_reps),
        "--init-mode",
        "zero",
        "--init-file",
        str(init_file),
        "--dump-output-compact",
        str(build_dir / "gpu_output_compact.bin"),
        "--execution-backend",
        str(execution_backend),
    ]
    if requested_hybrid_mode == "off" or int(sequential_steps) > 0:
        cmd.extend(["--sequential-steps", str(sequential_steps)])
    if execution_backend == "rocm_llvm":
        cmd.extend(["--rocm-launch-mode", str(getattr(ns, "rocm_launch_mode", "auto") or "auto")])
        gfx_arch = str(getattr(ns, "gfx_arch", "") or "")
        if gfx_arch:
            cmd.extend(["--gfx-arch", gfx_arch])
    cmd.extend(native_block_args)
    for arg in getattr(ns, "bench_extra_args", []) or []:
        cmd.append(str(arg))
    if cpu_reps > 0 and not ns.skip_cpu_reference_build:
        cmd.extend(["--dump-output-compact-cpu", str(build_dir / "cpu_output_compact.bin")])
    elif not rocm_native_cpu_ref_required:
        cmd.append("--skip-cpu-reference-build")
    if ns.no_compile_cache:
        cmd.append("--no-compile-cache")
    else:
        cmd.extend(["--compile-cache-dir", str(Path(ns.compile_cache_dir).expanduser().resolve())])
    if execute_runtime_inputs.get("program_hex"):
        cmd.extend(["--program-hex", str(execute_runtime_inputs["program_hex"])])
    if execute_runtime_inputs.get("program_hex_target"):
        cmd.extend(["--program-hex-target", str(execute_runtime_inputs["program_hex_target"])])
    if execute_runtime_inputs.get("memory_image"):
        cmd.extend(["--memory-image", str(execute_runtime_inputs["memory_image"])])
    if execute_runtime_inputs.get("memory_image_target"):
        cmd.extend(["--memory-image-target", str(execute_runtime_inputs["memory_image_target"])])
    if execute_runtime_inputs.get("memory_image_format"):
        cmd.extend(["--memory-image-format", str(execute_runtime_inputs["memory_image_format"])])
    for sim_arg in list(execute_runtime_inputs.get("sim_args") or []):
        cmd.extend(["--sim-arg", str(sim_arg)])
    cmd.append("--")
    cmd.extend(str(arg) for arg in compile_desc.verilatorArgs)
    cmd.append(f"+incdir+{include_dir}")
    cmd.append("+define+__RTLMETER_SIM_ACCEL=1")
    for key, value in sorted(compile_desc.verilogDefines.items()):
        cmd.append(f"+define+{key}={value}")
    if compile_desc.cppIncludeFiles:
        cmd.extend(["-CFLAGS", f"-I{cpp_include_dir}"])
    for key, value in sorted(compile_desc.cppDefines.items()):
        cmd.extend(["-CFLAGS", f"-D{key}={value}"])
    cmd.extend(["-f", str(filelist_path)])
    return cmd


def _can_reuse_bench_kernel(
    *,
    build_dir: Path,
    top_module: str,
    execute_runtime_inputs: dict[str, Any],
) -> bool:
    required = [
        build_dir / "bench_kernel",
        build_dir / f"{top_module}.sim_accel.kernel.cu.vars.tsv",
    ]
    if not all(path.exists() for path in required):
        return False
    program_hex = str(execute_runtime_inputs.get("program_hex") or "").strip()
    program_hex_target = str(execute_runtime_inputs.get("program_hex_target") or "").strip()
    memory_image = str(execute_runtime_inputs.get("memory_image") or "").strip()
    memory_image_target = str(execute_runtime_inputs.get("memory_image_target") or "").strip()
    # Runtime reuse can now handle preload materialization when a target
    # descriptor is available. Keep the old wrapper path only for cases that
    # still rely on wrapper-only map-based program/image lowering.
    if program_hex and not program_hex_target:
        return False
    if memory_image and not memory_image_target:
        return False
    return True


def _merge_init_files(parts: list[Path], out_path: Path) -> Path:
    existing_parts = [path for path in parts if path.exists() and path.stat().st_size > 0]
    if not existing_parts:
        return out_path
    if len(existing_parts) == 1:
        return existing_parts[0]
    with out_path.open("w", encoding="utf-8") as handle:
        for index, path in enumerate(existing_parts):
            text = path.read_text(encoding="utf-8")
            handle.write(text)
            if text and not text.endswith("\n"):
                handle.write("\n")
            if index + 1 != len(existing_parts):
                handle.write("\n")
    return out_path


def _tsv_has_data_rows(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        next(handle, None)
        for line in handle:
            if line.strip():
                return True
    return False


def _materialize_runtime_preload_artifacts(
    *,
    build_dir: Path,
    top_module: str,
    init_file: Path,
    execute_runtime_inputs: dict[str, Any],
    compile_cache_dir: Path | None,
) -> dict[str, Any]:
    runtime_dir = build_dir / "runtime_preload_materialized"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    vars_tsv = build_dir / f"{top_module}.sim_accel.kernel.cu.vars.tsv"
    if not vars_tsv.exists():
        raise SystemExit(f"Missing vars.tsv required for runtime preload materialization: {vars_tsv}")

    init_parts = [init_file]
    direct_preload_files: list[str] = []
    array_preload_payload_files: list[str] = []
    materialized_rows: list[dict[str, Any]] = []
    cache_hit_count = 0
    cache_entry_count = 0
    cache_root = None
    helper_digest = _sha256_path(DEFAULT_PRELOAD_MATERIALIZE) if DEFAULT_PRELOAD_MATERIALIZE.exists() else ""
    vars_digest = _sha256_path(vars_tsv)
    if compile_cache_dir is not None:
        cache_root = _runtime_preload_cache_dir(compile_cache_dir)
        cache_root.mkdir(parents=True, exist_ok=True)

    def _materialize(
        *,
        prefix: str,
        memory_image: str,
        image_format: str,
        target_descriptor: str,
    ) -> None:
        nonlocal cache_hit_count, cache_entry_count
        memory_image_path = Path(memory_image).expanduser().resolve()
        target_path = Path(target_descriptor).expanduser().resolve()
        out_init = runtime_dir / f"{prefix}.init"
        out_preload = runtime_dir / f"{prefix}.preload.tsv"
        out_direct = runtime_dir / f"{prefix}.direct.tsv"
        out_payload = runtime_dir / f"{prefix}.payload.tsv"
        cache_hit = False
        cache_key = ""
        cache_entry = None
        cache_init = None
        cache_preload = None
        cache_direct = None
        cache_payload = None
        if cache_root is not None:
            cache_entry_count += 1
            cache_key_payload = {
                "prefix": prefix,
                "memory_image": str(memory_image_path),
                "memory_image_sha256": _sha256_path(memory_image_path),
                "target_descriptor": str(target_path),
                "target_descriptor_sha256": _sha256_path(target_path),
                "image_format": str(image_format),
                "vars_tsv": str(vars_tsv),
                "vars_tsv_sha256": vars_digest,
                "helper_sha256": helper_digest,
            }
            cache_key = hashlib.sha256(
                json.dumps(cache_key_payload, sort_keys=True).encode("utf-8")
            ).hexdigest()
            cache_entry = cache_root / cache_key
            cache_init = cache_entry / f"{prefix}.init"
            cache_preload = cache_entry / f"{prefix}.preload.tsv"
            cache_direct = cache_entry / f"{prefix}.direct.tsv"
            cache_payload = cache_entry / f"{prefix}.payload.tsv"
            if (
                cache_entry.exists()
                and cache_init is not None
                and cache_preload is not None
                and cache_direct is not None
                and cache_payload is not None
                and cache_init.exists()
                and cache_preload.exists()
                and cache_direct.exists()
                and cache_payload.exists()
            ):
                cache_hit = True
                cache_hit_count += 1
        if not cache_hit:
            target_init = cache_init or out_init
            target_preload = cache_preload or out_preload
            target_direct = cache_direct or out_direct
            target_payload = cache_payload or out_payload
            if cache_entry is not None:
                tmp_entry = cache_root / f".tmp.{cache_key}.{os.getpid()}"
                if tmp_entry.exists():
                    shutil.rmtree(tmp_entry)
                tmp_entry.mkdir(parents=True, exist_ok=True)
                target_init = tmp_entry / f"{prefix}.init"
                target_preload = tmp_entry / f"{prefix}.preload.tsv"
                target_direct = tmp_entry / f"{prefix}.direct.tsv"
                target_payload = tmp_entry / f"{prefix}.payload.tsv"
            cmd = [
                sys.executable,
                str(DEFAULT_PRELOAD_MATERIALIZE),
                "--memory-image",
                str(memory_image_path),
                "--vars-tsv",
                str(vars_tsv),
                "--format",
                str(image_format),
                "--target-descriptor",
                str(target_path),
                "--out-init",
                str(target_init),
                "--out-preload-tsv",
                str(target_preload),
                "--out-direct",
                str(target_direct),
                "--out-payload-tsv",
                str(target_payload),
            ]
            subprocess.run(cmd, cwd=build_dir, check=True)
            if cache_entry is not None:
                if cache_entry.exists():
                    shutil.rmtree(cache_entry, ignore_errors=True)
                tmp_entry.rename(cache_entry)
                target_init = cache_init
                target_preload = cache_preload
                target_direct = cache_direct
                target_payload = cache_payload
        else:
            target_init = cache_init
            target_preload = cache_preload
            target_direct = cache_direct
            target_payload = cache_payload

        assert target_init is not None
        assert target_preload is not None
        assert target_direct is not None
        assert target_payload is not None
        _replace_with_symlink(out_init, target_init)
        _replace_with_symlink(out_preload, target_preload)
        _replace_with_symlink(out_direct, target_direct)
        _replace_with_symlink(out_payload, target_payload)
        if _tsv_has_data_rows(out_direct):
            direct_preload_files.append(str(out_direct))
        elif out_init.exists() and out_init.stat().st_size > 0:
            init_parts.append(out_init)
        if out_payload.exists() and out_payload.stat().st_size > 0:
            array_preload_payload_files.append(str(out_payload))
        materialized_rows.append(
            {
                "prefix": prefix,
                "memory_image": str(memory_image_path),
                "format": str(image_format),
                "target_descriptor": str(target_path),
                "init_file": str(out_init),
                "direct_file": str(out_direct),
                "payload_tsv": str(out_payload),
                "cache_hit": cache_hit,
                "cache_key": cache_key,
                "cache_entry": str(cache_entry) if cache_entry is not None else "",
            }
        )

    program_hex = str(execute_runtime_inputs.get("program_hex") or "").strip()
    program_hex_target = str(execute_runtime_inputs.get("program_hex_target") or "").strip()
    if program_hex and program_hex_target:
        _materialize(
            prefix="program_hex",
            memory_image=program_hex,
            image_format="hex",
            target_descriptor=program_hex_target,
        )

    memory_image = str(execute_runtime_inputs.get("memory_image") or "").strip()
    memory_image_target = str(execute_runtime_inputs.get("memory_image_target") or "").strip()
    if memory_image and memory_image_target:
        _materialize(
            prefix="memory_image",
            memory_image=memory_image,
            image_format=str(execute_runtime_inputs.get("memory_image_format") or "auto"),
            target_descriptor=memory_image_target,
        )

    effective_init_file = _merge_init_files(init_parts, runtime_dir / "effective.init")
    return {
        "effective_init_file": str(effective_init_file),
        "direct_preload_files": direct_preload_files,
        "array_preload_payload_files": array_preload_payload_files,
        "materialized": materialized_rows,
        "cache_entry_count": cache_entry_count,
        "cache_hit_count": cache_hit_count,
        "cache_hit_rate": (
            float(cache_hit_count) / float(cache_entry_count) if cache_entry_count else 0.0
        ),
    }


def _bench_kernel_runtime_command(
    *,
    build_dir: Path,
    init_file: Path,
    direct_preload_files: list[str],
    array_preload_payload_files: list[str],
    nstates: int,
    gpu_reps: int,
    cpu_reps: int,
    gpu_warmup_reps: int,
    sequential_steps: int,
    skip_cpu_reference_build: bool,
    sim_args: list[str],
    bench_extra_args: list[str],
    execution_backend: str,
    rocm_launch_mode: str,
) -> list[str]:
    requested_hybrid_mode = _requested_hybrid_mode(bench_extra_args)
    native_block_args = _native_hsaco_safe_block_size_args(
        execution_backend=execution_backend,
        rocm_launch_mode=rocm_launch_mode,
        extra_args=bench_extra_args,
    )
    cmd = [
        str(build_dir / "bench_kernel"),
        "--nstates",
        str(nstates),
        "--gpu-reps",
        str(gpu_reps),
        "--cpu-reps",
        str(cpu_reps),
        "--gpu-warmup-reps",
        str(gpu_warmup_reps),
        "--init-mode",
        "zero",
        "--init-file",
        str(init_file),
        "--dump-output-compact",
        str(build_dir / "gpu_output_compact.bin"),
    ]
    cmd.extend(native_block_args)
    if requested_hybrid_mode == "off":
        cmd.extend(["--sequential-steps", str(sequential_steps)])
    if cpu_reps > 0 and not skip_cpu_reference_build:
        cmd.extend(["--dump-output-compact-cpu", str(build_dir / "cpu_output_compact.bin")])
    for path in direct_preload_files:
        cmd.extend(["--direct-preload-file", str(path)])
    for path in array_preload_payload_files:
        cmd.extend(["--array-preload-payload", str(path)])
    for sim_arg in sim_args:
        cmd.extend(["--sim-arg", str(sim_arg)])
    for extra_arg in bench_extra_args:
        cmd.append(str(extra_arg))
    return cmd


def _requested_hybrid_mode(extra_args: list[str]) -> str:
    mode = "off"
    pending_value = False
    for raw_arg in extra_args:
        arg = str(raw_arg)
        if pending_value:
            mode = arg
            pending_value = False
            continue
        if arg == "--hybrid-mode":
            pending_value = True
            continue
        if arg.startswith("--hybrid-mode="):
            mode = arg.split("=", 1)[1] or "off"
    return mode


def _build_caliptra_focused_wave_artifact(
    *,
    output_map: dict[str, dict[str, Any]],
    artifact_dir: Path,
    nstates: int,
) -> dict[str, Any] | None:
    focused_names = [f"focused_wave_word{i}_o" for i in range(8)]
    if any(name not in output_map for name in focused_names):
        return None

    def _state_values(name: str) -> list[int]:
        return [int(value) & 0xFFFF_FFFF for value in list(output_map[name].get("state_values") or [])]

    word_values = {name: _state_values(name) for name in focused_names}
    if any(not values for values in word_values.values()):
        return None
    state_count = min(int(nstates), *(len(values) for values in word_values.values()))
    if state_count <= 0:
        return None

    def _decode_status(word5: int, word6: int) -> dict[str, Any]:
        return {
            "ready_for_fuses": word5 & 0x1,
            "ready_for_mb_processing": (word5 >> 1) & 0x1,
            "mailbox_data_avail": (word5 >> 2) & 0x1,
            "pass_seen": (word5 >> 3) & 0x1,
            "fail_seen": (word5 >> 4) & 0x1,
            "cptra_error_fatal": word6 & 0x1,
            "cptra_error_non_fatal": (word6 >> 1) & 0x1,
        }

    state_samples: list[dict[str, Any]] = []
    for state_index in range(state_count):
        word0 = word_values["focused_wave_word0_o"][state_index]
        word1 = word_values["focused_wave_word1_o"][state_index]
        word2 = word_values["focused_wave_word2_o"][state_index]
        word3 = word_values["focused_wave_word3_o"][state_index]
        word4 = word_values["focused_wave_word4_o"][state_index]
        word5 = word_values["focused_wave_word5_o"][state_index]
        word6 = word_values["focused_wave_word6_o"][state_index]
        word7 = word_values["focused_wave_word7_o"][state_index]
        sample = {
            "state_index": state_index,
            "cycle_count": word0,
            "commit_count": word1,
            "host_req_accepted": word2,
            "device_rsp_accepted": word3,
            "last_mailbox_data_hex": f"0x{word4:08x}",
            "cfg_signature_hex": f"0x{word7:08x}",
            "word5_hex": f"0x{word5:08x}",
            "word6_hex": f"0x{word6:08x}",
        }
        sample.update(_decode_status(word5, word6))
        state_samples.append(sample)

    summary = {
        "state_count": state_count,
        "max_cycle_count": max(sample["cycle_count"] for sample in state_samples),
        "max_commit_count": max(sample["commit_count"] for sample in state_samples),
        "max_host_req_accepted": max(sample["host_req_accepted"] for sample in state_samples),
        "max_device_rsp_accepted": max(sample["device_rsp_accepted"] for sample in state_samples),
        "last_mailbox_data_or_hex": f"0x{int(output_map['focused_wave_word4_o'].get('or_reduce') or 0):08x}",
        "cfg_signature_values_hex": sorted({sample["cfg_signature_hex"] for sample in state_samples}),
        "any_ready_for_fuses": any(sample["ready_for_fuses"] for sample in state_samples),
        "any_ready_for_mb_processing": any(sample["ready_for_mb_processing"] for sample in state_samples),
        "any_mailbox_data_avail": any(sample["mailbox_data_avail"] for sample in state_samples),
        "any_pass_seen": any(sample["pass_seen"] for sample in state_samples),
        "any_fail_seen": any(sample["fail_seen"] for sample in state_samples),
        "any_cptra_error_fatal": any(sample["cptra_error_fatal"] for sample in state_samples),
        "any_cptra_error_non_fatal": any(sample["cptra_error_non_fatal"] for sample in state_samples),
    }
    artifact_path = artifact_dir / "gpu_focused_wave.json"
    artifact = {
        "schema_version": "caliptra-focused-wave-v1",
        "design": "Caliptra",
        "artifact_path": str(artifact_path),
        "summary": summary,
        "states": state_samples,
    }
    _write_json(artifact_path, artifact, compact=False)
    return artifact


def _build_runtime_focused_wave_artifact(
    *,
    design: str,
    output_map: dict[str, dict[str, Any]],
    compact_path: Path,
    vars_path: Path,
    comm_path: Path,
    artifact_dir: Path,
    nstates: int,
) -> dict[str, Any] | None:
    if str(design) == "Caliptra":
        artifact = _build_caliptra_focused_wave_artifact(
            output_map=output_map,
            artifact_dir=artifact_dir,
            nstates=nstates,
        )
        if artifact is not None:
            return artifact
    return _build_focused_wave_artifact(
        compact_path=compact_path,
        vars_path=vars_path,
        comm_path=comm_path,
        artifact_dir=artifact_dir,
        nstates=nstates,
    )


def _has_bench_arg(extra_args: list[str], option: str) -> bool:
    pending_value = False
    for raw_arg in extra_args:
        arg = str(raw_arg)
        if pending_value:
            pending_value = False
            continue
        if arg == option:
            pending_value = True
            return True
        if arg.startswith(f"{option}="):
            return True
    return False


def _native_hsaco_safe_block_size_args(
    *,
    execution_backend: str,
    rocm_launch_mode: str,
    extra_args: list[str],
) -> list[str]:
    if execution_backend != "rocm_llvm" or rocm_launch_mode != "native-hsaco":
        return []
    if _has_bench_arg(extra_args, "--block-size"):
        return []
    return ["--block-size", "80"]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run verilator_sim_accel_bench for a generic RTLMeter gpu_cov case."
    )
    parser.add_argument("--case", required=True, help="RTLMeter case, for example VeeR-EL2:gpu_cov:hello")
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--json-out", default="")
    parser.add_argument("--bench", default=str(DEFAULT_BENCH))
    parser.add_argument("--verilator", default=str(DEFAULT_VERILATOR))
    parser.add_argument("--nstates", type=int, default=4)
    parser.add_argument("--gpu-reps", type=int, default=1)
    parser.add_argument("--cpu-reps", type=int, default=1)
    parser.add_argument("--gpu-warmup-reps", type=int, default=1)
    parser.add_argument("--sequential-steps", type=int, default=0)
    parser.add_argument("--skip-cpu-reference-build", action="store_true")
    parser.add_argument("--summary-mode", choices=("full", "prefilter"), default="full")
    parser.add_argument(
        "--gpu-execution-backend",
        choices=("auto", "cuda_source", "cuda_circt_cubin", "cuda_clang_ir", "cuda_vl_ir", "rocm_llvm"),
        default="auto",
    )
    parser.add_argument(
        "--gpu-selection-policy",
        choices=("auto", "prefer_cuda", "prefer_rocm", "cuda_only", "rocm_only"),
        default="auto",
    )
    parser.add_argument(
        "--rocm-launch-mode",
        choices=("auto", "source-bridge", "native-hsaco"),
        default="auto",
    )
    parser.add_argument(
        "--gfx-arch",
        default="",
        help="GFX architecture for ROCm bridge compilation (e.g. gfx1201). "
        "Also sets HSA_OVERRIDE_GFX_VERSION at runtime. "
        "Derived from HSA_OVERRIDE_GFX_VERSION env var when not specified.",
    )
    parser.add_argument(
        "--bench-extra-arg",
        dest="bench_extra_args",
        action="append",
        default=[],
        help="Extra argument forwarded directly to verilator_sim_accel_bench before the '--' separator.",
    )
    parser.add_argument(
        "--include-focused-wave-prefilter",
        action="store_true",
        help="Retain focused wave/metric outputs even in prefilter summary mode.",
    )
    parser.add_argument("--compile-cache-dir", default=str(DEFAULT_COMPILE_CACHE))
    parser.add_argument("--no-compile-cache", action="store_true")
    parser.add_argument("--compile-full-all-only", dest="compile_full_all_only", action="store_true")
    parser.add_argument("--no-compile-full-all-only", dest="compile_full_all_only", action="store_false")
    parser.set_defaults(compile_full_all_only=True)
    parser.add_argument(
        "--pre-gpu-gate",
        choices=("auto", "always", "never"),
        default="auto",
        help="Run a standard non-gpu_cov precheck before GPU baseline for designs that need onboarding validation.",
    )
    parser.add_argument(
        "--pre-gpu-gate-only",
        action="store_true",
        help="Stop after pre-GPU validation and emit only gate results without compiling the GPU benchmark.",
    )
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument(
        "--reuse-bench-kernel-if-present",
        dest="reuse_bench_kernel_if_present",
        action="store_true",
        help="If bench_kernel already exists, run it directly and materialize any target-described runtime preload payloads locally instead of rebuilding through the wrapper. Defaults to enabled for GPU executions.",
    )
    parser.add_argument(
        "--no-reuse-bench-kernel-if-present",
        dest="reuse_bench_kernel_if_present",
        action="store_false",
        help="Force wrapper execution even when direct bench reuse is available.",
    )
    parser.set_defaults(reuse_bench_kernel_if_present=None)
    for key in DRIVER_DEFAULTS:
        parser.add_argument(f"--{key.replace('_', '-')}", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    build_dir = Path(ns.build_dir).expanduser().resolve()
    if ns.rebuild and build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    compile_case = ":".join(str(ns.case).split(":")[:2])
    compile_desc = CompileDescriptor(compile_case)
    execute_desc = ExecuteDescriptor(str(ns.case))
    execute_arg_overrides = _parse_execute_args(execute_desc)

    tb_path = _find_coverage_tb(compile_desc.verilogSourceFiles, compile_desc.topModule)
    manifest_path = _find_coverage_manifest(execute_desc.files)
    selected_output_names = _summary_selected_output_names(
        str(ns.summary_mode),
        include_focused_wave_prefilter=bool(ns.include_focused_wave_prefilter),
    )

    driver = _load_driver_from_args(ns)
    nstates = int(ns.nstates)
    gpu_reps = int(ns.gpu_reps)
    cpu_reps = 0 if ns.skip_cpu_reference_build else int(ns.cpu_reps)
    reuse_bench_kernel_if_present = ns.reuse_bench_kernel_if_present
    if reuse_bench_kernel_if_present is None:
        reuse_bench_kernel_if_present = gpu_reps > 0
    requested_hybrid_mode = _requested_hybrid_mode(list(getattr(ns, "bench_extra_args", []) or []))
    if requested_hybrid_mode != "off":
        sequential_steps = int(ns.sequential_steps)
    else:
        sequential_steps = int(ns.sequential_steps) or estimate_sync_sequential_steps(driver)
    gpu_execution_backend = resolve_gpu_execution_backend(
        requested=str(ns.gpu_execution_backend),
        launch_backend="source",
        execution_engine=("gpu" if gpu_reps > 0 else "cpu"),
        selection_policy=str(ns.gpu_selection_policy),
    )
    ensure_gpu_execution_backend_supported(
        gpu_execution_backend,
        runner_name=Path(__file__).name,
    )

    source_dir, include_dir, cpp_source_dir, cpp_include_dir, filelist_path = _stage_filelist(
        build_dir,
        compile_desc,
    )
    staged_contract_patch = _apply_xiangshan_sim_accel_staged_contract_patch(
        build_dir=build_dir,
        compile_desc=compile_desc,
    )
    if not staged_contract_patch.get("applied"):
        staged_contract_patch = _apply_xuantie_c906_sim_accel_staged_contract_patch(
            build_dir=build_dir,
            compile_desc=compile_desc,
        )
    if not staged_contract_patch.get("applied"):
        staged_contract_patch = _apply_xuantie_e90x_sim_accel_staged_contract_patch(
            build_dir=build_dir,
            compile_desc=compile_desc,
        )
    staged_execute_files = _stage_execute_files(build_dir, execute_desc)
    execute_runtime_inputs = _materialize_execute_runtime_inputs(
        build_dir=build_dir,
        top_module=compile_desc.topModule,
        design=execute_desc.design,
        staged_execute_files=staged_execute_files,
        execute_arg_overrides=execute_arg_overrides,
    )
    pre_gpu_gate = _build_pregpu_gate(
        ns=ns,
        design=execute_desc.design,
        test=execute_desc.test,
        top_module=compile_desc.topModule,
        execute_runtime_inputs=execute_runtime_inputs,
        build_dir=build_dir,
    )
    _write_json(build_dir / "pre_gpu_gate.json", pre_gpu_gate)
    if ns.pre_gpu_gate_only:
        gate_summary = {
            "schema_version": "rtlmeter-gpu-toggle-pre-gate-v1",
            "case": str(ns.case),
            "compile_case": compile_case,
            "design": execute_desc.design,
            "config": execute_desc.config,
            "test": execute_desc.test,
            "build_dir": str(build_dir),
            "execute_files": [str(path) for path in staged_execute_files],
            "execute_runtime_inputs": execute_runtime_inputs,
            "pre_gpu_gate": pre_gpu_gate,
        }
        if ns.json_out:
            _write_json(Path(ns.json_out).expanduser().resolve(), gate_summary)
        print(str(Path(ns.json_out).expanduser().resolve()) if ns.json_out else json.dumps(gate_summary))
        return 0 if pre_gpu_gate.get("status") == "pass" else 2
    if pre_gpu_gate.get("status") != "pass":
        raise SystemExit(
            "Pre-GPU gate failed; see "
            f"{build_dir / 'pre_gpu_gate.json'}"
        )
    init_file = build_dir / "gpu_driver.init"
    _write_init_file(init_file, driver, nstates=nstates, uniform_states=True)
    extra_init_lines = [str(line).strip() for line in execute_runtime_inputs.get("extra_init_lines", []) if str(line).strip()]
    if extra_init_lines:
        with init_file.open("a", encoding="utf-8") as handle:
            for line in extra_init_lines:
                handle.write(f"{line}\n")

    stdout_log = build_dir / "baseline_stdout.log"
    bench_cmd = _bench_command(
        ns=ns,
        compile_desc=compile_desc,
        filelist_path=filelist_path,
        include_dir=include_dir,
        cpp_include_dir=cpp_include_dir,
        build_dir=build_dir,
        init_file=init_file,
        execute_runtime_inputs=execute_runtime_inputs,
        nstates=nstates,
        gpu_reps=gpu_reps,
        cpu_reps=cpu_reps,
        sequential_steps=sequential_steps,
        execution_backend=str(gpu_execution_backend.get("selected") or "cuda_vl_ir"),
    )
    bench_runtime_mode = "wrapper"
    bench_runtime_reused = False
    direct_reuse_eligible = _can_reuse_bench_kernel(
        build_dir=build_dir,
        top_module=compile_desc.topModule,
        execute_runtime_inputs=execute_runtime_inputs,
    )
    runtime_cmd = bench_cmd
    runtime_preloads = {
        "effective_init_file": str(init_file),
        "direct_preload_files": [],
        "array_preload_payload_files": [],
        "materialized": [],
    }
    if bool(reuse_bench_kernel_if_present) and direct_reuse_eligible:
        runtime_preloads = _materialize_runtime_preload_artifacts(
            build_dir=build_dir,
            top_module=compile_desc.topModule,
            init_file=init_file,
            execute_runtime_inputs=execute_runtime_inputs,
            compile_cache_dir=(
                None
                if ns.no_compile_cache
                else Path(ns.compile_cache_dir).expanduser().resolve()
            ),
        )
        runtime_cmd = _bench_kernel_runtime_command(
            build_dir=build_dir,
            init_file=Path(runtime_preloads["effective_init_file"]),
            direct_preload_files=list(runtime_preloads["direct_preload_files"]),
            array_preload_payload_files=list(runtime_preloads["array_preload_payload_files"]),
            nstates=nstates,
            gpu_reps=gpu_reps,
            cpu_reps=cpu_reps,
            gpu_warmup_reps=int(ns.gpu_warmup_reps),
            sequential_steps=sequential_steps,
            skip_cpu_reference_build=bool(ns.skip_cpu_reference_build),
            sim_args=list(execute_runtime_inputs.get("sim_args") or []),
            bench_extra_args=list(getattr(ns, "bench_extra_args", []) or []),
            execution_backend=str(gpu_execution_backend.get("selected") or "cuda_vl_ir"),
            rocm_launch_mode=str(getattr(ns, "rocm_launch_mode", "auto") or "auto"),
        )
        bench_runtime_mode = "direct_bench_kernel"
        bench_runtime_reused = True

    env = dict(os.environ)
    env.setdefault("VERILATOR_ROOT", str(ROOT_DIR / "third_party/verilator"))
    env["SIM_ACCEL_COMPILE_FULL_ALL_ONLY"] = "1" if ns.compile_full_all_only else "0"
    env["SIM_ACCEL_ENABLE_FULL_KERNEL_FUSER"] = "1" if ns.compile_full_all_only else "0"
    if str(gpu_execution_backend.get("selected") or "") == "rocm_llvm":
        _gfx = str(getattr(ns, "gfx_arch", "") or "")
        if _gfx:
            import re as _re
            _m = _re.fullmatch(r"gfx(\d+)(\d)(\d)", _gfx)
            if _m:
                env.setdefault("HSA_OVERRIDE_GFX_VERSION", f"{_m.group(1)}.{_m.group(2)}.{_m.group(3)}")
    with stdout_log.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(
            runtime_cmd,
            cwd=build_dir,
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if proc.returncode != 0 and bench_runtime_reused:
        bench_runtime_mode = "wrapper_fallback_after_direct_reuse_failure"
        bench_runtime_reused = False
        with stdout_log.open("a", encoding="utf-8") as handle:
            handle.write("\n[rtlmeter_gpu_toggle_baseline] direct bench_kernel reuse failed; retrying wrapper build path\n")
        with stdout_log.open("a", encoding="utf-8") as handle:
            proc = subprocess.run(
                bench_cmd,
                cwd=build_dir,
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )
    if proc.returncode != 0:
        raise SystemExit(f"RTLMeter gpu toggle baseline failed: see {stdout_log}")

    bench_log = build_dir / "bench_run.log"
    bench_log.write_text(stdout_log.read_text(encoding="utf-8"), encoding="utf-8")
    vars_path = build_dir / f"{compile_desc.topModule}.sim_accel.kernel.cu.vars.tsv"
    comm_path = build_dir / f"{compile_desc.topModule}.sim_accel.kernel.cu.comm.tsv"
    if not vars_path.exists():
        raise SystemExit(f"Missing vars.tsv after bench run: {vars_path}")

    gpu_compact_path = build_dir / "gpu_output_compact.bin"
    cpu_compact_path = build_dir / "cpu_output_compact.bin"
    active_compact_path = gpu_compact_path if gpu_compact_path.exists() else cpu_compact_path
    active_compact_source = "gpu" if active_compact_path == gpu_compact_path else "cpu"
    runtime_selected_output_names = set(selected_output_names)
    runtime_selected_output_names.update(REQUIRED_OUTPUTS_FLAT)
    output_rows = extract_sim_accel_output_slot_values(
        active_compact_path,
        vars_path,
        comm_path=comm_path if comm_path.exists() else None,
        nstates=nstates,
        selected_names=runtime_selected_output_names,
        dense_selected_names=False,
    )
    output_map = {row["name"]: row for row in output_rows}
    active_words = [
        name
        for name in REAL_TOGGLE_SUBSET_OUTPUTS
        if any(int(value) != 0 for value in output_map.get(name, {}).get("state_values", []))
    ]
    dead_words = [name for name in REAL_TOGGLE_SUBSET_OUTPUTS if name not in active_words]
    region_manifest = load_region_manifest(manifest_path)
    region_summary = summarize_regions(
        region_manifest,
        active_words=active_words,
        dead_words=dead_words,
    )

    metrics = parse_bench_log(bench_log)
    active_walltime_s = (
        float(metrics.get("gpu_ms_per_rep") or 0.0) / 1000.0
        if active_compact_source == "gpu"
        else float(metrics.get("cpu_ms_per_rep") or 0.0) / 1000.0
    )
    collector = build_collector_summary(metrics)
    populate_collector_coverage(
        collector,
        points_hit=len(active_words),
        points_total=len(REAL_TOGGLE_SUBSET_OUTPUTS),
        gpu_walltime_s=active_walltime_s if active_compact_source == "gpu" else None,
        cpu_walltime_s=(
            active_walltime_s
            if active_compact_source == "cpu"
            else (
                float(metrics["cpu_ms_per_rep"]) / 1000.0
                if cpu_reps > 0 and isinstance(metrics.get("cpu_ms_per_rep"), (int, float))
                else None
            )
        ),
        source_summary={
            "coverage_mode": "real_toggle_subset_word_level",
            "compact_source": f"{active_compact_source}_output_compact.bin",
            "coverage_manifest_path": str(manifest_path),
        },
    )

    template_contract = validate_slice_contract(
        target=str(ns.case),
        top_module=compile_desc.topModule,
        tb_path=tb_path,
        manifest_path=manifest_path,
    )
    constant_folded_outputs = _constant_folded_outputs(tb_path, REQUIRED_OUTPUTS_FLAT)
    runtime_missing_outputs = [name for name in REQUIRED_OUTPUTS_FLAT if name not in output_map]
    runtime_constant_folded_outputs = [
        name for name in runtime_missing_outputs if name in constant_folded_outputs
    ]
    runtime_missing_required_outputs = [
        name for name in runtime_missing_outputs if name not in constant_folded_outputs
    ]
    tb_contract = {
        "status": (
            "pass"
            if template_contract.get("status") == "contract_ready" and not runtime_missing_required_outputs
            else "needs_review"
        ),
        "template": template_contract,
        "runtime_output_count": len(output_map),
        "runtime_missing_outputs": runtime_missing_outputs,
        "runtime_missing_required_outputs": runtime_missing_required_outputs,
        "runtime_constant_folded_outputs": runtime_constant_folded_outputs,
    }
    observability = _build_observability_summary(
        metrics=metrics,
        collector=collector,
        build_dir=build_dir,
        stdout_log=stdout_log,
        region_summary=region_summary,
        skip_cpu_reference_build=bool(ns.skip_cpu_reference_build),
    )
    focused_wave = _build_runtime_focused_wave_artifact(
        design=str(compile_desc.design),
        output_map=output_map,
        compact_path=active_compact_path,
        vars_path=vars_path,
        comm_path=comm_path if comm_path.exists() else Path(""),
        artifact_dir=build_dir,
        nstates=nstates,
    )

    summary = {
        "schema_version": "rtlmeter-gpu-toggle-baseline-v1",
        "case": str(ns.case),
        "compile_case": compile_case,
        "design": execute_desc.design,
        "config": execute_desc.config,
        "test": execute_desc.test,
        "build_dir": str(build_dir),
        "compile_dir_layout": {
            "source_dir": str(source_dir),
            "include_dir": str(include_dir),
            "cpp_source_dir": str(cpp_source_dir),
            "cpp_include_dir": str(cpp_include_dir),
            "filelist": str(filelist_path),
        },
        "execute_files": [str(path) for path in staged_execute_files],
        "execute_args": list(execute_desc.args),
        "staged_contract_patch": staged_contract_patch,
        "execute_runtime_inputs": execute_runtime_inputs,
        "pre_gpu_gate": pre_gpu_gate,
        "driver": driver,
        "bench_command": bench_cmd,
        "bench_runtime_command": runtime_cmd,
        "bench_runtime_mode": bench_runtime_mode,
        "bench_runtime_reused": bench_runtime_reused,
        "gpu_execution_backend": gpu_execution_backend,
        "gpu_selection_policy": str(ns.gpu_selection_policy),
        "rocm_launch_mode_request": str(ns.rocm_launch_mode),
        "native_hsaco_mode": (
            str(gpu_execution_backend.get("selected") or "") == "rocm_llvm"
            and str(metrics.get("rocm_launch_mode") or "") == "native-hsaco"
        ),
        "reuse_bench_kernel_if_present": bool(reuse_bench_kernel_if_present),
        "bench_runtime_materialized_preloads": runtime_preloads,
        "metrics": metrics,
        "collector": collector,
        "tb_contract": tb_contract,
        "observability": observability,
        "coverage_regions": region_summary,
        "real_toggle_subset": {
            "points_hit": len(active_words),
            "points_total": len(REAL_TOGGLE_SUBSET_OUTPUTS),
            "active_words": active_words,
            "dead_words": dead_words,
        },
        "compact": {
            "active_source": active_compact_source,
            "gpu_sha256": (
                sha256_hex_bytes(gpu_compact_path.read_bytes()) if gpu_compact_path.exists() else None
            ),
            "cpu_sha256": (
                sha256_hex_bytes(cpu_compact_path.read_bytes()) if cpu_compact_path.exists() else None
            ),
        },
        "focused_wave": focused_wave,
        "artifacts": {
            "stdout_log": str(stdout_log),
            "bench_log": str(bench_log),
            "vars_tsv": str(vars_path),
            "comm_tsv": str(comm_path) if comm_path.exists() else "",
            "gpu_compact": str(gpu_compact_path) if gpu_compact_path.exists() else "",
            "cpu_compact": str(cpu_compact_path) if cpu_compact_path.exists() else "",
            "coverage_tb": str(tb_path),
            "coverage_manifest": str(manifest_path),
        },
    }
    if ns.json_out:
        _write_json(Path(ns.json_out).expanduser().resolve(), summary)
    print(str(Path(ns.json_out).expanduser().resolve()) if ns.json_out else json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
