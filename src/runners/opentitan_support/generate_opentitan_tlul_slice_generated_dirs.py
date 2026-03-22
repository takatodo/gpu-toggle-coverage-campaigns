#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent.parent
SLICE_INDEX_JSON = ROOT_DIR / "config/slice_launch_templates/index.json"
BASELINE_SCRIPT = ROOT_DIR / "src/scripts/run_opentitan_tlul_slice_gpu_baseline.py"
HDL_TO_FULL_ALL = ROOT_DIR / "third_party/verilator/opt/gpu/cuda/hdl_to_full_all.py"
STRUCTURED_RAW_OVERLAY_MARKER = ".structured_raw_sidecars_overlay_v2"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _import_baseline_module():
    spec = importlib.util.spec_from_file_location("slice_baseline", BASELINE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import baseline helper from {BASELINE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate per-slice fused full_all/CIRCT artifact directories from "
            "OpenTitan TL-UL launch templates."
        )
    )
    parser.add_argument("--index-json", default=str(SLICE_INDEX_JSON))
    parser.add_argument("--slice", action="append", default=[])
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--cuda-arch", default="sm_80")
    parser.add_argument("--emit-hsaco", action="store_true")
    parser.add_argument("--gfx-arch", default="")
    parser.add_argument("--hybrid-abi", choices=("full-all-only", "synthetic-full-all"), default="synthetic-full-all")
    parser.add_argument("--emit-raw-cuda-sidecars", action="store_true")
    parser.add_argument("--json-out", default="")
    parser.add_argument("--md-out", default="")
    return parser.parse_args(argv)


def _selected_rows(index_payload: dict[str, Any], selected: set[str]) -> list[dict[str, Any]]:
    rows = list(index_payload.get("index") or [])
    if not selected:
        return rows
    return [row for row in rows if str(row.get("slice_name")) in selected]


def _raw_sidecar_overlay_ready(slice_out_dir: Path) -> bool:
    return (slice_out_dir / STRUCTURED_RAW_OVERLAY_MARKER).is_file()


def _generated_dir_ready(slice_out_dir: Path) -> bool:
    fused_dir = slice_out_dir / "fused"
    required = (
        fused_dir / "kernel_generated.api.h",
        fused_dir / "kernel_generated.link.cu",
        fused_dir / "kernel_generated.full_all.cu",
        fused_dir / "kernel_generated.part0.cu",
        fused_dir / "kernel_generated.cluster0.cu",
        fused_dir / "kernel_generated.full_all.circt_driver.cpp",
        fused_dir / "kernel_generated.full_all.circt.cubin",
        slice_out_dir / "pipeline_manifest.json",
    )
    return all(path.is_file() for path in required) and _raw_sidecar_overlay_ready(slice_out_dir)


def _native_hsaco_ready(slice_out_dir: Path) -> bool:
    fused_dir = slice_out_dir / "fused"
    required = (
        fused_dir / "kernel_generated.full_all.hsaco",
        fused_dir / "kernel_generated.full_all.rocm_driver.cpp",
    )
    return all(path.is_file() for path in required)


