#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import textwrap
import time
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent.parent
PROGRAM_JSON_TO_FULL_ALL = ROOT_DIR / "src/sim_accel/program_json_to_full_all.py"
DEFAULT_OUT_DIR = Path("/tmp/rocm_native_hsaco_mainline_probe_v1")
DEFAULT_SUMMARY_JSON = SCRIPT_DIR / "rocm_native_hsaco_mainline_probe.json"
DEFAULT_SUMMARY_MD = SCRIPT_DIR / "rocm_native_hsaco_mainline_probe.md"
DEFAULT_PROGRAM_JSON = Path(
    "/tmp/opentitan_tlul_slice_generated_dir_cache/tlul_fifo_sync/raw/"
    "tlul_fifo_sync_gpu_cov_tb.sim_accel.program.json"
)
DEFAULT_LINK = Path("/tmp/opentitan_tlul_slice_generated_dir_cache/tlul_fifo_sync/fused/kernel_generated.link.cu")
ROCM_LLVM_BIN = Path("/opt/rocm-7.2.0/lib/llvm/bin")


HOST_TEMPLATE = textwrap.dedent(
    """\
    #include <hip/hip_runtime.h>

    #include <cstdint>
    #include <cstdio>
    #include <cstdlib>
    #include <vector>

    namespace {
    constexpr uint32_t kStateVarCount = __STATE_VAR_COUNT__U;
    constexpr uint32_t kStateWidths[kStateVarCount] = {__STATE_WIDTHS__};
    static uint32_t g_preload_state_count = 0U;

    static void check(hipError_t status, const char* what) {
      if (status != hipSuccess) {
        std::fprintf(stderr, "%s: %s\\n", what, hipGetErrorString(status));
        std::fflush(stderr);
        std::exit(1);
      }
    }

    static uint64_t mix64(uint64_t x) {
      x ^= x >> 30;
      x *= 0xbf58476d1ce4e5b9ULL;
      x ^= x >> 27;
      x *= 0x94d049bb133111ebULL;
      x ^= x >> 31;
      return x;
    }

    static uint64_t mask_width(uint64_t value, uint32_t width) {
      if (width >= 64U) return value;
      if (width == 0U) return 0ULL;
      return value & ((1ULL << width) - 1ULL);
    }
    }  // namespace

    extern "C" void sim_accel_eval_assignw_cpu_ref(const uint64_t* state_in,
                                                   uint64_t* state_out,
                                                   uint32_t nstates);
    extern "C" uint32_t sim_accel_eval_preload_runtime_resize(uint32_t nstates) {
      g_preload_state_count = nstates;
      return 0U;
    }
    extern "C" uint32_t sim_accel_eval_preload_runtime_state_count() {
      return g_preload_state_count;
    }
    extern "C" uint32_t sim_accel_eval_preload_target_apply_word_range(
        uint32_t, uint32_t, uint32_t, uint32_t, uint64_t) {
      return 0U;
    }
    extern "C" uint64_t sim_accel_eval_preload_target_runtime_word(
        uint32_t, uint32_t, uint32_t) {
      return 0ULL;
    }

    int main(int argc, char** argv) {
      const char* hsaco = argc > 1 ? argv[1] : "";
      const uint32_t nstates = argc > 2 ? static_cast<uint32_t>(std::strtoul(argv[2], nullptr, 10))
                                        : 4U;
      if (!hsaco || !hsaco[0]) {
        std::fprintf(stderr, "missing hsaco path\\n");
        return 2;
      }
      if (nstates == 0U) {
        std::fprintf(stderr, "nstates must be > 0\\n");
        return 2;
      }

      const size_t total_words = static_cast<size_t>(nstates) * kStateVarCount;
      std::vector<uint64_t> state_in(total_words);
      std::vector<uint64_t> cpu_out = state_in;
      std::vector<uint64_t> gpu_out(total_words, 0ULL);
      for (uint32_t var = 0; var < kStateVarCount; ++var) {
        for (uint32_t tid = 0; tid < nstates; ++tid) {
          const size_t i = static_cast<size_t>(var) * nstates + tid;
          state_in[i] = mask_width(mix64(0x9e3779b97f4a7c15ULL + i), kStateWidths[var]);
        }
      }

      sim_accel_eval_preload_runtime_resize(nstates);
      sim_accel_eval_assignw_cpu_ref(state_in.data(), cpu_out.data(), nstates);

      hipDeviceProp_t props{};
      check(hipGetDeviceProperties(&props, 0), "hipGetDeviceProperties");

      uint64_t* d_in = nullptr;
      uint64_t* d_out = nullptr;
      check(hipMalloc(&d_in, total_words * sizeof(uint64_t)), "hipMalloc d_in");
      check(hipMalloc(&d_out, total_words * sizeof(uint64_t)), "hipMalloc d_out");
      check(
          hipMemcpy(d_in, state_in.data(), total_words * sizeof(uint64_t), hipMemcpyHostToDevice),
          "hipMemcpy H2D input");
      check(
          hipMemcpy(d_out, state_in.data(), total_words * sizeof(uint64_t), hipMemcpyHostToDevice),
          "hipMemcpy H2D output seed");

      hipModule_t module{};
      hipFunction_t func{};
      check(hipModuleLoad(&module, hsaco), "hipModuleLoad");
      check(hipModuleGetFunction(&func, module, "sim_accel_eval_assignw_u32_full_all"),
            "hipModuleGetFunction");

      void* kernel_args[] = {&d_in, &d_out, const_cast<uint32_t*>(&nstates)};
      const unsigned block_x = 64U;
      const unsigned grid_x = (nstates + block_x - 1U) / block_x;
      check(
          hipModuleLaunchKernel(
              func, grid_x, 1, 1, block_x, 1, 1, 0, 0, kernel_args, nullptr),
          "hipModuleLaunchKernel");
      check(hipDeviceSynchronize(), "hipDeviceSynchronize");
      check(
          hipMemcpy(gpu_out.data(), d_out, total_words * sizeof(uint64_t), hipMemcpyDeviceToHost),
          "hipMemcpy D2H");

      size_t mismatch = 0;
      size_t first_index = static_cast<size_t>(-1);
      uint64_t first_expected = 0ULL;
      uint64_t first_actual = 0ULL;
      for (size_t i = 0; i < total_words; ++i) {
        if (cpu_out[i] != gpu_out[i]) {
          if (mismatch == 0U) {
            first_index = i;
            first_expected = cpu_out[i];
            first_actual = gpu_out[i];
          }
          ++mismatch;
        }
      }

      std::printf("runtime_gpu_api=hip\\n");
      std::printf("runtime_gpu_platform=amd\\n");
      std::printf("runtime_gpu_device_name=%s\\n", props.name);
      std::printf("runtime_gpu_arch_name=%s\\n", props.gcnArchName);
      std::printf("nstates=%u\\n", nstates);
      std::printf("state_var_count=%u\\n", kStateVarCount);
      std::printf("mismatch=%zu\\n", mismatch);
      if (mismatch != 0U) {
        std::printf("first_mismatch_index=%zu\\n", first_index);
        std::printf("first_expected=%llu\\n", static_cast<unsigned long long>(first_expected));
        std::printf("first_actual=%llu\\n", static_cast<unsigned long long>(first_actual));
      }

      check(hipModuleUnload(module), "hipModuleUnload");
      check(hipFree(d_out), "hipFree d_out");
      check(hipFree(d_in), "hipFree d_in");
      return mismatch == 0U ? 0 : 3;
    }
    """
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate native rocdl/hsaco artifacts from a real sim_accel.program.json, "
            "launch the hsaco via HIP, and compare it against the generated CPU reference."
        )
    )
    parser.add_argument("--program-json", type=Path, default=DEFAULT_PROGRAM_JSON)
    parser.add_argument("--link", type=Path, default=DEFAULT_LINK)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_SUMMARY_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_SUMMARY_MD)
    parser.add_argument("--nstates", type=int, default=4)
    parser.add_argument("--gfx-arch", default="")
    parser.add_argument("--hipcc", default=shutil.which("hipcc") or "hipcc")
    return parser.parse_args()


