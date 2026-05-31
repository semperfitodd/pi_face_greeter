from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from pi_face_greeter.app.detector import detect_faces
from pi_face_greeter.app.recognizer import ENCODINGS_FILENAME, encode_face
from pi_face_greeter.camera import create_camera
from pi_face_greeter.config_loader import PROJECT_ROOT

logger = logging.getLogger("pi_face_greeter.enrollment")

PEOPLE_YAML = PROJECT_ROOT / "config" / "people.yaml"


def slugify_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug:
        raise ValueError("Name must contain at least one letter or number")
    return slug


def register_person(name: str, face_dir: Path) -> None:
    data = yaml.safe_load(PEOPLE_YAML.read_text(encoding="utf-8")) or {}
    people = data.get("people", [])

    relative_face_dir = face_dir.relative_to(PROJECT_ROOT).as_posix()
    for person in people:
        if person.get("name") == name:
            person["face_dir"] = relative_face_dir
            break
    else:
        people.append({"name": name, "face_dir": relative_face_dir})

    data["people"] = people
    PEOPLE_YAML.parent.mkdir(parents=True, exist_ok=True)
    PEOPLE_YAML.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    logger.info("Registered %s in %s", name, PEOPLE_YAML)


def _save_frame_jpeg(frame: np.ndarray, path: Path) -> None:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is required to save enrollment photos") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    if not cv2.imwrite(str(path), bgr):
        raise RuntimeError(f"Failed to write enrollment photo: {path}")


def enroll_from_frames(
    name: str,
    frames: list[np.ndarray],
    enrollment_cfg: dict[str, Any],
    detection_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not frames:
        raise ValueError("At least one frame is required for enrollment")

    slug = slugify_name(name)
    known_faces_dir = Path(
        enrollment_cfg.get("known_faces_dir", PROJECT_ROOT / "data" / "known_faces")
    )
    if not known_faces_dir.is_absolute():
        known_faces_dir = PROJECT_ROOT / known_faces_dir

    person_dir = known_faces_dir / slug
    person_dir.mkdir(parents=True, exist_ok=True)

    encodings: list[np.ndarray] = []
    saved_count = 0

    for index, frame in enumerate(frames, start=1):
        boxes = detect_faces(frame, detection_cfg)
        if len(boxes) != 1:
            logger.warning(
                "Skipping enrollment frame %d for %s: expected 1 face, got %d",
                index,
                name,
                len(boxes),
            )
            continue

        encoding = encode_face(frame, boxes[0])
        if encoding is None:
            logger.warning(
                "Skipping enrollment frame %d for %s: could not compute encoding",
                index,
                name,
            )
            continue

        photo_path = person_dir / f"{saved_count + 1:03d}.jpg"
        _save_frame_jpeg(frame, photo_path)
        encodings.append(encoding)
        saved_count += 1

    minimum_photos = int(enrollment_cfg.get("minimum_photos", 1))
    if saved_count < minimum_photos:
        raise RuntimeError(
            f"Need at least {minimum_photos} valid single-face photo(s); got {saved_count}"
        )

    np.save(person_dir / ENCODINGS_FILENAME, np.stack(encodings))
    register_person(name, person_dir)

    return {
        "name": name,
        "slug": slug,
        "face_dir": person_dir,
        "photo_count": saved_count,
    }


def _validate_frame(frame: np.ndarray, detection_cfg: dict[str, Any] | None = None) -> None:
    boxes = detect_faces(frame, detection_cfg)
    if len(boxes) != 1:
        raise RuntimeError(f"Expected exactly one face, found {len(boxes)}")


def enroll_person(
    name: str,
    camera_cfg: dict[str, Any],
    enrollment_cfg: dict[str, Any],
    detection_cfg: dict[str, Any] | None = None,
) -> Path:
    capture_count = int(enrollment_cfg.get("capture_count", 5))
    delay_seconds = float(enrollment_cfg.get("delay_seconds", 0.5))

    camera = create_camera(camera_cfg)
    frames: list[np.ndarray] = []

    try:
        for _ in range(capture_count):
            frame = camera.capture_frame()
            _validate_frame(frame, detection_cfg)
            frames.append(frame)
            if delay_seconds > 0:
                time.sleep(delay_seconds)
    finally:
        camera.close()

    result = enroll_from_frames(name, frames, enrollment_cfg, detection_cfg)
    return result["face_dir"]
