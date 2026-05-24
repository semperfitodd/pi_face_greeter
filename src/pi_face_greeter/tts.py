from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import Any

logger = logging.getLogger("pi_face_greeter.tts")


def speak(text: str, voice: str = "en", alsa_device: str | None = None) -> None:
    if not text.strip():
        logger.warning("Empty TTS text, skipping")
        return

    if shutil.which("espeak-ng") is None:
        raise RuntimeError("espeak-ng not found. Install with: sudo apt install espeak-ng")

    command = ["espeak-ng", "-v", voice, text]
    env = None
    if alsa_device:
        env = os.environ.copy()
        env["AUDIODEV"] = alsa_device

    logger.info("Speaking greeting")
    subprocess.run(command, check=True, env=env)


def speak_from_config(text: str, tts_cfg: dict[str, Any]) -> None:
    if not tts_cfg.get("enabled", True):
        logger.info("TTS disabled in config, skipping speech")
        return

    engine = tts_cfg.get("engine", "espeak")
    if engine != "espeak":
        raise ValueError(f"Unsupported TTS engine: {engine}")

    speak(
        text=text,
        voice=tts_cfg.get("voice", "en"),
        alsa_device=tts_cfg.get("alsa_device"),
    )
