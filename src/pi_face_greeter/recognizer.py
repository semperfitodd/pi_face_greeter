from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from pi_face_greeter.detector import FaceBox, detect_faces
from pi_face_greeter.config_loader import PROJECT_ROOT
from pi_face_greeter.path_security import PathSecurityError, resolve_known_face_dir

logger = logging.getLogger("pi_face_greeter.recognizer")

ENCODINGS_FILENAME = "encodings.npy"


@dataclass(frozen=True)
class IdentifyMiss:
    reason: str
    encodings_count: int
    tolerance: float
    best_name: str | None = None
    best_distance: float | None = None


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
        self._last_identify_miss: IdentifyMiss | None = None

    @property
    def last_identify_miss(self) -> IdentifyMiss | None:
        return self._last_identify_miss

    @property
    def enrolled_people_count(self) -> int:
        return len(self._people_by_name)

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
            try:
                person_dir = resolve_known_face_dir(root, str(face_dir))
            except PathSecurityError:
                logger.warning("Skipping %s: invalid face_dir %s", name, face_dir)
                continue
            encodings_path = person_dir / ENCODINGS_FILENAME
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

    def _record_miss(self, miss: IdentifyMiss) -> None:
        self._last_identify_miss = miss

    def identify(self, frame: np.ndarray) -> tuple[str | None, float]:
        if not self.encodings:
            self._record_miss(
                IdentifyMiss(
                    reason="no_encodings",
                    encodings_count=0,
                    tolerance=self.tolerance,
                )
            )
            return None, 0.0

        try:
            import face_recognition
        except ImportError:
            logger.warning("face_recognition not installed; cannot identify faces")
            self._record_miss(
                IdentifyMiss(
                    reason="library_missing",
                    encodings_count=len(self.encodings),
                    tolerance=self.tolerance,
                )
            )
            return None, 0.0

        encoding = encode_face(frame)
        if encoding is None:
            self._record_miss(
                IdentifyMiss(
                    reason="no_face_encoding",
                    encodings_count=len(self.encodings),
                    tolerance=self.tolerance,
                )
            )
            return None, 0.0

        distances = face_recognition.face_distance(self.encodings, encoding)
        if len(distances) == 0:
            self._record_miss(
                IdentifyMiss(
                    reason="no_distances",
                    encodings_count=len(self.encodings),
                    tolerance=self.tolerance,
                )
            )
            return None, 0.0

        best_index = int(np.argmin(distances))
        best_distance = float(distances[best_index])
        best_name = self.names[best_index]
        if best_distance > self.tolerance:
            self._record_miss(
                IdentifyMiss(
                    reason="over_tolerance",
                    encodings_count=len(self.encodings),
                    tolerance=self.tolerance,
                    best_name=best_name,
                    best_distance=best_distance,
                )
            )
            return None, 0.0

        self._last_identify_miss = None
        confidence = max(0.0, 1.0 - best_distance)
        return best_name, confidence
