#!/usr/bin/env python3
"""
Codebase complexity snapshot tool.

Usage — take a snapshot:
    python complexity_audit/audit.py --target /path/to/repo --config complexity_audit/config.json

Usage — compare against a baseline:
    python complexity_audit/audit.py --target . --config complexity_audit/config.json \\
        --baseline work/complexity_snapshot.json --diff-out work/complexity_diff.json

The config JSON drives everything; see complexity_audit/config.json for the schema.
Exit code 1 when --baseline is given and at least one regression is detected.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# config schema (all keys optional — defaults shown in config.json)
# ---------------------------------------------------------------------------

def _load_config(config_path: Path) -> dict[str, Any]:
    return json.loads(config_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _count_lines(path: Path) -> int:
    try:
        return path.read_text(encoding="utf-8", errors="replace").count("\n")
    except OSError:
        return 0


def _is_ignored(path: Path, ignored: set[str]) -> bool:
    return any(part in ignored for part in path.parts)


# ---------------------------------------------------------------------------
# metric collectors
# ---------------------------------------------------------------------------

def _git_tracked_files(target: Path) -> set[str]:
    """Return set of git-tracked relative paths, or empty set if not a git repo."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return set(result.stdout.splitlines())
    except (OSError, subprocess.TimeoutExpired):
        pass
    return set()


