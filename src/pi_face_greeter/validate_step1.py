from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from pi_face_greeter.camera import create_camera
from pi_face_greeter.config_loader import load_config
from pi_face_greeter.logger import setup_logging
from pi_face_greeter.tts import speak_from_config

logger = logging.getLogger("pi_face_greeter.validate_step1")

STEP1_FRAME = "step1_frame.jpg"


def validate_camera(camera_cfg: dict[str, Any]) -> Path:
    if not camera_cfg.get("enabled", True):
        raise RuntimeError("Camera is disabled in config")

    capture_dir = Path(camera_cfg.get("capture_dir", "data/captured"))
    output_path = capture_dir / STEP1_FRAME

    camera = create_camera(camera_cfg)
    try:
        frame = camera.capture_frame()
        saved = camera.save_frame(frame, output_path)
        if saved.stat().st_size == 0:
            raise RuntimeError(f"Captured frame is empty: {saved}")
        return saved
    finally:
        camera.close()


def validate_tts(tts_cfg: dict[str, Any]) -> None:
    if not tts_cfg.get("enabled", True):
        raise RuntimeError("TTS is disabled in config")

    greeting = tts_cfg.get(
        "placeholder_greeting",
        "Hello. Face recognition is not enabled yet.",
    )
    speak_from_config(greeting, tts_cfg)


def run_validate_step1(config: dict[str, Any]) -> int:
    camera_cfg = config.get("camera", {})
    tts_cfg = config.get("tts", {})

    print("Step 1 validation: Camera Module 3 + USB TTS (no PIR)\n")

    try:
        print("[1/2] Camera capture...")
        frame_path = validate_camera(camera_cfg)
        print(f"      OK — saved {frame_path} ({frame_path.stat().st_size} bytes)")
    except Exception as exc:
        print(f"      FAIL — {exc}", file=sys.stderr)
        logger.exception("Camera validation failed")
        print("\nTroubleshooting: rpicam-hello --list-cameras", file=sys.stderr)
        return 1

    try:
        print("[2/2] Text-to-speech...")
        validate_tts(tts_cfg)
        print("      OK — greeting spoken")
    except Exception as exc:
        print(f"      FAIL — {exc}", file=sys.stderr)
        logger.exception("TTS validation failed")
        alsa = tts_cfg.get("alsa_device")
        if not alsa:
            print("Troubleshooting: run aplay -l and set tts.alsa_device in config", file=sys.stderr)
        return 1

    print("\nStep 1 validation passed.")
    return 0


def main() -> int:
    config = load_config()
    logging_cfg = config.get("logging", {})
    setup_logging(
        level=logging_cfg.get("level", "INFO"),
        log_file=logging_cfg.get("file"),
    )
    return run_validate_step1(config)
