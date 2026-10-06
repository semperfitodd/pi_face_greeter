from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from collections.abc import Callable, Iterator
from queue import Empty, Queue

from pi_face_greeter.alsa_devices import normalize_alsa_device

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2
DEFAULT_FRAME_SAMPLES = 512

logger = logging.getLogger("pi_face_greeter.mic")

FrameCallback = Callable[[bytes], None]


class MicStream:
    """Single-owner ALSA capture stream shared by wake word and conversation."""

    def __init__(
        self,
        *,
        alsa_device: str | None = None,
        frame_samples: int = DEFAULT_FRAME_SAMPLES,
    ) -> None:
        self._configured_device = alsa_device
        self._frame_samples = frame_samples
        self._frame_bytes = frame_samples * SAMPLE_WIDTH * CHANNELS
        self._subscribers: list[FrameCallback] = []
        self._lock = threading.Lock()
        self._paused = False
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen[bytes] | None = None
        self._running = False

    @property
    def frame_samples(self) -> int:
        return self._frame_samples

    @property
    def frame_bytes(self) -> int:
        return self._frame_bytes

    def subscribe(self, callback: FrameCallback) -> None:
        with self._lock:
            if callback not in self._subscribers:
                self._subscribers.append(callback)

    def unsubscribe(self, callback: FrameCallback) -> None:
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def start(self) -> None:
        if self._running:
            return
        if shutil.which("arecord") is None:
            raise RuntimeError("arecord not found. Install with: sudo apt install alsa-utils")
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, name="mic-capture", daemon=True)
        self._thread.start()
        logger.info("Mic stream started")

    def stop(self) -> None:
        self._running = False
        proc = self._proc
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        self._proc = None
        logger.info("Mic stream stopped")

    def iter_frames(self, *, timeout: float | None = None) -> Iterator[bytes]:
        queue: Queue[bytes | None] = Queue()

        def _enqueue(frame: bytes) -> None:
            queue.put(frame)

        self.subscribe(_enqueue)
        try:
            while self._running:
                try:
                    frame = queue.get(timeout=timeout)
                except Empty:
                    return
                if frame is None:
                    return
                yield frame
        finally:
            self.unsubscribe(_enqueue)

    def _emit(self, frame: bytes) -> None:
        if self._paused:
            return
        with self._lock:
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(frame)
            except Exception:
                logger.warning("Mic subscriber failed", exc_info=True)

    def _capture_loop(self) -> None:
        from pi_face_greeter.alsa_devices import resolve_capture_device

        device = resolve_capture_device(self._configured_device)
        command = [
            "arecord",
            "-q",
            "-f",
            "S16_LE",
            "-r",
            str(SAMPLE_RATE),
            "-c",
            str(CHANNELS),
            "-t",
            "raw",
        ]
        alsa = normalize_alsa_device(device)
        if alsa:
            command.extend(["-D", alsa])

        try:
            self._proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError:
            logger.exception("Failed to start arecord")
            self._running = False
            return

        stdout = self._proc.stdout
        if stdout is None:
            self._running = False
            return

        while self._running:
            chunk = stdout.read(self._frame_bytes)
            if not chunk:
                break
            if len(chunk) < self._frame_bytes:
                continue
            self._emit(chunk)

        proc = self._proc
        if proc is not None and proc.stderr is not None:
            err = proc.stderr.read().decode("utf-8", errors="replace").strip()
            if err:
                logger.error("arecord exited: %s", err)
        if proc is not None and proc.poll() is None:
            proc.terminate()


def create_mic_stream(stt_cfg: dict, tts_cfg: dict | None = None) -> MicStream:
    from pi_face_greeter.alsa_devices import resolve_audio_devices

    playback_cfg = tts_cfg.get("alsa_device") if tts_cfg else None
    playback, capture = resolve_audio_devices(
        playback_configured=playback_cfg,
        capture_configured=stt_cfg.get("alsa_device"),
    )
    logger.info(
        "Mic stream ALSA: playback=%s capture=%s",
        playback or "default",
        capture or "default",
    )
    return MicStream(alsa_device=capture)
