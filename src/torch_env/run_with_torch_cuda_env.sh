#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="${TORCH_CUDA_ENV_DIR:-$ROOT_DIR/.venv-torch-cuda}"

if [[ $# -eq 0 ]]; then
  exec "${ENV_DIR}/bin/python"
fi

exec "${ENV_DIR}/bin/python" "$@"
