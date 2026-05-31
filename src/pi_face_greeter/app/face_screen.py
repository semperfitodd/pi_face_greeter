from __future__ import annotations

import logging
import threading
from typing import Any

from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from pi_face_greeter.app.camera_preview import CameraPreview
from pi_face_greeter.app.camera_source import CameraSource
from pi_face_greeter.app.conversation import generate_greeting
from pi_face_greeter.app.face_widget import AnimatedFace
from pi_face_greeter.app.greeting import build_greeting
from pi_face_greeter.app.identity_vote import PENDING, IdentityVoter
from pi_face_greeter.app.per_person_cooldown import PerPersonCooldown, cooldown_key
from pi_face_greeter.app.presence import should_trigger_greeting
from pi_face_greeter.face_recognition import get_person_cooldown, get_person_greeting, identify
from pi_face_greeter.tts import speak_from_config

logger = logging.getLogger("pi_face_greeter.face_screen")


class FaceScreen(Screen):
    def __init__(
        self,
        camera_source: CameraSource,
        tts_cfg: dict[str, Any],
        ui_cfg: dict[str, Any],
        ollama_cfg: dict[str, Any] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.camera_source = camera_source
        self.tts_cfg = tts_cfg
        self.ui_cfg = ui_cfg
        self._ollama_cfg = ollama_cfg or {}

        cooldown_seconds = float(ui_cfg.get("greet_cooldown_seconds", 30))
        self._cooldown = PerPersonCooldown(cooldown_seconds)
        self._presence_frames_required = int(ui_cfg.get("presence_frames_required", 5))
        self._recognition_frames_required = int(ui_cfg.get("recognition_frames_required", 3))
        self._identity_voter = IdentityVoter(self._recognition_frames_required)
        self._consecutive_face_frames = 0
        self._greeting_in_progress = False
        self._status_label: Label | None = None
        self._animated_face: AnimatedFace | None = None
        self._tick_event = None
        self._ask_how_are_you = bool(tts_cfg.get("ask_how_are_you", True))

        self._build_ui()
        Clock.schedule_once(self._start_presence_watch, 0)

    def _start_presence_watch(self, _dt=None) -> None:
        if self._tick_event is None:
            self._tick_event = Clock.schedule_interval(self._tick, 1 / 10)
            logger.debug("Presence watch started")

    def stop_presence_watch(self) -> None:
        if self._tick_event is not None:
            self._tick_event.cancel()
            self._tick_event = None
            logger.debug("Presence watch stopped")

    def on_enter(self, *_args) -> None:
        self._start_presence_watch()

    def on_leave(self, *_args) -> None:
        self.stop_presence_watch()

    def _reset_presence_state(self) -> None:
        self._consecutive_face_frames = 0
        self._identity_voter.reset()

    def _build_ui(self) -> None:
        root = FloatLayout()

        face = AnimatedFace(
            blink_interval_min=float(self.ui_cfg.get("blink_interval_min", 2.0)),
            blink_interval_max=float(self.ui_cfg.get("blink_interval_max", 6.0)),
            size_hint=(1, 1),
        )
        self._animated_face = face
        root.add_widget(face)

        preview_width = int(self.ui_cfg.get("preview_width", 200))
        preview_height = int(self.ui_cfg.get("preview_height", 150))
        preview = CameraPreview(
            camera_source=self.camera_source,
            size_hint=(None, None),
            size=(preview_width, preview_height),
            pos_hint={"x": 0.02, "top": 0.98},
        )
        root.add_widget(preview)

        status = Label(
            text="",
            size_hint=(1, None),
            height=32,
            pos_hint={"center_x": 0.5, "y": 0.02},
            color=(0.9, 0.9, 0.9, 1),
        )
        self._status_label = status
        root.add_widget(status)

        hint = Label(
            text="Swipe left for settings",
            size_hint=(None, None),
            size=(220, 24),
            pos_hint={"right": 0.98, "y": 0.02},
            color=(0.6, 0.6, 0.6, 1),
        )
        root.add_widget(hint)

        self.add_widget(root)

    def _tick(self, _dt) -> None:
        if self._greeting_in_progress:
            return

        snapshot = self.camera_source.get_snapshot()
        if snapshot.frame is None:
            self._reset_presence_state()
            return

        if snapshot.boxes:
            self._consecutive_face_frames += 1
        else:
            self._reset_presence_state()
            if self._status_label is not None:
                self._status_label.text = ""
            return

        if not should_trigger_greeting(
            self._consecutive_face_frames,
            self._presence_frames_required,
        ):
            logger.debug(
                "Face detected (%d/%d frames)",
                self._consecutive_face_frames,
                self._presence_frames_required,
            )
            return

        name, confidence = identify(snapshot.frame)
        confirmed = self._identity_voter.push(name)
        if confirmed is PENDING:
            logger.debug(
                "Confirming identity (%s, confidence %.2f)",
                name or "unknown",
                confidence,
            )
            return

        key = cooldown_key(confirmed)
        person_cooldown = get_person_cooldown(confirmed)
        if person_cooldown is not None:
            self._cooldown.set_duration(key, person_cooldown)

        if not self._cooldown.can_trigger(key):
            remaining = int(self._cooldown.seconds_remaining(key))
            if self._status_label is not None:
                label = confirmed or "friend"
                self._status_label.text = f"Cooldown for {label} ({remaining}s)"
            return

        self._trigger_greeting(confirmed, confidence)

    def _trigger_greeting(self, name: str | None, confidence: float) -> None:
        self._greeting_in_progress = True
        self._reset_presence_state()
        self._cooldown.mark_triggered(cooldown_key(name))

        if name:
            logger.info("Recognized %s (confidence %.2f)", name, confidence)
        else:
            logger.info("Unknown face detected; using friend greeting")

        thread = threading.Thread(
            target=self._speak_and_finish,
            args=(name, get_person_greeting(name)),
            daemon=True,
        )
        thread.start()

    def _on_greeting_ready(self, greeting: str) -> None:
        if self._status_label is not None:
            self._status_label.text = greeting
        if self._animated_face is not None:
            self._animated_face.start_talking()

    def _speak_and_finish(self, name: str | None, custom_greeting: str | None) -> None:
        try:
            fallback = build_greeting(
                name,
                custom_greeting,
                ask_how_are_you=self._ask_how_are_you,
            )
            greeting = generate_greeting(
                name,
                ollama_cfg=self._ollama_cfg,
                fallback_text=fallback,
            )
            logger.info("Speaking greeting: %s", greeting)
            Clock.schedule_once(lambda _dt: self._on_greeting_ready(greeting), 0)
            speak_from_config(greeting, self.tts_cfg)
        except Exception:
            logger.exception("TTS failed")
        finally:
            Clock.schedule_once(self._finish_greeting, 0)

    def _finish_greeting(self, _dt) -> None:
        if self._animated_face is not None:
            self._animated_face.stop_talking()
        self._greeting_in_progress = False
