from __future__ import annotations

from pathlib import Path

import numpy as np

from pi_face_greeter.camera import CameraBackend


class StubCamera(CameraBackend):
    def __init__(self, frame: np.ndarray) -> None:
        self._frame = frame

    def capture_frame(self) -> np.ndarray:
        return self._frame

    def close(self) -> None:
        pass


def test_save_frame_writes_jpeg(tmp_path: Path) -> None:
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    frame[:, :, 0] = 255

    camera = StubCamera(frame)
    output = tmp_path / "test.jpg"
    saved = camera.save_frame(frame, output)

    assert saved == output
    assert output.exists()
    assert output.stat().st_size > 0
