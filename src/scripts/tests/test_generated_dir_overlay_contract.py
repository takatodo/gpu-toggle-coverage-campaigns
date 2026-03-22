#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest

_RUNNERS_DIR = Path(__file__).resolve().parents[2] / "runners"
if str(_RUNNERS_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNERS_DIR))

from opentitan_support.generate_opentitan_tlul_slice_generated_dirs import (
    _overlay_structured_raw_sidecars,
)


class GeneratedDirOverlayContractTest(unittest.TestCase):
    def test_overlay_preserves_existing_fused_link_cu(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            raw_dir = root / "raw"
            fused_dir = root / "fused"
            raw_dir.mkdir()
            fused_dir.mkdir()

            top_module = "edn_main_sm_gpu_cov_tb"
            raw_base = raw_dir / f"{top_module}.sim_accel.kernel.cu"
            raw_base.write_text("// raw kernel base\n", encoding="utf-8")
            raw_link = raw_base.with_name(raw_base.name + ".link.cu")
            raw_link.write_text("// raw link without host views\n", encoding="utf-8")
            raw_comm = raw_base.with_name(raw_base.name + ".comm.tsv")
            raw_comm.write_text("raw-comm\n", encoding="utf-8")

            fused_link = fused_dir / "kernel_generated.link.cu"
            fused_link.write_text(
                "// fused link with sim_accel_eval_preload_target_host_views\n",
                encoding="utf-8",
            )
            fused_comm = fused_dir / "kernel_generated.comm.tsv"
            fused_comm.write_text("old-comm\n", encoding="utf-8")

            _overlay_structured_raw_sidecars(root, top_module=top_module)

            self.assertEqual(
                fused_link.read_text(encoding="utf-8"),
                "// fused link with sim_accel_eval_preload_target_host_views\n",
            )
            self.assertEqual(fused_comm.read_text(encoding="utf-8"), "raw-comm\n")


if __name__ == "__main__":
    unittest.main()
