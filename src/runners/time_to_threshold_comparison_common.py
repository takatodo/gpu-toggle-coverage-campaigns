from __future__ import annotations

from pathlib import Path
from typing import Any

from stock_hybrid_validation_common import read_json_if_exists, write_json


def side_payload(path: Path, payload: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "runner_json": str(path.resolve()),
        "status": payload.get("status") if payload else None,
        "backend": payload.get("backend") if payload else None,
        "campaign_threshold": payload.get("campaign_threshold") if payload else None,
        "campaign_measurement": payload.get("campaign_measurement") if payload else None,
    }


def build_reject_payload(
    *,
    baseline_path: Path,
    hybrid_path: Path,
    baseline_payload: dict[str, Any] | None,
    hybrid_payload: dict[str, Any] | None,
    reject_reason: str,
    caveat: str,
) -> dict[str, Any]:
    target = None
    if (
        baseline_payload is not None
        and hybrid_payload is not None
        and baseline_payload.get("target") == hybrid_payload.get("target")
    ):
        target = baseline_payload.get("target")
    elif baseline_payload:
        target = baseline_payload.get("target")
    elif hybrid_payload:
        target = hybrid_payload.get("target")
    return {
        "schema_version": 1,
        "status": "error",
        "target": target,
        "campaign_threshold": None,
        "baseline": side_payload(baseline_path, baseline_payload),
        "hybrid": side_payload(hybrid_path, hybrid_payload),
        "comparison_ready": False,
        "speedup_ratio": None,
        "winner": "rejected",
        "reject_reason": reject_reason,
        "caveats": [caveat],
    }


