#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
TRAINER_PATH = SCRIPT_DIR.parent / "grpo/train_grpo_policy_minimal.py"


def _load_module(name: str, path: Path):
    module_dir = str(path.parent)
    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _record(
    *,
    group_id: str,
    action_key: str,
    reward: float,
    target_region: str,
    context_key: str = "slice::target::dead-region",
    slice_context_key: str = "slice::*::dead-region",
    missing_region_context_key: str = "slice::missing::dead-region",
) -> dict[str, object]:
    return {
        "group_id": group_id,
        "context_key": context_key,
        "slice_context_key": slice_context_key,
        "missing_region_context_key": missing_region_context_key,
        "action_key": action_key,
        "action_patch": {"name": action_key},
        "reward": reward,
        "case_summary": {"coverage_per_second": 100.0},
        "frontier": {"target_region": target_region},
    }


class TrainGrpoPolicyMinimalTest(unittest.TestCase):
    def setUp(self) -> None:
        if not TRAINER_PATH.is_file():
            self.skipTest(f"Module not available: {TRAINER_PATH.name}")
        self.trainer = _load_module("train_grpo_policy_minimal_test_module", TRAINER_PATH)

    def _run_trainer(
        self,
        rows: list[dict[str, object]],
        reward_profile: str,
        *,
        diversity_weight: float | None = None,
        rarity_weight: float | None = None,
        frequency_novelty_weight: float | None = None,
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            dataset = tmpdir / "dataset.jsonl"
            output = tmpdir / "policy.json"
            dataset.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            argv = [
                "--dataset-jsonl",
                str(dataset),
                "--json-out",
                str(output),
                "--top-actions-per-context",
                "2",
                "--reward-profile",
                reward_profile,
            ]
            if diversity_weight is not None:
                argv.extend(["--diversity-weight", str(diversity_weight)])
            if rarity_weight is not None:
                argv.extend(["--rarity-weight", str(rarity_weight)])
            if frequency_novelty_weight is not None:
                argv.extend(["--frequency-novelty-weight", str(frequency_novelty_weight)])
            rc = self.trainer.main(argv)
            self.assertEqual(rc, 0)
            return json.loads(output.read_text(encoding="utf-8"))

    def test_closure_promotes_second_target_family(self) -> None:
        rows = [
            _record(group_id="g1", action_key="req_1", reward=1.00, target_region="reqfifo_storage_upper"),
            _record(group_id="g2", action_key="req_2", reward=0.99, target_region="reqfifo_storage_upper"),
            _record(group_id="g3", action_key="rsp_1", reward=0.90, target_region="rspfifo_storage_upper"),
        ]
        payload = self._run_trainer(
            rows,
            "closure",
            diversity_weight=0.25,
            rarity_weight=0.0,
            frequency_novelty_weight=0.0,
        )
        actions = payload["contexts"]["slice::target::dead-region"]
        self.assertEqual(actions[0]["target_regions"], ["reqfifo_storage_upper"])
        self.assertEqual(actions[1]["target_regions"], ["rspfifo_storage_upper"])

    def test_throughput_keeps_reward_order_without_family_bonus(self) -> None:
        rows = [
            _record(group_id="g1", action_key="req_1", reward=1.00, target_region="reqfifo_storage_upper"),
            _record(group_id="g2", action_key="req_2", reward=0.99, target_region="reqfifo_storage_upper"),
            _record(group_id="g3", action_key="rsp_1", reward=0.90, target_region="rspfifo_storage_upper"),
        ]
        payload = self._run_trainer(
            rows,
            "throughput",
            diversity_weight=0.0,
            rarity_weight=0.0,
            frequency_novelty_weight=0.0,
        )
        actions = payload["contexts"]["slice::target::dead-region"]
        self.assertEqual(actions[0]["action_key"], "req_1")
        self.assertEqual(actions[1]["action_key"], "req_2")

    def test_single_family_stays_stable(self) -> None:
        rows = [
            _record(group_id="g1", action_key="req_1", reward=1.00, target_region="reqfifo_storage_upper"),
            _record(group_id="g2", action_key="req_2", reward=0.95, target_region="reqfifo_storage_upper"),
            _record(group_id="g3", action_key="req_3", reward=0.90, target_region="reqfifo_storage_upper"),
        ]
        payload = self._run_trainer(rows, "closure")
        actions = payload["contexts"]["slice::target::dead-region"]
        self.assertEqual([item["action_key"] for item in actions], ["req_1", "req_2"])


if __name__ == "__main__":
    unittest.main()
