from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

SESSION_TEXT_MAX = 200

_session_handler: RotatingFileHandler | None = None


def configure_session_log(
    path: str | Path | None,
    *,
    max_bytes: int = 1_000_000,
    backup_count: int = 3,
) -> None:
    global _session_handler
    if _session_handler is not None:
        logging.getLogger("pi_face_greeter.session").removeHandler(_session_handler)
        _session_handler.close()
        _session_handler = None

    if not path:
        return

    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    session_logger = logging.getLogger("pi_face_greeter.session")
    session_logger.setLevel(logging.INFO)
    session_logger.handlers.clear()
    session_logger.addHandler(handler)
    session_logger.propagate = False
    _session_handler = handler


def truncate_session_text(text: str, *, limit: int = SESSION_TEXT_MAX) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def log_event(message: str) -> None:
    session_logger = logging.getLogger("pi_face_greeter.session")
    if not session_logger.handlers:
        return
    session_logger.info(message)


def format_face_recognized(name: str, confidence: float) -> str:
    return f"face recognized name={name} confidence={confidence:.2f}"


def format_face_unknown() -> str:
    return "face unknown"


def format_face_cooldown(name: str | None) -> str:
    if name:
        return f"face recognized name={name} cooldown=yes"
    return "face unknown cooldown=yes"
