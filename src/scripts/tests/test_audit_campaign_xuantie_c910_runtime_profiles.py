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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xuantie_c910_runtime_profiles.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXuantieC910RuntimeProfilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xuantie_c910_runtime_profiles_test", MODULE_PATH)

    def test_prefers_debug_profile_when_runtime_is_killed_and_no_tactic_override_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir(parents=True)
            (profiles_dir / "hold_c910_runtime_branch.json").write_text(
                json.dumps({"name": "hold_c910_runtime_branch", "runtime_mode": "hold_c910_runtime_branch"})
                + "\n",
                encoding="utf-8",
            )
            (profiles_dir / "debug_c910_hybrid_runtime.json").write_text(
                json.dumps({"name": "debug_c910_hybrid_runtime", "runtime_mode": "debug_c910_hybrid_runtime"})
                + "\n",
                encoding="utf-8",
            )
            (profiles_dir / "open_veer_fallback_family.json").write_text(
                json.dumps({"name": "open_veer_fallback_family", "runtime_mode": "open_fallback_family"})
                + "\n",
                encoding="utf-8",
            )
            payload = self.module.build_profiles_matrix(
                runtime_status_payload={
                    "outcome": {"status": "decide_hybrid_runtime_debug_vs_open_veer_fallback_family"},
                    "runtime_smoke": {"status": "hybrid_runtime_killed_even_at_minimal_shapes"},
                    "hybrid": {"status": "error"},
                    "cpu_baseline": {"status": "ok"},
                },
                same_family_next_axes_payload={
                    "decision": {
                        "status": "decide_continue_to_remaining_same_family_design_vs_open_fallback_family",
                        "recommended_same_family_design": "XuanTie-C910",
                    },
                    "next_family_axis": {
                        "fallback_profile_name": "open_veer_fallback_family",
                        "fallback_family": "VeeR",
                    },
                },
                debug_tactics_payload=None,
                profiles_dir=profiles_dir,
                current_selection_payload={"profile_name": "hold_c910_runtime_branch"},
                current_selection_path=root / "selection.json",
            )

            self.assertEqual(payload["summary"]["recommended_profile_name"], "debug_c910_hybrid_runtime")
            self.assertIn("open_veer_fallback_family", payload["summary"]["ready_profiles"])
            self.assertIn("hold_c910_runtime_branch", payload["summary"]["hold_profiles"])

    def test_prefers_fallback_profile_when_debug_tactics_recommend_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir(parents=True)
            (profiles_dir / "debug_c910_hybrid_runtime.json").write_text(
                json.dumps({"name": "debug_c910_hybrid_runtime", "runtime_mode": "debug_c910_hybrid_runtime"})
                + "\n",
                encoding="utf-8",
            )
            (profiles_dir / "open_veer_fallback_family.json").write_text(
                json.dumps({"name": "open_veer_fallback_family", "runtime_mode": "open_fallback_family"})
                + "\n",
                encoding="utf-8",
            )
            payload = self.module.build_profiles_matrix(
                runtime_status_payload={
                    "outcome": {"status": "decide_hybrid_runtime_debug_vs_open_veer_fallback_family"},
                    "runtime_smoke": {"status": "hybrid_runtime_killed_even_at_minimal_shapes"},
                    "hybrid": {"status": "error"},
                    "cpu_baseline": {"status": "ok"},
                },
                same_family_next_axes_payload={
                    "decision": {
                        "status": "decide_continue_to_remaining_same_family_design_vs_open_fallback_family",
                        "recommended_same_family_design": "XuanTie-C910",
                    },
                    "next_family_axis": {
                        "fallback_profile_name": "open_veer_fallback_family",
                        "fallback_family": "VeeR",
                    },
                },
                debug_tactics_payload={
                    "decision": {
                        "recommended_next_tactic": "open_veer_fallback_family",
                    }
                },
                profiles_dir=profiles_dir,
                current_selection_payload={"profile_name": "debug_c910_hybrid_runtime"},
                current_selection_path=root / "selection.json",
            )

            self.assertEqual(payload["summary"]["recommended_profile_name"], "open_veer_fallback_family")
            self.assertEqual(
                payload["summary"]["debug_tactic_recommended_next_tactic"],
                "open_veer_fallback_family",
            )

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profiles_dir = root / "profiles"
            profiles_dir.mkdir(parents=True)
            (profiles_dir / "hold_c910_runtime_branch.json").write_text(
                json.dumps({"name": "hold_c910_runtime_branch", "runtime_mode": "hold_c910_runtime_branch"})
                + "\n",
                encoding="utf-8",
            )
            selection_json = root / "selection.json"
            selection_json.write_text(
                json.dumps({"profile_name": "hold_c910_runtime_branch"}) + "\n",
                encoding="utf-8",
            )
            runtime_json = root / "runtime.json"
            runtime_json.write_text(
                json.dumps({"outcome": {"status": "decide_hybrid_runtime_debug_vs_open_veer_fallback_family"}})
                + "\n",
                encoding="utf-8",
            )
            next_axes_json = root / "next_axes.json"
            next_axes_json.write_text(
                json.dumps(
                    {
                        "decision": {
                            "status": "decide_continue_to_remaining_same_family_design_vs_open_fallback_family",
                            "recommended_same_family_design": "XuanTie-C910",
                        },
                        "next_family_axis": {
                            "fallback_profile_name": "open_veer_fallback_family",
                            "fallback_family": "VeeR",
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            debug_tactics_json = root / "debug_tactics.json"
            debug_tactics_json.write_text(
                json.dumps({"decision": {"recommended_next_tactic": "open_veer_fallback_family"}}) + "\n",
                encoding="utf-8",
            )
            json_out = root / "profiles.json"
            argv = [
                "audit_campaign_xuantie_c910_runtime_profiles.py",
                "--runtime-status-json",
                str(runtime_json),
                "--same-family-next-axes-json",
                str(next_axes_json),
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
            self.assertEqual(payload["scope"], "campaign_xuantie_c910_runtime_profiles")
            self.assertEqual(
                payload["summary"]["debug_tactic_recommended_next_tactic"],
                "open_veer_fallback_family",
            )


if __name__ == "__main__":
    unittest.main()
