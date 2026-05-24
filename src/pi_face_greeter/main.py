from __future__ import annotations

import logging
import signal
from datetime import datetime
from pathlib import Path
from typing import Any

from pi_face_greeter.camera import CameraBackend, create_camera
from pi_face_greeter.config_loader import load_config
from pi_face_greeter.cooldown import CooldownGate
from pi_face_greeter.face_recognition import identify
from pi_face_greeter.logger import setup_logging
from pi_face_greeter.pir_sensor import PIRSensor
from pi_face_greeter.tts import speak_from_config

logger = logging.getLogger("pi_face_greeter")

_running = True


def _handle_shutdown(signum, frame) -> None:
    global _running
    _running = False


def run_greet_cycle(
    camera_cfg: dict[str, Any],
    tts_cfg: dict[str, Any],
    camera: CameraBackend | None = None,
    filename_prefix: str = "motion",
) -> tuple[CameraBackend | None, Path | None]:
    frame_path = None
    active_camera = camera

    if camera_cfg.get("enabled", True):
        if active_camera is None:
            active_camera = create_camera(camera_cfg)
        frame = active_camera.capture_frame()
        capture_dir = Path(camera_cfg.get("capture_dir", "data/captured"))
        filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        frame_path = active_camera.save_frame(frame, capture_dir / filename)

        name, confidence = identify(frame)
        if name:
            logger.info("Recognized %s (confidence %.2f)", name, confidence)
    else:
        logger.info("Camera disabled in config")

    greeting = tts_cfg.get(
        "placeholder_greeting",
        "Hello. Face recognition is not enabled yet.",
    )
    speak_from_config(greeting, tts_cfg)

    return active_camera, frame_path


def main() -> int:
    config = load_config()
    logging_cfg = config.get("logging", {})
    setup_logging(
        level=logging_cfg.get("level", "INFO"),
        log_file=logging_cfg.get("file"),
    )

    app_cfg = config.get("app", {})
    pir_cfg = config.get("pir", {})
    camera_cfg = config.get("camera", {})
    tts_cfg = config.get("tts", {})

    if not pir_cfg.get("enabled", False):
        logger.error(
            "PIR is disabled. Set pir.enabled: true when the sensor is wired, "
            "or use pi-face-greeter-validate-step1 / pi-face-greeter-greet-once."
        )
        return 1

    cooldown = CooldownGate(app_cfg.get("cooldown_seconds", 30))
    pir = PIRSensor(gpio_pin=pir_cfg.get("gpio_pin", 17))
    camera: CameraBackend | None = None

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    logger.info(
        "%s started — waiting for motion on GPIO %s",
        app_cfg.get("name", "Pi Face Greeter"),
        pir_cfg.get("gpio_pin", 17),
    )
    print("Waiting for motion... (Ctrl+C to stop)")

    try:
        while _running:
            if not pir.wait_for_motion(timeout=1.0):
                continue

            timestamp = datetime.now().isoformat(timespec="seconds")
            print(f"Motion detected at {timestamp}")
            logger.info("Motion detected at %s", timestamp)

            if not cooldown.can_trigger():
                remaining = cooldown.seconds_remaining()
                logger.info("Cooldown active (%.0fs remaining), skipping greeting", remaining)
                continue

            try:
                camera, frame_path = run_greet_cycle(
                    camera_cfg, tts_cfg, camera=camera, filename_prefix="motion"
                )
            except Exception:
                logger.exception("Greet cycle failed")
                continue

            cooldown.mark_triggered()
            if frame_path:
                logger.info("Greeting complete, frame saved to %s", frame_path)
            else:
                logger.info("Greeting complete")

    except Exception:
        logger.exception("Unexpected error in main loop")
        return 1
    finally:
        if camera is not None:
            camera.close()
        pir.close()
        logger.info("Shutdown complete")

    return 0
