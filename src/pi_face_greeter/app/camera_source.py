from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from pi_face_greeter.app.debug_frames import save_debug_frame
from pi_face_greeter.app.detector import FaceBox, detect_faces
from pi_face_greeter.camera import CameraBackend, create_camera

logger = logging.getLogger("pi_face_greeter.camera_source")


@dataclass(frozen=True)
class CameraSnapshot:
    frame: np.ndarray | None
    boxes: tuple[FaceBox, ...]
    timestamp: float


class CameraSource:
    def __init__(
        self,
        camera_cfg: dict[str, Any],
        detection_cfg: dict[str, Any] | None = None,
        diagnostics_cfg: dict[str, Any] | None = None,
        poll_interval: float = 0.05,
    ) -> None:
        self._camera_cfg = camera_cfg
        self._detection_cfg = detection_cfg or {}
        self._diagnostics_cfg = diagnostics_cfg or {}
        self._debug = bool(self._diagnostics_cfg.get("debug", False))
        self._snapshot_dir = Path(self._diagnostics_cfg.get("snapshot_dir", "data/debug"))
        self._snapshot_interval = float(
            self._diagnostics_cfg.get("snapshot_interval_seconds", 2.0)
        )
        self._last_snapshot_time = 0.0
        self._poll_interval = poll_interval
        self._lock = threading.Lock()
        self._snapshot = CameraSnapshot(frame=None, boxes=(), timestamp=0.0)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._camera: CameraBackend | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="camera-source", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._camera is not None:
            try:
                self._camera.close()
            except Exception:
                logger.exception("Failed to close camera")
            self._camera = None

    def get_snapshot(self) -> CameraSnapshot:
        with self._lock:
            return self._snapshot

    def _maybe_save_debug_snapshot(self, frame: np.ndarray, boxes: tuple[FaceBox, ...]) -> None:
        if not self._debug:
            return

        now = time.monotonic()
        if now - self._last_snapshot_time < self._snapshot_interval:
            return

        self._last_snapshot_time = now
        try:
            save_debug_frame(frame, boxes, self._snapshot_dir)
        except Exception:
            logger.exception("Failed to save debug snapshot")

    def _run(self) -> None:
        try:
            self._camera = create_camera(self._camera_cfg)
        except Exception:
            logger.exception("Failed to start camera")
            return

        while not self._stop_event.is_set():
            try:
                frame = self._camera.capture_frame()
            except Exception:
                logger.exception("Camera capture failed")
                time.sleep(self._poll_interval)
                continue

            try:
                boxes = tuple(detect_faces(frame, self._detection_cfg))
            except Exception:
                logger.exception("Face detection failed")
                boxes = ()

            self._maybe_save_debug_snapshot(frame, boxes)

            snapshot = CameraSnapshot(frame=frame, boxes=boxes, timestamp=time.monotonic())
            with self._lock:
                self._snapshot = snapshot
            time.sleep(self._poll_interval)
