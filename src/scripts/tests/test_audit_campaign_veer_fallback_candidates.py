#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_veer_fallback_candidates.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignVeerFallbackCandidatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_veer_fallback_candidates_test", MODULE_PATH)

    def test_recommends_smallest_bootstrap_ready_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            designs_root = root / "designs"
            runners_dir = root / "runners"
            runners_dir.mkdir(parents=True)
            (runners_dir / "run_veer_family_gpu_toggle_validation.py").write_text("", encoding="utf-8")

            for design, lines in [("VeeR-EL2", 300), ("VeeR-EH1", 200), ("VeeR-EH2", 250)]:
                stem = design.lower().replace("-", "_")
                tb = designs_root / design / "src" / f"{stem}_gpu_cov_tb.sv"
                tb.parent.mkdir(parents=True, exist_ok=True)
                tb.write_text("\n".join(["module demo;"] * lines) + "\n", encoding="utf-8")

            payload = self.module.build_candidates(
                bootstrap_payloads=[
                    {"design": "VeeR-EL2", "status": "ok", "verilog_source_count": 53, "verilog_include_count": 8},
                    {"design": "VeeR-EH1", "status": "ok", "verilog_source_count": 45, "verilog_include_count": 6},
                    {"design": "VeeR-EH2", "status": "ok", "verilog_source_count": 51, "verilog_include_count": 6},
                ],
                designs_root=designs_root,
                runners_dir=runners_dir,
            )

            self.assertEqual(
                payload["decision"]["status"],
                "recommend_first_veer_single_surface_candidate",
            )
            self.assertEqual(payload["decision"]["recommended_first_design"], "VeeR-EH1")
            self.assertEqual(payload["decision"]["fallback_design"], "VeeR-EH2")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            designs_root = root / "designs"
            runners_dir = root / "runners"
            runners_dir.mkdir(parents=True)
            (runners_dir / "run_veer_family_gpu_toggle_validation.py").write_text("", encoding="utf-8")
            tb = designs_root / "VeeR-EH1" / "src" / "veer_eh1_gpu_cov_tb.sv"
            tb.parent.mkdir(parents=True, exist_ok=True)
            tb.write_text("module demo;\nendmodule\n", encoding="utf-8")
            bootstrap_json = root / "veer.json"
            bootstrap_json.write_text(
                json.dumps(
                    {
                        "design": "VeeR-EH1",
                        "status": "ok",
                        "verilog_source_count": 45,
                        "verilog_include_count": 6,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            json_out = root / "candidates.json"

            argv = [
                "audit_campaign_veer_fallback_candidates.py",
                "--bootstrap-json",
                str(bootstrap_json),
                "--designs-root",
                str(designs_root),
                "--runners-dir",
                str(runners_dir),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_veer_fallback_candidates")
            self.assertEqual(payload["decision"]["recommended_first_design"], "VeeR-EH1")


if __name__ == "__main__":
    unittest.main()
