from __future__ import annotations

import logging
import threading
import time
from typing import Any

from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView

from pi_face_greeter.app.camera_preview import CameraPreview
from pi_face_greeter.app.mic_level_bar import MicLevelBar
from pi_face_greeter.app.camera_source import CameraSource
from pi_face_greeter.app.face_widget import AnimatedFace
from pi_face_greeter.app.transcript_format import (
    TranscriptTurn,
    append_or_update_turn,
    format_transcript_markup,
)
from pi_face_greeter.conversation import DEFAULT_ASSISTANT_NAME
from pi_face_greeter.events import (
    format_face_cooldown,
    format_face_recognized,
    format_face_unknown,
    log_event,
)
from pi_face_greeter.wake_word import WakeWordListener, build_wake_hint
from pi_face_greeter.greet_pipeline import run_greeting_interaction
from pi_face_greeter.identity_vote import PENDING, IdentityVoter
from pi_face_greeter.mic import MicStream
from pi_face_greeter.per_person_cooldown import PerPersonCooldown, cooldown_key
from pi_face_greeter.presence import should_trigger_greeting
from pi_face_greeter.recognition import (
    get_person_cooldown,
    get_person_greeting,
    get_recognizer,
    identify,
)

logger = logging.getLogger("pi_face_greeter.face_screen")

_PREVIEW_WIDTH_RATIO = 0.75


