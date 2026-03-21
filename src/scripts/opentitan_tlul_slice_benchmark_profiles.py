#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_FREEZE_JSON = SCRIPT_DIR / "opentitan_tlul_slice_benchmark_freeze.json"
PROFILE_KEYS = ("nstates", "gpu_reps", "cpu_reps", "sequential_steps")


def load_benchmark_freeze(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    freeze_path = Path(path).expanduser().resolve()
    if not freeze_path.exists():
        return {}
    return json.loads(freeze_path.read_text(encoding="utf-8"))


def _slice_entry(freeze_payload: dict[str, Any], slice_name: str) -> dict[str, Any]:
    for entry in list(freeze_payload.get("slices") or []):
        if str(entry.get("slice_name")) == slice_name:
            return dict(entry)
    return {}


def _scenario_name_for_phase(phase: str, profile_scenario: str) -> str:
    if profile_scenario and profile_scenario != "auto":
        return profile_scenario
    if phase == "single_step":
        return "single_step_small"
    return "multi_step_medium"


def resolve_slice_profile(
    freeze_payload: dict[str, Any],
    *,
    slice_name: str,
    phase: str,
    profile_scenario: str = "auto",
) -> dict[str, Any]:
    slice_entry = _slice_entry(freeze_payload, slice_name)
    if not slice_entry:
        return {}
    scenario_name = _scenario_name_for_phase(phase, profile_scenario)
    scenario = dict((slice_entry.get("scenarios") or {}).get(scenario_name) or {})
    if scenario.get("status") != "frozen":
        return {}
    profile = {
        key: int(scenario[key])
        for key in PROFILE_KEYS
        if isinstance(scenario.get(key), (int, float))
    }
    if not profile:
        return {}
    profile["scenario"] = scenario_name
    return profile
