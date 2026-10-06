from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from pi_face_greeter.conversation import (
    OllamaConfigError,
    _build_prompt,
    _sanitize,
    build_opener,
    build_system_prompt,
    conversation_enabled,
    generate_greeting,
    iter_sentences_from_tokens,
    iter_speech_chunks_from_sentences,
    run_conversation,
    validate_ollama_base_url,
)


def test_generate_greeting_disabled_returns_fallback() -> None:
    fallback = "Hey Todd, good to see you."
    result = generate_greeting(
        "Todd",
        ollama_cfg={"enabled": False},
        fallback_text=fallback,
    )
    assert result == fallback


def test_generate_greeting_success_returns_sanitized_text() -> None:
    with patch(
        "pi_face_greeter.ollama_client.generate",
        return_value=' "Hello Todd! Great to see you this morning." ',
    ):
        result = generate_greeting(
            "Todd",
            ollama_cfg={
                "enabled": True,
                "base_url": "http://localhost:11434",
                "model": "llama3.2:1b",
            },
            fallback_text="fallback",
            now=datetime(2026, 5, 31, 9, 0, 0),
        )
    assert result == "Hello Todd! Great to see you this morning."


def test_generate_greeting_error_returns_fallback() -> None:
    with patch(
        "pi_face_greeter.ollama_client.generate",
        side_effect=RuntimeError("timeout"),
    ):
        result = generate_greeting(
            "Todd",
            ollama_cfg={"enabled": True},
            fallback_text="fallback",
        )
    assert result == "fallback"


def test_build_prompt_includes_name_and_time_of_day() -> None:
    prompt = _build_prompt("Todd", "morning")
    assert "Todd" in prompt
    assert "morning" in prompt


def test_build_prompt_unknown_visitor() -> None:
    prompt = _build_prompt(None, "evening")
    assert "visitor" in prompt
    assert "evening" in prompt


def test_build_opener_known_name() -> None:
    assert build_opener("Todd", None) == "Hi, Todd. How are you?"


def test_build_opener_custom_greeting() -> None:
    assert build_opener("Todd", "Welcome home.") == "Welcome home."


def test_build_system_prompt_includes_freyja_and_name() -> None:
    prompt = build_system_prompt(
        "Todd",
        assistant_cfg={"name": "Freyja"},
        now=datetime(2026, 5, 31, 9, 0, 0),
    )
    assert "Freyja" in prompt
    assert "Todd" in prompt
    assert "morning" in prompt


def test_iter_sentences_from_tokens_splits_on_punctuation() -> None:
    tokens = iter(["Hello", " Todd", ". ", "How are you", "?"])
    sentences = list(iter_sentences_from_tokens(tokens))
    assert sentences == ["Hello Todd.", "How are you?"]


def test_iter_speech_chunks_batches_after_first_sentence() -> None:
    sentences = iter(["One.", "Two.", "Three.", "Four."])
    chunks = list(iter_speech_chunks_from_sentences(sentences))
    assert chunks == [
        ("One.", ["One."]),
        ("Two. Three.", ["Two.", "Three."]),
        ("Four.", ["Four."]),
    ]


def test_conversation_enabled_requires_both_flags() -> None:
    assert conversation_enabled({"enabled": True}, {"enabled": True}) is True
    assert conversation_enabled({"enabled": True}, {"enabled": False}) is False


def test_run_conversation_speaks_opener_only_when_disabled() -> None:
    with patch("pi_face_greeter.conversation.speak_from_config") as mock_speak:
        run_conversation(
            "Todd",
            "Hi, Todd. How are you?",
            mic=None,
            tts_cfg={"enabled": True},
            stt_cfg={"enabled": True},
            ollama_cfg={"enabled": False},
            conversation_cfg={"enabled": True},
            assistant_cfg={"name": "Freyja"},
        )
    mock_speak.assert_called_once_with("Hi, Todd. How are you?", {"enabled": True})


def test_run_conversation_stops_on_empty_transcript() -> None:
    from pi_face_greeter.stt import ListenOutcome

    mic = MagicMock()
    statuses: list[str] = []
    session_events: list[str] = []
    with (
        patch("pi_face_greeter.conversation.speak_from_config") as mock_speak,
        patch(
            "pi_face_greeter.conversation.listen_from_config",
            return_value=ListenOutcome(None, peak_vad=0.08, peak_rms=310.0, noise_floor=40.0),
        ),
        patch("pi_face_greeter.conversation._speak_streamed_reply") as mock_stream,
        patch("pi_face_greeter.conversation.play_chime"),
        patch("pi_face_greeter.conversation.time.sleep"),
        patch("pi_face_greeter.conversation.log_event", side_effect=session_events.append),
    ):
        run_conversation(
            "Todd",
            "Hi, Todd. How are you?",
            mic=mic,
            tts_cfg={"enabled": True},
            stt_cfg={"enabled": True},
            ollama_cfg={"enabled": True, "base_url": "http://localhost:11434", "model": "x"},
            conversation_cfg={"enabled": True, "listen_chime": False},
            assistant_cfg={"name": "Freyja"},
            on_status=statuses.append,
        )

    mock_stream.assert_not_called()
    assert mock_speak.call_count == 1
    assert any("Didn't catch that (vad 0.08, level 310)" in s for s in statuses)
    assert "listen start" in session_events
    assert any("listen missed" in event and "vad=0.08" in event for event in session_events)
    assert "conversation ended: no speech" in session_events


