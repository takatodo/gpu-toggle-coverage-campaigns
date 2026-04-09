#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_xuantie_e906_case_variants.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditXuanTieE906CaseVariantsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_xuantie_e906_case_variants_test", MODULE_PATH)

    def _write_validation(
        self,
        path: Path,
        *,
        bits_hit: int,
        threshold_value: int = 8,
        status: str = "ok",
    ) -> None:
        path.write_text(
            json.dumps(
                {
                    "status": status,
                    "campaign_threshold": {
                        "kind": "toggle_bits_hit",
                        "aggregation": "bitwise_or_across_trials",
                        "value": threshold_value,
                    },
                    "campaign_measurement": {
                        "bits_hit": bits_hit,
                        "threshold_satisfied": bits_hit >= threshold_value,
                    },
                    "inputs": {
                        "case_pat": f"/tmp/{path.stem}.pat",
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_detects_plateau_across_known_case_pats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            validation_dir = Path(tmpdir)
            for stem in (
                "xuantie_e906_stock_hybrid_validation",
                "xuantie_e906_cpu_baseline_validation",
                "xuantie_e906_stock_hybrid_validation_hello",
                "xuantie_e906_cpu_baseline_validation_hello",
                "xuantie_e906_stock_hybrid_validation_memcpy",
                "xuantie_e906_cpu_baseline_validation_memcpy",
            ):
                self._write_validation(validation_dir / f"{stem}.json", bits_hit=2)
            (validation_dir / "xuantie_e906_time_to_threshold_comparison_threshold2.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "comparison_ready": True,
                        "winner": "hybrid",
                        "speedup_ratio": 30.3,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_case_variants(validation_dir=validation_dir)

            self.assertEqual(payload["decision"]["status"], "default_gate_blocked_across_known_case_pats")
            self.assertEqual(payload["summary"]["max_stock_hybrid_bits_hit"], 2)
            self.assertEqual(payload["summary"]["max_cpu_baseline_bits_hit"], 2)
            self.assertTrue(payload["threshold2_candidate"]["comparison_ready"])
            self.assertEqual(payload["threshold2_candidate"]["winner"], "hybrid")


if __name__ == "__main__":
    unittest.main()
