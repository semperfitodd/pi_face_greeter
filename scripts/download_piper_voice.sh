#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VOICE_DIR="$PROJECT_ROOT/data/voices"
MODEL_NAME="en_US-amy-medium"
BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium"

mkdir -p "$VOICE_DIR"

download_if_missing() {
  local filename="$1"
  local destination="$VOICE_DIR/$filename"
  if [[ -f "$destination" ]]; then
    echo "Already present: $destination"
    return
  fi

  echo "Downloading $filename..."
  curl -L --fail --show-error "$BASE_URL/$filename" -o "$destination"
}

download_if_missing "${MODEL_NAME}.onnx"
download_if_missing "${MODEL_NAME}.onnx.json"

echo "Piper voice ready in $VOICE_DIR"
