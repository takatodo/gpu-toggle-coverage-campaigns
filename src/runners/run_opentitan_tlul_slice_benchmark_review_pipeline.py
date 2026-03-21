#!/usr/bin/env python3
from __future__ import annotations

import runpy
import sys
from pathlib import Path


ARCHIVE_SCRIPT = (
    Path(__file__).resolve().parent
    / "archive"
    / "run_opentitan_tlul_slice_benchmark_review_pipeline.py"
)


def main() -> int:
    sys.argv[0] = str(ARCHIVE_SCRIPT)
    runpy.run_path(str(ARCHIVE_SCRIPT), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
