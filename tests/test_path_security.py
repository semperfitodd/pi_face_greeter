from __future__ import annotations

from pathlib import Path

import pytest

from pi_face_greeter.path_security import PathSecurityError, resolve_known_face_dir


def test_resolve_known_face_dir_accepts_relative_path(tmp_path: Path) -> None:
    faces = tmp_path / "data" / "known_faces" / "todd"
    faces.mkdir(parents=True)
    resolved = resolve_known_face_dir(tmp_path, "data/known_faces/todd")
    assert resolved == faces.resolve()


def test_resolve_known_face_dir_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(PathSecurityError):
        resolve_known_face_dir(tmp_path, "/etc/passwd")
