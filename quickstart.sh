#!/usr/bin/env bash
# quickstart.sh — environment check and smoke test
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RESET='\033[0m'
ok()   { echo -e "  ${GREEN}[ok]${RESET}  $*"; }
warn() { echo -e "  ${YELLOW}[warn]${RESET} $*"; }
fail() { echo -e "  ${RED}[fail]${RESET} $*"; FAILED=1; }
FAILED=0

echo "=== GPU Toggle Coverage Campaigns — quickstart ==="
echo

# ── 1. Python ────────────────────────────────────────────────────────────────
echo "[1/5] Python"
PY=$(python3 --version 2>&1 | awk '{print $2}')
PYMINOR=$(echo "$PY" | cut -d. -f2)
if [ "${PYMINOR:-0}" -ge 10 ]; then
  ok "python3 $PY"
else
  fail "python3 $PY — 3.10+ required"
fi

# ── 2. Submodules ─────────────────────────────────────────────────────────────
echo
echo "[2/5] Submodules"
if git submodule status | grep -q '^-'; then
  warn "uninitialized submodules detected — running git submodule update --init"
  git submodule update --init --recursive
  ok "submodules initialized"
else
  ok "submodules present"
fi

# ── 3. RTLMeter venv ─────────────────────────────────────────────────────────
echo
echo "[3/5] RTLMeter Python venv"
VENV="$REPO_ROOT/rtlmeter/venv"
REQ="$REPO_ROOT/rtlmeter/python-requirements.txt"
if [ ! -f "$REQ" ]; then
  warn "rtlmeter/python-requirements.txt not found — skipping venv setup"
elif [ ! -d "$VENV" ]; then
  echo "  creating venv at rtlmeter/venv ..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -r "$REQ"
  ok "venv created and dependencies installed"
else
  ok "venv already exists (rtlmeter/venv)"
fi

# ── 4. GPU / build artifacts ──────────────────────────────────────────────────
echo
echo "[4/5] GPU and build artifacts"
BENCH="$REPO_ROOT/third_party/verilator/bin/verilator_sim_accel_bench"
VERILATOR="$REPO_ROOT/third_party/verilator/bin/verilator"
if [ -x "$BENCH" ]; then
  ok "verilator_sim_accel_bench found"
else
  warn "verilator_sim_accel_bench not found at third_party/verilator/bin/"
  warn "build from source: cd third_party/verilator && ./configure && make -j\$(nproc)"
  warn "(GPU runs will fail without this binary)"
fi
if command -v nvcc &>/dev/null; then
  ok "nvcc $(nvcc --version 2>&1 | grep -o 'release [0-9.]*')"
elif command -v hipcc &>/dev/null; then
  ok "hipcc (ROCm) found"
else
  warn "nvcc and hipcc not found — GPU compilation will not work"
fi

# ── 5. Unit tests ────────────────────────────────────────────────────────────
echo
echo "[5/5] Unit tests"
TEST_OUT=$(python3 -m unittest discover -s src/scripts -p 'test_*.py' 2>&1)
SUMMARY=$(echo "$TEST_OUT" | grep -E '^(OK|FAIL|ERROR|Ran [0-9]+)' | tr '\n' ' ')
if echo "$TEST_OUT" | grep -qE '^OK'; then
  COUNTS=$(echo "$TEST_OUT" | grep -oE 'Ran [0-9]+ tests|skipped=[0-9]+' | tr '\n' ' ')
  ok "$COUNTS"
else
  fail "unit tests failed: $SUMMARY"
  echo "$TEST_OUT" | grep -E '^(FAIL|ERROR|Traceback)' | head -10
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo
if [ "$FAILED" -eq 0 ]; then
  echo -e "${GREEN}Environment ready.${RESET} Suggested first run:"
  echo
  echo "  # VeeR family (dry-run, no GPU required for script load):"
  echo "  python3 src/runners/run_veer_family_gpu_toggle_validation.py --help"
  echo
  echo "  # Single baseline run (requires GPU + verilator_sim_accel_bench):"
  echo "  python3 src/runners/run_rtlmeter_gpu_toggle_baseline.py \\"
  echo "      --case VeeR-EL2:gpu_cov_gate:hello \\"
  echo "      --build-dir work/VeeR-EL2/gpu_cov_gate \\"
  echo "      --nstates 16 --gpu-reps 1"
else
  echo -e "${RED}Some checks failed.${RESET} Fix the issues above before running."
  exit 1
fi
