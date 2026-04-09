"""
Shared logic for generic design enrollment: runtime input setup, payload building,
threshold probe. Used by run_design_enrollment_trio (CLI entrypoint).

Supports runtime input types:
  - "program_hex":          VeeR-style hidden preload via program_entries.bin
  - "case_pat":             XuanTie-style case.pat symlink
  - "memory_image":         descriptor-backed contiguous RAM preload (for example program.bin)
  - "runtime_file":         staged file copied into mdir and consumed by model helper code
                             Optional companion files may be staged alongside it.
  - "blackparrot_prog_mem": BlackParrot readmemh byte image lowered into packed
                             gpu_cov_program_words preload entries
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

from stock_hybrid_validation_common import (
    campaign_threshold_toggle_bits_hit,
    parse_gpu_metrics,
    read_json_if_exists,
    toggle_coverage_summary,
    write_json,
)

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
FLOW_TOOL = ROOT_DIR / "src" / "tools" / "run_tlul_slice_host_gpu_flow.py"
HOST_PROBE_TOOL = ROOT_DIR / "src" / "tools" / "run_tlul_slice_host_probe.py"

STANDARD_OUTPUT_NAMES = [
    "done_o",
    "cfg_signature_o",
    "host_req_accepted_o",
    "device_req_accepted_o",
    "device_rsp_accepted_o",
    "host_rsp_accepted_o",
    "rsp_queue_overflow_o",
    "progress_cycle_count_o",
    "progress_signature_o",
    "toggle_bitmap_word0_o",
    "toggle_bitmap_word1_o",
    "toggle_bitmap_word2_o",
]

REFERENCE_GATE_NAME = "candidate_non_opentitan_single_surface_v1"


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

def load_template(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_enrollment(tmpl: dict[str, Any]) -> dict[str, Any]:
    """Extract and validate the enrollment section from a launch template."""
    enroll = tmpl.get("enrollment")
    if not isinstance(enroll, dict):
        raise ValueError("template missing 'enrollment' section")
    for key in ("slug", "mdir_name", "runtime_input_type", "runtime_input_path"):
        if key not in enroll:
            raise ValueError(f"enrollment missing required key: {key!r}")
    rt = enroll["runtime_input_type"]
    if rt not in (
        "program_hex",
        "case_pat",
        "memory_image",
        "runtime_file",
        "blackparrot_prog_mem",
    ):
        raise ValueError(
            f"unsupported runtime_input_type: {rt!r} "
            "("
            "expected 'program_hex', 'case_pat', 'memory_image', "
            "'runtime_file', or 'blackparrot_prog_mem'"
            ")"
        )
    if rt in ("memory_image", "blackparrot_prog_mem"):
        if "runtime_input_target" not in enroll and "runtime_input_target_path" not in enroll:
            raise ValueError(
                f"{rt} enrollment requires 'runtime_input_target' or 'runtime_input_target_path'"
            )
    return enroll


def runner_args(tmpl: dict[str, Any]) -> dict[str, Any]:
    return dict(tmpl.get("runner_args_template") or {})


# ---------------------------------------------------------------------------
# Runtime input setup
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_memory_image_target_payload(
    *,
    runtime_input_target: dict[str, Any] | None,
    runtime_input_target_path: Path | None,
) -> dict[str, Any]:
    if runtime_input_target is not None:
        payload = dict(runtime_input_target)
    elif runtime_input_target_path is not None:
        payload = json.loads(runtime_input_target_path.read_text(encoding="utf-8"))
    else:
        raise ValueError("memory_image runtime input requires target descriptor data")
    if not isinstance(payload, dict):
        raise ValueError("memory_image target descriptor payload must be a JSON object")
    if str(payload.get("kind") or "") != "memory-array-preload-v1":
        raise ValueError(
            "memory_image target descriptor kind must be 'memory-array-preload-v1'"
        )
    return payload


def _apply_memory_image_patch_bytes(
    *,
    image_path: Path,
    patch_bytes: list[dict[str, Any]] | None,
) -> None:
    if not patch_bytes:
        return
    payload = bytearray(image_path.read_bytes())
    for patch in patch_bytes:
        if not isinstance(patch, dict):
            raise ValueError("memory_image patch entries must be JSON objects")
        if "offset" not in patch or "value" not in patch:
            raise ValueError("memory_image patches require 'offset' and 'value'")
        offset = int(patch["offset"])
        width_bytes = int(patch.get("width_bytes", 8))
        if offset < 0:
            raise ValueError("memory_image patch offset must be >= 0")
        if width_bytes <= 0:
            raise ValueError("memory_image patch width_bytes must be > 0")
        endianness = str(patch.get("endianness") or "little")
        if endianness not in ("little", "big"):
            raise ValueError("memory_image patch endianness must be 'little' or 'big'")
        signed = bool(patch.get("signed", False))
        value = int(patch["value"])
        encoded = value.to_bytes(width_bytes, byteorder=endianness, signed=signed)
        required_size = offset + width_bytes
        if len(payload) < required_size:
            payload.extend(b"\x00" * (required_size - len(payload)))
        payload[offset:required_size] = encoded
    image_path.write_bytes(bytes(payload))


def _load_readmemh_byte_image(path: Path) -> dict[int, int]:
    memory: dict[int, int] = {}
    current_addr = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        for token in line.split():
            if token.startswith("@"):
                current_addr = int(token[1:], 16)
                continue
            value = int(token, 16)
            if value < 0 or value > 0xFF:
                raise ValueError(f"readmemh byte token out of 8-bit range in {path}: {token}")
            memory[current_addr] = value
            current_addr += 1
    if not memory:
        raise ValueError(f"No readmemh bytes found in {path}")
    return memory


def _apply_patch_bytes_to_byte_memory(
    *,
    memory: dict[int, int],
    patch_bytes: list[dict[str, Any]] | None,
) -> None:
    if not patch_bytes:
        return
    for patch in patch_bytes:
        if not isinstance(patch, dict):
            raise ValueError("memory_image patch entries must be JSON objects")
        if "offset" not in patch or "value" not in patch:
            raise ValueError("memory_image patches require 'offset' and 'value'")
        offset = int(patch["offset"])
        width_bytes = int(patch.get("width_bytes", 8))
        if offset < 0:
            raise ValueError("memory_image patch offset must be >= 0")
        if width_bytes <= 0:
            raise ValueError("memory_image patch width_bytes must be > 0")
        endianness = str(patch.get("endianness") or "little")
        if endianness not in ("little", "big"):
            raise ValueError("memory_image patch endianness must be 'little' or 'big'")
        signed = bool(patch.get("signed", False))
        value = int(patch["value"])
        encoded = value.to_bytes(width_bytes, byteorder=endianness, signed=signed)
        for index, byte_value in enumerate(encoded):
            memory[offset + index] = int(byte_value)


def _materialize_blackparrot_prog_mem(
    *,
    mdir: Path,
    runtime_input_path: Path,
    top_module: str,
    runtime_input_target: dict[str, Any] | None,
    runtime_input_target_path: Path | None,
    runtime_input_patch_bytes: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    source = runtime_input_path.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"BlackParrot prog.mem not found: {source}")

    target_payload = _resolve_memory_image_target_payload(
        runtime_input_target=runtime_input_target,
        runtime_input_target_path=runtime_input_target_path,
    )
    word_bits = int(target_payload.get("word_bits", 0))
    if word_bits <= 0 or (word_bits % 8) != 0:
        raise ValueError(
            f"blackparrot_prog_mem target descriptor requires word_bits multiple of 8: {word_bits}"
        )
    word_bytes = word_bits // 8
    depth = int(target_payload.get("depth", 0))
    if depth <= 1:
        raise ValueError(f"blackparrot_prog_mem target descriptor has invalid depth: {depth}")
    base_addr = int(target_payload.get("base_addr", 0))
    if base_addr != 0:
        raise ValueError(f"unsupported blackparrot_prog_mem base_addr: {base_addr}")
    endianness = str(target_payload.get("endianness") or "little")
    if endianness != "little":
        raise ValueError(
            f"unsupported blackparrot_prog_mem endianness: {endianness!r} (expected 'little')"
        )
    address_unit_bytes = int(target_payload.get("address_unit_bytes", 0))
    if address_unit_bytes != word_bytes:
        raise ValueError(
            "blackparrot_prog_mem descriptor must use address_unit_bytes equal to word size "
            f"({address_unit_bytes} != {word_bytes})"
        )

    memory = _load_readmemh_byte_image(source)
    _apply_patch_bytes_to_byte_memory(
        memory=memory,
        patch_bytes=runtime_input_patch_bytes,
    )
    max_addr = max(memory)
    word_count = (int(max_addr) // word_bytes) + 1
    if word_count > depth - 1:
        raise ValueError(
            "blackparrot_prog_mem image exceeds entry capacity: "
            f"{word_count} > {depth - 1}"
        )

    image_path = (mdir / "blackparrot_prog_mem_entries.bin").resolve()
    payload = bytearray()
    payload.extend(int(word_count).to_bytes(word_bytes, byteorder="little", signed=False))
    for word_index in range(word_count):
        word = 0
        base_byte_addr = word_index * word_bytes
        for byte_index in range(word_bytes):
            word |= (int(memory.get(base_byte_addr + byte_index, 0)) & 0xFF) << (8 * byte_index)
        payload.extend(int(word).to_bytes(word_bytes, byteorder="little", signed=False))
    image_path.write_bytes(bytes(payload))

    descriptor_path = (mdir / f"{top_module}.blackparrot_prog_mem.target.json").resolve()
    _write_json(descriptor_path, target_payload)
    return {
        "memory_image": str(image_path),
        "memory_image_target": str(descriptor_path),
        "memory_image_format": "bin",
    }


def _materialize_memory_image(
    *,
    mdir: Path,
    runtime_input_path: Path,
    top_module: str,
    runtime_input_format: str | None,
    runtime_input_target: dict[str, Any] | None,
    runtime_input_target_path: Path | None,
    runtime_input_patch_bytes: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    source = runtime_input_path.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"runtime memory image not found: {source}")
    image_path = (mdir / source.name).resolve()
    shutil.copyfile(source, image_path)
    _apply_memory_image_patch_bytes(
        image_path=image_path,
        patch_bytes=runtime_input_patch_bytes,
    )
    target_payload = _resolve_memory_image_target_payload(
        runtime_input_target=runtime_input_target,
        runtime_input_target_path=runtime_input_target_path,
    )
    descriptor_path = (mdir / f"{top_module}.memory_image.target.json").resolve()
    _write_json(descriptor_path, target_payload)
    image_format = str(runtime_input_format or "bin")
    if image_format != "bin":
        raise ValueError(f"unsupported memory_image format for enrollment trio: {image_format!r}")
    return {
        "memory_image": str(image_path),
        "memory_image_target": str(descriptor_path),
        "memory_image_format": image_format,
    }


def _materialize_runtime_file(
    *,
    mdir: Path,
    runtime_input_path: Path,
    runtime_input_name: str | None,
    runtime_input_companion_paths: list[Path] | None,
) -> dict[str, Any]:
    source = runtime_input_path.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"runtime file not found: {source}")
    staged_name = str(runtime_input_name or source.name).strip()
    if not staged_name:
        raise ValueError("runtime_file enrollment requires a non-empty runtime_input_name")
    if "/" in staged_name or "\\" in staged_name:
        raise ValueError(
            "runtime_file runtime_input_name must be a plain filename without path separators"
        )
    staged_path = (mdir / staged_name).resolve()
    shutil.copyfile(source, staged_path)
    companion_names: list[str] = []
    companion_files: list[str] = []
    for companion_path in runtime_input_companion_paths or []:
        companion_source = companion_path.resolve()
        if not companion_source.is_file():
            raise FileNotFoundError(f"runtime companion file not found: {companion_source}")
        companion_name = companion_source.name
        companion_dest = (mdir / companion_name).resolve()
        shutil.copyfile(companion_source, companion_dest)
        companion_names.append(companion_name)
        companion_files.append(str(companion_dest))
    payload = {
        "runtime_file": str(staged_path),
        "runtime_file_name": staged_name,
    }
    if companion_files:
        payload["runtime_file_companion_names"] = companion_names
        payload["runtime_file_companion_files"] = companion_files
    return payload

def ensure_runtime_input(
    *,
    mdir: Path,
    runtime_input_type: str,
    runtime_input_path: Path,
    top_module: str,
    runtime_input_format: str | None = None,
    runtime_input_target: dict[str, Any] | None = None,
    runtime_input_target_path: Path | None = None,
    runtime_input_name: str | None = None,
    runtime_input_patch_bytes: list[dict[str, Any]] | None = None,
    runtime_input_companion_paths: list[Path] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """
    Prepare runtime input for the given design.

    Returns:
        runtime_inputs: dict with paths to materialized input files
        extra_defines:  list of -D flags for the host probe build
    """
    if runtime_input_type == "program_hex":
        from veer_runtime_inputs import ensure_runtime_program_entries, veer_program_entries_probe_defines
        runtime_inputs = ensure_runtime_program_entries(mdir=mdir, program_hex=runtime_input_path)
        extra_defines = veer_program_entries_probe_defines(top_module)
        return runtime_inputs, extra_defines

    if runtime_input_type == "memory_image":
        return (
            _materialize_memory_image(
                mdir=mdir,
                runtime_input_path=runtime_input_path,
                top_module=top_module,
                runtime_input_format=runtime_input_format,
                runtime_input_target=runtime_input_target,
                runtime_input_target_path=runtime_input_target_path,
                runtime_input_patch_bytes=runtime_input_patch_bytes,
            ),
            [],
        )

    if runtime_input_type == "blackparrot_prog_mem":
        return (
            _materialize_blackparrot_prog_mem(
                mdir=mdir,
                runtime_input_path=runtime_input_path,
                top_module=top_module,
                runtime_input_target=runtime_input_target,
                runtime_input_target_path=runtime_input_target_path,
                runtime_input_patch_bytes=runtime_input_patch_bytes,
            ),
            [],
        )

    if runtime_input_type == "runtime_file":
        return (
            _materialize_runtime_file(
                mdir=mdir,
                runtime_input_path=runtime_input_path,
                runtime_input_name=runtime_input_name,
                runtime_input_companion_paths=runtime_input_companion_paths,
            ),
            [],
        )

    # case_pat: symlink into mdir
    source = runtime_input_path.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"runtime case.pat not found: {source}")
    dest = mdir / "case.pat"
    if dest.is_symlink():
        if dest.resolve() != source:
            dest.unlink()
            dest.symlink_to(source)
    elif dest.exists():
        dest.unlink()
        dest.symlink_to(source)
    else:
        dest.symlink_to(source)
    return {"case_pat": source}, []


# ---------------------------------------------------------------------------
# Hybrid validation
# ---------------------------------------------------------------------------

def run_hybrid_validation(
    *,
    slug: str,
    mdir: Path,
    template_path: Path,
    runtime_inputs: dict[str, Any],
    extra_defines: list[str],
    runtime_input_type: str,
    nstates: int,
    steps: int,
    block_size: int,
    host_reset_cycles: int,
    host_post_reset_cycles: int,
    support_tier: str,
    campaign_threshold_bits: int,
    json_out: Path,
) -> dict[str, Any]:
    """Run stock-Verilator hybrid validation for a generic design."""
    flow_json_out = mdir / f"{slug}_host_gpu_flow_summary.json"
    host_report_out = mdir / f"{slug}_host_probe_report.json"
    host_state_out = mdir / f"{slug}_host_init_state.bin"
    final_state_out = mdir / f"{slug}_gpu_final_state.bin"

    flow_cmd: list[str] = [
        sys.executable, str(FLOW_TOOL),
        "--mdir", str(mdir),
        "--template", str(template_path),
        "--target", slug,
        "--support-tier", support_tier,
        "--nstates", str(nstates),
        "--steps", str(steps),
        "--block-size", str(block_size),
        "--host-reset-cycles", str(host_reset_cycles),
        "--host-post-reset-cycles", str(host_post_reset_cycles),
        "--json-out", str(flow_json_out),
        "--host-report-out", str(host_report_out),
        "--host-state-out", str(host_state_out),
        "--final-state-out", str(final_state_out),
        "--sanitize-host-only-internals",
    ]
    if runtime_input_type == "program_hex":
        flow_cmd.extend(["--program-entries-bin", str(runtime_inputs["program_entries_bin"])])
        for d in extra_defines:
            flow_cmd.append(f"--host-probe-extra-define={d}")
    elif runtime_input_type in ("memory_image", "blackparrot_prog_mem"):
        flow_cmd.extend(["--memory-image", str(runtime_inputs["memory_image"])])
        flow_cmd.extend(["--memory-image-target", str(runtime_inputs["memory_image_target"])])

    proc = subprocess.run(flow_cmd, text=True, capture_output=True, check=False)
    flow_json = read_json_if_exists(flow_json_out)
    host_report = read_json_if_exists(host_report_out)

    metrics = parse_gpu_metrics(proc.stdout)
    flow_timing = dict((flow_json or {}).get("campaign_timing") or {})
    wall_time_ms = flow_timing.get("wall_time_ms") or metrics.get("wall_time_ms")

    outputs = {n: int(dict((flow_json or {}).get("outputs") or {}).get(n, 0)) for n in STANDARD_OUTPUT_NAMES}
    host_outputs = {n: int((host_report or {}).get(n, 0)) for n in STANDARD_OUTPUT_NAMES}
    toggle_words = [outputs[f"toggle_bitmap_word{i}_o"] for i in range(3)]
    toggle_summary = toggle_coverage_summary(toggle_words)

    status = "ok" if proc.returncode == 0 and flow_json is not None and host_report is not None else "error"
    gate_checks = {
        "outputs_match_host_probe": outputs == host_outputs,
        "rsp_queue_overflow_o": outputs["rsp_queue_overflow_o"] == 0,
        "toggle_coverage_any_hit": bool(toggle_summary["any_hit"]),
    }
    reference_gate: dict[str, Any] = {
        "name": REFERENCE_GATE_NAME,
        "target_support_tier": support_tier,
        "passed": all(gate_checks.values()),
        "blocked_by": [n for n, p in gate_checks.items() if not p],
        "criteria": {"outputs_match_host_probe": True, "rsp_queue_overflow_o": 0, "toggle_coverage_any_hit": True},
        "observed": {
            "toggle_bits_hit": int(toggle_summary["bits_hit"]),
            "host_outputs": host_outputs,
            "gpu_outputs": outputs,
        },
    }
    campaign_threshold = campaign_threshold_toggle_bits_hit(campaign_threshold_bits)
    gpu_runs = list((flow_json or {}).get("gpu_runs") or [])
    steps_executed = sum(int(r.get("steps", 0)) for r in gpu_runs) or steps

    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "target": slug,
        "backend": "stock_verilator_hybrid",
        "support_tier": support_tier,
        "clock_ownership": str((flow_json or {}).get("clock_ownership") or "tb_timed_coroutine"),
        "acceptance_gate": REFERENCE_GATE_NAME,
        "reference_gate": reference_gate,
        "outputs": outputs,
        "toggle_coverage": toggle_summary,
        "campaign_threshold": campaign_threshold,
        "campaign_measurement": {
            "bits_hit": int(toggle_summary["bits_hit"]),
            "threshold_satisfied": (
                status == "ok"
                and bool(reference_gate["passed"])
                and int(toggle_summary["bits_hit"]) >= campaign_threshold["value"]
            ),
            "wall_time_ms": float(wall_time_ms) if isinstance(wall_time_ms, (int, float)) else None,
            "steps_executed": steps_executed,
        },
        "performance": metrics,
        "caveats": [
            "enrollment trio v1: generic runner via enrollment_common",
            "campaign_measurement.wall_time_ms taken from flow campaign_timing when available",
        ],
    }
    if proc.returncode != 0:
        payload["stdout_tail"] = "\n".join(proc.stdout.splitlines()[-40:])
        payload["stderr_tail"] = "\n".join(proc.stderr.splitlines()[-40:])
    write_json(json_out, payload)
    return payload


# ---------------------------------------------------------------------------
# CPU baseline validation
# ---------------------------------------------------------------------------

def run_cpu_baseline_validation(
    *,
    slug: str,
    mdir: Path,
    template_path: Path,
    runtime_inputs: dict[str, Any],
    extra_defines: list[str],
    runtime_input_type: str,
    host_reset_cycles: int,
    host_post_reset_cycles: int,
    support_tier: str,
    campaign_threshold_bits: int,
    json_out: Path,
) -> dict[str, Any]:
    """Run stock-Verilator CPU baseline validation for a generic design."""
    binary_out = mdir / f"{slug}_cpu_baseline_probe"
    host_report_out = mdir / f"{slug}_cpu_baseline_host_report.json"

    build_cmd: list[str] = [
        sys.executable, str(HOST_PROBE_TOOL),
        "--mdir", str(mdir),
        "--template", str(template_path),
        "--binary-out", str(binary_out),
        "--build-only",
    ]
    for d in extra_defines:
        build_cmd.append(f"--extra-define={d}")
    if runtime_input_type in ("memory_image", "blackparrot_prog_mem"):
        build_cmd.extend(["--memory-image-target", str(runtime_inputs["memory_image_target"])])
    build_proc = subprocess.run(build_cmd, text=True, capture_output=True, check=False)

    flow_proc = subprocess.CompletedProcess(args=[str(binary_out)], returncode=1, stdout="", stderr="")
    elapsed_ms = 0.0
    host_report: dict[str, Any] | None = None
    flow_cmd: list[str] = []

    if build_proc.returncode == 0:
        flow_cmd = [
            str(binary_out),
            "--reset-cycles", str(host_reset_cycles),
            "--post-reset-cycles", str(host_post_reset_cycles),
        ]
        if runtime_input_type == "program_hex":
            flow_cmd.extend(["--program-entries-bin", str(runtime_inputs["program_entries_bin"])])
        elif runtime_input_type in ("memory_image", "blackparrot_prog_mem"):
            flow_cmd.extend(["--memory-image", str(runtime_inputs["memory_image"])])
        t0 = time.perf_counter()
        flow_proc = subprocess.run(flow_cmd, text=True, capture_output=True, check=False, cwd=binary_out.parent)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        raw = flow_proc.stdout
        start = raw.find("{")
        if start >= 0:
            try:
                host_report = json.loads(raw[start:])
                host_report_out.parent.mkdir(parents=True, exist_ok=True)
                host_report_out.write_text(json.dumps(host_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            except json.JSONDecodeError:
                pass

    status = "ok" if build_proc.returncode == 0 and flow_proc.returncode == 0 and host_report is not None else "error"
    toggle_words = [int((host_report or {}).get(f"toggle_bitmap_word{i}_o", 0)) for i in range(3)]
    coverage = toggle_coverage_summary(toggle_words)
    campaign_threshold = campaign_threshold_toggle_bits_hit(campaign_threshold_bits)
    steps_executed = int((host_report or {}).get("drained_events", host_reset_cycles + host_post_reset_cycles))

    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "target": slug,
        "backend": "stock_verilator_cpu_baseline",
        "support_tier": support_tier,
        "clock_ownership": str((host_report or {}).get("clock_ownership") or "tb_timed_coroutine"),
        "campaign_threshold": campaign_threshold,
        "campaign_measurement": {
            "bits_hit": int(coverage["bits_hit"]),
            "threshold_satisfied": status == "ok" and int(coverage["bits_hit"]) >= campaign_threshold["value"],
            "wall_time_ms": elapsed_ms if status == "ok" else None,
            "steps_executed": steps_executed,
        },
        "coverage": coverage,
        "caveats": [
            "enrollment trio v1: generic CPU baseline runner via enrollment_common",
            "wall_time_ms covers probe binary execution only; compile time excluded",
        ],
    }
    if build_proc.returncode != 0:
        payload["build_stdout_tail"] = "\n".join(build_proc.stdout.splitlines()[-40:])
        payload["build_stderr_tail"] = "\n".join(build_proc.stderr.splitlines()[-40:])
    if flow_proc.returncode != 0:
        payload["stdout_tail"] = "\n".join(flow_proc.stdout.splitlines()[-40:])
        payload["stderr_tail"] = "\n".join(flow_proc.stderr.splitlines()[-40:])
    write_json(json_out, payload)
    return payload


# ---------------------------------------------------------------------------
# Threshold probe (analytical — no re-run required)
# ---------------------------------------------------------------------------

def probe_best_threshold(
    *,
    slug: str,
    hybrid_payload: dict[str, Any],
    baseline_payload: dict[str, Any],
    json_out: Path,
) -> dict[str, Any]:
    """
    Analytically determine the highest threshold at which both sides satisfy,
    without re-running simulations.

    Both sides already have observed bits_hit and wall_time_ms. The probe finds
    max_threshold = min(hybrid_bits_hit, baseline_bits_hit) and declares a winner
    based on wall time.
    """
    hm = hybrid_payload.get("campaign_measurement", {})
    bm = baseline_payload.get("campaign_measurement", {})
    h_bits = int(hm.get("bits_hit", 0))
    b_bits = int(bm.get("bits_hit", 0))
    h_time = hm.get("wall_time_ms")
    b_time = bm.get("wall_time_ms")

    if h_bits == 0 or b_bits == 0:
        result: dict[str, Any] = {
            "status": "unresolvable_zero_coverage",
            "target": slug,
            "hybrid_bits_hit": h_bits,
            "baseline_bits_hit": b_bits,
            "note": "at least one side has zero coverage; no candidate threshold exists",
        }
    elif not isinstance(h_time, (int, float)) or not isinstance(b_time, (int, float)):
        result = {
            "status": "unresolvable_missing_wall_time",
            "target": slug,
            "hybrid_bits_hit": h_bits,
            "baseline_bits_hit": b_bits,
            "note": "wall_time_ms missing from one or both sides",
        }
    else:
        max_threshold = min(h_bits, b_bits)
        h_t = float(h_time)
        b_t = float(b_time)
        winner = "hybrid" if h_t < b_t else ("baseline" if h_t > b_t else "tie")
        speedup = b_t / h_t if winner == "hybrid" else (h_t / b_t if winner == "baseline" else 1.0)
        result = {
            "status": "candidate_threshold_found",
            "target": slug,
            "candidate_threshold": max_threshold,
            "winner": winner,
            "speedup_ratio": round(speedup, 4),
            "hybrid_bits_hit": h_bits,
            "baseline_bits_hit": b_bits,
            "hybrid_wall_time_ms": h_t,
            "baseline_wall_time_ms": b_t,
            "note": (
                f"candidate-only: both sides observe bits_hit >= {max_threshold}; "
                "this is not a default gate result and requires explicit policy acceptance"
            ),
        }
    write_json(json_out, result)
    return result
