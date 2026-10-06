from __future__ import annotations

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
