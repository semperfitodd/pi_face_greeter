from __future__ import annotations

from pathlib import Path

from pi_face_greeter.events import (
    configure_session_log,
    format_face_cooldown,
    format_face_recognized,
    format_face_unknown,
    log_event,
    truncate_session_text,
)


def test_truncate_session_text_shortens_long_lines() -> None:
    text = "a" * 250
    assert len(truncate_session_text(text)) == 200
    assert truncate_session_text(text).endswith("...")


def test_format_face_helpers() -> None:
    assert format_face_recognized("Todd", 0.82) == "face recognized name=Todd confidence=0.82"
    assert format_face_unknown() == "face unknown"
    assert format_face_cooldown("Todd") == "face recognized name=Todd cooldown=yes"


def test_log_event_writes_to_session_file(tmp_path: Path) -> None:
    session_path = tmp_path / "session.log"
    configure_session_log(session_path)
    log_event("listen start")
    log_event("listen heard: hello")
    configure_session_log(None)
    content = session_path.read_text(encoding="utf-8")
    assert "listen start" in content
    assert "listen heard: hello" in content
