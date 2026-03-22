#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent

GENERATE_SCRIPT = SCRIPT_DIR / "run_opentitan_tlul_slice_gpu_baseline.py"
PREPARE_PLAN_SCRIPT = ROOT_DIR / "src/runners/opentitan_support/prepare_backend_compare_plan.py"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run GPU vs CPU backend comparison for an OpenTitan TLUL slice"
    )
    parser.add_argument("--slice", required=True)
    parser.add_argument("--generated-root", required=True)
    parser.add_argument("--compare-root", required=True)
    parser.add_argument("--summary-json", required=True)
    parser.add_argument("--summary-md", required=True)
    args = parser.parse_args(argv)

    generated_root = Path(args.generated_root)
    compare_root = Path(args.compare_root)
    compare_root.mkdir(parents=True, exist_ok=True)

    manifest_path = generated_root / "generated_dir_manifest.json"
    manifest = _load_json(manifest_path)

    row = next(
        (r for r in manifest.get("rows", []) if r.get("slice_name") == args.slice),
        None,
    )
    fused_dir = row["fused_dir"] if row else str(generated_root / args.slice / "fused")

    subprocess.run(
        [
            sys.executable,
            str(GENERATE_SCRIPT),
            "--slice", args.slice,
            "--fused-dir", fused_dir,
            "--emit-raw-cuda-sidecars",
        ],
        cwd=compare_root,
        check=True,
    )

    subprocess.run(
        [
            sys.executable,
            str(PREPARE_PLAN_SCRIPT),
            "--slice", args.slice,
            "--compare-root", str(compare_root),
        ],
        cwd=compare_root,
        check=True,
    )

    plan_path = compare_root / "backend_compare_plan.json"
    plan = _load_json(plan_path) if plan_path.exists() else {"rows": []}

    summary = {
        "slice_name": args.slice,
        "compare_root": str(compare_root),
        "plan_row_count": len(plan.get("rows", [])),
    }
    Path(args.summary_json).write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    Path(args.summary_md).write_text(
        f"# Backend Compare: {args.slice}\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
