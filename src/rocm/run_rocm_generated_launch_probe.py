#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_BUNDLE_DIR = Path(
    "/tmp/rocm_tlul_fifo_sync_runner_single_cluster_smoke_v8/bundle_cache/tlul_fifo_sync/cuda"
)
DEFAULT_OUT_DIR = Path("/tmp/rocm_generated_launch_probe_v1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compile a tiny HIP probe against kernel_generated.cu and directly exercise "
            "sim_accel_eval_assignw_launch_all / launch_cluster."
        )
    )
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--nstates", type=int, default=4)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--gfx-arch", default="")
    parser.add_argument("--opt-level", default="O0")
    return parser.parse_args()


def _derive_gfx_arch(explicit: str) -> str:
    if explicit:
        return explicit
    override = os.getenv("HSA_OVERRIDE_GFX_VERSION", "").strip()
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", override)
    if match:
        return f"gfx{match.group(1)}{match.group(2)}{match.group(3)}"
    raise RuntimeError(
        "Could not derive gfx arch. Pass --gfx-arch explicitly or set HSA_OVERRIDE_GFX_VERSION."
    )


def _gfx_to_hsa_override(gfx_arch: str) -> str:
    match = re.fullmatch(r"gfx(\d+)(\d)(\d)", gfx_arch)
    if not match:
        return ""
    return f"{match.group(1)}.{match.group(2)}.{match.group(3)}"


def _rocm_env(gfx_arch: str) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("ROCM_PATH", "/opt/rocm")
    env.setdefault("HSA_OVERRIDE_GFX_VERSION", _gfx_to_hsa_override(gfx_arch))
    hip_preload = Path(env["ROCM_PATH"]) / "lib" / "libamdhip64.so"
    preload = env.get("LD_PRELOAD", "")
    if hip_preload.is_file() and "libamdhip64.so" not in preload:
        env["LD_PRELOAD"] = str(hip_preload) if not preload else f"{hip_preload}:{preload}"
    return env


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str], log_path: Path) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    log_path.write_text(
        f"$ {' '.join(cmd)}\n\n[stdout]\n{proc.stdout}\n[stderr]\n{proc.stderr}\n",
        encoding="utf-8",
    )
    return proc


PROBE_SOURCE = r"""#include <hip/hip_runtime.h>
#include "kernel_generated.api.h"

#include <cstdio>
#include <cstdint>
#include <cstdlib>

extern "C" __global__ void sim_accel_eval_assignw_u32_full_all(
    const uint64_t* state_in, uint64_t* state_out, uint32_t nstates);

__global__ void sim_accel_probe_noop(uint64_t* out) {
  if (threadIdx.x == 0 && blockIdx.x == 0) out[0] = 0x5a5a5a5a5a5a5a5aULL;
}

static void print_error(const char* label, hipError_t err) {
  std::printf("%s_code=%d\n", label, static_cast<int>(err));
  std::printf("%s_name=%s\n", label, hipGetErrorName(err));
  std::printf("%s_string=%s\n", label, hipGetErrorString(err));
}

static void run_launch_all(uint64_t* d_in, uint64_t* d_out, uint32_t nstates, uint32_t blockSize) {
  (void)hipGetLastError();
  const hipError_t launch = sim_accel_eval_assignw_launch_all(d_in, d_out, nstates, blockSize);
  print_error("launch_all", launch);
  const hipError_t sync = hipDeviceSynchronize();
  print_error("launch_all_sync", sync);
}

static void run_launch_cluster(
    uint32_t clusterIdx, uint64_t* d_in, uint64_t* d_out, uint32_t nstates, uint32_t blockSize) {
  (void)hipGetLastError();
  const hipError_t launch =
      sim_accel_eval_assignw_launch_cluster(clusterIdx, d_in, d_out, nstates, blockSize);
  std::printf("launch_cluster_index=%u\n", clusterIdx);
  print_error("launch_cluster", launch);
  const hipError_t sync = hipDeviceSynchronize();
  print_error("launch_cluster_sync", sync);
}

static void run_direct_full_all(
    uint64_t* d_in, uint64_t* d_out, uint32_t nstates, uint32_t blockSize) {
  const uint32_t block = blockSize ? blockSize : 256U;
  const uint32_t grid = (nstates + block - 1U) / block;
  (void)hipGetLastError();
  hipLaunchKernelGGL(sim_accel_eval_assignw_u32_full_all, dim3(grid), dim3(block), 0, 0, d_in, d_out,
                     nstates);
  const hipError_t launch = hipGetLastError();
  print_error("direct_full_all", launch);
  const hipError_t sync = hipDeviceSynchronize();
  print_error("direct_full_all_sync", sync);
}

static void run_direct_part0(
    uint64_t* d_in, uint64_t* d_out, uint32_t nstates, uint32_t blockSize) {
  const uint32_t block = blockSize ? blockSize : 256U;
  const uint32_t grid = (nstates + block - 1U) / block;
  (void)hipGetLastError();
  hipLaunchKernelGGL(sim_accel_eval_assignw_u32_part0, dim3(grid), dim3(block), 0, 0, d_in, d_out,
                     nstates);
  const hipError_t launch = hipGetLastError();
  print_error("direct_part0", launch);
  const hipError_t sync = hipDeviceSynchronize();
  print_error("direct_part0_sync", sync);
}

static void run_direct_cluster0(
    uint64_t* d_in, uint64_t* d_out, uint32_t nstates, uint32_t blockSize) {
  const uint32_t block = blockSize ? blockSize : 256U;
  const uint32_t grid = (nstates + block - 1U) / block;
  (void)hipGetLastError();
  hipLaunchKernelGGL(sim_accel_eval_assignw_u32_cluster0, dim3(grid), dim3(block), 0, 0, d_in, d_out,
                     nstates);
  const hipError_t launch = hipGetLastError();
  print_error("direct_cluster0", launch);
  const hipError_t sync = hipDeviceSynchronize();
  print_error("direct_cluster0_sync", sync);
}

static void run_direct_noop(uint64_t* d_out) {
  (void)hipGetLastError();
  hipLaunchKernelGGL(sim_accel_probe_noop, dim3(1), dim3(1), 0, 0, d_out);
  const hipError_t launch = hipGetLastError();
  print_error("direct_noop", launch);
  const hipError_t sync = hipDeviceSynchronize();
  print_error("direct_noop_sync", sync);
}

int main(int argc, char** argv) {
  const uint32_t nstates = static_cast<uint32_t>(argc > 1 ? std::strtoul(argv[1], nullptr, 10) : 4UL);
  const uint32_t blockSize = static_cast<uint32_t>(argc > 2 ? std::strtoul(argv[2], nullptr, 10) : 256UL);
  int dev = 0;
  if (hipSetDevice(dev) != hipSuccess) {
    print_error("set_device", hipGetLastError());
    return 2;
  }
  hipDeviceProp_t prop{};
  hipError_t propStatus = hipGetDeviceProperties(&prop, dev);
  print_error("get_device_properties", propStatus);
  if (propStatus == hipSuccess) {
    std::printf("device_name=%s\n", prop.name);
    std::printf("device_pci_bus_id=%02x:%02x\n", prop.pciBusID, prop.pciDeviceID);
  }
  const uint32_t nvars = sim_accel_eval_var_count();
  const uint32_t clusterCount = sim_accel_eval_cluster_count();
  const size_t elems = static_cast<size_t>(nvars) * static_cast<size_t>(nstates);
  const size_t bytes = elems * sizeof(uint64_t);
  std::printf("nvars=%u\n", nvars);
  std::printf("nstates=%u\n", nstates);
  std::printf("cluster_count=%u\n", clusterCount);
  std::printf("block_size=%u\n", blockSize);
  uint64_t* d_in = nullptr;
  uint64_t* d_out = nullptr;
  hipError_t st = hipMalloc(&d_in, bytes);
  print_error("malloc_in", st);
  if (st != hipSuccess) return 3;
  st = hipMalloc(&d_out, bytes);
  print_error("malloc_out", st);
  if (st != hipSuccess) return 4;
  st = hipMemset(d_in, 0, bytes);
  print_error("memset_in", st);
  st = hipMemset(d_out, 0, bytes);
  print_error("memset_out", st);

  run_direct_noop(d_out);
  run_direct_part0(d_in, d_out, nstates, blockSize);
  run_launch_all(d_in, d_out, nstates, blockSize);
  run_direct_full_all(d_in, d_out, nstates, blockSize);
  if (clusterCount > 0) {
    run_launch_cluster(0, d_in, d_out, nstates, blockSize);
    run_direct_cluster0(d_in, d_out, nstates, blockSize);
  }

  st = hipFree(d_in);
  print_error("free_in", st);
  st = hipFree(d_out);
  print_error("free_out", st);
  return 0;
}
"""


