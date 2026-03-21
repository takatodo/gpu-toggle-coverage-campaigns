#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
SUPPORT_DIR = ROOT_DIR / "opentitan_support"
DEFAULT_SCOPE_JSON = SUPPORT_DIR / "opentitan_tlul_search_scope_estimate.json"
DEFAULT_GRAPH_JSON = SUPPORT_DIR / "opentitan_tlul_search_scope_graph.json"

_SLICE_SUBSYSTEM = {
    "tlul_err": "checker",
    "tlul_sink": "checker",
    "tlul_fifo_sync": "transport",
    "tlul_fifo_async": "transport",
    "tlul_request_loopback": "transport",
    "tlul_socket_1n": "sockets",
    "tlul_socket_m1": "sockets",
    "xbar_main": "fabric",
    "xbar_peri": "fabric",
}

_QUEUE_PRIORITY = {
    "wide_live_transport_scope": 90,
    "medium_partial_scope": 75,
    "narrow_hard_scope": 60,
    "control_plateau_scope": 35,
    "benchmark_only_scope": 25,
    "structural_only_scope": 20,
    "contract_debug_scope": 15,
    "widening_scope": 10,
}

_SEARCH_HOLD_SCOPES = {
    "contract_debug_scope",
    "widening_scope",
}

_REGION_BUDGET_SCALE = {
    "wide_live_transport_scope": 2.0,
    "medium_partial_scope": 1.5,
    "narrow_hard_scope": 1.0,
    "control_plateau_scope": 1.0,
    "benchmark_only_scope": 1.0,
    "structural_only_scope": 1.0,
    "contract_debug_scope": 1.0,
    "widening_scope": 1.0,
}

_PROBE_CASE_CAP = {
    "sweep": 64,
    "campaign": 128,
}
_PROBE_TOPK_CAP = 8


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    return float(value)


def _scale_positive_int(value: int, scale: float) -> int:
    return max(1, int(math.ceil(int(value) * float(scale))))


def _normalize_region_budget(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, int] = {}
    for region, quota in raw.items():
        region_name = str(region or "").strip()
        if not region_name:
            continue
        quota_int = int(quota or 0)
        if quota_int <= 0:
            continue
        normalized[region_name] = quota_int
    return normalized


def _row_by_name(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("slice_name") or row.get("node_name")): dict(row) for row in list(payload.get("rows") or [])}


def _resolve_cases_key(search_defaults: dict[str, Any], phase: str) -> str | None:
    for key in (
        "pilot_campaign_candidate_count" if str(phase) == "campaign" else "pilot_sweep_cases",
        "cases",
    ):
        if key in search_defaults:
            return key
    return None


def _scale_region_budget(
    region_budget: dict[str, int],
    *,
    scope_name: str,
) -> dict[str, int]:
    normalized = _normalize_region_budget(region_budget)
    if not normalized:
        return {}
    scale = float(_REGION_BUDGET_SCALE.get(scope_name, 1.0))
    if scale == 1.0:
        return normalized
    return {
        region: max(1, int(math.ceil(int(quota) * scale)))
        for region, quota in sorted(normalized.items())
    }


def _queue_priority(
    *,
    scope_name: str,
    subsystem_row: dict[str, Any] | None,
    root_row: dict[str, Any] | None,
) -> int:
    priority = int(_QUEUE_PRIORITY.get(scope_name, 0))
    subsystem_frontier = str((subsystem_row or {}).get("frontier_scope_estimate") or "")
    subsystem_risk = str((subsystem_row or {}).get("dominant_risk_scope_estimate") or "")
    root_frontier = str((root_row or {}).get("frontier_scope_estimate") or "")
    root_risk = str((root_row or {}).get("dominant_risk_scope_estimate") or "")
    if subsystem_frontier == "wide_live_transport_scope":
        priority += 5
    elif subsystem_frontier == "medium_partial_scope":
        priority += 3
    if subsystem_risk in {"contract_debug_scope", "widening_scope"}:
        priority -= 10
    elif subsystem_risk == "control_plateau_scope":
        priority -= 5
    if root_frontier == "wide_live_transport_scope":
        priority += 2
    if root_risk in {"contract_debug_scope", "widening_scope"}:
        priority -= 2
    return max(0, min(100, priority))


