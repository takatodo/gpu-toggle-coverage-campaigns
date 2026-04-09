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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_non_opentitan_breadth_branch_candidates.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignNonOpentitanBreadthBranchCandidatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module(
            "audit_campaign_non_opentitan_breadth_branch_candidates_test",
            MODULE_PATH,
        )

    def test_recommends_same_family_first_with_c906_as_first_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            designs_root = root / "designs"
            runners_dir = root / "runners"
            validation_dir = root / "validation"
            for design, lines in (
                ("XuanTie-C906", 10),
                ("XuanTie-C910", 20),
                ("VeeR-EL2", 5),
                ("VeeR-EH1", 5),
            ):
                tb_dir = designs_root / design / "src"
                tb_dir.mkdir(parents=True)
                stem = design.lower().replace("-", "_")
                (tb_dir / f"{stem}_gpu_cov_tb.sv").write_text("//\n" * lines, encoding="utf-8")

            runners_dir.mkdir(parents=True)
            (runners_dir / "run_xuantie_family_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            (runners_dir / "run_xuantie_c906_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            (runners_dir / "run_xuantie_c910_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            (runners_dir / "run_veer_family_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            validation_dir.mkdir(parents=True)

            payload = self.module.build_branch_candidates(
                breadth_axes_payload={
                    "accepted_baseline": {
                        "selected_seed_design": "XuanTie-E902",
                        "selected_breadth_design": "XuanTie-E906",
                        "selected_breadth_profile_name": "e906_candidate_only_threshold2",
                    },
                    "recommended_family_axis": {
                        "recommended_family": "XuanTie",
                        "fallback_family": "VeeR",
                        "remaining_same_family_designs": ["XuanTie-C906", "XuanTie-C910"],
                    },
                },
                breadth_profiles_payload={
                    "summary": {
                        "current_profile_name": "hold_post_e906_branch",
                        "ready_profile_names": [
                            "open_veer_fallback_family",
                            "xuantie_continue_same_family",
                        ],
                    }
                },
                designs_root=designs_root,
                runners_dir=runners_dir,
                validation_dir=validation_dir,
            )

            self.assertEqual(payload["decision"]["status"], "recommend_same_family_first")
            self.assertEqual(payload["decision"]["recommended_profile_name"], "xuantie_continue_same_family")
            self.assertEqual(payload["decision"]["recommended_first_design"], "XuanTie-C906")

    def test_recommends_fallback_family_if_same_family_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            designs_root = root / "designs"
            runners_dir = root / "runners"
            validation_dir = root / "validation"
            for design in ("VeeR-EL2", "VeeR-EH1", "VeeR-EH2"):
                (designs_root / design / "src").mkdir(parents=True)

            runners_dir.mkdir(parents=True)
            (runners_dir / "run_veer_family_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            validation_dir.mkdir(parents=True)

            payload = self.module.build_branch_candidates(
                breadth_axes_payload={
                    "accepted_baseline": {},
                    "recommended_family_axis": {
                        "recommended_family": "XuanTie",
                        "fallback_family": "VeeR",
                        "remaining_same_family_designs": ["XuanTie-C906", "XuanTie-C910"],
                    },
                },
                breadth_profiles_payload={
                    "summary": {
                        "current_profile_name": "hold_post_e906_branch",
                        "ready_profile_names": [
                            "open_veer_fallback_family",
                            "xuantie_continue_same_family",
                        ],
                    }
                },
                designs_root=designs_root,
                runners_dir=runners_dir,
                validation_dir=validation_dir,
            )

            self.assertEqual(payload["decision"]["status"], "recommend_fallback_family_first")
            self.assertEqual(payload["decision"]["recommended_profile_name"], "open_veer_fallback_family")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            axes_path = root / "axes.json"
            profiles_path = root / "profiles.json"
            designs_root = root / "designs"
            runners_dir = root / "runners"
            validation_dir = root / "validation"
            json_out = root / "branch.json"

            (designs_root / "XuanTie-C906" / "src").mkdir(parents=True)
            (designs_root / "XuanTie-C906" / "src" / "xuantie_c906_gpu_cov_tb.sv").write_text("// stub\n", encoding="utf-8")
            runners_dir.mkdir(parents=True)
            (runners_dir / "run_xuantie_c906_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            (runners_dir / "run_xuantie_family_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            validation_dir.mkdir(parents=True)

            axes_path.write_text(
                json.dumps(
                    {
                        "accepted_baseline": {
                            "selected_seed_design": "XuanTie-E902",
                            "selected_breadth_design": "XuanTie-E906",
                            "selected_breadth_profile_name": "e906_candidate_only_threshold2",
                        },
                        "recommended_family_axis": {
                            "recommended_family": "XuanTie",
                            "fallback_family": "VeeR",
                            "remaining_same_family_designs": ["XuanTie-C906"],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            profiles_path.write_text(
                json.dumps(
                    {
                        "summary": {
                            "current_profile_name": "hold_post_e906_branch",
                            "ready_profile_names": ["xuantie_continue_same_family"],
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_non_opentitan_breadth_branch_candidates.py",
                "--breadth-axes-json",
                str(axes_path),
                "--breadth-profiles-json",
                str(profiles_path),
                "--designs-root",
                str(designs_root),
                "--runners-dir",
                str(runners_dir),
                "--validation-dir",
                str(validation_dir),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_non_opentitan_breadth_branch_candidates")
            self.assertEqual(payload["decision"]["recommended_profile_name"], "xuantie_continue_same_family")

    def test_prefers_same_family_design_with_real_candidate_only_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            designs_root = root / "designs"
            runners_dir = root / "runners"
            validation_dir = root / "validation"
            validation_dir.mkdir(parents=True)

            for design, lines in (("XuanTie-C906", 30), ("XuanTie-C910", 10), ("VeeR-EL2", 5)):
                tb_dir = designs_root / design / "src"
                tb_dir.mkdir(parents=True)
                stem = design.lower().replace("-", "_")
                (tb_dir / f"{stem}_gpu_cov_tb.sv").write_text("//\n" * lines, encoding="utf-8")

            runners_dir.mkdir(parents=True)
            (runners_dir / "run_xuantie_family_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            (runners_dir / "run_xuantie_c906_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            (runners_dir / "run_xuantie_c910_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            (runners_dir / "run_veer_family_gpu_toggle_validation.py").write_text("# stub\n", encoding="utf-8")
            (validation_dir / "xuantie_c906_time_to_threshold_comparison_threshold5.json").write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "comparison_ready": True,
                        "winner": "hybrid",
                        "speedup_ratio": 9.5,
                        "campaign_threshold": {"kind": "toggle_bits_hit", "value": 5},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_branch_candidates(
                breadth_axes_payload={
                    "accepted_baseline": {
                        "selected_seed_design": "XuanTie-E902",
                        "selected_breadth_design": "XuanTie-E906",
                        "selected_breadth_profile_name": "e906_candidate_only_threshold2",
                    },
                    "recommended_family_axis": {
                        "recommended_family": "XuanTie",
                        "fallback_family": "VeeR",
                        "remaining_same_family_designs": ["XuanTie-C906", "XuanTie-C910"],
                    },
                },
                breadth_profiles_payload={
                    "summary": {
                        "current_profile_name": "hold_post_e906_branch",
                        "ready_profile_names": [
                            "open_veer_fallback_family",
                            "xuantie_continue_same_family",
                        ],
                    }
                },
                designs_root=designs_root,
                runners_dir=runners_dir,
                validation_dir=validation_dir,
            )

            same_family = next(
                row for row in payload["branch_candidates"] if row["profile_name"] == "xuantie_continue_same_family"
            )
            self.assertEqual(same_family["status"], "same_family_validated_candidate_ready")
            self.assertEqual(same_family["recommended_first_design"], "XuanTie-C906")
            self.assertEqual(same_family["recommended_first_design_reason"], "candidate_only_hybrid_win_already_exists")
            self.assertEqual(payload["decision"]["status"], "recommend_same_family_first")


if __name__ == "__main__":
    unittest.main()