class _SidePanel(BoxLayout):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.08, 0.08, 0.11, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync_bg, size=self._sync_bg)

    def _sync_bg(self, *_args) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size


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
        self._assistant_name = str(assistant_cfg.get("name", DEFAULT_ASSISTANT_NAME) if assistant_cfg else DEFAULT_ASSISTANT_NAME)
        self._wake_cfg = wake_cfg or {}
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
        self._transcript_label: Label | None = None
        self._transcript_scroll: ScrollView | None = None
        self._transcript_turns: list[TranscriptTurn] = []
        self._mic_label: Label | None = None
        self._mic_level_bar: MicLevelBar | None = None
        self._preview_host: AnchorLayout | None = None
        self._side_panel: _SidePanel | None = None
        self._animated_face: AnimatedFace | None = None
        self._tick_event = None
        self._mic_ui_event = None
        self._wake_listener: WakeWordListener | None = None
        self._cooldown_session_logged: str | None = None

        self._build_ui()
        Clock.schedule_once(self._start_presence_watch, 0)
        self._mic_ui_event = Clock.schedule_interval(self._update_mic_panel, 0.1)

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
        if self._mic_ui_event is not None:
            self._mic_ui_event.cancel()
            self._mic_ui_event = None
        if self._wake_listener is not None:
            self._wake_listener.stop()

    def _reset_presence_state(self) -> None:
        self._consecutive_face_frames = 0
        self._identity_voter.reset()
        self._cooldown_session_logged = None

    def _is_present(self) -> bool:
        if self._last_face_seen <= 0:
            return False
        return time.monotonic() - self._last_face_seen < self._presence_grace

    def _build_ui(self) -> None:
        root = BoxLayout(orientation="horizontal", spacing=0, padding=0)

        face = AnimatedFace(
            blink_interval_min=float(self.ui_cfg.get("blink_interval_min", 2.0)),
            blink_interval_max=float(self.ui_cfg.get("blink_interval_max", 6.0)),
            size_hint_x=2 / 3,
        )
        self._animated_face = face
        root.add_widget(face)

        side = _SidePanel(
            orientation="vertical",
            size_hint_x=1 / 3,
            padding=(8, 8, 8, 8),
            spacing=6,
        )
        self._side_panel = side

        preview_host = AnchorLayout(size_hint_y=None, anchor_x="center", anchor_y="top")
        preview = CameraPreview(
            camera_source=self.camera_source,
            size_hint=(None, None),
        )
        preview_host.add_widget(preview)
        self._preview_host = preview_host
        side.bind(width=self._sync_preview_size)
        side.add_widget(preview_host)

        mic_row = BoxLayout(size_hint_y=None, height=22, spacing=6)
        mic_label = Label(
            text="Mic",
            size_hint_x=None,
            width=120,
            halign="left",
            valign="middle",
            color=(0.75, 0.75, 0.75, 1),
        )
        mic_label.bind(size=lambda inst, _val: setattr(inst, "text_size", (inst.width, None)))
        self._mic_label = mic_label
        mic_bar = MicLevelBar(size_hint_x=1, height=14)
        self._mic_level_bar = mic_bar
        mic_row.add_widget(mic_label)
        mic_row.add_widget(mic_bar)
        side.add_widget(mic_row)

        status = Label(
            text="",
            size_hint_y=None,
            height=28,
            color=(0.9, 0.9, 0.9, 1),
            halign="left",
            valign="middle",
        )
        status.bind(size=lambda inst, _val: setattr(inst, "text_size", (inst.width, None)))
        self._status_label = status
        side.add_widget(status)

        scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            do_scroll_y=True,
        )
        transcript = Label(
            text="",
            markup=True,
            size_hint_y=None,
            color=(0.85, 0.85, 0.85, 1),
            halign="left",
            valign="top",
        )
        transcript.bind(
            width=lambda inst, w: setattr(inst, "text_size", (w, None)),
            texture_size=lambda inst, ts: setattr(inst, "height", ts[1]),
        )
        self._transcript_label = transcript
        scroll.add_widget(transcript)
        self._transcript_scroll = scroll
        side.add_widget(scroll)

        hint = Label(
            text="Swipe left for settings",
            size_hint_y=None,
            height=22,
            color=(0.6, 0.6, 0.6, 1),
            halign="center",
        )
        side.add_widget(hint)

        root.add_widget(side)
        self.add_widget(root)
        Clock.schedule_once(lambda _dt: self._sync_preview_size(side), 0)

    def _sync_preview_size(self, *_args) -> None:
        side = self._side_panel
        host = self._preview_host
        if side is None or host is None or side.width <= 0:
            return
        inner = side.width - side.padding[0] - side.padding[2]
        size = max(1, inner * _PREVIEW_WIDTH_RATIO)
        host.height = size
        for child in host.children:
            if isinstance(child, CameraPreview):
                child.size = (size, size)

    def _update_mic_panel(self, _dt) -> None:
        mic = self._mic
        label = self._mic_label
        bar = self._mic_level_bar
        if label is None or bar is None:
            return
        if mic is None:
            label.text = "Mic: off"
            label.color = (0.6, 0.6, 0.6, 1)
            bar.set_level(0.0)
            return
        device = mic.device or "default"
        if mic.is_alive:
            label.text = f"Mic {device}"
            label.color = (0.75, 0.75, 0.75, 1)
            bar.set_level(mic.level)
        else:
            label.text = "Mic: no audio"
            label.color = (1.0, 0.35, 0.35, 1)
            bar.set_level(0.0)

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
            if self._cooldown_session_logged != key:
                log_event(format_face_cooldown(confirmed))
                self._cooldown_session_logged = key
            if self._status_label is not None:
                hint = build_wake_hint(
                    self._wake_cfg,
                    listener_enabled=self._wake_listener is not None
                    and self._wake_listener.enabled,
                )
                self._status_label.text = hint or ""
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
        self._clear_transcript()
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
        self._clear_transcript()
        self._reset_presence_state()
        self._pending_cooldown_key = cooldown_key(name)
        self._pause_wake_listener()

        if name:
            logger.info("Recognized %s (confidence %.2f)", name, confidence)
            log_event(format_face_recognized(name, confidence))
        else:
            logger.info("Unknown face detected; using friend greeting")
            recognizer = get_recognizer()
            miss = recognizer.last_identify_miss if recognizer is not None else None
            log_event(format_face_unknown(miss))

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

    def _on_before_speak(self, _text: str) -> None:
        if self._animated_face is not None:
            Clock.schedule_once(lambda _dt: self._animated_face.start_talking(), 0)

    def _on_transcript(self, speaker: str, text: str, replace_last: bool) -> None:
        append_or_update_turn(
            self._transcript_turns,
            speaker,
            text,
            replace_last=replace_last,
        )
        Clock.schedule_once(lambda _dt: self._refresh_transcript_label(), 0)

    def _refresh_transcript_label(self) -> None:
        if self._transcript_label is None:
            return
        self._transcript_label.text = format_transcript_markup(
            self._transcript_turns,
            self._assistant_name,
        )
        if self._transcript_scroll is not None:
            self._transcript_scroll.scroll_y = 0

    def _clear_transcript(self) -> None:
        self._transcript_turns.clear()
        if self._transcript_label is not None:
            self._transcript_label.text = ""

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
                on_transcript=self._on_transcript,
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
        if self._status_label is not None:
            self._status_label.text = ""
        if self._pending_cooldown_key is not None:
            self._cooldown.mark_triggered(self._pending_cooldown_key)
            self._pending_cooldown_key = None
        self._greeting_in_progress = False
        self._resume_wake_listener()
