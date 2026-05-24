from __future__ import annotations

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
    with patch("pi_face_greeter.tts.speak") as mock_speak:
        speak_from_config("Hello", {"enabled": False})
    mock_speak.assert_not_called()


def test_speak_from_config_unsupported_engine() -> None:
    with pytest.raises(ValueError, match="Unsupported TTS engine"):
        speak_from_config("Hello", {"enabled": True, "engine": "piper"})


def test_speak_from_config_delegates_to_speak() -> None:
    with patch("pi_face_greeter.tts.speak") as mock_speak:
        speak_from_config(
            "Hello",
            {"enabled": True, "engine": "espeak", "voice": "en", "alsa_device": None},
        )
    mock_speak.assert_called_once_with(text="Hello", voice="en", alsa_device=None)
