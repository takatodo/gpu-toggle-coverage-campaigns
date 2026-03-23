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

## Experimental: Standard Verilator → LLVM IR → GPU

An experimental flow lives under `work/vl_ir_exp/` (see also `work/circt_exp/gen_vl_gpu_kernel.py`).

**Motivation:** The CIRCT path does not support `seq.firmem` or combinational loops, which blocks
tlul_socket_1n / crossbar-style designs. **Stock Verilator** can compile complex SystemVerilog,
including UVM. This path reuses that frontend strength to emit GPU kernels **without** the sim-accel fork.

```
RTL (SystemVerilog)
    │
    └─[stock Verilator --cc --flatten]─→ V*.cpp  (ordinary C++ simulator output)
                                              │
                                      clang++-18 -S -emit-llvm -O1
                                              │ (multiple .ll)
                                      llvm-link-18 → merged.ll
                                              │
                                  gen_vl_gpu_kernel.py <merged.ll> <storage_size>
                                    · extract only functions reachable from _eval
                                    · replace VL_FATAL_MT etc. with no-op stubs
                                    · set NVPTX target metadata
                                    · add AoS-strided kernel
                                      (thread i → _eval(base + i * storage_size))
                                              │
                                      opt-18 -O3 → llc-18 -march=nvptx64 → ptxas
                                              │
                                           cubin
```

**Status (2026-03-23):**

| Slice | storage_size | cubin | ns/state/cycle (65K states) |
|----------|-------------|-------|-----------------------------|
| tlul_request_loopback | 192 bytes | ✓ | ~2.6 ns |
| tlul_socket_m1 | 2048 bytes | ✓ | ~13.5 ns |

**Convergence loop workaround (`patch_convergence_exit`):**

When Verilator is built with `--no-timing`, timed testbench constructs such as
`always #5 clk_i = ~clk_i` become combinational feedback loops. Then `eval_phase__ico`
stays true and the convergence loop never terminates.

`patch_convergence_exit` in `gen_vl_gpu_kernel.py` applies these CFG edits:
1. **Fatal block redirect:** after `VL_FATAL_MT`, rewrite `br label %BODY` → `br label %EXIT`.
2. **Single-pass threshold:** `icmp ugt i32 %N, 100` → `icmp ugt i32 %N, 0`
   (fatal fires after the first body iteration → exit the convergence loop in at most 2 iterations).
3. **VerilatedSyms stub:** functions that touch the vlSyms pointer (field `[6]`), e.g. `nba_comb`,
   are stubbed at runtime (zero-initialized buffer avoids NULL dereferences).

**Comparison vs. CIRCT path:**

| Aspect | CIRCT arc | Stock Verilator IR |
|--------|-----------|-------------------|
| `seq.firmem` | ✗ | ✓ (handled by Verilator) |
| Combinational loops | ✗ | ✓ |
| UVM | ✗ | ✓ |
| tlul_socket_m1 | ✗ (blocked on firmem) | ✓ (cubin built and run) |
| Storage size | 156 bytes (loopback) | 192 bytes (loopback), 2048 bytes (socket_m1) |
| Extern stubs | not required | `VL_FATAL_MT` + VerilatedSyms-related |

**Files:**
- `src/tools/gen_vl_gpu_kernel.py` — merged.ll → NVPTX GPU kernel generator
- `src/tools/build_vl_gpu.py` — Verilator `--cc` output dir → cubin build driver
- `work/vl_ir_exp/loopback_vl/` — tlul_request_loopback: Verilator C++ / LLVM IR / cubin
- `work/vl_ir_exp/socket_m1_vl/` — tlul_socket_m1: Verilator C++ / LLVM IR / cubin
- `work/vl_ir_exp/bench_vl_sweep.cu` — NSTATES sweep benchmark (`STORAGE_SIZE` macro)

### Python layout (current)

`gen_vl_gpu_kernel.py` is the orchestrator only; IR transforms live in four modules:

| File | Role |
|------|------|
| `llvm_ir_parse.py` | IR text → dict/set (pure) |
| `llvm_ir_patch.py` | `strip_x86_attrs`, `lower_invoke_to_call`, `patch_convergence_exit` |
| `llvm_stub_gen.py` | no-op stubs for external functions |
| `vl_runtime_filter.py` | `is_runtime()`, `detect_vlsyms_offset()` |

