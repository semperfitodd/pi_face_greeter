from __future__ import annotations

from pi_face_greeter.app.per_person_cooldown import (
    UNKNOWN_COOLDOWN_KEY,
    PerPersonCooldown,
    cooldown_key,
)


def test_cooldown_key_for_unknown() -> None:
    assert cooldown_key(None) == UNKNOWN_COOLDOWN_KEY
    assert cooldown_key("Todd") == "Todd"


def test_per_person_cooldown_is_independent() -> None:
    cooldown = PerPersonCooldown(default_seconds=30)
    cooldown.mark_triggered("Todd")

    assert cooldown.can_trigger("Todd") is False
    assert cooldown.can_trigger("Jane") is True


def test_per_person_cooldown_unknown_shares_key() -> None:
    cooldown = PerPersonCooldown(default_seconds=30)
    cooldown.mark_triggered(cooldown_key(None))

    assert cooldown.can_trigger(cooldown_key(None)) is False


def test_per_person_cooldown_duration_override() -> None:
    cooldown = PerPersonCooldown(default_seconds=30)
    cooldown.set_duration("Todd", 120)
    cooldown.mark_triggered("Todd")

    assert cooldown.seconds_remaining("Todd") > 30
