from __future__ import annotations

from unittest.mock import MagicMock, patch

from pi_face_greeter.greet_pipeline import run_greeting_interaction


def test_run_greeting_interaction_speaks_when_conversation_disabled() -> None:
    tts_cfg = {"enabled": True, "ask_how_are_you": True}
    with patch("pi_face_greeter.greet_pipeline.speak_from_config") as mock_speak:
        result = run_greeting_interaction(
            "Todd",
            tts_cfg=tts_cfg,
            ollama_cfg={"enabled": False},
            conversation_cfg={"enabled": False},
        )

    assert "Todd" in result
    mock_speak.assert_called_once()
    spoken_text = mock_speak.call_args[0][0]
    assert "Todd" in spoken_text


def test_run_greeting_interaction_uses_conversation_when_enabled() -> None:
    tts_cfg = {"enabled": True}
    with (
        patch("pi_face_greeter.greet_pipeline.run_conversation") as mock_conversation,
        patch("pi_face_greeter.greet_pipeline.speak_from_config") as mock_speak,
    ):
        result = run_greeting_interaction(
            "Todd",
            tts_cfg=tts_cfg,
            ollama_cfg={"enabled": True},
            conversation_cfg={"enabled": True},
            stt_cfg={"enabled": True},
            assistant_cfg={"name": "Freyja"},
            mic=MagicMock(),
        )

    assert result == "Hi, Todd. How are you?"
    mock_conversation.assert_called_once()
    mock_speak.assert_not_called()
