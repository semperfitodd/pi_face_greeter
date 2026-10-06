from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from pi_face_greeter.config_loader import PROJECT_ROOT
from pi_face_greeter.people_store import slugify_name

logger = logging.getLogger("pi_face_greeter.person_memory")

MEMORY_DIR = PROJECT_ROOT / "data" / "people_memory"
MAX_FACTS = 20
MEMORY_TOPICS = ("work", "home", "likes", "family")

TOPIC_QUESTION_HINTS: dict[str, str] = {
    "work": "where they work or what they do for work",
    "home": "where they live",
    "likes": "what they like to do for fun",
    "family": "their family",
}

_EXTRACT_SYSTEM = (
    "You extract lasting facts about a person from one spoken message. "
    "Topics: work (job), home (where they live), likes (hobbies and interests), "
    "family (relatives). Ignore greetings, mood, weather, and goodbyes. "
    "Reply with one line per fact using exactly: topic: short fact "
    "(topic must be work, home, likes, or family). "
    "If there is nothing lasting to save, reply with exactly NONE."
)


@dataclass
class PersonFact:
    topic: str
    text: str


@dataclass
class PersonMemory:
    facts: list[PersonFact] = field(default_factory=list)
    last_greeted_on: str | None = None
    asked_topic_on: str | None = None

    def topics_known(self) -> set[str]:
        return {fact.topic for fact in self.facts if fact.topic in MEMORY_TOPICS}

    def all_topics_known(self) -> bool:
        return all(topic in self.topics_known() for topic in MEMORY_TOPICS)

    def first_missing_topic(self) -> str | None:
        known = self.topics_known()
        for topic in MEMORY_TOPICS:
            if topic not in known:
                return topic
        return None

    def already_greeted_today(self, today: date) -> bool:
        return self.last_greeted_on == today.isoformat()

    def can_ask_curiosity_today(self, today: date) -> bool:
        return self.asked_topic_on != today.isoformat()

    def mark_greeted_today(self, today: date) -> None:
        self.last_greeted_on = today.isoformat()

    def mark_asked_today(self, today: date) -> None:
        self.asked_topic_on = today.isoformat()

    def add_fact(self, topic: str, text: str) -> bool:
        topic = topic.strip().lower()
        text = " ".join(text.split()).strip()
        if topic not in MEMORY_TOPICS or not text or len(text) > 200:
            return False
        for existing in self.facts:
            if existing.topic == topic and existing.text.lower() == text.lower():
                return False
        if len(self.facts) >= MAX_FACTS:
            return False
        self.facts.append(PersonFact(topic=topic, text=text))
        return True

    def format_for_prompt(self, person_name: str) -> str:
        if not self.facts:
            return f"You do not have saved facts about {person_name} yet."
        lines = [f"What you remember about {person_name}:"]
        for fact in self.facts:
            lines.append(f"- {fact.topic}: {fact.text}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "facts": [{"topic": f.topic, "text": f.text} for f in self.facts],
            "last_greeted_on": self.last_greeted_on,
            "asked_topic_on": self.asked_topic_on,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PersonMemory:
        facts: list[PersonFact] = []
        for item in data.get("facts") or []:
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic", "")).strip().lower()
            text = str(item.get("text", "")).strip()
            if topic in MEMORY_TOPICS and text:
                facts.append(PersonFact(topic=topic, text=text))
        return cls(
            facts=facts[:MAX_FACTS],
            last_greeted_on=_optional_date_str(data.get("last_greeted_on")),
            asked_topic_on=_optional_date_str(data.get("asked_topic_on")),
        )


def _optional_date_str(value: Any) -> str | None:
    if value is None:
        return None
    token = str(value).strip()
    return token or None


def _memory_path(name: str) -> Path:
    slug = slugify_name(name)
    return MEMORY_DIR / f"{slug}.yaml"


def load_person_memory(name: str) -> PersonMemory:
    path = _memory_path(name)
    if not path.is_file():
        return PersonMemory()
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            return PersonMemory()
        return PersonMemory.from_dict(data)
    except Exception:
        logger.warning("Failed to load person memory for %s", name, exc_info=True)
        return PersonMemory()


def save_person_memory(name: str, memory: PersonMemory) -> None:
    path = _memory_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(memory.to_dict(), handle, default_flow_style=False, sort_keys=False)


def build_curiosity_instruction(topic: str) -> str:
    hint = TOPIC_QUESTION_HINTS.get(topic, topic)
    return (
        f"You may ask one short, friendly question about {hint}. "
        "Ask only one question in this reply, then stay natural. "
        "Do not interrogate or stack multiple personal questions."
    )


def build_memory_system_extras(
    person_name: str,
    memory: PersonMemory,
    *,
    curiosity_topic: str | None = None,
) -> str:
    parts = [memory.format_for_prompt(person_name)]
    if curiosity_topic:
        parts.append(build_curiosity_instruction(curiosity_topic))
    elif memory.all_topics_known():
        parts.append(
            "Do not ask personal questions about work, home, hobbies, or family. "
            "You already know enough about them."
        )
    return "\n\n".join(parts)


def parse_extracted_facts(raw: str) -> list[tuple[str, str]]:
    if not raw or raw.strip().upper() == "NONE":
        return []
    results: list[tuple[str, str]] = []
    for line in raw.splitlines():
        line = line.strip().lstrip("-•").strip()
        if not line or ":" not in line:
            continue
        topic, _, text = line.partition(":")
        topic = topic.strip().lower()
        text = text.strip()
        if topic in MEMORY_TOPICS and text:
            results.append((topic, text))
    return results


def merge_extracted_facts(name: str, raw: str) -> int:
    pairs = parse_extracted_facts(raw)
    if not pairs:
        return 0
    memory = load_person_memory(name)
    added = 0
    for topic, text in pairs:
        if memory.add_fact(topic, text):
            added += 1
    if added:
        save_person_memory(name, memory)
        logger.info("Saved %d fact(s) for %s", added, name)
    return added


def extract_facts_from_utterance(
    name: str,
    utterance: str,
    *,
    base_url: str,
    model: str,
    timeout: float,
) -> int:
    from pi_face_greeter import ollama_client

    utterance = utterance.strip()
    if not utterance or not name.strip():
        return 0
    messages = [
        {"role": "system", "content": _EXTRACT_SYSTEM},
        {
            "role": "user",
            "content": f"Person: {name}\nMessage: {utterance}",
        },
    ]
    try:
        raw = ollama_client.chat(
            messages,
            base_url=base_url,
            model=model,
            timeout=min(timeout, 15.0),
            max_tokens=120,
            temperature=0.0,
        )
    except Exception:
        logger.warning("Fact extraction failed for %s", name, exc_info=True)
        return 0
    return merge_extracted_facts(name, raw)
