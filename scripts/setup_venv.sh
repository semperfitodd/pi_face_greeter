#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

python3 -m venv --system-site-packages .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
pip install -e ".[recognition]"
pip install -e ".[voice]"

VOICE_DIR="$PROJECT_ROOT/data/voices"
PIPER_MODEL_NAME="${PIPER_MODEL_NAME:-en_US-amy-medium}"
PIPER_BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:1b}"

mkdir -p "$VOICE_DIR"

download_piper_if_missing() {
  local filename="$1"
  local destination="$VOICE_DIR/$filename"
  if [[ -f "$destination" ]]; then
    echo "Already present: $destination"
    return
  fi

  echo "Downloading $filename..."
  curl -L --fail --show-error "$PIPER_BASE_URL/$filename" -o "$destination"
}

download_piper_if_missing "${PIPER_MODEL_NAME}.onnx"
download_piper_if_missing "${PIPER_MODEL_NAME}.onnx.json"
echo "Piper voice ready in $VOICE_DIR"

if command -v ollama >/dev/null 2>&1; then
  if ollama list 2>/dev/null | grep -q "^${OLLAMA_MODEL}[[:space:]]"; then
    echo "Ollama model already present: $OLLAMA_MODEL"
  else
    echo "Pulling Ollama model: $OLLAMA_MODEL"
    ollama pull "$OLLAMA_MODEL"
  fi
else
  echo "Ollama not installed; skipping model pull. Run ./scripts/setup_system.sh first."
fi

echo "venv ready. Activate with: source .venv/bin/activate"
echo "Run the app with: pi-face-greeter-app"
echo "Note: face_recognition/dlib build can take a while on the Pi."
