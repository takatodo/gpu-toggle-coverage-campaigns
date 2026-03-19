#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_OUT = SCRIPT_DIR / "output_cleanup_candidates.json"
DEFAULT_MD_OUT = SCRIPT_DIR / "output_cleanup_candidates.md"
OUTPUT_INVENTORY_JSON = SCRIPT_DIR / "output_inventory.json"
RUNTIME_SCOPE_JSON = SCRIPT_DIR / "runtime_runner_scope.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _bucket_for(
    name: str,
    canonical_outputs: set[str],
    canonical_generators: set[str],
    mainline_runners: set[str],
    scoped_out_runners: set[str],
) -> tuple[str, str, str]:
    if name in canonical_outputs:
        return ("canonical_output", "keep_top_level", "Canonical decision/validation artifact.")
    if name in canonical_generators:
        return ("canonical_generator", "keep_top_level", "Generator for canonical artifacts.")
    if name in mainline_runners:
        return ("mainline_runner", "keep_top_level", "Mainline runtime/default runner retained by runtime scope.")
    if name in scoped_out_runners:
        return ("scoped_out_runner", "archive_candidate", "Scoped-out debug/raw or Tier-0 runner; not required for the frozen packet.")
    if name.startswith(".multi_codex") or name.startswith("multi_codex_") or name == "run_project_multi_codex_watch.sh":
        return ("ops_support", "archive_candidate", "Operational helper, not part of canonical output review.")
    if "direct_llvm" in name or "direct_feedback" in name or "gpu_cov_cpu_debug" in name or "direct_vsim" in name:
        return ("debug_probe", "archive_candidate", "One-off debug/probe helper outside the mainline frozen packet.")
    if name.startswith("veer_") or name.startswith("xuantie_") or name.startswith("vortex_"):
        return ("family_readiness_support", "keep_with_family_docs", "Family bring-up/readiness support artifact.")
    if name.startswith("opentitan_tlul_slice_"):
        return ("opentitan_slice_support", "archive_candidate", "Slice-era support/freeze artifact not in the canonical read-first set.")
    if name.startswith("run_opentitan_tlul_slice_") or name.startswith("prepare_opentitan_tlul_slice_") or name.startswith("report_opentitan_tlul_slice_") or name.startswith("sync_opentitan_tlul_slice_") or name.startswith("refresh_opentitan_tlul_slice_") or name.startswith("plan_opentitan_tlul_slice_") or name.startswith("record_opentitan_tlul_slice_") or name.startswith("rebuild_opentitan_tlul_slice_"):
        return ("opentitan_slice_support", "archive_candidate", "OpenTitan slice support script outside the canonical generator shortlist.")
    if name.startswith("run_tier1_") or name.startswith("run_tier2_") or name.startswith("run_tiny_accel_") or name == "tier2_vortex_abc_manifest.json":
        return ("experiment_runner", "archive_candidate", "Tier-specific experimental runner/artifact; useful for replay, not canonical read-first output.")
    if name.startswith("rtlmeter_design_"):
        return ("cross_design_support", "keep_top_level", "Cross-design classification/validation support.")
    if name.startswith("toggle_coverage_"):
        return ("rule_support", "keep_top_level", "Rule-table or validation support artifact.")
    if name in {"tiny_accel.v", "tiny_accel_cpu_run.cpp"}:
        return ("tier0_seed", "archive_candidate", "Tier-0 local seed artifact; not part of the frozen output packet.")
    if name in {"campaign_manifest.json", "summary.json", "launch_shards.sh", "shard_commands.txt"}:
        return ("ad_hoc_runtime", "archive_candidate", "Ad hoc runtime byproduct or helper.")
    return ("unclassified_support", "review_manually", "Not in the canonical set; needs manual placement if physical reorg is attempted.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze a non-destructive cleanup candidate list for top-level outputs.")
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    return parser.parse_args()


def main() -> int:
    ns = parse_args()
    inventory = _load_json(OUTPUT_INVENTORY_JSON)
    runtime_scope = _load_json(RUNTIME_SCOPE_JSON)

    canonical_outputs: set[str] = set()
    canonical_generators: set[str] = set()
    for section in inventory.get("sections", []):
        labels = {item["label"] for item in section.get("items", [])}
        if section.get("title") == "Canonical Generators":
            canonical_generators |= labels
        else:
            canonical_outputs |= labels

    mainline_runners = {row["runner"] for row in runtime_scope.get("mainline_runtime_runners", [])}
    scoped_out_runners = {row["runner"] for row in runtime_scope.get("scoped_out_runners", [])}

    rows = []
    for path in sorted(p for p in SCRIPT_DIR.iterdir() if p.is_file()):
        bucket, action, reason = _bucket_for(
            path.name,
            canonical_outputs,
            canonical_generators,
            mainline_runners,
            scoped_out_runners,
        )
        rows.append(
            {
                "name": path.name,
                "bucket": bucket,
                "recommended_action": action,
                "reason": reason,
            }
        )

    payload = {
        "schema_version": "output-cleanup-candidates-v1",
        "status": "cleanup_candidates_frozen",
        "root": str(SCRIPT_DIR),
        "rows": rows,
        "summary": {
            "keep_top_level": sum(1 for row in rows if row["recommended_action"] == "keep_top_level"),
            "archive_candidate": sum(1 for row in rows if row["recommended_action"] == "archive_candidate"),
            "keep_with_family_docs": sum(1 for row in rows if row["recommended_action"] == "keep_with_family_docs"),
            "review_manually": sum(1 for row in rows if row["recommended_action"] == "review_manually"),
        },
    }
    ns.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Output Cleanup Candidates",
        "",
        f"- status: `{payload['status']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Classified Top-Level Files",
            "",
            "| File | Bucket | Recommended action | Reason |",
            "|---|---|---|---|",
        ]
    )
    for row in rows:
        lines.append(
            "| {name} | {bucket} | {recommended_action} | {reason} |".format(**row)
        )
    ns.md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(ns.json_out)
    print(ns.md_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
