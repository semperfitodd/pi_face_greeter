from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from urllib.parse import urlparse

from pi_face_greeter import ollama_client

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
