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


class VlGpuGenSegmentManifestTest(unittest.TestCase):
    def _run_vlgpugen(self, ir_text: str) -> dict:
        self.assertTrue(VLGPUGEN.is_file(), f"missing vlgpugen binary: {VLGPUGEN}")
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            merged_ll = root / "merged.ll"
            out_ll = root / "vl_batch_gpu.ll"
            manifest = root / "vl_kernel_manifest.json"
            merged_ll.write_text(textwrap.dedent(ir_text).strip() + "\n", encoding="utf-8")
            REAL_SUBPROCESS_RUN(
                [
                    str(VLGPUGEN),
                    str(merged_ll),
                    "--storage-size=64",
                    f"--out={out_ll}",
                    "--kernel-split=phases",
                    f"--kernel-manifest-out={manifest}",
                ],
                check=True,
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return json.loads(manifest.read_text(encoding="utf-8"))

    def test_helper_only_eval_nba_emits_guarded_helper_segments(self) -> None:
        manifest = self._run_vlgpugen(
            """
            define void @_Zdemo_eval(ptr %root) {
            entry:
              call void @_Zdemo___ico_sequent(ptr %root)
              call void @_Zdemo___eval_nba(ptr %root)
              ret void
            }

            define void @_Zdemo___ico_sequent(ptr %root) {
            entry:
              ret void
            }

            define void @_Zdemo___nba_sequent__TOP__0(ptr %root) {
            entry:
              ret void
            }

            define void @_Zdemo___nba_comb__TOP__0(ptr %root) {
            entry:
              ret void
            }

            define void @_Zdemo___eval_nba(ptr %root) {
            entry:
              %trigger_gep0 = getelementptr i8, ptr %root, i64 8
              %trigger0 = load i64, ptr %trigger_gep0, align 8
              %masked0 = and i64 %trigger0, 1
              %cond0 = icmp eq i64 %masked0, 0
              br i1 %cond0, label %after0, label %seg0

            seg0:
              call void @_Zdemo___nba_sequent__TOP__0(ptr %root)
              br label %after0

            after0:
              %trigger_gep1 = getelementptr i8, ptr %root, i64 8
              %trigger1 = load i64, ptr %trigger_gep1, align 8
              %masked1 = and i64 %trigger1, 3
              %cond1 = icmp eq i64 %masked1, 0
              br i1 %cond1, label %after1, label %seg1

            seg1:
              call void @_Zdemo___nba_comb__TOP__0(ptr %root)
              br label %after1

            after1:
              ret void
            }
            """
        )

        self.assertEqual(
            manifest["launch_sequence"],
            [
                "vl_ico_batch_gpu",
                "vl_nba_seg0_batch_gpu",
                "vl_nba_seg1_batch_gpu",
            ],
        )
        self.assertEqual(
            [kernel["selector"] for kernel in manifest["kernels"]],
            [
                "___ico_sequent",
                "___eval_nba_guarded_helper:_Zdemo___nba_sequent__TOP__0",
                "___eval_nba_guarded_helper:_Zdemo___nba_comb__TOP__0",
            ],
        )

    def test_inline_eval_nba_region_emits_inline_segment_selector(self) -> None:
        manifest = self._run_vlgpugen(
            """
            define void @_Zdemo_eval(ptr %root) {
            entry:
              call void @_Zdemo___ico_sequent(ptr %root)
              call void @_Zdemo___eval_nba(ptr %root)
              ret void
            }

            define void @_Zdemo___ico_sequent(ptr %root) {
            entry:
              ret void
            }

            define void @_Zdemo___nba_sequent__TOP__0(ptr %root) {
            entry:
              ret void
            }

            define void @_Zdemo___nba_comb__TOP__0(ptr %root) {
            entry:
              ret void
            }

            define void @_Zdemo___eval_nba(ptr %root) {
            entry:
              %trigger_gep0 = getelementptr i8, ptr %root, i64 8
              %trigger0 = load i64, ptr %trigger_gep0, align 8
              %masked0 = and i64 %trigger0, 1
              %cond0 = icmp eq i64 %masked0, 0
              br i1 %cond0, label %after0, label %seg0

            seg0:
              call void @_Zdemo___nba_sequent__TOP__0(ptr %root)
              br label %after0

            after0:
              %trigger_gep1 = getelementptr i8, ptr %root, i64 8
              %trigger1 = load i64, ptr %trigger_gep1, align 8
              %masked1 = and i64 %trigger1, 3
              %cond1 = icmp eq i64 %masked1, 0
              br i1 %cond1, label %after1, label %seg1

            seg1:
              %inline_gep = getelementptr i8, ptr %root, i64 16
              store i8 1, ptr %inline_gep, align 1
              br label %after1

            after1:
              %trigger_gep2 = getelementptr i8, ptr %root, i64 8
              %trigger2 = load i64, ptr %trigger_gep2, align 8
              %masked2 = and i64 %trigger2, 3
              %cond2 = icmp eq i64 %masked2, 0
              br i1 %cond2, label %after2, label %seg2

            seg2:
              call void @_Zdemo___nba_comb__TOP__0(ptr %root)
              br label %after2

            after2:
              ret void
            }
            """
        )

        self.assertEqual(
            manifest["launch_sequence"],
            [
                "vl_ico_batch_gpu",
                "vl_nba_seg0_batch_gpu",
                "vl_nba_seg1_batch_gpu",
                "vl_nba_seg2_batch_gpu",
            ],
        )
        self.assertEqual(
            [kernel["selector"] for kernel in manifest["kernels"]],
            [
                "___ico_sequent",
                "___eval_nba_guarded_helper:_Zdemo___nba_sequent__TOP__0",
                "___eval_nba_inline_region:seg1",
                "___eval_nba_guarded_helper:_Zdemo___nba_comb__TOP__0",
            ],
        )


if __name__ == "__main__":
    unittest.main()
