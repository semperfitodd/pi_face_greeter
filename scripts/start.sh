#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
PIPER_MODEL="${PIPER_MODEL_NAME:-en_US-amy-medium}"
WHISPER_MODEL_DIR="$PROJECT_ROOT/data/models/faster-whisper-tiny.en"

system_tools_missing() {
  local tool
  for tool in python3 aplay arecord espeak-ng ollama curl; do
    if ! command -v "$tool" >/dev/null 2>&1; then
      return 0
    fi
  done
  return 1
}

venv_ready() {
  [[ -d "$PROJECT_ROOT/.venv" ]] || return 1
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.venv/bin/activate"
  python -c "import pi_face_greeter, piper, faster_whisper" >/dev/null 2>&1 || return 1

  local piper_model="$PROJECT_ROOT/data/voices/${PIPER_MODEL}.onnx"
  [[ -f "$piper_model" ]] || return 1
  [[ -f "$WHISPER_MODEL_DIR/model.bin" ]] || return 1
  return 0
}

wait_for_ollama() {
  local attempt
  for attempt in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

if system_tools_missing; then
  echo "Missing system tools; running setup_system.sh..."
  "$PROJECT_ROOT/scripts/setup_system.sh"
fi

if ! venv_ready; then
  echo "Python environment or models missing; running setup_venv.sh..."
  "$PROJECT_ROOT/scripts/setup_venv.sh"
fi

# shellcheck disable=SC1091
source "$PROJECT_ROOT/.venv/bin/activate"

if ! curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null; then
  echo "Starting Ollama service..."
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl start ollama || true
  fi
  if ! wait_for_ollama; then
    echo "Warning: Ollama did not become reachable on 127.0.0.1:11434" >&2
  fi
fi

if command -v ollama >/dev/null 2>&1; then
  if ! ollama list 2>/dev/null | grep -q "^${OLLAMA_MODEL}[[:space:]]"; then
    echo "Pulling Ollama model: $OLLAMA_MODEL"
    ollama pull "$OLLAMA_MODEL"
  fi
fi

python - <<'PY'
from pathlib import Path

import yaml

config_path = Path("config/config.yaml")
config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
ollama_enabled = bool(config.get("ollama", {}).get("enabled", False))
conversation_enabled = bool(config.get("conversation", {}).get("enabled", False))
if not ollama_enabled:
    print(
        "Warning: ollama.enabled is false in config/config.yaml; "
        "Vesper will not use the local LLM."
    )
if not conversation_enabled:
    print(
        "Warning: conversation.enabled is false in config/config.yaml; "
        "the greeter will not listen after the opener."
    )
PY

export PYTHONUNBUFFERED=1
if [[ -z "${DISPLAY:-}" ]]; then
  export DISPLAY=:0
fi

echo "Starting Pi Face Greeter kiosk..."
exec pi-face-greeter-app
