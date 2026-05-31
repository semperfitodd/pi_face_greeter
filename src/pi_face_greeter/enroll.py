from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

from pi_face_greeter.cli_output import configure_validation_logging, report_failure, report_success
from pi_face_greeter.config_loader import load_config
from pi_face_greeter.enrollment import enroll_person

logger = logging.getLogger("pi_face_greeter.enroll")


def _log_path(config: dict[str, Any]) -> Path | None:
    log_file = config.get("logging", {}).get("file")
    return Path(log_file) if log_file else None


def run_enroll(name: str, config: dict[str, Any], count: int | None = None) -> int:
    log_path = _log_path(config)
    camera_cfg = config.get("camera", {})
    enrollment_cfg = config.get("enrollment", {})

    if not camera_cfg.get("enabled", True):
        report_failure(
            "Enrollment failed: camera disabled",
            RuntimeError("Enable camera in config/config.yaml"),
            log_path,
        )
        return 1

    try:
        person_dir = enroll_person(
            name,
            camera_cfg,
            enrollment_cfg,
            detection_cfg=config.get("detection", {}),
            count=count,
        )
        photo_count = len(list(person_dir.glob("*.jpg")))
        report_success(
            f"Step 2 passed. Enrolled {name}: {photo_count} photos in {person_dir}"
        )
        return 0
    except Exception as exc:
        report_failure(
            "Enrollment failed",
            exc,
            log_path,
            hint="Face the camera with good lighting; one face per frame",
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Enroll a known face for Pi Face Greeter")
    parser.add_argument("name", help="Person name to enroll")
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of photos to capture (default: enrollment.capture_count in config)",
    )
    args = parser.parse_args()

    config = load_config()
    logging_cfg = config.get("logging", {})
    configure_validation_logging(
        log_file=logging_cfg.get("file"),
        level=logging_cfg.get("level", "INFO"),
    )

    return run_enroll(args.name, config, count=args.count)
