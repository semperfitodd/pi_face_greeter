from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from pi_face_greeter.config_loader import PROJECT_ROOT

logger = logging.getLogger("pi_face_greeter.vad")

_session_cache: dict[str, Any] = {}


def _resolve_model_path(model_path: str | Path) -> Path:
    path = Path(model_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _load_ort_session(model_path: Path) -> Any:
    key = str(model_path)
    cached = _session_cache.get(key)
    if cached is not None:
        return cached

    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError(
            'onnxruntime not installed. Install with: pip install -e ".[stt]"'
        ) from exc

    if not model_path.is_file():
        raise FileNotFoundError(f"VAD model not found: {model_path}")

    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    _session_cache[key] = session
    logger.info("Loaded Silero VAD model: %s", model_path)
    return session


class SileroVADSession:
    """Streaming Silero VAD with internal RNN state."""

    def __init__(self, model_path: str | Path, *, sample_rate: int = 16000) -> None:
        self._model_path = _resolve_model_path(model_path)
        self._session = _load_ort_session(self._model_path)
        self._sample_rate = sample_rate
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._input_name = self._session.get_inputs()[0].name

    def reset(self) -> None:
        self._state = np.zeros((2, 1, 128), dtype=np.float32)

    def speech_probability(self, frame_pcm: bytes) -> float:
        samples = np.frombuffer(frame_pcm, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.size == 0:
            return 0.0

        inputs: dict[str, Any] = {
            self._input_name: samples.reshape(1, -1),
            "state": self._state,
            "sr": np.array([self._sample_rate], dtype=np.int64),
        }
        outputs = self._session.run(None, inputs)
        if len(outputs) >= 2:
            self._state = outputs[1]
        prob = outputs[0]
        return float(np.asarray(prob).reshape(-1)[0])
