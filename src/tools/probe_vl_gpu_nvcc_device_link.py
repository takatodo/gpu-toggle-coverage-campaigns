#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any


def _run_step(cmd: list[str], *, timeout_seconds: int) -> dict[str, Any]:
    started_at_ms = time.time_ns() / 1_000_000
    completed: subprocess.CompletedProcess[str] | None = None
    timeout_expired: subprocess.TimeoutExpired | None = None
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        timeout_expired = exc

    elapsed_ms = time.time_ns() / 1_000_000 - started_at_ms
    if timeout_expired is not None:
        return {
            "command": cmd,
            "status": "timed_out",
            "returncode": None,
            "elapsed_ms": elapsed_ms,
            "stdout_tail": "\n".join((timeout_expired.stdout or "").splitlines()[-40:]),
            "stderr_tail": "\n".join((timeout_expired.stderr or "").splitlines()[-40:]),
        }
    assert completed is not None
    return {
        "command": cmd,
        "status": "ok" if completed.returncode == 0 else ("killed" if completed.returncode < 0 else "error"),
        "returncode": completed.returncode,
        "elapsed_ms": elapsed_ms,
        "stdout_tail": "\n".join((completed.stdout or "").splitlines()[-40:]),
        "stderr_tail": "\n".join((completed.stderr or "").splitlines()[-40:]),
    }


def _symbol_present(path: Path, symbol_name: str) -> bool | None:
    if not path.is_file():
        return None
    completed = subprocess.run(
        ["cuobjdump", "--dump-elf-symbols", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    haystack = "\n".join([completed.stdout or "", completed.stderr or ""])
    return symbol_name in haystack


def _size_if_exists(path: Path) -> int | None:
    if not path.is_file():
        return None
    return path.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile PTX to a relocatable device object via nvcc --device-c and then "
            "link it to an executable device image via nvcc --device-link."
        )
    )
    parser.add_argument("--ptx", type=Path, required=True)
    parser.add_argument("--object-out", type=Path, required=True)
    parser.add_argument("--linked-out", type=Path, required=True)
    parser.add_argument("--sm", default="sm_89")
    parser.add_argument("--linked-kind", choices=("cubin", "fatbin"), default="cubin")
    parser.add_argument("--kernel-symbol", default="vl_eval_batch_gpu")
    parser.add_argument("--compile-timeout-seconds", type=int, default=240)
    parser.add_argument("--link-timeout-seconds", type=int, default=240)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()

    ptx = args.ptx.resolve()
    object_out = args.object_out.resolve()
    linked_out = args.linked_out.resolve()
    json_out = args.json_out.resolve()
    if not ptx.is_file():
        raise FileNotFoundError(f"PTX not found: {ptx}")

    object_out.parent.mkdir(parents=True, exist_ok=True)
    linked_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    object_out.unlink(missing_ok=True)
    linked_out.unlink(missing_ok=True)

    compile_cmd = [
        "nvcc",
        f"--gpu-architecture={args.sm}",
        "--device-c",
        str(ptx),
        "-o",
        str(object_out),
    ]
    compile_step = _run_step(compile_cmd, timeout_seconds=args.compile_timeout_seconds)

    if compile_step["status"] == "ok":
        link_cmd = [
            "nvcc",
            f"--gpu-architecture={args.sm}",
            "--device-link",
            str(object_out),
            f"--{args.linked_kind}",
            "-o",
            str(linked_out),
            "--verbose",
        ]
        link_step = _run_step(link_cmd, timeout_seconds=args.link_timeout_seconds)
    else:
        link_step = {
            "command": None,
            "status": "skipped",
            "returncode": None,
            "elapsed_ms": 0.0,
            "stdout_tail": "",
            "stderr_tail": "",
        }

    payload = {
        "schema_version": 1,
        "scope": "probe_vl_gpu_nvcc_device_link",
        "ptx": str(ptx),
        "sm": args.sm,
        "linked_kind": args.linked_kind,
        "kernel_symbol": args.kernel_symbol,
        "compile_timeout_seconds": args.compile_timeout_seconds,
        "link_timeout_seconds": args.link_timeout_seconds,
        "compile": compile_step,
        "link": link_step,
        "observations": {
            "object_path": str(object_out),
            "object_exists": object_out.is_file(),
            "object_size": _size_if_exists(object_out),
            "object_kernel_symbol_present": _symbol_present(object_out, args.kernel_symbol),
            "linked_path": str(linked_out),
            "linked_exists": linked_out.is_file(),
            "linked_size": _size_if_exists(linked_out),
            "linked_kernel_symbol_present": _symbol_present(linked_out, args.kernel_symbol),
        },
    }
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
