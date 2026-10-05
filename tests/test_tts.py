from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pi_face_greeter.tts import (
    normalize_alsa_device,
    parse_usb_playback_device,
    resolve_playback_device,
    speak,
    speak_from_config,
)

PI5_APLAY_LISTING = """\
**** List of PLAYBACK Hardware Devices ****
card 0: vc4hdmi0 [vc4-hdmi-0], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]
  Subdevices: 1/1
card 1: vc4hdmi1 [vc4-hdmi-1], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]
  Subdevices: 1/1
card 2: Device [USB PnP Audio Device], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
"""

USB_CARD1_APLAY_LISTING = """\
card 0: vc4hdmi0 [vc4-hdmi-0], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]
card 1: Device [USB Audio Device], device 0: USB Audio [USB Audio]
"""

NO_USB_APLAY_LISTING = """\
card 0: vc4hdmi0 [vc4-hdmi-0], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]
"""


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


def test_normalize_alsa_device_rejects_injection() -> None:
    with pytest.raises(ValueError, match="Invalid ALSA device"):
        normalize_alsa_device("plughw:1,0;rm -rf /")


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
    with (
        patch("pi_face_greeter.tts.speak") as mock_speak,
        patch("pi_face_greeter.tts.resolve_playback_device", return_value="plughw:2,0"),
    ):
        speak_from_config(
            "Hello",
            {"enabled": True, "engine": "espeak", "voice": "en", "alsa_device": None},
        )
    mock_speak.assert_called_once_with(text="Hello", voice="en", alsa_device="plughw:2,0")


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
                },
            },
        )

    mock_piper.assert_called_once_with(
        text="Hello there",
        model_path="data/voices/en_US-amy-medium.onnx",
        alsa_device="plughw:1,0",
        length_scale=1.1,
    )
    mock_speak.assert_not_called()


def test_speak_from_config_falls_back_to_espeak() -> None:
    with (
        patch("pi_face_greeter.tts.speak_piper", side_effect=RuntimeError("missing model")),
        patch("pi_face_greeter.tts.speak") as mock_speak,
        patch("pi_face_greeter.tts.resolve_playback_device", return_value=None),
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


def test_parse_usb_playback_device_pi5_layout() -> None:
    assert parse_usb_playback_device(PI5_APLAY_LISTING) == "plughw:2,0"


def test_parse_usb_playback_device_usb_on_card1() -> None:
    assert parse_usb_playback_device(USB_CARD1_APLAY_LISTING) == "plughw:1,0"


def test_parse_usb_playback_device_no_usb() -> None:
    assert parse_usb_playback_device(NO_USB_APLAY_LISTING) is None


def test_resolve_playback_device_uses_explicit_override() -> None:
    with patch("pi_face_greeter.tts.detect_usb_alsa_device") as mock_detect:
        assert resolve_playback_device("plughw:9,0") == "plughw:9,0"
    mock_detect.assert_not_called()


def test_resolve_playback_device_detects_usb_when_unconfigured() -> None:
    with patch(
        "pi_face_greeter.tts.detect_usb_alsa_device",
        return_value="plughw:2,0",
    ):
        assert resolve_playback_device(None) == "plughw:2,0"


def test_speak_piper_raises_when_model_missing(tmp_path: Path) -> None:
    from pi_face_greeter.tts import speak_piper

    missing = tmp_path / "missing.onnx"
    fake_piper = MagicMock()
    with (
        patch("pi_face_greeter.tts.shutil.which", return_value="/usr/bin/aplay"),
        patch.dict("sys.modules", {"piper": fake_piper}),
        pytest.raises(FileNotFoundError, match="Piper model not found"),
    ):
        speak_piper("Hello", missing)


def test_speak_piper_synthesizes_and_plays(tmp_path: Path, monkeypatch) -> None:
    from pi_face_greeter import tts as tts_module
    from pi_face_greeter.tts import speak_piper

    model_path = tmp_path / "voice.onnx"
    model_path.write_bytes(b"onnx")

    mock_voice = MagicMock()

    def fake_synthesize_wav(_text, wav_file, syn_config=None) -> None:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x00")

    mock_voice.synthesize_wav.side_effect = fake_synthesize_wav

    mock_piper = MagicMock()
    mock_piper.PiperVoice.load.return_value = mock_voice

    def fake_synthesis_config(**kwargs):
        return kwargs

    mock_piper.SynthesisConfig = fake_synthesis_config
    monkeypatch.setitem(sys.modules, "piper", mock_piper)
    tts_module._voice_cache.clear()

    with (
        patch("pi_face_greeter.tts.shutil.which", return_value="/usr/bin/aplay"),
        patch("pi_face_greeter.tts.subprocess.run") as mock_run,
    ):
        speak_piper("Hello there", model_path, alsa_device="plughw:1,0", length_scale=1.1)

    mock_piper.PiperVoice.load.assert_called_once_with(str(model_path))
    mock_voice.synthesize_wav.assert_called_once()
    synth_args, synth_kwargs = mock_voice.synthesize_wav.call_args
    assert synth_args[0] == "Hello there"
    assert synth_kwargs["syn_config"] == {"length_scale": 1.1}

    mock_run.assert_called_once()
    aplay_args, _kwargs = mock_run.call_args
    assert aplay_args[0][0:3] == ["aplay", "-q", "-D"]
    assert aplay_args[0][3] == "plughw:1,0"
