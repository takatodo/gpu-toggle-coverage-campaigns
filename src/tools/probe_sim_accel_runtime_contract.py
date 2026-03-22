#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _find_top_module(build_dir: Path, summary: dict[str, Any]) -> str:
    for candidate in (
        summary.get("compile_desc", {}).get("topModule"),
        summary.get("pre_gpu_gate", {}).get("top_module"),
    ):
        if candidate:
            return str(candidate)
    vars_matches = sorted(build_dir.glob("*.sim_accel.kernel.cu.vars.tsv"))
    if vars_matches:
        stem = vars_matches[0].name
        return stem.split(".sim_accel.kernel.cu.vars.tsv", 1)[0]
    return ""


def _find_candidate_lines(lines: list[str], patterns: list[str], limit: int = 32) -> list[str]:
    lowered = [pattern.lower() for pattern in patterns]
    matches: list[str] = []
    for line in lines:
        text = line.lower()
        if any(pattern in text for pattern in lowered):
            matches.append(line)
        if len(matches) >= limit:
            break
    return matches


def _truthy_runtime_inputs(runtime_inputs: dict[str, Any]) -> dict[str, str]:
    keys = [
        "program_hex",
        "program_hex_target",
        "memory_image",
        "memory_image_target",
        "case_pat",
    ]
    out: dict[str, str] = {}
    for key in keys:
        value = str(runtime_inputs.get(key) or "").strip()
        if value:
            out[key] = value
    return out


def probe_build_dir(build_dir: Path) -> dict[str, Any]:
    summary = _read_json(build_dir / "summary.json")
    top_module = _find_top_module(build_dir, summary)
    filelist_path = build_dir / "filelist"
    filelist_lines = _read_text(filelist_path).splitlines()
    execute_files = [str(item) for item in summary.get("execute_files") or []]
    execute_file_names = [Path(item).name for item in execute_files]
    runtime_inputs = dict(summary.get("execute_runtime_inputs") or {})
    truthy_runtime_inputs = _truthy_runtime_inputs(runtime_inputs)

    cpu_cpp_path = build_dir / f"{top_module}.sim_accel.kernel.cu.cpu.cpp"
    cpu_cpp_text = _read_text(cpu_cpp_path)
    preload_targets_tsv = build_dir / f"{top_module}.sim_accel.kernel.cu.preload_targets.tsv"
    preload_targets_lines = _read_text(preload_targets_tsv).splitlines()
    preload_elements_tsv = build_dir / f"{top_module}.sim_accel.kernel.cu.preload_target_elements.tsv"
    preload_elements_lines = _read_text(preload_elements_tsv).splitlines()

    helper_hits = {
        "memrw_helper_in_filelist": any("MemRWHelper.v" in line for line in filelist_lines),
        "flash_helper_in_filelist": any("FlashHelper.v" in line for line in filelist_lines),
    }
    dpi_loader_tokens = {
        "cpu_cpp_has_ram_read": "ram_read" in cpu_cpp_text,
        "cpu_cpp_has_ram_write": "ram_write" in cpu_cpp_text,
        "cpu_cpp_has_flash_read": "flash_read" in cpu_cpp_text,
        "cpu_cpp_has_program_bin": "program.bin" in cpu_cpp_text,
    }

    preload_target_hits = {
        "top_memory_targets": _find_candidate_lines(
            preload_targets_lines,
            ["top.memory", "rdata_mem", "memory.ram"],
        ),
        "flash_targets": _find_candidate_lines(
            preload_targets_lines,
            ["flash"],
        ),
        "top_memory_elements": _find_candidate_lines(
            preload_elements_lines,
            ["top.memory", "rdata_mem", "memory.ram"],
        ),
        "flash_elements": _find_candidate_lines(
            preload_elements_lines,
            ["flash"],
        ),
    }

    issues: list[str] = []
    hypotheses: list[str] = []
    program_bin_staged = "program.bin" in execute_file_names
    if program_bin_staged and not truthy_runtime_inputs:
        issues.append("program_bin_staged_without_runtime_materialization")
    if helper_hits["memrw_helper_in_filelist"] and not (
        dpi_loader_tokens["cpu_cpp_has_ram_read"] or dpi_loader_tokens["cpu_cpp_has_ram_write"]
    ):
        issues.append("memrw_helper_present_but_no_ram_dpi_tokens_in_sim_accel_cpu_cpp")
    if helper_hits["flash_helper_in_filelist"] and not dpi_loader_tokens["cpu_cpp_has_flash_read"]:
        issues.append("flash_helper_present_but_no_flash_dpi_token_in_sim_accel_cpu_cpp")
    if program_bin_staged and not preload_target_hits["top_memory_targets"] and not preload_target_hits["top_memory_elements"]:
        issues.append("no_exposed_top_memory_preload_target_for_program_bin")

    if (
        program_bin_staged
        and "program_bin_staged_without_runtime_materialization" in issues
        and "memrw_helper_present_but_no_ram_dpi_tokens_in_sim_accel_cpu_cpp" in issues
    ):
        hypotheses.append("sim_accel_runtime_likely_skips_program_bin_dpi_ram_loader_contract")
    if (
        helper_hits["flash_helper_in_filelist"]
        and "flash_helper_present_but_no_flash_dpi_token_in_sim_accel_cpu_cpp" in issues
    ):
        hypotheses.append("sim_accel_runtime_likely_skips_flash_dpi_helper_contract")
    if (
        program_bin_staged
        and "no_exposed_top_memory_preload_target_for_program_bin" in issues
    ):
        hypotheses.append("current_preload_target_inventory_cannot_reproduce_plain_program_bin_ram_load")

    return {
        "schema_version": "sim-accel-runtime-contract-probe-v1",
        "build_dir": str(build_dir),
        "top_module": top_module,
        "execute_file_names": execute_file_names,
        "runtime_inputs_truthy": truthy_runtime_inputs,
        "helper_hits": helper_hits,
        "dpi_loader_tokens": dpi_loader_tokens,
        "preload_target_hits": preload_target_hits,
        "issues": issues,
        "hypotheses": hypotheses,
        "status": (
            "contract_gap_likely"
            if hypotheses
            else ("needs_review" if issues else "no_obvious_gap_detected")
        ),
    }


