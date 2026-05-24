from __future__ import annotations

import logging
import sys
from pathlib import Path

from pi_face_greeter.logger import setup_logging

LOG_TAIL_LINES = 40
NOISY_LOGGER_NAMES = ("picamera2", "libcamera", "PIL", "gpiozero")


def configure_validation_logging(
    log_file: str | Path | None,
    level: str = "INFO",
) -> Path | None:
    path = Path(log_file) if log_file else None
    setup_logging(level=level, log_file=path, console=False)

    for name in NOISY_LOGGER_NAMES:
        logging.getLogger(name).setLevel(logging.WARNING)

    return path


def report_success(message: str) -> None:
    print(message)


def report_failure(
    title: str,
    error: Exception,
    log_path: Path | None,
    hint: str | None = None,
) -> None:
    logger = logging.getLogger("pi_face_greeter")
    logger.error("%s: %s", title, error, exc_info=(type(error), error, error.__traceback__))

    lines = [title, f"Error: {error}"]
    if log_path is not None:
        lines.append(f"Log: {log_path.resolve()}")
    if hint:
        lines.append(f"Hint: {hint}")

    if log_path is not None and log_path.exists():
        tail = _read_log_tail(log_path)
        if tail:
            lines.append("--- log tail ---")
            lines.extend(tail)

    print("\n".join(lines), file=sys.stderr)


def _read_log_tail(log_path: Path, max_lines: int = LOG_TAIL_LINES) -> list[str]:
    try:
        content = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return content[-max_lines:]
