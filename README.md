# GPU Toggle Coverage Campaigns

GPU-accelerated RTL toggle coverage collection across multiple open-source RISC-V and SoC designs, using [RTLMeter](https://github.com/verilator/rtlmeter) and a custom Verilator sim-accel backend.

## Architecture

Primary backend: **`cuda_vl_ir`** — Verilator C++ → LLVM IR (no intermediate JSON).

```
RTL (SystemVerilog)
    │
    └─[Verilator sim-accel fork]─→ full_comb.cu + full_seq.cu  (Verilator C++)
                                          │
                                  clang++ -emit-llvm
                                          │
                                    LLVM IR (.ll)
                                          │
                                    llvm-link-18
                                          │
                                   merged.ll → llc-18 → PTX
                                          │
                                        ptxas
                                          │
                                       cubin  ← no JIT at runtime
                                          │
                                   GPU parallel simulation
                                          │
                                 toggle coverage bits
```

### Backend selection

| Backend | Description | Status |
|---------|-------------|--------|
| `cuda_vl_ir` | Verilator C++ → LLVM IR → ptxas cubin | **primary** (mismatch=20 known) |
| `rocm_llvm` | Same pipeline, AMD GPU (AMDGCN) | auto-selected on WSL2/ROCm |
| `cuda_circt_cubin` | CIRCT flow (program.json → chunked cubin) | legacy compat |

Known mismatch=20 breakdown (architectural limitations, not bugs):
- `preload_word` stub: 2 variables (array preload not yet implemented)
- `always_ff` conditional reset: ~18 variables (sim-accel limitation)

### Why Verilator C++ → LLVM IR

The previous flow (`program.json` → `program_json_to_llvm_ir.py`) split assigns into
comb/seq domains before generating LLVM IR. However, `program.json` assigns are
**interleaved across domains in global dependency order** — splitting them corrupts
execution order and produces wrong values.

Verilator C++ (`full_comb.cu` + `full_seq.cu`) preserves this order correctly.
`clang++ -emit-llvm` lowers it directly to LLVM IR. No `nvcc`/`hipcc` required —
only `clang-18`, `llvm-link-18`, `llc-18`, and `ptxas`.

## Repository Structure

```
src/
├── runners/        Execution scripts (run_veer_*, run_xuantie_*, run_opentitan_*, ...)
├── scripts/        Shared utilities and test scripts
├── sim_accel/      GPU kernel build pipeline (build_bench_bundle.py, etc.)
├── generators/     Artifact generation scripts
├── grpo/           GRPO policy scripts
├── rocm/           ROCm backend scripts
└── meta/           Inventory management

config/
├── rules/                  Toggle coverage rule definitions (input to runners)
└── slice_launch_templates/ OpenTitan TLUL slice JSON templates

third_party/
├── rtlmeter/   takatodo/rtlmeter fork, feature/gpu-cov (gpu_cov + gpu_cov_gate designs)
├── verilator/  takatodo/verilator fork, feature/sim-accel-pr-clean-v2
└── circt/      llvm/circt (reference)

rtlmeter/       Python venv + requirements
work/           Build artifacts and GPU sim outputs (gitignored)
output/         Generated research artifacts (gitignored)
```

## Quick Start

`./quickstart.sh` initializes submodules, creates the RTLMeter venv, runs unit tests,
and (if GPU + bench binary are present) runs a short VeeR-EL2 smoke job with `cuda_vl_ir`.

```bash
git clone --recurse-submodules <this-repo-url>
cd gpu-toggle-coverage-campaigns

./quickstart.sh              # checks + optional smoke run
./quickstart.sh --skip-run   # checks only (skip GPU smoke)
```

## Setup (manual)

```bash
git clone --recurse-submodules <this-repo-url>

# RTLMeter Python deps (venv path rtlmeter/venv matches quickstart.sh)
python3 -m venv rtlmeter/venv
rtlmeter/venv/bin/pip install -r rtlmeter/python-requirements.txt

# Build the Verilator sim-accel fork (or install a matching prebuilt binary).
# Runners expect third_party/verilator/bin/verilator_sim_accel_bench
# Example: cd third_party/verilator && ./configure && make -j"$(nproc)"
```

## Running

```bash
# VeeR family (EL2/EH1/EH2) — outputs to work/
python3 src/runners/run_veer_family_gpu_toggle_validation.py

# XuanTie family
python3 src/runners/run_xuantie_family_gpu_toggle_validation.py

# Single baseline run (cuda_vl_ir by default)
python3 src/runners/run_rtlmeter_gpu_toggle_baseline.py \
    --case VeeR-EL2:gpu_cov_gate:hello \
    --build-dir work/VeeR-EL2/gpu_cov_gate \
    --nstates 256 --gpu-reps 1
```

## Design Coverage Status

| Design | Family | Status | Rule |
|--------|--------|--------|------|
| VeeR-EL2/EH1/EH2 | VeeR | gate_validated | balanced_source_general |
| XuanTie-E902/E906 | XuanTie | actual_gpu (18/18) | balanced_source_general |
| XuanTie-C906/C910 | XuanTie | actual_gpu | balanced_source_general |
| Vortex | — | actual_gpu | balanced_source_general |
| XiangShan | — | actual_gpu | balanced_source_general |
| BlackParrot | — | actual_gpu | balanced_source_general |
| OpenPiton | — | actual_gpu | balanced_source_general |
| OpenTitan | Slice scope | slice_scope_validated | (per-slice) |
| Caliptra | Phase 4 | gpu_cov_codegen_proven | TBD |

## Known Limitations

- **mismatch=20 on VeeR-EL2** (`cuda_vl_ir`): 2 vars from unimplemented `preload_word` stub,
  ~18 vars from `always_ff` conditional reset semantics (sim-accel architectural limit).
  RTL simulation passes correctly; GPU toggle counts are accurate for the remaining signals.

## Prerequisites

- CUDA-capable GPU (sm_80+) or ROCm GPU
- Python 3.10+
- LLVM 18: `clang-18`, `llvm-link-18`, `llc-18`
- `ptxas` (from CUDA toolkit)
- `third_party/verilator/bin/verilator_sim_accel_bench` (sim-accel fork build output)
