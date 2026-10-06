#!/usr/bin/env bash
set -euo pipefail

step="${1:-all}"

run_packages() {
  sudo apt update
  sudo apt full-upgrade -y
  sudo apt install -y \
    python3-picamera2 python3-libcamera rpicam-apps \
    python3-gpiozero python3-lgpio \
    python3-opencv \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
    pkg-config libmtdev-dev xinput xfonts-base xfonts-scalable \
    espeak-ng alsa-utils v4l-utils curl git \
    cmake build-essential libopenblas-dev liblapack-dev libjpeg-dev libsndfile1
}

run_groups() {
  sudo usermod -aG video,gpio "$USER"
}

run_ollama() {
  if command -v ollama >/dev/null 2>&1; then
    echo "Ollama already installed."
    return 0
  fi
  echo "Installing Ollama..."
  curl -fsSL https://ollama.com/install.sh | sh

  OLLAMA_ENV="/etc/systemd/system/ollama.service.d/override.conf"
  if [[ -d /etc/systemd/system ]]; then
    sudo mkdir -p /etc/systemd/system/ollama.service.d
    printf '%s\n' '[Service]' 'Environment=OLLAMA_HOST=127.0.0.1' | sudo tee "$OLLAMA_ENV" >/dev/null
    sudo systemctl daemon-reload
    if systemctl is-active --quiet ollama 2>/dev/null; then
      sudo systemctl restart ollama
    fi
    echo "Configured Ollama to listen on 127.0.0.1 only ($OLLAMA_ENV)."
  fi
}

case "$step" in
  packages) run_packages ;;
  groups) run_groups ;;
  ollama) run_ollama ;;
  all)
    run_packages
    run_groups
    run_ollama
    echo "System setup complete. Log out and back in for group changes to apply."
    ;;
  *)
    echo "Unknown setup_system step: $step" >&2
    exit 1
    ;;
esac
