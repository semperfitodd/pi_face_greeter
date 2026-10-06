from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from pi_face_greeter.config_loader import PROJECT_ROOT
from pi_face_greeter.events import log_event
from pi_face_greeter.mic import MicStream

logger = logging.getLogger("pi_face_greeter.wake_word")

WakeCallback = Callable[[], None]

_BUILTIN_MODELS = frozenset({"hey_jarvis", "alexa", "hey_mycroft"})
_OPENWAKEWORD_CHUNK_SAMPLES = 1280
_DEBUG_SCORE_INTERVAL_SECONDS = 5.0


def build_wake_hint(wake_cfg: dict[str, Any], *, listener_enabled: bool) -> str | None:
    if not wake_cfg.get("enabled", False) or not listener_enabled:
        return None
    phrase = str(wake_cfg.get("phrase", "")).strip()
    if not phrase:
        return None
    return f'Say "{phrase}" to talk'


def _resolve_model(model: str) -> Path | str | None:
    token = model.strip()
    if not token:
        return None
    if token in _BUILTIN_MODELS:
        return token
    path = Path(token)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if path.is_file():
        return path
    return None


class WakeWordListener:
    def __init__(
        self,
        wake_cfg: dict[str, Any],
        mic: MicStream,
        on_wake: WakeCallback,
    ) -> None:
        self._cfg = wake_cfg
        self._mic = mic
        self._on_wake = on_wake
        self._model: Any = None
        self._enabled = False
        self._active = False
        self._lock = threading.Lock()
        self._sample_buffer = np.array([], dtype=np.int16)
        self._last_debug_log = 0.0

    @property
    def enabled(self) -> bool:
        return self._enabled

    def start(self) -> None:
        if not self._cfg.get("enabled", False):
            logger.info("Wake word disabled in config")
            return

        model_ref = _resolve_model(str(self._cfg.get("model", "")))
        if model_ref is None:
            logger.warning(
                "Wake word model not found (%s); wake word disabled. "
                "Run ./scripts/install.sh or set wake_word.model: hey_jarvis.",
                self._cfg.get("model"),
            )
            return

        try:
            from openwakeword.model import Model
        except ImportError:
            logger.warning(
                "openwakeword not installed; wake word disabled. "
                'Install with: pip install -e ".[stt]"'
            )
            return

        threshold = float(self._cfg.get("threshold", 0.5))
        if isinstance(model_ref, Path):
            self._model = Model(
                wakeword_models=[str(model_ref)],
                inference_framework="onnx",
            )
        else:
            self._model = Model(wakeword_models=[model_ref], inference_framework="onnx")

        self._threshold = threshold
        self._enabled = True
        self._active = True
        self._mic.subscribe(self._on_audio)
        logger.info("Wake word listener started (model: %s)", model_ref)

    def stop(self) -> None:
        self._active = False
        if self._enabled:
            self._mic.unsubscribe(self._on_audio)
        self._enabled = False
        self._sample_buffer = np.array([], dtype=np.int16)

    def pause(self) -> None:
        with self._lock:
            self._active = False

    def resume(self) -> None:
        with self._lock:
            if self._enabled:
                self._active = True

    def _on_audio(self, frame: bytes) -> None:
        with self._lock:
            if not self._active or self._model is None:
                return

        samples = np.frombuffer(frame, dtype=np.int16)
        if samples.size == 0:
            return

        self._sample_buffer = np.concatenate([self._sample_buffer, samples])
        while self._sample_buffer.size >= _OPENWAKEWORD_CHUNK_SAMPLES:
            chunk = self._sample_buffer[:_OPENWAKEWORD_CHUNK_SAMPLES]
            self._sample_buffer = self._sample_buffer[_OPENWAKEWORD_CHUNK_SAMPLES:]
            self._predict_chunk(chunk)

    def _predict_chunk(self, chunk: np.ndarray) -> None:
        try:
            prediction = self._model.predict(chunk)
        except Exception:
            logger.debug("Wake word predict failed", exc_info=True)
            return

        if not isinstance(prediction, dict) or not prediction:
            return

        top_name = max(prediction, key=lambda key: float(prediction[key]))
        top_score = float(prediction[top_name])
        now = time.monotonic()

        if now - self._last_debug_log >= _DEBUG_SCORE_INTERVAL_SECONDS:
            logger.debug(
                "Wake word scores (top %s=%.3f, threshold=%.2f)",
                top_name,
                top_score,
                self._threshold,
            )
            self._last_debug_log = now

        half_threshold = self._threshold * 0.5
        for name, score in prediction.items():
            score_f = float(score)
            if score_f >= self._threshold:
                logger.info("Wake word detected (%s score %.2f)", name, score_f)
                log_event(f"wake detected {name} score={score_f:.2f}")
                self._on_wake()
                return
            if score_f >= half_threshold:
                logger.info("Wake word near miss (%s score %.2f)", name, score_f)
