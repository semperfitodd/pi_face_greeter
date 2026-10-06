from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from pi_face_greeter import stt


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
    assert stt.parse_usb_capture_device(ARECORD_SAMPLE) == "plughw:2,0"


def test_rms_silence_is_low() -> None:
    silent = np.zeros(320, dtype=np.int16).tobytes()
    assert stt._rms(silent) == 0.0


def test_rms_speech_is_higher() -> None:
    loud = (np.sin(np.linspace(0, 8 * np.pi, 320)) * 20000).astype(np.int16).tobytes()
    assert stt._rms(loud) > 1000.0


def test_record_until_silence_stops_after_trailing_silence() -> None:
    chunk_samples = stt.CHUNK_FRAMES
    loud = (np.sin(np.linspace(0, 8 * np.pi, chunk_samples)) * 20000).astype(np.int16)
    silent = np.zeros(chunk_samples, dtype=np.int16)
    chunks = [loud.tobytes()] * 3 + [silent.tobytes()] * 6

    mock_proc = MagicMock()
    mock_proc.stdout.read.side_effect = chunks + [b""]

    with (
        patch("pi_face_greeter.stt.shutil.which", return_value="/usr/bin/arecord"),
        patch("pi_face_greeter.stt.subprocess.Popen", return_value=mock_proc),
    ):
        pcm = stt.record_until_silence(
            alsa_device="plughw:2,0",
            max_record_seconds=8.0,
            silence_seconds=1.0,
            start_timeout_seconds=5.0,
            speech_rms_threshold=400.0,
        )

    assert pcm is not None
    assert len(pcm) > 0


def test_listen_once_returns_none_when_no_speech() -> None:
    with patch("pi_face_greeter.stt.record_until_silence", return_value=None):
        assert stt.listen_once({"enabled": True}) is None
