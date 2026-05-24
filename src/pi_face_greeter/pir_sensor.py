from __future__ import annotations

import logging
import threading
from typing import Callable

logger = logging.getLogger("pi_face_greeter.pir")


class PIRSensor:
    def __init__(self, gpio_pin: int = 17) -> None:
        from gpiozero import MotionSensor

        self.gpio_pin = gpio_pin
        self._sensor = MotionSensor(gpio_pin)
        self._motion_event = threading.Event()
        self._sensor.when_motion = self._on_motion
        logger.info("PIR sensor initialized on GPIO %s", gpio_pin)

    def _on_motion(self) -> None:
        self._motion_event.set()

    def wait_for_motion(self, timeout: float | None = None) -> bool:
        self._motion_event.clear()
        triggered = self._motion_event.wait(timeout=timeout)
        if triggered:
            logger.debug("Motion detected on GPIO %s", self.gpio_pin)
        return triggered

    def on_motion(self, callback: Callable[[], None]) -> None:
        self._sensor.when_motion = lambda: (self._on_motion(), callback())

    def close(self) -> None:
        self._sensor.close()
        logger.info("PIR sensor closed")

    def __enter__(self) -> PIRSensor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
