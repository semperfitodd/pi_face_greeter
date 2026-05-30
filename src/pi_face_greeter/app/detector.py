from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger("pi_face_greeter.detector")

FaceBox = tuple[int, int, int, int]


def detect_faces(frame: np.ndarray) -> list[FaceBox]:
    try:
        import cv2
    except ImportError:
        logger.debug("OpenCV not available; skipping face detection")
        return []

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    if detector.empty():
        logger.warning("Haar cascade unavailable; skipping face detection")
        return []

    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
    return [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]
