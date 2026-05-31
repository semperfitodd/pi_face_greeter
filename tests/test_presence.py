from __future__ import annotations

from pi_face_greeter.app.presence import should_trigger_greeting
from pi_face_greeter.cooldown import CooldownGate


def test_should_trigger_greeting_when_ready() -> None:
    cooldown = CooldownGate(30)
    assert should_trigger_greeting(5, 5, cooldown) is True


def test_should_not_trigger_before_enough_frames() -> None:
    cooldown = CooldownGate(30)
    assert should_trigger_greeting(4, 5, cooldown) is False


def test_should_not_trigger_during_cooldown() -> None:
    cooldown = CooldownGate(30)
    cooldown.mark_triggered()
    assert should_trigger_greeting(5, 5, cooldown) is False
