#!/usr/bin/env zsh
# quickstart.sh — environment check, setup, optional LLVM passes build, optional legacy smoke
# Runs under zsh by default; `bash quickstart.sh` also works if you prefer bash.
set -euo pipefail

_script="${BASH_SOURCE[0]:-$0}"
REPO_ROOT="$(cd "$(dirname "$_script")" && pwd)"
cd "$REPO_ROOT"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; RESET='\033[0m'
ok()   { echo -e "  ${GREEN}[ok]${RESET}  $*"; }
warn() { echo -e "  ${YELLOW}[warn]${RESET} $*"; }
fail() { echo -e "  ${RED}[fail]${RESET} $*"; FAILED=1; }
FAILED=0

SKIP_RUN=0
SKIP_PASSES=0
LEGACY_SIM_ACCEL_SMOKE=0
for arg in "$@"; do
  case "$arg" in
    --skip-run)                 SKIP_RUN=1 ;;
    --skip-passes)              SKIP_PASSES=1 ;;
    --legacy-sim-accel-smoke)   LEGACY_SIM_ACCEL_SMOKE=1 ;;
  esac
done

VL_STOCK_OK=0

print_next_steps() {
  echo
  echo -e "${GREEN}All done.${RESET} Next steps:"
  echo "  python3 src/tools/build_vl_gpu.py <verilator-cc-out-dir>   # stock Verilator → cubin (recommended)"
  if [ "$VL_STOCK_OK" -eq 0 ]; then
    echo "  # Install LLVM-18 dev packages and: make -C src/passes"
  fi
  echo "  python3 src/runners/run_veer_family_gpu_toggle_validation.py   # legacy RTLMeter / sim-accel family runs"
  echo "  python3 src/runners/run_xuantie_family_gpu_toggle_validation.py"
  echo "  python3 src/runners/run_opentitan_tlul_slice_gpu_baseline.py --help"
  if [ "$LEGACY_SIM_ACCEL_SMOKE" -eq 0 ]; then
    echo "  # Old VeeR bench: ./quickstart.sh --legacy-sim-accel-smoke (requires verilator_sim_accel_bench)"
  fi
}

echo -e "${BOLD}=== GPU Toggle Coverage Campaigns — quickstart ===${RESET}"
echo

# ── 1. Python ────────────────────────────────────────────────────────────────
echo "[1/7] Python"
PY=$(python3 --version 2>&1 | awk '{print $2}')
PYMINOR=$(echo "$PY" | cut -d. -f2)
if [ "${PYMINOR:-0}" -ge 10 ]; then
  ok "python3 $PY"
else
  fail "python3 $PY — 3.10+ required"
fi

# ── 2. Submodules ─────────────────────────────────────────────────────────────
echo
echo "[2/7] Submodules"
if git submodule status | grep -q '^-'; then
  warn "uninitialized submodules detected — running git submodule update --init"
  git submodule update --init --recursive
  ok "submodules initialized"
else
  ok "submodules present"
fi

# ── 3. RTLMeter venv ─────────────────────────────────────────────────────────
echo
echo "[3/7] RTLMeter Python venv"
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

# ── 4. GPU toolchain (+ optional legacy sim-accel bench) ─────────────────────
echo
echo "[4/7] GPU toolchain (nvcc / hipcc)"
HAS_GPU_COMPILER=0
if command -v nvcc &>/dev/null; then
  ok "nvcc $(nvcc --version 2>&1 | grep -o 'release [0-9.]*')"
  HAS_GPU_COMPILER=1
elif command -v hipcc &>/dev/null; then
  ok "hipcc (ROCm) found"
  HAS_GPU_COMPILER=1
else
  warn "nvcc and hipcc not found — GPU / ptxas path may be limited"
fi

