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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_xuantie_c910_runtime_status.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class AuditCampaignXuantieC910RuntimeStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_xuantie_c910_runtime_status_test", MODULE_PATH)

    def test_reports_runtime_debug_vs_veer_when_hybrid_is_sigkilled(self) -> None:
        payload = self.module.build_status(
            hybrid_payload={
                "status": "error",
                "flow_returncode": 1,
                "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
                "campaign_measurement": {"bits_hit": 0, "threshold_satisfied": False},
                "stderr_tail": "run_vl_hybrid ... died with <Signals.SIGKILL: 9>.",
            },
            baseline_payload={
                "status": "ok",
                "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
                "campaign_measurement": {"bits_hit": 4, "threshold_satisfied": False},
            },
            meta_payload={"cubin": "vl_batch_gpu.ptx", "cuda_module_format": "ptx"},
            runtime_smoke_payload=None,
            o0_build_log_text=None,
            o1_trace_log_text=None,
            cubin_probe_payload=None,
        )

        self.assertEqual(
            payload["outcome"]["status"],
            "decide_hybrid_runtime_debug_vs_open_veer_fallback_family",
        )
        self.assertTrue(payload["hybrid"]["runtime_killed"])
        self.assertEqual(payload["gpu_module"]["module_format"], "ptx")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            hybrid_json = root / "hybrid.json"
            baseline_json = root / "baseline.json"
            meta_json = root / "meta.json"
            json_out = root / "status.json"

            hybrid_json.write_text(
                json.dumps(
                    {
                        "status": "error",
                        "flow_returncode": 1,
                        "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
                        "campaign_measurement": {"bits_hit": 0, "threshold_satisfied": False},
                        "stderr_tail": "run_vl_hybrid ... died with <Signals.SIGKILL: 9>.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            baseline_json.write_text(
                json.dumps(
                    {
                        "status": "ok",
                        "campaign_threshold": {"kind": "toggle_bits_hit", "value": 8},
                        "campaign_measurement": {"bits_hit": 4, "threshold_satisfied": False},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            meta_json.write_text(
                json.dumps({"cubin": "vl_batch_gpu.ptx", "cuda_module_format": "ptx"}) + "\n",
                encoding="utf-8",
            )
            runtime_smoke_json = root / "runtime_smoke.json"
            runtime_smoke_json.write_text(
                json.dumps(
                    {
                        "decision": {"status": "hybrid_runtime_killed_even_at_minimal_shapes"},
                        "runs": [
                            {"label": "minimal_shape_1x1", "outcome": "sigkill"},
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            o0_build_log = root / "c910_o0_build.log"
            o0_build_log.write_text(
                "LLVM ERROR: Cannot select: AtomicLoad<(load acquire (s64) from %ir.6)>\n",
                encoding="utf-8",
            )
            o1_trace_log = root / "c910_o1_trace.log"
            o1_trace_log.write_text(
                "\n".join(
                    [
                        "run_vl_hybrid: stage=before_cuInit",
                        "run_vl_hybrid: stage=after_cuCtxCreate",
                        "run_vl_hybrid: stage=before_cuModuleLoad",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            cubin_probe_json = root / "c910_ptxas_o1_probe.json"
            cubin_probe_json.write_text(
                json.dumps(
                    {
                        "scope": "probe_vl_gpu_ptxas",
                        "status": "killed",
                        "opt_level": 1,
                        "timeout_seconds": 180,
                        "cubin_exists": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            argv = [
                "audit_campaign_xuantie_c910_runtime_status.py",
                "--hybrid-json",
                str(hybrid_json),
                "--baseline-json",
                str(baseline_json),
                "--meta-json",
                str(meta_json),
                "--runtime-smoke-json",
                str(runtime_smoke_json),
                "--o0-build-log",
                str(o0_build_log),
                "--o1-trace-log",
                str(o1_trace_log),
                "--cubin-probe-json",
                str(cubin_probe_json),
                "--json-out",
                str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_xuantie_c910_runtime_status")
            self.assertEqual(
                payload["outcome"]["status"],
                "decide_hybrid_runtime_debug_vs_open_veer_fallback_family",
            )
            self.assertEqual(payload["runtime_smoke"]["status"], "hybrid_runtime_killed_even_at_minimal_shapes")
            self.assertEqual(
                payload["low_opt_runtime_debug"]["o0_rebuild"]["status"],
                "llc_sigabrt_on_atomicload_acquire_i64",
            )
            self.assertEqual(
                payload["low_opt_runtime_debug"]["o1_trace"]["status"],
                "stalled_before_cuModuleLoad",
            )
            self.assertEqual(
                payload["low_opt_runtime_debug"]["cubin_probe"]["status"],
                "killed",
            )
            self.assertEqual(payload["gpu_module"]["gpu_opt_level"], None)
            self.assertEqual(
                payload["outcome"]["next_action"],
                "choose_between_deeper_c910_cubin_debug_and_opening_the_veer_fallback_family",
            )


if __name__ == "__main__":
    unittest.main()
