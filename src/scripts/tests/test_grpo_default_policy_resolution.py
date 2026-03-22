#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent.parent
RUNNER_PATH = SCRIPT_DIR.parent / "grpo/run_gpro_coverage_improvement.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class DefaultPolicyResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        if not RUNNER_PATH.is_file():
            self.skipTest(f"Module not available: {RUNNER_PATH.name}")
        self.runner = _load_module("grpo_default_policy_resolution_test", RUNNER_PATH)

    def test_recommended_defaults_exist_for_lc_ctrl_fsm(self) -> None:
        self.assertEqual(self.runner.recommended_grpo_policy_profile("lc_ctrl_fsm"), "diversity")
        self.assertEqual(self.runner.recommended_grpo_reward_profile("lc_ctrl_fsm"), "closure")
        self.assertEqual(self.runner.recommended_grpo_selection_mode("lc_ctrl_fsm"), "closure")
        self.assertEqual(
            self.runner.recommended_grpo_target_region("lc_ctrl_fsm"),
            "flash_rma_and_terminal_error_path",
        )

    def test_resolve_defaults_uses_closure_mode_and_missing_regions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            fake_summary = tmpdir / "summary.json"
            fake_summary.write_text("{}", encoding="utf-8")
            template_payload = {"runner_args_template": {"coverage_manifest_path": ""}}

            def _fake_run(cmd: list[str], cwd: Path, check: bool, env: dict[str, str]) -> None:
                self.assertIn("--selection-mode", cmd)
                mode_idx = cmd.index("--selection-mode") + 1
                self.assertEqual(cmd[mode_idx], "closure")
                self.assertIn("--missing-region", cmd)
                pipeline_dir = Path(cmd[cmd.index("--work-dir") + 1])
                pipeline_dir.mkdir(parents=True, exist_ok=True)
                (pipeline_dir / "policy.json").write_text(
                    json.dumps({"contexts": {}, "slice_contexts": {}, "missing_region_contexts": {}}),
                    encoding="utf-8",
                )
                (pipeline_dir / "pipeline_summary.json").write_text("{}", encoding="utf-8")

            ns = types.SimpleNamespace(
                grpo_default_mode="force",
                execution_engine="gpu",
                grpo_policy_profile="auto",
                grpo_target_region="auto",
                grpo_selection_mode="auto",
                grpo_reward_profile="closure",
                grpo_summary_json=[str(fake_summary)],
                grpo_summary_glob=[],
                grpo_missing_region=[],
                grpo_proposal_k=0,
            )
            with mock.patch.object(self.runner, "_derive_missing_regions_from_summaries", return_value=["r1", "r2"]):
                with mock.patch.object(self.runner.subprocess, "run", side_effect=_fake_run):
                    payload = self.runner._resolve_grpo_socket_defaults(
                        slice_name="tlul_socket_m1",
                        ns=ns,
                        work_dir=tmpdir / "run",
                        template_payload=template_payload,
                        defaults={"profile_family": "dead-region"},
                    )
            self.assertEqual(payload["policy_profile"], "diversity")
            self.assertEqual(payload["target_region"], "response_select_path")
            self.assertEqual(payload["selection_mode"], "closure")
            self.assertEqual(payload["missing_regions"], ["r1", "r2"])
            self.assertEqual(payload["proposal_k"], 2)
            self.assertTrue(Path(payload["policy_json"]).exists())


if __name__ == "__main__":
    unittest.main()
