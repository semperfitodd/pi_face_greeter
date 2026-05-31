from __future__ import annotations

import glob
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pi_face_greeter.config_loader import PROJECT_ROOT

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger("pi_face_greeter.detector")

FaceBox = tuple[int, int, int, int]
CASCADE_FILENAME = "haarcascade_frontalface_default.xml"
BUNDLED_CASCADE = PROJECT_ROOT / "data" / "haarcascades" / CASCADE_FILENAME

DEFAULT_DETECTION_CFG: dict[str, float | int | bool] = {
    "scale_factor": 1.05,
    "min_neighbors": 4,
    "min_face_ratio": 0.08,
    "use_clahe": True,
}

_cascade_classifier: Any | None = None
_cascade_load_logged = False


def _find_cascade_path() -> Path | None:
    if BUNDLED_CASCADE.is_file():
        return BUNDLED_CASCADE

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
    global _cascade_classifier, _cascade_load_logged

    if _cascade_classifier is not None:
        return _cascade_classifier

    try:
        import cv2
    except ImportError:
        if not _cascade_load_logged:
            logger.warning("OpenCV not available; face detection disabled")
            _cascade_load_logged = True
        return None

    cascade_path = _find_cascade_path()
    if cascade_path is None:
        if not _cascade_load_logged:
            logger.warning("Haar cascade not found; face detection disabled")
            _cascade_load_logged = True
        return None

    detector = cv2.CascadeClassifier(str(cascade_path))
    if detector.empty():
        if not _cascade_load_logged:
            logger.warning(
                "Haar cascade unavailable at %s; face detection disabled",
                cascade_path,
            )
            _cascade_load_logged = True
        return None

    _cascade_classifier = detector
    if not _cascade_load_logged:
        logger.info("Face detection enabled using cascade at %s", cascade_path)
        _cascade_load_logged = True
    return _cascade_classifier


def _prepare_gray(frame: np.ndarray, use_clahe: bool) -> Any:
    import cv2

    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    if not use_clahe:
        return gray

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def detect_faces(
    frame: np.ndarray,
    detection_cfg: dict[str, Any] | None = None,
) -> list[FaceBox]:
    detector = get_cascade_classifier()
    if detector is None:
        return []

    cfg = {**DEFAULT_DETECTION_CFG, **(detection_cfg or {})}
    scale_factor = float(cfg["scale_factor"])
    min_neighbors = int(cfg["min_neighbors"])
    min_face_ratio = float(cfg["min_face_ratio"])
    use_clahe = bool(cfg["use_clahe"])

    height, width = frame.shape[:2]
    min_edge = max(24, int(min(width, height) * min_face_ratio))

    gray = _prepare_gray(frame, use_clahe=use_clahe)
    faces = detector.detectMultiScale(
        gray,
        scaleFactor=scale_factor,
        minNeighbors=min_neighbors,
        minSize=(min_edge, min_edge),
        flags=0,
    )
    boxes = [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "detect_faces frame shape=%s dtype=%s brightness min=%.1f mean=%.1f max=%.1f "
            "params scale_factor=%.2f min_neighbors=%d min_size=%d use_clahe=%s "
            "faces=%d boxes=%s",
            frame.shape,
            frame.dtype,
            float(frame.min()),
            float(frame.mean()),
            float(frame.max()),
            scale_factor,
            min_neighbors,
            min_edge,
            use_clahe,
            len(boxes),
            boxes,
        )

    return boxes
