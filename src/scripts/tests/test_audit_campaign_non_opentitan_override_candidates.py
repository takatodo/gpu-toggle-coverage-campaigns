#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_non_opentitan_override_candidates.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignNonOpentitanOverrideCandidatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module(
            "audit_campaign_non_opentitan_override_candidates_test",
            MODULE_PATH,
        )

    def test_recommends_smallest_ready_bootstrap_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            e902 = root / "e902.json"
            e906 = root / "e906.json"
            e902.write_text(
                json.dumps(
                    {
                        "design": "XuanTie-E902",
                        "config": "gpu_cov_gate",
                        "status": "ok",
                        "returncode": 0,
                        "verilog_source_count": 126,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            e906.write_text(
                json.dumps(
                    {
                        "design": "XuanTie-E906",
                        "config": "gpu_cov_gate",
                        "status": "ok",
                        "returncode": 0,
                        "verilog_source_count": 252,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            validation_dir = root / "validation"
            validation_dir.mkdir()

            payload = self.module.build_override_candidates(
                readiness_payload={
                    "recommended_family": "XuanTie",
                    "recommended_entry_mode": "family_pilot",
                    "decision": {
                        "readiness": "legacy_family_pilot_failed_but_single_surface_override_ready",
                    },
                    "single_surface_bootstrap_summary": {
                        "candidates": [
                            {
                                "design": "XuanTie-E906",
                                "config": "gpu_cov_gate",
                                "path": str(e906),
                                "ready": True,
                                "status": "ok",
                                "returncode": 0,
                            },
                            {
                                "design": "XuanTie-E902",
                                "config": "gpu_cov_gate",
                                "path": str(e902),
                                "ready": True,
                                "status": "ok",
                                "returncode": 0,
                            },
                        ]
                    },
                },
                validation_dir=validation_dir,
            )

            self.assertEqual(
                payload["decision"]["status"],
                "recommend_single_surface_override_candidate",
            )
            self.assertEqual(payload["decision"]["recommended_design"], "XuanTie-E902")
            self.assertEqual(payload["decision"]["fallback_design"], "XuanTie-E906")

    def test_requires_override_ready_state(self) -> None:
        payload = self.module.build_override_candidates(
            readiness_payload={
                "recommended_family": "XuanTie",
                "recommended_entry_mode": "family_pilot",
                "decision": {"readiness": "legacy_family_pilot_failed"},
                "single_surface_bootstrap_summary": {"candidates": []},
            },
            validation_dir=Path("/tmp/nonexistent"),
        )

        self.assertEqual(payload["decision"]["status"], "override_not_currently_recommended")

    def test_prefers_checked_in_trio_candidate_over_bootstrap_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            validation_dir = root / "validation"
            validation_dir.mkdir()
            e902 = root / "e902.json"
            e906 = root / "e906.json"
            e902.write_text(
                json.dumps(
                    {
                        "design": "XuanTie-E902",
                        "config": "gpu_cov_gate",
                        "status": "ok",
                        "returncode": 0,
                        "verilog_source_count": 126,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            e906.write_text(
                json.dumps(
                    {
                        "design": "XuanTie-E906",
                        "config": "gpu_cov_gate",
                        "status": "ok",
                        "returncode": 0,
                        "verilog_source_count": 100,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (validation_dir / "xuantie_e902_stock_hybrid_validation.json").write_text(
                json.dumps({"status": "ok"}) + "\n",
                encoding="utf-8",
            )
            (validation_dir / "xuantie_e902_cpu_baseline_validation.json").write_text(
                json.dumps({"status": "ok"}) + "\n",
                encoding="utf-8",
            )
            (validation_dir / "xuantie_e902_time_to_threshold_comparison.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "comparison_ready": True,
                        "winner": "hybrid",
                        "speedup_ratio": 16.7,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_override_candidates(
                readiness_payload={
                    "recommended_family": "XuanTie",
                    "recommended_entry_mode": "family_pilot",
                    "decision": {
                        "readiness": "legacy_family_pilot_failed_but_single_surface_override_ready",
                    },
                    "single_surface_bootstrap_summary": {
                        "candidates": [
                            {
                                "design": "XuanTie-E906",
                                "config": "gpu_cov_gate",
                                "path": str(e906),
                                "ready": True,
                                "status": "ok",
                                "returncode": 0,
                            },
                            {
                                "design": "XuanTie-E902",
                                "config": "gpu_cov_gate",
                                "path": str(e902),
                                "ready": True,
                                "status": "ok",
                                "returncode": 0,
                            },
                        ]
                    },
                },
                validation_dir=validation_dir,
            )

            self.assertEqual(payload["decision"]["status"], "recommend_validated_single_surface_candidate")
            self.assertEqual(payload["decision"]["recommended_design"], "XuanTie-E902")
            self.assertTrue(payload["ranked_candidates"][0]["hybrid_wins"])

    def test_surfaces_threshold_candidate_variants_for_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            validation_dir = root / "validation"
            validation_dir.mkdir()
            e902 = root / "e902.json"
            e906 = root / "e906.json"
            e902.write_text(
                json.dumps(
                    {
                        "design": "XuanTie-E902",
                        "config": "gpu_cov_gate",
                        "status": "ok",
                        "returncode": 0,
                        "verilog_source_count": 126,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            e906.write_text(
                json.dumps(
                    {
                        "design": "XuanTie-E906",
                        "config": "gpu_cov_gate",
                        "status": "ok",
                        "returncode": 0,
                        "verilog_source_count": 252,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (validation_dir / "xuantie_e902_stock_hybrid_validation.json").write_text(
                json.dumps({"status": "ok"}) + "\n",
                encoding="utf-8",
            )
            (validation_dir / "xuantie_e902_cpu_baseline_validation.json").write_text(
                json.dumps({"status": "ok"}) + "\n",
                encoding="utf-8",
            )
            (validation_dir / "xuantie_e902_time_to_threshold_comparison.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "comparison_ready": True,
                        "winner": "hybrid",
                        "speedup_ratio": 16.7,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (validation_dir / "xuantie_e906_time_to_threshold_comparison_threshold2.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "comparison_ready": True,
                        "winner": "hybrid",
                        "speedup_ratio": 30.3,
                        "campaign_threshold": {
                            "kind": "toggle_bits_hit",
                            "aggregation": "bitwise_or_across_trials",
                            "value": 2,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_override_candidates(
                readiness_payload={
                    "recommended_family": "XuanTie",
                    "recommended_entry_mode": "family_pilot",
                    "decision": {
                        "readiness": "legacy_family_pilot_failed_but_single_surface_override_ready",
                    },
                    "single_surface_bootstrap_summary": {
                        "candidates": [
                            {
                                "design": "XuanTie-E906",
                                "config": "gpu_cov_gate",
                                "path": str(e906),
                                "ready": True,
                                "status": "ok",
                                "returncode": 0,
                            },
                            {
                                "design": "XuanTie-E902",
                                "config": "gpu_cov_gate",
                                "path": str(e902),
                                "ready": True,
                                "status": "ok",
                                "returncode": 0,
                            },
                        ]
                    },
                },
                validation_dir=validation_dir,
            )

            fallback = payload["ranked_candidates"][1]
            self.assertEqual(fallback["design"], "XuanTie-E906")
            self.assertTrue(fallback["best_candidate_hybrid_wins"])
            self.assertTrue(fallback["best_candidate_comparison_ready"])
            self.assertEqual(fallback["best_candidate_threshold_value"], 2)
            self.assertEqual(fallback["candidate_variant_count"], 1)


if __name__ == "__main__":
    unittest.main()
