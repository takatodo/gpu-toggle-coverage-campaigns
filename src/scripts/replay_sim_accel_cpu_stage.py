#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


CPP_TEMPLATE = r"""
#include <cstdint>
#include <cstddef>
#include <vector>

static std::vector<uint32_t> g_preload_depths;
static std::vector<std::vector<uint64_t>> g_preload_storage;
static uint32_t g_preload_nstates = 0;

extern "C" uint32_t sim_accel_replay_configure_targets(uint32_t target_count,
                                                       const uint32_t* depths) {
    g_preload_depths.assign(depths, depths + target_count);
    g_preload_storage.clear();
    g_preload_storage.resize(target_count);
    for (uint32_t i = 0; i < target_count; ++i) {
        g_preload_storage[i].assign(static_cast<size_t>(g_preload_depths[i]) * g_preload_nstates,
                                    0ULL);
    }
    return target_count;
}

extern "C" uint64_t sim_accel_eval_preload_target_runtime_word(
    uint32_t index, uint32_t state_index, uint32_t word_index) {
    if (index >= g_preload_storage.size()) return 0ULL;
    if (state_index >= g_preload_nstates) return 0ULL;
    if (word_index >= g_preload_depths[index]) return 0ULL;
    const size_t linear_index = static_cast<size_t>(state_index) * g_preload_depths[index]
                              + word_index;
    return g_preload_storage[index][linear_index];
}

extern "C" uint32_t sim_accel_eval_preload_runtime_state_count() {
    return g_preload_nstates;
}

extern "C" uint32_t sim_accel_eval_preload_runtime_resize(uint32_t nstates) {
    g_preload_nstates = nstates;
    for (size_t i = 0; i < g_preload_storage.size(); ++i) {
        g_preload_storage[i].assign(static_cast<size_t>(g_preload_depths[i]) * g_preload_nstates,
                                    0ULL);
    }
    return g_preload_nstates;
}

extern "C" uint32_t sim_accel_eval_preload_target_apply_word_range(
    uint32_t index, uint32_t state_begin, uint32_t state_count, uint32_t word_index,
    uint64_t value) {
    if (index >= g_preload_storage.size()) return 0U;
    if (word_index >= g_preload_depths[index]) return 0U;
    uint32_t applied = 0U;
    for (uint32_t state = 0; state < state_count; ++state) {
        const uint32_t state_index = state_begin + state;
        if (state_index >= g_preload_nstates) break;
        const size_t linear_index =
            static_cast<size_t>(state_index) * g_preload_depths[index] + word_index;
        g_preload_storage[index][linear_index] = value;
        ++applied;
    }
    return applied;
}

#include "__CPU_CPP_PATH__"
"""


DEFAULT_SELECTED_NAMES = [
    "focused_wave_word0_o",
    "focused_wave_word1_o",
    "focused_wave_word4_o",
    "focused_wave_word5_o",
    "focused_wave_word6_o",
    "focused_wave_word7_o",
    "real_toggle_subset_word0_o",
    "real_toggle_subset_word1_o",
    "real_toggle_subset_word2_o",
    "real_toggle_subset_word3_o",
    "veer_el2_gpu_cov_tb__DOT__dut__DOT__gpu_cov_program_loaded_q",
    "veer_el2_gpu_cov_tb__DOT__dut__DOT__gpu_cov_reset_phase_q",
    "veer_el2_gpu_cov_tb__DOT__dut__DOT__gpu_cov_porst_l_w",
    "veer_el2_gpu_cov_tb__DOT__dut__DOT__gpu_cov_rst_l_w",
    "veer_el2_gpu_cov_tb__DOT__dut__DOT__rvtop_wrapper__DOT__rvtop__DOT__core_rst_l",
]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Replay a generated sim-accel CPU artifact with optional init/preload injection."
    )
    ap.add_argument("--build-dir", type=Path, required=True)
    ap.add_argument("--cycles", type=int, default=2140)
    ap.add_argument("--nstates", type=int, default=1)
    ap.add_argument("--apply-gpu-init", action="store_true")
    ap.add_argument("--apply-program-payload", action="store_true")
    ap.add_argument("--apply-program-direct", action="store_true")
    ap.add_argument("--apply-program-preload", action="store_true")
    ap.add_argument("--selected-name", action="append", default=[])
    ap.add_argument("--json-out", type=Path)
    return ap.parse_args()


