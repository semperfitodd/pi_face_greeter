from __future__ import annotations

from kivy.graphics import Color, Rectangle
from kivy.uix.widget import Widget


class MicLevelBar(Widget):
    """Horizontal bar showing mic input level 0.0–1.0."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._level = 0.0
        self.bind(size=self._redraw, pos=self._redraw)
        self._redraw()

    def set_level(self, level: float) -> None:
        clamped = max(0.0, min(1.0, level))
        if abs(clamped - self._level) < 0.01:
            return
        self._level = clamped
        self._redraw()

    def _redraw(self, *_args) -> None:
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        with self.canvas:
            Color(0.2, 0.2, 0.25, 1)
            Rectangle(pos=self.pos, size=self.size)
            if self._level > 0:
                Color(0.1, 0.85, 0.95, 1)
                Rectangle(
                    pos=self.pos,
                    size=(self.width * self._level, self.height),
                )