def _overlay_structured_raw_sidecars(slice_out_dir: Path, *, top_module: str) -> None:
    raw_dir = slice_out_dir / "raw"
    fused_dir = slice_out_dir / "fused"
    raw_base = raw_dir / f"{top_module}.sim_accel.kernel.cu"
    if not raw_base.is_file():
        raise RuntimeError(f"Missing raw kernel base for overlay: {raw_base}")

    overlay_pairs: list[tuple[Path, Path]] = []

    overwrite_names = {
        "kernel_generated.cu",
        "kernel_generated.comm.tsv",
        "kernel_generated.deps.tsv",
        "kernel_generated.partitions.tsv",
        "kernel_generated.clusters.tsv",
        "kernel_generated.preload_targets.tsv",
        "kernel_generated.preload_target_elements.tsv",
        "kernel_generated.preload_targets.json",
        "kernel_generated.full_comb.cu",
        "kernel_generated.full_seq.cu",
    }

    def add_if_exists(src: Path, dst_name: str) -> None:
        if src.is_file():
            dst = fused_dir / dst_name
            if dst.exists() and dst_name not in overwrite_names and not (
                dst_name.startswith("kernel_generated.part")
                or dst_name.startswith("kernel_generated.cluster")
                or dst_name.startswith("kernel_generated.seqpart")
            ):
                return
            overlay_pairs.append((src, dst))

    add_if_exists(raw_base, "kernel_generated.cu")
    for suffix in (
        ".api.h",
        ".link.cu",
        ".comm.tsv",
        ".vars.tsv",
        ".cpu.cpp",
        ".deps.tsv",
        ".partitions.tsv",
        ".clusters.tsv",
        ".preload_targets.tsv",
        ".preload_target_elements.tsv",
        ".preload_targets.json",
        ".full_comb.cu",
        ".full_seq.cu",
        ".full_all.cu",
    ):
        add_if_exists(raw_base.with_name(raw_base.name + suffix), f"kernel_generated{suffix}")
    for candidate in sorted(raw_dir.glob(raw_base.name + ".part*.cu")):
        suffix = candidate.name[len(raw_base.name):]
        overlay_pairs.append((candidate, fused_dir / f"kernel_generated{suffix}"))
    for candidate in sorted(raw_dir.glob(raw_base.name + ".cluster*.cu")):
        suffix = candidate.name[len(raw_base.name):]
        overlay_pairs.append((candidate, fused_dir / f"kernel_generated{suffix}"))

    if not overlay_pairs:
        raise RuntimeError(f"No raw structured sidecars found for overlay under {raw_dir}")

    for src, dst in overlay_pairs:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    (slice_out_dir / STRUCTURED_RAW_OVERLAY_MARKER).write_text(
        f"top_module={top_module}\n",
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    ns = parse_args(argv)
    index_payload = _load_json(Path(ns.index_json).expanduser().resolve())
    baseline = _import_baseline_module()
    out_dir = Path(ns.out_dir).expanduser().resolve()
    if ns.force and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for row in _selected_rows(index_payload, set(ns.slice)):
        slice_name = str(row.get("slice_name"))
        template_path = Path(str(row.get("launch_template_path"))).expanduser().resolve()
        template = _load_json(template_path)
        runner_args = dict(template.get("runner_args_template") or {})
        rtl_path = Path(str(runner_args["rtl_path"])).expanduser().resolve()
        tb_path = Path(str(runner_args["coverage_tb_path"])).expanduser().resolve()
        sources = baseline._collect_compile_sources(slice_name, rtl_path, tb_path)
        slice_out_dir = out_dir / slice_name
        cmd = [
            sys.executable,
            str(HDL_TO_FULL_ALL),
            "--top-module",
            str(runner_args["top_module"]),
            "--out-dir",
            str(slice_out_dir),
            "--program-json-backend",
            "--hybrid-abi",
            ns.hybrid_abi,
            "--emit-circt-ptx",
            "--validate-circt-ptx",
            "--cuda-arch",
            ns.cuda_arch,
        ]
        if ns.emit_hsaco:
            cmd.append("--emit-hsaco")
            if ns.gfx_arch:
                cmd.extend(["--gfx-arch", ns.gfx_arch])
        if ns.emit_raw_cuda_sidecars:
            cmd.append("--emit-raw-cuda-sidecars")
        cmd.extend(
            [
                "--",
                "--timing",
                f"-I{baseline.OPENTITAN_SRC}",
                *[str(path) for path in sources],
            ]
        )
        result: dict[str, Any] = {
            "slice_name": slice_name,
            "template_path": str(template_path),
            "status": "pending",
            "out_dir": str(slice_out_dir),
            "fused_dir": str(slice_out_dir / "fused"),
            "pipeline_manifest": str(slice_out_dir / "pipeline_manifest.json"),
            "command": cmd,
            "cache_hit": False,
        }
        if not ns.force and _generated_dir_ready(slice_out_dir) and (
            (not ns.emit_hsaco) or _native_hsaco_ready(slice_out_dir)
        ):
            result["status"] = "completed"
            result["cache_hit"] = True
        else:
            try:
                subprocess.run(cmd, cwd=ROOT_DIR, check=True)
                _overlay_structured_raw_sidecars(
                    slice_out_dir,
                    top_module=str(runner_args["top_module"]),
                )
                result["status"] = "completed"
            except subprocess.CalledProcessError as exc:
                result["status"] = "failed"
                result["returncode"] = exc.returncode
            except RuntimeError as exc:
                result["status"] = "failed"
                result["error"] = str(exc)
        rows.append(result)

    payload = {
        "schema_version": "opentitan-tlul-slice-generated-dirs-v1",
        "rows": rows,
    }
    json_out = Path(ns.json_out).expanduser().resolve() if ns.json_out else out_dir / "generated_dir_manifest.json"
    md_out = Path(ns.md_out).expanduser().resolve() if ns.md_out else out_dir / "generated_dir_manifest.md"
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# OpenTitan TL-UL Slice Generated Dirs",
        "",
        "| Slice | Status | Fused dir |",
        "|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['slice_name']} | {row['status']} | {row['fused_dir']} |"
        )
    md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json_out)
    print(md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
