from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from pi_face_greeter.config_loader import PROJECT_ROOT

logger = logging.getLogger("pi_face_greeter.vad")

_session_cache: dict[str, Any] = {}

VAD_UNAVAILABLE = -1.0


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


def _log_session_signature(session: Any) -> str:
    parts: list[str] = []
    for inp in session.get_inputs():
        shape = getattr(inp, "shape", None)
        parts.append(f"{inp.name}{shape}")
    for out in session.get_outputs():
        shape = getattr(out, "shape", None)
        parts.append(f"->{out.name}{shape}")
    signature = ", ".join(parts)
    logger.info("Silero VAD ONNX signature: %s", signature)
    return signature


def _zeros_for_input(inp: Any) -> np.ndarray:
    shape = inp.shape
    resolved: list[int] = []
    for dim in shape:
        if isinstance(dim, int) and dim > 0:
            resolved.append(dim)
        else:
            resolved.append(1)
    return np.zeros(tuple(resolved), dtype=np.float32)


_CONTEXT_SAMPLES = 64


class SileroVADSession:
    """Streaming Silero VAD with internal RNN state."""

    def __init__(self, model_path: str | Path, *, sample_rate: int = 16000) -> None:
        self._model_path = _resolve_model_path(model_path)
        self._session = _load_ort_session(self._model_path)
        self._sample_rate = sample_rate
        self._context = np.zeros(_CONTEXT_SAMPLES, dtype=np.float32)
        self._inference_error_logged = False

        inputs = {item.name: item for item in self._session.get_inputs()}
        self._signature = _log_session_signature(self._session)

        if "input" in inputs:
            self._input_name = "input"
        else:
            self._input_name = self._session.get_inputs()[0].name

        self._sr_name = "sr" if "sr" in inputs else next(
            (name for name in inputs if name.lower() == "sr"),
            "sr",
        )

        self._use_state = "state" in inputs
        self._use_hc = "h" in inputs and "c" in inputs
        self._state: np.ndarray | None = None
        self._h: np.ndarray | None = None
        self._c: np.ndarray | None = None

        if self._use_state:
            self._state = _zeros_for_input(inputs["state"])
        if self._use_hc:
            self._h = _zeros_for_input(inputs["h"])
            self._c = _zeros_for_input(inputs["c"])

        if not self._use_state and not self._use_hc:
            logger.warning(
                "Silero VAD model has no state/h/c inputs; assuming stateless layout"
            )

    def reset(self) -> None:
        if self._state is not None:
            self._state = np.zeros_like(self._state)
        if self._h is not None:
            self._h = np.zeros_like(self._h)
        if self._c is not None:
            self._c = np.zeros_like(self._c)
        self._context = np.zeros(_CONTEXT_SAMPLES, dtype=np.float32)

    def speech_probability(self, frame_pcm: bytes) -> float:
        samples = np.frombuffer(frame_pcm, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.size == 0:
            return 0.0

        window = np.concatenate([self._context, samples])
        self._context = samples[-_CONTEXT_SAMPLES:].copy()

        feed: dict[str, Any] = {
            self._input_name: window.reshape(1, -1),
            self._sr_name: np.int64(self._sample_rate),
        }
        if self._use_state and self._state is not None:
            feed["state"] = self._state
        if self._use_hc and self._h is not None and self._c is not None:
            feed["h"] = self._h
            feed["c"] = self._c

        try:
            outputs = self._session.run(None, feed)
        except Exception as exc:
            if not self._inference_error_logged:
                logger.error(
                    "Silero VAD inference failed (%s); signature=%s",
                    exc,
                    self._signature,
                    exc_info=True,
                )
                self._inference_error_logged = True
            return VAD_UNAVAILABLE

        if self._use_state and len(outputs) >= 2:
            self._state = outputs[1]
        elif self._use_hc and len(outputs) >= 3:
            self._h = outputs[1]
            self._c = outputs[2]

        prob = outputs[0]
        return float(np.asarray(prob).reshape(-1)[0])
