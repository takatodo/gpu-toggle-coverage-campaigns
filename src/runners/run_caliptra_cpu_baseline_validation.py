#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from enrollment_common import (
    ensure_runtime_input,
    load_enrollment,
    load_template,
    run_cpu_baseline_validation,
    runner_args,
)


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
DEFAULT_MDIR = ROOT_DIR / "work" / "vl_ir_exp" / "caliptra_gpu_cov_vl"
DEFAULT_TEMPLATE = ROOT_DIR / "config" / "slice_launch_templates" / "caliptra.json"
DEFAULT_JSON_OUT = ROOT_DIR / "output" / "validation" / "caliptra_cpu_baseline_validation.json"
DEFAULT_PROGRAM_HEX = (
    ROOT_DIR / "third_party" / "rtlmeter" / "designs" / "Caliptra" / "tests" / "hello" / "program.hex"
)
DEFAULT_DCCM_HEX = (
    ROOT_DIR / "third_party" / "rtlmeter" / "designs" / "Caliptra" / "tests" / "hello" / "dccm.hex"
)
DEFAULT_ICCM_HEX = (
    ROOT_DIR / "third_party" / "rtlmeter" / "designs" / "Caliptra" / "tests" / "hello" / "iccm.hex"
)
DEFAULT_MAILBOX_HEX = (
    ROOT_DIR / "third_party" / "rtlmeter" / "designs" / "Caliptra" / "tests" / "hello" / "mailbox.hex"
)
DEFAULT_TARGET = "caliptra"
DEFAULT_TOP_MODULE = "caliptra_gpu_cov_tb"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Run the stock-Verilator CPU baseline validation for Caliptra."
    )
    parser.add_argument("--mdir", type=Path, default=DEFAULT_MDIR)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--program-hex", type=Path, default=DEFAULT_PROGRAM_HEX)
    parser.add_argument("--dccm-hex", type=Path, default=DEFAULT_DCCM_HEX)
    parser.add_argument("--iccm-hex", type=Path, default=DEFAULT_ICCM_HEX)
    parser.add_argument("--mailbox-hex", type=Path, default=DEFAULT_MAILBOX_HEX)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--host-reset-cycles", type=int, default=4)
    parser.add_argument("--host-post-reset-cycles", type=int, default=64)
    parser.add_argument("--campaign-threshold-bits", type=int, default=8)
    args = parser.parse_args(argv)

    mdir = args.mdir.resolve()
    template_path = args.template.resolve()
    program_hex = args.program_hex.resolve()
    dccm_hex = args.dccm_hex.resolve()
    iccm_hex = args.iccm_hex.resolve()
    mailbox_hex = args.mailbox_hex.resolve()
    json_out = args.json_out.resolve()

    template_payload = load_template(template_path)
    enrollment = load_enrollment(template_payload)
    runtime_inputs, extra_defines = ensure_runtime_input(
        mdir=mdir,
        runtime_input_type=str(enrollment["runtime_input_type"]),
        runtime_input_path=program_hex,
        top_module=str(runner_args(template_payload).get("top_module") or DEFAULT_TOP_MODULE),
        runtime_input_format=(
            str(enrollment.get("runtime_input_format"))
            if enrollment.get("runtime_input_format") is not None
            else None
        ),
        runtime_input_target=(
            dict(enrollment.get("runtime_input_target"))
            if isinstance(enrollment.get("runtime_input_target"), dict)
            else None
        ),
        runtime_input_target_path=(
            (ROOT_DIR / str(enrollment["runtime_input_target_path"])).resolve()
            if "runtime_input_target_path" in enrollment
            else None
        ),
        runtime_input_name=(
            str(enrollment.get("runtime_input_name"))
            if enrollment.get("runtime_input_name") is not None
            else None
        ),
        runtime_input_companion_paths=[dccm_hex, iccm_hex, mailbox_hex],
        runtime_input_patch_bytes=(
            list(enrollment.get("runtime_input_patch_bytes"))
            if isinstance(enrollment.get("runtime_input_patch_bytes"), list)
            else None
        ),
    )

    payload = run_cpu_baseline_validation(
        slug=DEFAULT_TARGET,
        mdir=mdir,
        template_path=template_path,
        runtime_inputs=runtime_inputs,
        extra_defines=extra_defines,
        runtime_input_type=str(enrollment["runtime_input_type"]),
        host_reset_cycles=args.host_reset_cycles,
        host_post_reset_cycles=args.host_post_reset_cycles,
        support_tier=str(template_payload.get("status") or "candidate_non_opentitan_single_surface"),
        campaign_threshold_bits=args.campaign_threshold_bits,
        json_out=json_out,
    )
    return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
