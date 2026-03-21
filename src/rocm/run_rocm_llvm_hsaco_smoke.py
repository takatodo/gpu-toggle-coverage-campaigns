#!/usr/bin/env python3
from __future__ import annotations

import argparse
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
DEFAULT_OUT_DIR = Path("/tmp/rocm_llvm_hsaco_smoke_v1")
DEFAULT_JSON = SCRIPT_DIR / "rocm_llvm_hsaco_smoke.json"
DEFAULT_MD = SCRIPT_DIR / "rocm_llvm_hsaco_smoke.md"
ROCM_LLVM_BIN = Path("/opt/rocm-7.2.0/lib/llvm/bin")

KERNEL_SOURCE = textwrap.dedent(
    """\
    #include <hip/hip_runtime.h>

    extern "C" __global__ void add_one(const float* in, float* out, int n) {
      int i = blockIdx.x * blockDim.x + threadIdx.x;
      if (i < n) out[i] = in[i] + 1.0f;
    }
    """
)

HOST_SOURCE = textwrap.dedent(
    """\
    #include <hip/hip_runtime.h>
    #include <cmath>
    #include <cstdio>
    #include <cstdlib>
    #include <vector>

    static void check(hipError_t status, const char* what) {
      if (status != hipSuccess) {
        std::fprintf(stderr, "%s: %s\\n", what, hipGetErrorString(status));
        std::fflush(stderr);
        std::exit(1);
      }
    }

    int main(int argc, char** argv) {
      const char* hsaco = argc > 1 ? argv[1] : "";
      if (!hsaco || !hsaco[0]) {
        std::fprintf(stderr, "missing hsaco path\\n");
        return 2;
      }
      constexpr int N = 256;
      std::vector<float> in(N), out(N, 0.0f);
      for (int i = 0; i < N; ++i) in[i] = static_cast<float>(i);

      float* d_in = nullptr;
      float* d_out = nullptr;
      check(hipMalloc(&d_in, N * sizeof(float)), "hipMalloc d_in");
      check(hipMalloc(&d_out, N * sizeof(float)), "hipMalloc d_out");
      check(hipMemcpy(d_in, in.data(), N * sizeof(float), hipMemcpyHostToDevice), "hipMemcpy H2D");
      check(hipMemset(d_out, 0, N * sizeof(float)), "hipMemset d_out");

      hipModule_t module{};
      hipFunction_t func{};
      check(hipModuleLoad(&module, hsaco), "hipModuleLoad");
      check(hipModuleGetFunction(&func, module, "add_one"), "hipModuleGetFunction");

      int n = N;
      void* kernel_args[] = {&d_in, &d_out, &n};
      check(hipModuleLaunchKernel(func,
                                  (N + 63) / 64, 1, 1,
                                  64, 1, 1,
                                  0, 0,
                                  kernel_args, nullptr),
            "hipModuleLaunchKernel");
      check(hipDeviceSynchronize(), "hipDeviceSynchronize");
      check(hipMemcpy(out.data(), d_out, N * sizeof(float), hipMemcpyDeviceToHost), "hipMemcpy D2H");

      int mismatches = 0;
      for (int i = 0; i < N; ++i) {
        const float expected = in[i] + 1.0f;
        if (std::fabs(out[i] - expected) > 1e-5f) {
          if (mismatches < 8) {
            std::fprintf(stderr, "mismatch[%d]: got=%f expected=%f\\n", i, out[i], expected);
          }
          ++mismatches;
        }
      }

      std::printf("hsaco=%s\\n", hsaco);
      std::printf("mismatches=%d\\n", mismatches);
      std::printf("sample0=%f\\n", out[0]);
      std::printf("sample255=%f\\n", out[255]);

      check(hipModuleUnload(module), "hipModuleUnload");
      check(hipFree(d_out), "hipFree d_out");
      check(hipFree(d_in), "hipFree d_in");
      return mismatches == 0 ? 0 : 2;
    }
    """
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a minimal hsaco from LLVM IR under ROCm, launch it with HIP module APIs, "
            "and write canonical smoke artifacts."
        )
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--summary-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--gfx-arch", default="")
    parser.add_argument("--hipcc", default=shutil.which("hipcc") or "hipcc")
    parser.add_argument("--clang", default=str(ROCM_LLVM_BIN / "clang"))
    parser.add_argument("--ld-lld", default=str(ROCM_LLVM_BIN / "ld.lld"))
    return parser.parse_args()


def _derive_gfx_arch(explicit: str) -> str:
    if explicit:
        return explicit
    override = os.getenv("HSA_OVERRIDE_GFX_VERSION", "").strip()
    match = re.fullmatch(r"(\\d+)\\.(\\d+)\\.(\\d+)", override)
    if match:
        return f"gfx{match.group(1)}{match.group(2)}{match.group(3)}"
    raise RuntimeError(
        "Could not derive gfx arch. Pass --gfx-arch explicitly or set HSA_OVERRIDE_GFX_VERSION."
    )


def _run(cmd: list[str], *, cwd: Path, log_path: Path) -> dict[str, Any]:
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
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\nSee {log_path}"
        )
    return {
        "cmd": cmd,
        "elapsed_s": elapsed,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "log_path": str(log_path),
    }


