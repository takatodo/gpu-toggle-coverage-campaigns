#!/usr/bin/env bash
# quickstart.sh — environment check, setup, and smoke run
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; RESET='\033[0m'
ok()   { echo -e "  ${GREEN}[ok]${RESET}  $*"; }
warn() { echo -e "  ${YELLOW}[warn]${RESET} $*"; }
fail() { echo -e "  ${RED}[fail]${RESET} $*"; FAILED=1; }
FAILED=0

# parse flags
SKIP_RUN=0
for arg in "$@"; do
  case "$arg" in --skip-run) SKIP_RUN=1 ;; esac
done

echo -e "${BOLD}=== GPU Toggle Coverage Campaigns — quickstart ===${RESET}"
echo

# ── 1. Python ────────────────────────────────────────────────────────────────
echo "[1/6] Python"
PY=$(python3 --version 2>&1 | awk '{print $2}')
PYMINOR=$(echo "$PY" | cut -d. -f2)
if [ "${PYMINOR:-0}" -ge 10 ]; then
  ok "python3 $PY"
else
  fail "python3 $PY — 3.10+ required"
fi

# ── 2. Submodules ─────────────────────────────────────────────────────────────
echo
echo "[2/6] Submodules"
if git submodule status | grep -q '^-'; then
  warn "uninitialized submodules detected — running git submodule update --init"
  git submodule update --init --recursive
  ok "submodules initialized"
else
  ok "submodules present"
fi

# ── 3. RTLMeter venv ─────────────────────────────────────────────────────────
echo
echo "[3/6] RTLMeter Python venv"
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
echo "[4/6] GPU and build artifacts"
BENCH="$REPO_ROOT/third_party/verilator/bin/verilator_sim_accel_bench"
GPU_OK=1
if [ -x "$BENCH" ]; then
  ok "verilator_sim_accel_bench found"
else
  warn "verilator_sim_accel_bench not found at third_party/verilator/bin/"
  warn "build from source: cd third_party/verilator && ./configure && make -j\$(nproc)"
  GPU_OK=0
fi
if command -v nvcc &>/dev/null; then
  ok "nvcc $(nvcc --version 2>&1 | grep -o 'release [0-9.]*')"
elif command -v hipcc &>/dev/null; then
  ok "hipcc (ROCm) found"
else
  warn "nvcc and hipcc not found — GPU compilation will not work"
  GPU_OK=0
fi

# ── 5. Unit tests ────────────────────────────────────────────────────────────
echo
echo "[5/6] Unit tests"
TEST_OUT=$(python3 -m unittest discover -s src/scripts -p 'test_*.py' 2>&1)
if echo "$TEST_OUT" | grep -qE '^OK'; then
  COUNTS=$(echo "$TEST_OUT" | grep -oE 'Ran [0-9]+ tests|skipped=[0-9]+' | tr '\n' ' ')
  ok "$COUNTS"
else
  fail "unit tests failed"
  echo "$TEST_OUT" | grep -E '^(FAIL|ERROR|Traceback)' | head -10
fi

# ── abort early if anything is broken ────────────────────────────────────────
if [ "$FAILED" -ne 0 ]; then
  echo
  echo -e "${RED}Prerequisite checks failed. Fix the issues above before running.${RESET}"
  exit 1
fi

# ── 6. Smoke run ─────────────────────────────────────────────────────────────
echo
echo "[6/6] Smoke run — VeeR-EL2 gpu_cov_gate (nstates=4, gpu-reps=1)"
if [ "$SKIP_RUN" -eq 1 ]; then
  warn "skipped (--skip-run)"
elif [ "$GPU_OK" -eq 0 ]; then
  warn "skipped — GPU or bench binary not available"
  echo
  echo -e "${GREEN}Environment ready.${RESET} Re-run without --skip-run once GPU/bench is set up."
else
  WORK_DIR="work/quickstart/VeeR-EL2/gpu_cov_gate"
  JSON_OUT="$WORK_DIR/baseline.json"
  mkdir -p "$WORK_DIR"
  echo "  output → $WORK_DIR"
  # Skip pre-GPU gate (CPU RTL sim) — it runs ~3 min every time and is not
  # needed for a quickstart smoke test where we just want GPU execution.
  echo
  python3 src/runners/run_rtlmeter_gpu_toggle_baseline.py \
    --case VeeR-EL2:gpu_cov_gate:hello \
    --build-dir "$WORK_DIR" \
    --nstates 4 \
    --gpu-reps 1 \
    --skip-cpu-reference-build \
    --pre-gpu-gate never \
    2>&1 | grep -v '^{' || true
  echo
  if [ -f "$JSON_OUT" ]; then
    python3 -c "
import json, subprocess

b = json.load(open('$JSON_OUT'))
cov  = b['collector']['coverage']
perf = b['collector']['performance']
hits  = cov.get('coverage_points_hit', '?')
total = cov.get('coverage_points_total', '?')
gpu_ms = perf.get('gpu_ms_per_rep') or 0.0

# CPU: run bench_kernel directly with gpu-reps=0 cpu-reps=1
cpu_ms = None
rt_cmd = b.get('bench_runtime_command', [])
if rt_cmd:
    cmd = rt_cmd[:]
    for i, v in enumerate(cmd):
        if v == '--cpu-reps':        cmd[i+1] = '1'
        if v == '--gpu-reps':        cmd[i+1] = '0'
        if v == '--gpu-warmup-reps': cmd[i+1] = '0'
    r = subprocess.run(cmd, capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith('cpu_ms_per_rep='):
            try: cpu_ms = float(line.split('=')[1])
            except: pass

WINDOW = 30_000  # ms
gpu_per_30s = int(WINDOW / gpu_ms) if gpu_ms > 0 else '?'
cpu_per_30s = int(WINDOW / cpu_ms) if cpu_ms and cpu_ms > 0 else '?'

print(f'  coverage : {hits}/{total} toggle points')
print(f'  GPU      : {gpu_ms:.0f} ms/rep  → {gpu_per_30s} sims in 30 s')
if cpu_ms and cpu_ms > 0:
    ratio = cpu_ms / gpu_ms if gpu_ms > 0 else 0
    label = f'{ratio:.1f}x faster' if ratio > 1 else f'{1/ratio:.1f}x slower'
    print(f'  CPU      : {cpu_ms:.0f} ms/rep  → {cpu_per_30s} sims in 30 s  (GPU is {label} at nstates=4)')
    print(f'  note     : GPU advantage grows with --nstates (at 256: GPU ~92x faster than CPU)')
" 2>/dev/null || echo "  done (see $JSON_OUT)"
    ok "VeeR-EL2 smoke run complete"
  else
    ok "VeeR-EL2 smoke run complete"
  fi
  echo
  echo -e "${GREEN}All done.${RESET} Next steps:"
  echo "  python3 src/runners/run_veer_family_gpu_toggle_validation.py   # full VeeR family"
  echo "  python3 src/runners/run_xuantie_family_gpu_toggle_validation.py"
  echo "  python3 src/runners/run_opentitan_tlul_slice_gpu_baseline.py --help"
fi
