#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_xuantie_e906_threshold_options.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditXuantieE906ThresholdOptionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_xuantie_e906_threshold_options_test", MODULE_PATH)

    def test_reports_threshold2_as_strongest_ready_numeric_gate(self) -> None:
        payload = self.module.build_threshold_options(
            case_variants_payload={
                "summary": {
                    "default_threshold_values": [8],
                    "case_count": 3,
                    "max_stock_hybrid_bits_hit": 2,
                    "all_default_blocked": True,
                },
                "threshold2_candidate": {
                    "comparison_ready": True,
                    "winner": "hybrid",
                    "speedup_ratio": 30.3,
                    "comparison_path": "/tmp/e906_threshold2.json",
                },
            }
        )

        self.assertEqual(payload["decision"]["status"], "threshold2_is_strongest_ready_numeric_gate")
        self.assertEqual(payload["strongest_ready_numeric_gate"]["threshold_value"], 2)
        self.assertEqual(payload["blocked_numeric_thresholds"], [3, 4, 5, 6, 7, 8])


if __name__ == "__main__":
    unittest.main()
