#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "runners" / "run_socket_m1_time_to_threshold_comparison.py"


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
    threshold_value: int = 3,
    threshold_aggregation: str = "bitwise_or_across_trials",
    threshold_satisfied: bool = True,
    bits_hit: int = 3,
    wall_time_ms: float | None = 10.0,
    steps_executed: int = 1,
    status: str = "ok",
    target: str = "tlul_socket_m1",
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


class RunSocketM1TimeToThresholdComparisonTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("run_socket_m1_time_to_threshold_comparison_test", MODULE_PATH)

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
                _artifact(backend="stock_verilator_cpu_baseline", wall_time_ms=40.0, steps_executed=12),
            )
            self._write_artifact(
                hybrid,
                _artifact(backend="stock_verilator_hybrid", wall_time_ms=10.0, steps_executed=1),
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
            self.assertEqual(payload["target"], "tlul_socket_m1")
            self.assertTrue(payload["comparison_ready"])
            self.assertEqual(payload["winner"], "hybrid")
            self.assertEqual(payload["speedup_ratio"], 4.0)
            self.assertEqual(
                payload["campaign_threshold"],
                {
                    "kind": "toggle_bits_hit",
                    "value": 3,
                    "aggregation": "bitwise_or_across_trials",
                },
            )
            self.assertEqual(payload["baseline"]["campaign_measurement"]["steps_executed"], 12)
            self.assertEqual(payload["hybrid"]["campaign_measurement"]["steps_executed"], 1)

    def test_runner_rejects_threshold_kind_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            baseline = root / "baseline.json"
            hybrid = root / "hybrid.json"
            comparison = root / "comparison.json"
            self._write_artifact(baseline, _artifact(backend="stock_verilator_cpu_baseline"))
            self._write_artifact(
                hybrid,
                _artifact(backend="stock_verilator_hybrid", threshold_kind="coverage_ratio"),
            )

            rc = self.module.main(
                ["--baseline", str(baseline), "--hybrid", str(hybrid), "--json-out", str(comparison)]
            )

            self.assertEqual(rc, 1)
            payload = json.loads(comparison.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["winner"], "rejected")
            self.assertEqual(payload["reject_reason"], "threshold_kind_mismatch")
            self.assertFalse(payload["comparison_ready"])
            self.assertIsNone(payload["speedup_ratio"])

    def test_runner_rejects_threshold_value_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            baseline = root / "baseline.json"
            hybrid = root / "hybrid.json"
            comparison = root / "comparison.json"
            self._write_artifact(baseline, _artifact(backend="stock_verilator_cpu_baseline", threshold_value=3))
            self._write_artifact(hybrid, _artifact(backend="stock_verilator_hybrid", threshold_value=4))

            rc = self.module.main(
                ["--baseline", str(baseline), "--hybrid", str(hybrid), "--json-out", str(comparison)]
            )

            self.assertEqual(rc, 1)
            payload = json.loads(comparison.read_text(encoding="utf-8"))
            self.assertEqual(payload["reject_reason"], "threshold_value_mismatch")
            self.assertEqual(payload["winner"], "rejected")

    def test_runner_rejects_threshold_aggregation_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            baseline = root / "baseline.json"
            hybrid = root / "hybrid.json"
            comparison = root / "comparison.json"
            self._write_artifact(baseline, _artifact(backend="stock_verilator_cpu_baseline"))
            self._write_artifact(
                hybrid,
                _artifact(backend="stock_verilator_hybrid", threshold_aggregation="per_trial"),
            )

            rc = self.module.main(
                ["--baseline", str(baseline), "--hybrid", str(hybrid), "--json-out", str(comparison)]
            )

            self.assertEqual(rc, 1)
            payload = json.loads(comparison.read_text(encoding="utf-8"))
            self.assertEqual(payload["reject_reason"], "threshold_aggregation_mismatch")
            self.assertEqual(payload["winner"], "rejected")

    def test_runner_marks_unresolved_when_threshold_not_reached(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            baseline = root / "baseline.json"
            hybrid = root / "hybrid.json"
            comparison = root / "comparison.json"
            self._write_artifact(
                baseline,
                _artifact(
                    backend="stock_verilator_cpu_baseline",
                    threshold_satisfied=False,
                    bits_hit=2,
                    wall_time_ms=40.0,
                ),
            )
            self._write_artifact(
                hybrid,
                _artifact(backend="stock_verilator_hybrid", wall_time_ms=10.0),
            )

            rc = self.module.main(
                ["--baseline", str(baseline), "--hybrid", str(hybrid), "--json-out", str(comparison)]
            )

            self.assertEqual(rc, 0)
            payload = json.loads(comparison.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ok")
            self.assertFalse(payload["comparison_ready"])
            self.assertEqual(payload["winner"], "unresolved")
            self.assertIsNone(payload["speedup_ratio"])

    def test_runner_reports_baseline_win(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            baseline = root / "baseline.json"
            hybrid = root / "hybrid.json"
            comparison = root / "comparison.json"
            self._write_artifact(
                baseline,
                _artifact(backend="stock_verilator_cpu_baseline", wall_time_ms=5.0),
            )
            self._write_artifact(
                hybrid,
                _artifact(backend="stock_verilator_hybrid", wall_time_ms=10.0),
            )

            rc = self.module.main(
                ["--baseline", str(baseline), "--hybrid", str(hybrid), "--json-out", str(comparison)]
            )

            self.assertEqual(rc, 0)
            payload = json.loads(comparison.read_text(encoding="utf-8"))
            self.assertTrue(payload["comparison_ready"])
            self.assertEqual(payload["winner"], "baseline")
            self.assertEqual(payload["speedup_ratio"], 0.5)

    def test_runner_reports_tie(self) -> None:
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
                _artifact(backend="stock_verilator_hybrid", wall_time_ms=10.0),
            )

            rc = self.module.main(
                ["--baseline", str(baseline), "--hybrid", str(hybrid), "--json-out", str(comparison)]
            )

            self.assertEqual(rc, 0)
            payload = json.loads(comparison.read_text(encoding="utf-8"))
            self.assertTrue(payload["comparison_ready"])
            self.assertEqual(payload["winner"], "tie")
            self.assertEqual(payload["speedup_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
