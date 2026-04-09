#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_post_openpiton_axes.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignPostOpenPitonAxesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_post_openpiton_axes_test", MODULE_PATH)

    def test_prefers_blackparrot_and_uses_xiangshan_as_blocked_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            designs_root = root / "designs"
            runners_dir = root / "runners"
            readiness_dir = root / "readiness"

            for family, rel in (
                ("BlackParrot", "src/bp/blackparrot_gpu_cov_tb.sv"),
                ("XiangShan", "src/xiangshan_gpu_cov_tb.sv"),
                ("OpenPiton", "src/openpiton_gpu_cov_tb.sv"),
                ("Caliptra", "src/caliptra_gpu_cov_tb.sv"),
            ):
                path = designs_root / family / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("// tb\n", encoding="utf-8")

            runners_dir.mkdir()
            (runners_dir / "run_xiangshan_stock_hybrid_validation.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            (runners_dir / "run_xiangshan_cpu_baseline_validation.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            (runners_dir / "run_xiangshan_time_to_threshold_comparison.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")

            readiness_dir.mkdir()
            (readiness_dir / "blackparrot_gpu_toggle_readiness.md").write_text("status: actual_gpu_validated\n", encoding="utf-8")
            (readiness_dir / "xiangshan_gpu_toggle_readiness.md").write_text("status: actual_gpu_validated\n", encoding="utf-8")
            (readiness_dir / "caliptra_gpu_toggle_readiness.md").write_text("status: ready_for_gpu_toggle\n", encoding="utf-8")

            payload = self.module.build_axes(
                openpiton_acceptance_payload={
                    "outcome": {
                        "status": "accepted_selected_openpiton_first_surface_step",
                        "selected_family": "OpenPiton",
                    }
                },
                xiangshan_status_payload={
                    "outcome": {
                        "status": "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family",
                        "next_action": "offline_xiangshan_cubin_first_debug",
                    }
                },
                designs_root=designs_root,
                runners_dir=runners_dir,
                readiness_dir=readiness_dir,
            )

            self.assertEqual(payload["decision"]["status"], "decide_open_next_family_after_openpiton_acceptance")
            self.assertEqual(payload["decision"]["recommended_family"], "BlackParrot")
            self.assertEqual(payload["decision"]["fallback_family"], "XiangShan")


if __name__ == "__main__":
    unittest.main()
