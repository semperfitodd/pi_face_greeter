from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from pi_face_greeter.app.detector import get_cascade_classifier
from pi_face_greeter.camera import create_camera
from pi_face_greeter.config_loader import PROJECT_ROOT

logger = logging.getLogger("pi_face_greeter.enrollment")

PEOPLE_YAML = PROJECT_ROOT / "config" / "people.yaml"
MIN_IMAGE_BYTES = 1000
MIN_FACE_WIDTH = 80


def slugify_name(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if not slug:
        raise ValueError("Name must contain at least one letter or number")
    return slug


def _validate_frame(frame: np.ndarray, output_path: Path) -> None:
    if output_path.stat().st_size < MIN_IMAGE_BYTES:
        raise RuntimeError(f"Captured image is too small: {output_path}")

    height, width = frame.shape[:2]
    if width < MIN_FACE_WIDTH or height < MIN_FACE_WIDTH:
        raise RuntimeError(f"Captured image resolution too low: {width}x{height}")

    detector = get_cascade_classifier()
    if detector is None:
        logger.warning("OpenCV or Haar cascade unavailable; skipping face count check")
        return

    import cv2

    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
    face_count = len(faces)
    if face_count != 1:
        raise RuntimeError(
            f"Expected exactly one face in frame, detected {face_count}. "
            "Adjust lighting or position and retry."
        )


def register_person(name: str, face_dir: Path) -> None:
    if not PEOPLE_YAML.exists():
        data: dict[str, Any] = {"people": []}
    else:
        with PEOPLE_YAML.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {"people": []}

    people: list[dict[str, Any]] = data.setdefault("people", [])
    relative_dir = face_dir.relative_to(PROJECT_ROOT).as_posix()

    for person in people:
        if person.get("name") == name:
            person["face_dir"] = relative_dir
            break
    else:
        people.append({"name": name, "face_dir": relative_dir})

    with PEOPLE_YAML.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, default_flow_style=False, sort_keys=False)


def enroll_person(
    name: str,
    camera_cfg: dict[str, Any],
    enrollment_cfg: dict[str, Any],
    count: int | None = None,
) -> Path:
    slug = slugify_name(name)
    capture_count = count if count is not None else int(enrollment_cfg.get("capture_count", 5))
    delay_seconds = float(enrollment_cfg.get("delay_seconds", 2))
    known_faces_dir = Path(enrollment_cfg.get("known_faces_dir", "data/known_faces"))
    person_dir = known_faces_dir / slug
    person_dir.mkdir(parents=True, exist_ok=True)

    if capture_count < 1:
        raise ValueError("capture_count must be at least 1")

    print(f"Enrolling {name}: capture {capture_count} photos ({delay_seconds:.0f}s apart)...")

    camera = create_camera(camera_cfg)
    saved_paths: list[Path] = []

    try:
        for index in range(1, capture_count + 1):
            frame = camera.capture_frame()
            output_path = person_dir / f"{index:03d}.jpg"
            camera.save_frame(frame, output_path)
            _validate_frame(frame, output_path)
            saved_paths.append(output_path)
            logger.info("Enrolled photo %s for %s", output_path.name, name)

            if index < capture_count:
                time.sleep(delay_seconds)
    finally:
        camera.close()

    register_person(name, person_dir)
    return person_dir
