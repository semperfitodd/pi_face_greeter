from __future__ import annotations

import glob
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger("pi_face_greeter.detector")

FaceBox = tuple[int, int, int, int]
CASCADE_FILENAME = "haarcascade_frontalface_default.xml"

_cascade_classifier: Any | None = None
_cascade_unavailable_logged = False


def _find_cascade_path() -> Path | None:
    try:
        import cv2
    except ImportError:
        return None

    cv2_data = getattr(cv2, "data", None)
    if cv2_data is not None:
        haarcascades = getattr(cv2_data, "haarcascades", None)
        if haarcascades:
            path = Path(haarcascades) / CASCADE_FILENAME
            if path.is_file():
                return path

    candidates: list[Path] = [
        Path("/usr/share/opencv4/haarcascades") / CASCADE_FILENAME,
    ]
    for pattern in ("/usr/share/opencv*/haarcascades", "/usr/local/share/opencv*/haarcascades"):
        for directory in glob.glob(pattern):
            candidates.append(Path(directory) / CASCADE_FILENAME)

    for path in candidates:
        if path.is_file():
            return path
    return None


def get_cascade_classifier() -> Any | None:
    global _cascade_classifier, _cascade_unavailable_logged

    if _cascade_classifier is not None:
        return _cascade_classifier

    try:
        import cv2
    except ImportError:
        if not _cascade_unavailable_logged:
            logger.debug("OpenCV not available; skipping face detection")
            _cascade_unavailable_logged = True
        return None

    cascade_path = _find_cascade_path()
    if cascade_path is None:
        if not _cascade_unavailable_logged:
            logger.warning("Haar cascade not found; face detection disabled")
            _cascade_unavailable_logged = True
        return None

    detector = cv2.CascadeClassifier(str(cascade_path))
    if detector.empty():
        if not _cascade_unavailable_logged:
            logger.warning(
                "Haar cascade unavailable at %s; face detection disabled",
                cascade_path,
            )
            _cascade_unavailable_logged = True
        return None

    _cascade_classifier = detector
    return _cascade_classifier


def detect_faces(frame: np.ndarray) -> list[FaceBox]:
    detector = get_cascade_classifier()
    if detector is None:
        return []

    import cv2

    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
    return [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]
