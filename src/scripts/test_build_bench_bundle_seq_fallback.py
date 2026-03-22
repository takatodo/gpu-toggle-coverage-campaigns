#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest

ROOT_DIR = Path(__file__).resolve().parents[2]
CUDA_OPT_DIR = ROOT_DIR / "src" / "sim_accel"
if str(CUDA_OPT_DIR) not in sys.path:
    sys.path.insert(0, str(CUDA_OPT_DIR))

from build_bench_bundle import _patch_cuda_seq_partition_fallback


class BuildBenchBundleSeqFallbackTest(unittest.TestCase):
    def test_missing_seq_partition_symbols_is_clean_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = Path(tmpdir)
            (bundle_dir / "kernel_generated.link.cu").write_text(
                "extern \"C\" __host__ cudaError_t sim_accel_eval_assignw_launch_all("
                "const uint64_t* state_in, uint64_t* state_out, uint32_t nstates, uint32_t block_size) {\n"
                "    return cudaSuccess;\n"
                "}\n",
                encoding="utf-8",
            )
            (bundle_dir / "kernel_generated.full_seq.cu").write_text("// full seq\n", encoding="utf-8")

            changed = _patch_cuda_seq_partition_fallback(bundle_dir)

            self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
