#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_veer_post_family_exhaustion_axes.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignVeerPostFamilyExhaustionAxesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_veer_post_family_exhaustion_axes_test", MODULE_PATH)

    def test_prefers_xiangshan_then_openpiton_from_non_veer_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            designs_root = root / "designs"
            runners_dir = root / "runners"
            readiness_dir = root / "readiness"
            (designs_root / "XiangShan" / "src").mkdir(parents=True)
            (designs_root / "OpenPiton" / "src").mkdir(parents=True)
            (designs_root / "BlackParrot" / "src" / "bp").mkdir(parents=True)
            (designs_root / "VeeR-EL2" / "src").mkdir(parents=True)
            for tb in (
                designs_root / "XiangShan" / "src" / "xiangshan_gpu_cov_tb.sv",
                designs_root / "OpenPiton" / "src" / "openpiton_gpu_cov_tb.sv",
                designs_root / "BlackParrot" / "src" / "bp" / "blackparrot_gpu_cov_tb.sv",
                designs_root / "VeeR-EL2" / "src" / "veer_el2_gpu_cov_tb.sv",
            ):
                tb.write_text("// tb\n", encoding="utf-8")
            runners_dir.mkdir()
            (runners_dir / "run_xiangshan_gpu_toggle_validation.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            (runners_dir / "run_openpiton_gpu_toggle_validation.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            readiness_dir.mkdir()
            (readiness_dir / "xiangshan_gpu_toggle_readiness.md").write_text(
                "status: actual_gpu_validated\n",
                encoding="utf-8",
            )
            (readiness_dir / "blackparrot_gpu_toggle_readiness.md").write_text(
                "status: actual_gpu_validated\n",
                encoding="utf-8",
            )

            payload = self.module.build_axes(
                veer_final_same_family_acceptance_payload={
                    "outcome": {
                        "status": "accepted_selected_veer_final_same_family_step",
                        "selected_design": "VeeR-EL2",
                    }
                },
                designs_root=designs_root,
                runners_dir=runners_dir,
                readiness_dir=readiness_dir,
            )

            self.assertEqual(payload["decision"]["status"], "decide_open_next_non_veer_family_after_veer_exhaustion")
            self.assertEqual(payload["decision"]["recommended_family"], "XiangShan")
            self.assertEqual(payload["decision"]["fallback_family"], "OpenPiton")


if __name__ == "__main__":
    unittest.main()
