from __future__ import annotations

import logging
import sys
from io import StringIO
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import patch

from pi_face_greeter.cli_output import (
    configure_validation_logging,
    report_failure,
    report_success,
)


def test_report_success_prints_one_line(capsys) -> None:
    report_success("Step 1 passed.")
    captured = capsys.readouterr()
    assert captured.out.strip() == "Step 1 passed."
    assert captured.err == ""


def test_report_failure_includes_error_and_log_path(tmp_path: Path) -> None:
    log_path = tmp_path / "greeter.log"
    log_path.write_text("line1\nline2\n", encoding="utf-8")

    with patch("sys.stderr", new=StringIO()) as stderr:
        report_failure(
            "Step 1 failed: camera capture",
            RuntimeError("camera unavailable"),
            log_path,
            hint="rpicam-hello --list-cameras",
        )
        output = stderr.getvalue()

    assert "Step 1 failed: camera capture" in output
    assert "Error: camera unavailable" in output
    assert str(log_path.resolve()) in output
    assert "Hint: rpicam-hello --list-cameras" in output
    assert "--- log tail ---" in output
    assert "line2" in output


def test_configure_validation_logging_no_console_handler(tmp_path: Path) -> None:
    log_path = tmp_path / "test.log"
    configure_validation_logging(log_file=log_path, level="INFO")

    root = logging.getLogger("pi_face_greeter")
    assert not any(getattr(h, "stream", None) in (sys.stderr, sys.stdout) for h in root.handlers)
    assert any(isinstance(h, RotatingFileHandler) for h in root.handlers)

    assert logging.getLogger("picamera2").level == logging.WARNING
