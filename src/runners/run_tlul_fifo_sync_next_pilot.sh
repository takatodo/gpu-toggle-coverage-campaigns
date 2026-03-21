#!/usr/bin/env bash
set -euo pipefail
# Legacy compatibility wrapper: respect the queue-aware selector instead of
# forcing a stale tlul_fifo_sync-specific pilot.
python3 /home/takatodo/GEM_try/out/opentitan_tlul_fifo_sync_trace_gpu_campaign_100k/run_next_opentitan_tlul_slice_pilot.py --prepare-only
