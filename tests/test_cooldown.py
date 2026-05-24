from __future__ import annotations

from pi_face_greeter.cooldown import CooldownGate


def test_can_trigger_initially() -> None:
    gate = CooldownGate(30)
    assert gate.can_trigger() is True
    assert gate.seconds_remaining() == 0.0


def test_blocks_until_cooldown_elapsed(monkeypatch) -> None:
    times = iter([100.0, 110.0, 110.0, 140.0, 140.0])
    monkeypatch.setattr("pi_face_greeter.cooldown.time.monotonic", lambda: next(times))

    gate = CooldownGate(30)
    gate.mark_triggered()

    assert gate.can_trigger() is False
    assert gate.seconds_remaining() == 20.0

    assert gate.can_trigger() is True
    assert gate.seconds_remaining() == 0.0
