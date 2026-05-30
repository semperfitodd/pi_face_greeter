from __future__ import annotations

import random

from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.properties import BooleanProperty, NumericProperty
from kivy.uix.widget import Widget


class AnimatedFace(Widget):
    blink_interval_min = NumericProperty(2.0)
    blink_interval_max = NumericProperty(6.0)
    is_talking = BooleanProperty(False)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._blink_event = None
        self._talk_event = None
        self._mouth_open = False
        self._eyes_open = True
        self.bind(size=self._redraw, pos=self._redraw)
        self.bind(
            blink_interval_min=self._schedule_blink,
            blink_interval_max=self._schedule_blink,
        )
        Clock.schedule_once(lambda _dt: self._schedule_blink(), 0)

    def on_is_talking(self, _instance, value: bool) -> None:
        if value:
            self._start_talking()
        else:
            self._stop_talking()

    def start_talking(self) -> None:
        self.is_talking = True

    def stop_talking(self) -> None:
        self.is_talking = False

    def _schedule_blink(self, *_args) -> None:
        if self._blink_event is not None:
            self._blink_event.cancel()
        delay = random.uniform(self.blink_interval_min, self.blink_interval_max)
        self._blink_event = Clock.schedule_once(self._blink_once, delay)

    def _blink_once(self, _dt) -> None:
        self._eyes_open = False
        self._redraw()
        Clock.schedule_once(self._open_eyes, 0.12)

    def _open_eyes(self, _dt) -> None:
        self._eyes_open = True
        self._redraw()
        self._schedule_blink()

    def _start_talking(self) -> None:
        if self._talk_event is not None:
            return
        self._talk_event = Clock.schedule_interval(self._toggle_mouth, 0.18)

    def _stop_talking(self) -> None:
        if self._talk_event is not None:
            self._talk_event.cancel()
            self._talk_event = None
        self._mouth_open = False
        self._redraw()

    def _toggle_mouth(self, _dt) -> None:
        self._mouth_open = not self._mouth_open
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.clear()

        if self.width <= 0 or self.height <= 0:
            return

        cx = self.x + self.width / 2
        cy = self.y + self.height / 2
        face_radius = min(self.width, self.height) * 0.42

        with self.canvas:
            Color(0.95, 0.82, 0.55, 1)
            Ellipse(
                pos=(cx - face_radius, cy - face_radius),
                size=(face_radius * 2, face_radius * 2),
            )

            eye_y = cy + face_radius * 0.2
            eye_offset_x = face_radius * 0.35
            eye_radius = face_radius * 0.12

            Color(1, 1, 1, 1)
            for sign in (-1, 1):
                Ellipse(
                    pos=(cx + sign * eye_offset_x - eye_radius, eye_y - eye_radius),
                    size=(eye_radius * 2, eye_radius * 2),
                )

            if self._eyes_open:
                pupil_radius = eye_radius * 0.45
                Color(0.1, 0.1, 0.1, 1)
                for sign in (-1, 1):
                    Ellipse(
                        pos=(
                            cx + sign * eye_offset_x - pupil_radius,
                            eye_y - pupil_radius,
                        ),
                        size=(pupil_radius * 2, pupil_radius * 2),
                    )
            else:
                Color(0.1, 0.1, 0.1, 1)
                line_width = max(2, int(face_radius * 0.04))
                for sign in (-1, 1):
                    Line(
                        points=[
                            cx + sign * eye_offset_x - eye_radius,
                            eye_y,
                            cx + sign * eye_offset_x + eye_radius,
                            eye_y,
                        ],
                        width=line_width,
                    )

            mouth_y = cy - face_radius * 0.25
            mouth_width = face_radius * 0.55
            mouth_height = face_radius * (0.18 if self._mouth_open else 0.08)

            Color(0.55, 0.2, 0.2, 1)
            if self._mouth_open:
                Ellipse(
                    pos=(cx - mouth_width / 2, mouth_y - mouth_height / 2),
                    size=(mouth_width, mouth_height),
                )
            else:
                Line(
                    points=[
                        cx - mouth_width / 2,
                        mouth_y,
                        cx + mouth_width / 2,
                        mouth_y,
                    ],
                    width=max(2, int(face_radius * 0.05)),
                )

            Color(0.2, 0.2, 0.2, 0.15)
            Rectangle(
                pos=(self.x, self.y),
                size=(self.width, self.height * 0.08),
            )
