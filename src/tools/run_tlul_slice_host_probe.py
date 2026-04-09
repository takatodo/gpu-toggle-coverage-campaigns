#!/usr/bin/env python3
"""
Build and run a generic OpenTitan TL-UL slice host probe against stock Verilator --cc output.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from build_vl_gpu import find_prefix


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
PROBE_SOURCE = REPO_ROOT / "src" / "hybrid" / "tlul_slice_host_probe.cpp"
VERILATOR_ROOT = REPO_ROOT / "third_party" / "verilator"
DEFAULT_TEMPLATE_DIR = REPO_ROOT / "config" / "slice_launch_templates"
DEFAULT_MDIR = REPO_ROOT / "work" / "vl_ir_exp" / "tlul_request_loopback_vl"
DEFAULT_BINARY = "tlul_slice_host_probe"

TARGET_RE = re.compile(r"^V(?P<target>.+?)(?:_gpu_cov(?:_(?:host|cpu_replay))?|_cov)_tb$")
DRIVER_SIGNAL_NAMES = {
    "batch_length": "cfg_batch_length_i",
    "req_valid_pct": "cfg_req_valid_pct_i",
    "rsp_valid_pct": "cfg_rsp_valid_pct_i",
    "host_d_ready_pct": "cfg_host_d_ready_pct_i",
    "device_a_ready_pct": "cfg_device_a_ready_pct_i",
    "put_full_pct": "cfg_put_full_pct_i",
    "put_partial_pct": "cfg_put_partial_pct_i",
    "req_fill_target": "cfg_req_fill_target_i",
    "req_burst_len_max": "cfg_req_burst_len_max_i",
    "req_family": "cfg_req_family_i",
    "req_address_mode": "cfg_req_address_mode_i",
    "req_data_mode": "cfg_req_data_mode_i",
    "req_data_hi_xor": "cfg_req_data_hi_xor_i",
    "access_ack_data_pct": "cfg_access_ack_data_pct_i",
    "rsp_error_pct": "cfg_rsp_error_pct_i",
    "rsp_fill_target": "cfg_rsp_fill_target_i",
    "rsp_delay_max": "cfg_rsp_delay_max_i",
    "rsp_family": "cfg_rsp_family_i",
    "rsp_delay_mode": "cfg_rsp_delay_mode_i",
    "rsp_data_mode": "cfg_rsp_data_mode_i",
    "rsp_data_hi_xor": "cfg_rsp_data_hi_xor_i",
    "reset_cycles": "cfg_reset_cycles_i",
    "drain_cycles": "cfg_drain_cycles_i",
    "seed": "cfg_seed_i",
    "address_base": "cfg_address_base_i",
    "address_mask": "cfg_address_mask_i",
    "source_mask": "cfg_source_mask_i",
}


def _derive_target(prefix: str) -> str:
    match = TARGET_RE.match(prefix)
    if not match:
        raise RuntimeError(f"cannot derive target name from prefix: {prefix}")
    return match.group("target")


def _read_root_header_text(mdir: Path, prefix: str) -> tuple[Path, str]:
    root_header = mdir / f"{prefix}___024root.h"
    if not root_header.is_file():
        raise FileNotFoundError(f"{root_header} not found")
    return root_header, root_header.read_text(encoding="utf-8")


def _has_member(text: str, member_name: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(member_name)}(?![A-Za-z0-9_])", text) is not None


def _first_present(text: str, names: list[str]) -> str | None:
    for name in names:
        if _has_member(text, name):
            return name
    return None


def _load_template_settings(template_path: Path | None) -> dict[str, int]:
    if template_path is None or not template_path.is_file():
        return {}
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    driver_defaults = dict(payload.get("runner_args_template", {}).get("driver_defaults") or {})
    settings: dict[str, int] = {}
    for key, signal_name in DRIVER_SIGNAL_NAMES.items():
        if key in driver_defaults:
            settings[signal_name] = int(driver_defaults[key], 0) if isinstance(driver_defaults[key], str) else int(driver_defaults[key])
    return settings


def _load_template_watch_fields(template_path: Path | None) -> list[str]:
    if template_path is None or not template_path.is_file():
        return []
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    merged: list[str] = []
    seen: set[str] = set()
    for source in (
        payload.get("debug_internal_output_names") or [],
        payload.get("runner_args_template", {}).get("debug_internal_output_names") or [],
    ):
        for raw_name in source:
            name = str(raw_name)
            if name not in seen:
                seen.add(name)
                merged.append(name)
    return merged


def _load_memory_image_target_descriptor(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _memory_image_target_member_name(prefix: str, descriptor: dict[str, Any]) -> str:
    target_path = str(descriptor.get("target_path") or "").strip()
    if not target_path:
        raise ValueError("memory-image target descriptor missing target_path")
    top_module = prefix[1:] if prefix.startswith("V") else prefix
    parts = [part for part in target_path.split(".") if part]
    if not parts:
        raise ValueError("memory-image target_path is empty")
    if parts[0] != top_module:
        raise ValueError(
            f"memory-image target_path top module mismatch: {parts[0]!r} != {top_module!r}"
        )
    return "__DOT__".join(parts)


def _memory_image_extra_defines(mdir: Path, prefix: str, descriptor_path: Path) -> list[str]:
    descriptor = _load_memory_image_target_descriptor(descriptor_path)
    if str(descriptor.get("kind") or "") != "memory-array-preload-v1":
        raise ValueError(
            "memory-image target descriptor kind must be 'memory-array-preload-v1'"
        )
    word_bits = int(descriptor.get("word_bits", 0))
    if word_bits not in (32, 64):
        raise ValueError(f"unsupported memory-image word_bits: {word_bits}")
    depth = int(descriptor.get("depth", 0))
    if depth <= 0:
        raise ValueError(f"invalid memory-image depth: {depth}")
    base_addr = int(descriptor.get("base_addr", 0))
    if base_addr != 0:
        raise ValueError(f"unsupported memory-image base_addr: {base_addr}")
    endianness = str(descriptor.get("endianness") or "little")
    if endianness != "little":
        raise ValueError(f"unsupported memory-image endianness: {endianness!r}")
    address_unit_bytes = int(descriptor.get("address_unit_bytes", 0))
    expected_word_bytes = word_bits // 8
    if address_unit_bytes != expected_word_bytes:
        raise ValueError(
            "memory-image descriptor must use address_unit_bytes equal to word size "
            f"({address_unit_bytes} != {expected_word_bytes})"
        )
    member_name = _memory_image_target_member_name(prefix, descriptor)
    _, root_text = _read_root_header_text(mdir, prefix)
    if not _has_member(root_text, member_name):
        raise RuntimeError(
            f"memory-image target member not found in root header: {member_name}"
        )
    return [
        f"-DMEMORY_IMAGE_ARRAY={member_name}",
        f"-DMEMORY_IMAGE_WORD_BITS={word_bits}",
        f"-DMEMORY_IMAGE_EXPECTED_DEPTH={depth}",
    ]


def _apply_overrides(settings: dict[str, int], raw_overrides: list[str]) -> dict[str, int]:
    updated = dict(settings)
    for raw in raw_overrides:
        if "=" not in raw:
            raise ValueError(f"bad --set {raw!r} (want field=value)")
        name, raw_value = raw.split("=", 1)
        updated[name] = int(raw_value, 0)
    return updated


def _select_clock_field(mdir: Path, prefix: str) -> tuple[str, str, bool]:
    _, text = _read_root_header_text(mdir, prefix)
    top_module = prefix[1:] if prefix.startswith("V") else prefix
    direct_field = _first_present(text, ["clk_i", "clk"])
    if direct_field is not None:
        report_name = "clk_i" if direct_field == "clk_i" else direct_field
        return (direct_field, report_name, True)
    nested_host_control_preferred = [
        "simaccel_main_clk",
        "dut__DOT__core_ref_clk",
    ]
    nested_host_control = _first_present(
        text,
        [f"{top_module}__DOT__{name}" for name in nested_host_control_preferred],
    )
    if nested_host_control is not None:
        return (
            nested_host_control,
            nested_host_control.removeprefix(f"{top_module}__DOT__"),
            True,
        )
    nested_preferred = [
        "clk_i",
        "clk",
        "clock",
        "core_clk",
        "dut__DOT__dut_clk",
        "dut__DOT__clk",
        "dut__DOT__clock",
        "dut__DOT__core_clk",
        "clk_main_i",
        "clk_fixed_i",
        "clk_usb_i",
        "clk_spi_host0_i",
        "clk_spi_host1_i",
    ]
    nested_candidates = [f"{top_module}__DOT__{name}" for name in nested_preferred]
    nested_field = _first_present(text, nested_candidates)
    if nested_field is not None:
        return (nested_field, nested_field.removeprefix(f"{top_module}__DOT__"), False)
    raise RuntimeError(
        "cannot find supported clock control field in "
        f"{mdir / f'{prefix}___024root.h'} (looked for clk_i / nested clk_i / known multi-clock aliases)"
    )


def _select_reset_field(mdir: Path, prefix: str) -> tuple[str, str, int, int, bool]:
    root_header, text = _read_root_header_text(mdir, prefix)
    top_module = prefix[1:] if prefix.startswith("V") else prefix
    if _has_member(text, "rst_ni"):
        return ("rst_ni", "rst_ni", 0, 1, True)
    if _has_member(text, "rst_b"):
        return ("rst_b", "rst_b", 0, 1, True)
    if _has_member(text, "nrst_b"):
        return ("nrst_b", "nrst_b", 0, 1, True)
    nested_active_low = [
        "rst_ni",
        "rst_l",
        "porst_l",
        "rst_b",
        "dut__DOT__cptra_rst_b",
        "dut__DOT__rst_b",
        "dut__DOT__rst_l",
        "dut__DOT__porst_l",
        "dut__DOT__gpu_cov_rst_l_w",
        "dut__DOT__gpu_cov_porst_l_w",
        "dut__DOT__sys_rst_n",
        "dut__DOT__rvtop__DOT__core_rst_l",
        "dut__DOT__nrst_b",
        "x_soc__DOT__pad_cpu_rst_b",
        "x_soc__DOT__x_cpu_sub_system_axi__DOT__x_rv_integration_platform__DOT__x_cpu_top__DOT__x_ct_mp_rst_top__DOT__async_core0_rst_b",
        "x_soc__DOT__x_cpu_sub_system_axi__DOT__x_rv_integration_platform__DOT__x_cpu_top__DOT__trst_b",
        "x_soc__DOT__x_cpu_sub_system_axi__DOT__x_rv_integration_platform__DOT__x_cpu_top__DOT__x_ct_top_0__DOT__x_ct_rst_top__DOT__idurst_b",
        "rst_main_ni",
        "rst_fixed_ni",
        "rst_usb_ni",
        "rst_spi_host0_ni",
        "rst_spi_host1_ni",
    ]
    nested_rst = _first_present(text, [f"{top_module}__DOT__{name}" for name in nested_active_low])
    if nested_rst is not None:
        return (nested_rst, nested_rst.removeprefix(f"{top_module}__DOT__"), 0, 1, False)
    nested_active_high = [
        "reset",
        "dut__DOT__dut_reset",
        "dut__DOT__reset",
    ]
    nested_reset = _first_present(text, [f"{top_module}__DOT__{name}" for name in nested_active_high])
    if nested_reset is not None:
        return (nested_reset, nested_reset.removeprefix(f"{top_module}__DOT__"), 1, 0, False)
    if _has_member(text, "reset_like_w"):
        return ("reset_like_w", "reset_like_w", 1, 0, False)
    reset_like_field = f"{top_module}__DOT__reset_like_w"
    if _has_member(text, reset_like_field):
        return (reset_like_field, "reset_like_w", 1, 0, False)
    raise RuntimeError(
        "cannot find supported reset control field in "
        f"{root_header} (looked for rst_ni / known rst_*_ni aliases / reset_like_w)"
    )


def _resolve_watch_fields(mdir: Path, prefix: str, watch_fields: list[str]) -> list[str]:
    if not watch_fields:
        return []
    root_header = mdir / f"{prefix}___024root.h"
    if not root_header.is_file():
        raise FileNotFoundError(f"{root_header} not found")
    text = root_header.read_text(encoding="utf-8")
    resolved: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()
    standard_names = {
        "done_o",
        "cfg_signature_o",
        "host_req_accepted_o",
        "device_req_accepted_o",
        "device_rsp_accepted_o",
        "host_rsp_accepted_o",
        "rsp_queue_overflow_o",
        "progress_cycle_count_o",
        "progress_signature_o",
        "toggle_bitmap_word0_o",
        "toggle_bitmap_word1_o",
        "toggle_bitmap_word2_o",
        "clk_i",
        "rst_ni",
        "reset_like_w",
    }
    for raw_name in watch_fields:
        name = str(raw_name)
        if name in standard_names or name in seen:
            continue
        if re.search(rf"\b{re.escape(name)}\b", text):
            seen.add(name)
            resolved.append(name)
        else:
            missing.append(name)
    if missing:
        raise RuntimeError(
            f"watch fields not found in {root_header}: {', '.join(missing)}"
        )
    return resolved


def _rewrite_top_module_watch_fields(prefix: str, target: str, watch_fields: list[str]) -> list[str]:
    top_module = prefix[1:] if prefix.startswith("V") else prefix
    default_top = f"{target}_gpu_cov_tb"
    rewritten: list[str] = []
    for raw_name in watch_fields:
        name = str(raw_name)
        if name.startswith(f"{default_top}__DOT__") and top_module != default_top:
            rewritten.append(name.replace(f"{default_top}__DOT__", f"{top_module}__DOT__", 1))
        else:
            rewritten.append(name)
    return rewritten


def _write_watch_fields_header(mdir: Path, watch_fields: list[str]) -> Path:
    path = mdir / "tlul_slice_host_probe_watch_fields.h"
    lines = ["#pragma once"]
    if watch_fields:
        lines.append("#define EXTRA_WATCH_FIELDS(X) \\")
        for index, name in enumerate(watch_fields):
            suffix = " \\" if index + 1 < len(watch_fields) else ""
            lines.append(f'  X("{name}", {name}){suffix}')
    else:
        lines.append("#define EXTRA_WATCH_FIELDS(X)")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_probe_stdout(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    if start < 0:
        raise json.JSONDecodeError("probe stdout did not contain JSON", stdout, 0)
    return json.loads(stdout[start:])


def _build_model_archive(mdir: Path, mk_path: Path, prefix: str, env: dict[str, str]) -> str:
    base_cmd = ["make"]
    jobs_text = str(env.get("HOST_PROBE_MAKE_JOBS", "")).strip()
    if jobs_text:
        jobs = int(jobs_text, 10)
        if jobs <= 0:
            raise ValueError("HOST_PROBE_MAKE_JOBS must be a positive integer")
        base_cmd.append(f"-j{jobs}")
    base_cmd.extend(["-C", str(mdir), "-f", mk_path.name, f"lib{prefix}"])
    for name in ("OPT_FAST", "OPT_SLOW", "OPT_GLOBAL"):
        if name in env:
            base_cmd.append(f"{name}={env[name]}")
    try:
        subprocess.run(base_cmd, check=True, env=env)
        return "default_pch"
    except subprocess.CalledProcessError:
        fallback_cmd = [*base_cmd, "VK_PCH_I_FAST=", "VK_PCH_I_SLOW="]
        subprocess.run(fallback_cmd, check=True, env=env)
        return "no_pch_fallback"


def build_probe_binary(
    mdir: Path,
    binary_out: Path,
    *,
    cxx: str = "g++",
    watch_fields: list[str] | None = None,
    probe_source: Path | None = None,
    extra_defines: list[str] | None = None,
) -> tuple[Path, str, str, dict[str, Any]]:
    mdir = mdir.resolve()
    binary_out = binary_out.resolve()
    prefix = find_prefix(mdir)
    target = _derive_target(prefix)
    mk_path = mdir / f"{prefix}.mk"
    if not mk_path.is_file():
        raise FileNotFoundError(f"{mk_path} not found")
    source_path = (probe_source or PROBE_SOURCE).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"{source_path} not found")
    clk_field_name, clk_report_name, host_clock_control = _select_clock_field(mdir, prefix)
    (
        rst_field_name,
        rst_report_name,
        rst_asserted_value,
        rst_deasserted_value,
        host_reset_control,
    ) = _select_reset_field(mdir, prefix)
    resolved_watch_fields = _resolve_watch_fields(mdir, prefix, list(watch_fields or []))
    watch_header = _write_watch_fields_header(mdir, resolved_watch_fields)

    env = os.environ.copy()
    env.setdefault("VERILATOR_ROOT", str(VERILATOR_ROOT))
    model_build_mode = _build_model_archive(mdir, mk_path, prefix, env)

    binary_out.parent.mkdir(parents=True, exist_ok=True)
    compile_cmd = [
        cxx,
        "-std=c++20",
        "-O2",
        "-Wall",
        "-Wextra",
        f"-I{mdir}",
        "-isystem",
        str(VERILATOR_ROOT / "include"),
        "-isystem",
        str(VERILATOR_ROOT / "include" / "vltstd"),
        f'-DMODEL_HEADER="{prefix}.h"',
        f'-DROOT_HEADER="{prefix}___024root.h"',
        f"-DMODEL_CLASS={prefix}",
        f"-DROOT_CLASS={prefix}___024root",
        f"-DROOT_CLK_FIELD={clk_field_name}",
        f"-DROOT_RST_FIELD={rst_field_name}",
        f'-DROOT_CLK_REPORT_NAME="{clk_report_name}"',
        f'-DROOT_RST_REPORT_NAME="{rst_report_name}"',
        f"-DROOT_RST_ASSERTED_VALUE={rst_asserted_value}U",
        f"-DROOT_RST_DEASSERTED_VALUE={rst_deasserted_value}U",
        f"-DHOST_CLOCK_CONTROL={1 if host_clock_control else 0}",
        f"-DHOST_RESET_CONTROL={1 if host_reset_control else 0}",
        f'-DEXTRA_WATCH_FIELDS_HEADER="{watch_header.name}"',
        f'-DTARGET_NAME="{target}"',
    ]
    if extra_defines:
        compile_cmd.extend(list(extra_defines))
    compile_cmd.extend(
        [
        str(source_path),
        str(mdir / f"lib{prefix}.a"),
        str(mdir / "libverilated.a"),
        "-pthread",
        "-o",
        str(binary_out),
        ]
    )
    subprocess.run(compile_cmd, check=True)
    return (
        binary_out,
        prefix,
        target,
        {
            "clock_field_name": clk_field_name,
            "clock_report_name": clk_report_name,
            "host_clock_control": host_clock_control,
            "reset_field_name": rst_field_name,
            "reset_report_name": rst_report_name,
            "host_reset_control": host_reset_control,
            "model_build_mode": model_build_mode,
        },
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mdir", type=Path, default=DEFAULT_MDIR)
    p.add_argument("--binary-out", type=Path)
    p.add_argument("--json-out", type=Path)
    p.add_argument("--state-out", type=Path)
    p.add_argument(
        "--clock-sequence",
        help="Optional comma-separated 0/1 host-owned clock levels to replay inside the probe",
    )
    p.add_argument(
        "--edge-state-dir",
        type=Path,
        help="Optional directory for host-only per-edge state dumps; requires --clock-sequence",
    )
    p.add_argument("--template", type=Path, help="Optional launch template for driver defaults")
    p.add_argument("--watch-field", action="append", default=[], metavar="FIELD_NAME")
    p.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    p.add_argument("--extra-define", action="append", default=[], metavar="DEFINE")
    p.add_argument("--program-entries-bin", type=Path)
    p.add_argument("--memory-image", type=Path)
    p.add_argument("--memory-image-target", type=Path)
    p.add_argument("--cfg-valid", type=int, choices=(0, 1), default=1)
    p.add_argument("--reset-cycles", type=int, default=4)
    p.add_argument("--post-reset-cycles", type=int, default=2)
    p.add_argument("--build-only", action="store_true")
    args = p.parse_args()
    if args.memory_image is not None and args.memory_image_target is None:
        p.error("--memory-image requires --memory-image-target")
    if args.memory_image_target is not None and args.memory_image is None and not args.build_only:
        p.error("--memory-image-target requires --memory-image unless --build-only is set")

    mdir = args.mdir.resolve()
    prefix = find_prefix(mdir)
    target = _derive_target(prefix)
    template_path = (
        args.template.resolve()
        if args.template is not None
        else (DEFAULT_TEMPLATE_DIR / f"{target}.json").resolve()
    )
    watch_fields = _load_template_watch_fields(template_path if template_path.is_file() else None)
    watch_fields = _rewrite_top_module_watch_fields(prefix, target, watch_fields)
    for raw_name in args.watch_field:
        name = str(raw_name)
        if name not in watch_fields:
            watch_fields.append(name)
    binary_out = (args.binary_out or (mdir / DEFAULT_BINARY)).resolve()
    all_extra_defines = list(args.extra_define)
    if args.memory_image_target is not None:
        all_extra_defines.extend(
            _memory_image_extra_defines(
                mdir,
                prefix,
                args.memory_image_target.resolve(),
            )
        )
    binary_path, _, target, control_meta = build_probe_binary(
        mdir, binary_out, watch_fields=watch_fields, extra_defines=all_extra_defines
    )
    if args.build_only:
        print(binary_path)
        return

    settings = _load_template_settings(template_path if template_path.is_file() else None)
    settings["cfg_valid_i"] = int(args.cfg_valid)
    settings = _apply_overrides(settings, list(args.set))

    cmd = [
        str(binary_path),
        "--reset-cycles",
        str(args.reset_cycles),
        "--post-reset-cycles",
        str(args.post_reset_cycles),
    ]
    state_out = args.state_out.resolve() if args.state_out else None
    if state_out is not None:
        state_out.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--state-out", str(state_out)])
    if args.clock_sequence:
        cmd.extend(["--clock-sequence", args.clock_sequence])
    if args.edge_state_dir is not None:
        edge_state_dir = args.edge_state_dir.resolve()
        edge_state_dir.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--edge-state-dir", str(edge_state_dir)])
    for name in sorted(settings):
        cmd.extend(["--set", f"{name}={settings[name]}"])
    if args.program_entries_bin is not None:
        cmd.extend(["--program-entries-bin", str(args.program_entries_bin.resolve())])
    if args.memory_image is not None:
        cmd.extend(["--memory-image", str(args.memory_image.resolve())])

    result = subprocess.run(cmd, check=True, text=True, capture_output=True, cwd=mdir)
    payload = _parse_probe_stdout(result.stdout)
    payload["configured_inputs"] = settings
    payload["host_clock_control"] = bool(control_meta["host_clock_control"])
    payload["host_reset_control"] = bool(control_meta["host_reset_control"])
    payload["clock_field_name"] = str(control_meta["clock_field_name"])
    payload["reset_field_name"] = payload.get("reset_field_name") or str(
        control_meta["reset_report_name"]
    )
    payload["model_build_mode"] = str(control_meta["model_build_mode"])
    payload["clock_ownership"] = (
        "host_direct_ports" if payload["host_clock_control"] else "tb_timed_coroutine"
    )
    payload["template_path"] = str(template_path) if template_path.is_file() else None
    payload["probe_binary"] = str(binary_path)
    payload["mdir"] = str(mdir)
    payload["watch_field_names"] = watch_fields
    payload["extra_defines"] = all_extra_defines
    payload["program_entries_bin"] = (
        str(args.program_entries_bin.resolve()) if args.program_entries_bin is not None else None
    )
    payload["memory_image"] = (
        str(args.memory_image.resolve()) if args.memory_image is not None else None
    )
    payload["memory_image_target"] = (
        str(args.memory_image_target.resolve()) if args.memory_image_target is not None else None
    )
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        _write_json(args.json_out.resolve(), payload)
    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
