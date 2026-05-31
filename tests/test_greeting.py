from __future__ import annotations

from pi_face_greeter.app.greeting import build_greeting


def test_build_greeting_with_name() -> None:
    assert build_greeting("Todd") == "Hi Todd"


def test_build_greeting_without_name() -> None:
    assert build_greeting(None) == "Hi friend"


def test_build_greeting_custom_message() -> None:
    assert build_greeting("Todd", "Welcome home, Todd!") == "Welcome home, Todd!"