def _derive_gfx_arch(explicit: str) -> str:
    if explicit:
        return explicit
    override = os.getenv("HSA_OVERRIDE_GFX_VERSION", "").strip()
    match = re.fullmatch(r"(\\d+)\\.(\\d+)\\.(\\d+)", override)
    if match:
        return f"gfx{match.group(1)}{match.group(2)}{match.group(3)}"
    return "gfx1201"


def _run(cmd: list[str], *, cwd: Path, log_path: Path, check: bool = True) -> dict[str, Any]:
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    elapsed = time.perf_counter() - t0
    log_path.write_text(
        f"$ {' '.join(cmd)}\n\n[stdout]\n{proc.stdout}\n[stderr]\n{proc.stderr}\n",
        encoding="utf-8",
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\nSee {log_path}"
        )
    return {
        "cmd": cmd,
        "elapsed_s": elapsed,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "log_path": str(log_path),
    }


def _parse_var_count(vars_tsv: Path) -> int:
    with vars_tsv.open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh, delimiter="\t"))
    return max(0, len(rows) - 1)


def _parse_var_names(vars_tsv: Path) -> list[str]:
    with vars_tsv.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    return [str(row.get("name") or "") for row in rows]


def _parse_var_widths(vars_tsv: Path) -> list[int]:
    with vars_tsv.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    return [int(row.get("width") or 0) for row in rows]


def _parse_run_output(stdout: str) -> dict[str, Any]:
    def _match(name: str, default: str = "") -> str:
        m = re.search(rf"^{re.escape(name)}=([^\r\n]+)$", stdout, re.MULTILINE)
        return m.group(1).strip() if m else default

    return {
        "runtime_gpu_api": _match("runtime_gpu_api"),
        "runtime_gpu_platform": _match("runtime_gpu_platform"),
        "runtime_gpu_device_name": _match("runtime_gpu_device_name"),
        "runtime_gpu_arch_name": _match("runtime_gpu_arch_name"),
        "nstates": int(_match("nstates", "0")),
        "state_var_count": int(_match("state_var_count", "0")),
        "mismatch": int(_match("mismatch", "999999")),
        "first_mismatch_index": int(_match("first_mismatch_index", "-1")),
        "first_expected": int(_match("first_expected", "0")),
        "first_actual": int(_match("first_actual", "0")),
    }


