#!/usr/bin/env python3
"""
Quantify a small, machine-checkable subset of AGENTS.md repository-structure rules.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "agents_guideline_audit.json"

BANNED_PYTHON_BASENAMES = {"misc.py", "tmp.py", "do_everything.py"}
CLI_DIRS = ("src/tools", "src/runners")
DOC_PATHS = ("AGENTS.md", "README.md", "docs")
LINE_COUNT_WARN = 300
LINE_COUNT_DANGER = 500
IGNORED_TOP_LEVEL_DIRS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "output",
    "rtlmeter",
    "third_party",
    "work",
}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _iter_repo_python_files(repo_root: Path) -> list[Path]:
    results: list[Path] = []
    for path in repo_root.rglob("*.py"):
        rel = path.relative_to(repo_root)
        if any(part in IGNORED_TOP_LEVEL_DIRS for part in rel.parts):
            continue
        results.append(path)
    return sorted(results)


def _collect_markdown_texts(repo_root: Path) -> dict[Path, str]:
    texts: dict[Path, str] = {}
    for raw in DOC_PATHS:
        path = (repo_root / raw).resolve()
        if path.is_file():
            texts[path] = path.read_text(encoding="utf-8")
            continue
        if path.is_dir():
            for child in sorted(path.rglob("*.md")):
                texts[child] = child.read_text(encoding="utf-8")
    return texts


def _collect_cli_rows(repo_root: Path) -> list[dict[str, Any]]:
    markdown_texts = _collect_markdown_texts(repo_root)
    tests_dir = repo_root / "src" / "scripts" / "tests"
    rows: list[dict[str, Any]] = []
    for raw_dir in CLI_DIRS:
        cli_dir = repo_root / raw_dir
        if not cli_dir.is_dir():
            continue
        for path in sorted(cli_dir.glob("*.py")):
            if path.name == "__init__.py":
                continue
            text = path.read_text(encoding="utf-8")
            if 'if __name__ == "__main__"' not in text:
                continue
            rel = path.relative_to(repo_root)
            stem = path.stem
            matching_tests = (
                sorted(tests_dir.glob(f"test_{stem}*.py")) if tests_dir.is_dir() else []
            )
            doc_mentions = [
                str(doc_path.relative_to(repo_root))
                for doc_path, text in markdown_texts.items()
                if path.name in text
            ]
            line_count = len(text.splitlines())
            rows.append(
                {
                    "path": str(rel),
                    "directory": raw_dir,
                    "basename": path.name,
                    "line_count": line_count,
                    "has_matching_test": bool(matching_tests),
                    "matching_test_count": len(matching_tests),
                    "matching_test_paths": [
                        str(test_path.relative_to(repo_root)) for test_path in matching_tests
                    ],
                    "has_doc_mention": bool(doc_mentions),
                    "doc_mentions": doc_mentions,
                    "over_300_loc": line_count > LINE_COUNT_WARN,
                    "over_500_loc": line_count > LINE_COUNT_DANGER,
                }
            )
    return rows


def _ratio(hit_count: int, total_count: int) -> float | None:
    if total_count == 0:
        return None
    return hit_count / total_count


def _build_payload(repo_root: Path) -> dict[str, Any]:
    repo_python_files = _iter_repo_python_files(repo_root)
    root_python_files = sorted(path for path in repo_python_files if path.parent == repo_root)
    banned_python_files = sorted(
        path for path in repo_python_files if path.name in BANNED_PYTHON_BASENAMES
    )
    cli_rows = _collect_cli_rows(repo_root)
    total_clis = len(cli_rows)
    with_tests = sum(1 for row in cli_rows if row["has_matching_test"])
    with_docs = sum(1 for row in cli_rows if row["has_doc_mention"])
    over_300 = [row for row in cli_rows if row["over_300_loc"]]
    over_500 = [row for row in cli_rows if row["over_500_loc"]]

    hard_gates = {
        "repo_root_python_files_zero": {
            "passed": len(root_python_files) == 0,
            "count": len(root_python_files),
            "violations": [str(path.relative_to(repo_root)) for path in root_python_files],
        },
        "banned_python_filenames_zero": {
            "passed": len(banned_python_files) == 0,
            "count": len(banned_python_files),
            "violations": [str(path.relative_to(repo_root)) for path in banned_python_files],
        },
    }
    directory_counts: dict[str, int] = {}
    for raw_dir in CLI_DIRS:
        cli_dir = repo_root / raw_dir
        if cli_dir.is_dir():
            directory_counts[raw_dir] = len(
                [path for path in cli_dir.glob("*.py") if path.name != "__init__.py"]
            )

    return {
        "schema_version": 1,
        "scope": "agents_guideline_audit",
        "agents_md": str((repo_root / "AGENTS.md").resolve()),
        "summary": {
            "hard_gate_passed": all(gate["passed"] for gate in hard_gates.values()),
            "repo_root_python_file_count": len(root_python_files),
            "banned_python_filename_count": len(banned_python_files),
            "total_cli_files": total_clis,
            "cli_with_matching_test_count": with_tests,
            "cli_with_matching_test_ratio": _ratio(with_tests, total_clis),
            "cli_with_doc_mention_count": with_docs,
            "cli_with_doc_mention_ratio": _ratio(with_docs, total_clis),
            "cli_over_300_loc_count": len(over_300),
            "cli_over_500_loc_count": len(over_500),
            "directory_cli_counts": directory_counts,
        },
        "policy_targets": {
            "repo_root_python_file_count": 0,
            "banned_python_filename_count": 0,
            "new_cli_requires_matching_test": True,
            "new_cli_requires_doc_mention": True,
            "cli_over_300_loc_count": "tracked_debt",
            "cli_over_500_loc_count": "tracked_debt",
        },
        "hard_gates": hard_gates,
        "top_debt_lists": {
            "missing_tests": [row["path"] for row in cli_rows if not row["has_matching_test"]],
            "missing_doc_mentions": [row["path"] for row in cli_rows if not row["has_doc_mention"]],
            "over_300_loc": [row["path"] for row in over_300],
            "over_500_loc": [row["path"] for row in over_500],
        },
        "cli_rows": cli_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    payload = _build_payload(repo_root)
    _write_json(args.json_out.resolve(), payload)
    print(args.json_out.resolve())
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["summary"]["hard_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
