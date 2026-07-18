#!/usr/bin/env bash
set -euo pipefail

source /root/miniconda3/etc/profile.d/conda.sh
conda activate auto-research

export LIGHTCODER_BASE_URL="${LIGHTCODER_BASE_URL:-https://api.deepseek.com/v1}"
export LIGHTCODER_MODEL="${LIGHTCODER_MODEL:-deepseek-v4-pro}"

if [[ -z "${LIGHTCODER_API_KEY:-}" && -f /data/.deepseek_api_key ]]; then
  export LIGHTCODER_API_KEY="$(tr -d '\r\n' < /data/.deepseek_api_key)"
fi

export PYTHONUNBUFFERED=1
