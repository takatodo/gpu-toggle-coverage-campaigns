#!/bin/bash
# Apply gpu_cov patches to third_party/rtlmeter
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RTLMETER_DIR="$(cd "$SCRIPT_DIR/../third_party/rtlmeter" && pwd)"

echo "Applying gpu_cov_designs.patch to $RTLMETER_DIR ..."
git -C "$RTLMETER_DIR" apply --check "$SCRIPT_DIR/gpu_cov_designs.patch" 2>&1
git -C "$RTLMETER_DIR" apply "$SCRIPT_DIR/gpu_cov_designs.patch"
echo "Done."
