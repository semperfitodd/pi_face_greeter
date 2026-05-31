#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt full-upgrade -y
sudo apt install -y \
  python3-picamera2 python3-libcamera rpicam-apps \
  python3-gpiozero python3-lgpio \
  python3-opencv \
  libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
  pkg-config libmtdev-dev xinput xfonts-base xfonts-scalable \
  espeak-ng alsa-utils v4l-utils \
  cmake build-essential libopenblas-dev liblapack-dev libjpeg-dev

sudo usermod -aG video,gpio "$USER"

echo "apt setup complete. Log out and back in for group changes to apply."
