#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


def build_probe_payload(
    *,
    ptx: Path,
    output_path: Path,
    sm: str,
    opt_level: int,
    timeout_seconds: int,
    compile_only: bool,
    cmd: list[str],
    started_at_ms: float,
    completed: subprocess.CompletedProcess[str] | None,
    timeout_expired: subprocess.TimeoutExpired | None,
) -> dict:
    elapsed_ms = time.time_ns() / 1_000_000 - started_at_ms
    if timeout_expired is not None:
        status = "timed_out"
        returncode = None
        stdout = timeout_expired.stdout or ""
        stderr = timeout_expired.stderr or ""
    elif completed is None:
        status = "unknown"
        returncode = None
        stdout = ""
        stderr = ""
    else:
        returncode = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        if returncode == 0:
            status = "ok"
        elif returncode < 0:
            status = "killed"
        else:
            status = "error"

    return {
        "schema_version": 1,
        "scope": "probe_vl_gpu_ptxas",
        "ptx": str(ptx),
        "output_path": str(output_path),
        "compile_only": compile_only,
        "output_kind": "relocatable_object" if compile_only else "cubin",
        "cubin_out": str(output_path),
        "sm": sm,
        "opt_level": opt_level,
        "timeout_seconds": timeout_seconds,
        "command": cmd,
        "status": status,
        "returncode": returncode,
        "elapsed_ms": elapsed_ms,
        "output_exists": output_path.is_file(),
        "output_size": output_path.stat().st_size if output_path.is_file() else None,
        "cubin_exists": output_path.is_file(),
        "cubin_size": output_path.stat().st_size if output_path.is_file() else None,
        "stdout_tail": "\n".join(stdout.splitlines()[-40:]) if stdout else "",
        "stderr_tail": "\n".join(stderr.splitlines()[-40:]) if stderr else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run ptxas under a timeout and summarize the attempt as JSON."
    )
    parser.add_argument("--ptx", type=Path, required=True)
    parser.add_argument("--cubin-out", type=Path, required=True)
    parser.add_argument("--sm", default="sm_89")
    parser.add_argument("--opt-level", type=int, choices=(0, 1, 2, 3), default=0)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument(
        "--compile-only",
        action="store_true",
        help="Pass --compile-only to ptxas and treat the output as a relocatable object probe.",
    )
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()

    ptx = args.ptx.resolve()
    output_path = args.cubin_out.resolve()
    json_out = args.json_out.resolve()
    if not ptx.is_file():
        raise FileNotFoundError(f"PTX not found: {ptx}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    cmd = [
        "ptxas",
        "--gpu-name",
        args.sm,
        "--opt-level",
        str(args.opt_level),
        "--verbose",
    ]
    if args.compile_only:
        cmd.append("--compile-only")
    cmd.extend([str(ptx), "-o", str(output_path)])
    started_at_ms = time.time_ns() / 1_000_000
    completed: subprocess.CompletedProcess[str] | None = None
    timeout_expired: subprocess.TimeoutExpired | None = None
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=args.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        timeout_expired = exc

    payload = build_probe_payload(
        ptx=ptx,
        output_path=output_path,
        sm=args.sm,
        opt_level=args.opt_level,
        timeout_seconds=args.timeout_seconds,
        compile_only=args.compile_only,
        cmd=cmd,
        started_at_ms=started_at_ms,
        completed=completed,
        timeout_expired=timeout_expired,
    )
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
