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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xuantie_c910_split_phase_trial.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXuantieC910SplitPhaseTrialTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xuantie_c910_split_phase_trial_test", MODULE_PATH)

    def test_build_trial_marks_timeout_before_module_load(self) -> None:
        payload = self.module.build_trial(
            meta_payload={
                "cuda_module_format": "ptx",
                "cubin": "vl_batch_gpu.ptx",
                "gpu_opt_level": "O1",
                "storage_size": 1234,
            },
            manifest_payload={
                "kernels": [{"name": "k0"}, {"name": "k1"}],
                "launch_sequence": ["k0", "k1"],
            },
            trace_log_text="\n".join(
                [
                    "run_vl_hybrid: stage=before_cuInit",
                    "run_vl_hybrid: stage=before_cuModuleLoad",
                ]
            ),
            returncode_text="137\n",
        )

        self.assertEqual(payload["decision"]["status"], "timed_out_before_cuModuleLoad")
        self.assertEqual(
            payload["decision"]["recommended_next_action"],
            "choose_between_open_veer_fallback_family_and_deeper_c910_cubin_debug",
        )
        self.assertEqual(payload["split_phase_build"]["kernel_count"], 2)

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            meta_json = root / "meta.json"
            manifest_json = root / "manifest.json"
            trace_log = root / "trace.log"
            returncode_txt = root / "rc.txt"
            json_out = root / "trial.json"
            meta_json.write_text(
                json.dumps(
                    {
                        "cuda_module_format": "ptx",
                        "cubin": "vl_batch_gpu.ptx",
                        "gpu_opt_level": "O1",
                        "launch_sequence": ["k0"],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            manifest_json.write_text(
                json.dumps({"kernels": [{"name": "k0"}], "launch_sequence": ["k0"]}) + "\n",
                encoding="utf-8",
            )
            trace_log.write_text(
                "run_vl_hybrid: stage=before_cuModuleLoad\n",
                encoding="utf-8",
            )
            returncode_txt.write_text("137\n", encoding="utf-8")

            argv = [
                "audit_campaign_xuantie_c910_split_phase_trial.py",
                "--meta-json",
                str(meta_json),
                "--manifest-json",
                str(manifest_json),
                "--trace-log",
                str(trace_log),
                "--returncode-txt",
                str(returncode_txt),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_xuantie_c910_split_phase_trial")
            self.assertEqual(payload["split_phase_runtime"]["status"], "timed_out")


if __name__ == "__main__":
    unittest.main()
