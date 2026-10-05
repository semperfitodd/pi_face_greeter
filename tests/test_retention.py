from __future__ import annotations

from pathlib import Path

from pi_face_greeter.retention import prune_jpeg_directory


def test_prune_jpeg_directory_removes_oldest(tmp_path: Path) -> None:
    for index in range(5):
        path = tmp_path / f"frame_{index:03d}.jpg"
        path.write_bytes(b"jpeg")
        path.touch()

    prune_jpeg_directory(tmp_path, max_files=2)
    remaining = sorted(tmp_path.glob("*.jpg"))
    assert len(remaining) == 2
