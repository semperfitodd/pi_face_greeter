from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from pi_face_greeter.app.conversation import (
    _build_prompt,
    _sanitize,
    generate_greeting,
)


def test_generate_greeting_disabled_returns_fallback() -> None:
    fallback = "Hey Todd, good to see you."
    result = generate_greeting(
        "Todd",
        ollama_cfg={"enabled": False},
        fallback_text=fallback,
    )
    assert result == fallback


def test_generate_greeting_success_returns_sanitized_text() -> None:
    with patch(
        "pi_face_greeter.ollama_client.generate",
        return_value=' "Hello Todd! Great to see you this morning." ',
    ):
        result = generate_greeting(
            "Todd",
            ollama_cfg={
                "enabled": True,
                "base_url": "http://localhost:11434",
                "model": "llama3.2:1b",
            },
            fallback_text="fallback",
            now=datetime(2026, 5, 31, 9, 0, 0),
        )
    assert result == "Hello Todd! Great to see you this morning."


def test_generate_greeting_error_returns_fallback() -> None:
    with patch(
        "pi_face_greeter.ollama_client.generate",
        side_effect=RuntimeError("timeout"),
    ):
        result = generate_greeting(
            "Todd",
            ollama_cfg={"enabled": True},
            fallback_text="fallback",
        )
    assert result == "fallback"


def test_build_prompt_includes_name_and_time_of_day() -> None:
    prompt = _build_prompt("Todd", "morning")
    assert "Todd" in prompt
    assert "morning" in prompt


def test_build_prompt_unknown_visitor() -> None:
    prompt = _build_prompt(None, "evening")
    assert "visitor" in prompt
    assert "evening" in prompt


def test_warmup_ollama_skips_when_disabled() -> None:
    from pi_face_greeter.app.conversation import warmup_ollama

    with patch("pi_face_greeter.ollama_client.warmup") as mock_warmup:
        warmup_ollama({"enabled": False})
    mock_warmup.assert_not_called()


def test_warmup_ollama_loads_model_when_enabled() -> None:
    from pi_face_greeter.app.conversation import warmup_ollama

    with patch("pi_face_greeter.ollama_client.warmup") as mock_warmup:
        warmup_ollama({"enabled": True, "model": "llama3.2:1b"})
    mock_warmup.assert_called_once()


def test_sanitize_strips_quotes_and_limits_sentences() -> None:
    text = '"Hello there. How are you? Nice to see you again."'
    assert _sanitize(text) == "Hello there. How are you?"
