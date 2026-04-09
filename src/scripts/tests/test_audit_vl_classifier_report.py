#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_vl_classifier_report.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditVlClassifierReportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_vl_classifier_report_test", MODULE_PATH)

    def test_main_passes_when_counts_and_required_entries_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report_path = root / "report.json"
            expect_path = root / "expect.json"
            out_path = root / "summary.json"

            report_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "eval_function": "_Zdemo_eval",
                        "counts": {"reachable": 4, "gpu": 3, "runtime": 1},
                        "functions": [
                            {
                                "name": "_Zdemo_eval",
                                "placement": "gpu",
                                "reason": "gpu_reachable",
                                "detail": "reachable_from_eval",
                            },
                            {
                                "name": "_Zdemo___ico_sequent__TOP__0",
                                "placement": "gpu",
                                "reason": "force_include",
                                "detail": "___ico_sequent",
                            },
                            {
                                "name": "_Zdemo___eval_phase__act",
                                "placement": "runtime",
                                "reason": "decl_host_callee",
                                "detail": "_Z13sc_time_stampv",
                            },
                            {
                                "name": "_Zdemo___nba_sequent__TOP__0",
                                "placement": "gpu",
                                "reason": "gpu_reachable",
                                "detail": "reachable_from_eval",
                            },
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            expect_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "target": "demo",
                        "expected_counts": {"reachable": 4, "gpu": 3, "runtime": 1},
                        "required_reasons": ["gpu_reachable", "force_include", "decl_host_callee"],
                        "required_entries": [
                            {"name_contains": "___ico_sequent__TOP__0", "placement": "gpu", "reason": "force_include"},
                            {"name_contains": "___eval_phase__act", "placement": "runtime", "reason": "decl_host_callee", "detail_contains": "sc_time_stamp"},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            rc = self.module.main(
                [str(report_path), "--expect", str(expect_path), "--json-out", str(out_path)]
            )

            self.assertEqual(rc, 0)
            summary = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertTrue(summary["passed"])
            self.assertEqual(summary["target"], "demo")
            self.assertEqual(summary["count_mismatches"], {})
            self.assertEqual(summary["missing_reasons"], [])
            self.assertEqual(summary["missing_entries"], [])
            self.assertEqual(len(summary["matched_entries"]), 2)

    def test_main_fails_when_reason_or_required_entry_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            report_path = root / "report.json"
            expect_path = root / "expect.json"

            report_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "eval_function": "_Zdemo_eval",
                        "counts": {"reachable": 2, "gpu": 2, "runtime": 0},
                        "functions": [
                            {
                                "name": "_Zdemo_eval",
                                "placement": "gpu",
                                "reason": "gpu_reachable",
                                "detail": "reachable_from_eval",
                            },
                            {
                                "name": "_Zdemo___nba_sequent__TOP__0",
                                "placement": "gpu",
                                "reason": "gpu_reachable",
                                "detail": "reachable_from_eval",
                            },
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            expect_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "target": "demo",
                        "expected_counts": {"reachable": 2, "gpu": 1, "runtime": 1},
                        "required_reasons": ["gpu_reachable", "decl_host_callee"],
                        "required_entries": [
                            {"name_contains": "___eval_phase__act", "placement": "runtime", "reason": "decl_host_callee"},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            rc = self.module.main([str(report_path), "--expect", str(expect_path)])

            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
