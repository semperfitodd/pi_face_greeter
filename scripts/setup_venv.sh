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

echo "venv ready. Activate with: source .venv/bin/activate"
echo "Run the app with: pi-face-greeter-app"
echo "Note: face_recognition/dlib build can take a while on the Pi."
