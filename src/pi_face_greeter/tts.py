from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from pi_face_greeter.alsa_devices import (
    detect_usb_playback_device as detect_usb_alsa_device,
    normalize_alsa_device,
    parse_usb_playback_device,
    resolve_playback_device,
)
from pi_face_greeter.config_loader import PROJECT_ROOT

_CHIME_SAMPLE_RATE = 16000

logger = logging.getLogger("pi_face_greeter.tts")

_voice_cache: dict[str, Any] = {}


def speak(
    text: str,
    voice: str = "en",
    alsa_device: str | None = None,
    *,
    on_audio_start: Callable[[], None] | None = None,
) -> None:
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
    if on_audio_start is not None:
        on_audio_start()
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
    *,
    on_audio_start: Callable[[], None] | None = None,
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
        if on_audio_start is not None:
            on_audio_start()
        subprocess.run(command, check=True)
    finally:
        if wav_path is not None:
            Path(wav_path).unlink(missing_ok=True)


def apply_speech_pronunciation(text: str) -> str:
    return re.sub(r"\bFreyja\b", "Fraya", text, flags=re.IGNORECASE)


def play_chime(tts_cfg: dict[str, Any]) -> None:
    if shutil.which("aplay") is None:
        return

    alsa_device = resolve_playback_device(tts_cfg.get("alsa_device"))
    sample_rate = _CHIME_SAMPLE_RATE
    tone_a = 880.0
    tone_b = 1174.7
    duration = 0.08
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    wave_a = (0.25 * np.sin(2 * np.pi * tone_a * t)).astype(np.float32)
    wave_b = (0.25 * np.sin(2 * np.pi * tone_b * t)).astype(np.float32)
    envelope = np.linspace(1.0, 0.2, wave_a.size, dtype=np.float32)
    pcm = np.concatenate([(wave_a * envelope), (wave_b * envelope)])
    pcm_int16 = (pcm * 32767).astype(np.int16)

    wav_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            wav_path = handle.name
        with wave.open(wav_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_int16.tobytes())

        command = ["aplay", "-q"]
        if alsa_device:
            command.extend(["-D", alsa_device])
        command.append(wav_path)
        subprocess.run(command, check=True)
    finally:
        if wav_path is not None:
            Path(wav_path).unlink(missing_ok=True)


def speak_from_config(
    text: str,
    tts_cfg: dict[str, Any],
    *,
    on_audio_start: Callable[[], None] | None = None,
) -> None:
    if not tts_cfg.get("enabled", True):
        logger.info("TTS disabled in config, skipping speech")
        return

    text = apply_speech_pronunciation(text)
    engine = tts_cfg.get("engine", "espeak")
    alsa_device = resolve_playback_device(tts_cfg.get("alsa_device"))
    espeak_voice = tts_cfg.get("voice", "en")

    if engine == "piper":
        piper_cfg = tts_cfg.get("piper", {})
        try:
            speak_piper(
                text=text,
                model_path=piper_cfg.get("model", "data/voices/en_US-lessac-high.onnx"),
                alsa_device=alsa_device,
                length_scale=float(piper_cfg.get("length_scale", 1.0)),
                on_audio_start=on_audio_start,
            )
            return
        except Exception:
            logger.error("Piper TTS failed (engine=piper)", exc_info=True)
            if not tts_cfg.get("fallback_to_espeak", False):
                raise

    speak(
        text=text,
        voice=espeak_voice,
        alsa_device=alsa_device,
        on_audio_start=on_audio_start,
    )
