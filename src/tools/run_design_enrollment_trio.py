#!/usr/bin/env python3
"""
Generic enrollment trio runner for RTLMeter designs with extended launch templates.

Runs stock-hybrid validation, CPU baseline validation, and time-to-threshold
comparison for any design whose launch template has an "enrollment" section.

Template enrollment section (required):
  {
    "enrollment": {
      "slug":               "veer_eh2",
      "mdir_name":          "veer_eh2_gpu_cov_vl",
      "runtime_input_type": "program_hex",    # or "case_pat" / "memory_image" / "runtime_file"
      "runtime_input_path": "third_party/rtlmeter/designs/VeeR-EH2/tests/hello/program.hex"
    }
  }

Usage:
  # Run full trio for VeeR-EH2 (bootstrap must be done first):
  python3 src/tools/run_design_enrollment_trio.py \\
    --template config/slice_launch_templates/veer_eh2.json

  # Run trio and auto-probe best candidate threshold if comparison is unresolved:
  python3 src/tools/run_design_enrollment_trio.py \\
    --template config/slice_launch_templates/veer_eh2.json --probe-threshold

  # Run a single stage:
  python3 src/tools/run_design_enrollment_trio.py \\
    --template config/slice_launch_templates/veer_eh2.json --stage hybrid
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
RUNNERS_DIR = ROOT_DIR / "src" / "runners"

if str(RUNNERS_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNERS_DIR))

from enrollment_common import (
    ensure_runtime_input,
    load_enrollment,
    load_template,
    probe_best_threshold,
    run_cpu_baseline_validation,
    run_hybrid_validation,
    runner_args,
)
from stock_hybrid_validation_common import read_json_if_exists, write_json
from time_to_threshold_comparison_common import build_comparison_payload


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--template", type=Path, required=True, help="Launch template JSON with enrollment section")
    parser.add_argument(
        "--stage",
        choices=("all", "hybrid", "baseline", "comparison"),
        default="all",
        help="Which stage(s) to run (default: all)",
    )
    parser.add_argument("--campaign-threshold-bits", type=int, default=8)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--host-reset-cycles", type=int, default=4)
    parser.add_argument("--host-post-reset-cycles", type=int, default=64)
    parser.add_argument(
        "--probe-threshold",
        action="store_true",
        help="If comparison is unresolved, analytically probe the best candidate threshold",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "output" / "validation",
    )
    args = parser.parse_args(argv)

    template_path = args.template.resolve()
    tmpl = load_template(template_path)
    enroll = load_enrollment(tmpl)
    rargs = runner_args(tmpl)

    slug = enroll["slug"]
    mdir_name = enroll["mdir_name"]
    runtime_input_type = enroll["runtime_input_type"]
    runtime_input_path = (ROOT_DIR / enroll["runtime_input_path"]).resolve()
    top_module = str(rargs.get("top_module") or f"{slug}_gpu_cov_tb")
    support_tier = str(tmpl.get("status") or "candidate_non_opentitan_single_surface")
    nstates = int(rargs.get("gpu_nstates", 8))
    steps = int(rargs.get("gpu_sequential_steps", 56))

    mdir = (ROOT_DIR / "work" / "vl_ir_exp" / mdir_name).resolve()
    mdir.mkdir(parents=True, exist_ok=True)
    out_dir = args.output_dir.resolve()

    hybrid_json = out_dir / f"{slug}_stock_hybrid_validation.json"
    baseline_json = out_dir / f"{slug}_cpu_baseline_validation.json"
    comparison_json = out_dir / f"{slug}_time_to_threshold_comparison.json"
    probe_json = out_dir / f"{slug}_threshold_probe.json"

    runtime_inputs, extra_defines = ensure_runtime_input(
        mdir=mdir,
        runtime_input_type=runtime_input_type,
        runtime_input_path=runtime_input_path,
        top_module=top_module,
        runtime_input_format=(
            str(enroll.get("runtime_input_format"))
            if enroll.get("runtime_input_format") is not None
            else None
        ),
        runtime_input_target=(
            dict(enroll.get("runtime_input_target"))
            if isinstance(enroll.get("runtime_input_target"), dict)
            else None
        ),
        runtime_input_target_path=(
            (ROOT_DIR / str(enroll["runtime_input_target_path"])).resolve()
            if "runtime_input_target_path" in enroll
            else None
        ),
        runtime_input_name=(
            str(enroll.get("runtime_input_name"))
            if enroll.get("runtime_input_name") is not None
            else None
        ),
        runtime_input_companion_paths=(
            [
                (ROOT_DIR / str(raw_path)).resolve()
                for raw_path in list(enroll.get("runtime_input_companion_paths") or [])
            ]
            if isinstance(enroll.get("runtime_input_companion_paths"), list)
            else None
        ),
        runtime_input_patch_bytes=(
            list(enroll.get("runtime_input_patch_bytes"))
            if isinstance(enroll.get("runtime_input_patch_bytes"), list)
            else None
        ),
    )

    rc = 0
    common_kwargs = dict(
        host_reset_cycles=args.host_reset_cycles,
        host_post_reset_cycles=args.host_post_reset_cycles,
        support_tier=support_tier,
        campaign_threshold_bits=args.campaign_threshold_bits,
    )

    if args.stage in ("all", "hybrid"):
        print(f"[enrollment] hybrid validation: {slug}")
        p = run_hybrid_validation(
            slug=slug, mdir=mdir, template_path=template_path,
            runtime_inputs=runtime_inputs, extra_defines=extra_defines,
            runtime_input_type=runtime_input_type,
            nstates=nstates, steps=steps, block_size=args.block_size,
            json_out=hybrid_json,
            **common_kwargs,
        )
        cm = p.get("campaign_measurement", {})
        print(f"  status={p['status']}  bits_hit={cm.get('bits_hit')}  "
              f"threshold_satisfied={cm.get('threshold_satisfied')}  "
              f"wall_time_ms={cm.get('wall_time_ms')}")
        if p["status"] != "ok":
            rc = 1

    if args.stage in ("all", "baseline"):
        print(f"[enrollment] cpu baseline validation: {slug}")
        p = run_cpu_baseline_validation(
            slug=slug, mdir=mdir, template_path=template_path,
            runtime_inputs=runtime_inputs, extra_defines=extra_defines,
            runtime_input_type=runtime_input_type,
            json_out=baseline_json,
            **common_kwargs,
        )
        cm = p.get("campaign_measurement", {})
        print(f"  status={p['status']}  bits_hit={cm.get('bits_hit')}  "
              f"threshold_satisfied={cm.get('threshold_satisfied')}  "
              f"wall_time_ms={cm.get('wall_time_ms')}")
        if p["status"] != "ok":
            rc = 1

    if args.stage in ("all", "comparison"):
        print(f"[enrollment] time-to-threshold comparison: {slug}")
        baseline_p = read_json_if_exists(baseline_json)
        hybrid_p = read_json_if_exists(hybrid_json)
        comp_rc, comp_payload = build_comparison_payload(
            baseline_path=baseline_json,
            hybrid_path=hybrid_json,
            baseline_payload=baseline_p,
            hybrid_payload=hybrid_p,
        )
        write_json(comparison_json, comp_payload)
        winner = comp_payload.get("winner")
        speedup = comp_payload.get("speedup_ratio")
        print(f"  winner={winner}  speedup_ratio={speedup}")

        if winner == "unresolved" and args.probe_threshold:
            print(f"[enrollment] unresolved — probing best candidate threshold: {slug}")
            probe = probe_best_threshold(
                slug=slug,
                hybrid_payload=hybrid_p or {},
                baseline_payload=baseline_p or {},
                json_out=probe_json,
            )
            print(f"  status={probe.get('status')}  "
                  f"candidate_threshold={probe.get('candidate_threshold')}  "
                  f"winner={probe.get('winner')}  speedup_ratio={probe.get('speedup_ratio')}")

        if comp_rc != 0:
            rc = comp_rc

    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
