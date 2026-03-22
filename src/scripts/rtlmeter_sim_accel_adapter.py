#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shlex
import struct
import subprocess
import sys
from typing import Any, Iterable


_SCRIPT_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _SCRIPT_DIR.parent.parent
DEFAULT_VERILATOR = str(_ROOT_DIR / "third_party/verilator/bin/verilator")
DEFAULT_BENCH = str(_ROOT_DIR / "third_party/verilator/bin/verilator_sim_accel_bench")

SKIP_FLAGS = {
    "--cc",
    "--main",
    "--exe",
    "--quiet-stats",
    "-Wno-fatal",
    "--autoflush",
}
SKIP_WITH_VALUE = {
    "--prefix",
    "--top-module",
}


def split_args(argv: list[str]) -> tuple[list[str], list[str]]:
    if "--" not in argv:
        return argv, []
    idx = argv.index("--")
    return argv[:idx], argv[idx + 1 :]


def parse_cli(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    own_argv, bench_argv = split_args(argv)
    parser = argparse.ArgumentParser(
        description=(
            "Run verilator_sim_accel_bench from an RTLMeter compile workspace and emit a JSON summary."
        )
    )
    parser.add_argument("--compile-dir", required=True, help="RTLMeter compile-0 directory")
    parser.add_argument("--bench-outdir", required=True, help="Output directory for sim-accel bench")
    parser.add_argument("--verilator", default=DEFAULT_VERILATOR, help="Verilator binary")
    parser.add_argument("--bench", default=DEFAULT_BENCH, help="verilator_sim_accel_bench path")
    parser.add_argument("--json-out", default="", help="Write summary JSON to this path")
    parser.add_argument(
        "--execute-dir",
        default="",
        help="Optional RTLMeter _execute directory to include execute time/stdout summary",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print resolved bench command only")
    ns = parser.parse_args(own_argv)
    return ns, bench_argv


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(load_text(path))


def _parse_optional_decimal(raw: str) -> int | None:
    text = raw.strip()
    if not text or text == "-":
        return None
    return int(text, 10)


def load_sim_accel_var_rows(vars_path: Path) -> list[dict[str, str]]:
    with vars_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_sim_accel_comm_rows(comm_path: Path) -> list[dict[str, str]]:
    with comm_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def collect_sim_accel_output_slots(
    vars_path: Path,
    comm_path: Path | None = None,
    *,
    selected_names: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    selected_name_set = set(selected_names) if selected_names is not None else None
    vars_by_name = {row.get("name", ""): row for row in load_sim_accel_var_rows(vars_path)}
    rows: list[dict[str, Any]] = []
    if comm_path is not None:
        for row in load_sim_accel_comm_rows(comm_path):
            if row.get("direction") != "gpu_to_cpu":
                continue
            slot = _parse_optional_decimal(row.get("slot", ""))
            if slot is None:
                continue
            name = row.get("name", "")
            if selected_name_set is not None and name not in selected_name_set:
                continue
            var_row = vars_by_name.get(name, {})
            width = _parse_optional_decimal(row.get("width", "")) or _parse_optional_decimal(
                var_row.get("width", "")
            ) or 64
            rows.append({
                "index": _parse_optional_decimal(var_row.get("index", "")),
                "name": name,
                "hierarchy": var_row.get("hierarchy", ""),
                "direction": var_row.get("direction", ""),
                "width": width,
                "output_slot": slot,
                "is_primary_io": var_row.get("is_primary_io", "") == "1",
                "var_idx": _parse_optional_decimal(row.get("var_idx", "")),
                "is_cpu_visible": row.get("is_cpu_visible", "") == "1",
            })
        rows.sort(key=lambda entry: int(entry["output_slot"]))
        return rows

    for row in vars_by_name.values():
        output_slot = _parse_optional_decimal(row.get("output_slot", ""))
        if output_slot is None:
            continue
        name = row.get("name", "")
        if selected_name_set is not None and name not in selected_name_set:
            continue
        width = _parse_optional_decimal(row.get("width", "")) or 64
        rows.append({
            "index": _parse_optional_decimal(row.get("index", "")),
            "name": name,
            "hierarchy": row.get("hierarchy", ""),
            "direction": row.get("direction", ""),
            "width": width,
            "output_slot": output_slot,
            "is_primary_io": row.get("is_primary_io", "") == "1",
            "var_idx": None,
            "is_cpu_visible": row.get("is_cpu_visible", "") == "1",
        })
    rows.sort(key=lambda entry: int(entry["output_slot"]))
    return rows


def load_sim_accel_compact_u64(compact_path: Path) -> list[int]:
    payload = compact_path.read_bytes()
    if len(payload) % 8 != 0:
        raise ValueError(
            f"Compact output payload must be a multiple of 8 bytes: {compact_path} "
            f"(got {len(payload)} bytes)"
        )
    return [word for (word,) in struct.iter_unpack("<Q", payload)]


def _load_sim_accel_selected_slots_u64(
    compact_path: Path,
    *,
    slots: list[int],
    nstates: int,
    dense_slots: bool,
) -> list[list[int]]:
    slot_word_count = int(nstates)
    slot_byte_count = slot_word_count * 8
    total_bytes = compact_path.stat().st_size
    if total_bytes % 8 != 0:
        raise ValueError(
            f"Compact output payload must be a multiple of 8 bytes: {compact_path} "
            f"(got {total_bytes} bytes)"
        )
    total_words = total_bytes // 8
    if dense_slots:
        expected_words = len(slots) * slot_word_count
        if total_words != expected_words:
            raise ValueError(
                f"Dense compact output payload length mismatch: expected {expected_words} u64 words "
                f"for {len(slots)} selected output slots x {nstates} states, got {total_words}"
            )
    elif slots:
        required_words = (max(slots) + 1) * slot_word_count
        if total_words < required_words:
            raise ValueError(
                f"Compact output payload length too short for selected slots: need at least "
                f"{required_words} u64 words for max slot {max(slots)}, got {total_words}"
            )
    extracted: list[list[int]] = []
    with compact_path.open("rb") as handle:
        for dense_idx, slot in enumerate(slots):
            word_offset = dense_idx * slot_word_count if dense_slots else slot * slot_word_count
            handle.seek(word_offset * 8)
            payload = handle.read(slot_byte_count)
            if len(payload) != slot_byte_count:
                raise ValueError(
                    f"Compact output payload truncated while reading slot {slot}: "
                    f"expected {slot_byte_count} bytes, got {len(payload)}"
                )
            extracted.append([word for (word,) in struct.iter_unpack("<Q", payload)])
    return extracted


def extract_sim_accel_output_slot_values(
    compact_path: Path,
    vars_path: Path,
    *,
    comm_path: Path | None = None,
    nstates: int,
    selected_names: Iterable[str] | None = None,
    dense_selected_names: bool = False,
) -> list[dict[str, Any]]:
    slot_rows = collect_sim_accel_output_slots(
        vars_path,
        comm_path=comm_path,
        selected_names=selected_names,
    )
    if not slot_rows:
        return []
    slot_count = int(slot_rows[-1]["output_slot"]) + 1
    expected_words = slot_count * nstates
    if selected_names is None:
        values = load_sim_accel_compact_u64(compact_path)
        if len(values) != expected_words:
            raise ValueError(
                f"Compact output payload length mismatch: expected {expected_words} u64 words "
                f"for {slot_count} output slots x {nstates} states, got {len(values)}"
            )
        extracted: list[dict[str, Any]] = []
        for row in slot_rows:
            slot = int(row["output_slot"])
            state_values = values[slot * nstates:(slot + 1) * nstates]
            entry = dict(row)
            entry["state_values"] = state_values
            extracted.append(entry)
        return extracted

    total_words = compact_path.stat().st_size // 8
    dense_word_count = len(slot_rows) * nstates
    use_dense_slots = bool(total_words == dense_word_count)
    if not use_dense_slots and nstates > 0 and total_words % nstates == 0:
        dense_prefix_count = total_words // nstates
        if 0 < dense_prefix_count < len(slot_rows):
            slot_rows = slot_rows[:dense_prefix_count]
            use_dense_slots = True
    selected_slot_values = _load_sim_accel_selected_slots_u64(
        compact_path,
        slots=[int(row["output_slot"]) for row in slot_rows],
        nstates=nstates,
        dense_slots=use_dense_slots,
    )
    extracted = []
    for row, state_values in zip(slot_rows, selected_slot_values):
        entry = dict(row)
        entry["state_values"] = state_values
        extracted.append(entry)
    return extracted


def find_cmd_line(cmd_file: Path) -> str:
    for line in load_text(cmd_file).splitlines():
        line = line.strip()
        if not line or line.startswith("#!"):
            continue
        return line
    raise RuntimeError(f"No command line found in {cmd_file}")


def recover_verilator_args(cmd_file: Path) -> tuple[str, list[str], list[str]]:
    cmd_line = find_cmd_line(cmd_file)
    tokens = shlex.split(cmd_line)
    if not tokens:
        raise RuntimeError(f"Empty command line in {cmd_file}")
    if Path(tokens[0]).name == "verilator":
        tokens = tokens[1:]
    top_module = ""
    passthrough: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in {"$@", '"$@"'} or "$@" in tok:
            i += 1
            continue
        if tok in SKIP_FLAGS:
            i += 1
            continue
        if tok in SKIP_WITH_VALUE:
            if i + 1 >= len(tokens):
                raise RuntimeError(f"Missing value for {tok} in {cmd_file}")
            if tok == "--top-module":
                top_module = tokens[i + 1]
            i += 2
            continue
        passthrough.append(tok)
        if tok == "-f" and i + 1 < len(tokens):
            passthrough.append(tokens[i + 1])
            i += 2
            continue
        i += 1
    if not top_module:
        raise RuntimeError(f"Unable to recover --top-module from {cmd_file}")
    return top_module, passthrough, tokens


def parse_bench_log(log_file: Path) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for raw in load_text(log_file).splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        parsed: Any = value
        if value.endswith("x"):
            core = value[:-1]
            try:
                parsed = float(core)
            except ValueError:
                parsed = value
        else:
            try:
                if value.lower().startswith("0x"):
                    parsed = int(value, 16)
                else:
                    parsed = int(value)
            except ValueError:
                try:
                    parsed = float(value)
                except ValueError:
                    parsed = value
        metrics[key] = parsed
    return metrics


def summarize_execute_dir(execute_dir: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {"path": str(execute_dir)}
    time_file = execute_dir / "time.json"
    if time_file.exists():
        summary["time"] = load_json(time_file)
    stdout_file = execute_dir / "stdout.log"
    if stdout_file.exists():
        lines = load_text(stdout_file).splitlines()
        summary["stdout_tail"] = lines[-20:]
        summary["passed"] = any("PASS" in line for line in lines)
    return summary


def metric(metrics: dict[str, Any], key: str, default: Any = None) -> Any:
    return metrics.get(key, default)


def collect_prefixed(metrics: dict[str, Any], prefix: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in metrics.items():
        if key.startswith(prefix):
            result[key[len(prefix) :]] = value
    return result


def normalize_rtlmeter_time(block: dict[str, Any]) -> dict[str, Any]:
    if not block:
        return {}
    if "elapsed" in block:
        return {
            "elapsed_s": block.get("elapsed"),
            "user_s": block.get("user"),
            "system_s": block.get("system"),
            "cpu_s": block.get("cpu"),
            "memory_mib": block.get("memory"),
        }
    return block


def build_collector_summary(metrics: dict[str, Any],
                            compare_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    mismatch = metric(metrics, "mismatch")
    compact_mismatch = metric(metrics, "compact_mismatch")
    cpu_reference_checked = metric(metrics, "cpu_reference_checked")
    collector: dict[str, Any] = {
        "schema_version": "sim-accel-contract-collector-v1",
        "status": {
            "cpu_reference_checked": cpu_reference_checked,
            "mismatch": mismatch,
            "compact_mismatch": compact_mismatch,
            "aggregate_pass": bool(
                mismatch == 0
                and (compact_mismatch in (None, 0))
                and (cpu_reference_checked in (None, 0, 1))
            ),
        },
        "contract": {
            "preload": {
                "direct_preload_file_count": metric(metrics, "direct_preload_file_count"),
                "direct_preload_rules_applied": metric(metrics, "direct_preload_rules_applied"),
                "direct_preload_values_applied": metric(metrics, "direct_preload_values_applied"),
                "direct_preload_lines_ignored": metric(metrics, "direct_preload_lines_ignored"),
                "array_preload_payload_file_count": metric(metrics,
                                                           "array_preload_payload_file_count"),
                "array_preload_targets_loaded": metric(metrics, "array_preload_targets_loaded"),
                "array_preload_words_loaded": metric(metrics, "array_preload_words_loaded"),
                "array_preload_lines_ignored": metric(metrics, "array_preload_lines_ignored"),
            },
            "runtime": {
                "hybrid_mode": metric(metrics, "hybrid_mode", "off"),
                "hybrid_run_cycles": metric(metrics, "hybrid_run_cycles"),
                "hybrid_run_until_event": metric(metrics, "hybrid_run_until_event"),
                "fault_lines_ignored": metric(metrics, "fault_lines_ignored"),
            },
        },
        "reasons": {
            "unsupported": {
                "cuda_assignw_supported": metric(metrics, "cuda_assignw_supported"),
                "cuda_assignw_total": metric(metrics, "cuda_assignw_total"),
                "cuda_assignw_ignored": metric(metrics, "cuda_assignw_ignored"),
                "cuda_assignw_ignored_unsupported": metric(metrics,
                                                           "cuda_assignw_ignored_unsupported"),
                "cuda_assignw_ignored_internal": metric(metrics, "cuda_assignw_ignored_internal"),
                "cuda_assignw_ignored_non_var_lhs": metric(metrics,
                                                           "cuda_assignw_ignored_non_var_lhs"),
                "cuda_assignw_ignored_timing": metric(metrics, "cuda_assignw_ignored_timing"),
                "cuda_assignw_offload_pct": metric(metrics, "cuda_assignw_offload_pct"),
            },
            "fallback": {
                "hybrid_cluster_auto_fallback_used": metric(metrics,
                                                            "hybrid_cluster_auto_fallback_used"),
                "hybrid_cluster_group_auto_fallback_used": metric(
                    metrics, "hybrid_cluster_group_auto_fallback_used"),
                "hybrid_cluster_owner_hint": metric(metrics, "hybrid_cluster_owner_hint"),
                "hybrid_cluster_auto_selected_owner_hint": metric(
                    metrics, "hybrid_cluster_auto_selected_owner_hint"),
                "hybrid_cluster_group_auto_selected_owner_hint": metric(
                    metrics, "hybrid_cluster_group_auto_selected_owner_hint"),
                "hybrid_gpu_candidate_clusters": metric(metrics, "hybrid_gpu_candidate_clusters"),
                "hybrid_cpu_boundary_heavy_clusters": metric(
                    metrics, "hybrid_cpu_boundary_heavy_clusters"),
                "hybrid_cpu_only_blocked_clusters": metric(
                    metrics, "hybrid_cpu_only_blocked_clusters"),
            },
        },
        "performance": {
            "gpu_ms_per_rep": metric(metrics, "gpu_ms_per_rep"),
            "cpu_ms_per_rep": metric(metrics, "cpu_ms_per_rep"),
            "speedup_gpu_over_cpu": metric(metrics, "speedup_gpu_over_cpu"),
            "bench_run_s": metric(metrics, "bench_run_s"),
            "total_elapsed_s": metric(metrics, "total_elapsed_s"),
            "total_elapsed_cold_s": metric(metrics, "total_elapsed_cold_s"),
        },
        "coverage": {
            "coverage_points_hit": None,
            "coverage_points_total": None,
            "gpu_coverage_per_second": None,
            "cpu_coverage_per_second": None,
            "coverage_speedup_gpu_over_cpu": None,
            "available": False,
            "missing_fields": [
                "coverage_points_hit",
                "coverage_points_total",
                "gpu_coverage_walltime_s",
                "cpu_coverage_walltime_s",
            ],
        },
    }
    if compare_summary:
        totals = compare_summary.get("totals", {}) if isinstance(compare_summary, dict) else {}
        collector["comparison"] = {
            "standard_total_walltime_s": totals.get("standard_total_walltime_s"),
            "sim_accel_total_walltime_s": totals.get("sim_accel_total_walltime_s"),
            "speedup_standard_over_sim_accel": totals.get("speedup_standard_over_sim_accel"),
        }
    return collector


def _parse_coverage_count(raw: str) -> int | float:
    text = raw.strip()
    try:
        return int(text, 10)
    except ValueError:
        return float(text)


def _substring_match(value: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    return any(pattern in value for pattern in patterns)


def parse_verilator_coverage_record(line: str) -> dict[str, Any] | None:
    if not line.startswith("C '"):
        return None
    try:
        payload, count_text = line[3:].rsplit("' ", 1)
    except ValueError:
        return None
    fields: dict[str, str] = {}
    for entry in payload.split("\x01"):
        if not entry or "\x02" not in entry:
            continue
        key, value = entry.split("\x02", 1)
        fields[key] = value
    if not fields:
        return None
    return {
        "count": _parse_coverage_count(count_text),
        "file": fields.get("f", ""),
        "line": fields.get("l", ""),
        "type": fields.get("t", ""),
        "page": fields.get("page", ""),
        "object": fields.get("o", ""),
        "hierarchy": fields.get("h", ""),
        "raw_fields": fields,
    }


def summarize_verilator_coverage_dat(
    dat_path: Path,
    *,
    coverage_type: str | None = None,
    file_substrings: list[str] | None = None,
    page_substrings: list[str] | None = None,
    hierarchy_substrings: list[str] | None = None,
) -> dict[str, Any]:
    total_points = 0
    hit_points = 0
    count_by_type: dict[str, int] = {}
    hit_by_type: dict[str, int] = {}
    for raw in load_text(dat_path).splitlines():
        record = parse_verilator_coverage_record(raw)
        if not record:
            continue
        record_type = str(record.get("type", ""))
        count_by_type[record_type] = count_by_type.get(record_type, 0) + 1
        count_value = record.get("count", 0)
        if isinstance(count_value, (int, float)) and count_value > 0:
            hit_by_type[record_type] = hit_by_type.get(record_type, 0) + 1
        if coverage_type and record_type != coverage_type:
            continue
        if not _substring_match(str(record.get("file", "")), file_substrings):
            continue
        if not _substring_match(str(record.get("page", "")), page_substrings):
            continue
        if not _substring_match(str(record.get("hierarchy", "")), hierarchy_substrings):
            continue
        total_points += 1
        if isinstance(count_value, (int, float)) and count_value > 0:
            hit_points += 1
    return {
        "format": "verilator_dat",
        "source": str(dat_path),
        "coverage_type": coverage_type,
        "points_total": total_points,
        "points_hit": hit_points,
        "count_by_type": count_by_type,
        "hit_by_type": hit_by_type,
        "filters": {
            "file_substrings": file_substrings or [],
            "page_substrings": page_substrings or [],
            "hierarchy_substrings": hierarchy_substrings or [],
        },
    }


def coverage_record_key(record: dict[str, Any]) -> str:
    return "|".join(
        [
            str(record.get("type", "")),
            str(record.get("file", "")),
            str(record.get("line", "")),
            str(record.get("page", "")),
            str(record.get("object", "")),
            str(record.get("hierarchy", "")),
        ]
    )


def collect_verilator_coverage_index(
    dat_path: Path,
    *,
    coverage_type: str | None = None,
    file_substrings: list[str] | None = None,
    page_substrings: list[str] | None = None,
    hierarchy_substrings: list[str] | None = None,
) -> list[str]:
    keys: set[str] = set()
    for raw in load_text(dat_path).splitlines():
        record = parse_verilator_coverage_record(raw)
        if not record:
            continue
        if coverage_type and str(record.get("type", "")) != coverage_type:
            continue
        if not _substring_match(str(record.get("file", "")), file_substrings):
            continue
        if not _substring_match(str(record.get("page", "")), page_substrings):
            continue
        if not _substring_match(str(record.get("hierarchy", "")), hierarchy_substrings):
            continue
        keys.add(coverage_record_key(record))
    return sorted(keys)


def build_coverage_bitmap_index(index_keys: list[str]) -> dict[str, int]:
    return {key: idx for idx, key in enumerate(index_keys)}


def pack_coverage_bitmap(total_points: int, hit_indices: list[int]) -> bytes:
    bitmap = bytearray((total_points + 7) // 8)
    for idx in hit_indices:
        if idx < 0 or idx >= total_points:
            raise ValueError(f"Bitmap index out of range: {idx} for total_points={total_points}")
        bitmap[idx >> 3] |= 1 << (idx & 7)
    return bytes(bitmap)


def sha256_hex_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_hex_lines(lines: list[str]) -> str:
    return sha256_hex_bytes("\n".join(lines).encode("utf-8"))


def materialize_verilator_coverage_bitmap(
    dat_path: Path,
    *,
    coverage_type: str | None = None,
    file_substrings: list[str] | None = None,
    page_substrings: list[str] | None = None,
    hierarchy_substrings: list[str] | None = None,
    index_keys: list[str] | None = None,
) -> dict[str, Any]:
    resolved_index_keys = (
        list(index_keys)
        if index_keys is not None
        else collect_verilator_coverage_index(
            dat_path,
            coverage_type=coverage_type,
            file_substrings=file_substrings,
            page_substrings=page_substrings,
            hierarchy_substrings=hierarchy_substrings,
        )
    )
    index_map = build_coverage_bitmap_index(resolved_index_keys)
    hits = collect_verilator_coverage_hits(
        dat_path,
        coverage_type=coverage_type,
        file_substrings=file_substrings,
        page_substrings=page_substrings,
        hierarchy_substrings=hierarchy_substrings,
    )
    missing_keys = sorted(set(hits) - set(index_map))
    if missing_keys:
        raise ValueError(
            "Coverage bitmap index is missing hit keys: "
            + ", ".join(missing_keys[:5])
            + ("..." if len(missing_keys) > 5 else "")
        )
    hit_indices = sorted(index_map[key] for key in hits)
    bitmap_bytes = pack_coverage_bitmap(len(resolved_index_keys), hit_indices)
    return {
        "coverage_type": coverage_type,
        "points_total": len(resolved_index_keys),
        "points_hit": len(hit_indices),
        "bit_order": "lsb0",
        "hit_indices": hit_indices,
        "bitmap_bytes": bitmap_bytes,
        "bitmap_sha256": sha256_hex_bytes(bitmap_bytes),
        "index_sha256": sha256_hex_lines(resolved_index_keys),
    }


def collect_verilator_coverage_hits(
    dat_path: Path,
    *,
    coverage_type: str | None = None,
    file_substrings: list[str] | None = None,
    page_substrings: list[str] | None = None,
    hierarchy_substrings: list[str] | None = None,
) -> dict[str, int | float]:
    hits: dict[str, int | float] = {}
    for raw in load_text(dat_path).splitlines():
        record = parse_verilator_coverage_record(raw)
        if not record:
            continue
        if coverage_type and str(record.get("type", "")) != coverage_type:
            continue
        if not _substring_match(str(record.get("file", "")), file_substrings):
            continue
        if not _substring_match(str(record.get("page", "")), page_substrings):
            continue
        if not _substring_match(str(record.get("hierarchy", "")), hierarchy_substrings):
            continue
        count_value = record.get("count", 0)
        if not isinstance(count_value, (int, float)) or count_value <= 0:
            continue
        hits[coverage_record_key(record)] = count_value
    return hits


def summarize_lcov_info(
    info_path: Path,
    *,
    coverage_type: str = "toggle",
) -> dict[str, Any]:
    total_points = 0
    hit_points = 0
    record_prefix = "BRDA:" if coverage_type == "toggle" else "DA:"
    for raw in load_text(info_path).splitlines():
        line = raw.strip()
        if not line.startswith(record_prefix):
            continue
        total_points += 1
        value = line.rsplit(",", 1)[1] if coverage_type == "toggle" else line.rsplit(",", 1)[1]
        value = value.strip()
        if value not in {"0", "-"}:
            hit_points += 1
    return {
        "format": "lcov_info",
        "source": str(info_path),
        "coverage_type": coverage_type,
        "points_total": total_points,
        "points_hit": hit_points,
    }


def populate_collector_coverage(
    collector: dict[str, Any],
    *,
    points_hit: int | float | None = None,
    points_total: int | float | None = None,
    gpu_walltime_s: float | None = None,
    cpu_walltime_s: float | None = None,
    source_summary: dict[str, Any] | None = None,
    convergence_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coverage = collector.setdefault("coverage", {})
    coverage["coverage_points_hit"] = points_hit
    coverage["coverage_points_total"] = points_total
    coverage["gpu_coverage_walltime_s"] = gpu_walltime_s
    coverage["cpu_coverage_walltime_s"] = cpu_walltime_s
    coverage["gpu_coverage_per_second"] = None
    coverage["cpu_coverage_per_second"] = None
    coverage["coverage_speedup_gpu_over_cpu"] = None
    if isinstance(points_hit, (int, float)) and gpu_walltime_s and gpu_walltime_s > 0:
        coverage["gpu_coverage_per_second"] = points_hit / gpu_walltime_s
    if isinstance(points_hit, (int, float)) and cpu_walltime_s and cpu_walltime_s > 0:
        coverage["cpu_coverage_per_second"] = points_hit / cpu_walltime_s
    gpu_cov = coverage.get("gpu_coverage_per_second")
    cpu_cov = coverage.get("cpu_coverage_per_second")
    if isinstance(gpu_cov, (int, float)) and isinstance(cpu_cov, (int, float)) and cpu_cov > 0:
        coverage["coverage_speedup_gpu_over_cpu"] = gpu_cov / cpu_cov
    coverage["available"] = (
        coverage.get("coverage_points_hit") is not None
        and coverage.get("coverage_points_total") is not None
    )
    coverage["missing_fields"] = [
        field
        for field in (
            "coverage_points_hit",
            "coverage_points_total",
            "gpu_coverage_walltime_s",
            "cpu_coverage_walltime_s",
        )
        if coverage.get(field) is None
    ]
    if source_summary is not None:
        coverage["source_summary"] = source_summary
    if convergence_summary is not None:
        coverage["convergence_summary"] = convergence_summary
    return coverage


def summarize_coverage_convergence(
    iterations: list[dict[str, Any]],
    *,
    points_total: int | float | None = None,
    target_ratios: list[float] | None = None,
) -> dict[str, Any]:
    normalized_targets: list[float] = []
    for raw in target_ratios or [0.25, 0.50, 0.75, 0.90]:
        ratio = float(raw)
        if 0.0 < ratio <= 1.0:
            normalized_targets.append(ratio)
    normalized_targets = sorted(set(normalized_targets))

    cumulative_walltime_s = 0.0
    cumulative_hit_points = 0
    max_total_hit_points = 0
    max_coverage_per_second = None
    total_novelty_points = 0
    zero_novelty_iterations = 0
    target_hits: dict[str, int] = {}
    target_reach: dict[str, Any] = {}

    if isinstance(points_total, (int, float)) and points_total > 0:
        for ratio in normalized_targets:
            target_hits[f"{ratio:.2f}"] = int(math.ceil(points_total * ratio))

    for iteration in iterations:
        walltime_s = iteration.get("walltime_s")
        if isinstance(walltime_s, (int, float)) and walltime_s > 0:
            cumulative_walltime_s += float(walltime_s)

        total_hit_points = iteration.get("total_hit_points")
        if isinstance(total_hit_points, (int, float)):
            max_total_hit_points = max(max_total_hit_points, int(total_hit_points))

        coverage_per_second = iteration.get("coverage_per_second")
        if isinstance(coverage_per_second, (int, float)):
            if max_coverage_per_second is None or coverage_per_second > max_coverage_per_second:
                max_coverage_per_second = float(coverage_per_second)

        novelty_points = iteration.get("novelty_points")
        if isinstance(novelty_points, (int, float)):
            novelty_points = int(novelty_points)
            total_novelty_points += novelty_points
            if novelty_points == 0:
                zero_novelty_iterations += 1

        cumulative_points = iteration.get("cumulative_hit_points")
        if isinstance(cumulative_points, (int, float)):
            cumulative_hit_points = max(cumulative_hit_points, int(cumulative_points))

        if target_hits:
            for ratio_key, hit_target in target_hits.items():
                if ratio_key in target_reach:
                    continue
                if cumulative_hit_points >= hit_target:
                    target_reach[ratio_key] = {
                        "target_hit_points": hit_target,
                        "iteration": iteration.get("iteration"),
                        "seed": iteration.get("seed"),
                        "cumulative_hit_points": cumulative_hit_points,
                        "cumulative_walltime_s": cumulative_walltime_s,
                    }

    average_novelty_points = None
    if iterations:
        average_novelty_points = total_novelty_points / len(iterations)

    cumulative_coverage_ratio = None
    if isinstance(points_total, (int, float)) and points_total > 0:
        cumulative_coverage_ratio = cumulative_hit_points / float(points_total)

    return {
        "coverage_points_total": points_total,
        "cumulative_hit_points": cumulative_hit_points,
        "max_total_hit_points": max_total_hit_points,
        "cumulative_coverage_ratio": cumulative_coverage_ratio,
        "total_walltime_s": cumulative_walltime_s,
        "max_coverage_per_second": max_coverage_per_second,
        "average_novelty_points": average_novelty_points,
        "zero_novelty_iterations": zero_novelty_iterations,
        "target_hit_points": target_hits,
        "targets_reached": target_reach,
    }


def build_normalized_summary(summary: dict[str, Any]) -> dict[str, Any]:
    sim_accel = summary.get("sim_accel", {})
    metrics = sim_accel.get("metrics", {}) if isinstance(sim_accel, dict) else {}
    rtlmeter = summary.get("rtlmeter", {})
    execute = rtlmeter.get("execute", {}) if isinstance(rtlmeter, dict) else {}

    mode = metric(metrics, "hybrid_mode", "off")

    normalized: dict[str, Any] = {
        "schema_version": "rtlmeter-sim-accel-adapter-v1",
        "design": {
            "compile_dir": summary["adapter"]["compile_dir"],
            "bench_outdir": summary["adapter"]["bench_outdir"],
            "top_module": summary["adapter"]["top_module"],
        },
        "rtlmeter": {
            "compile": {
                "verilate": normalize_rtlmeter_time(rtlmeter.get("verilate", {})),
                "cppbuild": normalize_rtlmeter_time(rtlmeter.get("cppbuild", {})),
            },
            "execute": {
                "elapsed_s": execute.get("time", {}).get("elapsed") if execute else None,
                "passed": execute.get("passed") if execute else None,
                "path": execute.get("path") if execute else None,
            },
        },
        "sim_accel": {
            "mode": mode,
            "returncode": sim_accel.get("returncode"),
            "bench_log": sim_accel.get("bench_log"),
            "selection": {
                "auto_parallel_judgement": metric(metrics, "auto_parallel_judgement"),
                "auto_engine_recommendation": metric(metrics, "auto_engine_recommendation"),
                "hybrid_cluster_auto": metric(metrics, "hybrid_cluster_auto", 0),
                "hybrid_cluster_auto_candidate_count": metric(metrics, "hybrid_cluster_auto_candidate_count"),
                "hybrid_cluster_auto_fallback_used": metric(metrics, "hybrid_cluster_auto_fallback_used", 0),
                "hybrid_cluster_index": metric(metrics, "hybrid_cluster_index"),
                "hybrid_cluster_owner_hint": metric(metrics, "hybrid_cluster_owner_hint"),
                "hybrid_cluster_group_indices": metric(metrics, "hybrid_cluster_group_indices"),
                "hybrid_cluster_group_size": metric(metrics, "hybrid_cluster_group_size"),
                "hybrid_cluster_group_auto": metric(metrics, "hybrid_cluster_group_auto", 0),
                "hybrid_cluster_group_auto_candidate_count": metric(metrics, "hybrid_cluster_group_auto_candidate_count"),
            },
            "offload": {
                "supported_assignw": metric(metrics, "cuda_assignw_supported"),
                "total_assignw": metric(metrics, "cuda_assignw_total"),
                "ignored_assignw": metric(metrics, "cuda_assignw_ignored"),
                "post_lowering_assignw_offload_pct": metric(metrics, "cuda_assignw_offload_pct"),
                "scope": metric(metrics, "cuda_assignw_offload_scope"),
                "basis": metric(metrics, "cuda_assignw_offload_basis"),
            },
            "topology": {
                "kernel_partitions": metric(metrics, "kernel_partitions"),
                "kernel_clusters": metric(metrics, "kernel_clusters"),
                "approx_regcut_cluster_count": metric(metrics, "approx_regcut_cluster_count"),
                "approx_regcut_assign_count": metric(metrics, "approx_regcut_assign_count"),
                "approx_regcut_boundary_input_vars": metric(metrics, "approx_regcut_boundary_input_vars"),
                "approx_regcut_boundary_output_vars": metric(metrics, "approx_regcut_boundary_output_vars"),
                "approx_regcut_internal_vars": metric(metrics, "approx_regcut_internal_vars"),
            },
            "compile": {
                "verilator_codegen_s": metric(metrics, "verilator_codegen_s"),
                "verilator_codegen_cold_s": metric(metrics, "verilator_codegen_cold_s"),
                "verilator_artifact_cache_mode": metric(metrics, "verilator_artifact_cache_mode"),
                "verilator_artifact_cache_key": metric(metrics, "verilator_artifact_cache_key"),
                "nvcc_compile_s": metric(metrics, "nvcc_compile_s"),
                "nvcc_cold_compile_s": metric(metrics, "nvcc_cold_compile_s"),
                "nvcc_cache_mode": metric(metrics, "nvcc_cache_mode"),
                "nvcc_cache_key": metric(metrics, "nvcc_cache_key"),
                "object_cache_hits": metric(metrics, "object_cache_hits"),
                "object_cache_misses": metric(metrics, "object_cache_misses"),
                "bench_run_s": metric(metrics, "bench_run_s"),
                "total_elapsed_s": metric(metrics, "total_elapsed_s"),
                "total_elapsed_cold_s": metric(metrics, "total_elapsed_cold_s"),
            },
            "execution": {
                "nstates": metric(metrics, "nstates"),
                "state_chunk": metric(metrics, "state_chunk"),
                "state_chunks": metric(metrics, "state_chunks"),
                "block_size": metric(metrics, "block_size"),
                "gpu_ms_per_rep": metric(metrics, "gpu_ms_per_rep"),
                "cpu_ms_per_rep": metric(metrics, "cpu_ms_per_rep"),
                "speedup_gpu_over_cpu": metric(metrics, "speedup_gpu_over_cpu"),
                "mismatch": metric(metrics, "mismatch"),
                "compact_mismatch": metric(metrics, "compact_mismatch"),
            },
            "transfer": {
                "comm_input_vars": metric(metrics, "comm_input_vars"),
                "comm_output_vars": metric(metrics, "comm_output_vars"),
                "comm_input_bytes_per_batch": metric(metrics, "comm_input_bytes_per_batch"),
                "comm_output_bytes_per_batch": metric(metrics, "comm_output_bytes_per_batch"),
                "comm_total_bytes_per_batch": metric(metrics, "comm_total_bytes_per_batch"),
                "comm_verify_full_d2h_bytes": metric(metrics, "comm_verify_full_d2h_bytes"),
                "comm_roundtrip_ratio_pct": metric(metrics, "comm_roundtrip_ratio_pct"),
            },
            "hybrid": {
                "mode": mode,
                "metrics": collect_prefixed(metrics, "hybrid_"),
            },
        },
        "collector": build_collector_summary(metrics),
    }
    return normalized


def main(argv: list[str]) -> int:
    ns, bench_args = parse_cli(argv)
    compile_dir = Path(ns.compile_dir).resolve()
    bench_outdir = Path(ns.bench_outdir).resolve()
    verilator = Path(ns.verilator).resolve()
    bench = Path(ns.bench).resolve()

    cmd_file = compile_dir / "_verilate" / "cmd"
    filelist = compile_dir / "filelist"
    if not cmd_file.exists():
        raise SystemExit(f"Missing RTLMeter verilate cmd file: {cmd_file}")
    if not filelist.exists():
        raise SystemExit(f"Missing RTLMeter filelist: {filelist}")
    if not verilator.exists():
        raise SystemExit(f"Missing Verilator binary: {verilator}")
    if not bench.exists():
        raise SystemExit(f"Missing sim-accel bench: {bench}")

    top_module, passthrough_args, raw_tokens = recover_verilator_args(cmd_file)
    bench_outdir.mkdir(parents=True, exist_ok=True)

    bench_cmd = [
        str(bench),
        "--verilator",
        str(verilator),
        "--top-module",
        top_module,
        "--outdir",
        str(bench_outdir),
    ]
    bench_cmd.extend(bench_args)
    bench_cmd.append("--")
    bench_cmd.extend(passthrough_args)

    summary: dict[str, Any] = {
        "adapter": {
            "compile_dir": str(compile_dir),
            "bench_outdir": str(bench_outdir),
            "verilator": str(verilator),
            "bench": str(bench),
            "top_module": top_module,
            "recovered_verilator_args": passthrough_args,
            "raw_verilate_tokens": raw_tokens,
            "bench_args": bench_args,
            "bench_command": bench_cmd,
        },
        "rtlmeter": {
            "verilate": load_json(compile_dir / "_verilate" / "time.json") if (compile_dir / "_verilate" / "time.json").exists() else {},
            "cppbuild": load_json(compile_dir / "_cppbuild" / "time.json") if (compile_dir / "_cppbuild" / "time.json").exists() else {},
        },
    }

    execute_dir = Path(ns.execute_dir).resolve() if ns.execute_dir else None
    if execute_dir:
        summary["rtlmeter"]["execute"] = summarize_execute_dir(execute_dir)

    if ns.dry_run:
        summary["sim_accel"] = {"dry_run": True}
        summary["normalized"] = build_normalized_summary(summary)
    else:
        proc = subprocess.run(
            bench_cmd,
            cwd=compile_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        summary["sim_accel"] = {
            "returncode": proc.returncode,
            "stdout": proc.stdout.splitlines(),
            "stderr": proc.stderr.splitlines(),
            "bench_log": str(bench_outdir / "bench_run.log"),
        }
        log_file = bench_outdir / "bench_run.log"
        if log_file.exists():
            summary["sim_accel"]["metrics"] = parse_bench_log(log_file)
        summary["normalized"] = build_normalized_summary(summary)
        if proc.returncode != 0:
            if ns.json_out:
                Path(ns.json_out).write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
            print(json.dumps(summary, indent=2, sort_keys=True))
            return proc.returncode

    if ns.json_out:
        Path(ns.json_out).write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
