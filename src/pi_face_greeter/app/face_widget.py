from __future__ import annotations

import random

from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
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

    def _draw_capsule(
        self,
        center_x: float,
        center_y: float,
        width: float,
        height: float,
        radius: float,
    ) -> None:
        RoundedRectangle(
            pos=(center_x - width / 2, center_y - height / 2),
            size=(width, height),
            radius=[radius],
        )

    def _redraw(self, *_args) -> None:
        self.canvas.clear()

        if self.width <= 0 or self.height <= 0:
            return

        cx = self.x + self.width / 2
        eye_y = self.y + self.height * 0.62
        mouth_y = self.y + self.height * 0.28

        eye_width = self.width * 0.18
        eye_height = self.height * (0.11 if self._eyes_open else 0.014)
        eye_offset_x = self.width * 0.22
        eye_radius = min(eye_width, eye_height) * 0.45

        mouth_width = self.width * (0.34 if self._mouth_open else 0.38)
        mouth_height = self.height * (0.11 if self._mouth_open else 0.022)
        mouth_radius = min(mouth_width, mouth_height) * 0.45

        with self.canvas:
            Color(0.02, 0.02, 0.05, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[0])

            glow = (0.1, 0.9, 1.0, 0.25)
            solid = (0.1, 0.9, 1.0, 1.0)

            for sign in (-1, 1):
                eye_cx = cx + sign * eye_offset_x
                Color(*glow)
                self._draw_capsule(
                    eye_cx,
                    eye_y,
                    eye_width * 1.08,
                    eye_height * 1.2,
                    eye_radius,
                )
                Color(*solid)
                self._draw_capsule(eye_cx, eye_y, eye_width, eye_height, eye_radius)

            Color(*glow)
            self._draw_capsule(
                cx,
                mouth_y,
                mouth_width * 1.08,
                mouth_height * 1.2,
                mouth_radius,
            )
            Color(*solid)
            self._draw_capsule(cx, mouth_y, mouth_width, mouth_height, mouth_radius)
