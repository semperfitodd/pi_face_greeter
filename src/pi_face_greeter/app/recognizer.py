from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from pi_face_greeter.app.detector import FaceBox, detect_faces
from pi_face_greeter.config_loader import PROJECT_ROOT

logger = logging.getLogger("pi_face_greeter.recognizer")

ENCODINGS_FILENAME = "encodings.npy"


def _largest_box(boxes: list[FaceBox]) -> FaceBox | None:
    if not boxes:
        return None
    return max(boxes, key=lambda box: box[2] * box[3])


def _box_to_location(box: FaceBox) -> tuple[int, int, int, int]:
    x, y, w, h = box
    return (y, x + w, y + h, x)


def encode_face(frame: np.ndarray, box: FaceBox | None = None) -> np.ndarray | None:
    try:
        import face_recognition
    except ImportError:
        logger.warning("face_recognition not installed; cannot encode faces")
        return None

    target_box = box or _largest_box(detect_faces(frame))
    if target_box is None:
        return None

    locations = [_box_to_location(target_box)]
    encodings = face_recognition.face_encodings(frame, known_face_locations=locations)
    if not encodings:
        return None
    return np.asarray(encodings[0], dtype=np.float64)


class FaceRecognizer:
    def __init__(self, tolerance: float = 0.6) -> None:
        self.tolerance = tolerance
        self.names: list[str] = []
        self.encodings: list[np.ndarray] = []
        self._people_by_name: dict[str, dict[str, Any]] = {}

    def load(self, people: list[dict[str, Any]], project_root: Path | None = None) -> None:
        root = project_root or PROJECT_ROOT
        self.names = []
        self.encodings = []
        self._people_by_name = {}

        for person in people:
            name = person.get("name")
            face_dir = person.get("face_dir")
            if not name or not face_dir:
                continue

            self._people_by_name[name] = person
            encodings_path = root / face_dir / ENCODINGS_FILENAME
            if not encodings_path.is_file():
                logger.warning("No encodings for %s at %s", name, encodings_path)
                continue

            stored = np.load(encodings_path)
            if stored.ndim == 1:
                stored = stored.reshape(1, -1)

            for encoding in stored:
                self.names.append(name)
                self.encodings.append(np.asarray(encoding, dtype=np.float64))

        logger.info(
            "Loaded %d face encoding(s) for %d people",
            len(self.encodings),
            len({name for name in self.names}),
        )

    def get_person(self, name: str | None) -> dict[str, Any] | None:
        if not name:
            return None
        return self._people_by_name.get(name)

    def identify(self, frame: np.ndarray) -> tuple[str | None, float]:
        if not self.encodings:
            return None, 0.0

        try:
            import face_recognition
        except ImportError:
            logger.warning("face_recognition not installed; cannot identify faces")
            return None, 0.0

        encoding = encode_face(frame)
        if encoding is None:
            return None, 0.0

        distances = face_recognition.face_distance(self.encodings, encoding)
        if len(distances) == 0:
            return None, 0.0

        best_index = int(np.argmin(distances))
        best_distance = float(distances[best_index])
        if best_distance > self.tolerance:
            return None, 0.0

        confidence = max(0.0, 1.0 - best_distance)
        return self.names[best_index], confidence
