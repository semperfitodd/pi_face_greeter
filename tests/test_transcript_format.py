from __future__ import annotations

from pi_face_greeter.app.transcript_format import (
    MAX_TRANSCRIPT_TURNS,
    TranscriptTurn,
    append_or_update_turn,
    format_transcript_markup,
)


def test_format_transcript_escapes_markup_in_message() -> None:
    turns = [TranscriptTurn(speaker="Todd", text="Hello <b>world</b>")]
    markup = format_transcript_markup(turns, "Freyja")
    assert "<b>world</b>" not in markup.split("\n", 1)[1]
    assert "Hello" in markup
    assert "Todd" in markup


def test_format_transcript_assistant_color() -> None:
    turns = [TranscriptTurn(speaker="Freyja", text="Hi there")]
    markup = format_transcript_markup(turns, "Freyja")
    assert "0.1,0.9,1.0,1" in markup


def test_append_or_update_turn_replaces_last_for_same_speaker() -> None:
    turns = [TranscriptTurn(speaker="Freyja", text="Hi")]
    append_or_update_turn(turns, "Freyja", "Hi Todd.", replace_last=True)
    assert len(turns) == 1
    assert turns[0].text == "Hi Todd."


def test_append_or_update_turn_caps_history() -> None:
    turns: list[TranscriptTurn] = []
    for index in range(MAX_TRANSCRIPT_TURNS + 5):
        append_or_update_turn(turns, "Todd", f"line {index}", replace_last=False)
    assert len(turns) == MAX_TRANSCRIPT_TURNS
    assert turns[0].text == f"line {5}"
