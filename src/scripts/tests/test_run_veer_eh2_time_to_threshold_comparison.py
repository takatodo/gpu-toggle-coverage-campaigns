#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_veer_eh2_time_to_threshold_comparison.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _artifact(
    *,
    backend: str,
    threshold_value: int = 8,
    threshold_satisfied: bool = True,
    bits_hit: int = 8,
    wall_time_ms: float | None = 10.0,
    steps_executed: int = 56,
    status: str = "ok",
    target: str = "veer_eh2",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": status,
        "target": target,
        "backend": backend,
        "campaign_threshold": {
            "kind": "toggle_bits_hit",
            "value": threshold_value,
            "aggregation": "bitwise_or_across_trials",
        },
        "campaign_measurement": {
            "bits_hit": bits_hit,
            "threshold_satisfied": threshold_satisfied,
            "wall_time_ms": wall_time_ms,
            "steps_executed": steps_executed,
        },
    }


class RunVeeREH2TimeToThresholdComparisonTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_veer_eh2_time_to_threshold_comparison_test", MODULE_PATH)

    def _write_artifact(self, path: Path, payload: dict[str, object]) -> None:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def test_runner_writes_hybrid_win_comparison_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            baseline = root / "baseline.json"
            hybrid = root / "hybrid.json"
            comparison = root / "comparison.json"
            self._write_artifact(
                baseline,
                _artifact(backend="stock_verilator_cpu_baseline", wall_time_ms=10.0),
            )
            self._write_artifact(
                hybrid,
                _artifact(backend="stock_verilator_hybrid", wall_time_ms=2.0),
            )

            rc = self.module.main(
                [
                    "--baseline",
                    str(baseline),
                    "--hybrid",
                    str(hybrid),
                    "--json-out",
                    str(comparison),
                ]
            )

            self.assertEqual(rc, 0)
            payload = json.loads(comparison.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["target"], "veer_eh2")
            self.assertTrue(payload["comparison_ready"])
            self.assertEqual(payload["winner"], "hybrid")
            self.assertEqual(payload["speedup_ratio"], 5.0)


if __name__ == "__main__":
    unittest.main()
