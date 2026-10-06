from __future__ import annotations

import logging
import threading
import time
from typing import Any

from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen

from pi_face_greeter.app.camera_preview import CameraPreview
from pi_face_greeter.app.camera_source import CameraSource
from pi_face_greeter.app.face_widget import AnimatedFace
from pi_face_greeter.conversation import WAKE_HINT
from pi_face_greeter.greet_pipeline import run_greeting_interaction
from pi_face_greeter.identity_vote import PENDING, IdentityVoter
from pi_face_greeter.mic import MicStream
from pi_face_greeter.per_person_cooldown import PerPersonCooldown, cooldown_key
from pi_face_greeter.presence import should_trigger_greeting
from pi_face_greeter.recognition import get_person_cooldown, get_person_greeting, identify
from pi_face_greeter.wake_word import WakeWordListener

logger = logging.getLogger("pi_face_greeter.face_screen")


class FaceScreen(Screen):
    def __init__(
        self,
        camera_source: CameraSource,
        tts_cfg: dict[str, Any],
        ui_cfg: dict[str, Any],
        ollama_cfg: dict[str, Any] | None = None,
        conversation_cfg: dict[str, Any] | None = None,
        stt_cfg: dict[str, Any] | None = None,
        assistant_cfg: dict[str, Any] | None = None,
        wake_cfg: dict[str, Any] | None = None,
        mic: MicStream | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.camera_source = camera_source
        self.tts_cfg = tts_cfg
        self.ui_cfg = ui_cfg
        self._ollama_cfg = ollama_cfg or {}
        self._conversation_cfg = conversation_cfg or {}
        self._stt_cfg = stt_cfg or {}
        self._assistant_cfg = assistant_cfg or {}
        self._mic = mic
        self._pending_cooldown_key: str | None = None
        self._last_face_seen = 0.0
        self._last_confirmed_name: str | None = None
        self._presence_grace = float(self._conversation_cfg.get("presence_grace_seconds", 8))

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
        self._wake_listener: WakeWordListener | None = None

        self._build_ui()
        Clock.schedule_once(self._start_presence_watch, 0)

        if self._mic is not None and wake_cfg is not None:
            self._wake_listener = WakeWordListener(
                wake_cfg,
                self._mic,
                on_wake=self._schedule_wake_conversation,
            )
            self._wake_listener.start()

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

    def shutdown(self) -> None:
        if self._wake_listener is not None:
            self._wake_listener.stop()

    def _reset_presence_state(self) -> None:
        self._consecutive_face_frames = 0
        self._identity_voter.reset()

    def _is_present(self) -> bool:
        if self._last_face_seen <= 0:
            return False
        return time.monotonic() - self._last_face_seen < self._presence_grace

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
            self._last_face_seen = time.monotonic()
        else:
            self._reset_presence_state()
            if self._status_label is not None and not self._cooldown_active_for_display():
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

        if confirmed:
            self._last_confirmed_name = confirmed

        key = cooldown_key(confirmed)
        person_cooldown = get_person_cooldown(confirmed)
        if person_cooldown is not None:
            self._cooldown.set_duration(key, person_cooldown)

        if not self._cooldown.can_trigger(key):
            if self._status_label is not None:
                self._status_label.text = WAKE_HINT
            return

        self._trigger_greeting(confirmed, confidence)

    def _cooldown_active_for_display(self) -> bool:
        key = cooldown_key(self._last_confirmed_name)
        return not self._cooldown.can_trigger(key)

    def _pause_wake_listener(self) -> None:
        if self._wake_listener is not None:
            self._wake_listener.pause()

    def _resume_wake_listener(self) -> None:
        if self._wake_listener is not None:
            self._wake_listener.resume()

    def _schedule_wake_conversation(self) -> None:
        Clock.schedule_once(lambda _dt: self._trigger_wake_conversation(), 0)

    def _trigger_wake_conversation(self) -> None:
        if self._greeting_in_progress:
            return
        self._greeting_in_progress = True
        self._pause_wake_listener()
        self._pending_cooldown_key = None
        name = self._last_confirmed_name
        logger.info("Wake word conversation for %s", name or "unknown")

        thread = threading.Thread(
            target=self._speak_and_finish,
            kwargs={
                "name": name,
                "custom_greeting": None,
                "skip_opener": True,
                "require_presence": False,
            },
            daemon=True,
        )
        thread.start()

    def _trigger_greeting(self, name: str | None, confidence: float) -> None:
        self._greeting_in_progress = True
        self._reset_presence_state()
        self._pending_cooldown_key = cooldown_key(name)
        self._pause_wake_listener()

        if name:
            logger.info("Recognized %s (confidence %.2f)", name, confidence)
        else:
            logger.info("Unknown face detected; using friend greeting")

        thread = threading.Thread(
            target=self._speak_and_finish,
            kwargs={
                "name": name,
                "custom_greeting": get_person_greeting(name),
                "skip_opener": False,
                "require_presence": True,
            },
            daemon=True,
        )
        thread.start()

    def _set_status(self, text: str) -> None:
        if self._status_label is not None:
            self._status_label.text = text

    def _on_before_speak(self, text: str) -> None:
        Clock.schedule_once(lambda _dt: self._set_status(text), 0)
        if self._animated_face is not None:
            Clock.schedule_once(lambda _dt: self._animated_face.start_talking(), 0)

    def _on_after_speak(self) -> None:
        if self._animated_face is not None:
            Clock.schedule_once(lambda _dt: self._animated_face.stop_talking(), 0)

    def _on_status(self, text: str) -> None:
        Clock.schedule_once(lambda _dt: self._set_status(text), 0)

    def _speak_and_finish(
        self,
        name: str | None,
        custom_greeting: str | None,
        *,
        skip_opener: bool,
        require_presence: bool,
    ) -> None:
        try:
            greeting = run_greeting_interaction(
                name,
                tts_cfg=self.tts_cfg,
                ollama_cfg=self._ollama_cfg,
                conversation_cfg=self._conversation_cfg,
                stt_cfg=self._stt_cfg,
                assistant_cfg=self._assistant_cfg,
                custom_greeting=custom_greeting,
                on_status=self._on_status,
                on_before_speak=self._on_before_speak,
                on_after_speak=self._on_after_speak,
                mic=self._mic,
                skip_opener=skip_opener,
                require_presence=require_presence,
                is_present=self._is_present,
            )
            logger.info("Greeting interaction complete: %s", greeting or "(wake)")
        except Exception:
            logger.exception("Greeting interaction failed")
        finally:
            Clock.schedule_once(self._finish_greeting, 0)

    def _finish_greeting(self, _dt) -> None:
        if self._animated_face is not None:
            self._animated_face.stop_talking()
        if self._pending_cooldown_key is not None:
            self._cooldown.mark_triggered(self._pending_cooldown_key)
            self._pending_cooldown_key = None
        self._greeting_in_progress = False
        self._resume_wake_listener()
