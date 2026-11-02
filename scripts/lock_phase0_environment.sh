#!/usr/bin/env bash
# Resolve a hashed lock from a successfully installed environment, then rebuild it.
# A successful install is still not a smoke result: run both pilots in the new venvs.
set -euo pipefail
VIDOCLENS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VIDOCLENS_UV="$HOME/.local/share/vidoclens-bootstrap/bin/uv"
VIDOCLENS_KIND="${1:?Use ml or ocr}"
case "$VIDOCLENS_KIND" in ml|ocr) ;; *) exit 2 ;; esac
VIDOCLENS_PY="$HOME/.venvs/vidoclens-$VIDOCLENS_KIND/bin/python"
VIDOCLENS_REBUILD="$HOME/.venvs/vidoclens-$VIDOCLENS_KIND-repro"
VIDOCLENS_LOCK="$VIDOCLENS_ROOT/infra/requirements/phase0-$VIDOCLENS_KIND-linux-py311.lock"
VIDOCLENS_FREEZE="$VIDOCLENS_ROOT/artifacts/phase0/$VIDOCLENS_KIND-freeze.txt"
if [ -e "$VIDOCLENS_REBUILD" ] || [ -e "$VIDOCLENS_LOCK" ]; then
  echo 'Rebuild destination or lock exists; inspect rather than overwrite.' >&2
  exit 1
fi
"$VIDOCLENS_UV" pip freeze --python "$VIDOCLENS_PY" | sed '/^#/d; /^-e /d' > "$VIDOCLENS_FREEZE"
VIDOCLENS_INDEX_ARGS=()
if [ "$VIDOCLENS_KIND" = ml ]; then
  # Both indexes are primary publishers; exact versions come from the tested inventory.
  VIDOCLENS_INDEX_ARGS=(--index https://download.pytorch.org/whl/cu126 --index-strategy unsafe-best-match)
fi
"$VIDOCLENS_UV" pip compile "$VIDOCLENS_FREEZE" --python "$VIDOCLENS_PY" \
  --generate-hashes --only-binary :all: --emit-index-url --no-annotate \
  "${VIDOCLENS_INDEX_ARGS[@]}" -o "$VIDOCLENS_LOCK" --quiet
"$VIDOCLENS_UV" venv --python 3.11.14 "$VIDOCLENS_REBUILD"
"$VIDOCLENS_UV" pip sync --python "$VIDOCLENS_REBUILD/bin/python" \
  --require-hashes --only-binary :all: "${VIDOCLENS_INDEX_ARGS[@]}" "$VIDOCLENS_LOCK"
"$VIDOCLENS_UV" pip install --python "$VIDOCLENS_REBUILD/bin/python" --no-deps -e "$VIDOCLENS_ROOT"
"$VIDOCLENS_UV" pip check --python "$VIDOCLENS_REBUILD/bin/python"
"$VIDOCLENS_UV" pip freeze --python "$VIDOCLENS_REBUILD/bin/python" | sed '/^#/d; /^-e /d' > "$VIDOCLENS_ROOT/artifacts/phase0/$VIDOCLENS_KIND-repro-freeze.txt"
diff -u "$VIDOCLENS_FREEZE" "$VIDOCLENS_ROOT/artifacts/phase0/$VIDOCLENS_KIND-repro-freeze.txt"
echo "$VIDOCLENS_KIND: hash-checked fresh environment matches original package versions; run smoke next."
