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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_tlul_fifo_sync_threshold_semantics.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _comparison_payload(*, winner: str, ratio: float, bits_hit: int, steps: int) -> dict:
    threshold = {
        "kind": "toggle_bits_hit",
        "value": 24,
        "aggregation": "bitwise_or_across_trials",
    }
    measurement = {
        "bits_hit": bits_hit,
        "threshold_satisfied": True,
        "wall_time_ms": 10.0,
        "steps_executed": steps,
    }
    return {
        "schema_version": 1,
        "target": "tlul_fifo_sync",
        "campaign_threshold": threshold,
        "comparison_ready": True,
        "winner": winner,
        "speedup_ratio": ratio,
        "baseline": {
            "campaign_measurement": dict(measurement),
        },
        "hybrid": {
            "campaign_measurement": dict(measurement),
        },
    }


class AuditTlulFifoSyncThresholdSemanticsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_tlul_fifo_sync_threshold_semantics_test", MODULE_PATH)

    def test_detects_flip_when_longer_sequence_loses(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            seq1 = root / "seq1.json"
            seq10 = root / "seq10.json"
            seq101 = root / "seq101.json"
            seq1010 = root / "seq1010.json"
            seq1.write_text(json.dumps(_comparison_payload(winner="hybrid", ratio=2.64, bits_hit=24, steps=1)) + "\n")
            seq10.write_text(json.dumps(_comparison_payload(winner="hybrid", ratio=1.12, bits_hit=24, steps=2)) + "\n")
            seq101.write_text(json.dumps(_comparison_payload(winner="baseline", ratio=0.81, bits_hit=31, steps=3)) + "\n")
            seq1010.write_text(json.dumps(_comparison_payload(winner="baseline", ratio=0.55, bits_hit=31, steps=4)) + "\n")

            payload = self.module.build_audit(
                seq1_path=seq1,
                seq10_path=seq10,
                seq101_path=seq101,
                seq1010_path=seq1010,
            )

            self.assertEqual(payload["summary"]["recommended_action"], "evaluate_minimal_progress_sequence_semantics")
            self.assertEqual(
                payload["summary"]["reason"],
                "longer_sequence_flips_winner_to_baseline_while_shorter_sequence_strengthens_hybrid",
            )
            self.assertEqual(payload["summary"]["first_sequence_extension_flip"]["label"], "seq101_threshold24")
            self.assertEqual(payload["summary"]["strongest_positive_case"]["label"], "seq1_threshold24")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            seq1 = root / "seq1.json"
            seq10 = root / "seq10.json"
            seq101 = root / "seq101.json"
            seq1010 = root / "seq1010.json"
            seq1.write_text(json.dumps(_comparison_payload(winner="hybrid", ratio=2.64, bits_hit=24, steps=1)) + "\n")
            seq10.write_text(json.dumps(_comparison_payload(winner="hybrid", ratio=1.12, bits_hit=24, steps=2)) + "\n")
            seq101.write_text(json.dumps(_comparison_payload(winner="baseline", ratio=0.81, bits_hit=31, steps=3)) + "\n")
            seq1010.write_text(json.dumps(_comparison_payload(winner="baseline", ratio=0.55, bits_hit=31, steps=4)) + "\n")
            json_out = root / "audit.json"
            argv = [
                "audit_tlul_fifo_sync_threshold_semantics.py",
                "--seq1",
                str(seq1),
                "--seq10",
                str(seq10),
                "--seq101",
                str(seq101),
                "--seq1010",
                str(seq1010),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "tlul_fifo_sync_threshold_semantics_audit")
            self.assertEqual(payload["summary"]["recommended_action"], "evaluate_minimal_progress_sequence_semantics")


if __name__ == "__main__":
    unittest.main()
