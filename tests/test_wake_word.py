from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from pi_face_greeter.mic import MicStream
from pi_face_greeter.wake_word import WakeWordListener, build_wake_hint


def test_wake_word_disabled_when_model_missing(tmp_path) -> None:
    mic = MagicMock(spec=MicStream)
    triggered = False

    def on_wake() -> None:
        nonlocal triggered
        triggered = True

    listener = WakeWordListener(
        {"enabled": True, "model": str(tmp_path / "missing.onnx"), "threshold": 0.5},
        mic,
        on_wake=on_wake,
    )
    listener.start()
    assert listener.enabled is False
    assert triggered is False


def test_build_wake_hint_from_phrase() -> None:
    hint = build_wake_hint(
        {"enabled": True, "phrase": "Hey Jarvis"},
        listener_enabled=True,
    )
    assert hint == 'Say "Hey Jarvis" to talk'


def test_build_wake_hint_hidden_when_listener_disabled() -> None:
    assert build_wake_hint({"enabled": True, "phrase": "Hey Jarvis"}, listener_enabled=False) is None
    assert build_wake_hint({"enabled": False, "phrase": "Hey Jarvis"}, listener_enabled=True) is None


def test_wake_word_buffers_to_1280_samples_before_predict() -> None:
    mic = MagicMock(spec=MicStream)
    listener = WakeWordListener.__new__(WakeWordListener)
    listener._cfg = {"enabled": True}
    listener._mic = mic
    listener._on_wake = MagicMock()
    listener._model = MagicMock()
    listener._model.predict.return_value = {"hey_jarvis": 0.1}
    listener._enabled = True
    listener._active = True
    listener._lock = __import__("threading").Lock()
    listener._threshold = 0.5
    listener._sample_buffer = np.array([], dtype=np.int16)
    listener._last_debug_log = 0.0

    frame = (np.ones(512, dtype=np.int16)).tobytes()
    listener._on_audio(frame)
    listener._model.predict.assert_not_called()
    listener._on_audio(frame)
    listener._model.predict.assert_not_called()
    listener._on_audio(frame)
    listener._model.predict.assert_called_once()
    chunk = listener._model.predict.call_args[0][0]
    assert chunk.size == 1280
