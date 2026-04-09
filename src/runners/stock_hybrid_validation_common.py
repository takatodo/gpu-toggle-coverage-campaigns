from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_OK_RE = re.compile(
    r"^ok: steps=(?P<steps>\d+) kernels_per_step=(?P<kernels>\d+) "
    r"patches_per_step=(?P<patches>\d+) grid=(?P<grid>\d+) block=(?P<block>\d+) "
    r"nstates=(?P<nstates>\d+) storage=(?P<storage>\d+) B$"
)
_GPU_MS_RE = re.compile(
    r"^gpu_kernel_time_ms: total=(?P<total>[0-9.]+)\s+per_launch=(?P<per_launch>[0-9.]+)"
)
_GPU_US_RE = re.compile(r"^gpu_kernel_time: per_state=(?P<per_state_us>[0-9.]+) us")
_WALL_MS_RE = re.compile(r"^wall_time_ms: (?P<wall_ms>[0-9.]+)")
_DEVICE_RE = re.compile(r"^device \d+: (?P<device>.+)$")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json_if_exists(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def parse_gpu_metrics(stdout: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _DEVICE_RE.match(line)
        if match:
            metrics["device_name"] = match.group("device")
            continue
        match = _OK_RE.match(line)
        if match:
            metrics["runner_shape"] = {
                "steps": int(match.group("steps")),
                "kernels_per_step": int(match.group("kernels")),
                "patches_per_step": int(match.group("patches")),
                "grid": int(match.group("grid")),
                "block": int(match.group("block")),
                "nstates": int(match.group("nstates")),
                "storage_size": int(match.group("storage")),
            }
            continue
        match = _GPU_MS_RE.match(line)
        if match:
            metrics["gpu_kernel_time_ms"] = {
                "total": float(match.group("total")),
                "per_launch": float(match.group("per_launch")),
            }
            continue
        match = _GPU_US_RE.match(line)
        if match:
            metrics["gpu_kernel_time_per_state_us"] = float(match.group("per_state_us"))
            continue
        match = _WALL_MS_RE.match(line)
        if match:
            metrics["wall_time_ms"] = float(match.group("wall_ms"))
    shape = metrics.get("runner_shape")
    gpu_ms = metrics.get("gpu_kernel_time_ms")
    if isinstance(shape, dict) and isinstance(gpu_ms, dict):
        total_ms = gpu_ms.get("total")
        nstates = shape.get("nstates")
        steps = shape.get("steps")
        kernels_per_step = shape.get("kernels_per_step")
        if isinstance(total_ms, float) and total_ms > 0.0 and isinstance(nstates, int) and isinstance(steps, int):
            metrics["throughput"] = {
                "state_steps_per_second": (nstates * steps * 1000.0) / total_ms,
            }
            if isinstance(kernels_per_step, int):
                metrics["throughput"]["kernel_launches"] = steps * kernels_per_step
    return metrics


def toggle_coverage_summary(toggle_words: list[int]) -> dict[str, Any]:
    bits_hit = sum(word.bit_count() for word in toggle_words)
    return {
        "artifact_type": "toggle_bitmap_words",
        "words_nonzero": sum(1 for word in toggle_words if word != 0),
        "bits_hit": bits_hit,
        "any_hit": bits_hit > 0,
    }


def campaign_threshold_toggle_bits_hit(value: int) -> dict[str, Any]:
    if value <= 0:
        raise ValueError("campaign threshold bits must be > 0")
    return {
        "kind": "toggle_bits_hit",
        "value": int(value),
        "aggregation": "bitwise_or_across_trials",
    }


def campaign_threshold_toggle_bits_hit_v1() -> dict[str, Any]:
    return campaign_threshold_toggle_bits_hit(3)
