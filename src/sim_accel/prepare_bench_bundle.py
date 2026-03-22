#!/usr/bin/env python3
"""Stage fused sim-accel outputs into a bench-compatible bundle directory."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
CUDA_OPT_DIR = SCRIPT_PATH.parent
ROOT_DIR = SCRIPT_PATH.parents[2]
VERILATOR_ROOT = ROOT_DIR / "third_party" / "verilator"
PROJECT_ROOT = ROOT_DIR / "include" / "sim_accel"
BENCH_TEMPLATE_DIR = VERILATOR_ROOT / "bin" / "verilator_sim_accel_bench_kernel"
MAILBOX_HEADERS = [
    "HYBRID_DEBUG_MAILBOX_ABI.h",
    "HYBRID_DEBUG_MAILBOX_CSR_RUNTIME.h",
    "HYBRID_DEBUG_MAILBOX_FAULT_RUNTIME.h",
    "HYBRID_DEBUG_MAILBOX_LOOP_RUNTIME.h",
    "HYBRID_DEBUG_MAILBOX_RUNTIME.h",
    "HYBRID_DEBUG_MAILBOX_MOCK.h",
    "HYBRID_DEBUG_MAILBOX_EPOCH_RUNTIME.h",
    "HYBRID_DEBUG_MAILBOX_BENCH_SCRIPT.h",
    "HYBRID_DEBUG_MAILBOX_PRELOAD_SHARED.h",
]
BUNDLE_CONFIG_NAME = "sim_accel_bundle_config.json"
GPU_BINARY_ENV_VAR = "SIM_ACCEL_GPU_BINARY_PATH"
LEGACY_CIRCT_CUBIN_ENV_VAR = "SIM_ACCEL_CIRCT_CUBIN_PATH"
EXECUTION_BACKENDS = ("auto", "cuda_source", "cuda_circt_cubin", "rocm_llvm")
ROCM_LAUNCH_MODES = ("auto", "source-bridge", "native-hsaco")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy fused opt/gpu/cuda outputs into a bench-compatible OUTDIR layout "
            "with bench_kernel.cu and mailbox headers."
        )
    )
    parser.add_argument(
        "--generated-dir",
        type=Path,
        required=True,
        help="Directory containing kernel_generated.* outputs from program_json_to_full_all.py or hdl_to_full_all.py",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="Destination bench bundle directory",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Remove an existing output directory before staging the bundle",
    )
    parser.add_argument(
        "--launch-backend",
        choices=("cuda", "circt-cubin"),
        default="cuda",
        help=(
            "Bundle-local launch backend. cuda keeps kernel_generated.link.cu unchanged; "
            "circt-cubin patches launch_all wrappers to call the emitted CIRCT cubin driver."
        ),
    )
    parser.add_argument(
        "--execution-backend",
        choices=EXECUTION_BACKENDS,
        default="auto",
        help=(
            "Explicit execution lane for the staged bundle. auto derives "
            "cuda_source from launch-backend=cuda and cuda_circt_cubin from "
            "launch-backend=circt-cubin. rocm_llvm reserves a future "
            "ROCDL/AMDGPU lane."
        ),
    )
    parser.add_argument(
        "--rocm-launch-mode",
        choices=ROCM_LAUNCH_MODES,
        default="auto",
        help=(
            "ROCm lane selection for execution-backend=rocm_llvm. source-bridge keeps the "
            "temporary hipify+hipcc path; native-hsaco stages the emitted hsaco + ROCm driver "
            "for full_all/off execution."
        ),
    )
    return parser.parse_args()


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise RuntimeError(f"Missing {label}: {path}")
    return path


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _render_bench_kernel(include_name: str) -> str:
    parts = sorted(BENCH_TEMPLATE_DIR.glob("bench_kernel_part_*.cu.inc"))
    if not parts:
        raise RuntimeError(f"Missing bench kernel templates under: {BENCH_TEMPLATE_DIR}")
    text = "".join(part.read_text(encoding="utf-8") for part in parts)
    return text.replace("__SIM_ACCEL_GENERATED_INCLUDE__", include_name)


def _resolve_execution_backend(*, launch_backend: str, requested_execution_backend: str) -> dict[str, object]:
    requested = str(requested_execution_backend or "auto").strip() or "auto"
    if requested == "auto":
        selected = "cuda_source" if launch_backend == "cuda" else "cuda_circt_cubin"
        reason = "derived_from_launch_backend"
    else:
        selected = requested
        reason = "explicit_request"

    if selected == "cuda_source" and launch_backend != "cuda":
        raise RuntimeError("execution-backend=cuda_source requires --launch-backend cuda")
    if selected == "cuda_circt_cubin" and launch_backend != "circt-cubin":
        raise RuntimeError("execution-backend=cuda_circt_cubin requires --launch-backend circt-cubin")
    if selected == "rocm_llvm" and launch_backend != "cuda":
        raise RuntimeError(
            "execution-backend=rocm_llvm currently stages only the source-style launch bundle; "
            "use --launch-backend cuda"
        )

    if selected == "cuda_source":
        compiler_backend = "nvptx"
        launcher_backend = "cuda_runtime"
    elif selected == "cuda_circt_cubin":
        compiler_backend = "nvptx"
        launcher_backend = "cuda_driver"
    else:
        compiler_backend = "rocdl"
        launcher_backend = "hip_hsa"

    return {
        "requested": requested,
        "selected": selected,
        "reason": reason,
        "compiler_backend": compiler_backend,
        "launcher_backend": launcher_backend,
        "supports_single_cluster_smoke": selected == "cuda_source",
    }


def _gpu_binary_metadata(*, execution_backend: str) -> dict[str, object]:
    if execution_backend == "cuda_circt_cubin":
        return {
            "gpu_binary_kind": "cubin",
            "gpu_binary_relpath": "kernel_generated.full_all.circt.cubin",
            "gpu_binary_env_var": GPU_BINARY_ENV_VAR,
            "gpu_binary_legacy_env_var": LEGACY_CIRCT_CUBIN_ENV_VAR,
            "gpu_binary_required": True,
        }
    if execution_backend == "rocm_llvm":
        return {
            "gpu_binary_kind": "hsaco",
            "gpu_binary_relpath": "kernel_generated.full_all.hsaco",
            "gpu_binary_env_var": GPU_BINARY_ENV_VAR,
            "gpu_binary_required": True,
        }
    return {
        "gpu_binary_kind": "embedded_cuda",
        "gpu_binary_relpath": "",
        "gpu_binary_env_var": "",
        "gpu_binary_required": False,
    }


def _resolve_rocm_launch_mode(
    *,
    generated_dir: Path,
    execution_backend: str,
    requested_rocm_launch_mode: str,
) -> dict[str, object]:
    requested = str(requested_rocm_launch_mode or "auto").strip() or "auto"
    if execution_backend != "rocm_llvm":
        return {
            "requested": requested,
            "selected": "",
            "reason": "not_applicable",
            "native_ready": False,
        }
    native_ready = (
        (generated_dir / "kernel_generated.full_all.hsaco").is_file()
        and (generated_dir / "kernel_generated.full_all.rocm_driver.cpp").is_file()
    )
    if requested == "auto":
        selected = "native-hsaco" if native_ready else "source-bridge"
        reason = "native_artifacts_present" if native_ready else "native_artifacts_missing"
    else:
        selected = requested
        reason = "explicit_request"
    if selected == "native-hsaco" and not native_ready:
        raise RuntimeError(
            "rocm-launch-mode=native-hsaco requires kernel_generated.full_all.hsaco and "
            "kernel_generated.full_all.rocm_driver.cpp in the generated dir"
        )
    return {
        "requested": requested,
        "selected": selected,
        "reason": reason,
        "native_ready": native_ready,
    }


def _patch_link_for_circt_cubin(link_text: str, *, cubin_relpath: str) -> str:
    if "sim_accel_eval_assignw_circt_bundle_cubin_path" in link_text:
        return link_text
    required_markers = (
        "sim_accel_eval_preload_runtime_state_count",
        "sim_accel_eval_preload_target_host_views",
    )
    for marker in required_markers:
        if marker not in link_text:
            raise RuntimeError(
                "circt-cubin backend requires a standalone kernel_generated.link.cu "
                f"with preload accessors; missing marker {marker!r}"
            )
    if "#include <stdlib.h>" not in link_text:
        link_text = link_text.replace(
            "#include <stdint.h>\n",
            "#include <stdint.h>\n#include <stdlib.h>\n",
            1,
        )
    helper_block = (
        '\nextern "C" __host__ cudaError_t sim_accel_eval_assignw_circt_launch_all(\n'
        "    const char* cubin_path,\n"
        "    const uint64_t* state_in,\n"
        "    uint64_t* state_out,\n"
        "    uint32_t nstates,\n"
        "    uint32_t block_size);\n"
        'extern "C" __host__ cudaError_t sim_accel_eval_assignw_circt_launch_all_inplace(\n'
        "    const char* cubin_path,\n"
        "    uint64_t* state,\n"
        "    uint32_t nstates,\n"
        "    uint32_t block_size);\n"
        "static const char* sim_accel_eval_assignw_circt_bundle_cubin_path() {\n"
        f'    const char* override_path = getenv("{GPU_BINARY_ENV_VAR}");\n'
        "    if (override_path && override_path[0] != '\\0') return override_path;\n"
        f'    const char* legacy_override_path = getenv("{LEGACY_CIRCT_CUBIN_ENV_VAR}");\n'
        "    if (legacy_override_path && legacy_override_path[0] != '\\0') return legacy_override_path;\n"
        f'    return "{cubin_relpath}";\n'
        "}\n"
    )
    helper_anchor = 'extern "C" __global__ void sim_accel_eval_assignw_u32_full_all('
    if helper_anchor not in link_text:
        raise RuntimeError("Could not find full-all kernel declaration in kernel_generated.link.cu")
    link_text = link_text.replace(helper_anchor, helper_block + "\n" + helper_anchor, 1)

    full_inplace_pattern = re.compile(
        r'(static __host__ cudaError_t sim_accel_eval_launch_full_all_inplace_impl\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    full_all_pattern = re.compile(
        r'(static __host__ cudaError_t sim_accel_eval_launch_full_all_impl\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    inplace_pattern = re.compile(
        r'(extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_all_inplace\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    all_pattern = re.compile(
        r'(extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_all\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    inplace_replacement = (
        "    return sim_accel_eval_assignw_circt_launch_all_inplace(\n"
        "        sim_accel_eval_assignw_circt_bundle_cubin_path(),\n"
        "        state,\n"
        "        nstates,\n"
        "        block_size);"
    )
    all_replacement = (
        "    return sim_accel_eval_assignw_circt_launch_all(\n"
        "        sim_accel_eval_assignw_circt_bundle_cubin_path(),\n"
        "        state_in,\n"
        "        state_out,\n"
        "        nstates,\n"
        "        block_size);"
    )
    link_text, full_inplace_count = full_inplace_pattern.subn(
        lambda match: match.group(1) + inplace_replacement + match.group(3),
        link_text,
        count=1,
    )
    link_text, full_all_count = full_all_pattern.subn(
        lambda match: match.group(1) + all_replacement + match.group(3),
        link_text,
        count=1,
    )
    link_text, inplace_count = inplace_pattern.subn(
        lambda match: match.group(1) + inplace_replacement + match.group(3),
        link_text,
        count=1,
    )
    link_text, all_count = all_pattern.subn(
        lambda match: match.group(1) + all_replacement + match.group(3),
        link_text,
        count=1,
    )
    if full_inplace_count != 1 or full_all_count != 1:
        raise RuntimeError("Failed to patch full-all helper launches for circt-cubin backend")
    if inplace_count != 1 or all_count != 1:
        raise RuntimeError("Failed to patch launch_all wrappers for circt-cubin backend")
    return link_text


def _patch_link_for_rocm_hsaco(
    link_text: str,
    *,
    hsaco_relpath: str,
    allow_structured_second_wave: bool = False,
    seq_partition_indices: list[int] | None = None,
    has_full_seq: bool = False,
) -> str:
    has_helper = "sim_accel_eval_assignw_rocm_bundle_hsaco_path" in link_text
    if not has_helper:
        if "#include <stdlib.h>" not in link_text:
            link_text = link_text.replace(
                "#include <stdint.h>\n",
                "#include <stdint.h>\n#include <stdlib.h>\n",
                1,
            )
        helper_block = (
            '\nextern "C" __host__ cudaError_t sim_accel_eval_assignw_rocm_launch_all(\n'
            "    const char* hsaco_path,\n"
            "    const uint64_t* state_in,\n"
            "    uint64_t* state_out,\n"
            "    uint32_t nstates,\n"
            "    uint32_t block_size);\n"
            'extern "C" __host__ cudaError_t sim_accel_eval_assignw_rocm_launch_all_inplace(\n'
            "    const char* hsaco_path,\n"
            "    uint64_t* state,\n"
            "    uint32_t nstates,\n"
            "    uint32_t block_size);\n"
            "static const char* sim_accel_eval_assignw_rocm_bundle_hsaco_path() {\n"
            f'    const char* override_path = getenv("{GPU_BINARY_ENV_VAR}");\n'
            "    if (override_path && override_path[0] != '\\0') return override_path;\n"
            f'    return "{hsaco_relpath}";\n'
            "}\n"
        )
        helper_anchor = 'extern "C" __global__ void sim_accel_eval_assignw_u32_full_all('
        if helper_anchor not in link_text:
            raise RuntimeError("Could not find full-all kernel declaration in kernel_generated.link.cu")
        link_text = link_text.replace(helper_anchor, helper_block + "\n" + helper_anchor, 1)

    full_inplace_pattern = re.compile(
        r'(static __host__ cudaError_t sim_accel_eval_launch_full_all_inplace_impl\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    full_all_pattern = re.compile(
        r'(static __host__ cudaError_t sim_accel_eval_launch_full_all_impl\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    inplace_pattern = re.compile(
        r'(extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_all_inplace\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    all_pattern = re.compile(
        r'(extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_all\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    partition_count_pattern = re.compile(
        r'(extern "C" __host__ uint32_t sim_accel_eval_partition_count\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    seq_count_pattern = re.compile(
        r'(extern "C" __host__ uint32_t sim_accel_eval_seq_partition_count\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    cluster_count_pattern = re.compile(
        r'(extern "C" __host__ uint32_t sim_accel_eval_cluster_count\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    partition_launch_pattern = re.compile(
        r'(extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_partition\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    seq_launch_pattern = re.compile(
        r'(extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_seq_partition\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    cluster_launch_pattern = re.compile(
        r'(extern "C" __host__ cudaError_t sim_accel_eval_assignw_launch_cluster\([^)]*\)\s*\{\n)'
        r'(.*?)'
        r'(\n\})',
        re.DOTALL,
    )
    inplace_replacement = (
        "    return sim_accel_eval_assignw_rocm_launch_all_inplace(\n"
        "        sim_accel_eval_assignw_rocm_bundle_hsaco_path(),\n"
        "        state,\n"
        "        nstates,\n"
        "        block_size);"
    )
    all_replacement = (
        "    return sim_accel_eval_assignw_rocm_launch_all(\n"
        "        sim_accel_eval_assignw_rocm_bundle_hsaco_path(),\n"
        "        state_in,\n"
        "        state_out,\n"
        "        nstates,\n"
        "        block_size);"
    )
    invalid_stub = "    return cudaErrorInvalidValue;"
    zero_stub = "    return 0U;"
    link_text, full_inplace_count = full_inplace_pattern.subn(
        lambda match: match.group(1) + inplace_replacement + match.group(3),
        link_text,
        count=1,
    )
    link_text, full_all_count = full_all_pattern.subn(
        lambda match: match.group(1) + all_replacement + match.group(3),
        link_text,
        count=1,
    )
    link_text, inplace_count = inplace_pattern.subn(
        lambda match: match.group(1) + inplace_replacement + match.group(3),
        link_text,
        count=1,
    )
    link_text, all_count = all_pattern.subn(
        lambda match: match.group(1) + all_replacement + match.group(3),
        link_text,
        count=1,
    )
    if allow_structured_second_wave:
        partition_count_rewritten = 0
        seq_count_rewritten = 0
        cluster_count_rewritten = 0
        partition_launch_rewritten = 0
        seq_launch_rewritten = 0
        cluster_launch_rewritten = 0
    else:
        link_text, partition_count_rewritten = partition_count_pattern.subn(
            lambda match: match.group(1) + zero_stub + match.group(3),
            link_text,
            count=1,
        )
        link_text, seq_count_rewritten = seq_count_pattern.subn(
            lambda match: match.group(1) + zero_stub + match.group(3),
            link_text,
            count=1,
        )
        link_text, cluster_count_rewritten = cluster_count_pattern.subn(
            lambda match: match.group(1) + zero_stub + match.group(3),
            link_text,
            count=1,
        )
        link_text, partition_launch_rewritten = partition_launch_pattern.subn(
            lambda match: match.group(1) + invalid_stub + match.group(3),
            link_text,
            count=1,
        )
        link_text, seq_launch_rewritten = seq_launch_pattern.subn(
            lambda match: match.group(1) + invalid_stub + match.group(3),
            link_text,
            count=1,
        )
        link_text, cluster_launch_rewritten = cluster_launch_pattern.subn(
            lambda match: match.group(1) + invalid_stub + match.group(3),
            link_text,
            count=1,
        )
    if inplace_count != 1 or all_count != 1:
        raise RuntimeError("Failed to patch launch_all wrappers for rocm native-hsaco backend")
    structured_rewrite_counts = (
        partition_count_rewritten,
        seq_count_rewritten,
        cluster_count_rewritten,
        partition_launch_rewritten,
        seq_launch_rewritten,
        cluster_launch_rewritten,
    )
    if any(count not in (0, 1) for count in structured_rewrite_counts):
        raise RuntimeError("Failed to patch structured launch stubs for rocm native-hsaco backend")
    if allow_structured_second_wave and not seq_partition_indices:
        seq_count_replacement = "    return 1U;" if has_full_seq else zero_stub
        if has_full_seq:
            seq_launch_replacement = (
                "    const uint32_t block = block_size ? block_size : 256U;\n"
                "    const uint32_t grid = (nstates + block - 1U) / block;\n"
                "    if (index != 0U) return cudaErrorInvalidValue;\n"
                "    sim_accel_eval_assignw_u32_full_seq<<<grid, block>>>(state_in, state_out, nstates);\n"
                "    return cudaGetLastError();"
            )
        else:
            seq_launch_replacement = invalid_stub
        link_text, seq_count_fallback_count = seq_count_pattern.subn(
            lambda match: match.group(1) + seq_count_replacement + match.group(3),
            link_text,
            count=1,
        )
        link_text, seq_launch_fallback_count = seq_launch_pattern.subn(
            lambda match: match.group(1) + seq_launch_replacement + match.group(3),
            link_text,
            count=1,
        )
        if seq_count_fallback_count not in (0, 1) or seq_launch_fallback_count not in (0, 1):
            raise RuntimeError("Failed to patch seq-partition fallback for rocm native-hsaco backend")
    return link_text

def main() -> int:
    args = parse_args()
    generated_dir = args.generated_dir.resolve()
    out_dir = args.out_dir.resolve()

    _require_file(generated_dir / "kernel_generated.api.h", "kernel_generated.api.h")
    _require_file(generated_dir / "kernel_generated.link.cu", "kernel_generated.link.cu")
    if args.launch_backend == "circt-cubin":
        _require_file(
            generated_dir / "kernel_generated.full_all.circt_driver.cpp",
            "kernel_generated.full_all.circt_driver.cpp",
        )
        _require_file(
            generated_dir / "kernel_generated.full_all.circt.cubin",
            "kernel_generated.full_all.circt.cubin",
        )

    if args.force and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for src in sorted(generated_dir.iterdir()):
        if not src.is_file():
            continue
        if src.name.startswith("kernel_generated.") or src.name == "full_kernel_fuser.log":
            _copy_file(src, out_dir / src.name)

    execution_backend = _resolve_execution_backend(
        launch_backend=args.launch_backend,
        requested_execution_backend=args.execution_backend,
    )
    rocm_launch_mode = _resolve_rocm_launch_mode(
        generated_dir=generated_dir,
        execution_backend=str(execution_backend["selected"]),
        requested_rocm_launch_mode=args.rocm_launch_mode,
    )
    bundle_config = {
        "launch_backend": args.launch_backend,
        "execution_backend_request": str(execution_backend["requested"]),
        "execution_backend": str(execution_backend["selected"]),
        "execution_backend_reason": str(execution_backend["reason"]),
        "compiler_backend": str(execution_backend["compiler_backend"]),
        "launcher_backend": str(execution_backend["launcher_backend"]),
        "supports_single_cluster_smoke": bool(execution_backend["supports_single_cluster_smoke"]),
    }
    bundle_config.update(_gpu_binary_metadata(execution_backend=str(execution_backend["selected"])))
    if args.launch_backend == "circt-cubin":
        bundle_config["circt_cubin_relpath"] = "kernel_generated.full_all.circt.cubin"
        bundle_config["circt_cubin_env_var"] = LEGACY_CIRCT_CUBIN_ENV_VAR
        local_link_path = out_dir / "kernel_generated.link.cu"
        local_link_path.write_text(
            _patch_link_for_circt_cubin(
                local_link_path.read_text(encoding="utf-8"),
                cubin_relpath=str(bundle_config["circt_cubin_relpath"]),
            ),
            encoding="utf-8",
        )
    if str(execution_backend["selected"]) == "rocm_llvm":
        bundle_config["rocm_launch_mode_request"] = str(rocm_launch_mode["requested"])
        bundle_config["rocm_launch_mode"] = str(rocm_launch_mode["selected"])
        bundle_config["rocm_launch_mode_reason"] = str(rocm_launch_mode["reason"])
        if str(rocm_launch_mode["selected"]) == "native-hsaco":
            structured_native = any(generated_dir.glob("kernel_generated.part*.cu")) or any(
                generated_dir.glob("kernel_generated.seqpart*.cu")
            ) or any(generated_dir.glob("kernel_generated.cluster*.cu"))
            seq_partition_indices = sorted(
                int(match.group(1))
                for path in generated_dir.glob("kernel_generated.seqpart*.cu")
                if (match := re.fullmatch(r"kernel_generated\.seqpart(\d+)\.cu", path.name))
            )
            _require_file(
                generated_dir / "kernel_generated.full_all.rocm_driver.cpp",
                "kernel_generated.full_all.rocm_driver.cpp",
            )
            _require_file(
                generated_dir / "kernel_generated.full_all.hsaco",
                "kernel_generated.full_all.hsaco",
            )
            bundle_config["rocm_native_driver_relpath"] = "kernel_generated.full_all.rocm_driver.cpp"
            bundle_config["supports_single_cluster_smoke"] = structured_native
            local_link_path = out_dir / "kernel_generated.link.cu"
            local_link_path.write_text(
                _patch_link_for_rocm_hsaco(
                    local_link_path.read_text(encoding="utf-8"),
                    hsaco_relpath=str(bundle_config["gpu_binary_relpath"]),
                    allow_structured_second_wave=structured_native,
                    seq_partition_indices=seq_partition_indices,
                    has_full_seq=(generated_dir / "kernel_generated.full_seq.cu").is_file(),
                ),
                encoding="utf-8",
            )

    kernel_generated_cu = out_dir / "kernel_generated.cu"
    if not kernel_generated_cu.exists():
        full_all_cu = generated_dir / "kernel_generated.full_all.cu"
        _require_file(full_all_cu, "kernel_generated.full_all.cu")
        _copy_file(full_all_cu, kernel_generated_cu)

    use_object_mode = any(out_dir.glob("kernel_generated.part*.cu")) or any(
        out_dir.glob("kernel_generated.cluster*.cu")
    ) or any(out_dir.glob("kernel_generated.full_*.cu"))
    include_name = "kernel_generated.api.h" if use_object_mode else "kernel_generated.cu"
    (out_dir / "bench_kernel.cu").write_text(
        _render_bench_kernel(include_name),
        encoding="utf-8",
    )

    for header_name in MAILBOX_HEADERS:
        _copy_file(PROJECT_ROOT / header_name, out_dir / header_name)

    (out_dir / BUNDLE_CONFIG_NAME).write_text(
        json.dumps(bundle_config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"generated_dir={generated_dir}")
    print(f"out_dir={out_dir}")
    print(f"bench_include={include_name}")
    print(f"launch_backend={args.launch_backend}")
    print(f"execution_backend={bundle_config['execution_backend']}")
    print(f"gpu_binary_kind={bundle_config['gpu_binary_kind']}")
    print(f"gpu_binary_relpath={bundle_config['gpu_binary_relpath']}")
    print(f"gpu_binary_env_var={bundle_config['gpu_binary_env_var']}")
    print(f"bundle_config={out_dir / BUNDLE_CONFIG_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
