from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

import numpy as np

from pi_face_greeter.config_loader import PROJECT_ROOT
from pi_face_greeter.tts import _APLAY_CARD_LINE, normalize_alsa_device

logger = logging.getLogger("pi_face_greeter.stt")

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
CHUNK_FRAMES = 320

_model_cache: dict[str, Any] = {}


def parse_usb_capture_device(arecord_listing: str) -> str | None:
    for line in arecord_listing.splitlines():
        if "usb" not in line.lower():
            continue
        match = _APLAY_CARD_LINE.match(line.strip())
        if match is None:
            continue
        card = match.group(1)
        return f"plughw:{card},0"
    return None


def detect_usb_capture_device() -> str | None:
    if shutil.which("arecord") is None:
        logger.debug("arecord not found; cannot detect USB capture device")
        return None

    try:
        completed = subprocess.run(
            ["arecord", "-l"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        logger.warning("Failed to list ALSA capture devices", exc_info=True)
        return None

    device = parse_usb_capture_device(completed.stdout)
    if device is not None:
        logger.info("Using USB capture device: %s", device)
    else:
        logger.debug("No USB capture card found in arecord -l output")
    return device


def resolve_capture_device(configured: str | None) -> str | None:
    explicit = normalize_alsa_device(configured)
    if explicit is not None:
        return explicit
    return detect_usb_capture_device()


def _resolve_model_path(model_path: str | Path) -> Path:
    path = Path(model_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _rms(chunk: bytes) -> float:
    if len(chunk) < SAMPLE_WIDTH:
        return 0.0
    samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float64)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples * samples)))


def record_until_silence(
    *,
    alsa_device: str | None,
    max_record_seconds: float = 8.0,
    silence_seconds: float = 1.2,
    start_timeout_seconds: float = 5.0,
    speech_rms_threshold: float = 400.0,
) -> bytes | None:
    if shutil.which("arecord") is None:
        raise RuntimeError("arecord not found. Install with: sudo apt install alsa-utils")

    alsa_device = normalize_alsa_device(alsa_device)
    chunk_bytes = CHUNK_FRAMES * SAMPLE_WIDTH * CHANNELS

    command = [
        "arecord",
        "-q",
        "-f",
        "S16_LE",
        "-r",
        str(SAMPLE_RATE),
        "-c",
        str(CHANNELS),
        "-t",
        "raw",
    ]
    if alsa_device:
        command.extend(["-D", alsa_device])

    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if proc.stdout is None:
        proc.kill()
        raise RuntimeError("arecord did not provide stdout")

    chunks: list[bytes] = []
    speech_started = False
    silence_elapsed = 0.0
    total_elapsed = 0.0
    start_deadline = start_timeout_seconds
    chunk_duration = CHUNK_FRAMES / SAMPLE_RATE

    try:
        while total_elapsed < max_record_seconds:
            chunk = proc.stdout.read(chunk_bytes)
            if not chunk:
                break

            total_elapsed += chunk_duration
            level = _rms(chunk)

            if not speech_started:
                if level >= speech_rms_threshold:
                    speech_started = True
                    chunks.append(chunk)
                else:
                    start_deadline -= chunk_duration
                    if start_deadline <= 0:
                        logger.debug("No speech detected within start timeout")
                        return None
                continue

            chunks.append(chunk)
            if level < speech_rms_threshold:
                silence_elapsed += chunk_duration
                if silence_elapsed >= silence_seconds:
                    break
            else:
                silence_elapsed = 0.0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

    if not chunks:
        return None
    return b"".join(chunks)


def _raw_pcm_to_wav(pcm: bytes, wav_path: Path) -> None:
    with wave.open(str(wav_path), "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(SAMPLE_WIDTH)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm)


def _load_whisper_model(model_path: Path, compute_type: str) -> Any:
    cache_key = f"{model_path}:{compute_type}"
    cached = _model_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            'faster-whisper not installed. Install with: pip install -e ".[stt]"'
        ) from exc

    logger.info("Loading faster-whisper model: %s", model_path)
    model = WhisperModel(str(model_path), device="cpu", compute_type=compute_type)
    _model_cache[cache_key] = model
    return model


def transcribe_pcm(
    pcm: bytes,
    *,
    model_path: str | Path,
    compute_type: str = "int8",
    language: str = "en",
) -> str:
    resolved = _resolve_model_path(model_path)
    if not resolved.is_dir() and not resolved.is_file():
        raise FileNotFoundError(f"Whisper model not found: {resolved}")

    wav_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
            wav_path = handle.name
        _raw_pcm_to_wav(pcm, Path(wav_path))

        model = _load_whisper_model(resolved, compute_type)
        segments, _info = model.transcribe(
            wav_path,
            language=language,
            beam_size=1,
            vad_filter=True,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text
    finally:
        if wav_path is not None:
            Path(wav_path).unlink(missing_ok=True)


def listen_once(stt_cfg: dict[str, Any]) -> str | None:
    if not stt_cfg.get("enabled", True):
        return None

    alsa_device = resolve_capture_device(stt_cfg.get("alsa_device"))
    pcm = record_until_silence(
        alsa_device=alsa_device,
        max_record_seconds=float(stt_cfg.get("max_record_seconds", 8.0)),
        silence_seconds=float(stt_cfg.get("silence_seconds", 1.2)),
        start_timeout_seconds=float(stt_cfg.get("start_timeout_seconds", 5.0)),
        speech_rms_threshold=float(stt_cfg.get("speech_rms_threshold", 400.0)),
    )
    if pcm is None:
        return None

    text = transcribe_pcm(
        pcm,
        model_path=stt_cfg.get("model", "data/models/faster-whisper-tiny.en"),
        compute_type=str(stt_cfg.get("compute_type", "int8")),
        language=str(stt_cfg.get("language", "en")),
    )
    if text:
        logger.info("Transcribed speech (%d chars)", len(text))
    else:
        logger.debug("Transcription empty")
    return text or None


def listen_from_config(stt_cfg: dict[str, Any]) -> str | None:
    try:
        return listen_once(stt_cfg)
    except Exception:
        logger.warning("Speech capture or transcription failed", exc_info=True)
        return None
