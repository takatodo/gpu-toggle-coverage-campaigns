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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_vortex_first_surface_profiles.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignVortexFirstSurfaceProfilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_vortex_first_surface_profiles_test", MODULE_PATH)

    def test_prefers_debug_profile_when_vortex_is_the_active_blocked_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir(parents=True)
            (profiles_dir / "hold_vortex_first_surface_branch.json").write_text(
                json.dumps({"name": "hold_vortex_first_surface_branch", "branch_mode": "hold_vortex_first_surface_branch"})
                + "\n",
                encoding="utf-8",
            )
            (profiles_dir / "debug_vortex_tls_lowering.json").write_text(
                json.dumps({"name": "debug_vortex_tls_lowering", "branch_mode": "debug_vortex_tls_lowering"})
                + "\n",
                encoding="utf-8",
            )
            (profiles_dir / "reopen_xiangshan_fallback_family.json").write_text(
                json.dumps({"name": "reopen_xiangshan_fallback_family", "branch_mode": "reopen_xiangshan_fallback_family"})
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_profiles_matrix(
                vortex_status_payload={
                    "outcome": {"status": "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback"},
                    "gpu_build": {"status": "llc_tls_global_blocked"},
                },
                post_blackparrot_axes_payload={
                    "decision": {
                        "status": "decide_open_next_family_after_blackparrot_baseline_loss",
                        "recommended_family": "Vortex",
                        "fallback_family": "XiangShan",
                    }
                },
                xiangshan_status_payload={
                    "outcome": {"status": "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family"}
                },
                debug_tactics_payload=None,
                profiles_dir=profiles_dir,
                current_selection_payload={"profile_name": "hold_vortex_first_surface_branch"},
                current_selection_path=root / "selection.json",
            )

            self.assertEqual(payload["summary"]["recommended_profile_name"], "debug_vortex_tls_lowering")
            self.assertIn("reopen_xiangshan_fallback_family", payload["summary"]["ready_profiles"])
            self.assertIn("hold_vortex_first_surface_branch", payload["summary"]["hold_profiles"])

    def test_prefers_xiangshan_reopen_when_debug_tactics_recommend_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir(parents=True)
            (profiles_dir / "debug_vortex_tls_lowering.json").write_text(
                json.dumps({"name": "debug_vortex_tls_lowering", "branch_mode": "debug_vortex_tls_lowering"})
                + "\n",
                encoding="utf-8",
            )
            (profiles_dir / "reopen_xiangshan_fallback_family.json").write_text(
                json.dumps({"name": "reopen_xiangshan_fallback_family", "branch_mode": "reopen_xiangshan_fallback_family"})
                + "\n",
                encoding="utf-8",
            )

            payload = self.module.build_profiles_matrix(
                vortex_status_payload={
                    "outcome": {"status": "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback"},
                    "gpu_build": {"status": "llc_tls_global_blocked"},
                },
                post_blackparrot_axes_payload={
                    "decision": {
                        "status": "decide_open_next_family_after_blackparrot_baseline_loss",
                        "recommended_family": "Vortex",
                        "fallback_family": "XiangShan",
                    }
                },
                xiangshan_status_payload={
                    "outcome": {"status": "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family"}
                },
                debug_tactics_payload={
                    "decision": {"recommended_next_tactic": "reopen_xiangshan_fallback_family"}
                },
                profiles_dir=profiles_dir,
                current_selection_payload={"profile_name": "debug_vortex_tls_lowering"},
                current_selection_path=root / "selection.json",
            )

            self.assertEqual(payload["summary"]["recommended_profile_name"], "reopen_xiangshan_fallback_family")
            self.assertEqual(
                payload["summary"]["debug_tactic_recommended_next_tactic"],
                "reopen_xiangshan_fallback_family",
            )

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir(parents=True)
            (profiles_dir / "hold_vortex_first_surface_branch.json").write_text(
                json.dumps({"name": "hold_vortex_first_surface_branch", "branch_mode": "hold_vortex_first_surface_branch"})
                + "\n",
                encoding="utf-8",
            )
            selection_json = root / "selection.json"
            selection_json.write_text(
                json.dumps({"profile_name": "hold_vortex_first_surface_branch"}) + "\n",
                encoding="utf-8",
            )
            vortex_json = root / "vortex.json"
            vortex_json.write_text(
                json.dumps({"outcome": {"status": "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback"}})
                + "\n",
                encoding="utf-8",
            )
            axes_json = root / "axes.json"
            axes_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "status": "decide_open_next_family_after_blackparrot_baseline_loss",
                            "recommended_family": "Vortex",
                            "fallback_family": "XiangShan",
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            xiangshan_json = root / "xiangshan.json"
            xiangshan_json.write_text(
                json.dumps({"outcome": {"status": "decide_xiangshan_cubin_first_debug_vs_open_openpiton_fallback_family"}})
                + "\n",
                encoding="utf-8",
            )
            debug_tactics_json = root / "debug_tactics.json"
            debug_tactics_json.write_text(
                json.dumps({"decision": {"recommended_next_tactic": "reopen_xiangshan_fallback_family"}})
                + "\n",
                encoding="utf-8",
            )
            json_out = root / "profiles.json"
            argv = [
                "audit_campaign_vortex_first_surface_profiles.py",
                "--vortex-status-json",
                str(vortex_json),
                "--post-blackparrot-axes-json",
                str(axes_json),
                "--xiangshan-status-json",
                str(xiangshan_json),
                "--debug-tactics-json",
                str(debug_tactics_json),
                "--profiles-dir",
                str(profiles_dir),
                "--selection-config",
                str(selection_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_vortex_first_surface_profiles")
            self.assertEqual(payload["summary"]["vortex_status"], "decide_vortex_tls_lowering_debug_vs_reopen_xiangshan_fallback")
            self.assertEqual(
                payload["summary"]["debug_tactic_recommended_next_tactic"],
                "reopen_xiangshan_fallback_family",
            )


if __name__ == "__main__":
    unittest.main()
