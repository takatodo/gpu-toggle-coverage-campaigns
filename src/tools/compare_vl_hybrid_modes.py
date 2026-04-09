#!/usr/bin/env python3
"""
Compare stock-Verilator hybrid outputs between:
  1) single-kernel vl_eval_batch_gpu
  2) phase-split launch_sequence (ico/nba)

This is a regression harness for Phase B fidelity work. It rebuilds the cubin in both modes,
runs src/tools/run_vl_hybrid.py twice with identical launch settings, dumps the final device
storage, and reports whether the bytewise state images match.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path

from build_vl_gpu import CLANG, CXX_STANDARD, build_vl_gpu, find_prefix, verilator_include_dir


SCRIPT_DIR = Path(__file__).resolve().parent
RUN_VL_HYBRID = SCRIPT_DIR / "run_vl_hybrid.py"
FIELD_MACRO_RE = re.compile(r"^\s*VL_(?:IN|OUT)\d*\(\s*([A-Za-z_]\w*)\s*,")
FIELD_DECL_RE = re.compile(r"([A-Za-z_]\w*)\s*;\s*$")
VERILATOR_INTERNAL_FIELDS = {"vlSymsp", "vlNamep", "__VdlySched"}
ACCEPTANCE_POLICY_STRICT = "strict_final_state"
ACCEPTANCE_POLICY_IGNORE_INTERNAL = "ignore_verilator_internal_final_state"
ACCEPTANCE_POLICY_PHASE_B_ENDPOINT = "phase_b_endpoint"
PHASE_B_ALLOWED_INTERNAL_FIELDS = {
    "__VicoPhaseResult",
    "__VactIterCount",
    "__VinactIterCount",
    "__VicoTriggered",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_root_member_names(root_h: Path) -> list[str]:
    names: list[str] = []
    for raw_line in root_h.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        if line in {"public:", "private:", "protected:", "};"}:
            continue
        if line.startswith("class ") or line.startswith("struct {"):
            continue
        macro_match = FIELD_MACRO_RE.match(line)
        if macro_match:
            names.append(macro_match.group(1))
            continue
        if "(" in line or ")" in line:
            continue
        decl_match = FIELD_DECL_RE.search(line)
        if decl_match:
            names.append(decl_match.group(1))
    return names


def classify_field_role(field_name: str) -> str:
    if field_name.startswith("__V") or field_name in VERILATOR_INTERNAL_FIELDS:
        return "verilator_internal"
    if "__DOT__" in field_name:
        return "design_state"
    if field_name.endswith("_i") or field_name.endswith("_o"):
        return "top_level_io"
    return "other"


def probe_root_layout(mdir: Path) -> list[dict[str, int | str]]:
    prefix = find_prefix(mdir)
    root_type = f"{prefix}___024root"
    root_h = mdir / f"{root_type}.h"
    member_names = extract_root_member_names(root_h)
    if not member_names:
        return []

    probe_lines = [
        "#include <cstddef>",
        "#include <cstdio>",
        f'#include "{root_h.resolve()}"',
        "int main() {",
    ]
    for name in member_names:
        probe_lines.append(
            f'  std::printf("{name}\\t%zu\\t%zu\\n", '
            f"offsetof({root_type}, {name}), sizeof((({root_type}*)nullptr)->{name}));"
        )
    probe_lines.append("  return 0;")
    probe_lines.append("}")
    probe_src = "\n".join(probe_lines) + "\n"

    with tempfile.TemporaryDirectory(prefix="vl_root_layout_") as tmpdir:
        tmp = Path(tmpdir)
        src = tmp / "probe_layout.cpp"
        exe = tmp / "probe_layout"
        src.write_text(probe_src, encoding="utf-8")
        cmd = [
            CLANG,
            f"-std={CXX_STANDARD}",
            "-Wno-invalid-offsetof",
            f"-I{mdir}",
            f"-I{verilator_include_dir()}",
            str(src),
            "-o",
            str(exe),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)

    layout: list[dict[str, int | str]] = []
    for line in result.stdout.splitlines():
        name, offset, size = line.split("\t")
        layout.append({"name": name, "offset": int(offset), "size": int(size)})
    layout.sort(key=lambda entry: (int(entry["offset"]), int(entry["size"]), str(entry["name"])))
    return layout


def annotate_state_offset(
    layout: list[dict[str, int | str]], state_offset: int | None
) -> dict[str, int | str] | None:
    if state_offset is None:
        return None
    for entry in layout:
        start = int(entry["offset"])
        size = int(entry["size"])
        if start <= state_offset < start + size:
            return {
                "field_name": str(entry["name"]),
                "field_offset": start,
                "field_size": size,
                "field_byte_offset": state_offset - start,
            }
    return None


def summarize_mismatch_fields(
    single: bytes,
    split: bytes,
    *,
    storage_size: int,
    layout: list[dict[str, int | str]],
    limit: int = 16,
) -> tuple[int, list[dict[str, object]], list[dict[str, object]], dict[str, dict[str, int]]]:
    groups: dict[tuple[str, int], dict[str, object]] = {}
    max_len = max(len(single), len(split))
    for idx in range(max_len):
        single_byte = single[idx] if idx < len(single) else None
        split_byte = split[idx] if idx < len(split) else None
        if single_byte == split_byte:
            continue
        state_offset = idx % storage_size if storage_size > 0 else idx
        state_index = idx // storage_size if storage_size > 0 else 0
        annotation = annotate_state_offset(layout, state_offset)
        field_name = str(annotation["field_name"]) if annotation else "<unknown>"
        field_offset = int(annotation["field_offset"]) if annotation else state_offset
        key = (field_name, field_offset)
        group = groups.get(key)
        if group is None:
            group = {
                "field_name": field_name,
                "field_role": classify_field_role(field_name),
                "field_offset": field_offset,
                "field_size": int(annotation["field_size"]) if annotation else 1,
                "mismatch_bytes": 0,
                "first_global_offset": idx,
                "first_state_offset": state_offset,
                "first_state_index": state_index,
                "field_byte_offsets": [],
                "state_indices": [],
                "example_single_byte": single_byte,
                "example_split_byte": split_byte,
            }
            groups[key] = group
        group["mismatch_bytes"] = int(group["mismatch_bytes"]) + 1
        field_byte_offset = (
            int(annotation["field_byte_offset"]) if annotation else 0
        )
        if (
            field_byte_offset not in group["field_byte_offsets"]
            and len(group["field_byte_offsets"]) < 8
        ):
            group["field_byte_offsets"].append(field_byte_offset)
        if state_index not in group["state_indices"] and len(group["state_indices"]) < 8:
            group["state_indices"].append(state_index)

    ordered = sorted(groups.values(), key=lambda entry: int(entry["first_global_offset"]))
    role_summary: dict[str, dict[str, int]] = {}
    for entry in ordered:
        role = str(entry["field_role"])
        bucket = role_summary.setdefault(role, {"field_count": 0, "mismatch_bytes": 0})
        bucket["field_count"] += 1
        bucket["mismatch_bytes"] += int(entry["mismatch_bytes"])
    return len(ordered), ordered[:limit], ordered, role_summary


def first_field_with_role(
    mismatch_fields: list[dict[str, object]], *roles: str
) -> dict[str, object] | None:
    wanted = set(roles)
    for entry in mismatch_fields:
        if str(entry.get("field_role")) in wanted:
            return dict(entry)
    return None


def build_acceptance_candidates(
    *,
    match: bool,
    mismatch_count: int,
    role_summary: dict[str, dict[str, int]],
) -> dict[str, int | bool]:
    internal_bytes = int(role_summary.get("verilator_internal", {}).get("mismatch_bytes", 0))
    design_state_bytes = int(role_summary.get("design_state", {}).get("mismatch_bytes", 0))
    top_level_io_bytes = int(role_summary.get("top_level_io", {}).get("mismatch_bytes", 0))
    other_bytes = mismatch_count - internal_bytes - design_state_bytes - top_level_io_bytes
    return {
        "strict_match": match,
        "match_excluding_verilator_internal": mismatch_count == internal_bytes,
        "verilator_internal_mismatch_bytes": internal_bytes,
        "design_state_mismatch_bytes": design_state_bytes,
        "top_level_io_mismatch_bytes": top_level_io_bytes,
        "other_mismatch_bytes": other_bytes,
    }


def has_only_phase_b_residual_fields(summary: dict[str, object]) -> bool:
    mismatch_fields = list(summary.get("mismatch_fields") or [])
    if not mismatch_fields:
        return True
    allowed = PHASE_B_ALLOWED_INTERNAL_FIELDS
    for entry in mismatch_fields:
        if str(entry.get("field_role")) != "verilator_internal":
            return False
        if str(entry.get("field_name")) not in allowed:
            return False
    return True


def build_acceptance_policies(summary: dict[str, object]) -> dict[str, dict[str, object]]:
    candidates = dict(summary.get("acceptance_candidates") or {})
    strict_passed = bool(candidates.get("strict_match", summary.get("match", False)))
    ignore_internal_passed = bool(candidates.get("match_excluding_verilator_internal", False))
    phase_b_endpoint_passed = ignore_internal_passed and has_only_phase_b_residual_fields(summary)
    return {
        ACCEPTANCE_POLICY_STRICT: {
            "passed": strict_passed,
            "description": "Final raw state bytes must match exactly.",
            "diagnostic_only_prefixes": True,
        },
        ACCEPTANCE_POLICY_IGNORE_INTERNAL: {
            "passed": ignore_internal_passed,
            "description": (
                "Final design_state/top_level_io/other bytes must match; "
                "verilator_internal bytes may differ."
            ),
            "diagnostic_only_prefixes": True,
        },
        ACCEPTANCE_POLICY_PHASE_B_ENDPOINT: {
            "passed": phase_b_endpoint_passed,
            "description": (
                "Final design_state/top_level_io/other bytes must match, and any residual "
                "verilator_internal mismatch must be limited to the known convergence "
                "bookkeeping fields (__VicoPhaseResult, __VactIterCount, "
                "__VinactIterCount, __VicoTriggered)."
            ),
            "diagnostic_only_prefixes": True,
        },
    }


def select_acceptance_policy(
    summary: dict[str, object], policy_name: str
) -> dict[str, object]:
    policies = dict(summary.get("acceptance_policies") or {})
    selected = dict(policies[policy_name])
    selected["name"] = policy_name
    return selected


def build_phase_delta_summary(summary: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {
        "mismatch_count": int(summary.get("mismatch_count", 0)),
        "mismatch_field_count": int(summary.get("mismatch_field_count", 0)),
        "mismatch_role_summary": dict(summary.get("mismatch_role_summary") or {}),
        "acceptance_candidates": dict(summary.get("acceptance_candidates") or {}),
        "mismatch_fields": [dict(entry) for entry in summary.get("mismatch_fields", [])],
    }
    for key in ("first_mismatch", "first_non_internal_mismatch", "first_design_state_mismatch"):
        value = summary.get(key)
        if value is not None:
            payload[key] = dict(value)
    return payload


def compare_state_dumps(
    single_dump: Path,
    split_dump: Path,
    storage_size: int,
    *,
    layout: list[dict[str, int | str]] | None = None,
) -> dict:
    single = single_dump.read_bytes()
    split = split_dump.read_bytes()
    first_mismatch = None
    mismatch_count = 0
    compare_len = min(len(single), len(split))
    for idx in range(compare_len):
        if single[idx] != split[idx]:
            mismatch_count += 1
            if first_mismatch is None:
                first_mismatch = idx
    mismatch_count += abs(len(single) - len(split))

    payload = {
        "match": mismatch_count == 0 and len(single) == len(split),
        "single_bytes": len(single),
        "split_bytes": len(split),
        "mismatch_count": mismatch_count,
        "storage_size": storage_size,
        "single_sha256": sha256_file(single_dump),
        "split_sha256": sha256_file(split_dump),
    }
    if first_mismatch is not None:
        payload["first_mismatch"] = {
            "global_offset": first_mismatch,
            "state_index": first_mismatch // storage_size if storage_size > 0 else None,
            "state_offset": first_mismatch % storage_size if storage_size > 0 else None,
            "single_byte": single[first_mismatch],
            "split_byte": split[first_mismatch],
        }
        if layout:
            annotation = annotate_state_offset(layout, payload["first_mismatch"]["state_offset"])
            if annotation is not None:
                payload["first_mismatch"].update(annotation)
    if layout:
        field_count, mismatch_fields, all_mismatch_fields, role_summary = summarize_mismatch_fields(
            single,
            split,
            storage_size=storage_size,
            layout=layout,
        )
        payload["mismatch_field_count"] = field_count
        payload["mismatch_fields"] = mismatch_fields
        payload["mismatch_role_summary"] = role_summary
        payload["acceptance_candidates"] = build_acceptance_candidates(
            match=payload["match"],
            mismatch_count=mismatch_count,
            role_summary=role_summary,
        )
        first_non_internal = first_field_with_role(
            all_mismatch_fields, "design_state", "top_level_io", "other"
        )
        if first_non_internal is not None:
            payload["first_non_internal_mismatch"] = first_non_internal
        first_design_state = first_field_with_role(all_mismatch_fields, "design_state")
        if first_design_state is not None:
            payload["first_design_state_mismatch"] = first_design_state
    return payload


def run_hybrid(
    *,
    mdir: Path | None,
    cubin: Path | None,
    storage_size: int,
    nstates: int,
    steps: int,
    block_size: int,
    dump_state: Path,
    patches: list[str],
    kernels: list[str] | None = None,
) -> None:
    cmd = [sys.executable, str(RUN_VL_HYBRID)]
    if mdir is not None:
        cmd.extend(["--mdir", str(mdir)])
    else:
        assert cubin is not None
        cmd.extend(["--cubin", str(cubin), "--storage-size", str(storage_size)])
    cmd.extend(
        [
            "--nstates",
            str(nstates),
            "--steps",
            str(steps),
            "--block-size",
            str(block_size),
            "--dump-state",
            str(dump_state),
        ]
    )
    if kernels is not None:
        cmd.extend(["--kernels", ",".join(kernels)])
    for patch in patches:
        cmd.extend(["--patch", patch])
    subprocess.run(cmd, check=True)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Compare single-kernel vs phase-split stock-Verilator hybrid outputs"
    )
    p.add_argument("mdir", type=Path, help="Verilator --cc output directory (contains *_classes.mk)")
    p.add_argument("--sm", default="sm_89", help="GPU arch (default: sm_89)")
    p.add_argument("--clang-O", dest="clang_opt", default="O1", help="clang optimization for .ll")
    p.add_argument("--force-build", action="store_true", help="Force both cubin rebuilds")
    p.add_argument("--nstates", type=int, default=64, help="Parallel states for each run")
    p.add_argument("--steps", type=int, default=1, help="Launch steps for each run")
    p.add_argument("--block-size", type=int, default=256, help="CUDA block size")
    p.add_argument(
        "--patch",
        action="append",
        default=[],
        metavar="GLOBAL_OFF:BYTE",
        help="Per-step HtoD patch forwarded to run_vl_hybrid.py",
    )
    p.add_argument("--json-out", type=Path, default=None, help="Optional JSON summary path")
    p.add_argument(
        "--dump-dir",
        type=Path,
        default=None,
        help="Optional directory to keep single/split raw state dumps for mismatch debugging",
    )
    p.add_argument(
        "--acceptance-policy",
        default=ACCEPTANCE_POLICY_STRICT,
        choices=[
            ACCEPTANCE_POLICY_STRICT,
            ACCEPTANCE_POLICY_IGNORE_INTERNAL,
            ACCEPTANCE_POLICY_PHASE_B_ENDPOINT,
        ],
        help="Pass/fail policy for the tool exit code (default: strict_final_state)",
    )
    args = p.parse_args()

    mdir = args.mdir.resolve()
    single_cubin = mdir / "vl_batch_gpu_single.cubin"
    split_cubin = mdir / "vl_batch_gpu_split.cubin"

    dump_ctx = (
        nullcontext(args.dump_dir.resolve())
        if args.dump_dir is not None
        else tempfile.TemporaryDirectory(prefix="vl_hybrid_compare_")
    )
    with dump_ctx as tmp:
        tmpdir = Path(tmp)
        tmpdir.mkdir(parents=True, exist_ok=True)
        single_dump = tmpdir / "single_state.bin"
        split_dump = tmpdir / "split_state.bin"
        layout = probe_root_layout(mdir)

        single_path, storage_size = build_vl_gpu(
            mdir,
            sm=args.sm,
            out_cubin=single_cubin,
            force=args.force_build,
            clang_opt=args.clang_opt,
            kernel_split_phases=False,
        )
        run_hybrid(
            mdir=None,
            cubin=single_path,
            storage_size=storage_size,
            nstates=args.nstates,
            steps=args.steps,
            block_size=args.block_size,
            dump_state=single_dump,
            patches=args.patch,
        )

        split_path, split_storage_size = build_vl_gpu(
            mdir,
            sm=args.sm,
            out_cubin=split_cubin,
            force=args.force_build,
            clang_opt=args.clang_opt,
            kernel_split_phases=True,
        )
        if split_storage_size != storage_size:
            raise RuntimeError(
                f"storage_size mismatch between single ({storage_size}) and split ({split_storage_size})"
            )
        run_hybrid(
            mdir=mdir,
            cubin=None,
            storage_size=storage_size,
            nstates=args.nstates,
            steps=args.steps,
            block_size=args.block_size,
            dump_state=split_dump,
            patches=args.patch,
        )

        summary = compare_state_dumps(single_dump, split_dump, storage_size, layout=layout)
        split_meta = json.loads((mdir / "vl_batch_gpu.meta.json").read_text(encoding="utf-8"))
        launch_sequence = list(split_meta.get("launch_sequence") or [])
        if launch_sequence:
            phase_debug = []
            prev_dump = None
            phase_localization = {
                "first_divergent_prefix_index": None,
                "first_divergent_kernels": None,
                "first_non_internal_prefix_index": None,
                "first_non_internal_kernels": None,
                "first_non_internal_mismatch": None,
                "first_design_state_prefix_index": None,
                "first_design_state_kernels": None,
                "first_design_state_mismatch": None,
                "first_delta_prefix_index": None,
                "first_delta_kernels": None,
                "first_delta_fields": None,
                "first_non_internal_delta_prefix_index": None,
                "first_non_internal_delta_kernels": None,
                "first_non_internal_delta_mismatch": None,
                "first_design_state_delta_prefix_index": None,
                "first_design_state_delta_kernels": None,
                "first_design_state_delta_mismatch": None,
                "per_prefix_mismatch_counts": [],
                "per_prefix_delta_counts": [],
            }
            for idx in range(len(launch_sequence)):
                kernels = launch_sequence[: idx + 1]
                prefix_dump = tmpdir / f"split_prefix_{idx + 1}.bin"
                run_hybrid(
                    mdir=None,
                    cubin=split_path,
                    storage_size=storage_size,
                    nstates=args.nstates,
                    steps=args.steps,
                    block_size=args.block_size,
                    dump_state=prefix_dump,
                    patches=args.patch,
                    kernels=kernels,
                )
                prefix_summary = compare_state_dumps(
                    single_dump,
                    prefix_dump,
                    storage_size,
                    layout=layout,
                )
                entry = {
                    "prefix_index": idx + 1,
                    "kernels": kernels,
                    "vs_single_final": prefix_summary,
                    "dump": str(prefix_dump),
                }
                phase_localization["per_prefix_mismatch_counts"].append(prefix_summary["mismatch_count"])
                if (
                    phase_localization["first_divergent_prefix_index"] is None
                    and prefix_summary["mismatch_count"] > 0
                ):
                    phase_localization["first_divergent_prefix_index"] = idx + 1
                    phase_localization["first_divergent_kernels"] = list(kernels)
                    phase_localization["first_divergent_fields"] = list(
                        prefix_summary.get("mismatch_fields", [])
                    )
                if (
                    phase_localization["first_non_internal_prefix_index"] is None
                    and prefix_summary.get("first_non_internal_mismatch") is not None
                ):
                    phase_localization["first_non_internal_prefix_index"] = idx + 1
                    phase_localization["first_non_internal_kernels"] = list(kernels)
                    phase_localization["first_non_internal_mismatch"] = dict(
                        prefix_summary["first_non_internal_mismatch"]
                    )
                if (
                    phase_localization["first_design_state_prefix_index"] is None
                    and prefix_summary.get("first_design_state_mismatch") is not None
                ):
                    phase_localization["first_design_state_prefix_index"] = idx + 1
                    phase_localization["first_design_state_kernels"] = list(kernels)
                    phase_localization["first_design_state_mismatch"] = dict(
                        prefix_summary["first_design_state_mismatch"]
                    )
                if prev_dump is not None:
                    prev_summary = compare_state_dumps(
                        prev_dump,
                        prefix_dump,
                        storage_size,
                        layout=layout,
                    )
                    entry["vs_previous_prefix"] = prev_summary
                    entry["delta_from_previous_prefix"] = build_phase_delta_summary(prev_summary)
                    phase_localization["per_prefix_delta_counts"].append(prev_summary["mismatch_count"])
                    if (
                        phase_localization["first_delta_prefix_index"] is None
                        and prev_summary["mismatch_count"] > 0
                    ):
                        phase_localization["first_delta_prefix_index"] = idx + 1
                        phase_localization["first_delta_kernels"] = list(kernels)
                        phase_localization["first_delta_fields"] = list(
                            prev_summary.get("mismatch_fields", [])
                        )
                    if (
                        phase_localization["first_non_internal_delta_prefix_index"] is None
                        and prev_summary.get("first_non_internal_mismatch") is not None
                    ):
                        phase_localization["first_non_internal_delta_prefix_index"] = idx + 1
                        phase_localization["first_non_internal_delta_kernels"] = list(kernels)
                        phase_localization["first_non_internal_delta_mismatch"] = dict(
                            prev_summary["first_non_internal_mismatch"]
                        )
                    if (
                        phase_localization["first_design_state_delta_prefix_index"] is None
                        and prev_summary.get("first_design_state_mismatch") is not None
                    ):
                        phase_localization["first_design_state_delta_prefix_index"] = idx + 1
                        phase_localization["first_design_state_delta_kernels"] = list(kernels)
                        phase_localization["first_design_state_delta_mismatch"] = dict(
                            prev_summary["first_design_state_mismatch"]
                        )
                else:
                    phase_localization["per_prefix_delta_counts"].append(None)
                phase_debug.append(entry)
                prev_dump = prefix_dump
            summary["phase_debug"] = phase_debug
            summary["phase_localization"] = phase_localization
        summary["phase_localization_note"] = (
            "Prefix comparisons are diagnostic against single final state, "
            "not phase-aligned acceptance gates; use delta_from_previous_prefix "
            "and first_*_delta_* keys to isolate what each added kernel changed."
        )
        summary["acceptance_policies"] = build_acceptance_policies(summary)
        summary["selected_acceptance_policy"] = select_acceptance_policy(
            summary, args.acceptance_policy
        )
        summary.update(
            {
                "schema_version": 2,
                "mdir": str(mdir),
                "single_cubin": str(single_path),
                "split_cubin": str(split_path),
                "launch_sequence": launch_sequence,
                "root_layout_member_count": len(layout),
                "nstates": args.nstates,
                "steps": args.steps,
                "block_size": args.block_size,
                "patches": list(args.patch),
                "single_dump": str(single_dump),
                "split_dump": str(split_dump),
            }
        )

        if args.json_out is not None:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
            print(f"wrote: {args.json_out}")

        print(json.dumps(summary, indent=2))
        return 0 if summary["selected_acceptance_policy"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