def _parse_run_output(stdout: str, stderr: str) -> dict[str, Any]:
    def _match(name: str) -> str:
        m = re.search(rf"^{name}=([^\r\n]+)$", stdout, re.MULTILINE)
        return m.group(1).strip() if m else ""

    return {
        "mismatches": int(_match("mismatches") or "999999"),
        "sample0": float(_match("sample0") or "nan"),
        "sample255": float(_match("sample255") or "nan"),
        "resource_leak_warning": "Resource leak detected by SharedSignalPool" in stderr,
    }


def _write_summary_md(path: Path, payload: dict[str, Any]) -> None:
    run = payload["run"]
    lines = [
        "# ROCm LLVM hsaco Smoke",
        "",
        f"- status: `{'pass' if payload['pass'] else 'fail'}`",
        f"- gfx_arch: `{payload['gfx_arch']}`",
        f"- llvm_ir_to_hsaco: `{payload['artifacts']['llvm_ir']} -> {payload['artifacts']['hsaco']}`",
        f"- mismatches: `{run['mismatches']}`",
        f"- sample0: `{run['sample0']}`",
        f"- sample255: `{run['sample255']}`",
        f"- resource_leak_warning: `{run['resource_leak_warning']}`",
        "",
        "## Evidence",
        "",
        f"- [summary.json]({path.with_suffix('.json')})",
        f"- [compile_llvm.log]({payload['steps']['compile_llvm']['log_path']})",
        f"- [compile_hsaco.log]({payload['steps']['compile_hsaco']['log_path']})",
        f"- [compile_host.log]({payload['steps']['compile_host']['log_path']})",
        f"- [run.log]({payload['steps']['run']['log_path']})",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    gfx_arch = _derive_gfx_arch(args.gfx_arch)
    kernel_src = out_dir / "rocm_probe_kernel.hip"
    llvm_ir = out_dir / "rocm_probe_kernel.ll"
    obj_path = out_dir / "rocm_probe_kernel.o"
    hsaco_path = out_dir / "rocm_probe_kernel.hsaco"
    host_src = out_dir / "rocm_probe_host.cpp"
    host_bin = out_dir / "rocm_probe_host"

    kernel_src.write_text(KERNEL_SOURCE, encoding="utf-8")
    host_src.write_text(HOST_SOURCE, encoding="utf-8")

    steps: dict[str, Any] = {}
    steps["compile_llvm"] = _run(
        [
            args.hipcc,
            "--offload-device-only",
            "-S",
            "-emit-llvm",
            f"--offload-arch={gfx_arch}",
            str(kernel_src),
            "-o",
            str(llvm_ir),
        ],
        cwd=out_dir,
        log_path=out_dir / "compile_llvm.log",
    )
    steps["compile_hsaco"] = _run(
        [
            "/bin/bash",
            "-lc",
            " ".join(
                [
                    args.clang,
                    "-x",
                    "ir",
                    "--target=amdgcn-amd-amdhsa",
                    f"-mcpu={gfx_arch}",
                    "-nogpulib",
                    "-c",
                    str(llvm_ir),
                    "-o",
                    str(obj_path),
                    "&&",
                    args.ld_lld,
                    "-shared",
                    str(obj_path),
                    "-o",
                    str(hsaco_path),
                ]
            ),
        ],
        cwd=out_dir,
        log_path=out_dir / "compile_hsaco.log",
    )
    steps["compile_host"] = _run(
        [
            args.hipcc,
            "-O2",
            str(host_src),
            "-o",
            str(host_bin),
        ],
        cwd=out_dir,
        log_path=out_dir / "compile_host.log",
    )
    steps["run"] = _run(
        [str(host_bin), str(hsaco_path)],
        cwd=out_dir,
        log_path=out_dir / "run.log",
    )

    run_metrics = _parse_run_output(steps["run"]["stdout"], steps["run"]["stderr"])
    payload = {
        "schema_version": "rocm-llvm-hsaco-smoke-v1",
        "pass": run_metrics["mismatches"] == 0,
        "gfx_arch": gfx_arch,
        "environment": {
            "HSA_OVERRIDE_GFX_VERSION": os.getenv("HSA_OVERRIDE_GFX_VERSION", ""),
            "LD_PRELOAD": os.getenv("LD_PRELOAD", ""),
            "ROCM_PATH": os.getenv("ROCM_PATH", ""),
        },
        "artifacts": {
            "out_dir": str(out_dir),
            "kernel_source": str(kernel_src),
            "llvm_ir": str(llvm_ir),
            "object": str(obj_path),
            "hsaco": str(hsaco_path),
            "host_source": str(host_src),
            "host_binary": str(host_bin),
        },
        "steps": steps,
        "run": run_metrics,
    }

    args.summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_summary_md(args.summary_md, payload)

    print(args.summary_json)
    print(args.summary_md)
    print(f"pass={1 if payload['pass'] else 0}")
    print(f"gfx_arch={gfx_arch}")
    print(f"mismatches={run_metrics['mismatches']}")
    return 0 if payload["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
