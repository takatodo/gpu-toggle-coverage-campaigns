#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_xbar_peri_time_to_threshold_comparison.py"


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
    threshold_kind: str = "toggle_bits_hit",
    threshold_value: int = 47,
    threshold_aggregation: str = "bitwise_or_across_trials",
    threshold_satisfied: bool = True,
    bits_hit: int = 47,
    wall_time_ms: float | None = 10.0,
    steps_executed: int = 56,
    status: str = "ok",
    target: str = "xbar_peri",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": status,
        "target": target,
        "backend": backend,
        "campaign_threshold": {
            "kind": threshold_kind,
            "value": threshold_value,
            "aggregation": threshold_aggregation,
        },
        "campaign_measurement": {
            "bits_hit": bits_hit,
            "threshold_satisfied": threshold_satisfied,
            "wall_time_ms": wall_time_ms,
            "steps_executed": steps_executed,
        },
    }


class RunXbarPeriTimeToThresholdComparisonTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_xbar_peri_time_to_threshold_comparison_test", MODULE_PATH)

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
                _artifact(backend="stock_verilator_cpu_baseline", wall_time_ms=20.0),
            )
            self._write_artifact(
                hybrid,
                _artifact(backend="stock_verilator_hybrid", wall_time_ms=4.0),
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
            self.assertEqual(payload["target"], "xbar_peri")
            self.assertTrue(payload["comparison_ready"])
            self.assertEqual(payload["winner"], "hybrid")
            self.assertEqual(payload["speedup_ratio"], 5.0)


if __name__ == "__main__":
    unittest.main()
