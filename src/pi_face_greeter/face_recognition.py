from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from pi_face_greeter.app.people_store import list_people
from pi_face_greeter.app.recognizer import FaceRecognizer
from pi_face_greeter.config_loader import PROJECT_ROOT, load_config

logger = logging.getLogger("pi_face_greeter.face_recognition")

_recognizer: FaceRecognizer | None = None


def configure(recognition_cfg: dict[str, Any] | None = None) -> FaceRecognizer:
    global _recognizer

    cfg = recognition_cfg or {}
    tolerance = float(cfg.get("tolerance", 0.6))
    _recognizer = FaceRecognizer(tolerance=tolerance)
    _recognizer.load(list_people(), project_root=PROJECT_ROOT)
    return _recognizer


def reload() -> None:
    if _recognizer is None:
        configure()
        return

    _recognizer.load(list_people(), project_root=PROJECT_ROOT)


def get_recognizer() -> FaceRecognizer | None:
    return _recognizer


def get_person_greeting(name: str | None) -> str | None:
    if _recognizer is None or not name:
        return None
    person = _recognizer.get_person(name)
    if not person:
        return None
    greeting = person.get("greeting")
    if isinstance(greeting, str) and greeting.strip():
        return greeting.strip()
    return None


def identify(frame: np.ndarray) -> tuple[str | None, float]:
    if _recognizer is None:
        logger.debug("Face recognizer not configured")
        return None, 0.0
    return _recognizer.identify(frame)


def ensure_configured() -> None:
    if _recognizer is None:
        config = load_config()
        configure(config.get("recognition", {}))
