from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from pi_face_greeter.validate_motion import run_validate_motion


def test_run_validate_motion_pir_disabled() -> None:
    config = {
        "logging": {"file": "data/logs/greeter.log"},
        "pir": {"enabled": False},
    }

    with patch("pi_face_greeter.validate_motion.report_failure") as mock_failure:
        result = run_validate_motion(config)

    assert result == 1
    mock_failure.assert_called_once()
    assert "PIR not enabled" in mock_failure.call_args[0][0]


def test_run_validate_motion_timeout() -> None:
    config = {
        "logging": {"file": "data/logs/greeter.log"},
        "pir": {"enabled": True, "gpio_pin": 17},
        "validation": {"pir_wait_seconds": 30},
        "camera": {"enabled": True},
        "tts": {"enabled": True},
    }

    mock_pir = MagicMock()
    mock_pir.wait_for_motion.return_value = False

    with (
        patch("pi_face_greeter.validate_motion.PIRSensor", return_value=mock_pir),
        patch("pi_face_greeter.validate_motion.report_failure") as mock_failure,
    ):
        result = run_validate_motion(config)

    assert result == 1
    mock_failure.assert_called_once()
    assert "no motion detected" in mock_failure.call_args[0][0]
    mock_pir.close.assert_called_once()


def test_run_validate_motion_success(tmp_path: Path) -> None:
    frame_path = tmp_path / "motion_frame.jpg"
    frame_path.write_bytes(b"jpeg")

    config = {
        "logging": {"file": str(tmp_path / "greeter.log")},
        "pir": {"enabled": True, "gpio_pin": 17},
        "validation": {"pir_wait_seconds": 30},
        "camera": {"enabled": True},
        "tts": {"enabled": True},
    }

    mock_pir = MagicMock()
    mock_pir.wait_for_motion.return_value = True

    with (
        patch("pi_face_greeter.validate_motion.PIRSensor", return_value=mock_pir),
        patch(
            "pi_face_greeter.validate_motion.run_greet_cycle",
            return_value=(None, frame_path),
        ),
        patch("pi_face_greeter.validate_motion.report_success") as mock_success,
    ):
        result = run_validate_motion(config)

    assert result == 0
    mock_success.assert_called_once()
    assert "GPIO17" in mock_success.call_args[0][0]
    mock_pir.close.assert_called_once()


def test_run_validate_motion_greet_failure() -> None:
    config = {
        "logging": {"file": "data/logs/greeter.log"},
        "pir": {"enabled": True, "gpio_pin": 17},
        "validation": {"pir_wait_seconds": 30},
        "camera": {"enabled": True},
        "tts": {"enabled": True},
    }

    mock_pir = MagicMock()
    mock_pir.wait_for_motion.return_value = True

    with (
        patch("pi_face_greeter.validate_motion.PIRSensor", return_value=mock_pir),
        patch(
            "pi_face_greeter.validate_motion.run_greet_cycle",
            side_effect=RuntimeError("camera error"),
        ),
        patch("pi_face_greeter.validate_motion.report_failure") as mock_failure,
    ):
        result = run_validate_motion(config)

    assert result == 1
    mock_failure.assert_called_once()
    assert "greet cycle" in mock_failure.call_args[0][0]
