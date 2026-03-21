# GPU Toggle Coverage Campaigns

GPU-accelerated RTL toggle coverage collection across multiple open-source RISC-V and SoC designs, using [RTLMeter](https://github.com/verilator/rtlmeter) and a custom Verilator sim-accel backend.

## Architecture

```
RTL (SystemVerilog)
    │
    └─[Verilator sim-accel fork]─→ CUDA kernel → GPU parallel simulation
                                                        │
                                               toggle coverage bits
```

`sim-accel` is a prototype for a future Verilator MLIR emitter (→ CIRCT GPU backend). It generates CUDA kernels from Verilator's C++ output to run RTL simulation across many initial states in parallel.

## Repository Structure

```
src/
├── runners/        Execution scripts (run_veer_*, run_xuantie_*, run_openpiton_*, ...)
├── scripts/        Shared utilities and test scripts
├── generators/     Artifact generation scripts
├── grpo/           GRPO policy scripts
├── rocm/           ROCm backend scripts
├── meta/           Inventory management
└── torch_env/      Torch environment setup

config/
├── rules/                  Toggle coverage rule definitions (input to runners)
└── slice_launch_templates/ OpenTitan TLUL slice JSON templates

third_party/
├── rtlmeter/   takatodo/rtlmeter fork, feature/gpu-cov (gpu_cov + gpu_cov_gate designs)
├── verilator/  takatodo/verilator fork, feature/sim-accel-pr-clean-v2
└── circt/      llvm/circt (reference)

rtlmeter/       Python venv + requirements
work/           Build artifacts and GPU sim outputs (gitignored)
output/         Generated research artifacts: readiness reports, validation results (gitignored)
```

## Setup

```bash
git clone --recurse-submodules <this-repo>

# Install RTLMeter Python deps
python3 -m venv rtlmeter/venv
rtlmeter/venv/bin/pip install -r rtlmeter/python-requirements.txt

# Build verilator_bin from source (or copy pre-built binary)
# third_party/verilator/bin/verilator_bin must exist before running
```

## Running

```bash
# VeeR family (EL2/EH1/EH2) — outputs to work/
python3 src/runners/run_veer_family_gpu_toggle_validation.py

# XuanTie family
python3 src/runners/run_xuantie_family_gpu_toggle_validation.py

# Single baseline run
python3 src/runners/run_rtlmeter_gpu_toggle_baseline.py \
    --case VeeR-EL2:gpu_cov_gate:hello \
    --build-dir work/VeeR-EL2/gpu_cov_gate \
    --nstates 16 --gpu-reps 1
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

## Known Issues

- **VeeR GPU sim coverage 0/18**: `always_ff` conditional branch semantics lost in CUDA text generation (sim-accel architectural limitation). RTL simulation passes correctly.

## Prerequisites

- CUDA-capable GPU (sm_80+) or ROCm
- Python 3.10+
- nvcc / ROCm HIP compiler
