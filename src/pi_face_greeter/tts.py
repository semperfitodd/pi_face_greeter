from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

from pi_face_greeter.config_loader import PROJECT_ROOT

logger = logging.getLogger("pi_face_greeter.tts")

_ALSA_DEVICE_PATTERN = re.compile(r"^(default|plughw:\d+,\d+|hw:\d+,\d+)$")
_APLAY_CARD_LINE = re.compile(r"^card (\d+):", re.IGNORECASE)

_voice_cache: dict[str, Any] = {}


def parse_usb_playback_device(aplay_listing: str) -> str | None:
    for line in aplay_listing.splitlines():
        if "usb" not in line.lower():
            continue
        match = _APLAY_CARD_LINE.match(line.strip())
        if match is None:
            continue
        card = match.group(1)
        return f"plughw:{card},0"
    return None


def detect_usb_alsa_device() -> str | None:
    if shutil.which("aplay") is None:
        logger.debug("aplay not found; cannot detect USB audio device")
        return None

    try:
        completed = subprocess.run(
            ["aplay", "-l"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        logger.warning("Failed to list ALSA playback devices", exc_info=True)
        return None

    device = parse_usb_playback_device(completed.stdout)
    if device is not None:
        logger.info("Using USB playback device: %s", device)
    else:
        logger.debug("No USB playback card found in aplay -l output")
    return device


def resolve_playback_device(configured: str | None) -> str | None:
    explicit = normalize_alsa_device(configured)
    if explicit is not None:
        return explicit
    return detect_usb_alsa_device()


def normalize_alsa_device(device: str | None) -> str | None:
    if device is None:
        return None
    token = str(device).strip()
    if not token:
        return None
    if not _ALSA_DEVICE_PATTERN.match(token):
        raise ValueError(f"Invalid ALSA device: {device!r}")
    return token


def speak(text: str, voice: str = "en", alsa_device: str | None = None) -> None:
    if not text.strip():
        logger.warning("Empty TTS text, skipping")
        return

    if shutil.which("espeak-ng") is None:
        raise RuntimeError("espeak-ng not found. Install with: sudo apt install espeak-ng")

    alsa_device = normalize_alsa_device(alsa_device)
    command = ["espeak-ng", "-v", voice, text]
    env = None
    if alsa_device:
        env = os.environ.copy()
        env["AUDIODEV"] = alsa_device

    logger.info("Speaking with espeak-ng")
    subprocess.run(command, check=True, env=env)


def _resolve_model_path(model_path: str | Path) -> Path:
    path = Path(model_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def speak_piper(
    text: str,
    model_path: str | Path,
    alsa_device: str | None = None,
    length_scale: float = 1.0,
) -> None:
    if not text.strip():
        logger.warning("Empty TTS text, skipping")
        return

    if shutil.which("aplay") is None:
        raise RuntimeError("aplay not found. Install with: sudo apt install alsa-utils")

    alsa_device = normalize_alsa_device(alsa_device)
    try:
        from piper import PiperVoice, SynthesisConfig
    except ImportError as exc:
        raise RuntimeError(
            "piper-tts not installed. Install with: pip install -e \".[voice]\""
        ) from exc

    resolved = _resolve_model_path(model_path)
    if not resolved.is_file():
        raise FileNotFoundError(f"Piper model not found: {resolved}")

    cache_key = str(resolved)
    voice = _voice_cache.get(cache_key)
    if voice is None:
        logger.info("Loading Piper voice model: %s", resolved)
        voice = PiperVoice.load(str(resolved))
        _voice_cache[cache_key] = voice

    wav_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            wav_path = handle.name

        syn_config = SynthesisConfig(length_scale=length_scale)
        with wave.open(wav_path, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file, syn_config=syn_config)

        command = ["aplay", "-q"]
        if alsa_device:
            command.extend(["-D", alsa_device])
        command.append(wav_path)

        logger.info("Speaking with Piper")
        subprocess.run(command, check=True)
    finally:
        if wav_path is not None:
            Path(wav_path).unlink(missing_ok=True)


def speak_from_config(text: str, tts_cfg: dict[str, Any]) -> None:
    if not tts_cfg.get("enabled", True):
        logger.info("TTS disabled in config, skipping speech")
        return

    engine = tts_cfg.get("engine", "espeak")
    alsa_device = resolve_playback_device(tts_cfg.get("alsa_device"))
    espeak_voice = tts_cfg.get("voice", "en")

    if engine == "piper":
        piper_cfg = tts_cfg.get("piper", {})
        try:
            speak_piper(
                text=text,
                model_path=piper_cfg.get("model", "data/voices/en_US-amy-medium.onnx"),
                alsa_device=alsa_device,
                length_scale=float(piper_cfg.get("length_scale", 1.0)),
            )
            return
        except Exception:
            logger.warning("Piper TTS failed; falling back to espeak-ng", exc_info=True)

    speak(text=text, voice=espeak_voice, alsa_device=alsa_device)
