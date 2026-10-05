from __future__ import annotations

from pathlib import Path


class PathSecurityError(ValueError):
    pass


def resolve_under_root(root: Path, relative_or_absolute: str | Path) -> Path:
    base = root.resolve()
    candidate = Path(relative_or_absolute)
    if not candidate.is_absolute():
        candidate = base / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise PathSecurityError(f"Path escapes allowed root: {relative_or_absolute}") from exc
    return resolved


def resolve_known_face_dir(
    project_root: Path,
    face_dir: str,
    known_faces_root: Path | None = None,
) -> Path:
    faces_root = (known_faces_root or project_root / "data" / "known_faces").resolve()
    resolved = resolve_under_root(project_root.resolve(), face_dir)
    try:
        resolved.relative_to(faces_root)
    except ValueError as exc:
        raise PathSecurityError(f"face_dir must be under known_faces: {face_dir}") from exc
    return resolved
