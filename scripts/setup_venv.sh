#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

step="${1:-all}"

VOICE_DIR="$PROJECT_ROOT/data/voices"
PIPER_MODEL_NAME="${PIPER_MODEL_NAME:-en_US-lessac-high}"
PIPER_BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high"
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
WHISPER_MODEL_DIR="$PROJECT_ROOT/data/models/faster-whisper-tiny.en"
WHISPER_REPO="${WHISPER_REPO:-Systran/faster-whisper-tiny.en}"
VAD_PATH="$PROJECT_ROOT/data/models/silero_vad.onnx"

run_python() {
  python3 -m venv --system-site-packages .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -e .
  pip install -e ".[recognition]"
  pip install -e ".[voice]"
  pip install -e ".[stt]" || {
    pip install onnxruntime scipy tqdm requests
    pip install --no-deps openwakeword
  }
}

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

run_models() {
  mkdir -p "$VOICE_DIR"
  download_piper_if_missing "${PIPER_MODEL_NAME}.onnx"
  download_piper_if_missing "${PIPER_MODEL_NAME}.onnx.json"
  echo "Piper voice ready in $VOICE_DIR"

  if [[ -d "$WHISPER_MODEL_DIR" && -f "$WHISPER_MODEL_DIR/model.bin" ]]; then
    echo "Whisper model already present: $WHISPER_MODEL_DIR"
  else
    echo "Downloading faster-whisper model to $WHISPER_MODEL_DIR ..."
    # shellcheck disable=SC1091
    source .venv/bin/activate
    python - <<PY
from huggingface_hub import snapshot_download
snapshot_download(
    "${WHISPER_REPO}",
    local_dir="${WHISPER_MODEL_DIR}",
)
PY
    echo "Whisper model ready in $WHISPER_MODEL_DIR"
  fi

  mkdir -p "$PROJECT_ROOT/data/models"
  if [[ -f "$VAD_PATH" ]]; then
    echo "Silero VAD model already present: $VAD_PATH"
  else
    echo "Downloading Silero VAD model..."
    curl -L --fail --show-error \
      "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx" \
      -o "$VAD_PATH"
    echo "Silero VAD ready at $VAD_PATH"
  fi
}

run_wakeword() {
  # shellcheck disable=SC1091
  source .venv/bin/activate
  echo "Downloading openWakeWord built-in models (hey_jarvis, etc.)..."
  python -c "import openwakeword.utils as u; u.download_models()" || {
    echo "Warning: openWakeWord model download failed. Wake word may not work until you retry install."
    return 1
  }
}

run_llm() {
  if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama not installed; skipping model pull."
    return 0
  fi
  if ollama list 2>/dev/null | grep -q "^${OLLAMA_MODEL}[[:space:]]"; then
    echo "Ollama model already present: $OLLAMA_MODEL"
  else
    echo "Pulling Ollama model: $OLLAMA_MODEL"
    ollama pull "$OLLAMA_MODEL"
  fi
}

case "$step" in
  python) run_python ;;
  models)
    # shellcheck disable=SC1091
    [[ -d .venv ]] || run_python
    run_models
    ;;
  wakeword)
    # shellcheck disable=SC1091
    source .venv/bin/activate
    run_wakeword
    ;;
  llm) run_llm ;;
  all)
    run_python
    run_models
    run_wakeword || true
    run_llm
    echo "venv ready. Run the app with: ./scripts/start.sh"
    echo "Note: face_recognition/dlib build can take a while on the Pi."
    ;;
  *)
    echo "Unknown setup_venv step: $step" >&2
    exit 1
    ;;
esac
