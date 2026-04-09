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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_post_checkpoint_axes.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignPostCheckpointAxesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_post_checkpoint_axes_test", MODULE_PATH)

    def test_recommends_non_opentitan_family_breadth_with_xuantie_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            designs_root = root / "designs"
            runners_dir = root / "runners"
            (designs_root / "OpenTitan" / "src").mkdir(parents=True)
            (designs_root / "XuanTie-C906" / "src").mkdir(parents=True)
            (designs_root / "XuanTie-C910" / "src").mkdir(parents=True)
            (designs_root / "XuanTie-E902" / "src").mkdir(parents=True)
            (designs_root / "XuanTie-E906" / "src").mkdir(parents=True)
            (designs_root / "VeeR-EH1" / "src").mkdir(parents=True)
            (designs_root / "VeeR-EH2" / "src").mkdir(parents=True)
            (designs_root / "VeeR-EL2" / "src").mkdir(parents=True)
            for tb in (
                designs_root / "OpenTitan" / "src" / "tlul_socket_m1_gpu_cov_tb.sv",
                designs_root / "XuanTie-C906" / "src" / "xuantie_c906_gpu_cov_tb.sv",
                designs_root / "XuanTie-C910" / "src" / "xuantie_c910_gpu_cov_tb.sv",
                designs_root / "XuanTie-E902" / "src" / "xuantie_e902_gpu_cov_tb.sv",
                designs_root / "XuanTie-E906" / "src" / "xuantie_e906_gpu_cov_tb.sv",
                designs_root / "VeeR-EH1" / "src" / "veer_eh1_gpu_cov_tb.sv",
                designs_root / "VeeR-EH2" / "src" / "veer_eh2_gpu_cov_tb.sv",
                designs_root / "VeeR-EL2" / "src" / "veer_el2_gpu_cov_tb.sv",
            ):
                tb.write_text("// stub\n", encoding="utf-8")

            runners_dir.mkdir(parents=True)
            (runners_dir / "run_xuantie_family_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            (runners_dir / "run_veer_family_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")

            checkpoint = {
                "scope": "campaign_checkpoint_readiness",
                "summary": {
                    "active_fraction_of_ready_pool": 1.0,
                    "family_diversity_count": 2,
                },
                "decision": {
                    "readiness": "cross_family_checkpoint_ready",
                },
            }
            active_scoreboard = {
                "scope": "campaign_speed_scoreboard_active",
                "selected_profile_name": "per_target_ready",
                "selected_policy_mode": "per_target",
                "selected_scenario_name": "candidate_design_specific_minimal_progress",
                "policy_gate_status": "promote_design_specific_v2",
                "rows": [
                    {"target": "tlul_socket_m1"},
                    {"target": "tlul_fifo_sync"},
                    {"target": "xbar_main"},
                ],
            }
            active_next_kpi = {
                "scope": "campaign_next_kpi_audit",
                "decision": {
                    "recommended_next_kpi": "broader_design_count",
                },
            }

            payload = self.module.build_post_checkpoint_axes(
                checkpoint_readiness=checkpoint,
                active_scoreboard=active_scoreboard,
                active_next_kpi=active_next_kpi,
                designs_root=designs_root,
                runners_dir=runners_dir,
            )

            self.assertEqual(payload["decision"]["recommended_next_axis"], "broaden_non_opentitan_family")
            self.assertEqual(payload["decision"]["recommended_family"], "XuanTie")
            self.assertEqual(payload["current_active_line"]["repo_families"], ["OpenTitan"])
            self.assertEqual(payload["axes"][0]["top_candidate_family"], "XuanTie")

    def test_blocks_axis_change_until_active_kpi_requests_broader_design_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            designs_root = root / "designs"
            runners_dir = root / "runners"
            (designs_root / "XiangShan" / "src").mkdir(parents=True)
            (designs_root / "XiangShan" / "src" / "xiangshan_gpu_cov_tb.sv").write_text("// stub\n", encoding="utf-8")
            runners_dir.mkdir(parents=True)

            payload = self.module.build_post_checkpoint_axes(
                checkpoint_readiness={
                    "scope": "campaign_checkpoint_readiness",
                    "summary": {"active_fraction_of_ready_pool": 1.0, "family_diversity_count": 2},
                    "decision": {"readiness": "cross_family_checkpoint_ready"},
                },
                active_scoreboard={
                    "scope": "campaign_speed_scoreboard_active",
                    "rows": [{"target": "tlul_socket_m1"}],
                },
                active_next_kpi={
                    "scope": "campaign_next_kpi_audit",
                    "decision": {"recommended_next_kpi": "stronger_thresholds"},
                },
                designs_root=designs_root,
                runners_dir=runners_dir,
            )

            self.assertEqual(payload["decision"]["recommended_next_axis"], "follow_current_active_kpi")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checkpoint_path = root / "checkpoint.json"
            active_path = root / "active.json"
            next_kpi_path = root / "next_kpi.json"
            designs_root = root / "designs"
            runners_dir = root / "runners"
            json_out = root / "axes.json"
            (designs_root / "OpenPiton" / "src" / "common").mkdir(parents=True)
            (designs_root / "OpenPiton" / "src" / "common" / "openpiton_gpu_cov_tb.sv").write_text("// stub\n", encoding="utf-8")
            runners_dir.mkdir(parents=True)
            (runners_dir / "run_openpiton_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")

            checkpoint_path.write_text(
                json.dumps(
                    {
                        "scope": "campaign_checkpoint_readiness",
                        "summary": {"active_fraction_of_ready_pool": 1.0, "family_diversity_count": 2},
                        "decision": {"readiness": "cross_family_checkpoint_ready"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            active_path.write_text(
                json.dumps(
                    {
                        "scope": "campaign_speed_scoreboard_active",
                        "rows": [{"target": "tlul_socket_m1"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            next_kpi_path.write_text(
                json.dumps(
                    {
                        "scope": "campaign_next_kpi_audit",
                        "decision": {"recommended_next_kpi": "broader_design_count"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_post_checkpoint_axes.py",
                "--checkpoint-json",
                str(checkpoint_path),
                "--active-scoreboard-json",
                str(active_path),
                "--active-next-kpi-json",
                str(next_kpi_path),
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
            self.assertEqual(payload["scope"], "campaign_post_checkpoint_axes")
            self.assertEqual(payload["decision"]["recommended_next_axis"], "broaden_non_opentitan_family")


if __name__ == "__main__":
    unittest.main()
