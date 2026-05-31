from __future__ import annotations

import random

GREETINGS_KNOWN = [
    "Hey {name}, good to see you.",
    "Hi {name}!",
    "Hello {name}, great to see you again.",
]
GREETINGS_UNKNOWN = [
    "Well, hello there.",
    "Hi there!",
    "Hey, nice to see you.",
]
HOW_ARE_YOU = [
    "How are you doing today?",
    "How's it going?",
    "How are you?",
]


def build_greeting(
    name: str | None,
    custom_greeting: str | None = None,
    *,
    ask_how_are_you: bool = True,
    rng: random.Random | None = None,
) -> str:
    chooser = rng or random

    if custom_greeting:
        base = custom_greeting
    elif name:
        base = chooser.choice(GREETINGS_KNOWN).format(name=name)
    else:
        base = chooser.choice(GREETINGS_UNKNOWN)

    if ask_how_are_you:
        return f"{base} {chooser.choice(HOW_ARE_YOU)}"
    return base
