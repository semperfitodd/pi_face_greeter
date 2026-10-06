from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pi_face_greeter.config_loader import PROJECT_ROOT
from pi_face_greeter.mic import MicStream

logger = logging.getLogger("pi_face_greeter.wake_word")

WakeCallback = Callable[[], None]

_BUILTIN_MODELS = frozenset({"hey_jarvis", "alexa", "hey_mycroft"})


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
                "Train hey_freyja.onnx or set wake_word.model: hey_jarvis to test.",
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
        import numpy as np

        samples = np.frombuffer(frame, dtype=np.int16)
        if samples.size == 0:
            return
        try:
            prediction = self._model.predict(samples)
        except Exception:
            logger.debug("Wake word predict failed", exc_info=True)
            return

        if not isinstance(prediction, dict):
            return
        for _name, score in prediction.items():
            if float(score) >= self._threshold:
                logger.info("Wake word detected (score %.2f)", float(score))
                self._on_wake()
                return
