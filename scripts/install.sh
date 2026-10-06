#!/usr/bin/env bash
set -euo pipefail

# Re-exec when piped (curl ... | bash) so sudo can prompt on a real TTY.
if [[ "${PI_FACE_GREETER_INSTALL_REEXEC:-}" != "1" ]] && [[ ! -t 0 ]]; then
  tmp="$(mktemp)"
  cat >"$tmp"
  chmod +x "$tmp"
  export PI_FACE_GREETER_INSTALL_REEXEC=1
  exec bash "$tmp" "$@"
fi

INSTALL_DIR="${INSTALL_DIR:-$HOME/pi_face_greeter}"
REPO_SSH="git@github.com:semperfitodd/pi_face_greeter.git"
REPO_HTTPS="https://github.com/semperfitodd/pi_face_greeter.git"

resolve_project_root() {
  local script_path="$1"
  local candidate
  candidate="$(cd "$(dirname "$script_path")/.." && pwd)"
  if [[ -f "$candidate/pyproject.toml" ]]; then
    echo "$candidate"
    return 0
  fi
  if [[ -f "$INSTALL_DIR/pyproject.toml" ]]; then
    echo "$INSTALL_DIR"
    return 0
  fi
  return 1
}

clone_repo() {
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    echo "Using existing clone: $INSTALL_DIR"
    return 0
  fi
  if [[ -d "$INSTALL_DIR" ]] && [[ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null || true)" ]]; then
    echo "Install directory exists but is not a git repo: $INSTALL_DIR" >&2
    echo "Remove it or set INSTALL_DIR to another path." >&2
    return 1
  fi
  mkdir -p "$(dirname "$INSTALL_DIR")"
  if git clone "$REPO_SSH" "$INSTALL_DIR" 2>/dev/null; then
    return 0
  fi
  if git clone "$REPO_HTTPS" "$INSTALL_DIR" 2>/dev/null; then
    return 0
  fi
  echo "Could not clone the repository (private repo needs SSH key or GitHub login)." >&2
  echo "Clone manually, then run: cd $INSTALL_DIR && ./scripts/install.sh" >&2
  return 1
}

if ! PROJECT_ROOT="$(resolve_project_root "${BASH_SOURCE[0]}")"; then
  clone_repo
  PROJECT_ROOT="$INSTALL_DIR"
fi

cd "$PROJECT_ROOT"
LOG="$PROJECT_ROOT/data/logs/install.log"
mkdir -p "$(dirname "$LOG")"
{
  echo "=== Pi Face Greeter install $(date -Iseconds) ==="
} >>"$LOG"

CURRENT_STEP=""
SPINNER_PID=""

stop_spinner() {
  if [[ -n "$SPINNER_PID" ]]; then
    kill "$SPINNER_PID" 2>/dev/null || true
    wait "$SPINNER_PID" 2>/dev/null || true
    SPINNER_PID=""
  fi
}

install_fail() {
  stop_spinner
  echo "FAILED"
  echo ""
  echo "Install stopped at: ${CURRENT_STEP:-unknown step}"
  echo "Full log: $LOG"
  echo ""
  echo "Last lines from the log:"
  tail -n 20 "$LOG" 2>/dev/null || true
  exit 1
}

run_step() {
  local label="$1"
  shift
  CURRENT_STEP="$label"
  printf '%-24s ' "$label"
  (
    while sleep 30; do
      echo "  ${label}: still working..." >&2
    done
  ) &
  SPINNER_PID=$!
  set +e
  {
    echo ""
    echo "--- $label ---"
    "$@"
  } >>"$LOG" 2>&1
  local rc=$?
  set -e
  stop_spinner
  if [[ $rc -eq 0 ]]; then
    echo "ok"
    return 0
  fi
  install_fail
}

run_step_optional() {
  local label="$1"
  shift
  CURRENT_STEP="$label"
  printf '%-24s ' "$label"
  (
    while sleep 30; do
      echo "  ${label}: still working..." >&2
    done
  ) &
  SPINNER_PID=$!
  set +e
  {
    echo ""
    echo "--- $label ---"
    "$@"
  } >>"$LOG" 2>&1
  local rc=$?
  set -e
  stop_spinner
  if [[ $rc -eq 0 ]]; then
    echo "ok"
  else
    echo "ok (optional; see log)"
    {
      echo "Warning: optional step failed: $label (exit $rc)"
    } >>"$LOG"
  fi
}

echo "Pi Face Greeter install"
echo "Project: $PROJECT_ROOT"
echo "Log: $LOG"
echo ""

run_step "System packages" "$PROJECT_ROOT/scripts/setup_system.sh" packages
run_step "Camera and GPIO groups" "$PROJECT_ROOT/scripts/setup_system.sh" groups
run_step "Ollama" "$PROJECT_ROOT/scripts/setup_system.sh" ollama
run_step "Python packages" "$PROJECT_ROOT/scripts/setup_venv.sh" python
run_step "Voice and speech models" "$PROJECT_ROOT/scripts/setup_venv.sh" models
run_step_optional "Wake word models" "$PROJECT_ROOT/scripts/setup_venv.sh" wakeword
run_step "Language model" "$PROJECT_ROOT/scripts/setup_venv.sh" llm

echo ""
echo "Installed. Log out and back in, then run:"
echo "  cd $PROJECT_ROOT && ./scripts/start.sh"
