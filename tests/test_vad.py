from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from pi_face_greeter.vad import SileroVADSession, VAD_UNAVAILABLE, _CONTEXT_SAMPLES


def _make_session(*, use_hc: bool = False) -> SileroVADSession:
    session = SileroVADSession.__new__(SileroVADSession)
    session._sample_rate = 16000
    session._context = np.zeros(_CONTEXT_SAMPLES, dtype=np.float32)
    session._input_name = "input"
    session._sr_name = "sr"
    session._signature = "test"
    session._inference_error_logged = False
    session._session = MagicMock()

    if use_hc:
        session._use_state = False
        session._use_hc = True
        session._state = None
        session._h = np.zeros((2, 1, 64), dtype=np.float32)
        session._c = np.zeros((2, 1, 64), dtype=np.float32)
        session._session.run.return_value = [
            np.array([[0.9]], dtype=np.float32),
            session._h,
            session._c,
        ]
    else:
        session._use_state = True
        session._use_hc = False
        session._state = np.zeros((2, 1, 128), dtype=np.float32)
        session._h = None
        session._c = None
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
    assert "state" in call_inputs


def test_v4_layout_uses_h_and_c() -> None:
    vad = _make_session(use_hc=True)
    frame = (np.ones(512, dtype=np.int16) * 500).tobytes()
    prob = vad.speech_probability(frame)
    assert prob == pytest.approx(0.9)
    call_inputs = vad._session.run.call_args[0][1]
    assert "h" in call_inputs
    assert "c" in call_inputs
    assert "state" not in call_inputs


def test_inference_error_returns_unavailable() -> None:
    vad = _make_session()
    vad._session.run.side_effect = RuntimeError("bad inputs")
    frame = (np.zeros(512, dtype=np.int16)).tobytes()
    assert vad.speech_probability(frame) == VAD_UNAVAILABLE
    assert vad.speech_probability(frame) == VAD_UNAVAILABLE


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
