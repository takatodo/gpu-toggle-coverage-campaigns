#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
DEFAULT_REGION_MANIFEST = (
    ROOT_DIR / "rtlmeter/designs/OpenTitan/tests/tlul_fifo_sync_coverage_regions.json"
)


def load_region_manifest(path: Path | None = None) -> dict[str, Any]:
    manifest_path = Path(path or DEFAULT_REGION_MANIFEST).expanduser().resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"Coverage region manifest must be a JSON object: {manifest_path}")
    regions = payload.get("regions")
    if not isinstance(regions, list):
        raise SystemExit(f"Coverage region manifest regions must be a JSON array: {manifest_path}")
    for region in regions:
        if not isinstance(region, dict):
            raise SystemExit(f"Coverage region entry must be a JSON object: {manifest_path}")
        if not isinstance(region.get("name"), str):
            raise SystemExit(f"Coverage region name must be a string: {manifest_path}")
        words = region.get("words")
        if not isinstance(words, list) or not all(isinstance(word, str) for word in words):
            raise SystemExit(f"Coverage region words must be a string array: {manifest_path}")
    payload["manifest_path"] = str(manifest_path)
    return payload


def summarize_regions(
    manifest: dict[str, Any],
    *,
    active_words: list[str],
    dead_words: list[str],
) -> dict[str, Any]:
    active_set = set(active_words)
    dead_set = set(dead_words)
    active_regions: list[str] = []
    partial_regions: list[str] = []
    dead_regions: list[str] = []
    region_entries: list[dict[str, Any]] = []
    for region in manifest.get("regions", []):
        name = str(region["name"])
        words = [str(word) for word in region.get("words", [])]
        region_active = [word for word in words if word in active_set]
        region_dead = [word for word in words if word in dead_set]
        if len(region_active) == len(words):
            status = "active"
            active_regions.append(name)
        elif len(region_dead) == len(words):
            status = "dead"
            dead_regions.append(name)
        else:
            status = "partial"
            partial_regions.append(name)
        region_entries.append(
            {
                "name": name,
                "status": status,
                "word_count": len(words),
                "active_word_count": len(region_active),
                "dead_word_count": len(region_dead),
                "active_words": region_active,
                "dead_words": region_dead,
            }
        )
    return {
        "schema_version": manifest.get("schema_version"),
        "target": manifest.get("target"),
        "coverage_domain": manifest.get("coverage_domain"),
        "manifest_path": manifest.get("manifest_path"),
        "region_count": len(region_entries),
        "active_regions": active_regions,
        "active_region_count": len(active_regions),
        "partial_regions": partial_regions,
        "partial_region_count": len(partial_regions),
        "dead_regions": dead_regions,
        "dead_region_count": len(dead_regions),
        "regions": region_entries,
    }
