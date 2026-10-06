from __future__ import annotations

from unittest.mock import MagicMock

from pi_face_greeter.mic import MicStream
from pi_face_greeter.wake_word import WakeWordListener


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
