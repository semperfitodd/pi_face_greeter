from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pi_face_greeter.conversation import (
    build_opener,
    conversation_enabled,
    generate_greeting,
    run_conversation,
)
from pi_face_greeter.mic import MicStream
from pi_face_greeter.greeting import build_greeting
from pi_face_greeter.recognition import get_person_greeting
from pi_face_greeter.tts import speak_from_config


def resolve_greeting_text(
    name: str | None,
    *,
    tts_cfg: dict[str, Any],
    ollama_cfg: dict[str, Any] | None = None,
    conversation_cfg: dict[str, Any] | None = None,
    custom_greeting: str | None = None,
    camera_disabled: bool = False,
) -> str:
    ollama = ollama_cfg or {}
    conversation = conversation_cfg or {}
    ask_how_are_you = bool(tts_cfg.get("ask_how_are_you", True))

    if conversation_enabled(conversation, ollama):
        if camera_disabled:
            return str(
                tts_cfg.get(
                    "placeholder_greeting",
                    "Hello. Face recognition is not enabled yet.",
                )
            )
        if custom_greeting is None and name:
            custom_greeting = get_person_greeting(name)
        return build_opener(name, custom_greeting)

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


def run_greeting_interaction(
    name: str | None,
    *,
    tts_cfg: dict[str, Any],
    ollama_cfg: dict[str, Any] | None = None,
    conversation_cfg: dict[str, Any] | None = None,
    stt_cfg: dict[str, Any] | None = None,
    assistant_cfg: dict[str, Any] | None = None,
    custom_greeting: str | None = None,
    camera_disabled: bool = False,
    on_status: Callable[[str], None] | None = None,
    on_before_speak: Callable[[str], None] | None = None,
    on_after_speak: Callable[[], None] | None = None,
    mic: MicStream | None = None,
    skip_opener: bool = False,
    require_presence: bool = True,
    is_present: Callable[[], bool] | None = None,
) -> str:
    ollama = ollama_cfg or {}
    conversation = conversation_cfg or {}
    stt = stt_cfg or {}
    assistant = assistant_cfg or {}

    greeting = resolve_greeting_text(
        name,
        tts_cfg=tts_cfg,
        ollama_cfg=ollama,
        conversation_cfg=conversation,
        custom_greeting=custom_greeting,
        camera_disabled=camera_disabled,
    )

    if conversation_enabled(conversation, ollama) and not camera_disabled:
        opener = "" if skip_opener else greeting
        run_conversation(
            name,
            opener,
            mic=mic,
            tts_cfg=tts_cfg,
            stt_cfg=stt,
            ollama_cfg=ollama,
            conversation_cfg=conversation,
            assistant_cfg=assistant,
            on_status=on_status,
            on_before_speak=on_before_speak,
            on_after_speak=on_after_speak,
            skip_opener=skip_opener,
            require_presence=require_presence,
            is_present=is_present,
        )
        return greeting if not skip_opener else ""

    if on_before_speak is not None:
        on_before_speak(greeting)
    speak_from_config(greeting, tts_cfg)
    if on_after_speak is not None:
        on_after_speak()
    return greeting


def speak_greeting(
    name: str | None,
    *,
    tts_cfg: dict[str, Any],
    ollama_cfg: dict[str, Any] | None = None,
    conversation_cfg: dict[str, Any] | None = None,
    stt_cfg: dict[str, Any] | None = None,
    assistant_cfg: dict[str, Any] | None = None,
    custom_greeting: str | None = None,
    camera_disabled: bool = False,
    mic: MicStream | None = None,
    skip_opener: bool = False,
    require_presence: bool = True,
    is_present: Callable[[], bool] | None = None,
) -> str:
    return run_greeting_interaction(
        name,
        tts_cfg=tts_cfg,
        ollama_cfg=ollama_cfg,
        conversation_cfg=conversation_cfg,
        stt_cfg=stt_cfg,
        assistant_cfg=assistant_cfg,
        custom_greeting=custom_greeting,
        camera_disabled=camera_disabled,
        mic=mic,
        skip_opener=skip_opener,
        require_presence=require_presence,
        is_present=is_present,
    )
