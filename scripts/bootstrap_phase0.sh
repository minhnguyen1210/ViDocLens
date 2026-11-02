#!/usr/bin/env bash
# Run as a normal Linux user; never installs a driver or modifies system Python.
set -euo pipefail
if [ "$(id -u)" = 0 ]; then
  echo 'Run as a non-root Linux user.' >&2
  exit 1
fi
VIDOCLENS_BOOT="$HOME/.local/share/vidoclens-bootstrap"
if [ ! -e "$VIDOCLENS_BOOT" ]; then
  python3 -m venv "$VIDOCLENS_BOOT"
fi
"$VIDOCLENS_BOOT/bin/python" -m pip install 'uv==0.9.6'
VIDOCLENS_UV="$VIDOCLENS_BOOT/bin/uv"
"$VIDOCLENS_UV" python install 3.11.14
mkdir -p "$HOME/.venvs" "$HOME/vidoclens-storage/cache" "$HOME/vidoclens-storage/artifacts"
for VIDOCLENS_ENV in ml ocr; do
  VIDOCLENS_TARGET="$HOME/.venvs/vidoclens-$VIDOCLENS_ENV"
  if [ -e "$VIDOCLENS_TARGET" ]; then
    echo "Environment already exists; inspect before continuing: $VIDOCLENS_TARGET" >&2
    exit 1
  fi
  "$VIDOCLENS_UV" venv --python 3.11.14 "$VIDOCLENS_TARGET"
done
"$HOME/.venvs/vidoclens-ml/bin/python" --version
"$HOME/.venvs/vidoclens-ocr/bin/python" --version
