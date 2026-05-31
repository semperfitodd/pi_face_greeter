from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from pi_face_greeter.app import detector as detector_module
from pi_face_greeter.app.debug_frames import save_debug_frame
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
    detector_module._cascade_load_logged = False
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
    detector_module._cascade_load_logged = False

    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    assert detect_faces(frame) == []
    assert get_cascade_classifier() is None


@pytest.mark.skipif(
    importlib.util.find_spec("cv2") is None,
    reason="OpenCV required",
)
def test_detect_faces_returns_list() -> None:
    detector_module._cascade_classifier = None
    detector_module._cascade_load_logged = False
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    boxes = detect_faces(frame)
    assert isinstance(boxes, list)


def test_detect_faces_emits_debug_logs(monkeypatch) -> None:
    class FakeDetector:
        def detectMultiScale(self, *_args, **_kwargs):
            return []

    debug_messages: list[str] = []

    def capture_debug(msg: str, *args) -> None:
        debug_messages.append(msg % args if args else msg)

    monkeypatch.setattr(detector_module, "get_cascade_classifier", lambda: FakeDetector())
    monkeypatch.setattr(detector_module, "_prepare_gray", lambda frame, use_clahe: frame[:, :, 0])
    monkeypatch.setattr(detector_module.logger, "isEnabledFor", lambda _level: True)
    monkeypatch.setattr(detector_module.logger, "debug", capture_debug)

    frame = np.full((120, 160, 3), 128, dtype=np.uint8)
    boxes = detect_faces(frame)
    assert isinstance(boxes, list)
    assert any("detect_faces frame shape=" in message for message in debug_messages)


def test_save_debug_frame_writes_jpeg(tmp_path: Path) -> None:
    frame = np.full((100, 120, 3), 200, dtype=np.uint8)
    boxes = ((10, 20, 30, 40),)

    output_path = save_debug_frame(frame, boxes, tmp_path)

    assert output_path.is_file()
    assert output_path.suffix == ".jpg"
    assert output_path.parent == tmp_path
