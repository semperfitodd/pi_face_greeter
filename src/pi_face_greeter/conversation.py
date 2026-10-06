from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from urllib.parse import urlparse

from collections.abc import Callable

from pi_face_greeter import ollama_client
from pi_face_greeter.stt import listen_from_config
from pi_face_greeter.tts import speak_from_config

logger = logging.getLogger("pi_face_greeter.conversation")

ALLOWED_OLLAMA_HOSTS = frozenset({"127.0.0.1", "localhost"})


class OllamaConfigError(ValueError):
    pass


def validate_ollama_base_url(base_url: str) -> str:
    parsed = urlparse(base_url.strip())
    if parsed.scheme != "http":
        raise OllamaConfigError("Ollama base_url must use http")
    if parsed.hostname not in ALLOWED_OLLAMA_HOSTS:
        raise OllamaConfigError("Ollama base_url must point to localhost")
    if parsed.username or parsed.password:
        raise OllamaConfigError("Ollama base_url must not include credentials")
    if parsed.path not in ("", "/"):
        raise OllamaConfigError("Ollama base_url must not include a path")
    port = parsed.port if parsed.port is not None else 11434
    host = parsed.hostname
    assert host is not None
    return f"http://{host}:{port}"

MAX_GREETING_CHARS = 280
MAX_REPLY_CHARS = 400

DEFAULT_ASSISTANT_NAME = "Vesper"
DEFAULT_SYSTEM_PROMPT = (
    "You are {assistant_name}, a helpful executive assistant speaking out loud. "
    "The person with you is {person_label}. It is {time_of_day}. "
    "Be warm, concise, and useful. Answer in one or two short spoken sentences. "
    "Do not use emojis, markdown, lists, or quotation marks. "
    "Do not mention being an AI."
)

_GOODBYE_PATTERN = re.compile(
    r"\b(goodbye|bye|see you|talk later|gotta go|have to go)\b",
    re.IGNORECASE,
)


def _time_of_day(now: datetime) -> str:
    hour = now.hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def _build_prompt(name: str | None, time_of_day: str) -> str:
    if name:
        subject = f"The person's name is {name}."
        audience = name
    else:
        subject = "You do not know this person's name."
        audience = "a visitor"

    return (
        "You are a friendly door greeter speaking out loud through a speaker. "
        f"{subject} "
        f"It is {time_of_day}. "
        f"Write one warm spoken greeting for {audience}. "
        "Keep it to one or two short sentences. "
        "Do not use emojis, markdown, bullet points, or quotation marks. "
        "Do not mention being an AI."
    )


def build_opener(name: str | None, custom_greeting: str | None = None) -> str:
    if custom_greeting:
        return custom_greeting.strip()
    if name:
        return f"Hi, {name}. How are you?"
    return "Hi. How are you?"


def build_system_prompt(
    name: str | None,
    *,
    assistant_cfg: dict[str, Any],
    now: datetime | None = None,
) -> str:
    moment = now or datetime.now()
    assistant_name = str(assistant_cfg.get("name", DEFAULT_ASSISTANT_NAME))
    template = str(assistant_cfg.get("system_prompt", DEFAULT_SYSTEM_PROMPT))
    person_label = name if name else "a visitor"
    return template.format(
        assistant_name=assistant_name,
        person_label=person_label,
        name=person_label,
        time_of_day=_time_of_day(moment),
    )


def _sanitize_reply(text: str) -> str:
    cleaned = _sanitize(text)
    if len(cleaned) > MAX_REPLY_CHARS:
        cleaned = cleaned[: MAX_REPLY_CHARS - 3].rstrip() + "..."
    return cleaned


def conversation_enabled(
    conversation_cfg: dict[str, Any],
    ollama_cfg: dict[str, Any],
) -> bool:
    return bool(conversation_cfg.get("enabled", False) and ollama_cfg.get("enabled", False))


def _is_goodbye(text: str) -> bool:
    return bool(_GOODBYE_PATTERN.search(text))