def validate_artifact(
    name: str,
    payload: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    if payload is None:
        return False, f"missing_{name}_artifact"
    if payload.get("status") != "ok":
        return False, f"{name}_status_not_ok"
    if not isinstance(payload.get("campaign_threshold"), dict):
        return False, f"missing_{name}_campaign_threshold"
    if not isinstance(payload.get("campaign_measurement"), dict):
        return False, f"missing_{name}_campaign_measurement"
    return True, None


def threshold_mismatch_reason(
    baseline_threshold: dict[str, Any],
    hybrid_threshold: dict[str, Any],
) -> tuple[str | None, str | None]:
    for field in ("kind", "value", "aggregation"):
        if baseline_threshold.get(field) != hybrid_threshold.get(field):
            return f"threshold_{field}_mismatch", (
                f"baseline/hybrid campaign_threshold.{field} differ: "
                f"{baseline_threshold.get(field)!r} != {hybrid_threshold.get(field)!r}"
            )
    return None, None


def measurement_time_ok(name: str, measurement: dict[str, Any]) -> tuple[bool, str | None, str | None]:
    wall_time_ms = measurement.get("wall_time_ms")
    if wall_time_ms is None:
        return False, f"{name}_missing_wall_time_ms", f"{name} campaign_measurement.wall_time_ms is null"
    if not isinstance(wall_time_ms, (int, float)):
        return False, f"{name}_invalid_wall_time_ms", f"{name} campaign_measurement.wall_time_ms is not numeric"
    if wall_time_ms <= 0:
        return False, f"{name}_non_positive_wall_time_ms", f"{name} campaign_measurement.wall_time_ms must be > 0"
    return True, None, None


def build_comparison_payload(
    *,
    baseline_path: Path,
    hybrid_path: Path,
    baseline_payload: dict[str, Any] | None,
    hybrid_payload: dict[str, Any] | None,
) -> tuple[int, dict[str, Any]]:
    baseline_ok, baseline_error = validate_artifact("baseline", baseline_payload)
    if not baseline_ok:
        return 1, build_reject_payload(
            baseline_path=baseline_path,
            hybrid_path=hybrid_path,
            baseline_payload=baseline_payload,
            hybrid_payload=hybrid_payload,
            reject_reason=str(baseline_error),
            caveat="comparison rejected because the baseline artifact is missing or not campaign-ready",
        )
    hybrid_ok, hybrid_error = validate_artifact("hybrid", hybrid_payload)
    if not hybrid_ok:
        return 1, build_reject_payload(
            baseline_path=baseline_path,
            hybrid_path=hybrid_path,
            baseline_payload=baseline_payload,
            hybrid_payload=hybrid_payload,
            reject_reason=str(hybrid_error),
            caveat="comparison rejected because the hybrid artifact is missing or not campaign-ready",
        )

    assert baseline_payload is not None
    assert hybrid_payload is not None
    if baseline_payload.get("target") != hybrid_payload.get("target"):
        return 1, build_reject_payload(
            baseline_path=baseline_path,
            hybrid_path=hybrid_path,
            baseline_payload=baseline_payload,
            hybrid_payload=hybrid_payload,
            reject_reason="target_mismatch",
            caveat=(
                f"baseline/hybrid target differ: {baseline_payload.get('target')!r} != "
                f"{hybrid_payload.get('target')!r}"
            ),
        )

    baseline_threshold = baseline_payload["campaign_threshold"]
    hybrid_threshold = hybrid_payload["campaign_threshold"]
    mismatch_reason, mismatch_caveat = threshold_mismatch_reason(baseline_threshold, hybrid_threshold)
    if mismatch_reason is not None:
        return 1, build_reject_payload(
            baseline_path=baseline_path,
            hybrid_path=hybrid_path,
            baseline_payload=baseline_payload,
            hybrid_payload=hybrid_payload,
            reject_reason=mismatch_reason,
            caveat=str(mismatch_caveat),
        )

    baseline_measurement = baseline_payload["campaign_measurement"]
    hybrid_measurement = hybrid_payload["campaign_measurement"]
    threshold = {
        "kind": baseline_threshold["kind"],
        "value": baseline_threshold["value"],
        "aggregation": baseline_threshold["aggregation"],
    }
    payload: dict[str, Any] = {
        "schema_version": 1,
        "status": "ok",
        "target": baseline_payload["target"],
        "campaign_threshold": threshold,
        "baseline": side_payload(baseline_path, baseline_payload),
        "hybrid": side_payload(hybrid_path, hybrid_payload),
        "comparison_ready": False,
        "speedup_ratio": None,
        "winner": "unresolved",
        "reject_reason": None,
        "caveats": [
            "comparison v1 uses wall-clock-to-threshold and requires schema-matched campaign artifacts",
        ],
    }

    baseline_satisfied = bool(baseline_measurement.get("threshold_satisfied"))
    hybrid_satisfied = bool(hybrid_measurement.get("threshold_satisfied"))
    if not (baseline_satisfied and hybrid_satisfied):
        payload["caveats"].append(
            "comparison remains unresolved until both baseline and hybrid satisfy the same campaign_threshold"
        )
        return 0, payload

    baseline_time_ok, baseline_time_reason, baseline_time_caveat = measurement_time_ok(
        "baseline", baseline_measurement
    )
    if not baseline_time_ok:
        return 1, build_reject_payload(
            baseline_path=baseline_path,
            hybrid_path=hybrid_path,
            baseline_payload=baseline_payload,
            hybrid_payload=hybrid_payload,
            reject_reason=str(baseline_time_reason),
            caveat=str(baseline_time_caveat),
        )
    hybrid_time_ok, hybrid_time_reason, hybrid_time_caveat = measurement_time_ok(
        "hybrid", hybrid_measurement
    )
    if not hybrid_time_ok:
        return 1, build_reject_payload(
            baseline_path=baseline_path,
            hybrid_path=hybrid_path,
            baseline_payload=baseline_payload,
            hybrid_payload=hybrid_payload,
            reject_reason=str(hybrid_time_reason),
            caveat=str(hybrid_time_caveat),
        )

    baseline_wall_time = float(baseline_measurement["wall_time_ms"])
    hybrid_wall_time = float(hybrid_measurement["wall_time_ms"])
    payload["comparison_ready"] = True
    payload["speedup_ratio"] = baseline_wall_time / hybrid_wall_time
    if hybrid_wall_time < baseline_wall_time:
        payload["winner"] = "hybrid"
    elif hybrid_wall_time > baseline_wall_time:
        payload["winner"] = "baseline"
    else:
        payload["winner"] = "tie"
    payload["caveats"].append(
        "v1 compares wall_time_ms from checked-in baseline and hybrid runners; orchestration scope may evolve later"
    )
    return 0, payload


def main_with_defaults(
    *,
    argv: list[str],
    description: str,
    default_baseline: Path,
    default_hybrid: Path,
    default_json_out: Path,
) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--baseline", type=Path, default=default_baseline)
    parser.add_argument("--hybrid", type=Path, default=default_hybrid)
    parser.add_argument("--json-out", type=Path, default=default_json_out)
    args = parser.parse_args(argv)

    baseline_path = args.baseline.resolve()
    hybrid_path = args.hybrid.resolve()
    json_out = args.json_out.resolve()

    baseline_payload = read_json_if_exists(baseline_path)
    hybrid_payload = read_json_if_exists(hybrid_path)
    rc, payload = build_comparison_payload(
        baseline_path=baseline_path,
        hybrid_path=hybrid_path,
        baseline_payload=baseline_payload,
        hybrid_payload=hybrid_payload,
    )
    write_json(json_out, payload)
    return rc