def apply_search_scope_runtime_policy(
    *,
    slice_name: str,
    search_defaults: dict[str, Any],
    phase: str,
    region_budget: dict[str, int] | None = None,
    policy_mode: str = "auto",
    scope_json: str | Path = DEFAULT_SCOPE_JSON,
    graph_json: str | Path = DEFAULT_GRAPH_JSON,
    scope_payload: dict[str, Any] | None = None,
    graph_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    adjusted_defaults = dict(search_defaults or {})
    adjusted_region_budget = _normalize_region_budget(region_budget)
    normalized_mode = str(policy_mode or "auto").strip() or "auto"
    if normalized_mode == "off":
        return {
            "policy": {
                "enabled": False,
                "policy_mode": normalized_mode,
                "reason": "policy_disabled",
            },
            "adjusted_search_defaults": adjusted_defaults,
            "adjusted_region_budget": adjusted_region_budget,
        }

    try:
        effective_scope_payload = scope_payload or _load_json(Path(scope_json).expanduser().resolve())
        effective_graph_payload = graph_payload or _load_json(Path(graph_json).expanduser().resolve())
    except FileNotFoundError:
        return {
            "policy": {
                "enabled": False,
                "policy_mode": normalized_mode,
                "reason": "scope_artifact_missing",
            },
            "adjusted_search_defaults": adjusted_defaults,
            "adjusted_region_budget": adjusted_region_budget,
        }

    scope_rows = _row_by_name(effective_scope_payload)
    graph_rows = _row_by_name(effective_graph_payload)
    scope_row = dict(scope_rows.get(str(slice_name)) or {})
    if not scope_row:
        return {
            "policy": {
                "enabled": False,
                "policy_mode": normalized_mode,
                "reason": "slice_scope_missing",
                "slice_name": str(slice_name),
            },
            "adjusted_search_defaults": adjusted_defaults,
            "adjusted_region_budget": adjusted_region_budget,
        }

    scope_name = str(scope_row.get("search_scope_estimate") or "")
    subsystem_name = _SLICE_SUBSYSTEM.get(str(slice_name))
    subsystem_row = dict(graph_rows.get(str(subsystem_name)) or {})
    root_row = dict(graph_rows.get("tlul") or {})
    cases_key = _resolve_cases_key(adjusted_defaults, str(phase))
    changed: dict[str, dict[str, Any]] = {}

    if cases_key and adjusted_defaults.get(cases_key) is not None:
        original = int(adjusted_defaults[cases_key])
        if scope_name in _SEARCH_HOLD_SCOPES:
            updated = min(original, int(_PROBE_CASE_CAP.get(str(phase), 64)))
        else:
            updated = _scale_positive_int(
                original,
                _safe_float(scope_row.get("recommended_scope_cases_scale"), 1.0),
            )
        if updated != original:
            adjusted_defaults[cases_key] = updated
            changed[cases_key] = {"before": original, "after": updated}

    if adjusted_defaults.get("keep_top_k") is not None:
        original_topk = int(adjusted_defaults["keep_top_k"])
        if scope_name in _SEARCH_HOLD_SCOPES:
            updated_topk = min(original_topk, _PROBE_TOPK_CAP)
        else:
            updated_topk = _scale_positive_int(
                original_topk,
                _safe_float(scope_row.get("recommended_scope_keep_top_k_scale"), 1.0),
            )
        if updated_topk != original_topk:
            adjusted_defaults["keep_top_k"] = updated_topk
            changed["keep_top_k"] = {"before": original_topk, "after": updated_topk}

    scaled_region_budget = _scale_region_budget(
        adjusted_region_budget,
        scope_name=scope_name,
    )
    if scaled_region_budget != adjusted_region_budget:
        changed["region_budget"] = {
            "before": adjusted_region_budget,
            "after": scaled_region_budget,
        }
        adjusted_region_budget = scaled_region_budget

    queue_priority = _queue_priority(
        scope_name=scope_name,
        subsystem_row=subsystem_row,
        root_row=root_row,
    )
    policy = {
        "enabled": True,
        "policy_mode": normalized_mode,
        "slice_name": str(slice_name),
        "phase": str(phase),
        "scope_json": str(Path(scope_json).expanduser().resolve()),
        "graph_json": str(Path(graph_json).expanduser().resolve()),
        "search_scope_estimate": scope_name,
        "recommended_front_action": str(scope_row.get("recommended_front_action") or ""),
        "subsystem_name": subsystem_name,
        "subsystem_primary_scope_estimate": str(subsystem_row.get("primary_scope_estimate") or ""),
        "subsystem_frontier_scope_estimate": str(subsystem_row.get("frontier_scope_estimate") or ""),
        "subsystem_dominant_risk_scope_estimate": str(subsystem_row.get("dominant_risk_scope_estimate") or ""),
        "root_frontier_scope_estimate": str(root_row.get("frontier_scope_estimate") or ""),
        "root_dominant_risk_scope_estimate": str(root_row.get("dominant_risk_scope_estimate") or ""),
        "queue_priority": int(queue_priority),
        "search_hold_recommended": bool(scope_name in _SEARCH_HOLD_SCOPES),
        "cases_scale": _safe_float(scope_row.get("recommended_scope_cases_scale"), 1.0),
        "keep_top_k_scale": _safe_float(scope_row.get("recommended_scope_keep_top_k_scale"), 1.0),
        "region_budget_scale": float(_REGION_BUDGET_SCALE.get(scope_name, 1.0)),
        "changed": changed,
    }
    return {
        "policy": policy,
        "adjusted_search_defaults": adjusted_defaults,
        "adjusted_region_budget": adjusted_region_budget,
    }
