from __future__ import annotations

from typing import Any

from pi_face_greeter.conversation import generate_greeting
from pi_face_greeter.greeting import build_greeting
from pi_face_greeter.recognition import get_person_greeting
from pi_face_greeter.tts import speak_from_config


def resolve_greeting_text(
    name: str | None,
    *,
    tts_cfg: dict[str, Any],
    ollama_cfg: dict[str, Any] | None = None,
    custom_greeting: str | None = None,
    camera_disabled: bool = False,
) -> str:
    ollama = ollama_cfg or {}
    ask_how_are_you = bool(tts_cfg.get("ask_how_are_you", True))

    if camera_disabled:
        fallback = tts_cfg.get(
            "placeholder_greeting",
            "Hello. Face recognition is not enabled yet.",
        )
        return generate_greeting(None, ollama_cfg=ollama, fallback_text=str(fallback))

    if custom_greeting is None and name:
        custom_greeting = get_person_greeting(name)

    fallback = build_greeting(
        name,
        custom_greeting,
        ask_how_are_you=ask_how_are_you,
    )
    return generate_greeting(name, ollama_cfg=ollama, fallback_text=fallback)


def speak_greeting(
    name: str | None,
    *,
    tts_cfg: dict[str, Any],
    ollama_cfg: dict[str, Any] | None = None,
    custom_greeting: str | None = None,
    camera_disabled: bool = False,
) -> str:
    greeting = resolve_greeting_text(
        name,
        tts_cfg=tts_cfg,
        ollama_cfg=ollama_cfg,
        custom_greeting=custom_greeting,
        camera_disabled=camera_disabled,
    )
    speak_from_config(greeting, tts_cfg)
    return greeting
