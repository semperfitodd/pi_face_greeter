from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pi_face_greeter.tts import speak, speak_from_config


def test_speak_invokes_espeak() -> None:
    with (
        patch("pi_face_greeter.tts.shutil.which", return_value="/usr/bin/espeak-ng"),
        patch("pi_face_greeter.tts.subprocess.run") as mock_run,
    ):
        speak("Hello", voice="en", alsa_device="plughw:1,0")

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] == ["espeak-ng", "-v", "en", "Hello"]
    assert kwargs["check"] is True
    assert kwargs["env"]["AUDIODEV"] == "plughw:1,0"


def test_speak_skips_empty_text() -> None:
    with patch("pi_face_greeter.tts.subprocess.run") as mock_run:
        speak("   ")
    mock_run.assert_not_called()


def test_speak_raises_when_espeak_missing() -> None:
    with patch("pi_face_greeter.tts.shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="espeak-ng not found"):
            speak("Hello")


def test_speak_from_config_respects_disabled() -> None:
    with (
        patch("pi_face_greeter.tts.speak") as mock_speak,
        patch("pi_face_greeter.tts.speak_piper") as mock_piper,
    ):
        speak_from_config("Hello", {"enabled": False})
    mock_speak.assert_not_called()
    mock_piper.assert_not_called()


def test_speak_from_config_delegates_to_speak() -> None:
    with patch("pi_face_greeter.tts.speak") as mock_speak:
        speak_from_config(
            "Hello",
            {"enabled": True, "engine": "espeak", "voice": "en", "alsa_device": None},
        )
    mock_speak.assert_called_once_with(text="Hello", voice="en", alsa_device=None)


def test_speak_from_config_uses_piper() -> None:
    with (
        patch("pi_face_greeter.tts.speak_piper") as mock_piper,
        patch("pi_face_greeter.tts.speak") as mock_speak,
    ):
        speak_from_config(
            "Hello there",
            {
                "enabled": True,
                "engine": "piper",
                "alsa_device": "plughw:1,0",
                "piper": {
                    "model": "data/voices/en_US-amy-medium.onnx",
                    "length_scale": 1.1,
                    "sentence_silence": 0.2,
                },
            },
        )

    mock_piper.assert_called_once_with(
        text="Hello there",
        model_path="data/voices/en_US-amy-medium.onnx",
        alsa_device="plughw:1,0",
        length_scale=1.1,
        sentence_silence=0.2,
    )
    mock_speak.assert_not_called()


def test_speak_from_config_falls_back_to_espeak() -> None:
    with (
        patch("pi_face_greeter.tts.speak_piper", side_effect=RuntimeError("missing model")),
        patch("pi_face_greeter.tts.speak") as mock_speak,
    ):
        speak_from_config(
            "Hello",
            {
                "enabled": True,
                "engine": "piper",
                "voice": "en",
                "alsa_device": None,
                "piper": {"model": "missing.onnx"},
            },
        )

    mock_speak.assert_called_once_with(text="Hello", voice="en", alsa_device=None)


def test_speak_piper_raises_when_model_missing(tmp_path: Path) -> None:
    from pi_face_greeter.tts import speak_piper

    missing = tmp_path / "missing.onnx"
    fake_piper = MagicMock()
    with (
        patch("pi_face_greeter.tts.shutil.which", return_value="/usr/bin/aplay"),
        patch.dict("sys.modules", {"piper": fake_piper, "piper.config": MagicMock()}),
        pytest.raises(FileNotFoundError, match="Piper model not found"),
    ):
        speak_piper("Hello", missing)
