#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

from time_to_threshold_comparison_common import main_with_defaults


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
DEFAULT_BASELINE = ROOT_DIR / "output" / "validation" / "vortex_cpu_baseline_validation.json"
DEFAULT_HYBRID = ROOT_DIR / "output" / "validation" / "vortex_stock_hybrid_validation.json"
DEFAULT_JSON_OUT = ROOT_DIR / "output" / "validation" / "vortex_time_to_threshold_comparison.json"


def main(argv: list[str]) -> int:
    return main_with_defaults(
        argv=argv,
        description="Compare Vortex CPU baseline vs stock-hybrid time-to-threshold artifacts.",
        default_baseline=DEFAULT_BASELINE,
        default_hybrid=DEFAULT_HYBRID,
        default_json_out=DEFAULT_JSON_OUT,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
