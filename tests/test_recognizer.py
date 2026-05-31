from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from pi_face_greeter.app.recognizer import FaceRecognizer, encode_face


@pytest.fixture
def fake_face_recognition(monkeypatch):
    module = types.ModuleType("face_recognition")

    def face_encodings(frame, known_face_locations=None):
        del frame
        if not known_face_locations:
            return []
        return [np.ones(128, dtype=np.float64)]

    def face_distance(known_encodings, face_encoding):
        return np.linalg.norm(np.stack(known_encodings) - face_encoding, axis=1)

    module.face_encodings = face_encodings
    module.face_distance = face_distance
    monkeypatch.setitem(sys.modules, "face_recognition", module)
    return module


def test_encode_face_returns_none_without_face(monkeypatch) -> None:
    monkeypatch.setattr(
        "pi_face_greeter.app.recognizer.detect_faces",
        lambda _frame, _cfg=None: [],
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    assert encode_face(frame) is None


def test_encode_face_uses_largest_box(fake_face_recognition, monkeypatch) -> None:
    monkeypatch.setattr(
        "pi_face_greeter.app.recognizer.detect_faces",
        lambda _frame, _cfg=None: [(10, 10, 20, 20), (0, 0, 50, 50)],
    )
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    encoding = encode_face(frame)
    assert encoding is not None
    assert encoding.shape == (128,)


def test_identify_empty_database() -> None:
    recognizer = FaceRecognizer(tolerance=0.6)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    assert recognizer.identify(frame) == (None, 0.0)


def test_identify_returns_best_match(fake_face_recognition, monkeypatch) -> None:
    monkeypatch.setattr(
        "pi_face_greeter.app.recognizer.encode_face",
        lambda _frame, _box=None: np.ones(128, dtype=np.float64),
    )

    recognizer = FaceRecognizer(tolerance=0.6)
    recognizer.names = ["Alice", "Bob"]
    recognizer.encodings = [
        np.ones(128, dtype=np.float64),
        np.array([0.0, 1.0] + [0.0] * 126, dtype=np.float64),
    ]

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    name, confidence = recognizer.identify(frame)
    assert name == "Alice"
    assert confidence > 0.0


def test_identify_respects_tolerance(fake_face_recognition, monkeypatch) -> None:
    monkeypatch.setattr(
        "pi_face_greeter.app.recognizer.encode_face",
        lambda _frame, _box=None: np.zeros(128, dtype=np.float64),
    )

    recognizer = FaceRecognizer(tolerance=0.1)
    recognizer.names = ["Alice"]
    recognizer.encodings = [np.array([1.0, 0.0] + [0.0] * 126, dtype=np.float64)]

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    assert recognizer.identify(frame) == (None, 0.0)


def test_load_reads_encodings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pi_face_greeter.app.recognizer.PROJECT_ROOT", tmp_path)

    face_dir = tmp_path / "data" / "known_faces" / "todd"
    face_dir.mkdir(parents=True)
    encodings = np.stack(
        [
            np.array([1.0] + [0.0] * 127, dtype=np.float64),
            np.array([0.5] + [0.0] * 127, dtype=np.float64),
        ]
    )
    np.save(face_dir / "encodings.npy", encodings)

    recognizer = FaceRecognizer()
    recognizer.load(
        [{"name": "Todd", "face_dir": "data/known_faces/todd"}],
        project_root=tmp_path,
    )

    assert recognizer.names == ["Todd", "Todd"]
    assert len(recognizer.encodings) == 2
    assert recognizer.get_person("Todd")["name"] == "Todd"


def test_face_recognition_module_reload(monkeypatch) -> None:
    import pi_face_greeter.face_recognition as fr

    recognizer = MagicMock()
    monkeypatch.setattr(fr, "_recognizer", recognizer)
    monkeypatch.setattr(
        fr,
        "list_people",
        lambda: [{"name": "Todd", "face_dir": "data/known_faces/todd"}],
    )

    fr.reload()
    recognizer.load.assert_called_once()


def test_identify_auto_configures(monkeypatch) -> None:
    import pi_face_greeter.face_recognition as fr

    mock_recognizer = MagicMock()
    mock_recognizer.identify.return_value = ("Todd", 0.9)

    monkeypatch.setattr(fr, "_recognizer", None)

    def fake_configure(recognition_cfg=None):
        fr._recognizer = mock_recognizer
        return mock_recognizer

    monkeypatch.setattr(fr, "configure", fake_configure)

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    name, confidence = fr.identify(frame)

    mock_recognizer.identify.assert_called_once_with(frame)
    assert name == "Todd"
    assert confidence == 0.9
