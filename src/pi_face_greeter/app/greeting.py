from __future__ import annotations


def build_greeting(name: str | None, custom_greeting: str | None = None) -> str:
    if custom_greeting:
        return custom_greeting
    if name:
        return f"Hi {name}"
    return "Hi friend"
