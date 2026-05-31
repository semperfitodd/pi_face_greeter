from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pi_face_greeter.app.people_store import (
    PersonAlreadyExistsError,
    PersonNotFoundError,
    add_person,
    delete_person,
    list_people,
    update_person_name,
    upsert_person,
)


@pytest.fixture
def people_env(tmp_path: Path):
    people_path = tmp_path / "people.yaml"
    faces_dir = tmp_path / "known_faces"
    return people_path, faces_dir


def test_list_people_empty(people_env) -> None:
    people_path, _faces_dir = people_env
    assert list_people(people_path) == []


def test_add_and_list_person(people_env) -> None:
    people_path, faces_dir = people_env
    entry = add_person("Todd", path=people_path, known_faces_dir=faces_dir)

    assert entry["name"] == "Todd"
    assert entry["face_dir"].endswith("known_faces/todd")
    assert (faces_dir / "todd").is_dir()

    people = list_people(people_path)
    assert len(people) == 1
    assert people[0]["name"] == "Todd"


def test_add_duplicate_raises(people_env) -> None:
    people_path, faces_dir = people_env
    add_person("Todd", path=people_path, known_faces_dir=faces_dir)

    with pytest.raises(PersonAlreadyExistsError):
        add_person("todd", path=people_path, known_faces_dir=faces_dir)


def test_update_person_name(people_env) -> None:
    people_path, faces_dir = people_env
    add_person("Todd", path=people_path, known_faces_dir=faces_dir)

    updated = update_person_name("Todd", "Theodore", path=people_path)
    assert updated["name"] == "Theodore"
    assert list_people(people_path)[0]["name"] == "Theodore"


def test_delete_person(people_env) -> None:
    people_path, faces_dir = people_env
    add_person("Todd", path=people_path, known_faces_dir=faces_dir)

    delete_person("Todd", path=people_path)
    assert list_people(people_path) == []


def test_delete_missing_raises(people_env) -> None:
    people_path, _faces_dir = people_env
    with pytest.raises(PersonNotFoundError):
        delete_person("Missing", path=people_path)


def test_upsert_person_adds_and_updates(people_env, tmp_path: Path, monkeypatch) -> None:
    people_path, faces_dir = people_env
    monkeypatch.setattr("pi_face_greeter.app.people_store.PROJECT_ROOT", tmp_path)

    face_dir = faces_dir / "todd"
    face_dir.mkdir(parents=True)

    entry = upsert_person("Todd", face_dir, path=people_path)
    assert entry["name"] == "Todd"
    assert entry["face_dir"].endswith("known_faces/todd")

    updated_dir = faces_dir / "todd-v2"
    updated_dir.mkdir(parents=True)
    updated = upsert_person("Todd", updated_dir, path=people_path)
    assert updated["face_dir"].endswith("known_faces/todd-v2")
    assert len(list_people(people_path)) == 1
