from __future__ import annotations

import logging
import tempfile
import time
import wave
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from pi_face_greeter.config_loader import PROJECT_ROOT
from pi_face_greeter.mic import CHANNELS, SAMPLE_RATE, SAMPLE_WIDTH, MicStream
from pi_face_greeter.vad import SileroVADSession, VAD_UNAVAILABLE

logger = logging.getLogger("pi_face_greeter.stt")

CHUNK_FRAMES = 512

_model_cache: dict[str, Any] = {}

NOISE_FLOOR_SECONDS = 0.3
DEFAULT_PRE_ROLL_SECONDS = 0.4


@dataclass(frozen=True)
class UtteranceCaptureResult:
    pcm: bytes | None
    peak_vad: float = 0.0
    peak_rms: float = 0.0
    noise_floor: float = 0.0


@dataclass(frozen=True)
class ListenOutcome:
    text: str | None = None
    peak_vad: float = 0.0
    peak_rms: float = 0.0
    noise_floor: float = 0.0


def _resolve_model_path(model_path: str | Path) -> Path:
    path = Path(model_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _frame_rms(frame: bytes) -> float:
    samples = np.frombuffer(frame, dtype=np.int16)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))


def _counts_as_speech(
    prob: float,
    rms: float,
    *,
    noise_floor: float,
    threshold: float,
    energy_fallback: bool,
    energy_ratio: float,
    min_speech_rms: float,
) -> bool:
    if prob >= threshold:
        return True
    if not energy_fallback:
        return False
    if rms < min_speech_rms:
        return False
    if noise_floor <= 0:
        return prob == VAD_UNAVAILABLE and rms >= min_speech_rms
    return rms >= noise_floor * energy_ratio


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


def listen_utterance(
    mic: MicStream,
    stt_cfg: dict[str, Any],
    *,
    on_phase: Callable[[str], None] | None = None,
) -> UtteranceCaptureResult:
    empty = UtteranceCaptureResult(None)
    if not stt_cfg.get("enabled", True):
        return empty

    vad_model = stt_cfg.get("vad_model", "data/models/silero_vad.onnx")
    threshold = float(stt_cfg.get("vad_threshold", 0.4))
    silence_seconds = float(stt_cfg.get("silence_seconds", 0.8))
    start_timeout = float(stt_cfg.get("start_timeout_seconds", 6.0))
    max_record_seconds = float(stt_cfg.get("max_record_seconds", 8.0))
    energy_fallback = bool(stt_cfg.get("energy_fallback", True))
    energy_ratio = float(stt_cfg.get("energy_ratio", 3.0))
    min_speech_rms = float(stt_cfg.get("min_speech_rms", 200.0))
    pre_roll_seconds = float(stt_cfg.get("pre_roll_seconds", DEFAULT_PRE_ROLL_SECONDS))

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
    noise_rms_samples: list[float] = []
    noise_floor_deadline = time.monotonic() + NOISE_FLOOR_SECONDS

    pre_roll_maxlen = max(1, int(pre_roll_seconds / frame_duration))
    preroll: deque[bytes] = deque(maxlen=pre_roll_maxlen)

    for frame in mic.iter_frames(timeout=0.5):
        if time.monotonic() > max_deadline:
            break

        frames_seen += 1
        preroll.append(frame)
        rms = _frame_rms(frame)
        peak_rms = max(peak_rms, rms)

        if not speech_started and time.monotonic() < noise_floor_deadline:
            noise_rms_samples.append(rms)

        noise_floor = float(np.median(noise_rms_samples)) if noise_rms_samples else 0.0

        prob = vad.speech_probability(frame)
        if prob >= 0:
            peak_prob = max(peak_prob, prob)

        is_speech = _counts_as_speech(
            prob,
            rms,
            noise_floor=noise_floor,
            threshold=threshold,
            energy_fallback=energy_fallback,
            energy_ratio=energy_ratio,
            min_speech_rms=min_speech_rms,
        )

        if not speech_started:
            if is_speech:
                speech_started = True
                if on_phase is not None:
                    on_phase("Hearing you...")
                chunks.extend(preroll)
            elif time.monotonic() > deadline:
                logger.info(
                    "No speech within start timeout: frames=%d peak_vad=%.3f peak_rms=%.1f "
                    "noise_floor=%.1f threshold=%.2f",
                    frames_seen,
                    peak_prob,
                    peak_rms,
                    noise_floor,
                    threshold,
                )
                return UtteranceCaptureResult(
                    None,
                    peak_vad=peak_prob,
                    peak_rms=peak_rms,
                    noise_floor=noise_floor,
                )
            continue

        chunks.append(frame)
        if is_speech:
            silence_elapsed = 0.0
        else:
            silence_elapsed += frame_duration
            if silence_elapsed >= silence_seconds:
                break

    noise_floor = float(np.median(noise_rms_samples)) if noise_rms_samples else 0.0

    if not chunks:
        logger.info(
            "No speech captured: frames=%d peak_vad=%.3f peak_rms=%.1f noise_floor=%.1f threshold=%.2f",
            frames_seen,
            peak_prob,
            peak_rms,
            noise_floor,
            threshold,
        )
        return UtteranceCaptureResult(
            None,
            peak_vad=peak_prob,
            peak_rms=peak_rms,
            noise_floor=noise_floor,
        )
    return UtteranceCaptureResult(
        b"".join(chunks),
        peak_vad=peak_prob,
        peak_rms=peak_rms,
        noise_floor=noise_floor,
    )


