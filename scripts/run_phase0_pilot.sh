#!/usr/bin/env bash
# Local feasibility only; preserves each run in a new, ignored artifact directory.
set -euo pipefail
VIDOCLENS_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VIDOCLENS_KIND="${1:?Use student or ocr}"
VIDOCLENS_RUN="${2:?Provide a new run name}"
VIDOCLENS_SUFFIX="${3:-}"
if [[ ! "$VIDOCLENS_RUN" =~ ^[a-zA-Z0-9_-]+$ ]]; then
  echo 'Run name must contain only letters, digits, underscores or hyphens.' >&2
  exit 2
fi
case "$VIDOCLENS_SUFFIX" in ''|-repro) ;; *) exit 2 ;; esac
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1
VIDOCLENS_ARGS=(--root "$VIDOCLENS_ROOT" \
  --manifest "$VIDOCLENS_ROOT/data/manifests/receiptvqa_phase0_pilot.json" \
  --image-inventory "$VIDOCLENS_ROOT/data/manifests/receiptvqa_rotated_image_manifest.json" \
  --output "$VIDOCLENS_ROOT/artifacts/phase0/$VIDOCLENS_RUN")
case "$VIDOCLENS_KIND" in
  student)
    "$HOME/.venvs/vidoclens-ml$VIDOCLENS_SUFFIX/bin/python" -m vidoclens.student.smoke \
      "${VIDOCLENS_ARGS[@]}" \
      --model "$VIDOCLENS_ROOT/artifacts/models/Qwen3-VL-2B-Instruct/89644892e4d85e24eaac8bacfd4f463576704203"
    ;;
  ocr)
    "$HOME/.venvs/vidoclens-ocr$VIDOCLENS_SUFFIX/bin/python" -m vidoclens.ocr.smoke \
      "${VIDOCLENS_ARGS[@]}" \
      --detector "$VIDOCLENS_ROOT/artifacts/models/paddleocr/PP-OCRv5_server_det/ca867c897ecbca8873081573a802ad70d499cb94" \
      --recognizer "$VIDOCLENS_ROOT/artifacts/models/paddleocr/latin_PP-OCRv5_mobile_rec/ab2cd5cc5fa6309be2e5acdfe66eca2c2c127d57"
    ;;
  *) echo 'Use student or ocr' >&2; exit 2 ;;
esac
