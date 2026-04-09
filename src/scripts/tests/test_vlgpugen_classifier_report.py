#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
VLGPUGEN = REPO_ROOT / "src" / "passes" / "vlgpugen"
REAL_SUBPROCESS_RUN = subprocess.run


class VlGpuGenClassifierReportTest(unittest.TestCase):
    def _run_classifier_report(self, ir_text: str, *extra_args: str) -> dict:
        self.assertTrue(VLGPUGEN.is_file(), f"missing vlgpugen binary: {VLGPUGEN}")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            merged_ll = root / "merged.ll"
            report = root / "vl_classifier_report.json"
            merged_ll.write_text(textwrap.dedent(ir_text).strip() + "\n", encoding="utf-8")
            REAL_SUBPROCESS_RUN(
                [
                    str(VLGPUGEN),
                    str(merged_ll),
                    f"--classifier-report-out={report}",
                    *extra_args,
                ],
                check=True,
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return json.loads(report.read_text(encoding="utf-8"))

    def test_classifier_report_explains_gpu_and_runtime_reasons(self) -> None:
        payload = self._run_classifier_report(
            """
            declare void @_ZN9Verilated10traceEverOnEb(ptr)

            define void @_Zdemo_eval(ptr %root) {
            entry:
              call void @_Zdemo___ico_sequent(ptr %root)
              call void @_Zdemo_gpu_worker(ptr %root)
              call void @_Zdemo_host_bridge(ptr %root)
              call void @_ZN9Verilated15commandArgsAddEv(ptr %root)
              ret void
            }

            define void @_Zdemo___ico_sequent(ptr %root) {
            entry:
              ret void
            }

            define void @_Zdemo_gpu_worker(ptr %root) {
            entry:
              ret void
            }

            define void @_Zdemo_host_bridge(ptr %root) {
            entry:
              call void @_ZN9Verilated10traceEverOnEb(ptr %root)
              ret void
            }

            define void @_ZN9Verilated15commandArgsAddEv(ptr %root) {
            entry:
              ret void
            }
            """
        )

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["eval_function"], "_Zdemo_eval")
        self.assertTrue(payload["decl_runtime_merge_enabled"])
        self.assertEqual(payload["counts"]["reachable"], 5)
        self.assertEqual(payload["counts"]["gpu"], 3)
        self.assertEqual(payload["counts"]["runtime"], 2)

        functions = {row["name"]: row for row in payload["functions"]}
        self.assertEqual(functions["_Zdemo___ico_sequent"]["placement"], "gpu")
        self.assertEqual(functions["_Zdemo___ico_sequent"]["reason"], "force_include")
        self.assertEqual(functions["_Zdemo___ico_sequent"]["detail"], "___ico_sequent")
        self.assertEqual(functions["_Zdemo_gpu_worker"]["placement"], "gpu")
        self.assertEqual(functions["_Zdemo_gpu_worker"]["reason"], "gpu_reachable")
        self.assertEqual(functions["_Zdemo_host_bridge"]["placement"], "runtime")
        self.assertEqual(functions["_Zdemo_host_bridge"]["reason"], "decl_host_callee")
        self.assertEqual(
            functions["_Zdemo_host_bridge"]["detail"],
            "_ZN9Verilated10traceEverOnEb",
        )
        self.assertEqual(
            functions["_ZN9Verilated15commandArgsAddEv"]["reason"],
            "runtime_prefix",
        )
        self.assertEqual(
            functions["_ZN9Verilated15commandArgsAddEv"]["detail"],
            "_ZN9Verilated",
        )

    def test_no_decl_runtime_merge_leaves_host_bridge_on_gpu(self) -> None:
        payload = self._run_classifier_report(
            """
            declare void @_ZN9Verilated10traceEverOnEb(ptr)

            define void @_Zdemo_eval(ptr %root) {
            entry:
              call void @_Zdemo_host_bridge(ptr %root)
              ret void
            }

            define void @_Zdemo_host_bridge(ptr %root) {
            entry:
              call void @_ZN9Verilated10traceEverOnEb(ptr %root)
              ret void
            }
            """,
            "--no-decl-runtime-merge",
        )

        self.assertFalse(payload["decl_runtime_merge_enabled"])
        functions = {row["name"]: row for row in payload["functions"]}
        self.assertEqual(functions["_Zdemo_host_bridge"]["placement"], "gpu")
        self.assertEqual(functions["_Zdemo_host_bridge"]["reason"], "gpu_reachable")

    def test_root_local_helpers_are_not_stubbed_by_runtime_heuristics(self) -> None:
        payload = self._run_classifier_report(
            """
            @VerilatedSyms_dummy = global i8 0

            declare void @_ZN9Verilated10traceEverOnEb(ptr)

            define void @_Zdemo___024root___eval(ptr %root) {
            entry:
              call void @_Zdemo___024root___ico_sequent__TOP__0(ptr %root)
              call void @_Zdemo___024root___nba_sequent__TOP__1(ptr %root)
              ret void
            }

            define void @_Zdemo___024root___ico_sequent__TOP__0(ptr %root) {
            entry:
              call void @_ZN9Verilated10traceEverOnEb(ptr %root)
              ret void
            }

            define void @_Zdemo___024root___nba_sequent__TOP__1(ptr %root) {
            entry:
              %v = load i8, ptr @VerilatedSyms_dummy
              ret void
            }
            """
        )

        functions = {row["name"]: row for row in payload["functions"]}
        self.assertEqual(
            functions["_Zdemo___024root___ico_sequent__TOP__0"]["placement"],
            "gpu",
        )
        self.assertEqual(
            functions["_Zdemo___024root___ico_sequent__TOP__0"]["reason"],
            "force_include",
        )
        self.assertEqual(
            functions["_Zdemo___024root___nba_sequent__TOP__1"]["placement"],
            "gpu",
        )
        self.assertEqual(
            functions["_Zdemo___024root___nba_sequent__TOP__1"]["reason"],
            "gpu_reachable",
        )


if __name__ == "__main__":
    unittest.main()
