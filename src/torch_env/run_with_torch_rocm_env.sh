#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="${TORCH_ROCM_ENV_DIR:-$ROOT_DIR/.venv-torch-rocm}"

export HSA_OVERRIDE_GFX_VERSION="${HSA_OVERRIDE_GFX_VERSION:-12.0.1}"
case ":${LD_PRELOAD:-}:" in
  *:/opt/rocm/lib/libamdhip64.so:*) ;;
  *) export LD_PRELOAD="/opt/rocm/lib/libamdhip64.so${LD_PRELOAD:+:${LD_PRELOAD}}";;
esac
case ":${LD_LIBRARY_PATH:-}:" in
  *:/opt/rocm/lib:*) ;;
  *) export LD_LIBRARY_PATH="/opt/rocm/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}";;
esac

if [[ $# -eq 0 ]]; then
  exec "${ENV_DIR}/bin/python"
fi

exec "${ENV_DIR}/bin/python" "$@"
