from __future__ import annotations

from dataclasses import dataclass

MAX_TRANSCRIPT_TURNS = 50

USER_COLOR = "0.95,0.85,0.55,1"
ASSISTANT_COLOR = "0.1,0.9,1.0,1"


@dataclass
class TranscriptTurn:
    speaker: str
    text: str


def _escape(text: str) -> str:
    import html

    return html.escape(text, quote=False)


def speaker_is_assistant(speaker: str, assistant_name: str) -> bool:
    return speaker.strip().lower() == assistant_name.strip().lower()


def append_or_update_turn(
    turns: list[TranscriptTurn],
    speaker: str,
    text: str,
    *,
    replace_last: bool,
) -> None:
    if replace_last and turns and turns[-1].speaker == speaker:
        turns[-1].text = text
    else:
        turns.append(TranscriptTurn(speaker=speaker, text=text))
    while len(turns) > MAX_TRANSCRIPT_TURNS:
        turns.pop(0)


def format_turn_markup(turn: TranscriptTurn, assistant_name: str) -> str:
    color = ASSISTANT_COLOR if speaker_is_assistant(turn.speaker, assistant_name) else USER_COLOR
    name = _escape(turn.speaker)
    body = _escape(turn.text)
    return f"[color={color}][b]{name}[/b][/color]\n{body}"


def format_transcript_markup(turns: list[TranscriptTurn], assistant_name: str) -> str:
    if not turns:
        return ""
    blocks = [format_turn_markup(turn, assistant_name) for turn in turns]
    return "\n\n".join(blocks)
