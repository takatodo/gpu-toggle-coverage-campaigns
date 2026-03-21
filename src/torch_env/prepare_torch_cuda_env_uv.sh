#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="${1:-$ROOT_DIR/.venv-torch-cuda}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[cuda-env] creating env: ${ENV_DIR}"
uv venv --python "${PYTHON_BIN}" "${ENV_DIR}"

echo "[cuda-env] installing PyTorch CUDA wheels"
uv pip install \
  --python "${ENV_DIR}/bin/python" \
  --index-url https://download.pytorch.org/whl/cu124 \
  "torch" \
  "torchvision" \
  "torchaudio"

echo "[cuda-env] installation complete"
echo "[cuda-env] verify with:"
echo "  ${ENV_DIR}/bin/python ${ROOT_DIR}/verify_torch_gpu_env.py --backend cuda"
