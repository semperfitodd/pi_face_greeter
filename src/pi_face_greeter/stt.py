from __future__ import annotations

import logging
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

from pi_face_greeter.config_loader import PROJECT_ROOT
from pi_face_greeter.mic import CHANNELS, SAMPLE_RATE, SAMPLE_WIDTH, MicStream
from pi_face_greeter.vad import SileroVADSession

logger = logging.getLogger("pi_face_greeter.stt")

CHUNK_FRAMES = 512

_model_cache: dict[str, Any] = {}


def _resolve_model_path(model_path: str | Path) -> Path:
    path = Path(model_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


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


def listen_utterance(mic: MicStream, stt_cfg: dict[str, Any]) -> bytes | None:
    if not stt_cfg.get("enabled", True):
        return None

    vad_model = stt_cfg.get("vad_model", "data/models/silero_vad.onnx")
    threshold = float(stt_cfg.get("vad_threshold", 0.5))
    silence_seconds = float(stt_cfg.get("silence_seconds", 0.8))
    start_timeout = float(stt_cfg.get("start_timeout_seconds", 6.0))
    max_record_seconds = float(stt_cfg.get("max_record_seconds", 8.0))

    vad = SileroVADSession(vad_model)
    chunks: list[bytes] = []
    speech_started = False
    silence_elapsed = 0.0
    frame_duration = mic.frame_samples / SAMPLE_RATE
    deadline = time.monotonic() + start_timeout
    max_deadline = time.monotonic() + max_record_seconds
    frames_seen = 0
    peak_prob = 0.0
    peak_rms = 0.0

    for frame in mic.iter_frames(timeout=0.5):
        if time.monotonic() > max_deadline:
            break

        frames_seen += 1
        samples = np.frombuffer(frame, dtype=np.int16)
        if samples.size:
            peak_rms = max(peak_rms, float(np.sqrt(np.mean(samples.astype(np.float32) ** 2))))

        prob = vad.speech_probability(frame)
        peak_prob = max(peak_prob, prob)
        is_speech = prob >= threshold

        if not speech_started:
            if is_speech:
                speech_started = True
                chunks.append(frame)
            elif time.monotonic() > deadline:
                logger.info(
                    "No speech within start timeout: frames=%d peak_vad=%.3f peak_rms=%.1f threshold=%.2f",
                    frames_seen,
                    peak_prob,
                    peak_rms,
                    threshold,
                )
                return None
            continue

        chunks.append(frame)
        if is_speech:
            silence_elapsed = 0.0
        else:
            silence_elapsed += frame_duration
            if silence_elapsed >= silence_seconds:
                break

    if not chunks:
        logger.info(
            "No speech captured: frames=%d peak_vad=%.3f peak_rms=%.1f threshold=%.2f",
            frames_seen,
            peak_prob,
            peak_rms,
            threshold,
        )
        return None
    return b"".join(chunks)


def listen_once(mic: MicStream | None, stt_cfg: dict[str, Any]) -> str | None:
    if mic is None:
        logger.warning("Mic stream not available for STT")
        return None

    pcm = listen_utterance(mic, stt_cfg)
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


def listen_from_config(mic: MicStream | None, stt_cfg: dict[str, Any]) -> str | None:
    try:
        return listen_once(mic, stt_cfg)
    except Exception:
        logger.warning("Speech capture or transcription failed", exc_info=True)
        return None
