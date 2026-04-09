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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_third_surface_candidates.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignThirdSurfaceCandidatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_third_surface_candidates_test", MODULE_PATH)

    def test_build_candidate_audit_prefers_reference_surface_over_build_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            loopback_validation = root / "loopback_validation.json"
            loopback_validation.write_text(
                json.dumps(
                    {
                        "promotion_assessment": {
                            "decision": "freeze_at_phase_b_reference_design",
                            "reason": "gpu replay did not advance progress under current ownership",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            err_watch = root / "err_watch.json"
            err_watch.write_text(json.dumps({"changed_watch_field_count": 0}) + "\n", encoding="utf-8")

            ready_scoreboard = {
                "rows": [
                    {
                        "slice_name": "tlul_socket_m1",
                        "tier": "Tier S",
                    },
                    {
                        "slice_name": "tlul_fifo_sync",
                        "tier": "Tier R",
                    },
                    {
                        "slice_name": "tlul_request_loopback",
                        "tier": "Tier R",
                        "validation": {"path": str(loopback_validation)},
                        "comparison": {"path": str(root / "missing_comparison.json")},
                    },
                    {
                        "slice_name": "tlul_err",
                        "tier": "Tier B",
                        "watch_summary_path": str(err_watch),
                        "comparison": {"path": str(root / "missing_err_comparison.json")},
                    },
                ]
            }
            active_scoreboard = {
                "selected_profile_name": "per_target_ready",
                "rows": [
                    {"target": "tlul_socket_m1"},
                    {"target": "tlul_fifo_sync"},
                ],
            }

            payload = self.module.build_candidate_audit(
                ready_scoreboard=ready_scoreboard,
                active_scoreboard=active_scoreboard,
            )

            self.assertEqual(payload["scope"], "campaign_third_surface_candidates")
            self.assertEqual(payload["summary"]["recommended_next_target"], "tlul_request_loopback")
            self.assertEqual(payload["rows"][0]["candidate_state"], "frozen_reference_surface")
            self.assertEqual(payload["rows"][1]["target"], "tlul_err")

    def test_build_candidate_audit_prefers_ready_hybrid_win_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            loopback_validation = root / "loopback_validation.json"
            loopback_validation.write_text(
                json.dumps(
                    {
                        "promotion_assessment": {
                            "decision": "freeze_at_phase_b_reference_design",
                            "reason": "gpu replay did not advance progress under current ownership",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            loopback_comparison = root / "loopback_comparison.json"
            loopback_comparison.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "target": "tlul_request_loopback",
                        "comparison_ready": True,
                        "winner": "hybrid",
                        "speedup_ratio": 4.8,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            ready_scoreboard = {
                "rows": [
                    {
                        "slice_name": "tlul_request_loopback",
                        "tier": "Tier R",
                        "validation": {"path": str(loopback_validation)},
                        "comparison": {"path": str(loopback_comparison)},
                    }
                ]
            }
            active_scoreboard = {
                "selected_profile_name": "per_target_ready",
                "rows": [
                    {"target": "tlul_socket_m1"},
                    {"target": "tlul_fifo_sync"},
                ],
            }

            payload = self.module.build_candidate_audit(
                ready_scoreboard=ready_scoreboard,
                active_scoreboard=active_scoreboard,
            )

            self.assertEqual(payload["summary"]["recommended_next_target"], "tlul_request_loopback")
            self.assertEqual(payload["rows"][0]["candidate_state"], "comparison_ready_frozen_reference_surface")
            self.assertEqual(payload["rows"][0]["comparison_winner"], "hybrid")
            self.assertEqual(payload["rows"][0]["comparison_speedup_ratio"], 4.8)

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ready_path = root / "ready.json"
            active_path = root / "active.json"
            ready_path.write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "slice_name": "tlul_fifo_async",
                                "tier": "Tier T",
                                "comparison": {"path": str(root / "missing.json")},
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            active_path.write_text(
                json.dumps({"selected_profile_name": "per_target_ready", "rows": []}) + "\n",
                encoding="utf-8",
            )
            json_out = root / "candidates.json"

            argv = [
                "audit_campaign_third_surface_candidates.py",
                "--ready-scoreboard-json",
                str(ready_path),
                "--active-scoreboard-json",
                str(active_path),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_third_surface_candidates")
            self.assertEqual(payload["summary"]["recommended_next_target"], "tlul_fifo_async")


if __name__ == "__main__":
    unittest.main()