def load_vars(vars_path: Path) -> list[dict[str, str]]:
    with vars_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_preload_targets(json_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    return list(payload.get("targets", []))


def build_shared_object(build_dir: Path) -> Path:
    cpu_cpp = (build_dir / "kernel_generated.cpu.cpp").resolve()
    work_dir = build_dir / "_cpu_replay"
    work_dir.mkdir(parents=True, exist_ok=True)
    src_path = work_dir / "cpu_replay.cc"
    so_path = work_dir / "cpu_replay.so"
    src_path.write_text(
        CPP_TEMPLATE.replace("__CPU_CPP_PATH__", str(cpu_cpp)),
        encoding="utf-8",
    )
    cmd = [
        "g++",
        "-std=c++17",
        "-O0",
        "-shared",
        "-fPIC",
        str(src_path),
        "-o",
        str(so_path),
    ]
    subprocess.run(cmd, check=True, cwd=work_dir)
    return so_path


def configure_library(lib: ctypes.CDLL, targets: list[dict[str, Any]], nstates: int) -> list[int]:
    lib.sim_accel_replay_configure_targets.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
    lib.sim_accel_replay_configure_targets.restype = ctypes.c_uint32
    lib.sim_accel_eval_preload_runtime_resize.argtypes = [ctypes.c_uint32]
    lib.sim_accel_eval_preload_runtime_resize.restype = ctypes.c_uint32
    depths = [int(target.get("depth", 0)) for target in targets]
    lib.sim_accel_eval_preload_runtime_resize(nstates)
    array_ty = ctypes.c_uint32 * len(depths)
    depth_arr = array_ty(*depths)
    lib.sim_accel_replay_configure_targets(len(depths), depth_arr)
    lib.sim_accel_eval_preload_target_apply_word_range.argtypes = [
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint64,
    ]
    lib.sim_accel_eval_preload_target_apply_word_range.restype = ctypes.c_uint32
    lib.sim_accel_eval_preload_target_runtime_word.argtypes = [
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
    ]
    lib.sim_accel_eval_preload_target_runtime_word.restype = ctypes.c_uint64
    lib.sim_accel_eval_assignw_cpu_ref.argtypes = [
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.c_uint32,
    ]
    lib.sim_accel_eval_assignw_cpu_ref.restype = None
    return depths


def apply_init_lines(state: list[int], rows: list[dict[str, str]], nstates: int, init_path: Path) -> int:
    by_name = {row["name"]: index for index, row in enumerate(rows)}
    applied = 0
    for line in init_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(None, 1)
        if len(parts) != 2:
            continue
        name, raw_value = parts
        if name not in by_name:
            continue
        value = int(raw_value, 0)
        var_index = by_name[name]
        for tid in range(nstates):
            state[var_index * nstates + tid] = value
        applied += 1
    return applied


def apply_payload_tsv(lib: ctypes.CDLL, targets: list[dict[str, Any]], nstates: int, payload_path: Path) -> int:
    target_by_path = {target.get("target_path"): index for index, target in enumerate(targets)}
    applied = 0
    with payload_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            target_index = target_by_path.get(row.get("target_path", ""))
            if target_index is None:
                continue
            word_index = int(row["word_index"], 0)
            value = int(row["value_hex"], 16)
            applied += int(
                lib.sim_accel_eval_preload_target_apply_word_range(
                    target_index, 0, nstates, word_index, value
                )
            )
    return applied


def apply_direct_tsv(state: list[int], rows: list[dict[str, str]], nstates: int, direct_path: Path) -> int:
    by_name = {row["name"]: index for index, row in enumerate(rows)}
    applied = 0
    with direct_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            name = row.get("var_name", "")
            if name not in by_name:
                continue
            var_index = by_name[name]
            value = int(row["value"], 0)
            for tid in range(nstates):
                state[var_index * nstates + tid] = value
            applied += 1
    return applied


def collect_selected(state: list[int], rows: list[dict[str, str]], nstates: int, selected_names: list[str]) -> dict[str, dict[str, Any]]:
    by_name = {row["name"]: index for index, row in enumerate(rows)}
    result: dict[str, dict[str, Any]] = {}
    for name in selected_names:
        if name not in by_name:
            continue
        var_index = by_name[name]
        values = [int(state[var_index * nstates + tid]) for tid in range(nstates)]
        value_or = 0
        for value in values:
            value_or |= value
        result[name] = {
            "var_index": var_index,
            "state_values": values,
            "or_reduce": value_or,
        }
    return result


def collect_nonzero_preload(lib: ctypes.CDLL, targets: list[dict[str, Any]], nstates: int, depths: list[int], limit: int = 32) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for target_index, target in enumerate(targets):
        depth = depths[target_index]
        nonzero_words: list[dict[str, Any]] = []
        for word_index in range(depth):
            value = int(lib.sim_accel_eval_preload_target_runtime_word(target_index, 0, word_index))
            if value != 0:
                nonzero_words.append({"word_index": word_index, "value": value})
                if len(nonzero_words) >= limit:
                    break
        if nonzero_words:
            out.append(
                {
                    "target_index": target_index,
                    "target_path": target.get("target_path", ""),
                    "word_bits": int(target.get("word_bits", 0)),
                    "nonzero_words": nonzero_words,
                }
            )
    return out


def main() -> int:
    ns = parse_args()
    build_dir = ns.build_dir.resolve()
    vars_path = build_dir / "kernel_generated.vars.tsv"
    preload_targets_path = build_dir / "veer_el2_gpu_cov_tb.sim_accel.kernel.cu.preload_targets.json"
    if not preload_targets_path.exists():
        preload_targets_path = build_dir / "kernel_generated.preload_targets.json"
    if not vars_path.exists():
        raise SystemExit(f"missing vars.tsv: {vars_path}")
    if not preload_targets_path.exists():
        raise SystemExit(f"missing preload target metadata: {preload_targets_path}")

    rows = load_vars(vars_path)
    targets = load_preload_targets(preload_targets_path)
    so_path = build_shared_object(build_dir)
    lib = ctypes.CDLL(str(so_path))
    depths = configure_library(lib, targets, int(ns.nstates))

    nvars = len(rows)
    total_words = nvars * int(ns.nstates)
    state_in = [0] * total_words
    state_out = [0] * total_words

    applied_gpu_init = 0
    if ns.apply_gpu_init:
        gpu_init = build_dir / "gpu_driver.init"
        if gpu_init.exists():
            applied_gpu_init = apply_init_lines(state_in, rows, int(ns.nstates), gpu_init)

    applied_direct = 0
    if ns.apply_program_direct:
        direct_tsv = build_dir / "program_hex.direct.tsv"
        if direct_tsv.exists():
            applied_direct = apply_direct_tsv(state_in, rows, int(ns.nstates), direct_tsv)

    applied_payload = 0
    if ns.apply_program_payload:
        payload_tsv = build_dir / "program_hex.payload.tsv"
        if payload_tsv.exists():
            applied_payload = apply_payload_tsv(lib, targets, int(ns.nstates), payload_tsv)

    applied_preload = 0
    if ns.apply_program_preload:
        preload_tsv = build_dir / "program_hex.preload.tsv"
        if preload_tsv.exists():
            applied_preload = apply_direct_tsv(state_in, rows, int(ns.nstates), preload_tsv)

    array_in = (ctypes.c_uint64 * total_words)(*state_in)
    array_out = (ctypes.c_uint64 * total_words)(*state_out)
    for _ in range(int(ns.cycles)):
        lib.sim_accel_eval_assignw_cpu_ref(array_in, array_out, int(ns.nstates))
        array_in, array_out = array_out, array_in

    final_state = [int(array_in[i]) for i in range(total_words)]
    selected_names = ns.selected_name or DEFAULT_SELECTED_NAMES
    summary = {
        "build_dir": str(build_dir),
        "cycles": int(ns.cycles),
        "nstates": int(ns.nstates),
        "nvars": nvars,
        "applied_gpu_init_lines": applied_gpu_init,
        "applied_program_direct_values": applied_direct,
        "applied_program_payload_values": applied_payload,
        "applied_program_preload_values": applied_preload,
        "selected": collect_selected(final_state, rows, int(ns.nstates), selected_names),
        "nonzero_preload_runtime_words": collect_nonzero_preload(
            lib, targets, int(ns.nstates), depths
        ),
    }

    payload = json.dumps(summary, indent=2, sort_keys=True)
    if ns.json_out:
        ns.json_out.write_text(payload + "\n", encoding="utf-8")
        print(ns.json_out)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
