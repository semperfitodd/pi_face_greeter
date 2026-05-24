from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("pi_face_greeter.camera")


class CameraBackend(ABC):
    @abstractmethod
    def capture_frame(self) -> np.ndarray:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    def save_frame(self, frame: np.ndarray, output_path: Path) -> Path:
        from PIL import Image

        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(frame).save(output_path, format="JPEG")
        logger.info("Saved frame to %s", output_path)
        return output_path


class Picamera2Camera(CameraBackend):
    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        warmup_frames: int = 2,
    ) -> None:
        from picamera2 import Picamera2

        self._picam2 = Picamera2()
        config = self._picam2.create_preview_configuration(
            main={"format": "RGB888", "size": (width, height)}
        )
        self._picam2.configure(config)
        self._picam2.start()
        logger.info("Picamera2 started at %sx%s", width, height)

        for _ in range(warmup_frames):
            self._picam2.capture_array()

    def capture_frame(self) -> np.ndarray:
        return self._picam2.capture_array()

    def close(self) -> None:
        self._picam2.stop()
        logger.info("Picamera2 stopped")


class OpenCVCamera(CameraBackend):
    def __init__(
        self,
        device_index: int = 0,
        width: int = 640,
        height: int = 480,
        warmup_frames: int = 2,
    ) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError(
                "OpenCV (cv2) is required for the USB camera backend. "
                "On Raspberry Pi: sudo apt install python3-opencv and use a venv "
                "with --system-site-packages."
            ) from exc

        self._cv2 = cv2
        self._cap = cv2.VideoCapture(device_index)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Could not open USB camera at index {device_index}. "
                "Check v4l2-ctl --list-devices and set camera.device_index in config."
            )

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        for _ in range(warmup_frames):
            self._cap.read()

        logger.info("OpenCV camera opened at index %s (%sx%s)", device_index, width, height)

    def capture_frame(self) -> np.ndarray:
        ok, frame = self._cap.read()
        if not ok:
            raise RuntimeError("Failed to capture frame from USB camera")
        return self._cv2.cvtColor(frame, self._cv2.COLOR_BGR2RGB)

    def close(self) -> None:
        self._cap.release()
        logger.info("OpenCV camera released")


def create_camera(config: dict[str, Any]) -> CameraBackend:
    if not config.get("enabled", True):
        raise RuntimeError("Camera is disabled in config")

    backend = config.get("backend", "picamera2").lower()
    width = int(config.get("width", 640))
    height = int(config.get("height", 480))
    warmup_frames = int(config.get("warmup_frames", 2))

    if backend == "picamera2":
        return Picamera2Camera(width=width, height=height, warmup_frames=warmup_frames)

    if backend == "opencv":
        device_index = int(config.get("device_index", 0))
        return OpenCVCamera(
            device_index=device_index,
            width=width,
            height=height,
            warmup_frames=warmup_frames,
        )

    raise ValueError(f"Unknown camera backend: {backend}")
