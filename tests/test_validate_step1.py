from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pi_face_greeter.validate_step1 import run_validate_step1, validate_camera, validate_tts


def test_run_validate_step1_success(tmp_path: Path) -> None:
    frame_path = tmp_path / "step1_frame.jpg"
    frame_path.write_bytes(b"jpeg-bytes")

    config = {
        "camera": {"enabled": True},
        "tts": {"enabled": True, "placeholder_greeting": "Hello"},
    }

    with (
        patch("pi_face_greeter.validate_step1.validate_camera") as mock_camera,
        patch("pi_face_greeter.validate_step1.validate_tts") as mock_tts,
        patch("pi_face_greeter.validate_step1.report_success") as mock_success,
    ):
        mock_camera.return_value = frame_path
        result = run_validate_step1(config)

    assert result == 0
    mock_camera.assert_called_once_with(config["camera"])
    mock_tts.assert_called_once_with(config["tts"])
    mock_success.assert_called_once()


def test_run_validate_step1_camera_failure() -> None:
    config = {"camera": {"enabled": True}, "tts": {"enabled": True}}

    with patch(
        "pi_face_greeter.validate_step1.validate_camera",
        side_effect=RuntimeError("camera error"),
    ):
        result = run_validate_step1(config)

    assert result == 1


def test_run_validate_step1_tts_failure(tmp_path: Path) -> None:
    frame_path = tmp_path / "step1_frame.jpg"
    frame_path.write_bytes(b"jpeg-bytes")

    config = {"camera": {"enabled": True}, "tts": {"enabled": True}}

    with (
        patch("pi_face_greeter.validate_step1.validate_camera", return_value=frame_path),
        patch(
            "pi_face_greeter.validate_step1.validate_tts",
            side_effect=RuntimeError("tts error"),
        ),
    ):
        result = run_validate_step1(config)

    assert result == 1


def test_validate_camera_disabled() -> None:
    with pytest.raises(RuntimeError, match="Camera is disabled"):
        validate_camera({"enabled": False})


def test_validate_tts_disabled() -> None:
    with pytest.raises(RuntimeError, match="TTS is disabled"):
        validate_tts({"enabled": False})
