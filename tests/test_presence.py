from __future__ import annotations

from pi_face_greeter.app.presence import should_trigger_greeting


def test_should_trigger_greeting_when_ready() -> None:
    assert should_trigger_greeting(5, 5) is True


def test_should_not_trigger_before_enough_frames() -> None:
    assert should_trigger_greeting(4, 5) is False
