from __future__ import annotations


def build_greeting(name: str | None) -> str:
    if name:
        return f"Hi {name}"
    return "Hi friend"
