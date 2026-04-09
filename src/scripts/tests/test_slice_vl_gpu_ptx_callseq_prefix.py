from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.tools.slice_vl_gpu_ptx_callseq_prefix import slice_kernel_callseq_prefix


SAMPLE_PTX = """// header
.visible .entry vl_target_gpu(
\t.param .u64 vl_target_gpu_param_0,
\t.param .u32 vl_target_gpu_param_1
)
{
\tmov.u32 \t%r1, %tid.x;
\t{ // callseq 10, 0
\t.param .b64 param0;
\tst.param.b64 \t[param0+0], %rd1;
\tcall.uni helper10, (param0);
\t} // callseq 10
\tadd.s32 \t%r2, %r1, 1;
\t{ // callseq 11, 0
\t.param .b64 param0;
\tst.param.b64 \t[param0+0], %rd1;
\tcall.uni helper11, (param0);
\t} // callseq 11
\tret;
}

.visible .entry vl_other_gpu(
\t.param .u64 vl_other_gpu_param_0
)
{
\tret;
}
"""


class SliceVlGpuPtxCallseqPrefixTest(unittest.TestCase):
    def test_truncates_target_kernel_after_requested_callseq(self) -> None:
        out_text, summary = slice_kernel_callseq_prefix(
            SAMPLE_PTX,
            kernel_name="vl_target_gpu",
            max_callseq=10,
        )

        self.assertIn("call.uni helper10", out_text)
        self.assertNotIn("call.uni helper11", out_text)
        self.assertIn("// truncated by slice_vl_gpu_ptx_callseq_prefix.py", out_text)
        self.assertIn(".visible .entry vl_other_gpu(", out_text)
        self.assertEqual(summary["kept_callseq_count"], 1)
        self.assertEqual(summary["kept_callseq_max"], 10)
        self.assertEqual(summary["dropped_callseq_count"], 1)
        self.assertEqual(summary["dropped_callseq_min"], 11)

    def test_rejects_missing_kernel(self) -> None:
        with self.assertRaisesRegex(ValueError, "kernel entry not found"):
            slice_kernel_callseq_prefix(
                SAMPLE_PTX,
                kernel_name="missing_kernel",
                max_callseq=10,
            )

    def test_allows_cutoff_before_first_callseq_as_zero_call_prefix(self) -> None:
        out_text, summary = slice_kernel_callseq_prefix(
            SAMPLE_PTX,
            kernel_name="vl_target_gpu",
            max_callseq=9,
        )

        self.assertNotIn("call.uni helper10", out_text)
        self.assertNotIn("call.uni helper11", out_text)
        self.assertEqual(summary["kept_callseq_count"], 0)
        self.assertEqual(summary["kept_callseq_min"], None)
        self.assertEqual(summary["dropped_callseq_min"], 10)

    def test_cli_writes_ptx_and_summary_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmpdir = Path(td)
            input_ptx = tmpdir / "input.ptx"
            output_ptx = tmpdir / "output.ptx"
            output_json = tmpdir / "summary.json"
            input_ptx.write_text(SAMPLE_PTX, encoding="utf-8")

            subprocess.run(
                [
                    "python3",
                    "src/tools/slice_vl_gpu_ptx_callseq_prefix.py",
                    "--ptx",
                    str(input_ptx),
                    "--kernel",
                    "vl_target_gpu",
                    "--max-callseq",
                    "10",
                    "--out",
                    str(output_ptx),
                    "--json-out",
                    str(output_json),
                ],
                check=True,
                cwd="/home/takatodo/gpu-toggle-coverage-campaigns",
            )

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["kernel_name"], "vl_target_gpu")
            self.assertEqual(payload["requested_max_callseq"], 10)
            self.assertEqual(payload["kept_callseq_max"], 10)
            self.assertTrue(output_ptx.is_file())


if __name__ == "__main__":
    unittest.main()
