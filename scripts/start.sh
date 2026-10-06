#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
PIPER_MODEL="${PIPER_MODEL_NAME:-en_US-lessac-high}"
WHISPER_MODEL_DIR="$PROJECT_ROOT/data/models/faster-whisper-tiny.en"
VAD_MODEL="$PROJECT_ROOT/data/models/silero_vad.onnx"
GREETER_LOG="$PROJECT_ROOT/data/logs/greeter.log"
INSTALL_HINT="Run ./scripts/install.sh from $PROJECT_ROOT"

check_line() {
  local label="$1"
  shift
  printf '%-24s ' "$label"
  if "$@"; then
    echo "ok"
    return 0
  fi
  echo "missing"
  return 1
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

failed=0

for tool in python3 aplay arecord espeak-ng ollama; do
  if ! check_line "Tool: $tool" command -v "$tool" >/dev/null 2>&1; then
    failed=1
  fi
done

if ! check_line "Python venv" test -d "$PROJECT_ROOT/.venv"; then
  failed=1
fi

if [[ -d "$PROJECT_ROOT/.venv" ]]; then
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.venv/bin/activate"
  if ! check_line "Python imports" python -c \
    "import pi_face_greeter, piper, faster_whisper, onnxruntime" 2>/dev/null; then
    failed=1
  fi
fi

piper_model="$PROJECT_ROOT/data/voices/${PIPER_MODEL}.onnx"
if ! check_line "Piper voice" test -f "$piper_model"; then
  failed=1
fi

if ! check_line "Whisper model" test -f "$WHISPER_MODEL_DIR/model.bin"; then
  failed=1
fi

if ! check_line "Silero VAD" test -f "$VAD_MODEL"; then
  failed=1
fi

if [[ $failed -ne 0 ]]; then
  echo ""
  echo "Install incomplete. $INSTALL_HINT"
  exit 1
fi

# shellcheck disable=SC1091
source "$PROJECT_ROOT/.venv/bin/activate"

printf '%-24s ' "Ollama service"
if curl -sf "http://127.0.0.1:11434/api/tags" >/dev/null; then
  echo "ok"
else
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl start ollama 2>/dev/null || true
  fi
  if wait_for_ollama; then
    echo "ok"
  else
    echo "not reachable"
    echo "Warning: Freyja voice chat needs Ollama on 127.0.0.1:11434."
  fi
fi

if command -v ollama >/dev/null 2>&1; then
  if ollama list 2>/dev/null | grep -q "^${OLLAMA_MODEL}[[:space:]]"; then
    printf '%-24s ' "Language model"
    echo "ok"
  else
    printf '%-24s ' "Language model"
    echo "missing"
    echo "Warning: Ollama model ${OLLAMA_MODEL} not found. Re-run ./scripts/install.sh"
  fi
fi

wake_enabled="$(python - <<'PY' 2>/dev/null || echo false
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8")) or {}
w = cfg.get("wake_word") or {}
print("true" if w.get("enabled", False) else "false")
PY
)"
wake_model="$(python - <<'PY' 2>/dev/null || true
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8")) or {}
print((cfg.get("wake_word") or {}).get("model", ""))
PY
)"
if [[ "$wake_enabled" == "true" ]] && [[ -n "$wake_model" ]]; then
  printf '%-24s ' "Wake word"
  if python - <<PY 2>/dev/null
from pi_face_greeter.wake_word import _resolve_model
from pathlib import Path
ref = _resolve_model("$wake_model")
if ref is None:
    raise SystemExit(1)
from openwakeword.model import Model
if isinstance(ref, Path):
    Model(wakeword_models=[str(ref)], inference_framework="onnx")
else:
    Model(wakeword_models=[ref], inference_framework="onnx")
PY
  then
    echo "ok"
  else
    echo "not loaded"
    echo "Warning: Wake word may not work. Re-run ./scripts/install.sh (wake word step)."
  fi
fi

export PYTHONUNBUFFERED=1
if [[ -z "${DISPLAY:-}" ]]; then
  export DISPLAY=:0
fi

echo ""
echo "Starting kiosk..."
set +e
pi-face-greeter-app
rc=$?
set -e
if [[ $rc -ne 0 ]]; then
  echo "Kiosk stopped (exit $rc). See ${GREETER_LOG}."
  exit "$rc"
fi