def _metric_variant_files(target: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    """Count git-tracked files whose name matches any variant_patterns glob."""
    patterns: list[str] = cfg.get("variant_patterns", [])
    search_dirs: list[str] = cfg.get("variant_search_dirs", [])
    ignored: set[str] = set(cfg.get("ignored_parts", []))

    tracked = _git_tracked_files(target)
    use_git = bool(tracked)

    files: list[str] = []
    for rel_dir in search_dirs:
        d = target / rel_dir
        if not d.exists():
            continue
        for pattern in patterns:
            for p in d.rglob(pattern):
                if _is_ignored(p, ignored) or not p.is_file():
                    continue
                rel = str(p.relative_to(target))
                if use_git and rel not in tracked:
                    continue
                files.append(rel)
    files = sorted(set(files))
    return {"count": len(files), "files": files, "git_tracked_only": use_git}


def _metric_runner_loc(target: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    runner_dirs: list[str] = cfg.get("runner_dirs", [])
    outlier_threshold: int = cfg.get("runner_outlier_loc", 500)
    ignored: set[str] = set(cfg.get("ignored_parts", []))

    entries: list[dict[str, Any]] = []
    for rel_dir in runner_dirs:
        d = target / rel_dir
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.py")):
            if _is_ignored(p, ignored):
                continue
            entries.append({"file": str(p.relative_to(target)), "loc": _count_lines(p)})

    entries.sort(key=lambda e: e["loc"], reverse=True)
    total = sum(e["loc"] for e in entries)
    outliers = [e for e in entries if e["loc"] >= outlier_threshold]
    outlier_total = sum(e["loc"] for e in outliers)

    return {
        "total_loc": total,
        "file_count": len(entries),
        "outlier_threshold": outlier_threshold,
        "outlier_count": len(outliers),
        "outlier_loc": outlier_total,
        "outlier_share": round(outlier_total / total, 3) if total else 0.0,
        "by_file": entries,
    }


def _metric_docs_categories(target: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    docs_dir_rel: str = cfg.get("docs_dir", "docs")
    suffix_map: dict[str, str] = cfg.get("docs_suffix_categories", {})
    index_stems: list[str] = cfg.get("docs_index_stems", ["README"])

    docs_dir = target / docs_dir_rel
    if not docs_dir.exists():
        return {}

    counts: dict[str, int] = {k: 0 for k in suffix_map}
    counts["other"] = 0
    by_file: list[dict[str, Any]] = []

    for p in sorted(docs_dir.glob("*.md")):
        if p.stem in index_stems:
            category = "index"
        else:
            category = "other"
            # longest suffix wins
            best_len = 0
            for cat, suffix in suffix_map.items():
                if p.stem.endswith(suffix) and len(suffix) > best_len:
                    category = cat
                    best_len = len(suffix)
            counts[category] = counts.get(category, 0) + 1

        by_file.append({"file": p.name, "category": category, "loc": _count_lines(p)})

    return {
        "total_doc_count": sum(v for k, v in counts.items() if k != "index"),
        "by_category": counts,
        "by_file": by_file,
    }


def _metric_test_naming(target: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    test_dir_rel: str = cfg.get("test_dir", "")
    suffix_patterns: dict[str, str] = cfg.get("test_suffix_patterns", {})

    if not test_dir_rel:
        return {}
    test_dir = target / test_dir_rel
    if not test_dir.exists():
        return {}

    buckets: dict[str, list[str]] = {k: [] for k in suffix_patterns}
    buckets["other"] = []

    for p in sorted(test_dir.glob("test_*.py")):
        matched = "other"
        best_len = 0
        for pat, suffix in suffix_patterns.items():
            if p.stem.endswith(suffix) and len(suffix) > best_len:
                matched = pat
                best_len = len(suffix)
        buckets[matched].append(p.name)

    return {
        "total_test_count": sum(len(v) for v in buckets.values()),
        "by_pattern": {k: {"count": len(v), "files": v} for k, v in buckets.items()},
    }


def _metric_file_counts(target: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    dirs: list[str] = cfg.get("file_count_dirs", [])
    result: dict[str, int] = {}
    for rel in dirs:
        d = target / rel
        result[rel] = sum(
            1 for p in d.iterdir() if p.is_file()
        ) if d.exists() else 0
    return result


def _metric_source_loc(target: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    dirs: list[str] = cfg.get("source_loc_dirs", [])
    suffix: str = cfg.get("source_loc_suffix", ".py")
    result: dict[str, int] = {}
    for rel in dirs:
        d = target / rel
        result[rel] = sum(_count_lines(p) for p in d.glob(f"*{suffix}")) if d.exists() else 0
    return result


# ---------------------------------------------------------------------------
# snapshot
# ---------------------------------------------------------------------------

def build_snapshot(target: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "target": str(target),
        "config_variant_patterns": cfg.get("variant_patterns", []),
        "metrics": {
            "variant_files": _metric_variant_files(target, cfg),
            "runner_loc": _metric_runner_loc(target, cfg),
            "docs_categories": _metric_docs_categories(target, cfg),
            "test_naming": _metric_test_naming(target, cfg),
            "file_counts": _metric_file_counts(target, cfg),
            "source_loc": _metric_source_loc(target, cfg),
        },
    }


# ---------------------------------------------------------------------------
# baseline diff
# ---------------------------------------------------------------------------

def _delta(label: str, old: int | float, new: int | float) -> dict[str, Any]:
    diff = new - old
    return {
        "metric": label,
        "baseline": old,
        "current": new,
        "delta": round(float(diff), 3),
        "direction": "up" if diff > 0 else ("down" if diff < 0 else "flat"),
    }


def compare_snapshots(
    baseline: dict[str, Any],
    current: dict[str, Any],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    bm = baseline["metrics"]
    cm = current["metrics"]
    comparisons: list[dict[str, Any]] = []

    # variant_files count
    comparisons.append(_delta(
        "variant_files.count",
        bm["variant_files"]["count"],
        cm["variant_files"]["count"],
    ))

    # runner outlier share + total LOC
    comparisons.append(_delta(
        "runner_loc.outlier_share",
        bm["runner_loc"]["outlier_share"],
        cm["runner_loc"]["outlier_share"],
    ))
    comparisons.append(_delta(
        "runner_loc.total_loc",
        bm["runner_loc"]["total_loc"],
        cm["runner_loc"]["total_loc"],
    ))

    # docs: each category
    b_cats = bm.get("docs_categories", {}).get("by_category", {})
    c_cats = cm.get("docs_categories", {}).get("by_category", {})
    all_cats = set(b_cats) | set(c_cats)
    for cat in sorted(all_cats):
        comparisons.append(_delta(
            f"docs_categories.{cat}",
            b_cats.get(cat, 0),
            c_cats.get(cat, 0),
        ))

    # test naming: other ratio
    btest = bm.get("test_naming", {})
    ctest = cm.get("test_naming", {})
    b_other = btest.get("by_pattern", {}).get("other", {}).get("count", 0)
    c_other = ctest.get("by_pattern", {}).get("other", {}).get("count", 0)
    b_total = btest.get("total_test_count", 1)
    c_total = ctest.get("total_test_count", 1)
    comparisons.append(_delta(
        "test_naming.other_ratio",
        round(b_other / b_total, 3) if b_total else 0.0,
        round(c_other / c_total, 3) if c_total else 0.0,
    ))

    # file counts per dir
    b_fc = bm.get("file_counts", {})
    c_fc = cm.get("file_counts", {})
    for key in sorted(set(b_fc) | set(c_fc)):
        comparisons.append(_delta(
            f"file_counts.{key}",
            b_fc.get(key, 0),
            c_fc.get(key, 0),
        ))

    # metrics where "up" is not a regression (e.g. test count growing is fine)
    not_regression: set[str] = set(cfg.get("not_regression_metrics", []))

    regressions = [
        c for c in comparisons
        if c["direction"] == "up" and c["metric"] not in not_regression
    ]

    return {
        "baseline_at": baseline.get("generated_at", ""),
        "current_at": current.get("generated_at", ""),
        "comparisons": comparisons,
        "regressions": regressions,
        "regression_count": len(regressions),
    }


# ---------------------------------------------------------------------------
# markdown report
# ---------------------------------------------------------------------------

def _trend(diff: dict[str, Any] | None, metric: str) -> str:
    """Return a trend suffix like ' (+2 ↑)' or ' (-1 ↓)' from a diff payload."""
    if diff is None:
        return ""
    for c in diff.get("comparisons", []):
        if c["metric"] == metric:
            d = c["delta"]
            if d == 0:
                return ""
            arrow = "↑" if d > 0 else "↓"
            sign = "+" if d > 0 else ""
            return f" ({sign}{d} {arrow})"
    return ""


def render_report(
    snapshot: dict[str, Any],
    diff: dict[str, Any] | None = None,
) -> str:
    m = snapshot["metrics"]
    ts = snapshot.get("generated_at", "")[:19].replace("T", " ")
    target = snapshot.get("target", "")
    lines: list[str] = []

    lines += [
        "# Codebase Complexity Report",
        "",
        f"Generated: {ts} UTC  ",
        f"Target: `{target}`",
        "",
    ]

    if diff:
        reg = diff["regression_count"]
        status = f"**{reg} regression(s) detected**" if reg else "No regressions"
        lines += [
            f"Baseline: {diff['baseline_at'][:19].replace('T', ' ')} UTC — {status}",
            "",
        ]

    # --- summary table ---
    rl = m["runner_loc"]
    vf = m["variant_files"]
    dc = m["docs_categories"]
    tn = m["test_naming"]

    total_tests = tn.get("total_test_count", 0)
    other_tests = tn.get("by_pattern", {}).get("other", {}).get("count", 0)
    other_ratio = f"{other_tests / total_tests:.0%}" if total_tests else "—"

    lines += [
        "## Summary",
        "",
        "| Metric | Value | Trend |",
        "|---|---|---|",
        f"| variant files (`*threshold5*`) | {vf['count']}"
        f" | {_trend(diff, 'variant_files.count') or '—'} |",
        f"| runner total LOC | {rl['total_loc']:,}"
        f" | {_trend(diff, 'runner_loc.total_loc') or '—'} |",
        f"| runner outlier share (≥{rl['outlier_threshold']} LOC) | {rl['outlier_share']:.1%}"
        f" | {_trend(diff, 'runner_loc.outlier_share') or '—'} |",
        f"| docs total | {dc.get('total_doc_count', 0)}"
        f" | {_trend(diff, 'docs_categories.other') or '—'} |",
        f"| test naming `other` ratio | {other_ratio}"
        f" | {_trend(diff, 'test_naming.other_ratio') or '—'} |",
        "",
    ]

    # --- variant files ---
    patterns_str = ", ".join(f"`{p}`" for p in snapshot.get("config_variant_patterns", []))
    lines += [
        "## 1. Variant Files",
        "",
        f"Patterns: {patterns_str or '_(none configured)_'}  ",
        f"Count outside build directories: **{vf['count']}**",
        "",
    ]
    if vf["files"]:
        lines.append("```")
        lines += vf["files"]
        lines.append("```")
    else:
        lines.append("_(none)_")
    lines.append("")

    # --- runner LOC ---
    lines += [
        "## 2. Runner LOC Distribution",
        "",
        f"Total: **{rl['total_loc']:,} LOC** across {rl['file_count']} files.  ",
        f"Outliers (≥ {rl['outlier_threshold']} LOC): "
        f"**{rl['outlier_count']} files**, "
        f"**{rl['outlier_share']:.1%}** of total.",
        "",
        "| File | LOC |",
        "|---|---|",
    ]
    for e in rl.get("by_file", []):
        marker = " ⚠" if e["loc"] >= rl["outlier_threshold"] else ""
        lines.append(f"| `{e['file']}` | {e['loc']:,}{marker} |")
    lines.append("")

    # --- docs categories ---
    cats = dc.get("by_category", {})
    lines += [
        "## 3. Docs Categories",
        "",
        f"Total: **{dc.get('total_doc_count', 0)} docs**",
        "",
        "| Category | Count | Trend |",
        "|---|---|---|",
    ]
    for cat, count in sorted(cats.items()):
        lines.append(
            f"| {cat} | {count} | {_trend(diff, f'docs_categories.{cat}') or '—'} |"
        )
    lines += [
        "",
        "### By file",
        "",
        "| File | Category | LOC |",
        "|---|---|---|",
    ]
    for entry in dc.get("by_file", []):
        lines.append(f"| `{entry['file']}` | {entry['category']} | {entry['loc']} |")
    lines.append("")

    # --- test naming ---
    lines += [
        "## 4. Test Naming Patterns",
        "",
        f"Total: **{total_tests} test files**",
        "",
        "| Pattern | Count | Share |",
        "|---|---|---|",
    ]
    for pat, info in sorted(tn.get("by_pattern", {}).items()):
        cnt = info["count"]
        share = f"{cnt / total_tests:.0%}" if total_tests else "—"
        lines.append(f"| `{pat}` | {cnt} | {share} |")
    lines.append("")

    # --- file counts ---
    fc = m.get("file_counts", {})
    lines += [
        "## 5. File Counts by Directory",
        "",
        "| Directory | Files | Trend |",
        "|---|---|---|",
    ]
    for d, cnt in sorted(fc.items()):
        lines.append(
            f"| `{d}` | {cnt} | {_trend(diff, f'file_counts.{d}') or '—'} |"
        )
    lines.append("")

    # --- source LOC ---
    sl = m.get("source_loc", {})
    total_sl = sum(sl.values())
    lines += [
        "## 6. Source LOC by Directory",
        "",
        f"Total (measured dirs): **{total_sl:,} LOC**",
        "",
        "| Directory | LOC | Share |",
        "|---|---|---|",
    ]
    for d, loc in sorted(sl.items(), key=lambda x: -x[1]):
        share = f"{loc / total_sl:.1%}" if total_sl else "—"
        lines.append(f"| `{d}` | {loc:,} | {share} |")
    lines.append("")

    # --- regression detail ---
    if diff and diff["regression_count"]:
        lines += [
            "## Regressions",
            "",
            "| Metric | Baseline | Current | Delta |",
            "|---|---|---|---|",
        ]
        for r in diff["regressions"]:
            lines.append(
                f"| `{r['metric']}` | {r['baseline']} | {r['current']} | +{r['delta']} |"
            )
        lines.append("")

    return "\n".join(lines)


def _print_diff(diff: dict[str, Any]) -> None:
    print(f"baseline : {diff['baseline_at']}")
    print(f"current  : {diff['current_at']}")
    print()
    col_w = 48
    print(f"{'metric':<{col_w}} {'baseline':>10} {'current':>10} {'delta':>8}  dir")
    print("-" * (col_w + 38))
    for c in diff["comparisons"]:
        marker = " !" if c["direction"] == "up" else ("  " if c["direction"] == "flat" else " v")
        print(
            f"{c['metric']:<{col_w}} {str(c['baseline']):>10} {str(c['current']):>10}"
            f" {c['delta']:>+8.3f}  {c['direction']}{marker}"
        )
    print()
    print(f"regressions: {diff['regression_count']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path.cwd(),
        help="Root directory of the codebase to audit (default: cwd)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=SCRIPT_DIR / "config.json",
        help="Path to config JSON (default: complexity_audit/config.json next to this script)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write snapshot JSON here (default: <target>/work/complexity_snapshot.json)",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Compare current snapshot against this baseline JSON",
    )
    parser.add_argument(
        "--diff-out",
        type=Path,
        default=None,
        help="Write diff JSON here (only used with --baseline)",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=None,
        help="Write Markdown report here (default: <target>/work/complexity_report.md)",
    )
    args = parser.parse_args(argv)

    target = args.target.resolve()
    cfg = _load_config(args.config)

    json_out = args.json_out or (target / "work" / "complexity_snapshot.json")
    snapshot = build_snapshot(target, cfg)
    _write_json(json_out, snapshot)
    print(f"snapshot -> {json_out}")

    diff: dict[str, Any] | None = None
    if args.baseline is not None:
        baseline_path = Path(args.baseline)
        if not baseline_path.exists():
            print(f"error: baseline not found: {baseline_path}", file=sys.stderr)
            return 1
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        diff = compare_snapshots(baseline, snapshot, cfg)
        _print_diff(diff)

        if args.diff_out:
            _write_json(args.diff_out, diff)
            print(f"diff -> {args.diff_out}")

    report_out = args.report_out or (target / "work" / "complexity_report.md")
    report_text = render_report(snapshot, diff)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(report_text, encoding="utf-8")
    print(f"report  -> {report_out}")

    return 1 if (diff and diff["regression_count"] > 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
