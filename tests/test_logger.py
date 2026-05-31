from __future__ import annotations

import logging
from pathlib import Path

from pi_face_greeter.logger import setup_logging


def test_setup_logging_capture_loggers(tmp_path: Path) -> None:
    log_file = tmp_path / "greeter.log"
    setup_logging(
        level="DEBUG",
        log_file=log_file,
        console=True,
        capture_loggers=["kivy"],
    )

    kivy_logger = logging.getLogger("kivy")
    assert kivy_logger.level == logging.DEBUG
    assert len(kivy_logger.handlers) == 2

    setup_logging(level="INFO", console=False)


def test_setup_logging_rotation_settings(tmp_path: Path) -> None:
    log_file = tmp_path / "greeter.log"
    logger = setup_logging(
        level="INFO",
        log_file=log_file,
        console=False,
        max_bytes=2048,
        backup_count=5,
    )

    file_handlers = [
        handler
        for handler in logger.handlers
        if handler.__class__.__name__ == "RotatingFileHandler"
    ]
    assert len(file_handlers) == 1
    handler = file_handlers[0]
    assert handler.maxBytes == 2048
    assert handler.backupCount == 5
