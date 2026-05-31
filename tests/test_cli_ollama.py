from __future__ import annotations

from unittest.mock import patch

from pi_face_greeter import cli


def test_test_ollama_success() -> None:
    config = {
        "logging": {"level": "INFO"},
        "ollama": {
            "enabled": False,
            "base_url": "http://localhost:11434",
            "model": "llama3.2:1b",
        },
    }

    with (
        patch("pi_face_greeter.cli.load_config", return_value=config),
        patch("pi_face_greeter.cli.setup_logging"),
        patch("pi_face_greeter.cli.health_check", return_value=True),
        patch(
            "pi_face_greeter.app.conversation.generate_greeting",
            return_value="Good morning, Todd!",
        ),
    ):
        assert cli.test_ollama() == 0


def test_test_ollama_health_check_failure() -> None:
    config = {"logging": {"level": "INFO"}, "ollama": {}}

    with (
        patch("pi_face_greeter.cli.load_config", return_value=config),
        patch("pi_face_greeter.cli.setup_logging"),
        patch("pi_face_greeter.cli.health_check", return_value=False),
    ):
        assert cli.test_ollama() == 1


def test_test_ollama_fallback_failure() -> None:
    config = {"logging": {"level": "INFO"}, "ollama": {"enabled": True}}

    with (
        patch("pi_face_greeter.cli.load_config", return_value=config),
        patch("pi_face_greeter.cli.setup_logging"),
        patch("pi_face_greeter.cli.health_check", return_value=True),
        patch(
            "pi_face_greeter.app.conversation.generate_greeting",
            return_value="Hey Todd, good to see you.",
        ),
        patch(
            "pi_face_greeter.app.greeting.build_greeting",
            return_value="Hey Todd, good to see you.",
        ),
    ):
        assert cli.test_ollama() == 1
