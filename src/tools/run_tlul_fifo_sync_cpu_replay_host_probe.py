#!/usr/bin/env python3
"""
Build and run the tlul_fifo_sync cpu-replay wrapper host probe.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_MDIR = REPO_ROOT / "work" / "vl_ir_exp" / "tlul_fifo_sync_cpu_replay_vl"
DEFAULT_TEMPLATE = REPO_ROOT / "config" / "slice_launch_templates" / "tlul_fifo_sync.json"
DEFAULT_BINARY = "tlul_fifo_sync_cpu_replay_host_probe"
MODEL_PREFIX = "Vtlul_fifo_sync_gpu_cov_cpu_replay_tb"
PROBE_SOURCE = REPO_ROOT / "src" / "hybrid" / "tlul_fifo_sync_cpu_replay_host_probe.cpp"
VERILATOR_ROOT = REPO_ROOT / "third_party" / "verilator"

TEMPLATE_TO_WRAPPER_FIELD = {
    "batch_length": "cfg_batch_length",
    "req_valid_pct": "cfg_req_valid_pct",
    "rsp_valid_pct": "cfg_rsp_valid_pct",
    "host_d_ready_pct": "cfg_host_d_ready_pct",
    "device_a_ready_pct": "cfg_device_a_ready_pct",
    "put_full_pct": "cfg_put_full_pct",
    "put_partial_pct": "cfg_put_partial_pct",
    "req_fill_target": "cfg_req_fill_target",
    "req_burst_len_max": "cfg_req_burst_len_max",
    "req_family": "cfg_req_family",
    "req_address_mode": "cfg_req_address_mode",
    "req_data_mode": "cfg_req_data_mode",
    "req_data_hi_xor": "cfg_req_data_hi_xor",
    "access_ack_data_pct": "cfg_access_ack_data_pct",
    "rsp_error_pct": "cfg_rsp_error_pct",
    "rsp_fill_target": "cfg_rsp_fill_target",
    "rsp_delay_max": "cfg_rsp_delay_max",
    "rsp_family": "cfg_rsp_family",
    "rsp_delay_mode": "cfg_rsp_delay_mode",
    "rsp_data_mode": "cfg_rsp_data_mode",
    "rsp_data_hi_xor": "cfg_rsp_data_hi_xor",
    "reset_cycles": "cfg_reset_cycles",
    "drain_cycles": "cfg_drain_cycles",
    "seed": "cfg_seed",
    "address_base": "cfg_address_base",
    "address_mask": "cfg_address_mask",
    "source_mask": "cfg_source_mask",
}


def _load_template_settings(template_path: Path | None) -> dict[str, int]:
    if template_path is None or not template_path.is_file():
        return {}
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    args = dict(payload.get("runner_args_template") or {})
    driver_defaults = dict(args.get("driver_defaults") or {})
    merged: dict[str, int] = {}
    if "batch_length" in args:
        merged["cfg_batch_length"] = int(args["batch_length"])
    for key, field_name in TEMPLATE_TO_WRAPPER_FIELD.items():
        if key in driver_defaults:
            raw_value = driver_defaults[key]
            merged[field_name] = int(raw_value, 0) if isinstance(raw_value, str) else int(raw_value)
    return merged


def _apply_overrides(settings: dict[str, int], raw_overrides: list[str]) -> dict[str, int]:
    updated = dict(settings)
    for raw in raw_overrides:
        if "=" not in raw:
            raise ValueError(f"bad --set {raw!r} (want field=value)")
        name, raw_value = raw.split("=", 1)
        updated[name] = int(raw_value, 0)
    return updated


def build_probe_binary(
    mdir: Path,
    binary_out: Path,
    *,
    cxx: str = "g++",
) -> Path:
    mdir = mdir.resolve()
    binary_out = binary_out.resolve()
    mk_path = mdir / f"{MODEL_PREFIX}.mk"
    if not mk_path.is_file():
        raise FileNotFoundError(f"{mk_path} not found")
    if not PROBE_SOURCE.is_file():
        raise FileNotFoundError(f"{PROBE_SOURCE} not found")

    env = os.environ.copy()
    env.setdefault("VERILATOR_ROOT", str(VERILATOR_ROOT))
    subprocess.run(
        ["make", "-C", str(mdir), "-f", mk_path.name, f"lib{MODEL_PREFIX}"],
        check=True,
        env=env,
    )

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
        str(PROBE_SOURCE),
        str(mdir / f"lib{MODEL_PREFIX}.a"),
        str(mdir / "libverilated.a"),
        "-pthread",
        "-o",
        str(binary_out),
    ]
    subprocess.run(compile_cmd, check=True)
    return binary_out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mdir", type=Path, default=DEFAULT_MDIR)
    p.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    p.add_argument("--binary-out", type=Path)
    p.add_argument("--json-out", type=Path)
    p.add_argument("--state-out", type=Path)
    p.add_argument("--clock-cycles", type=int, default=6)
    p.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    p.add_argument("--build-only", action="store_true")
    args = p.parse_args()

    mdir = args.mdir.resolve()
    template_path = args.template.resolve()
    binary_out = (args.binary_out or (mdir / DEFAULT_BINARY)).resolve()
    binary_path = build_probe_binary(mdir, binary_out)
    if args.build_only:
        print(binary_path)
        return

    settings = _load_template_settings(template_path if template_path.is_file() else None)
    settings["cfg_valid"] = 1
    settings = _apply_overrides(settings, list(args.set))

    cmd = [
        str(binary_path),
        "--clock-cycles",
        str(args.clock_cycles),
    ]
    state_out = args.state_out.resolve() if args.state_out else None
    if state_out is not None:
        state_out.parent.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--state-out", str(state_out)])
    for name in sorted(settings):
        cmd.extend(["--set", f"{name}={settings[name]}"])

    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    payload = json.loads(result.stdout)
    payload["configured_inputs"] = settings
    payload["clock_ownership"] = "tb_timed_coroutine"
    payload["probe_kind"] = "no_port_cpu_replay_wrapper"
    payload["probe_binary"] = str(binary_path)
    payload["template_path"] = str(template_path) if template_path.is_file() else None
    payload["mdir"] = str(mdir)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.json_out:
        json_out = args.json_out.resolve()
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)


if __name__ == "__main__":
    main()
