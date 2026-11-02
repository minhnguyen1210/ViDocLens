#!/usr/bin/env bash
set -euo pipefail
VIDOCLENS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VIDOCLENS_UV="$HOME/.local/share/vidoclens-bootstrap/bin/uv"
VIDOCLENS_KIND="${1:?Use ml or ocr}"
case "$VIDOCLENS_KIND" in
  ml)
    VIDOCLENS_PY="$HOME/.venvs/vidoclens-ml/bin/python"
    "$VIDOCLENS_UV" pip install --python "$VIDOCLENS_PY" 'torch==2.8.0' 'torchvision==0.23.0' --index-url https://download.pytorch.org/whl/cu126
    "$VIDOCLENS_UV" pip install --python "$VIDOCLENS_PY" -r "$VIDOCLENS_ROOT/infra/requirements/phase0-ml.in" -e "$VIDOCLENS_ROOT[serve,dev]"
    ;;
  ocr)
    VIDOCLENS_PY="$HOME/.venvs/vidoclens-ocr/bin/python"
    "$VIDOCLENS_UV" pip install --python "$VIDOCLENS_PY" -r "$VIDOCLENS_ROOT/infra/requirements/phase0-ocr.in" -e "$VIDOCLENS_ROOT"
    ;;
  *) echo 'Use ml or ocr' >&2; exit 2 ;;
esac
"$VIDOCLENS_UV" pip check --python "$VIDOCLENS_PY"
