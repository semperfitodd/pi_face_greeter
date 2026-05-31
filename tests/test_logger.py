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