### C++ pass migration plan

Move regex-based IR edits in Python to LLVM C++ passes incrementally.
Goal: plug into the stock LLVM pipeline via `opt -load-pass-plugin=vl_gpu_passes.so`.

**Python step → LLVM C++ mapping:**

| Python | Kind | C++ |
|--------|------|-----|
| `lower_invoke_to_call` | strip EH | `-lowerinvoke` **built-in pass** (no custom code) |
| `strip_x86_attrs` | strip attrs | custom `FunctionPass` |
| `patch_convergence_exit` | CFG edit | custom `FunctionPass` |
| `make_no_op_stub` | extern → define | custom `ModulePass` |
| `reachable_from` + `is_runtime` | reachability / filtering | custom `ModulePass` (CallGraph) |
| `detect_vlsyms_offset` | TBAA scrape | inside `ModulePass` or keep in Python |
| kernel wrapper | inject function | custom `ModulePass` |

**Phased rollout:**

| Phase | Work | Touch points |
|-------|------|--------------|
| 1 | Drop `lower_invoke_to_call`; use `-lowerinvoke` | add `-passes=lowerinvoke` to `opt` in `build_vl_gpu.py`; remove the Python helper from `llvm_ir_patch.py` |
| 2 | Implement `VlStripX86Attrs` + `VlPatchConvergence` as `FunctionPass`es | `src/passes/VlGpuPasses.cpp` + CMakeLists |
| 3 | Implement `VlStubRuntime` + `VlInjectKernel` as `ModulePass`es; retire Python | fold into standalone `vlgpugen` tool |

**Target pipeline (after phase 3):**

```
merged.ll
    ↓
vlgpugen merged.ll --storage-size=N --sm=sm_89
    (LLVM API: CallGraph reachability → stub injection → kernel insertion)
    ↓
vl_batch_gpu.ll
    ↓
opt -O3 | llc -march=nvptx64 | ptxas
    ↓
cubin
```

**LLVM version bumps:**

After the Python migration, only four constants in `build_vl_gpu.py` need updating (`CLANG` / `LLVMLINK` / `OPT` / `LLC`).
Before migration, watch:
- `_clean_param_type` attribute lists — new LLVM attrs can break stub parsing
- `detect_vlsyms_offset` `"any pointer"` pattern — TBAA shape changes can mis-detect offsets
- `NVPTX_DATALAYOUT` — must match the new LLVM version’s expectations

## Goal: Hybrid CPU-GPU Architecture

The long-term goal is **hybrid CPU–GPU execution using the stock Verilator frontend**:
no sim-accel fork, and broad design coverage including UVM, `seq.firmem`, and combinational loops.

```
CPU (host)                          GPU (device)
─────────────────────────────────   ───────────────────────────────────
constructors / initial values       ___ico_sequent  (combinational eval)
rst_n drive / reset sequencing      ___nba_sequent  (sequential assigns)
clk toggle (write all NSTATES)  →   eval kernel × NSTATES threads
toggle bit readback             ←
assertions, tracing (stub OK)
```

**Target build flow:**

```
verilator --cc --flatten
    │
    ├─ inject CXX="clang++ -emit-llvm" into Makefile
    │       ↓
    │   merged.ll
    │       ↓ classify functions
    │   GPU: ico_sequent / nba_sequent
    │        (single pointer arg, no unsafe extern side effects)
    │       ↓
    │   gen_vl_gpu_kernel.py → opt/llc/ptxas → cubin
    │
    └─ CPU: init / clk drive / collect
            ↓
        plain clang++ → host binary
            ↓
    Hybrid runtime (load host binary + cubin)
```

**Benefits:**

| Aspect | sim-accel fork | **Hybrid (target)** |
|--------|----------------|---------------------|
| sim-accel dependency | required | none |
| UVM / firmem | ✗ | ✓ (stock Verilator) |
| Combinational loops | ✗ | ✓ |
| GPU region selection | hard-coded in fork | structural analysis / automation |
| Applicability | validated designs (VeeR, XuanTie, …) | arbitrary SystemVerilog |

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