def main() -> int:
    args = parse_args()
    bundle_dir = args.bundle_dir.resolve()
    out_dir = args.out_dir.resolve()
    gfx_arch = _derive_gfx_arch(args.gfx_arch)
    env = _rocm_env(gfx_arch)

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    source_root = bundle_dir / ".sim_accel_obj" / "rocm_hipified"
    if not source_root.is_dir():
        source_root = bundle_dir

    required = ["kernel_generated.cu", "kernel_generated.api.h"]
    for name in required:
        src = source_root / name
        if not src.is_file():
            raise SystemExit(f"missing required bundle file: {src}")
        shutil.copy2(src, out_dir / name)

    probe_cc = out_dir / "probe.cpp"
    probe_cc.write_text(PROBE_SOURCE, encoding="utf-8")

    compile_log = out_dir / "build.log"
    compile_cmd = [
        "/usr/bin/hipcc",
        f"-{args.opt_level}",
        "-std=c++17",
        f"--offload-arch={gfx_arch}",
        "probe.cpp",
        "kernel_generated.cu",
        "-o",
        str(out_dir / "probe"),
    ]
    compile_proc = _run(compile_cmd, cwd=out_dir, env=env, log_path=compile_log)
    if compile_proc.returncode != 0:
        raise SystemExit(f"probe compile failed: see {compile_log}")

    run_log = out_dir / "run.log"
    run_cmd = [str(out_dir / "probe"), str(args.nstates), str(args.block_size)]
    run_proc = _run(run_cmd, cwd=out_dir, env=env, log_path=run_log)

    payload: dict[str, Any] = {
        "schema_version": "rocm-generated-launch-probe-v1",
        "bundle_dir": str(bundle_dir),
        "source_root": str(source_root),
        "out_dir": str(out_dir),
        "gfx_arch": gfx_arch,
        "opt_level": args.opt_level,
        "nstates": args.nstates,
        "block_size": args.block_size,
        "compile_returncode": compile_proc.returncode,
        "run_returncode": run_proc.returncode,
        "stdout": run_proc.stdout,
        "stderr": run_proc.stderr,
        "paths": {
            "compile_log": str(compile_log),
            "run_log": str(run_log),
            "probe_binary": str(out_dir / "probe"),
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
