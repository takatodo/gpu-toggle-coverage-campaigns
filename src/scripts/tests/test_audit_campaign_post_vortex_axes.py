#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_post_vortex_axes.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignPostVortexAxesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_post_vortex_axes_test", MODULE_PATH)

    def test_blocks_when_vortex_not_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = self.module.build_axes(
                vortex_acceptance_payload={"outcome": {"status": "hold_selected_vortex_first_surface_step"}},
                designs_root=root,
                runners_dir=root,
                readiness_dir=root,
            )

            self.assertEqual(payload["decision"]["status"], "blocked_vortex_not_yet_accepted")

    def test_recommends_first_remaining_family_after_vortex_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            designs_root = root / "designs"
            runners_dir = root / "runners"
            readiness_dir = root / "readiness"
            (designs_root / "Caliptra" / "src").mkdir(parents=True)
            (designs_root / "Example" / "src").mkdir(parents=True)
            (designs_root / "Caliptra" / "src" / "caliptra_gpu_cov_tb.sv").write_text("", encoding="utf-8")
            (designs_root / "Example" / "src" / "example_gpu_cov_tb.sv").write_text("", encoding="utf-8")
            runners_dir.mkdir()
            readiness_dir.mkdir()

            payload = self.module.build_axes(
                vortex_acceptance_payload={"outcome": {"status": "accepted_selected_vortex_first_surface_step"}},
                designs_root=designs_root,
                runners_dir=runners_dir,
                readiness_dir=readiness_dir,
            )

            self.assertEqual(payload["decision"]["status"], "decide_open_next_family_after_vortex_acceptance")
            self.assertEqual(payload["decision"]["recommended_family"], "Caliptra")
            self.assertEqual(payload["decision"]["fallback_family"], "Example")


if __name__ == "__main__":
    unittest.main()
