from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from pi_face_greeter.vad import SileroVADSession, _CONTEXT_SAMPLES


def _make_session() -> SileroVADSession:
    session = SileroVADSession.__new__(SileroVADSession)
    session._sample_rate = 16000
    session._state = np.zeros((2, 1, 128), dtype=np.float32)
    session._context = np.zeros(_CONTEXT_SAMPLES, dtype=np.float32)
    session._input_name = "input"
    session._session = MagicMock()
    session._session.run.return_value = [np.array([[0.9]], dtype=np.float32), session._state]
    return session


def test_speech_probability_uses_576_sample_window() -> None:
    vad = _make_session()
    frame = (np.ones(512, dtype=np.int16) * 1000).tobytes()
    prob = vad.speech_probability(frame)
    assert prob == pytest.approx(0.9)
    call_inputs = vad._session.run.call_args[0][1]
    assert call_inputs["input"].shape == (1, 512 + _CONTEXT_SAMPLES)
    assert call_inputs["sr"].dtype == np.int64
    assert call_inputs["sr"].shape == ()


def test_context_carries_across_frames() -> None:
    vad = _make_session()
    frame_a = (np.arange(512, dtype=np.int16) + 1).tobytes()
    vad.speech_probability(frame_a)
    frame_b = (np.zeros(512, dtype=np.int16)).tobytes()
    vad.speech_probability(frame_b)
    second_call = vad._session.run.call_args_list[1][0][1]
    window = second_call["input"].reshape(-1)
    expected_tail = (np.arange(512, dtype=np.int16) + 1).astype(np.float32)[-64:] / 32768.0
    np.testing.assert_allclose(window[:64], expected_tail, rtol=1e-5)


def test_reset_clears_context() -> None:
    vad = _make_session()
    frame = (np.ones(512, dtype=np.int16)).tobytes()
    vad.speech_probability(frame)
    vad.reset()
    assert np.allclose(vad._context, 0.0)
