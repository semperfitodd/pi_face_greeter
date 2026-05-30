from __future__ import annotations

import logging
import sys

from kivy.app import App
from kivy.uix.carousel import Carousel

from pi_face_greeter.app.camera_source import CameraSource
from pi_face_greeter.app.face_screen import FaceScreen
from pi_face_greeter.app.settings_screen import SettingsScreen
from pi_face_greeter.config_loader import load_config
from pi_face_greeter.logger import setup_logging

logger = logging.getLogger("pi_face_greeter.app")


class PiFaceGreeterApp(App):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config_data: dict = {}
        self.camera_source: CameraSource | None = None

    def build(self):
        self.config_data = load_config()
        logging_cfg = self.config_data.get("logging", {})
        setup_logging(
            level=logging_cfg.get("level", "INFO"),
            log_file=logging_cfg.get("file"),
        )

        ui_cfg = self.config_data.get("ui", {})
        camera_cfg = self.config_data.get("camera", {})
        tts_cfg = self.config_data.get("tts", {})

        if ui_cfg.get("fullscreen", True):
            from kivy.core.window import Window

            Window.fullscreen = "auto"

        self.camera_source = CameraSource(camera_cfg)
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
        settings_screen = SettingsScreen(name="settings")
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
