from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import yaml

from pi_face_greeter.enroll import run_enroll
from pi_face_greeter.enrollment import (
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

    def fake_save(_frame: np.ndarray, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * 2000)
        return path

    mock_camera.save_frame.side_effect = fake_save

    camera_cfg = {"enabled": True, "backend": "picamera2"}
    enrollment_cfg = {
        "capture_count": 2,
        "delay_seconds": 0,
        "known_faces_dir": str(tmp_path / "data" / "known_faces"),
    }

    with (
        patch("pi_face_greeter.enrollment.create_camera", return_value=mock_camera),
        patch("pi_face_greeter.enrollment._validate_frame"),
        patch("pi_face_greeter.enrollment.time.sleep"),
    ):
        person_dir = enroll_person("Todd", camera_cfg, enrollment_cfg)

    assert person_dir.name == "todd"
    assert (person_dir / "001.jpg").exists()
    assert (person_dir / "002.jpg").exists()
    mock_camera.close.assert_called_once()


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
