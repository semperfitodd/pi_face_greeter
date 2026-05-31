from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(
    level: str = "INFO",
    log_file: str | Path | None = None,
    console: bool = True,
    capture_loggers: list[str] | None = None,
) -> logging.Logger:
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger("pi_face_greeter")
    logger.setLevel(log_level)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handlers: list[logging.Handler] = []

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    for handler in handlers:
        logger.addHandler(handler)

    if capture_loggers:
        for name in capture_loggers:
            extra_logger = logging.getLogger(name)
            extra_logger.handlers.clear()
            extra_logger.setLevel(log_level)
            extra_logger.propagate = False
            for handler in handlers:
                extra_logger.addHandler(handler)

    return logger
