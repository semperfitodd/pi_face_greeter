from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

from pi_face_greeter.config_loader import PROJECT_ROOT

logger = logging.getLogger("pi_face_greeter.tts")

_voice_cache: dict[str, Any] = {}


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
    sentence_silence: float = 0.3,
) -> None:
    if not text.strip():
        logger.warning("Empty TTS text, skipping")
        return

    if shutil.which("aplay") is None:
        raise RuntimeError("aplay not found. Install with: sudo apt install alsa-utils")

    try:
        from piper import PiperVoice
        from piper.config import SynthesisConfig
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

        syn_config = SynthesisConfig(
            length_scale=length_scale,
            sentence_silence=sentence_silence,
        )
        with wave.open(wav_path, "wb") as wav_file:
            voice.synthesize(text, wav_file, syn_config=syn_config)

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
    alsa_device = tts_cfg.get("alsa_device")
    espeak_voice = tts_cfg.get("voice", "en")

    if engine == "piper":
        piper_cfg = tts_cfg.get("piper", {})
        try:
            speak_piper(
                text=text,
                model_path=piper_cfg.get("model", "data/voices/en_US-amy-medium.onnx"),
                alsa_device=alsa_device,
                length_scale=float(piper_cfg.get("length_scale", 1.0)),
                sentence_silence=float(piper_cfg.get("sentence_silence", 0.3)),
            )
            return
        except Exception:
            logger.warning("Piper TTS failed; falling back to espeak-ng", exc_info=True)

    speak(text=text, voice=espeak_voice, alsa_device=alsa_device)
