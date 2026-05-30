from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from pi_face_greeter.app.detector import detect_faces


def test_detect_faces_without_opencv(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "cv2":
            raise ImportError("opencv not installed")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    assert detect_faces(frame) == []


@pytest.mark.skipif(
    importlib.util.find_spec("cv2") is None,
    reason="OpenCV required",
)
def test_detect_faces_returns_list() -> None:
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    boxes = detect_faces(frame)
    assert isinstance(boxes, list)
