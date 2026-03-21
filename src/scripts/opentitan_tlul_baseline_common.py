#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def estimate_sync_sequential_steps(
    driver: dict[str, Any],
    *,
    transaction_trace: dict[str, Any] | None = None,
) -> int:
    effective_batch = max(1, int(driver.get("batch_length", 1)))
    burst_factor = max(1, int(driver.get("req_burst_len_max", 0)) + 1)
    rsp_delay = max(0, int(driver.get("rsp_delay_max", 0)))
    drain_cycles = max(8, int(driver.get("drain_cycles", 0)))
    reset_cycles = max(0, int(driver.get("reset_cycles", 0)))
    trace_steps = 0
    trace_payload = transaction_trace
    if trace_payload is None and isinstance(driver.get("_transaction_trace"), dict):
        trace_payload = driver.get("_transaction_trace")
    if isinstance(trace_payload, dict):
        steps = trace_payload.get("steps", [])
        if isinstance(steps, list):
            trace_steps = len(steps)
        else:
            trace_steps = max(0, int(driver.get("_transaction_trace_step_count", 0)))
    elif driver.get("_transaction_trace_step_count") is not None:
        trace_steps = max(0, int(driver.get("_transaction_trace_step_count", 0)))
    request_span = max(effective_batch * burst_factor, trace_steps)
    response_span = max(effective_batch, trace_steps) * max(1, rsp_delay // 2 + 1)
    total_cycles = (
        reset_cycles
        + 2
        + request_span
        + drain_cycles
        + response_span
        + 16
    )
    return 2 * total_cycles


def load_batch_overrides(raw_path: str) -> dict[str, Any]:
    if not raw_path:
        return {}
    path = Path(raw_path).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Missing batch config: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Batch config must be a JSON object: {path}")
    driver = payload.get("driver", payload)
    if not isinstance(driver, dict):
        raise SystemExit(f"Batch config 'driver' must be a JSON object: {path}")
    driver = dict(driver)
    driver["_batch_json_path"] = str(path)
    trace_payload = payload.get("transaction_trace")
    if trace_payload is not None:
        if not isinstance(trace_payload, dict):
            raise SystemExit(f"Batch config 'transaction_trace' must be a JSON object: {path}")
        steps = trace_payload.get("steps", [])
        if not isinstance(steps, list):
            raise SystemExit(f"Batch config 'transaction_trace.steps' must be a JSON array: {path}")
        trace_summary = trace_payload.get("summary", {})
        if trace_summary is not None and not isinstance(trace_summary, dict):
            raise SystemExit(f"Batch config 'transaction_trace.summary' must be a JSON object: {path}")
        driver["_transaction_trace"] = trace_payload
        driver["_transaction_trace_step_count"] = len(steps)
        driver["_transaction_trace_summary"] = dict(trace_summary or {})
    return driver


def apply_driver_overrides(ns: Any, defaults: dict[str, Any], overrides: dict[str, Any]) -> None:
    if not overrides:
        return
    for key, default in defaults.items():
        if key not in overrides:
            continue
        if getattr(ns, key) == default:
            setattr(ns, key, overrides[key])


def load_batch_case_manifest(raw_path: str) -> list[dict[str, Any]]:
    if not raw_path:
        return []
    path = Path(raw_path).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Missing batch case manifest: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        cases = payload.get("cases", [])
    elif isinstance(payload, list):
        cases = payload
    else:
        raise SystemExit(f"Batch case manifest must be a JSON object or array: {path}")
    if not isinstance(cases, list):
        raise SystemExit(f"Batch case manifest 'cases' must be a JSON array: {path}")

    resolved_cases: list[dict[str, Any]] = []
    for entry_index, entry in enumerate(cases):
        if isinstance(entry, str):
            entry = {"batch_json": entry}
        if not isinstance(entry, dict):
            raise SystemExit(
                f"Batch case manifest entry must be a JSON object or path string: "
                f"{path} entry {entry_index}"
            )
        batch_json_raw = entry.get("batch_json")
        batch_json = str(batch_json_raw).strip() if isinstance(batch_json_raw, str) else ""
        inline_driver = entry.get("driver")
        trace_payload = entry.get("transaction_trace")
        if inline_driver is None and not batch_json:
            raise SystemExit(
                f"Batch case manifest entry must include non-empty 'batch_json' or 'driver': "
                f"{path} entry {entry_index}"
            )

        overrides: dict[str, Any]
        if inline_driver is not None:
            if not isinstance(inline_driver, dict):
                raise SystemExit(
                    f"Batch case manifest entry 'driver' must be a JSON object: "
                    f"{path} entry {entry_index}"
                )
            overrides = dict(inline_driver)
        else:
            overrides = load_batch_overrides(batch_json)

        if trace_payload is not None:
            if not isinstance(trace_payload, dict):
                raise SystemExit(
                    f"Batch case manifest entry 'transaction_trace' must be a JSON object: "
                    f"{path} entry {entry_index}"
                )
            steps = trace_payload.get("steps", [])
            if not isinstance(steps, list):
                raise SystemExit(
                    f"Batch case manifest entry 'transaction_trace.steps' must be a JSON array: "
                    f"{path} entry {entry_index}"
                )
            trace_summary = trace_payload.get("summary", {})
            if trace_summary is not None and not isinstance(trace_summary, dict):
                raise SystemExit(
                    f"Batch case manifest entry 'transaction_trace.summary' must be a JSON object: "
                    f"{path} entry {entry_index}"
                )
            overrides["_transaction_trace"] = trace_payload
            overrides["_transaction_trace_step_count"] = len(steps)
            overrides["_transaction_trace_summary"] = dict(trace_summary or {})

        resolved_entry = {
            "batch_json": (
                str(Path(batch_json).expanduser().resolve())
                if batch_json
                else ""
            ),
            "driver": {
                key: value
                for key, value in overrides.items()
                if not str(key).startswith("_")
            },
            "states_per_case": max(1, int(entry.get("states_per_case", 1))),
            "transaction_trace": overrides.get("_transaction_trace"),
            "transaction_trace_step_count": overrides.get("_transaction_trace_step_count"),
            "transaction_trace_summary": overrides.get("_transaction_trace_summary"),
        }
        for key, value in entry.items():
            if key not in {"batch_json", "driver", "transaction_trace"}:
                resolved_entry[key] = value
        resolved_cases.append(resolved_entry)
    return resolved_cases
