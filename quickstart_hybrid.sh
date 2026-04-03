#!/usr/bin/env zsh
# quickstart_hybrid.sh — quickstart-style driver for stock Verilator → cubin → hybrid runner
# Runs under zsh by default; `bash quickstart_hybrid.sh` also works if you prefer bash.
set -euo pipefail

# Repo root = directory of this script (works even if cwd is not the repo).
_script="${BASH_SOURCE[0]:-$0}"
case "$_script" in
  /*) ;;
  *) _script="$PWD/$_script" ;;
esac
REPO_ROOT="$(cd "$(dirname "$_script")" && pwd)"
cd "$REPO_ROOT" || exit 1
# Canonical hybrid example (stock Verilator --cc); mkdir + bootstrap when missing.
_SOCKET_M1_CC="$REPO_ROOT/work/vl_ir_exp/socket_m1_vl"
# Compare paths even with trailing slashes or symlinked repo (GNU realpath -m).
_sock_m1_same() {
  local a b
  a="${1%/}"
  b="${2%/}"
  if [ "$a" = "$b" ]; then
    return 0
  fi
  if command -v realpath >/dev/null 2>&1 && realpath -m "$REPO_ROOT" >/dev/null 2>&1; then
    [ "$(realpath -m "$a")" = "$(realpath -m "$b")" ]
  else
    return 1
  fi
}
_sock_m1_model_present() {
  local d
  d="${1%/}"
  [ -f "$d/Vtlul_socket_m1_gpu_cov_tb_classes.mk" ] || [ -f "$d/Vtlul_socket_m1_gpu_cov_tb.mk" ]
}
# WSL2: nvidia-smi can work while cuInit/cuDeviceGet fail (error 100) until the host
# libcuda is preferred. Prepend when present (no-op on native Linux without this path).
if [[ -r /usr/lib/wsl/lib/libcuda.so.1 ]]; then
  export LD_LIBRARY_PATH="/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}"
fi
# zsh: inside functions, $0 is the function name — use SELF for usage text.
SELF="$_script"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; RESET='\033[0m'
ok()   { echo -e "  ${GREEN}[ok]${RESET}  $*"; }
warn() { echo -e "  ${YELLOW}[warn]${RESET} $*"; }
fail() { echo -e "  ${RED}[fail]${RESET} $*"; FAILED=1; }
FAILED=0

MDIR=""
# Step 7/7 scales with nstates (device bytes = storage * nstates); 256 is enough for smoke.
NSTATES=4096
STEPS=3
BLOCK=256
SM="sm_89"
SKIP_PASSES=0
SKIP_BUILD=0
SKIP_RUN=0
SKIP_SUBMODULES=0
FORCE_BUILD=0
FAST=0
LITE=0
CLANG_OPT=O1
NO_BOOTSTRAP=0
ANALYZE_PHASES=0
KERNEL_SPLIT_PHASES=0
SOCKET_M1_HOST_GPU_FLOW=0
PATCHES=()

usage() {
  cat <<EOF
quickstart_hybrid.sh — stock Verilator --cc → cubin → hybrid runner.

Usage:
  $SELF [--mdir <verilator-cc-dir> | <verilator-cc-dir>] [options]

Options:
  --mdir PATH          Verilator --cc output (contains *_classes.mk)
  --nstates N          Parallel states for step 7 (default: 256; use 4096+ for stress)
  --steps N            Patch+launch repeats (default: 1)
  --block-size N       CUDA block size (default: 256)
  --patch OFF:BYTE     HtoD patch per step (repeatable)
  --sm ARCH            ptxas arch, e.g. sm_89 (default: sm_89)
  --lite               Step 7 only: --nstates 64 --steps 1 (minimal GPU smoke)
  --force              Pass --force to build_vl_gpu.py
  --skip-passes        Skip make -C src/passes
  --skip-build         Skip build_vl_gpu.py (cubin must already exist)
  --skip-run           Build only; do not run run_vl_hybrid
  --skip-submodules    Skip git submodule check (faster when submodules already init)
  --fast               Skip submodules; skip passes if vlgpugen+VlGpuPasses.so exist;
                       skip build_vl_gpu if cubin+meta exist (unless --force)
  --fast-sim           Pass --clang-O O3 to build_vl_gpu.py (often shorter GPU _eval; slower compile)
  --clang-O LEVEL      clang -O when emitting .ll: O0 O1 O2 O3 Os Oz (default: O1)
  --no-bootstrap       Do not auto-run Verilator for work/vl_ir_exp/socket_m1_vl
  --analyze-phases     Pass --analyze-phases to build_vl_gpu.py (Phase B ico/nba report)
  --kernel-split-phases  Pass --kernel-split-phases to build_vl_gpu.py (Phase B multi-kernel)
  --socket-m1-host-gpu-flow
                       Run the first supported tlul_socket_m1 host->GPU handoff:
                       host probe dumps one raw root image, then run_vl_hybrid consumes it
                       via --init-state. Implies --kernel-split-phases and requires the
                       tlul_socket_m1 Verilator --cc directory.
  -h, --help           This help

Example:
  $SELF --mdir work/my_design/obj_dir --steps 4 --patch 0:1
  $SELF --fast --lite --mdir work/vl_ir_exp/socket_m1_vl   # fastest 7/7 smoke
  $SELF --mdir ... --fast-sim --force                       # rebuild cubin for faster sim
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --mdir)
      MDIR=$2
      shift 2
      ;;
    --nstates)
      NSTATES=$2
      shift 2
      ;;
    --steps)
      STEPS=$2
      shift 2
      ;;
    --block-size)
      BLOCK=$2
      shift 2
      ;;
    --patch)
      PATCHES+=("$2")
      shift 2
      ;;
    --sm)
      SM=$2
      shift 2
      ;;
    --force)
      FORCE_BUILD=1
      shift
      ;;
    --skip-passes)
      SKIP_PASSES=1
      shift
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --skip-run)
      SKIP_RUN=1
      shift
      ;;
    --skip-submodules)
      SKIP_SUBMODULES=1
      shift
      ;;
    --fast)
      FAST=1
      shift
      ;;
    --fast-sim)
      CLANG_OPT=O3
      shift
      ;;
    --clang-O)
      CLANG_OPT=$2
      shift 2
      ;;
    --no-bootstrap)
      NO_BOOTSTRAP=1
      shift
      ;;
    --analyze-phases)
      ANALYZE_PHASES=1
      shift
      ;;
    --kernel-split-phases)
      KERNEL_SPLIT_PHASES=1
      shift
      ;;
    --socket-m1-host-gpu-flow)
      SOCKET_M1_HOST_GPU_FLOW=1
      KERNEL_SPLIT_PHASES=1
      shift
      ;;
    --lite)
      LITE=1
      NSTATES=64
      STEPS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
    *)
      if [ -z "$MDIR" ] && [ -d "$1" ]; then
        MDIR=$1
        shift
      else
        echo "Unexpected argument: $1" >&2
        usage >&2
        exit 1
      fi
      ;;
  esac
done

print_next_steps() {
  echo
  echo -e "${GREEN}Hybrid quickstart done.${RESET} Next steps:"
  if [ "$SOCKET_M1_HOST_GPU_FLOW" -eq 1 ]; then
    echo "  python3 src/tools/run_socket_m1_host_gpu_flow.py --mdir <socket_m1-cc-dir> [--nstates N] [--steps S] [--patch off:byte ...]"
  else
    echo "  python3 src/tools/run_vl_hybrid.py --mdir <cc-dir> [--nstates N] [--steps S] [--patch off:byte ...]"
  fi
  echo "  python3 src/tools/build_vl_gpu.py <cc-dir> [--sm $SM]   # rebuild cubin"
  echo "  See README.md, docs/roadmap_tasks.md, and docs/phase_c_socket_m1_host_abi.md"
}

echo -e "${BOLD}=== Hybrid GPU path — quickstart (stock Verilator → cubin → hybrid runner) ===${RESET}"
echo

# If no --mdir, use bundled OpenTitan TLUL example when present (under work/ on many clones).
_DEFAULT_MDIR="$_SOCKET_M1_CC"
if [ -z "$MDIR" ]; then
  MDIR="$_DEFAULT_MDIR"
  warn "no --mdir given; using example work/vl_ir_exp/socket_m1_vl (mkdir + Verilator --cc if needed)"
fi

# Resolve relative paths from repo root (not the shell’s cwd).
case "$MDIR" in
  /*) ;;
  ./*) MDIR="$REPO_ROOT/${MDIR#./}" ;;
  *)   MDIR="$REPO_ROOT/$MDIR" ;;
esac

if [ ! -d "$MDIR" ]; then
  if [ -e "$MDIR" ] && [ ! -d "$MDIR" ]; then
    echo -e "${RED}error:${RESET} not a directory: $MDIR" >&2
    exit 1
  fi
  if _sock_m1_same "$MDIR" "$_SOCKET_M1_CC"; then
    mkdir -p "$MDIR"
    ok "created $MDIR"
  else
    echo -e "${RED}error:${RESET} path does not exist or is not a directory: $MDIR" >&2
    echo "  For the socket_m1 example use:  $SELF --mdir work/vl_ir_exp/socket_m1_vl" >&2
    echo "  Or create the Verilator --cc obj_dir yourself." >&2
    exit 1
  fi
fi

MDIR_ABS=$(cd "$MDIR" && pwd)

VL_STOCK_OK=0
if [ "$FAST" -eq 1 ]; then
  SKIP_SUBMODULES=1
  if [ -x "$REPO_ROOT/src/passes/vlgpugen" ] &&
    [ -f "$REPO_ROOT/src/passes/VlGpuPasses.so" ]; then
    SKIP_PASSES=1
    VL_STOCK_OK=1
  fi
  if [ "$FORCE_BUILD" -eq 0 ] &&
    [ -f "$MDIR_ABS/vl_batch_gpu.meta.json" ] &&
    [ -f "$MDIR_ABS/vl_batch_gpu.cubin" ]; then
    SKIP_BUILD=1
  fi
  warn "--fast: submodules off; passes/build skipped when artifacts already present"
fi

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
if [ "$SKIP_SUBMODULES" -eq 1 ]; then
  warn "skipped (--skip-submodules or --fast)"
else
  if git submodule status 2>/dev/null | grep -q '^-'; then
    warn "uninitialized submodules — git submodule update --init"
    git submodule update --init --recursive
    ok "submodules initialized"
  else
    ok "submodules present"
  fi
fi

# ── 3. LLVM-18 + passes ─────────────────────────────────────────────────────
echo
echo "[3/7] LLVM-18 and src/passes (vlgpugen, VlGpuPasses.so)"
if [ "$SKIP_PASSES" -eq 1 ]; then
  warn "skipped (--skip-passes)"
elif command -v llvm-config-18 &>/dev/null; then
  ok "llvm-config-18 $(llvm-config-18 --version)"
  if make -q -C "$REPO_ROOT/src/passes" --no-print-directory 2>/dev/null; then
    ok "src/passes up to date (make skipped)"
    if [ -x "$REPO_ROOT/src/passes/vlgpugen" ] && [ -f "$REPO_ROOT/src/passes/VlGpuPasses.so" ]; then
      VL_STOCK_OK=1
    fi
  else
    echo "  make -C src/passes ..."
    if make -C "$REPO_ROOT/src/passes" -s --no-print-directory 2>&1; then
      if [ -x "$REPO_ROOT/src/passes/vlgpugen" ] && [ -f "$REPO_ROOT/src/passes/VlGpuPasses.so" ]; then
        ok "vlgpugen + VlGpuPasses.so built"
        VL_STOCK_OK=1
      else
        warn "make finished but vlgpugen or VlGpuPasses.so missing"
      fi
    else
      warn "make -C src/passes failed"
    fi
  fi
else
  warn "llvm-config-18 not found — install LLVM 18 dev packages"
fi

# ── 4. GPU toolchain ──────────────────────────────────────────────────────────
echo
echo "[4/7] GPU toolchain (ptxas / CUDA)"
HAS_PTXAS=0
if command -v ptxas &>/dev/null; then
  ok "ptxas available"
  HAS_PTXAS=1
else
  warn "ptxas not found — cubin build will fail"
fi
if [ -f /usr/local/cuda/include/cuda.h ] || [ -f /usr/include/cuda.h ]; then
  ok "CUDA headers (for run_vl_hybrid)"
else
  warn "cuda.h not in usual paths — run_vl_hybrid may fail to compile"
fi

# ── early exit on broken prereqs ──────────────────────────────────────────────
if [ "$FAILED" -ne 0 ]; then
  echo
  echo -e "${RED}Prerequisite checks failed.${RESET}"
  exit 1
fi

echo
echo "  Verilator --cc dir: $MDIR_ABS"

if ! find "$MDIR_ABS" -maxdepth 1 -name '*_classes.mk' -print -quit | grep -q .; then
  if [ "$NO_BOOTSTRAP" -eq 0 ] && _sock_m1_same "$MDIR_ABS" "$_SOCKET_M1_CC"; then
    warn "no *_classes.mk — running stock Verilator --cc (bootstrap_hybrid_socket_m1_cc.py)"
    python3 "$REPO_ROOT/src/tools/bootstrap_hybrid_socket_m1_cc.py" --out-dir "$MDIR_ABS"
  else
    echo -e "${RED}error:${RESET} no *_classes.mk in $MDIR_ABS" >&2
    echo "  Run:  python3 src/tools/bootstrap_hybrid_socket_m1_cc.py --out-dir <mdir>" >&2
    echo "  (socket_m1 example only) or point --mdir at an existing Verilator --cc directory." >&2
    exit 1
  fi
fi
if ! find "$MDIR_ABS" -maxdepth 1 -name '*_classes.mk' -print -quit | grep -q .; then
  echo -e "${RED}error:${RESET} bootstrap did not produce *_classes.mk in $MDIR_ABS" >&2
  exit 1
fi

# ── 5. build_vl_gpu.py ───────────────────────────────────────────────────────
echo
echo "[5/7] build_vl_gpu.py → vl_batch_gpu.cubin"
if [ "$SKIP_BUILD" -eq 1 ]; then
  warn "skipped (--skip-build)"
  META="$MDIR_ABS/vl_batch_gpu.meta.json"
  if [ ! -f "$META" ]; then
    echo "error: $META missing — run without --skip-build" >&2
    exit 1
  fi
  ok "using existing meta + cubin"
else
  if [ "$VL_STOCK_OK" -eq 0 ] && [ "$SKIP_PASSES" -eq 0 ]; then
    warn "passes not confirmed built — build_vl_gpu.py may fail"
  fi
  if [ "$HAS_PTXAS" -eq 0 ]; then
    echo "error: ptxas required for cubin" >&2
    exit 1
  fi
  BUILD_CMD=(
    python3 "$REPO_ROOT/src/tools/build_vl_gpu.py" "$MDIR_ABS" --sm "$SM"
    --clang-O "$CLANG_OPT"
  )
  [ "$FORCE_BUILD" -eq 1 ] && BUILD_CMD+=(--force)
  [ "$ANALYZE_PHASES" -eq 1 ] && BUILD_CMD+=(--analyze-phases)
  [ "$KERNEL_SPLIT_PHASES" -eq 1 ] && BUILD_CMD+=(--kernel-split-phases)
  "${BUILD_CMD[@]}"
  ok "cubin + vl_batch_gpu.meta.json"
fi

# ── 6. Hybrid binary ─────────────────────────────────────────────────────────
echo
echo "[6/7] make -C src/hybrid (run_vl_hybrid)"
HYBRID_MAKE=(make)
if [ -z "${CUDA_HOME:-}" ] && [ -f /usr/include/cuda.h ] && [ ! -f /usr/local/cuda/include/cuda.h ]; then
  HYBRID_MAKE+=(CUDA_HOME=/usr)
  warn "CUDA_HOME not set; using CUDA_HOME=/usr for src/hybrid"
fi
if "${HYBRID_MAKE[@]}" -q -C "$REPO_ROOT/src/hybrid" --no-print-directory 2>/dev/null; then
  ok "src/hybrid up to date (make skipped)"
else
  if ! "${HYBRID_MAKE[@]}" -C "$REPO_ROOT/src/hybrid" -s --no-print-directory; then
    echo "error: make -C src/hybrid failed (need CUDA driver dev headers + libcuda)" >&2
    exit 1
  fi
  ok "run_vl_hybrid built"
fi

# ── 7. Run + GPU timing (CUDA events in run_vl_hybrid.c) ────────────────────
echo
if [ "$SOCKET_M1_HOST_GPU_FLOW" -eq 1 ] && [ "$LITE" -eq 1 ]; then
  echo "[7/7] run_socket_m1_host_gpu_flow.py (--lite: nstates=$NSTATES steps=$STEPS)"
elif [ "$SOCKET_M1_HOST_GPU_FLOW" -eq 1 ]; then
  echo "[7/7] run_socket_m1_host_gpu_flow.py (nstates=$NSTATES steps=$STEPS; supported socket_m1 handoff)"
elif [ "$LITE" -eq 1 ]; then
  echo "[7/7] run_vl_hybrid.py (--lite: nstates=$NSTATES steps=$STEPS)"
else
  echo "[7/7] run_vl_hybrid.py (nstates=$NSTATES steps=$STEPS; use --lite or lower --nstates if slow)"
fi
if [ "$SKIP_RUN" -eq 1 ]; then
  warn "skipped (--skip-run)"
  print_next_steps
  exit 0
fi

if [ "$SOCKET_M1_HOST_GPU_FLOW" -eq 1 ]; then
  if ! _sock_m1_same "$MDIR_ABS" "$_SOCKET_M1_CC" && ! _sock_m1_model_present "$MDIR_ABS"; then
    echo "error: --socket-m1-host-gpu-flow requires the tlul_socket_m1 Verilator --cc directory" >&2
    exit 1
  fi
  META="$MDIR_ABS/vl_batch_gpu.meta.json"
  if ! python3 - "$META" <<'PY'
import json
import sys
from pathlib import Path

meta_path = Path(sys.argv[1])
meta = json.loads(meta_path.read_text(encoding="utf-8"))
seq = meta.get("launch_sequence") or []
ok = bool(seq) and seq[0] == "vl_ico_batch_gpu" and any(name.startswith("vl_nba_seg") for name in seq)
raise SystemExit(0 if ok else 1)
PY
  then
    echo "error: --socket-m1-host-gpu-flow requires a guarded-segment build (run without --skip-build or pass --kernel-split-phases)" >&2
    exit 1
  fi
  HYBRID_ARGS=(
    python3 "$REPO_ROOT/src/tools/run_socket_m1_host_gpu_flow.py"
    --mdir "$MDIR_ABS"
    --nstates "$NSTATES"
    --steps "$STEPS"
    --block-size "$BLOCK"
    --json-out "$MDIR_ABS/socket_m1_host_gpu_flow_summary.json"
  )
else
  HYBRID_ARGS=(
    python3 "$REPO_ROOT/src/tools/run_vl_hybrid.py"
    --mdir "$MDIR_ABS"
    --nstates "$NSTATES"
    --steps "$STEPS"
    --block-size "$BLOCK"
  )
fi
for pat in "${PATCHES[@]}"; do
  HYBRID_ARGS+=(--patch "$pat")
done

"${HYBRID_ARGS[@]}"
ok "run complete"
print_next_steps
