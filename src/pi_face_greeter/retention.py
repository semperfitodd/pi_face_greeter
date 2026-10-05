from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("pi_face_greeter.retention")


def prune_jpeg_directory(directory: Path | str, max_files: int) -> None:
    if max_files <= 0:
        return

    root = Path(directory)
    if not root.is_dir():
        return

    files = sorted(
        (path for path in root.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg"}),
        key=lambda path: path.stat().st_mtime,
    )
    excess = len(files) - max_files
    if excess <= 0:
        return

    for path in files[:excess]:
        try:
            path.unlink()
            logger.debug("Pruned old capture: %s", path)
        except OSError:
            logger.warning("Failed to prune capture %s", path, exc_info=True)