def listen_once(
    mic: MicStream | None,
    stt_cfg: dict[str, Any],
    *,
    on_phase: Callable[[str], None] | None = None,
) -> ListenOutcome:
    if mic is None:
        logger.warning("Mic stream not available for STT")
        return ListenOutcome()

    capture = listen_utterance(mic, stt_cfg, on_phase=on_phase)
    if capture.pcm is None:
        return ListenOutcome(
            None,
            peak_vad=capture.peak_vad,
            peak_rms=capture.peak_rms,
            noise_floor=capture.noise_floor,
        )

    if on_phase is not None:
        on_phase("Transcribing...")
    text = transcribe_pcm(
        capture.pcm,
        model_path=stt_cfg.get("model", "data/models/faster-whisper-tiny.en"),
        compute_type=str(stt_cfg.get("compute_type", "int8")),
        language=str(stt_cfg.get("language", "en")),
    )
    if text:
        logger.info("Transcribed speech (%d chars)", len(text))
    else:
        logger.debug("Transcription empty")
    return ListenOutcome(
        text or None,
        peak_vad=capture.peak_vad,
        peak_rms=capture.peak_rms,
        noise_floor=capture.noise_floor,
    )


def listen_from_config(
    mic: MicStream | None,
    stt_cfg: dict[str, Any],
    *,
    on_phase: Callable[[str], None] | None = None,
) -> ListenOutcome:
    try:
        return listen_once(mic, stt_cfg, on_phase=on_phase)
    except Exception:
        logger.warning("Speech capture or transcription failed", exc_info=True)
        return ListenOutcome()


def run_vad_probe(
    mic: MicStream,
    stt_cfg: dict[str, Any],
    *,
    duration_seconds: float = 10.0,
    print_interval_seconds: float = 0.25,
) -> None:
    """Print live RMS and VAD scores (for CLI tuning)."""
    vad_model = stt_cfg.get("vad_model", "data/models/silero_vad.onnx")
    threshold = float(stt_cfg.get("vad_threshold", 0.4))
    energy_fallback = bool(stt_cfg.get("energy_fallback", True))
    energy_ratio = float(stt_cfg.get("energy_ratio", 3.0))
    min_speech_rms = float(stt_cfg.get("min_speech_rms", 200.0))

    vad = SileroVADSession(vad_model)
    frame_duration = mic.frame_samples / SAMPLE_RATE
    end_time = time.monotonic() + duration_seconds
    next_print = time.monotonic()
    noise_rms_samples: list[float] = []
    noise_floor_deadline = time.monotonic() + NOISE_FLOOR_SECONDS
    interval_rms: list[float] = []
    interval_vad: list[float] = []
    speech_in_interval = False

    print(
        f"Probing mic for {duration_seconds:.0f}s "
        f"(vad_threshold={threshold}, min_speech_rms={min_speech_rms})"
    )

    for frame in mic.iter_frames(timeout=0.5):
        now = time.monotonic()
        if now > end_time:
            break

        rms = _frame_rms(frame)
        if now < noise_floor_deadline:
            noise_rms_samples.append(rms)
        noise_floor = float(np.median(noise_rms_samples)) if noise_rms_samples else 0.0

        prob = vad.speech_probability(frame)
        is_speech = _counts_as_speech(
            prob,
            rms,
            noise_floor=noise_floor,
            threshold=threshold,
            energy_fallback=energy_fallback,
            energy_ratio=energy_ratio,
            min_speech_rms=min_speech_rms,
        )
        interval_rms.append(rms)
        if prob >= 0:
            interval_vad.append(prob)
        speech_in_interval = speech_in_interval or is_speech

        if now >= next_print:
            avg_rms = float(np.mean(interval_rms)) if interval_rms else 0.0
            peak_vad = max(interval_vad) if interval_vad else VAD_UNAVAILABLE
            vad_display = "n/a" if peak_vad == VAD_UNAVAILABLE else f"{peak_vad:.3f}"
            print(
                f"rms={avg_rms:.0f} vad={vad_display} speech={'yes' if speech_in_interval else 'no'}"
            )
            next_print += print_interval_seconds
            interval_rms.clear()
            interval_vad.clear()
            speech_in_interval = False


def warmup_stt(stt_cfg: dict[str, Any]) -> None:
    if not stt_cfg.get("enabled", True):
        return
    started = time.monotonic()
    model_path = stt_cfg.get("model", "data/models/faster-whisper-tiny.en")
    compute_type = str(stt_cfg.get("compute_type", "int8"))
    vad_model = stt_cfg.get("vad_model", "data/models/silero_vad.onnx")
    try:
        resolved = _resolve_model_path(model_path)
        _load_whisper_model(resolved, compute_type)
        SileroVADSession(vad_model)
    except Exception:
        logger.warning("STT warmup failed; first listen may be slow", exc_info=True)
        return
    elapsed = time.monotonic() - started
    logger.info("STT warmup complete in %.1fs", elapsed)
