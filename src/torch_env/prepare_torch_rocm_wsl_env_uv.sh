#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="${1:-$ROOT_DIR/.venv-torch-rocm}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TORCH_URL="${TORCH_URL:-https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2/torch-2.9.1%2Brocm7.2.0.lw.git7e1940d4-cp312-cp312-linux_x86_64.whl}"
TORCHVISION_URL="${TORCHVISION_URL:-https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2/torchvision-0.24.0%2Brocm7.2.0.gitb919bd0c-cp312-cp312-linux_x86_64.whl}"
TORCHAUDIO_URL="${TORCHAUDIO_URL:-https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2/torchaudio-2.9.0%2Brocm7.2.0.gite3c6ee2b-cp312-cp312-linux_x86_64.whl}"
TRITON_URL="${TRITON_URL:-https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2/triton-3.5.1%2Brocm7.2.0.gita272dfa8-cp312-cp312-linux_x86_64.whl}"

echo "[rocm-env] creating env: ${ENV_DIR}"
uv venv --python "${PYTHON_BIN}" "${ENV_DIR}"

echo "[rocm-env] installing numpy compatibility pin"
uv pip install --python "${ENV_DIR}/bin/python" "numpy==1.26.4" "wheel"

echo "[rocm-env] installing ROCm PyTorch wheels"
uv pip install \
  --python "${ENV_DIR}/bin/python" \
  "${TORCH_URL}" \
  "${TORCHVISION_URL}" \
  "${TORCHAUDIO_URL}" \
  "${TRITON_URL}"

TORCH_LIB_DIR="$("${ENV_DIR}/bin/python" - <<'PY'
import site
from pathlib import Path
for root in site.getsitepackages():
    candidate = Path(root) / "torch" / "lib"
    if candidate.exists():
        print(candidate)
        break
PY
)"

if [[ -n "${TORCH_LIB_DIR}" && -d "${TORCH_LIB_DIR}" ]]; then
  echo "[rocm-env] removing bundled HSA runtime for WSL compatibility: ${TORCH_LIB_DIR}"
  rm -f "${TORCH_LIB_DIR}"/libhsa-runtime64.so*
fi

echo "[rocm-env] installation complete"
echo "[rocm-env] run with:"
echo "  HSA_OVERRIDE_GFX_VERSION=12.0.1 LD_PRELOAD=/opt/rocm/lib/libamdhip64.so ${ENV_DIR}/bin/python ${ROOT_DIR}/verify_torch_gpu_env.py --backend rocm"
