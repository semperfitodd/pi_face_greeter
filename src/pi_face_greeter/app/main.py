from __future__ import annotations

import logging
import os
import sys

from kivy.app import App
from kivy.uix.carousel import Carousel

from pi_face_greeter.app.camera_source import CameraSource
from pi_face_greeter.app.face_screen import FaceScreen
from pi_face_greeter.app.settings_screen import SettingsScreen
from pi_face_greeter.config_loader import load_config
from pi_face_greeter.face_recognition import configure as configure_recognizer
from pi_face_greeter.face_recognition import reload as reload_recognizer
from pi_face_greeter.logger import setup_logging

logger = logging.getLogger("pi_face_greeter.app")


def _debug_enabled(diagnostics_cfg: dict) -> bool:
    env_value = os.environ.get("PI_FACE_GREETER_DEBUG", "").strip().lower()
    if env_value in ("1", "true", "yes"):
        return True
    return bool(diagnostics_cfg.get("debug", False))


class PiFaceGreeterApp(App):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config_data: dict = {}
        self.camera_source: CameraSource | None = None

    def build(self):
        self.config_data = load_config()
        logging_cfg = self.config_data.get("logging", {})
        diagnostics_cfg = dict(self.config_data.get("diagnostics", {}))
        debug = _debug_enabled(diagnostics_cfg)
        diagnostics_cfg["debug"] = debug

        log_level = "DEBUG" if debug else logging_cfg.get("level", "INFO")
        log_file = logging_cfg.get("file")
        capture_loggers = ["kivy"] if debug else None
        setup_logging(
            level=log_level,
            log_file=log_file,
            capture_loggers=capture_loggers,
            max_bytes=int(logging_cfg.get("max_bytes", 1_000_000)),
            backup_count=int(logging_cfg.get("backup_count", 3)),
        )

        if log_file:
            log_path_msg = f"Logs: {log_file}"
            print(log_path_msg)
            logger.info(log_path_msg)

        if debug:
            snapshot_dir = diagnostics_cfg.get("snapshot_dir", "data/debug")
            snapshot_msg = f"Debug snapshots: {snapshot_dir}"
            print(snapshot_msg)
            logger.info(snapshot_msg)
            logger.debug("Diagnostics debug mode enabled")

        ui_cfg = self.config_data.get("ui", {})
        camera_cfg = self.config_data.get("camera", {})
        tts_cfg = self.config_data.get("tts", {})
        enrollment_cfg = self.config_data.get("enrollment", {})
        detection_cfg = self.config_data.get("detection", {})

        configure_recognizer(self.config_data.get("recognition", {}))

        if ui_cfg.get("fullscreen", True):
            from kivy.core.window import Window

            Window.fullscreen = "auto"

        self.camera_source = CameraSource(
            camera_cfg,
            detection_cfg=self.config_data.get("detection", {}),
            diagnostics_cfg=diagnostics_cfg,
        )
        self.camera_source.start()

        carousel = Carousel(
            direction="right",
            loop=False,
            size_hint=(1, 1),
        )

        face_screen = FaceScreen(
            name="face",
            camera_source=self.camera_source,
            tts_cfg=tts_cfg,
            ui_cfg=ui_cfg,
        )
        settings_screen = SettingsScreen(
            name="settings",
            camera_source=self.camera_source,
            enrollment_cfg=enrollment_cfg,
            detection_cfg=detection_cfg,
            on_people_changed=reload_recognizer,
        )
        carousel.add_widget(face_screen)
        carousel.add_widget(settings_screen)

        logger.info("Pi Face Greeter kiosk app started")
        return carousel

    def on_stop(self) -> None:
        if self.camera_source is not None:
            self.camera_source.stop()
        logger.info("Pi Face Greeter kiosk app stopped")


def main() -> int:
    try:
        PiFaceGreeterApp().run()
    except KeyboardInterrupt:
        return 0
    except Exception:
        logger.exception("Kiosk app failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
