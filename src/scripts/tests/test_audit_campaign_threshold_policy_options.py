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
MODULE_PATH = SCRIPT_DIR.parent / "tools" / "audit_campaign_threshold_policy_options.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _comparison_payload(*, target: str, value: int, winner: str, ratio: float) -> dict:
    return {
        "schema_version": 1,
        "status": "ok",
        "target": target,
        "campaign_threshold": {
            "kind": "toggle_bits_hit",
            "value": value,
            "aggregation": "bitwise_or_across_trials",
        },
        "comparison_ready": True,
        "winner": winner,
        "speedup_ratio": ratio,
        "reject_reason": None,
        "baseline": {
            "campaign_measurement": {
                "wall_time_ms": 20.0,
            }
        },
        "hybrid": {
            "campaign_measurement": {
                "wall_time_ms": 10.0,
            }
        },
    }


class AuditCampaignThresholdPolicyOptionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module("audit_campaign_threshold_policy_options_test", MODULE_PATH)

    def test_prefers_design_specific_review_when_common_candidate_is_weak(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            common_v1 = []
            common_v5 = []
            design_specific = []
            for name, value, ratio in (
                ("socket_v1", 3, 15.0),
                ("fifo_v1", 3, 1.16),
            ):
                path = root / f"{name}.json"
                target = "tlul_socket_m1" if "socket" in name else "tlul_fifo_sync"
                path.write_text(json.dumps(_comparison_payload(target=target, value=value, winner="hybrid", ratio=ratio)) + "\n", encoding="utf-8")
                common_v1.append(path)
            for name, value, ratio in (
                ("socket_v5", 5, 22.5),
                ("fifo_v5", 5, 1.20),
            ):
                path = root / f"{name}.json"
                target = "tlul_socket_m1" if "socket" in name else "tlul_fifo_sync"
                path.write_text(json.dumps(_comparison_payload(target=target, value=value, winner="hybrid", ratio=ratio)) + "\n", encoding="utf-8")
                common_v5.append(path)
            for name, value, ratio in (
                ("socket_ds", 5, 22.5),
                ("fifo_ds", 24, 2.64),
            ):
                path = root / f"{name}.json"
                target = "tlul_socket_m1" if "socket" in name else "tlul_fifo_sync"
                path.write_text(json.dumps(_comparison_payload(target=target, value=value, winner="hybrid", ratio=ratio)) + "\n", encoding="utf-8")
                design_specific.append(path)

            payload = self.module.build_audit(
                common_v1_paths=common_v1,
                common_threshold5_paths=common_v5,
                design_specific_paths=design_specific,
                minimum_strong_margin=2.0,
            )

            self.assertEqual(
                payload["decision"]["recommended_policy"],
                "decide_if_design_specific_thresholds_are_allowed",
            )
            self.assertEqual(
                payload["decision"]["reason"],
                "design_specific_candidate_is_strong_but_common_candidate_is_not",
            )

    def test_promotes_common_candidate_when_it_is_strong(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            common_v1 = []
            common_v5 = []
            design_specific = []
            for prefix, ratio_pair, value in (
                ("v1", (15.0, 1.16), 3),
                ("v5", (22.5, 2.2), 5),
                ("ds", (22.5, 2.64), 5),
            ):
                for target_name, ratio in zip(("tlul_socket_m1", "tlul_fifo_sync"), ratio_pair):
                    short = "socket" if "socket" in target_name else "fifo"
                    path = root / f"{short}_{prefix}.json"
                    current_value = 24 if prefix == "ds" and short == "fifo" else value
                    path.write_text(
                        json.dumps(_comparison_payload(target=target_name, value=current_value, winner="hybrid", ratio=ratio)) + "\n",
                        encoding="utf-8",
                    )
                    if prefix == "v1":
                        common_v1.append(path)
                    elif prefix == "v5":
                        common_v5.append(path)
                    else:
                        design_specific.append(path)

            payload = self.module.build_audit(
                common_v1_paths=common_v1,
                common_threshold5_paths=common_v5,
                design_specific_paths=design_specific,
                minimum_strong_margin=2.0,
            )
            self.assertEqual(payload["decision"]["recommended_policy"], "promote_common_threshold_v2")

    def test_main_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = {}
            for name, target, value, ratio in (
                ("common_v1_socket", "tlul_socket_m1", 3, 15.0),
                ("common_v1_fifo", "tlul_fifo_sync", 3, 1.16),
                ("common_v5_socket", "tlul_socket_m1", 5, 22.5),
                ("common_v5_fifo", "tlul_fifo_sync", 5, 1.20),
                ("ds_socket", "tlul_socket_m1", 5, 22.5),
                ("ds_fifo", "tlul_fifo_sync", 24, 2.64),
            ):
                path = root / f"{name}.json"
                path.write_text(json.dumps(_comparison_payload(target=target, value=value, winner="hybrid", ratio=ratio)) + "\n", encoding="utf-8")
                paths[name] = path
            json_out = root / "policy.json"
            argv = [
                "audit_campaign_threshold_policy_options.py",
                "--common-v1-socket", str(paths["common_v1_socket"]),
                "--common-v1-fifo", str(paths["common_v1_fifo"]),
                "--common-threshold5-socket", str(paths["common_v5_socket"]),
                "--common-threshold5-fifo", str(paths["common_v5_fifo"]),
                "--design-specific-socket", str(paths["ds_socket"]),
                "--design-specific-fifo", str(paths["ds_fifo"]),
                "--json-out", str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_threshold_policy_options")

    def test_main_accepts_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = {}
            for name, target, value, ratio in (
                ("common_v1_socket", "tlul_socket_m1", 3, 15.0),
                ("common_v1_fifo", "tlul_fifo_sync", 3, 1.16),
                ("common_v5_socket", "tlul_socket_m1", 5, 22.5),
                ("common_v5_fifo", "tlul_fifo_sync", 5, 1.20),
                ("ds_socket", "tlul_socket_m1", 5, 22.5),
                ("ds_fifo", "tlul_fifo_sync", 24, 2.64),
            ):
                path = root / f"{name}.json"
                path.write_text(json.dumps(_comparison_payload(target=target, value=value, winner="hybrid", ratio=ratio)) + "\n", encoding="utf-8")
                paths[name] = path
            config = root / "index.json"
            config.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "minimum_strong_margin": 2.0,
                        "scenarios": [
                            {
                                "name": "checked_in_common_v1",
                                "label": "checked-in common threshold v1",
                                "policy_mode": "common",
                                "paths": [
                                    str(paths["common_v1_socket"].relative_to(root)),
                                    str(paths["common_v1_fifo"].relative_to(root)),
                                ],
                            },
                            {
                                "name": "candidate_common_threshold5",
                                "label": "common raw-bits threshold=5 candidate",
                                "policy_mode": "common",
                                "paths": [
                                    str(paths["common_v5_socket"].relative_to(root)),
                                    str(paths["common_v5_fifo"].relative_to(root)),
                                ],
                            },
                            {
                                "name": "candidate_design_specific_minimal_progress",
                                "label": "socket_m1 threshold5 + tlul_fifo_sync seq1 threshold24",
                                "policy_mode": "per_target",
                                "paths": [
                                    str(paths["ds_socket"].relative_to(root)),
                                    str(paths["ds_fifo"].relative_to(root)),
                                ],
                            },
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            json_out = root / "policy.json"
            argv = [
                "audit_campaign_threshold_policy_options.py",
                "--config", str(config),
                "--json-out", str(json_out),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch.object(self.module, "REPO_ROOT", root):
                rc = self.module.main()

            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["scope"], "campaign_threshold_policy_options")
            self.assertEqual(payload["decision"]["recommended_policy"], "decide_if_design_specific_thresholds_are_allowed")
            self.assertEqual(payload["scenarios"][2]["policy_mode"], "per_target")


if __name__ == "__main__":
    unittest.main()
