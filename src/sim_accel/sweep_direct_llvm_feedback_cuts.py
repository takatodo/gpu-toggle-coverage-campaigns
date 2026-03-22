#!/usr/bin/env python3
"""Sweep single-edge feedback cuts derived from an SCC cycle.

This is a narrow orchestration helper for direct-LLVM experiments. It reads an
SCC summary emitted by `analyze_mlir_graph_scc.py`, derives one single-edge cut
candidate per edge on the reported cycle, runs `direct_llvm_feedback_probe.py`
for each candidate, and writes a ranked summary JSON.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


CUDA_OPT_DIR = Path(__file__).resolve().parent
DIRECT_LLVM_FEEDBACK_PROBE = CUDA_OPT_DIR / "direct_llvm_feedback_probe.py"
SSA_DEF_RE = re.compile(r"(%[A-Za-z0-9_.$#-]+)\s*=")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Aggregate-lowered hw.module MLIR")
    parser.add_argument("--scc-json", type=Path, required=True, help="SCC summary JSON")
    parser.add_argument("--out-dir", type=Path, required=True, help="Sweep output directory")
    parser.add_argument(
        "--probe-script",
        type=Path,
        default=DIRECT_LLVM_FEEDBACK_PROBE,
        help="Path to direct_llvm_feedback_probe.py",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        required=True,
        help="CIRCT build directory forwarded to the probe",
    )
    parser.add_argument(
        "--stop-after",
        choices=("cut", "func", "llvm-dialect", "llvm-ir", "ptx"),
        default="llvm-ir",
        help="Probe stage to stop after",
    )
    parser.add_argument(
        "--cuda-arch",
        default=None,
        help="Optional CUDA arch forwarded to the probe",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional cap on the number of cycle edges to probe",
    )
    parser.add_argument(
        "--emit-best-cut-spec",
        type=Path,
        default=None,
        help="Optional path where the best successful cut spec should be written",
    )
    return parser.parse_args()


def _extract_def(op_text: str) -> str:
    match = SSA_DEF_RE.match(op_text.strip())
    if match is None:
        raise ValueError(f"Could not parse SSA def from: {op_text}")
    return match.group(1)


def _load_cycle_edges(scc_json: Path) -> list[tuple[str, str]]:
    payload = json.loads(scc_json.read_text(encoding="utf-8"))
    cycle = payload.get("largest_scc_cycle", [])
    if not isinstance(cycle, list) or len(cycle) < 2:
        raise ValueError("largest_scc_cycle is empty; nothing to sweep")
    defs = [_extract_def(item["text"]) for item in cycle]
    edges: list[tuple[str, str]] = []
    for src, dst in zip(defs, defs[1:]):
        edges.append((src, dst))
    unique_edges: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for edge in edges:
        if edge in seen:
            continue
        seen.add(edge)
        unique_edges.append(edge)
    return unique_edges


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _stage_rank(manifest: dict[str, object], requested_stop: str) -> tuple[int, str]:
    stages = manifest.get("stages", {})
    if not isinstance(stages, dict):
        return (-1, "missing")
    order = ["cut", "func", "llvm_dialect", "llvm_ir", "ptx"]
    requested_key = requested_stop.replace("-", "_")
    present = [name for name in order if name in stages]
    if not present:
        return (-1, "missing")
    last = present[-1]
    rank = order.index(last)
    if "error" not in manifest and last == requested_key:
        return (rank, "success")
    if "error" not in manifest:
        return (rank, "partial")
    return (rank, "error")


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    edges = _load_cycle_edges(args.scc_json)
    if args.limit > 0:
        edges = edges[: args.limit]

    summary: dict[str, object] = {
        "input": str(args.input.resolve()),
        "scc_json": str(args.scc_json.resolve()),
        "build_dir": str(args.build_dir.resolve()),
        "probe_script": str(args.probe_script.resolve()),
        "stop_after": args.stop_after,
        "cuda_arch": args.cuda_arch,
        "results": [],
    }

    results: list[dict[str, object]] = []
    for idx, (source_value, replace_in_op) in enumerate(edges):
        case_dir = args.out_dir / f"candidate_{idx:02d}_{source_value[1:]}_to_{replace_in_op[1:]}"
        case_dir.mkdir(parents=True, exist_ok=True)
        cut_spec = {
            "cuts": [
                {
                    "source_value": source_value,
                    "replace_in_ops": [replace_in_op],
                    "new_input_name": f"%cut_{source_value[1:]}",
                }
            ]
        }
        cut_spec_path = case_dir / "cut_spec.json"
        _write_json(cut_spec_path, cut_spec)
        cmd = [
            sys.executable,
            str(args.probe_script),
            "--input",
            str(args.input),
            "--out-dir",
            str(case_dir),
            "--cut-spec",
            str(cut_spec_path),
            "--build-dir",
            str(args.build_dir),
            "--stop-after",
            args.stop_after,
        ]
        if args.cuda_arch:
            cmd.extend(["--cuda-arch", args.cuda_arch])
        run = subprocess.run(cmd, capture_output=True, text=True)
        manifest_path = case_dir / "direct_feedback_probe_manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            manifest = {"error": "missing manifest"}
        stage_rank, status = _stage_rank(manifest, args.stop_after)
        cut_stage = manifest.get("stages", {}).get("cut", {})
        scc_summary = cut_stage.get("scc_summary", {}) if isinstance(cut_stage, dict) else {}
        result = {
            "candidate_index": idx,
            "source_value": source_value,
            "replace_in_op": replace_in_op,
            "status": status,
            "stage_rank": stage_rank,
            "returncode": run.returncode,
            "remaining_count": scc_summary.get("remaining_count"),
            "largest_scc_size": scc_summary.get("largest_scc_size"),
            "manifest": str(manifest_path),
            "cut_spec": str(cut_spec_path),
            "stderr_tail": "\n".join(run.stderr.strip().splitlines()[-5:]) if run.stderr else "",
            "error": manifest.get("error"),
        }
        results.append(result)

    status_rank = {"success": 3, "partial": 2, "error": 1, "missing": 0}
    results.sort(
        key=lambda item: (
            status_rank.get(str(item.get("status")), -1),
            int(item.get("stage_rank", -1)),
            -(
                int(item.get("remaining_count"))
                if item.get("remaining_count") is not None
                else 10**9
            ),
        ),
        reverse=True,
    )
    summary["results"] = results
    if results:
        summary["best"] = results[0]
    if args.emit_best_cut_spec is not None:
        best_success = next((item for item in results if item.get("status") == "success"), None)
        if best_success is not None:
            best_spec = {
                "cuts": [
                    {
                        "source_value": best_success["source_value"],
                        "replace_in_ops": [best_success["replace_in_op"]],
                        "new_input_name": f"%cut_{str(best_success['source_value'])[1:]}",
                    }
                ]
            }
            _write_json(args.emit_best_cut_spec, best_spec)
            summary["best_cut_spec"] = str(args.emit_best_cut_spec)
    summary_path = args.out_dir / "direct_feedback_sweep_summary.json"
    _write_json(summary_path, summary)
    print(f"wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