def run_conversation(
    name: str | None,
    opener: str,
    *,
    tts_cfg: dict[str, Any],
    stt_cfg: dict[str, Any],
    ollama_cfg: dict[str, Any],
    conversation_cfg: dict[str, Any],
    assistant_cfg: dict[str, Any],
    on_status: Callable[[str], None] | None = None,
    on_before_speak: Callable[[str], None] | None = None,
    on_after_speak: Callable[[], None] | None = None,
    now: datetime | None = None,
) -> None:
    if not conversation_enabled(conversation_cfg, ollama_cfg):
        speak_from_config(opener, tts_cfg)
        return

    settings = _ollama_settings(ollama_cfg)
    keep_alive = settings["keep_alive"]
    if keep_alive is not None:
        keep_alive = str(keep_alive)

    max_turns = int(conversation_cfg.get("max_turns", 4))
    max_tokens = int(conversation_cfg.get("max_tokens", ollama_cfg.get("max_tokens", 120)))
    temperature = float(conversation_cfg.get("temperature", ollama_cfg.get("temperature", 0.7)))

    system_prompt = build_system_prompt(name, assistant_cfg=assistant_cfg, now=now)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "assistant", "content": opener},
    ]

    def status(text: str) -> None:
        if on_status is not None:
            on_status(text)

    def speak_line(text: str) -> None:
        if on_before_speak is not None:
            on_before_speak(text)
        speak_from_config(text, tts_cfg)
        if on_after_speak is not None:
            on_after_speak()

    speak_line(opener)

    for turn in range(max_turns):
        status("Listening...")
        user_text = listen_from_config(stt_cfg)
        if not user_text:
            logger.info("Conversation ended: no speech (turn %d)", turn + 1)
            break

        logger.info("User said: %s", user_text[:120])
        messages.append({"role": "user", "content": user_text})

        if _is_goodbye(user_text):
            logger.info("Conversation ended: user goodbye")
            break

        try:
            raw = ollama_client.chat(
                messages,
                base_url=settings["base_url"],
                model=settings["model"],
                timeout=settings["timeout"],
                max_tokens=max_tokens,
                temperature=temperature,
                keep_alive=keep_alive,
            )
            reply = _sanitize_reply(raw)
            if not reply:
                raise RuntimeError("Ollama chat reply empty after sanitization")
        except Exception:
            logger.warning("Ollama chat failed on turn %d", turn + 1, exc_info=True)
            break

        messages.append({"role": "assistant", "content": reply})
        status(reply)
        speak_line(reply)

    status("")


def _sanitize(text: str) -> str:
    cleaned = text.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in "\"'":
        cleaned = cleaned[1:-1].strip()

    cleaned = re.sub(r"\s+", " ", cleaned)
    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    cleaned = " ".join(sentences[:2]).strip()

    if len(cleaned) > MAX_GREETING_CHARS:
        cleaned = cleaned[: MAX_GREETING_CHARS - 3].rstrip() + "..."
    return cleaned


def _ollama_settings(ollama_cfg: dict[str, Any]) -> dict[str, Any]:
    warmup_timeout = float(ollama_cfg.get("warmup_timeout_seconds", 60))
    raw_url = str(ollama_cfg.get("base_url", "http://localhost:11434"))
    return {
        "base_url": validate_ollama_base_url(raw_url),
        "model": str(ollama_cfg.get("model", "llama3.2:1b")),
        "timeout": float(ollama_cfg.get("timeout_seconds", 30)),
        "warmup_timeout": warmup_timeout,
        "keep_alive": ollama_cfg.get("keep_alive", "10m"),
    }


def warmup_ollama(ollama_cfg: dict[str, Any]) -> None:
    if not ollama_cfg.get("enabled", False):
        return
    if not ollama_cfg.get("warmup_on_startup", True):
        return

    settings = _ollama_settings(ollama_cfg)
    keep_alive = settings["keep_alive"]
    if keep_alive is not None:
        keep_alive = str(keep_alive)

    try:
        ollama_client.warmup(
            base_url=settings["base_url"],
            model=settings["model"],
            timeout=settings["warmup_timeout"],
            keep_alive=keep_alive,
        )
    except Exception:
        logger.warning("Ollama warmup failed; first greeting may be slow", exc_info=True)


def generate_greeting(
    name: str | None,
    *,
    ollama_cfg: dict[str, Any],
    fallback_text: str,
    now: datetime | None = None,
) -> str:
    if not ollama_cfg.get("enabled", False):
        return fallback_text

    settings = _ollama_settings(ollama_cfg)
    keep_alive = settings["keep_alive"]
    if keep_alive is not None:
        keep_alive = str(keep_alive)

    moment = now or datetime.now()
    prompt = _build_prompt(name, _time_of_day(moment))

    try:
        raw = ollama_client.generate(
            prompt,
            base_url=settings["base_url"],
            model=settings["model"],
            timeout=settings["timeout"],
            max_tokens=int(ollama_cfg.get("max_tokens", 60)),
            temperature=float(ollama_cfg.get("temperature", 0.7)),
            keep_alive=keep_alive,
        )
        sanitized = _sanitize(raw)
        if not sanitized:
            raise RuntimeError("Ollama greeting was empty after sanitization")
        logger.info("Ollama generated greeting for %s", name or "unknown")
        return sanitized
    except Exception:
        logger.warning(
            "Ollama greeting failed for %s; using fallback",
            name or "unknown",
            exc_info=True,
        )
        return fallback_text
