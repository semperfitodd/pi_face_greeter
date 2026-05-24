from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pi_face_greeter.cli_output import report_failure, report_success
from pi_face_greeter.config_loader import load_config
from pi_face_greeter.main import run_greet_cycle
from pi_face_greeter.pir_sensor import PIRSensor

logger = logging.getLogger("pi_face_greeter.validate_motion")


def _log_path(config: dict[str, Any]) -> Path | None:
    log_file = config.get("logging", {}).get("file")
    return Path(log_file) if log_file else None


def run_validate_motion(config: dict[str, Any]) -> int:
    pir_cfg = config.get("pir", {})
    validation_cfg = config.get("validation", {})
    camera_cfg = config.get("camera", {})
    tts_cfg = config.get("tts", {})
    log_path = _log_path(config)

    if not pir_cfg.get("enabled", False):
        report_failure(
            "Motion validation failed: PIR not enabled",
            RuntimeError("Set pir.enabled: true in config/config.yaml"),
            log_path,
            hint="Wire PIR to GPIO17 (3.3V, GND, OUT) then enable in config",
        )
        return 1

    gpio_pin = int(pir_cfg.get("gpio_pin", 17))
    wait_seconds = float(validation_cfg.get("pir_wait_seconds", 30))

    print(f"Trigger motion within {int(wait_seconds)}s (wave hand)...")

    pir = PIRSensor(gpio_pin=gpio_pin)
    camera = None

    try:
        if not pir.wait_for_motion(timeout=wait_seconds):
            report_failure(
                "Motion validation failed: no motion detected",
                TimeoutError(f"No motion on GPIO{gpio_pin} within {int(wait_seconds)}s"),
                log_path,
                hint="Check PIR wiring (3.3V pin 1, GND pin 6, OUT pin 11)",
            )
            return 1

        camera, frame_path = run_greet_cycle(
            camera_cfg,
            tts_cfg,
            camera=camera,
            filename_prefix="motion",
        )

        if frame_path:
            report_success(
                f"Motion validation passed. GPIO{gpio_pin}, frame: {frame_path}, greeting spoken."
            )
        else:
            report_success(
                f"Motion validation passed. GPIO{gpio_pin}, greeting spoken."
            )
        return 0

    except Exception as exc:
        report_failure(
            "Motion validation failed: greet cycle",
            exc,
            log_path,
            hint="Check camera and TTS; run pi-face-greeter-validate-step1 first",
        )
        return 1
    finally:
        if camera is not None:
            camera.close()
        pir.close()


def main() -> int:
    from pi_face_greeter.cli_output import configure_validation_logging

    config = load_config()
    logging_cfg = config.get("logging", {})
    configure_validation_logging(
        log_file=logging_cfg.get("file"),
        level=logging_cfg.get("level", "INFO"),
    )
    return run_validate_motion(config)
