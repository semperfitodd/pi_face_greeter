from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("pi_face_greeter.face_recognition")


def identify(frame: np.ndarray) -> tuple[str | None, float]:
    _ = frame
    logger.debug("Face recognition not enabled yet")
    return None, 0.0
