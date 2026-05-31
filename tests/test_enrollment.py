from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import yaml

from pi_face_greeter.enroll import run_enroll
from pi_face_greeter.enrollment import (
    enroll_from_frames,
    enroll_person,
    register_person,
    slugify_name,
)


def test_slugify_name() -> None:
    assert slugify_name("Todd") == "todd"
    assert slugify_name("Jane Doe") == "jane-doe"


def test_slugify_name_rejects_empty() -> None:
    with pytest.raises(ValueError, match="at least one"):
        slugify_name("!!!")


def test_register_person_adds_entry(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pi_face_greeter.enrollment.PROJECT_ROOT", tmp_path)
    people_file = tmp_path / "people.yaml"
    people_file.write_text("people: []\n", encoding="utf-8")
    monkeypatch.setattr("pi_face_greeter.enrollment.PEOPLE_YAML", people_file)

    face_dir = tmp_path / "data" / "known_faces" / "todd"
    face_dir.mkdir(parents=True)

    register_person("Todd", face_dir)

    data = yaml.safe_load(people_file.read_text(encoding="utf-8"))
    assert len(data["people"]) == 1
    assert data["people"][0]["name"] == "Todd"
    assert data["people"][0]["face_dir"] == "data/known_faces/todd"


def test_enroll_person_saves_photos(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pi_face_greeter.enrollment.PROJECT_ROOT", tmp_path)
    people_file = tmp_path / "config" / "people.yaml"
    people_file.parent.mkdir(parents=True)
    people_file.write_text("people: []\n", encoding="utf-8")
    monkeypatch.setattr("pi_face_greeter.enrollment.PEOPLE_YAML", people_file)

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_camera = MagicMock()
    mock_camera.capture_frame.return_value = frame

    camera_cfg = {"enabled": True, "backend": "picamera2"}
    enrollment_cfg = {
        "capture_count": 2,
        "delay_seconds": 0,
        "known_faces_dir": str(tmp_path / "data" / "known_faces"),
    }

    fake_encoding = np.ones(128, dtype=np.float64)

    with (
        patch("pi_face_greeter.enrollment.create_camera", return_value=mock_camera),
        patch("pi_face_greeter.enrollment._validate_frame"),
        patch("pi_face_greeter.enrollment.detect_faces", return_value=[(100, 100, 80, 80)]),
        patch("pi_face_greeter.enrollment.encode_face", return_value=fake_encoding),
        patch("pi_face_greeter.enrollment._save_frame_jpeg"),
        patch("pi_face_greeter.enrollment.time.sleep"),
    ):
        person_dir = enroll_person("Todd", camera_cfg, enrollment_cfg)

    assert person_dir.name == "todd"
    assert (person_dir / "encodings.npy").exists()
    mock_camera.close.assert_called_once()


def test_enroll_from_frames_saves_photos_and_encodings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("pi_face_greeter.enrollment.PROJECT_ROOT", tmp_path)
    people_file = tmp_path / "config" / "people.yaml"
    people_file.parent.mkdir(parents=True)
    people_file.write_text("people: []\n", encoding="utf-8")
    monkeypatch.setattr("pi_face_greeter.enrollment.PEOPLE_YAML", people_file)

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    enrollment_cfg = {
        "known_faces_dir": str(tmp_path / "data" / "known_faces"),
        "minimum_photos": 1,
    }
    fake_encoding = np.arange(128, dtype=np.float64)

    with (
        patch(
            "pi_face_greeter.enrollment.detect_faces",
            return_value=[(100, 100, 80, 80)],
        ),
        patch("pi_face_greeter.enrollment.encode_face", return_value=fake_encoding),
        patch("pi_face_greeter.enrollment._save_frame_jpeg") as mock_save,
    ):
        result = enroll_from_frames("Todd", [frame, frame], enrollment_cfg)

    assert result["photo_count"] == 2
    assert result["face_dir"].name == "todd"
    assert mock_save.call_count == 2
    encodings = np.load(result["face_dir"] / "encodings.npy")
    assert encodings.shape == (2, 128)

    data = yaml.safe_load(people_file.read_text(encoding="utf-8"))
    assert data["people"][0]["name"] == "Todd"


def test_run_enroll_success(tmp_path: Path) -> None:
    config = {
        "logging": {"file": str(tmp_path / "greeter.log")},
        "camera": {"enabled": True},
        "enrollment": {"known_faces_dir": str(tmp_path / "faces")},
    }

    with (
        patch(
            "pi_face_greeter.enroll.enroll_person",
            return_value=tmp_path / "faces" / "todd",
        ),
        patch("pi_face_greeter.enroll.report_success") as mock_success,
    ):
        (tmp_path / "faces" / "todd").mkdir(parents=True)
        for i in range(1, 4):
            (tmp_path / "faces" / "todd" / f"{i:03d}.jpg").write_bytes(b"jpeg")
        result = run_enroll("Todd", config)

    assert result == 0
    mock_success.assert_called_once()
    assert "Step 2 passed" in mock_success.call_args[0][0]
