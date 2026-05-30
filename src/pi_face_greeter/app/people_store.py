from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from pi_face_greeter.config_loader import PROJECT_ROOT
from pi_face_greeter.enrollment import slugify_name

logger = logging.getLogger("pi_face_greeter.people_store")

DEFAULT_PEOPLE_PATH = PROJECT_ROOT / "config" / "people.yaml"
DEFAULT_KNOWN_FACES_DIR = PROJECT_ROOT / "data" / "known_faces"


class PeopleStoreError(Exception):
    pass


class PersonNotFoundError(PeopleStoreError):
    pass


class PersonAlreadyExistsError(PeopleStoreError):
    pass


def _load_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"people": []}
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    data.setdefault("people", [])
    return data


def _save_data(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, default_flow_style=False, sort_keys=False)


def list_people(path: Path | None = None) -> list[dict[str, Any]]:
    people_path = path or DEFAULT_PEOPLE_PATH
    data = _load_data(people_path)
    return list(data.get("people", []))


def _relative_face_dir(face_dir: Path) -> str:
    try:
        return face_dir.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return face_dir.as_posix()


def add_person(
    name: str,
    path: Path | None = None,
    known_faces_dir: Path | None = None,
) -> dict[str, Any]:
    people_path = path or DEFAULT_PEOPLE_PATH
    faces_root = known_faces_dir or DEFAULT_KNOWN_FACES_DIR
    trimmed = name.strip()
    if not trimmed:
        raise PeopleStoreError("Name must not be empty")

    slug = slugify_name(trimmed)
    data = _load_data(people_path)
    people: list[dict[str, Any]] = data.setdefault("people", [])

    for person in people:
        if person.get("name", "").strip().lower() == trimmed.lower():
            raise PersonAlreadyExistsError(f"Person already exists: {trimmed}")

    person_dir = faces_root / slug
    person_dir.mkdir(parents=True, exist_ok=True)
    relative_dir = _relative_face_dir(person_dir)

    entry = {"name": trimmed, "face_dir": relative_dir}
    people.append(entry)
    _save_data(people_path, data)
    logger.info("Added person %s at %s", trimmed, relative_dir)
    return entry


def update_person_name(
    old_name: str,
    new_name: str,
    path: Path | None = None,
) -> dict[str, Any]:
    people_path = path or DEFAULT_PEOPLE_PATH
    trimmed = new_name.strip()
    if not trimmed:
        raise PeopleStoreError("Name must not be empty")

    data = _load_data(people_path)
    people: list[dict[str, Any]] = data.setdefault("people", [])

    target: dict[str, Any] | None = None
    for person in people:
        if person.get("name") == old_name:
            target = person
            break

    if target is None:
        raise PersonNotFoundError(f"Person not found: {old_name}")

    for person in people:
        if person is not target and person.get("name", "").strip().lower() == trimmed.lower():
            raise PersonAlreadyExistsError(f"Person already exists: {trimmed}")

    target["name"] = trimmed
    _save_data(people_path, data)
    logger.info("Renamed person %s to %s", old_name, trimmed)
    return target


def delete_person(name: str, path: Path | None = None) -> None:
    people_path = path or DEFAULT_PEOPLE_PATH
    data = _load_data(people_path)
    people: list[dict[str, Any]] = data.setdefault("people", [])

    remaining = [person for person in people if person.get("name") != name]
    if len(remaining) == len(people):
        raise PersonNotFoundError(f"Person not found: {name}")

    data["people"] = remaining
    _save_data(people_path, data)
    logger.info("Deleted person %s", name)


def stub_enroll_person(
    name: str,
    path: Path | None = None,
    known_faces_dir: Path | None = None,
) -> dict[str, Any]:
    """Record a person without capturing photos (stub for future enrollment)."""
    return add_person(name, path=path, known_faces_dir=known_faces_dir)
