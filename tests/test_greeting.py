from __future__ import annotations

import random

from pi_face_greeter.app.greeting import HOW_ARE_YOU, build_greeting


class _FakeRng:
    def __init__(self, choices: list) -> None:
        self._choices = choices
        self._index = 0

    def choice(self, options):
        value = self._choices[self._index]
        self._index += 1
        if isinstance(value, int):
            return options[value]
        return value


def test_build_greeting_with_name_includes_question() -> None:
    rng = _FakeRng([0, 0])
    greeting = build_greeting("Todd", rng=rng)
    assert "Todd" in greeting
    assert greeting.endswith("?")


def test_build_greeting_without_name_includes_question() -> None:
    rng = _FakeRng([0, 0])
    greeting = build_greeting(None, rng=rng)
    assert greeting.endswith("?")


def test_build_greeting_custom_message_appends_question() -> None:
    rng = _FakeRng([0])
    greeting = build_greeting(
        "Todd",
        "Welcome home, Todd!",
        rng=rng,
        ask_how_are_you=True,
    )
    assert greeting.startswith("Welcome home, Todd!")
    assert HOW_ARE_YOU[0] in greeting


def test_build_greeting_can_skip_question() -> None:
    rng = random.Random(0)
    greeting = build_greeting("Todd", ask_how_are_you=False, rng=rng)
    assert "Todd" in greeting
    assert "?" not in greeting
