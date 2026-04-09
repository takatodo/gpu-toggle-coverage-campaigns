#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_third_surface_preview.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _comparison_payload(*, target: str, threshold_value: int, wall_time_ms: float) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "ok",
        "target": target,
        "campaign_threshold": {
            "kind": "toggle_bits_hit",
            "value": threshold_value,
            "aggregation": "bitwise_or_across_trials",
        },
        "baseline": {
            "campaign_measurement": {
                "wall_time_ms": wall_time_ms * 4.0,
                "threshold_satisfied": True,
            }
        },
        "hybrid": {
            "campaign_measurement": {
                "wall_time_ms": wall_time_ms,
                "threshold_satisfied": True,
            }
        },
        "comparison_ready": True,
        "speedup_ratio": 4.0,
        "winner": "hybrid",
    }


class AuditCampaignThirdSurfacePreviewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_third_surface_preview_test", MODULE_PATH)

    def test_build_preview_adds_recommended_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            socket_path = root / "socket.json"
            fifo_path = root / "fifo.json"
            loopback_path = root / "loopback.json"
            socket_path.write_text(
                json.dumps(_comparison_payload(target="tlul_socket_m1", threshold_value=5, wall_time_ms=1.0)) + "\n",
                encoding="utf-8",
            )
            fifo_path.write_text(
                json.dumps(_comparison_payload(target="tlul_fifo_sync", threshold_value=24, wall_time_ms=2.0)) + "\n",
                encoding="utf-8",
            )
            loopback_path.write_text(
                json.dumps(_comparison_payload(target="tlul_request_loopback", threshold_value=2, wall_time_ms=3.0))
                + "\n",
                encoding="utf-8",
            )
            policy_gate = {
                "selection": {
                    "profile_name": "per_target_ready",
                    "require_matching_thresholds": False,
                }
            }
            active_scoreboard = {
                "selected_paths": [str(socket_path), str(fifo_path)],
            }
            candidate_audit = {
                "summary": {"recommended_next_target": "tlul_request_loopback"},
                "rows": [
                    {
                        "target": "tlul_request_loopback",
                        "candidate_state": "comparison_ready_frozen_reference_surface",
                        "next_step": "decide_whether_to_add_frozen_reference_surface_to_active_campaign_line",
                        "comparison_path": str(loopback_path),
                    }
                ],
            }

            payload = self.module.build_preview(
                policy_gate=policy_gate,
                active_scoreboard=active_scoreboard,
                candidate_audit=candidate_audit,
                minimum_ready_surfaces=2,
                minimum_strong_margin=2.0,
            )

            self.assertEqual(payload["scope"], "campaign_third_surface_preview")
            self.assertEqual(payload["candidate_target"], "tlul_request_loopback")
            self.assertEqual(len(payload["selected_paths"]), 3)
            self.assertEqual(payload["scoreboard_summary"]["comparison_ready_count"], 3)
            self.assertEqual(payload["decision"]["recommended_next_kpi"], "broader_design_count")


if __name__ == "__main__":
    unittest.main()
