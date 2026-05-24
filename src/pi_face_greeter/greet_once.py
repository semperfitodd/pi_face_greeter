from __future__ import annotations

import logging

from pi_face_greeter.config_loader import load_config
from pi_face_greeter.logger import setup_logging
from pi_face_greeter.main import run_greet_cycle

logger = logging.getLogger("pi_face_greeter.greet_once")


def main() -> int:
    config = load_config()
    logging_cfg = config.get("logging", {})
    setup_logging(
        level=logging_cfg.get("level", "INFO"),
        log_file=logging_cfg.get("file"),
    )

    camera_cfg = config.get("camera", {})
    tts_cfg = config.get("tts", {})
    camera = None

    print("Running single greet cycle (no PIR)...")

    try:
        camera, frame_path = run_greet_cycle(
            camera_cfg, tts_cfg, camera=camera, filename_prefix="greet"
        )
        if frame_path:
            print(f"Frame saved: {frame_path}")
        print("Greeting complete.")
        return 0
    except Exception:
        logger.exception("Greet once failed")
        return 1
    finally:
        if camera is not None:
            camera.close()
