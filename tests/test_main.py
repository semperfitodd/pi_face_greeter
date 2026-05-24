from __future__ import annotations

from unittest.mock import patch

from pi_face_greeter.main import main


def test_main_exits_when_pir_disabled() -> None:
    config = {
        "logging": {"level": "INFO"},
        "app": {"name": "Pi Face Greeter", "cooldown_seconds": 30},
        "pir": {"enabled": False, "gpio_pin": 17},
        "camera": {"enabled": True},
        "tts": {"enabled": True},
    }

    with (
        patch("pi_face_greeter.main.load_config", return_value=config),
        patch("pi_face_greeter.main.setup_logging"),
        patch("pi_face_greeter.main.PIRSensor") as mock_pir,
    ):
        result = main()

    assert result == 1
    mock_pir.assert_not_called()
