from __future__ import annotations

import logging
import signal
from datetime import datetime
from pathlib import Path
from typing import Any

from pi_face_greeter.camera import CameraBackend, create_camera
from pi_face_greeter.config_loader import load_config
from pi_face_greeter.greet_pipeline import speak_greeting
from pi_face_greeter.logger import setup_logging
from pi_face_greeter.per_person_cooldown import PerPersonCooldown, cooldown_key
from pi_face_greeter.pir_sensor import PIRSensor
from pi_face_greeter.recognition import configure as configure_recognizer
from pi_face_greeter.recognition import get_person_cooldown, identify

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
    ollama_cfg: dict[str, Any] | None = None,
    conversation_cfg: dict[str, Any] | None = None,
    stt_cfg: dict[str, Any] | None = None,
    assistant_cfg: dict[str, Any] | None = None,
    cooldown: PerPersonCooldown | None = None,
) -> tuple[CameraBackend | None, Path | None, bool]:
    frame_path = None
    active_camera = camera
    ollama = ollama_cfg or {}
    spoke = False

    if camera_cfg.get("enabled", True):
        if active_camera is None:
            active_camera = create_camera(camera_cfg)
        frame = active_camera.capture_frame()
        capture_dir = Path(camera_cfg.get("capture_dir", "data/captured"))
        filename = f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        frame_path = active_camera.save_frame(frame, capture_dir / filename)

        from pi_face_greeter.retention import prune_jpeg_directory

        max_captures = int(camera_cfg.get("max_retained_captures", 50))
        prune_jpeg_directory(capture_dir, max_captures)

        name, confidence = identify(frame)
        if name:
            logger.info("Recognized %s (confidence %.2f)", name, confidence)
        else:
            logger.info("No recognized face; using friend greeting")

        if cooldown is not None:
            key = cooldown_key(name)
            person_cooldown = get_person_cooldown(name)
            if person_cooldown is not None:
                cooldown.set_duration(key, person_cooldown)
            if not cooldown.can_trigger(key):
                remaining = cooldown.seconds_remaining(key)
                logger.info("Cooldown active for %s (%.0fs remaining), skipping greeting", key, remaining)
                return active_camera, frame_path, False

        speak_greeting(
            name,
            tts_cfg=tts_cfg,
            ollama_cfg=ollama,
            conversation_cfg=conversation_cfg,
            stt_cfg=stt_cfg,
            assistant_cfg=assistant_cfg,
        )
        if cooldown is not None:
            cooldown.mark_triggered(cooldown_key(name))
        spoke = True
    else:
        logger.info("Camera disabled in config")
        speak_greeting(
            None,
            tts_cfg=tts_cfg,
            ollama_cfg=ollama,
            conversation_cfg=conversation_cfg,
            stt_cfg=stt_cfg,
            assistant_cfg=assistant_cfg,
            camera_disabled=True,
        )
        spoke = True

    return active_camera, frame_path, spoke


def main() -> int:
    config = load_config()
    logging_cfg = config.get("logging", {})
    setup_logging(
        level=logging_cfg.get("level", "INFO"),
        log_file=logging_cfg.get("file"),
        max_bytes=int(logging_cfg.get("max_bytes", 1_000_000)),
        backup_count=int(logging_cfg.get("backup_count", 3)),
    )
    configure_recognizer(config.get("recognition", {}))

    app_cfg = config.get("app", {})
    ui_cfg = config.get("ui", {})
    pir_cfg = config.get("pir", {})
    camera_cfg = config.get("camera", {})
    tts_cfg = config.get("tts", {})
    ollama_cfg = config.get("ollama", {})
    conversation_cfg = config.get("conversation", {})
    stt_cfg = config.get("stt", {})
    assistant_cfg = config.get("assistant", {})

    if not pir_cfg.get("enabled", False):
        logger.error(
            "PIR is disabled. Set pir.enabled: true when the sensor is wired, "
            "or use pi-face-greeter-validate-step1 / pi-face-greeter-greet-once."
        )
        return 1

    greet_cooldown = float(ui_cfg.get("greet_cooldown_seconds", 30))
    cooldown = PerPersonCooldown(greet_cooldown)
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

            try:
                camera, frame_path, spoke = run_greet_cycle(
                    camera_cfg,
                    tts_cfg,
                    camera=camera,
                    filename_prefix="motion",
                    ollama_cfg=ollama_cfg,
                    conversation_cfg=conversation_cfg,
                    stt_cfg=stt_cfg,
                    assistant_cfg=assistant_cfg,
                    cooldown=cooldown,
                )
            except Exception:
                logger.exception("Greet cycle failed")
                continue

            if spoke:
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
