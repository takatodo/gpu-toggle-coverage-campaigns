# GPU Toggle Coverage Campaigns

GPU-accelerated RTL toggle coverage collection across multiple open-source RISC-V and SoC designs, using [RTLMeter](https://github.com/verilator/rtlmeter) and LLVM/NVPTX toolchains where applicable.

## Architecture

**Recommended path — stock Verilator → LLVM IR → cubin** (no sim-accel fork):

New work uses **normal `verilator --cc`** output, `clang++ -emit-llvm`, **`vlgpugen`**, and `opt`/`llc`/`ptxas` — see *Experimental: Standard Verilator → LLVM IR → GPU* below and `src/tools/build_vl_gpu.py`.

### Backend selection (RTLMeter / legacy runners)

| Backend | Description | Status |
|---------|-------------|--------|
| **Stock path** | `verilator --cc` → `vlgpugen` → `opt` → PTX/cubin | **recommended** for new GPU IR |
| `cuda_vl_ir` | sim-accel `full_comb`/`full_seq` → LLVM → cubin (inside `verilator_sim_accel_bench`) | **legacy** — semantic mismatches vs RTL |
| `rocm_llvm` | Same class of flow as `cuda_vl_ir`, AMD GPU | legacy / environment-specific |
| `cuda_circt_cubin` | CIRCT flow (`program.json` → chunked cubin) | legacy compat |

## Repository Structure

```
src/
├── runners/        Execution scripts (run_veer_*, run_xuantie_*, run_opentitan_*, ...)
├── scripts/        Shared utilities and test scripts
├── hybrid/         Minimal CUDA driver stub (run_vl_hybrid) for stock-Verilator cubin
├── sim_accel/      Legacy sim-accel / RTLMeter bench helpers (build_bench_bundle.py, etc.)
├── generators/     Artifact generation scripts
├── grpo/           GRPO policy scripts
├── rocm/           ROCm backend scripts
└── meta/           Inventory management

config/
├── rules/                  Toggle coverage rule definitions (input to runners)
└── slice_launch_templates/ OpenTitan TLUL slice JSON templates

docs/
└── phase_b_ico_nba_spike.md  Phase B notes (ico/nba multi-kernel direction)

third_party/
├── rtlmeter/   takatodo/rtlmeter fork, feature/gpu-cov (gpu_cov + gpu_cov_gate designs)
├── verilator/  optional: sim-accel fork (legacy RTLMeter bench only — not required for stock + vlgpugen)
└── circt/      llvm/circt (reference)

rtlmeter/       Python venv + requirements
work/           Build artifacts and GPU sim outputs (gitignored)
output/         Generated research artifacts (gitignored)
```

## Quick Start

`./quickstart.sh` initializes submodules, creates the RTLMeter venv, checks `nvcc`/ROCm, builds
`src/passes` (`vlgpugen`, `VlGpuPasses.so`) when LLVM-18 is present, and runs unit tests.
**Sim-accel VeeR smoke is off by default** (fork semantics unreliable); opt in with
`--legacy-sim-accel-smoke` if you still have `verilator_sim_accel_bench`.

```bash
git clone --recurse-submodules <this-repo-url>
cd gpu-toggle-coverage-campaigns

./quickstart.sh                          # checks + passes build; no sim-accel smoke
./quickstart.sh --legacy-sim-accel-smoke # optional: old VeeR cuda_vl_ir bench smoke
./quickstart.sh --skip-run               # skip step 7 entirely (no messages / no legacy smoke)
./quickstart.sh --skip-passes            # skip make -C src/passes
```

## Setup (manual)

```bash
git clone --recurse-submodules <this-repo-url>

# RTLMeter Python deps (venv path rtlmeter/venv matches quickstart.sh)
python3 -m venv rtlmeter/venv
rtlmeter/venv/bin/pip install -r rtlmeter/python-requirements.txt

# Stock Verilator GPU path: system Verilator (or any --cc output), LLVM 18, CUDA ptxas.
# See: python3 src/tools/build_vl_gpu.py <verilator-cc-dir>
#
# Legacy only: sim-accel fork + verilator_sim_accel_bench for old RTLMeter cuda_vl_ir runners.
```

## Running

```bash
# Stock Verilator → cubin (recommended)
python3 src/tools/build_vl_gpu.py <path-to-verilator--cc-output-dir> [--sm sm_89]
# Phase B: print ___ico_sequent / ___nba_* reachability after merged.ll, then continue to cubin:
#   python3 src/tools/build_vl_gpu.py <mdir> --analyze-phases
# Headers should match the Verilator that generated mdir: default include is third_party/verilator/include;
# set VERILATOR_ROOT or VL_INCLUDE to override (see build_vl_gpu.verilator_include_dir). Emit-LLVM uses -std=c++20.

# Load cubin + launch vl_eval_batch_gpu (Phase D skeleton)
make -C src/hybrid
python3 src/tools/run_vl_hybrid.py --mdir <same-verilator-cc-dir> [--nstates N] [--steps S] [--patch off:byte ...]

# Same path as a quickstart-style script (checks, build_vl_gpu, hybrid binary, run + GPU timing)
./quickstart_hybrid.sh --mdir <same-verilator-cc-dir> [--steps S] [--patch off:byte ...]
# With no args, default --mdir is work/vl_ir_exp/socket_m1_vl: the script mkdirs it if missing and runs
# src/tools/bootstrap_hybrid_socket_m1_cc.py (stock Verilator --cc) when *_classes.mk is absent. Use --no-bootstrap to skip.
# After a full run, ./quickstart_hybrid.sh --fast reuses cubin + skips submodule/git and make when up to date.
# ./quickstart_hybrid.sh --analyze-phases forwards Phase B reporting into build_vl_gpu.py.
# Step 7 defaults to --nstates 256 (not 4096) to keep GPU launch light; use --nstates 4096 or --lite (64) as needed.

# VeeR family (legacy RTLMeter + sim-accel backends) — outputs to work/
python3 src/runners/run_veer_family_gpu_toggle_validation.py

# XuanTie family
python3 src/runners/run_xuantie_family_gpu_toggle_validation.py

# Single baseline (defaults to cuda_vl_ir — legacy sim-accel bench)
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
                                  vlgpugen merged.ll --storage-size=N --out=vl_batch_gpu.ll
                                    · reachable from _eval, runtime vs GPU split
                                    · stub externs + drop host-only globals
                                    · NVPTX datalayout/triple, @fake_syms_buf, AoS kernel
                                              │
                                  opt-18 (lowerinvoke + VlGpuPasses.so) → opt -O3
                                              │
                                      llc-18 -march=nvptx64 → ptxas
                                              │
                                           cubin
```

**Status (2026-03-23):**

| Slice | storage_size | cubin | ns/state/cycle (65K states) |
|----------|-------------|-------|-----------------------------|
| tlul_request_loopback | 192 bytes | ✓ | ~2.6 ns |
| tlul_socket_m1 | 2048 bytes | ✓ | ~13.5 ns |

**Convergence loop and runtime safety:**

When Verilator is built with `--no-timing`, timed testbench constructs such as
`always #5 clk_i = ~clk_i` become combinational feedback loops. Then `eval_phase__ico`
stays true and the convergence loop never terminates.

1–2 are implemented in LLVM IR by **`VlPatchConvergencePass`** (`src/passes/VlGpuPasses.cpp`), run from
`build_vl_gpu.py` via `opt-18 --load-pass-plugin=... -passes=lowerinvoke,simplifycfg,vl-strip-x86-attrs,vl-patch-convergence`:

1. **Fatal block redirect:** after `VL_FATAL_MT`, rewrite the fatal block’s branch to `%exit` instead of `%body`.
2. **Single-pass threshold:** `icmp ugt i32 %N, 100` → `icmp ugt i32 %N, 0`
   (fatal after the first body iteration → at most two iterations to leave the loop).

3. **VerilatedSyms / vlSymsp:** handled in **`vlgpugen`** (generation mode): TBAA regex finds the field
   offset; `@fake_syms_buf` is stored into each state’s `vlSymsp` slot before calling `_eval`.

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
- `src/passes/vlgpugen.cpp` — **production** merged.ll → `vl_batch_gpu.ll` (analysis or `--out` generation)
- `src/tools/build_vl_gpu.py` — Verilator `--cc` output dir → cubin (`vlgpugen` + `opt` + `VlGpuPasses.so`)
- `src/passes/VlGpuPasses.cpp` — `vl-strip-x86-attrs`, `vl-patch-convergence` (plugin `.so`)
- `src/tools/gen_vl_gpu_kernel.py` — legacy Python path (reference / parity checks vs `vlgpugen`)
- `work/vl_ir_exp/loopback_vl/` — tlul_request_loopback: Verilator C++ / LLVM IR / cubin
- `work/vl_ir_exp/socket_m1_vl/` — tlul_socket_m1: Verilator C++ / LLVM IR / cubin
- `work/vl_ir_exp/bench_vl_sweep.cu` — NSTATES sweep benchmark (`STORAGE_SIZE` macro)

### Pipeline layout (current)

| Stage | Location | Responsibility |
|-------|----------|----------------|
| Reachability, runtime split, stubs, host globals, kernel, TBAA offset | **`vlgpugen`** (`--out`) | Replaces former `gen_vl_gpu_kernel.py` pipeline (Phase 3) |
| EH lowering | `opt -passes=lowerinvoke` | `invoke` → `call` (LLVM built-in) |
| Strip x86 / convergence CFG | `VlGpuPasses.so` | `vl-strip-x86-attrs`, `vl-patch-convergence` |

**Reference Python (parity / experiments only):**

| File | Role |
|------|------|
| `llvm_ir_parse.py` | Text IR helpers used by `gen_vl_gpu_kernel.py` |
| `llvm_stub_gen.py` | Stub text generation (Python path) |
| `vl_runtime_filter.py` | Same heuristics as `vlgpugen`’s `isRuntimeFunction` |

There is **no** `llvm_ir_patch.py`; lowering and CFG/attribute fixes run in `opt`, not ad-hoc regex passes on `.ll`.

### C++ pass migration plan

**Option A — `opt` plugin + Python orchestrator (superseded for stock-Verilator GPU IR):** was used while
stub/kernel emission lived in `gen_vl_gpu_kernel.py`. **Production now uses Option B** (`vlgpugen`) for
that stage; `opt` + `VlGpuPasses.so` are unchanged downstream.

**Option B — `vlgpugen` (production for merged.ll → `vl_batch_gpu.ll`):** LLVM API + typed IR transforms;
host-global cleanup and kernel injection live here. Build: `make -C src/passes` (links `libLLVM-18`).

**Option A vs. Option B:**

| | **Option A** (`opt` plugin + Python) | **Option B** (`vlgpugen`) |
|---|--------------------------------------|---------------------------|
| **IR representation** | Text `.ll`; Python regex/splicing + `opt` on the same file | In-memory `Module`; no string IR edits |
| **Entry commands** | `gen_vl_gpu_kernel.py` → `opt` … → `ptxas` (reference only) | `vlgpugen … --out=vl_batch_gpu.ll` → `opt` (plugin + built-ins) → `opt -O3` → `llc` → `ptxas` |
| **Reachability / stubs / kernel** | Python text IR + helpers | **`vlgpugen`** (LLVM `Module` API: BFS, stubs, globals, kernel) |
| **Build** | `python3` + optional scripts | `make -C src/passes` → `vlgpugen` + `VlGpuPasses.so` (links `libLLVM`) |
| **Pros** | Easy to diff against C++ for parity | Typed IR; production path for `build_vl_gpu.py` |
| **Cons** | Not used in default cubin build anymore | LLVM major-version upgrades require rebuild + occasional API tweaks |
| **Fit** | Legacy / diff vs `vlgpugen` | **Production** stock-Verilator path (Phase 3 complete) |

**Logic → implementation (after Phase 3):**

| Logic | Kind | Where |
|-------|------|--------|
| EH | strip exception handling | `-lowerinvoke` (`opt`) |
| x86 noise | attrs / comdat / personality | `VlStripX86AttrsPass` |
| convergence loop | CFG | `VlPatchConvergencePass` |
| stubs + reachable + kernel + TBAA offset + host globals | IR rewrite | **`vlgpugen`** (`--out`) |

**Phased rollout:**

| Phase | Status | Work |
|-------|--------|------|
| 1 | **done** | `lowerinvoke` only via `opt` in `build_vl_gpu.py` (no Python `lower_invoke_to_call`) |
| 2 | **done** | `VlStripX86Attrs` + `VlPatchConvergence` in `src/passes/VlGpuPasses.cpp` + `src/passes/Makefile` |
| 3 | **done** | `vlgpugen`: full generation (stubs, host-global removal, kernel, NVPTX module). `build_vl_gpu.py` invokes `vlgpugen` instead of `gen_vl_gpu_kernel.py`. |

**Verified (representative tlul slice build):** `make -C src/passes` succeeds; analysis reports eval + reachable
functions (e.g. **14** reachable, **11** GPU / **3** runtime), **vlSymsp** offset **2000** bytes; generation
stubs **6** extern calls, removes **6** host-only globals, emits `vl_batch_gpu.ll`; end-to-end cubin **~71 KiB**,
matching the previous Python generator output.

**vlgpugen usage:**

```bash
make -C src/passes
# analysis only (no --out): summary to stdout
./src/passes/vlgpugen path/to/merged.ll
# generation mode
./src/passes/vlgpugen path/to/merged.ll --storage-size=N --out=vl_batch_gpu.ll
```

**LLVM version bumps:**

Update the tool paths in `build_vl_gpu.py` (`CLANG` / `LLVMLINK` / `OPT` / `LLC`) and rebuild `vlgpugen` / `VlGpuPasses.so` against the same LLVM. When bumping LLVM, also watch:
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
    │   vlgpugen → opt/llc/ptxas → cubin
    │
    └─ CPU: init / clk drive / collect
            ↓
        plain clang++ → host binary
            ↓
    Hybrid runtime (load host binary + cubin)
```

**Roadmap — steps from today’s pipeline to hybrid runtime**

| Phase | What exists / what to build | Outcome |
|-------|-----------------------------|---------|
| **A — done** | `build_vl_gpu.py`: Verilator `--cc` → `.ll` → **`vlgpugen`** → `opt` + `VlGpuPasses.so` → cubin | Single **batch `_eval`** kernel over many states (AoS); runtime/host calls stubbed; `VlPatchConvergence` for `--no-timing` TB loops |
| **B** | **Timestep / phase fidelity:** align GPU execution with RTL time steps (multi-`eval`, ico/nba ordering, or explicit sched) where one batched `_eval` is insufficient | Reduces semantic gap vs event-driven RTL sim; may require IR slicing or multi-kernel launch |
| **C** | **CPU slice:** compile non-kernel functions with normal `clang++` (init, monitors, DPI hooks, assertion bodies) into a **host** binary; define a narrow ABI (storage layout, syms, toggle bitmap) | Host does constructors, reset sequencing, optional single-step debug path |
| **D** | **Hybrid driver:** one process loads **host .so/.exe + cubin**; drives `clk`/`rst` on CPU, copies or maps state, launches GPU kernels per batch, **pulls toggle bits** back | End-to-end toggle campaign without sim-accel; replaces ad-hoc `bench_vl_sweep.cu`-style harnesses |
| **E** | **Automatic GPU/CPU classification:** static analysis on Verilator IR (or LLVM) to mark safe GPU regions vs must-stay-on-host (I/O, time, `$display`) | Scales beyond hand-tuned `is_runtime` lists |

**Phase D (minimal, implemented):** after `build_vl_gpu.py`, `vl_batch_gpu.meta.json` records `cubin`, `storage_size`, `sm`, `schema_version`. Build and run the CUDA Driver stub:

```bash
make -C src/hybrid    # produces src/hybrid/run_vl_hybrid (needs CUDA headers + libcuda)
python3 src/tools/run_vl_hybrid.py --mdir <verilator-cc-dir> [--nstates 4096]
```

This loads `vl_batch_gpu.cubin`, zero-fills device storage (`nstates * storage_size`), and launches `@vl_eval_batch_gpu` (grid/block layout matches the LLVM kernel). Use **`--steps`** and **`--patch global_offset:byte`** on `run_vl_hybrid.py` to repeat launches with host-injected bytes (minimal CPU time axis). No full CPU-side Verilator link yet — see `src/hybrid/host_abi.h` and `make host_stub`.

**Per-launch cost:** one launch = one `_eval` per `nstates` slot; time ~ **(_eval work) × nstates × steps** (design-dependent, not “one cycle”). Lighten with smaller `--cc` / TB, lower `--nstates` / `--steps`, or `--lite`; profile with `nsys` if needed. **Shorter `_eval` IR:** `build_vl_gpu.py --clang-O O3` (or `quickstart_hybrid.sh --fast-sim`) re-emits `.ll` with heavier clang opt; rebuild with `--force` or change opt level (tracked via `mdir/.vl_gpu_clang_opt`).

**WSL2:** If `nvidia-smi` works but `run_vl_hybrid` fails with CUDA error 100 (no device), prepend the host driver library path: `export LD_LIBRARY_PATH=/usr/lib/wsl/lib:$LD_LIBRARY_PATH` — `run_vl_hybrid.py` and `quickstart_hybrid.sh` do this automatically when `/usr/lib/wsl/lib/libcuda.so.1` exists.

**Wall clock:** By default `run_vl_hybrid` uses **one** `cuCtxSynchronize()` after all `--steps` (fewer host–GPU round trips). For per-step sync (old behavior), set `RUN_VL_HYBRID_SYNC_EACH_STEP=1`. For a one-off untimed launch to hide first-kernel latency, set `RUN_VL_HYBRID_WARMUP=1`.

**Phase B spike:** `vlgpugen --analyze-phases <merged.ll>` reports whether `___ico_sequent` / `___nba_comb` / `___nba_sequent` appear reachable from `_eval`. See [docs/phase_b_ico_nba_spike.md](docs/phase_b_ico_nba_spike.md).

**Phase E prototype:** `vlgpugen` uses LLVM **CallGraph**-based callee hints merged with `isRuntimeFunction` (see `classifyRuntimeFunctions` in `vlgpugen.cpp`).

Dependencies: **B** may feed into **C** (what must stay on host). **D** can start with a minimal host that only drives clocks and collects toggles before full assertion parity.

**Benefits:**

| Aspect | sim-accel fork | **Hybrid (target)** |
|--------|----------------|---------------------|
| sim-accel dependency | required | none |
| UVM / firmem | ✗ | ✓ (stock Verilator) |
| Combinational loops | ✗ | ✓ |
| GPU region selection | hard-coded in fork | structural analysis / automation |
| Applicability | validated designs (VeeR, XuanTie, …) | arbitrary SystemVerilog |

## Known Limitations

- **Legacy `cuda_vl_ir` / sim-accel fork:** RTL vs GPU toggle mismatch (e.g. `preload_word`, `always_ff`
  conditional reset) — **this is why sim-accel is not the recommended path**; use stock Verilator + `vlgpugen`.

## Prerequisites

- CUDA-capable GPU (sm_80+) or ROCm GPU (for cubin execution and `ptxas` / drivers)
- Python 3.10+
- **Stock GPU IR path:** LLVM 18 (`clang++-18`, `llvm-link-18`, `opt-18`, `llc-18`), `ptxas`, `make -C src/passes`
- **Legacy RTLMeter bench:** `third_party/verilator/bin/verilator_sim_accel_bench` (sim-accel fork) — optional
