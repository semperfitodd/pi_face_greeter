from __future__ import annotations

import time

import numpy as np

from pi_face_greeter.mic import MicStream


def test_mic_pause_drops_frames() -> None:
    mic = MicStream(frame_samples=512)
    received: list[bytes] = []

    def capture(frame: bytes) -> None:
        received.append(frame)

    mic.subscribe(capture)
    mic.pause()
    mic._emit(b"\x00" * mic.frame_bytes)
    assert received == []
    mic.resume()
    mic._emit(b"\x01" * mic.frame_bytes)
    assert len(received) == 1


def test_mic_level_updates_even_when_paused() -> None:
    mic = MicStream(frame_samples=512)
    loud = (np.ones(512, dtype=np.int16) * 5000).tobytes()
    mic.pause()
    mic._update_level(loud)
    assert mic.level > 0.1


def test_mic_is_alive_requires_recent_frame() -> None:
    mic = MicStream(frame_samples=512)
    mic._running = True
    mic._update_level(b"\x01\x00" * 512)
    assert mic.is_alive is True
    with mic._metrics_lock:
        mic._last_frame_at = time.monotonic() - 5.0
    assert mic.is_alive is False
