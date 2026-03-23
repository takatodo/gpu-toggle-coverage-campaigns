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
  # Check alternate install location (sim-accel build outside repo).
  FALLBACK_BENCH="$HOME/verilator/bin/verilator_sim_accel_bench"
  if [ -x "$FALLBACK_BENCH" ]; then
    ok "verilator_sim_accel_bench found at $FALLBACK_BENCH"
    BENCH="$FALLBACK_BENCH"
  else
    warn "verilator_sim_accel_bench not found"
    warn "Build third_party/verilator (sim-accel fork) and install:"
    warn "  cd third_party/verilator && autoconf && ./configure && make -j\$(nproc)"
    GPU_OK=0
  fi
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
echo "[6/6] Smoke run — VeeR-EL2 gpu_cov_gate (nstates=256, gpu-reps=1)"
if [ "$SKIP_RUN" -eq 1 ]; then
  warn "skipped (--skip-run)"
elif [ "$GPU_OK" -eq 0 ]; then
  warn "skipped — GPU or bench binary not available"
  echo
  echo -e "${GREEN}Environment ready.${RESET} Re-run without --skip-run once GPU/bench is set up."
else
  WORK_DIR="work/quickstart/VeeR-EL2/gpu_cov_gate"
  mkdir -p "$WORK_DIR"
  echo "  output → $WORK_DIR"
  VLR="$(dirname "$BENCH")/verilator"
  RUNNER_COMMON=(
    --bench "$BENCH"
    --verilator "$VLR"
    --case VeeR-EL2:gpu_cov_gate:hello
    --build-dir "$WORK_DIR"
    --nstates 256
    --gpu-reps 1
    --skip-cpu-reference-build
    --pre-gpu-gate never
    --gpu-execution-backend cuda_vl_ir
  )

  # ── 6a. Build phase: compile Verilator C++ → LLVM IR → PTX → cubin ─────────
  # cuda_vl_ir: Verilator emits full_comb.cu + full_seq.cu, compiled via
  # clang++ -emit-llvm, merged with llvm-link, assembled with llc, then ptxas
  # produces a cubin (no runtime JIT penalty).
  # Only rebuild when the vl_ir cubin is absent (first run or after clean).
  if [ ! -f "$WORK_DIR/kernel_generated.vl_ir.cubin" ]; then
    echo "  Building cuda_vl_ir bench_kernel (first time, ~3 min) ..."
    python3 src/runners/run_rtlmeter_gpu_toggle_baseline.py \
      "${RUNNER_COMMON[@]}" \
      --no-reuse-bench-kernel-if-present \
      2>/dev/null >/dev/null || true
    echo
  fi

  # ── 6b. Measurement run — call bench_kernel_vl_ir_cpu directly ──────────────
  BENCH_KERNEL="$WORK_DIR/bench_kernel_vl_ir_cpu"
  INIT_FILE="$WORK_DIR/gpu_driver.init"
  NSTATES=256
  if [ ! -x "$BENCH_KERNEL" ]; then
    warn "bench_kernel_vl_ir_cpu not found — skipping measurement"
  else
    BENCH_OUT=$(SIM_ACCEL_GPU_BINARY_PATH="$WORK_DIR/kernel_generated.vl_ir.cubin" \
      "$BENCH_KERNEL" \
      ${INIT_FILE:+--init-file "$INIT_FILE"} \
      --nstates $NSTATES --gpu-reps 3 --gpu-warmup-reps 1 --cpu-reps 0 \
      --sequential-steps 1 2>/dev/null || true)
    GPU_MS=$(echo "$BENCH_OUT" | grep '^gpu_ms_per_rep=' | cut -d= -f2)
    COV_HIT=$(echo "$BENCH_OUT" | grep '^coverage_points_hit=' | cut -d= -f2 || true)
    COV_TOT=$(echo "$BENCH_OUT" | grep '^coverage_points_total=' | cut -d= -f2 || true)

    CPU_OUT=$(SIM_ACCEL_GPU_BINARY_PATH="$WORK_DIR/kernel_generated.vl_ir.cubin" \
      "$BENCH_KERNEL" \
      ${INIT_FILE:+--init-file "$INIT_FILE"} \
      --nstates 1 --gpu-reps 0 --cpu-reps 1 \
      --sequential-steps 1 2>/dev/null || true)
    CPU_MS=$(echo "$CPU_OUT" | grep '^cpu_ms_per_rep=' | cut -d= -f2)

    echo
    python3 -c "
g=${GPU_MS:-0}; c=${CPU_MS:-0}; n=$NSTATES
hit='${COV_HIT:-?}'; tot='${COV_TOT:-?}'
print(f'  coverage : {hit}/{tot} toggle points')
if g > 0:
    gpu_per_sim = g/n
    print(f'  GPU      : {g:.0f} ms / {n} states  ({gpu_per_sim:.2f} ms/sim)')
if c > 0 and g > 0:
    ratio = (c*n)/g
    label = f'{ratio:.0f}x faster' if ratio > 1 else f'{1/ratio:.1f}x slower'
    print(f'  CPU      : {c:.2f} ms/sim × {n} = {c*n:.0f} ms equiv  (GPU is {label})')
" 2>/dev/null || true
    ok "VeeR-EL2 smoke run complete"
  fi
  echo
  echo -e "${GREEN}All done.${RESET} Next steps:"
  echo "  python3 src/runners/run_veer_family_gpu_toggle_validation.py   # full VeeR family"
  echo "  python3 src/runners/run_xuantie_family_gpu_toggle_validation.py"
  echo "  python3 src/runners/run_opentitan_tlul_slice_gpu_baseline.py --help"
fi
