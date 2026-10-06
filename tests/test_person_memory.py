from __future__ import annotations

from datetime import date, datetime

from pi_face_greeter.conversation import build_opener, build_system_prompt
from pi_face_greeter.person_memory import (
    PersonFact,
    PersonMemory,
    build_memory_system_extras,
    load_person_memory,
    merge_extracted_facts,
    parse_extracted_facts,
)


def test_build_opener_asks_how_are_you_first_time_today() -> None:
    memory = PersonMemory()
    assert build_opener("Todd", None, memory=memory) == "Hi, Todd. How are you?"


def test_build_opener_skips_question_same_day() -> None:
    memory = PersonMemory(last_greeted_on="2026-10-06")
    moment = datetime(2026, 10, 6, 15, 0, 0)
    assert build_opener("Todd", None, memory=memory, now=moment) == "Hi, Todd."


def test_merge_extracted_facts_dedupes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("pi_face_greeter.person_memory.MEMORY_DIR", tmp_path)
    raw = "work: CEO\nlikes: baseball\nwork: CEO"
    added = merge_extracted_facts("Todd", raw)
    assert added == 2
    memory = load_person_memory("Todd")
    assert len(memory.facts) == 2


def test_parse_extracted_facts_ignores_none() -> None:
    assert parse_extracted_facts("NONE") == []


def test_system_prompt_includes_facts_not_other_person(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("pi_face_greeter.person_memory.MEMORY_DIR", tmp_path)
    merge_extracted_facts("Todd", "likes: baseball")
    todd_memory = load_person_memory("Todd")
    prompt = build_system_prompt(
        "Todd",
        assistant_cfg={"name": "Freyja"},
        now=datetime(2026, 10, 6, 9, 0, 0),
        memory=todd_memory,
    )
    assert "baseball" in prompt
    kai_memory = load_person_memory("Kai")
    kai_prompt = build_system_prompt(
        "Kai",
        assistant_cfg={"name": "Freyja"},
        memory=kai_memory,
    )
    assert "baseball" not in kai_prompt


def test_curiosity_instruction_when_work_missing() -> None:
    memory = PersonMemory()
    extras = build_memory_system_extras("Todd", memory, curiosity_topic="work")
    assert "work" in extras.lower()


def test_curiosity_blocked_when_asked_today() -> None:
    memory = PersonMemory(asked_topic_on="2026-10-06")
    assert memory.can_ask_curiosity_today(date(2026, 10, 6)) is False


def test_build_system_prompt_allows_work_question_when_missing() -> None:
    memory = PersonMemory()
    prompt = build_system_prompt(
        "Todd",
        assistant_cfg={"name": "Freyja"},
        memory=memory,
        curiosity_topic="work",
    )
    assert "one short" in prompt.lower()


def test_build_system_prompt_no_personal_questions_when_full() -> None:
    memory = PersonMemory(
        facts=[
            PersonFact(topic="work", text="CEO"),
            PersonFact(topic="home", text="Austin"),
            PersonFact(topic="likes", text="baseball"),
            PersonFact(topic="family", text="two kids"),
        ]
    )
    prompt = build_system_prompt(
        "Todd",
        assistant_cfg={"name": "Freyja"},
        memory=memory,
    )
    assert "Do not ask personal questions" in prompt
