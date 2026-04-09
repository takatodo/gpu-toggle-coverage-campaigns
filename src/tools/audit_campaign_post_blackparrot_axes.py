#!/usr/bin/env python3
"""
Pick the next family after the BlackParrot first-surface outcome is known.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_BLACKPARROT_STEP_JSON = REPO_ROOT / "work" / "campaign_blackparrot_first_surface_step.json"
DEFAULT_JSON_OUT = REPO_ROOT / "work" / "campaign_post_blackparrot_axes.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def build_status(*, blackparrot_step_payload: dict[str, Any] | None) -> dict[str, Any]:
    outcome = dict((blackparrot_step_payload or {}).get("outcome") or {})
    blackparrot_status = str(outcome.get("status") or "")

    if blackparrot_status != "blackparrot_candidate_only_baseline_win":
        decision = {
            "status": "blocked_post_blackparrot_axes_not_active",
            "reason": "post-BlackParrot axes only activate after the current BlackParrot first-surface line is closed as a non-promotable baseline-loss branch",
            "recommended_family": None,
            "fallback_family": outcome.get("fallback_family"),
            "recommended_next_task": outcome.get("next_action") or "close_blackparrot_first_surface_step",
        }
        candidate_families: list[dict[str, Any]] = []
    else:
        decision = {
            "status": "decide_open_next_family_after_blackparrot_baseline_loss",
            "reason": (
                "BlackParrot is actual-GPU validated at the family level but the first campaign trio "
                "loses even on the strongest checked-in candidate-only line, so breadth should move to "
                "the next non-blocked family"
            ),
            "recommended_family": "Vortex",
            "fallback_family": "XiangShan",
            "recommended_next_task": "open_the_first_vortex_campaign_trio",
        }
        candidate_families = [
            {
                "repo_family": "Vortex",
                "blocked_current_branch": False,
                "readiness_support": {
                    "kind": "readiness_artifact_only",
                    "readiness_md_path": str(
                        (REPO_ROOT / "output" / "family_readiness" / "vortex_gpu_toggle_readiness.md").resolve()
                    ),
                },
                "runner_support": {
                    "kind": "none",
                    "paths": [],
                },
            },
            {
                "repo_family": "XiangShan",
                "blocked_current_branch": True,
                "readiness_support": {
                    "kind": "actual_gpu_validated",
                    "readiness_md_path": str(
                        (REPO_ROOT / "output" / "family_readiness" / "xiangshan_gpu_toggle_readiness.md").resolve()
                    ),
                },
                "runner_support": {
                    "kind": "campaign_trio",
                    "paths": [
                        str((REPO_ROOT / "src" / "runners" / "run_xiangshan_stock_hybrid_validation.py").resolve()),
                        str((REPO_ROOT / "src" / "runners" / "run_xiangshan_cpu_baseline_validation.py").resolve()),
                        str((REPO_ROOT / "src" / "runners" / "run_xiangshan_time_to_threshold_comparison.py").resolve()),
                    ],
                },
            },
        ]

    return {
        "schema_version": 1,
        "scope": "campaign_post_blackparrot_axes",
        "blackparrot_outcome": {
            "status": blackparrot_status or None,
            "next_action": outcome.get("next_action"),
            "default_comparison_path": outcome.get("default_comparison_path") or outcome.get("comparison_path"),
            "candidate_comparison_path": outcome.get("candidate_comparison_path"),
        },
        "candidate_families": candidate_families,
        "decision": decision,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blackparrot-step-json", type=Path, default=DEFAULT_BLACKPARROT_STEP_JSON)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    args = parser.parse_args()

    payload = build_status(
        blackparrot_step_payload=_read_json(args.blackparrot_step_json.resolve()),
    )
    json_out = args.json_out.resolve()
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