def _write_summary_md(path: Path, payload: dict[str, Any]) -> None:
    run = payload["run"]
    lines = [
        "# ROCm Native hsaco Mainline Probe",
        "",
        f"- status: `{'pass' if payload['pass'] else 'fail'}`",
        f"- gfx_arch: `{payload['gfx_arch']}`",
        f"- device: `{run['runtime_gpu_device_name']}`",
        f"- runtime_gpu_api: `{run['runtime_gpu_api']}`",
        f"- mismatch: `{run['mismatch']}`",
        f"- first_mismatch_var: `{run.get('first_mismatch_var_name', '')}`",
        f"- nstates: `{run['nstates']}`",
        f"- state_var_count: `{run['state_var_count']}`",
        "",
        "## Evidence",
        "",
        f"- [summary.json]({path.with_suffix('.json')})",
        f"- [program_json_to_full_all.log]({payload['steps']['emit_artifacts']['log_path']})",
        f"- [compile_host.log]({payload['steps']['compile_host']['log_path']})",
        f"- [run.log]({payload['steps']['run']['log_path']})",
        f"- [kernel_generated.full_all.rocdl.ll]({payload['artifacts']['rocdl_llvm']})",
        f"- [kernel_generated.full_all.hsaco]({payload['artifacts']['hsaco']})",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    gfx_arch = _derive_gfx_arch(args.gfx_arch)

    steps: dict[str, Any] = {}
    steps["emit_artifacts"] = _run(
        [
            "python3",
            str(PROGRAM_JSON_TO_FULL_ALL),
            "--program-json",
            str(args.program_json),
            "--link",
            str(args.link),
            "--out-dir",
            str(out_dir),
            "--emit-hsaco",
            "--gfx-arch",
            gfx_arch,
        ],
        cwd=out_dir,
        log_path=out_dir / "program_json_to_full_all.log",
    )

    hsaco_path = out_dir / "kernel_generated.full_all.hsaco"
    rocdl_llvm_path = out_dir / "kernel_generated.full_all.rocdl.ll"
    cpu_cpp_path = out_dir / "kernel_generated.cpu.cpp"
    vars_tsv_path = out_dir / "kernel_generated.vars.tsv"

    state_var_count = _parse_var_count(vars_tsv_path)
    var_names = _parse_var_names(vars_tsv_path)
    var_widths = _parse_var_widths(vars_tsv_path)
    host_src = out_dir / "rocm_native_hsaco_mainline_host.cpp"
    host_bin = out_dir / "rocm_native_hsaco_mainline_host"
    host_src.write_text(
        HOST_TEMPLATE.replace("__STATE_VAR_COUNT__", str(state_var_count)).replace(
            "__STATE_WIDTHS__", ", ".join(str(width) for width in var_widths)
        ),
        encoding="utf-8",
    )

    steps["compile_host"] = _run(
        [
            args.hipcc,
            "-std=c++17",
            str(host_src),
            str(cpu_cpp_path),
            "-o",
            str(host_bin),
        ],
        cwd=out_dir,
        log_path=out_dir / "compile_host.log",
    )
    steps["run"] = _run(
        [str(host_bin), str(hsaco_path), str(args.nstates)],
        cwd=out_dir,
        log_path=out_dir / "run.log",
        check=False,
    )

    run = _parse_run_output(steps["run"]["stdout"])
    first_var_slot = (
        run["first_mismatch_index"] // run["nstates"]
        if run["mismatch"] > 0 and run["nstates"] > 0 and run["first_mismatch_index"] >= 0
        else -1
    )
    first_state_index = (
        run["first_mismatch_index"] % run["nstates"]
        if run["mismatch"] > 0 and run["nstates"] > 0 and run["first_mismatch_index"] >= 0
        else -1
    )
    run["first_mismatch_var_slot"] = first_var_slot
    run["first_mismatch_state_index"] = first_state_index
    run["first_mismatch_var_name"] = (
        var_names[first_var_slot] if 0 <= first_var_slot < len(var_names) else ""
    )
    run["returncode"] = int(steps["run"]["returncode"])
    payload = {
        "pass": run["mismatch"] == 0 and run["returncode"] == 0,
        "gfx_arch": gfx_arch,
        "steps": steps,
        "artifacts": {
            "out_dir": str(out_dir),
            "rocdl_llvm": str(rocdl_llvm_path),
            "hsaco": str(hsaco_path),
            "cpu_cpp": str(cpu_cpp_path),
            "vars_tsv": str(vars_tsv_path),
        },
        "run": run,
    }

    args.summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_summary_md(args.summary_md, payload)
    print(args.summary_json)
    return 0 if payload["pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
