from __future__ import annotations

from pathlib import Path

from pi_face_greeter.cli_output import configure_validation_logging, report_failure, report_success
from pi_face_greeter.config_loader import load_config
from pi_face_greeter.main import run_greet_cycle


def main() -> int:
    config = load_config()
    logging_cfg = config.get("logging", {})
    log_path = configure_validation_logging(
        log_file=logging_cfg.get("file"),
        level=logging_cfg.get("level", "INFO"),
    )

    camera_cfg = config.get("camera", {})
    tts_cfg = config.get("tts", {})
    camera = None

    try:
        camera, frame_path = run_greet_cycle(
            camera_cfg, tts_cfg, camera=camera, filename_prefix="greet"
        )
        if frame_path:
            report_success(f"Greet once passed. Frame: {frame_path}")
        else:
            report_success("Greet once passed.")
        return 0
    except Exception as exc:
        report_failure("Greet once failed", exc, log_path)
        return 1
    finally:
        if camera is not None:
            camera.close()
