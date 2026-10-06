from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from pi_face_greeter import alsa_devices, stt
from pi_face_greeter.mic import MicStream
from pi_face_greeter.vad import VAD_UNAVAILABLE

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
            result = stt.listen_utterance(mic, {"enabled": True, "silence_seconds": 0.5})

    assert result.pcm is not None
    assert len(result.pcm) > 0


def test_listen_utterance_energy_fallback_when_vad_unavailable() -> None:
    mic = MicStream(frame_samples=512)
    loud = (np.ones(512, dtype=np.int16) * 8000).tobytes()
    quiet = (np.zeros(512, dtype=np.int16)).tobytes()
    frames = [quiet] * 3 + [loud, loud, quiet]

    class BrokenVAD:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def speech_probability(self, _frame: bytes) -> float:
            return VAD_UNAVAILABLE

    times = iter([0.0, 0.0, 0.0] + [i * 0.05 for i in range(1, 80)])

    with patch("pi_face_greeter.stt.SileroVADSession", BrokenVAD):
        with patch.object(mic, "iter_frames", return_value=iter(frames)):
            with patch("pi_face_greeter.stt.time.monotonic", side_effect=lambda: next(times)):
                result = stt.listen_utterance(
                    mic,
                    {
                        "enabled": True,
                        "silence_seconds": 0.5,
                        "start_timeout_seconds": 5.0,
                        "min_speech_rms": 200,
                        "energy_ratio": 2.0,
                    },
                )

    assert result.pcm is not None


def test_listen_utterance_includes_preroll_frames() -> None:
    mic = MicStream(frame_samples=512)
    quiet = (np.zeros(512, dtype=np.int16)).tobytes()
    loud = (np.ones(512, dtype=np.int16) * 5000).tobytes()
    frames = [quiet, quiet, loud, loud, quiet]

    class FakeVAD:
        def __init__(self, *_args, **_kwargs) -> None:
            self._n = 0

        def speech_probability(self, _frame: bytes) -> float:
            self._n += 1
            return 0.9 if self._n >= 3 else 0.0

    with patch("pi_face_greeter.stt.SileroVADSession", FakeVAD):
        with patch.object(mic, "iter_frames", return_value=iter(frames)):
            with patch("pi_face_greeter.stt.time.monotonic") as mock_mono:
                mock_mono.side_effect = [0.0] * 20
                result = stt.listen_utterance(
                    mic,
                    {"enabled": True, "silence_seconds": 0.5, "pre_roll_seconds": 0.4},
                )

    assert result.pcm is not None
    assert len(result.pcm) >= 512 * 2 * 2


def test_listen_once_returns_none_when_no_speech() -> None:
    mic = MagicMock(spec=MicStream)
    empty = stt.UtteranceCaptureResult(None, peak_vad=0.01, peak_rms=50.0)
    with patch("pi_face_greeter.stt.listen_utterance", return_value=empty):
        outcome = stt.listen_once(mic, {"enabled": True})
    assert outcome.text is None
    assert outcome.peak_rms == pytest.approx(50.0)


def test_listen_utterance_logs_diagnostics_on_timeout(caplog) -> None:
    import logging

    mic = MicStream(frame_samples=512)
    caplog.set_level(logging.INFO, logger="pi_face_greeter.stt")

    class QuietVAD:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def speech_probability(self, _frame: bytes) -> float:
            return 0.01

    times = iter([0.0, 0.0, 0.0, 0.0, 2.0])

    with patch("pi_face_greeter.stt.SileroVADSession", QuietVAD):
        with patch.object(mic, "iter_frames", return_value=iter([b"\x01\x00" * 512])):
            with patch("pi_face_greeter.stt.time.monotonic", side_effect=lambda: next(times, 2.0)):
                result = stt.listen_utterance(
                    mic,
                    {"enabled": True, "start_timeout_seconds": 1.0, "vad_threshold": 0.5},
                )

    assert result.pcm is None
    assert result.peak_vad == pytest.approx(0.01)
    assert any("peak_vad" in record.message for record in caplog.records)


def test_listen_utterance_calls_on_phase() -> None:
    mic = MicStream(frame_samples=512)
    frames = [b"\x01\x00" * 512, b"\x02\x00" * 512, b"\x00\x00" * 512]
    phases: list[str] = []

    class FakeVAD:
        def __init__(self, *_args, **_kwargs) -> None:
            self._calls = 0

        def speech_probability(self, _frame: bytes) -> float:
            self._calls += 1
            return 0.9 if self._calls <= 2 else 0.1

    with patch("pi_face_greeter.stt.SileroVADSession", FakeVAD):
        with patch.object(mic, "iter_frames", return_value=iter(frames)):
            stt.listen_utterance(
                mic,
                {"enabled": True, "silence_seconds": 0.5},
                on_phase=phases.append,
            )

    assert "Hearing you..." in phases


def test_listen_once_calls_transcribing_phase() -> None:
    mic = MagicMock(spec=MicStream)
    phases: list[str] = []
    capture = stt.UtteranceCaptureResult(b"\x00" * 1024)
    with (
        patch("pi_face_greeter.stt.listen_utterance", return_value=capture),
        patch("pi_face_greeter.stt.transcribe_pcm", return_value="hello"),
    ):
        outcome = stt.listen_once(mic, {"enabled": True}, on_phase=phases.append)
    assert outcome.text == "hello"
    assert "Transcribing..." in phases
