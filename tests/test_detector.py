from __future__ import annotations

import importlib.util

import numpy as np
import pytest

from pi_face_greeter.app import detector as detector_module
from pi_face_greeter.app.detector import detect_faces, get_cascade_classifier


def test_detect_faces_without_opencv(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "cv2":
            raise ImportError("opencv not installed")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    detector_module._cascade_classifier = None
    detector_module._cascade_unavailable_logged = False
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    assert detect_faces(frame) == []


def test_detect_faces_without_cascade(monkeypatch) -> None:
    class FakeCv2Data:
        haarcascades = "/nonexistent/path/"

    class FakeCv2:
        data = FakeCv2Data()

        @staticmethod
        def cvtColor(frame, _code):
            return frame[:, :, 0]

        class CascadeClassifier:
            def __init__(self, _path: str) -> None:
                pass

            def empty(self) -> bool:
                return True

    monkeypatch.setitem(__import__("sys").modules, "cv2", FakeCv2())
    monkeypatch.setattr(detector_module, "_find_cascade_path", lambda: None)
    detector_module._cascade_classifier = None
    detector_module._cascade_unavailable_logged = False

    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    assert detect_faces(frame) == []
    assert get_cascade_classifier() is None


@pytest.mark.skipif(
    importlib.util.find_spec("cv2") is None,
    reason="OpenCV required",
)
def test_detect_faces_returns_list() -> None:
    detector_module._cascade_classifier = None
    detector_module._cascade_unavailable_logged = False
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    boxes = detect_faces(frame)
    assert isinstance(boxes, list)