def _write_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Sim-Accel Runtime Contract Probe",
        "",
        f"- status: `{payload['status']}`",
        f"- build_dir: `{payload['build_dir']}`",
        f"- top_module: `{payload['top_module']}`",
        "",
        "## Execute Files",
        "",
    ]
    for name in payload["execute_file_names"]:
        lines.append(f"- `{name}`")
    lines.extend(["", "## Runtime Inputs", ""])
    truthy = payload["runtime_inputs_truthy"]
    if truthy:
        for key, value in truthy.items():
            lines.append(f"- `{key}`: `{value}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Issues", ""])
    issues = payload["issues"]
    if issues:
        for item in issues:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Hypotheses", ""])
    hypotheses = payload["hypotheses"]
    if hypotheses:
        for item in hypotheses:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Evidence", ""])
    helper_hits = payload["helper_hits"]
    dpi_loader_tokens = payload["dpi_loader_tokens"]
    lines.append(f"- filelist contains `MemRWHelper.v`: `{helper_hits['memrw_helper_in_filelist']}`")
    lines.append(f"- filelist contains `FlashHelper.v`: `{helper_hits['flash_helper_in_filelist']}`")
    lines.append(f"- sim-accel cpu.cpp has `ram_read`: `{dpi_loader_tokens['cpu_cpp_has_ram_read']}`")
    lines.append(f"- sim-accel cpu.cpp has `ram_write`: `{dpi_loader_tokens['cpu_cpp_has_ram_write']}`")
    lines.append(f"- sim-accel cpu.cpp has `flash_read`: `{dpi_loader_tokens['cpu_cpp_has_flash_read']}`")
    lines.append(f"- sim-accel cpu.cpp has `program.bin`: `{dpi_loader_tokens['cpu_cpp_has_program_bin']}`")
    for label in ("top_memory_targets", "flash_targets", "top_memory_elements", "flash_elements"):
        lines.extend(["", f"### {label}", ""])
        values = payload["preload_target_hits"].get(label) or []
        if values:
            for item in values:
                lines.append(f"- `{item}`")
        else:
            lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Probe sim-accel runtime contract gaps from an existing build dir.")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--md-out", type=Path, required=True)
    args = parser.parse_args(argv)

    payload = probe_build_dir(args.build_dir.resolve())
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_md(args.md_out, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
