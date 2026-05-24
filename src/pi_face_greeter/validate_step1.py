from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pi_face_greeter.camera import create_camera
from pi_face_greeter.cli_output import report_failure, report_success
from pi_face_greeter.config_loader import load_config
from pi_face_greeter.tts import speak_from_config

logger = logging.getLogger("pi_face_greeter.validate_step1")

STEP1_FRAME = "step1_frame.jpg"


def _log_path(config: dict[str, Any]) -> Path | None:
    log_file = config.get("logging", {}).get("file")
    return Path(log_file) if log_file else None


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
    log_path = _log_path(config)

    try:
        frame_path = validate_camera(camera_cfg)
    except Exception as exc:
        report_failure(
            "Step 1 failed: camera capture",
            exc,
            log_path,
            hint="rpicam-hello --list-cameras",
        )
        return 1

    try:
        validate_tts(tts_cfg)
    except Exception as exc:
        hint = None if tts_cfg.get("alsa_device") else "Run aplay -l and set tts.alsa_device in config"
        report_failure(
            "Step 1 failed: text-to-speech",
            exc,
            log_path,
            hint=hint,
        )
        return 1

    report_success(f"Step 1 passed. Frame: {frame_path}")
    return 0


def main() -> int:
    from pi_face_greeter.cli_output import configure_validation_logging

    config = load_config()
    logging_cfg = config.get("logging", {})
    configure_validation_logging(
        log_file=logging_cfg.get("file"),
        level=logging_cfg.get("level", "INFO"),
    )
    return run_validate_step1(config)
