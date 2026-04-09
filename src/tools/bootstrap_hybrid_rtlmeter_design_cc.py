#!/usr/bin/env python3
"""
Create work/vl_ir_exp/<design>_<config>_vl (or --out-dir) with stock Verilator
--cc output for a generic RTLMeter design/config pair.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RTLMETER_ROOT = ROOT / "third_party" / "rtlmeter"
RTLMETER_SRC = RTLMETER_ROOT / "src"
RTLMETER_VENV = ROOT / "rtlmeter" / "venv"
DEFAULT_VERILATOR = ROOT / "third_party" / "verilator" / "bin" / "verilator"


def _ensure_import_paths() -> None:
    for path in (ROOT / "src", ROOT / "src" / "runners", ROOT / "src" / "scripts", RTLMETER_SRC):
        text = str(path)
        if text not in sys.path:
            sys.path.insert(0, text)
    for site_packages in sorted((RTLMETER_VENV / "lib").glob("python*/site-packages")):
        text = str(site_packages)
        if text not in sys.path:
            sys.path.insert(0, text)
    os.environ.setdefault("RTLMETER_ROOT", str(RTLMETER_ROOT))


def _load_compile_descriptor(compile_case: str) -> Any:
    _ensure_import_paths()
    from rtlmeter.descriptors import CompileDescriptor  # type: ignore

    return CompileDescriptor(compile_case)


def _slug(text: str) -> str:
    slug = []
    for ch in text:
        if ch.isalnum():
            slug.append(ch.lower())
        else:
            slug.append("_")
    collapsed = "".join(slug)
    while "__" in collapsed:
        collapsed = collapsed.replace("__", "_")
    return collapsed.strip("_")


def _replace_with_symlink(dst: Path, src: Path) -> None:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    dst.symlink_to(src)


def _stage_by_basename(paths: list[str], dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    seen: dict[str, Path] = {}
    for raw in paths:
        src = Path(raw).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(f"descriptor file missing: {src}")
        basename = src.name
        previous = seen.get(basename)
        if previous is not None and previous != src:
            raise RuntimeError(
                "basename collision while staging descriptor files: "
                f"{basename}: {previous} vs {src}"
            )
        seen[basename] = src
        dst = dest_dir / basename
        _replace_with_symlink(dst, src)
        staged.append(dst)
    return staged


def _stage_filelist(out_dir: Path, compile_desc: Any) -> tuple[Path, Path, Path]:
    source_dir = out_dir / "verilogSourceFiles"
    include_dir = out_dir / "verilogIncludeFiles"
    _stage_by_basename(list(compile_desc.verilogSourceFiles), source_dir)
    _stage_by_basename(list(compile_desc.verilogIncludeFiles), include_dir)
    filelist_path = out_dir / "filelist"
    filelist_lines = [f"verilogSourceFiles/{Path(path).name}" for path in compile_desc.verilogSourceFiles]
    filelist_path.write_text("\n".join(filelist_lines) + "\n", encoding="utf-8")
    return source_dir, include_dir, filelist_path


def _cpp_include_dirs(compile_desc: Any) -> list[Path]:
    include_dirs: list[Path] = []
    seen: set[Path] = set()
    for raw in list(getattr(compile_desc, "cppSourceFiles", []) or []):
        path = Path(raw).expanduser().resolve().parent
        if path not in seen:
            seen.add(path)
            include_dirs.append(path)
    for raw in list(getattr(compile_desc, "cppIncludeFiles", []) or []):
        path = Path(raw).expanduser().resolve().parent
        if path not in seen:
            seen.add(path)
            include_dirs.append(path)
    return include_dirs


def _build_cmd(
    *,
    verilator: Path,
    out_dir: Path,
    compile_desc: Any,
    source_dir: Path,
    include_dir: Path,
    filelist_path: Path,
) -> list[str]:
    cmd = [
        str(verilator),
        "--cc",
        "--flatten",
        "-Wno-fatal",
        "--top-module",
        str(compile_desc.topModule),
        "-Mdir",
        str(out_dir),
    ]
    cmd.extend(str(arg) for arg in list(compile_desc.verilatorArgs))
    cmd.append(f"+incdir+{source_dir}")
    if include_dir.exists():
        cmd.append(f"+incdir+{include_dir}")
    cmd.append("+define+__RTLMETER_SIM_ACCEL=1")
    for key, value in sorted(dict(getattr(compile_desc, "verilogDefines", {}) or {}).items()):
        cmd.append(f"+define+{key}={value}")
    for include_dir in _cpp_include_dirs(compile_desc):
        cmd.extend(["-CFLAGS", f"-I{include_dir}"])
    for key, value in sorted(dict(getattr(compile_desc, "cppDefines", {}) or {}).items()):
        if value is None or value is True or value == "":
            cmd.extend(["-CFLAGS", f"-D{key}"])
        else:
            cmd.extend(["-CFLAGS", f"-D{key}={value}"])
    cmd.extend(["-f", str(filelist_path)])
    cmd.extend(str(Path(path).expanduser().resolve()) for path in list(getattr(compile_desc, "cppSourceFiles", []) or []))
    return cmd


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _default_out_dir(compile_case: str) -> Path:
    return ROOT / "work" / "vl_ir_exp" / f"{_slug(compile_case)}_vl"


def _default_json_out(compile_case: str) -> Path:
    return ROOT / "work" / f"{_slug(compile_case)}_stock_verilator_cc_bootstrap.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--compile-case",
        default="XuanTie-E902:gpu_cov_gate",
        help="RTLMeter compile case, for example XuanTie-E902:gpu_cov_gate",
    )
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument(
        "--verilator",
        default=os.environ.get("VERILATOR", str(DEFAULT_VERILATOR)),
        help="verilator binary (default: $VERILATOR or third_party/verilator/bin/verilator)",
    )
    parser.add_argument("--force", action="store_true", help="Remove out-dir before running Verilator")
    args = parser.parse_args(argv)

    compile_case = str(args.compile_case)
    out_dir = (args.out_dir.expanduser().resolve() if args.out_dir else _default_out_dir(compile_case).resolve())
    json_out = (args.json_out.expanduser().resolve() if args.json_out else _default_json_out(compile_case).resolve())
    verilator = Path(args.verilator).expanduser().resolve()

    payload: dict[str, Any] = {
        "schema_version": 1,
        "scope": "rtlmeter_stock_verilator_cc_bootstrap",
        "compile_case": compile_case,
        "out_dir": str(out_dir),
        "verilator": str(verilator),
    }

    if not verilator.is_file():
        payload["status"] = "error"
        payload["error"] = f"verilator not found: {verilator}"
        _write_json(json_out, payload)
        return 1

    try:
        compile_desc = _load_compile_descriptor(compile_case)
    except Exception as exc:  # pragma: no cover - exercised through tests via error payload
        payload["status"] = "error"
        payload["error"] = f"failed to load compile descriptor: {exc}"
        _write_json(json_out, payload)
        return 1

    if args.force and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        source_dir, include_dir, filelist_path = _stage_filelist(out_dir, compile_desc)
        cmd = _build_cmd(
            verilator=verilator,
            out_dir=out_dir,
            compile_desc=compile_desc,
            source_dir=source_dir,
            include_dir=include_dir,
            filelist_path=filelist_path,
        )
        env = os.environ.copy()
        env.setdefault("VERILATOR_ROOT", str(ROOT / "third_party" / "verilator"))
        proc = subprocess.run(cmd, text=True, capture_output=True, check=False, cwd=str(out_dir), env=env)
    except Exception as exc:
        payload.update(
            {
                "status": "error",
                "design": str(getattr(compile_desc, "design", "")),
                "config": str(getattr(compile_desc, "config", "")),
                "top_module": str(getattr(compile_desc, "topModule", "")),
                "error": str(exc),
            }
        )
        _write_json(json_out, payload)
        return 1

    classes_mk = sorted(out_dir.glob("*_classes.mk"))
    payload.update(
        {
            "status": "ok" if proc.returncode == 0 and bool(classes_mk) else "error",
            "design": str(compile_desc.design),
            "config": str(compile_desc.config),
            "top_module": str(compile_desc.topModule),
            "verilog_source_count": len(list(compile_desc.verilogSourceFiles)),
            "verilog_include_count": len(list(compile_desc.verilogIncludeFiles)),
            "cpp_source_count": len(list(getattr(compile_desc, "cppSourceFiles", []) or [])),
            "cpp_include_count": len(list(getattr(compile_desc, "cppIncludeFiles", []) or [])),
            "verilator_args": list(compile_desc.verilatorArgs),
            "filelist": str(filelist_path),
            "verilator_cmd": cmd,
            "returncode": int(proc.returncode),
            "classes_mk": str(classes_mk[0]) if classes_mk else "",
            "stdout_tail": "\n".join(proc.stdout.splitlines()[-40:]),
            "stderr_tail": "\n".join(proc.stderr.splitlines()[-40:]),
        }
    )
    if proc.returncode != 0 and not payload["stderr_tail"] and not payload["stdout_tail"]:
        payload["error"] = "verilator returned nonzero without stdout/stderr output"
    elif proc.returncode == 0 and not classes_mk:
        payload["error"] = "verilator finished but no *_classes.mk was produced"

    _write_json(json_out, payload)
    print(json_out)
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