BENCH="$REPO_ROOT/third_party/verilator/bin/verilator_sim_accel_bench"
LEGACY_BENCH_OK=0
if [ "$LEGACY_SIM_ACCEL_SMOKE" -eq 1 ]; then
  echo "  (legacy) sim-accel bench for optional VeeR cuda_vl_ir smoke:"
  if [ -x "$BENCH" ]; then
    ok "verilator_sim_accel_bench found"
    LEGACY_BENCH_OK=1
  else
    FALLBACK_BENCH="$HOME/verilator/bin/verilator_sim_accel_bench"
    if [ -x "$FALLBACK_BENCH" ]; then
      ok "verilator_sim_accel_bench found at $FALLBACK_BENCH"
      BENCH="$FALLBACK_BENCH"
      LEGACY_BENCH_OK=1
    else
      warn "verilator_sim_accel_bench not found — cannot run legacy smoke"
      warn "  (sim-accel fork is deprecated here; use stock path: build_vl_gpu.py)"
    fi
  fi
else
  ok "legacy sim-accel smoke off by default (fork semantics unreliable)"
fi

# ── 5. LLVM-18 + vlgpugen (stock Verilator → cubin path) ─────────────────────
echo
echo "[5/7] LLVM-18 toolchain and src/passes (vlgpugen, VlGpuPasses.so)"
if [ "$SKIP_PASSES" -eq 1 ]; then
  warn "skipped (--skip-passes)"
elif command -v llvm-config-18 &>/dev/null; then
  ok "llvm-config-18 $(llvm-config-18 --version)"
  for t in clang++-18 opt-18 llvm-link-18 llc-18; do
    if command -v "$t" &>/dev/null; then
      ok "$t"
    else
      warn "$t not found — build_vl_gpu.py will fail without it"
      VL_STOCK_OK=0
    fi
  done
  if command -v ptxas &>/dev/null; then
    ok "ptxas (CUDA toolkit)"
  else
    warn "ptxas not found — cubin final step will fail"
    VL_STOCK_OK=0
  fi
  echo "  make -C src/passes ..."
  if make -C "$REPO_ROOT/src/passes" -s --no-print-directory 2>&1; then
    if [ -x "$REPO_ROOT/src/passes/vlgpugen" ] && [ -f "$REPO_ROOT/src/passes/VlGpuPasses.so" ]; then
      ok "vlgpugen + VlGpuPasses.so built"
      VL_STOCK_OK=1
    else
      warn "make finished but vlgpugen or VlGpuPasses.so missing"
      VL_STOCK_OK=0
    fi
  else
    warn "make -C src/passes failed — stock-Verilator GPU path unavailable"
    VL_STOCK_OK=0
  fi
else
  warn "llvm-config-18 not found — install LLVM 18 dev packages for stock-Verilator → GPU (README)"
  VL_STOCK_OK=0
fi

# ── 6. Unit tests ────────────────────────────────────────────────────────────
echo
echo "[6/7] Unit tests"
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

# ── 7. Optional legacy smoke (sim-accel cuda_vl_ir) ──────────────────────────
echo
echo "[7/7] Smoke — legacy VeeR cuda_vl_ir (opt-in only)"
if [ "$SKIP_RUN" -eq 1 ]; then
  warn "skipped (--skip-run)"
  print_next_steps
elif [ "$LEGACY_SIM_ACCEL_SMOKE" -eq 0 ]; then
  warn "skipped — sim-accel fork path not run by default (semantic drift vs RTL)"
  warn "  Use: ./quickstart.sh --legacy-sim-accel-smoke   or stock: python3 src/tools/build_vl_gpu.py …"
  print_next_steps
elif [ "$LEGACY_BENCH_OK" -eq 0 ] || [ "$HAS_GPU_COMPILER" -eq 0 ]; then
  warn "skipped — legacy bench or GPU compiler missing"
  print_next_steps
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

  # cuda_vl_ir: Verilator sim-accel emits full_comb/full_seq → LLVM IR → llc → ptxas → cubin.
  if [ ! -f "$WORK_DIR/kernel_generated.vl_ir.cubin" ]; then
    echo "  Building cuda_vl_ir bench_kernel (first time, ~3 min) ..."
    python3 src/runners/run_rtlmeter_gpu_toggle_baseline.py \
      "${RUNNER_COMMON[@]}" \
      --no-reuse-bench-kernel-if-present \
      2>/dev/null >/dev/null || true
    echo
  fi

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
    ok "VeeR-EL2 legacy smoke run complete"
  fi
  print_next_steps
fi
