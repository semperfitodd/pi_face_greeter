from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pi_face_greeter import alsa_devices, stt
from pi_face_greeter.mic import MicStream


ARECORD_SAMPLE = """
**** List of CAPTURE Hardware Devices ****
card 2: Device [USB PnP Sound Device], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 3: Device_1 [USB PnP Audio Device], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
"""


def test_parse_usb_capture_device_picks_first_usb_card() -> None:
    assert alsa_devices.parse_usb_capture_device(ARECORD_SAMPLE) == "plughw:2,0"


def test_listen_utterance_returns_pcm_when_vad_detects_speech() -> None:
    mic = MicStream(frame_samples=512)
    frames = [b"\x01\x00" * 512, b"\x02\x00" * 512, b"\x00\x00" * 512]

    class FakeVAD:
        def __init__(self, *_args, **_kwargs) -> None:
            self._calls = 0

        def speech_probability(self, _frame: bytes) -> float:
            self._calls += 1
            return 0.9 if self._calls <= 2 else 0.1

    with patch("pi_face_greeter.stt.SileroVADSession", FakeVAD):
        with patch.object(mic, "iter_frames", return_value=iter(frames)):
            pcm = stt.listen_utterance(mic, {"enabled": True, "silence_seconds": 0.5})

    assert pcm is not None
    assert len(pcm) > 0


def test_listen_once_returns_none_when_no_speech() -> None:
    mic = MagicMock(spec=MicStream)
    with patch("pi_face_greeter.stt.listen_utterance", return_value=None):
        assert stt.listen_once(mic, {"enabled": True}) is None
