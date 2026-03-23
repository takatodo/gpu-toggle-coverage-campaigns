#!/usr/bin/env python3
"""
Aggregate multiple rtlmeter GPU toggle baseline JSON outputs and report
toggle-subset *cumulative* coverage convergence (union of active_words over runs).

RTLMeter designs live under third_party/rtlmeter/designs; repo-root rtlmeter/ is venv-only.

Typical workflow:
  1) Run run_rtlmeter_gpu_toggle_baseline.py several times with different seeds / configs,
     each with --json-out work/.../run_<id>.json
  2) python3 src/tools/analyze_rtlmeter_coverage_convergence.py work/.../run_*.json

Uses summarize_coverage_convergence() from rtlmeter_sim_accel_adapter for ratio targets
(25/50/75/90%) and novelty stats.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNNERS = REPO_ROOT / "src" / "runners"
if str(_RUNNERS) not in sys.path:
    sys.path.insert(0, str(_RUNNERS))

from rtlmeter_sim_accel_adapter import summarize_coverage_convergence  # noqa: E402


def _load_summary(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _walltime_s(data: dict) -> float | None:
    cov = (data.get("collector") or {}).get("coverage") or {}
    v = cov.get("gpu_coverage_walltime_s")
    if isinstance(v, (int, float)) and v > 0:
        return float(v)
    v = cov.get("cpu_coverage_walltime_s")
    if isinstance(v, (int, float)) and v > 0:
        return float(v)
    m = data.get("metrics") or {}
    gpu = m.get("gpu_ms_per_rep")
    if isinstance(gpu, (int, float)) and gpu > 0:
        return float(gpu) / 1000.0
    cpu = m.get("cpu_ms_per_rep")
    if isinstance(cpu, (int, float)) and cpu > 0:
        return float(cpu) / 1000.0
    return None


def _active_words(data: dict) -> set[str]:
    rts = data.get("real_toggle_subset") or {}
    words = rts.get("active_words")
    if isinstance(words, list):
        return set(str(x) for x in words)
    return set()


def _points_total(data: dict) -> int | None:
    rts = data.get("real_toggle_subset") or {}
    t = rts.get("points_total")
    if isinstance(t, int):
        return t
    return None


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Union-toggle convergence across rtlmeter baseline JSON summaries"
    )
    p.add_argument(
        "json_paths",
        nargs="+",
        type=Path,
        help="Baseline JSON files (schema rtlmeter-gpu-toggle-baseline-v1)",
    )
    p.add_argument(
        "--sort-by",
        choices=("given", "case", "seed"),
        default="given",
        help="Order of runs (default: argv order)",
    )
    args = p.parse_args(argv)

    paths = [Path(x).resolve() for x in args.json_paths]
    rows: list[tuple[Path, dict]] = []
    for path in paths:
        if not path.is_file():
            print(f"missing: {path}", file=sys.stderr)
            return 1
        rows.append((path, _load_summary(path)))

    if args.sort_by == "case":
        rows.sort(key=lambda r: (str(r[1].get("case") or ""), r[0].name))
    elif args.sort_by == "seed":
        rows.sort(
            key=lambda r: (
                str((r[1].get("execute_runtime_inputs") or {}).get("seed") or ""),
                r[0].name,
            )
        )

    points_total: int | None = None
    cumulative: set[str] = set()
    iterations: list[dict] = []
    cum_wall = 0.0

    for i, (path, data) in enumerate(rows):
        if points_total is None:
            points_total = _points_total(data)
        aw = _active_words(data)
        new = aw - cumulative
        cumulative |= aw
        wt = _walltime_s(data)
        if wt is not None:
            cum_wall += wt
        novelty = len(new)
        iterations.append(
            {
                "iteration": i,
                "seed": (data.get("execute_runtime_inputs") or {}).get("seed"),
                "case": data.get("case"),
                "path": str(path),
                "walltime_s": wt,
                "total_hit_points": len(aw),
                "novelty_points": novelty,
                "cumulative_hit_points": len(cumulative),
                "coverage_per_second": (len(aw) / wt) if wt and wt > 0 else None,
            }
        )

    conv = summarize_coverage_convergence(
        iterations,
        points_total=points_total,
        target_ratios=[0.25, 0.50, 0.75, 0.90],
    )

    print("# per-run (order may be sorted; cumulative_hit_points = union so far)")
    for it in iterations:
        print(
            f"{it['iteration']}\tnovelty={it['novelty_points']}\t"
            f"run_hit={it['total_hit_points']}\tcum_union={it['cumulative_hit_points']}\t"
            f"wall_s={it['walltime_s']}\t{it['path']}"
        )
    print()
    print(json.dumps(conv, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