def test_run_conversation_logs_heard_utterance_to_session() -> None:
    from pi_face_greeter.stt import ListenOutcome

    mic = MagicMock()
    session_events: list[str] = []
    with (
        patch("pi_face_greeter.conversation.speak_from_config"),
        patch(
            "pi_face_greeter.conversation.listen_from_config",
            return_value=ListenOutcome("I'm good"),
        ),
        patch(
            "pi_face_greeter.conversation._speak_streamed_reply",
            return_value="Glad to hear it.",
        ),
        patch("pi_face_greeter.conversation.play_chime"),
        patch("pi_face_greeter.conversation.time.sleep"),
        patch("pi_face_greeter.conversation.log_event", side_effect=session_events.append),
    ):
        run_conversation(
            "Todd",
            "Hi, Todd. How are you?",
            mic=mic,
            tts_cfg={"enabled": True},
            stt_cfg={"enabled": True},
            ollama_cfg={"enabled": True, "base_url": "http://localhost:11434", "model": "x"},
            conversation_cfg={"enabled": True, "listen_chime": False},
            assistant_cfg={"name": "Freyja"},
        )

    assert "listen heard: I'm good" in session_events
    assert any(event.startswith("speak Freyja:") for event in session_events)


def test_run_conversation_pauses_mic_for_chime() -> None:
    mic = MagicMock()
    with (
        patch("pi_face_greeter.conversation.speak_from_config"),
        patch(
            "pi_face_greeter.conversation.listen_from_config",
            return_value=__import__("pi_face_greeter.stt", fromlist=["ListenOutcome"]).ListenOutcome(),
        ),
        patch("pi_face_greeter.conversation.play_chime"),
        patch("pi_face_greeter.conversation.time.sleep"),
    ):
        run_conversation(
            "Todd",
            "Hi, Todd. How are you?",
            mic=mic,
            tts_cfg={"enabled": True},
            stt_cfg={"enabled": True},
            ollama_cfg={"enabled": True, "base_url": "http://localhost:11434", "model": "x"},
            conversation_cfg={"enabled": True, "listen_chime": True},
            assistant_cfg={"name": "Freyja"},
        )

    mic.pause.assert_called()
    mic.resume.assert_called()


def test_run_conversation_emits_transcript_for_user_and_assistant() -> None:
    mic = MagicMock()
    transcript: list[tuple[str, str, bool]] = []
    with (
        patch("pi_face_greeter.conversation.speak_from_config"),
        patch(
            "pi_face_greeter.conversation.listen_from_config",
            return_value=__import__("pi_face_greeter.stt", fromlist=["ListenOutcome"]).ListenOutcome(
                "I'm good"
            ),
        ),
        patch(
            "pi_face_greeter.conversation._speak_streamed_reply",
            return_value="Glad to hear it.",
        ),
        patch("pi_face_greeter.conversation.play_chime"),
        patch("pi_face_greeter.conversation.time.sleep"),
    ):
        run_conversation(
            "Todd",
            "Hi, Todd. How are you?",
            mic=mic,
            tts_cfg={"enabled": True},
            stt_cfg={"enabled": True},
            ollama_cfg={"enabled": True, "base_url": "http://localhost:11434", "model": "x"},
            conversation_cfg={"enabled": True, "listen_chime": False},
            assistant_cfg={"name": "Freyja"},
            on_transcript=lambda speaker, text, replace: transcript.append((speaker, text, replace)),
        )

    assert ("Freyja", "Hi, Todd. How are you?", False) in transcript
    assert ("Todd", "I'm good", False) in transcript


def test_warmup_ollama_skips_when_disabled() -> None:
    from pi_face_greeter.conversation import warmup_ollama

    with patch("pi_face_greeter.ollama_client.warmup") as mock_warmup:
        warmup_ollama({"enabled": False})
    mock_warmup.assert_not_called()


def test_warmup_ollama_loads_model_when_enabled() -> None:
    from pi_face_greeter.conversation import warmup_ollama

    with patch("pi_face_greeter.ollama_client.warmup") as mock_warmup:
        warmup_ollama({"enabled": True, "model": "llama3.2:1b"})
    mock_warmup.assert_called_once()


def test_sanitize_strips_quotes_and_limits_sentences() -> None:
    text = '"Hello there. How are you? Nice to see you again."'
    assert _sanitize(text) == "Hello there. How are you?"


def test_validate_ollama_base_url_accepts_localhost() -> None:
    assert validate_ollama_base_url("http://localhost:11434") == "http://localhost:11434"
    assert validate_ollama_base_url("http://127.0.0.1") == "http://127.0.0.1:11434"


def test_validate_ollama_base_url_rejects_remote() -> None:
    with pytest.raises(OllamaConfigError):
        validate_ollama_base_url("http://192.168.1.50:11434")
