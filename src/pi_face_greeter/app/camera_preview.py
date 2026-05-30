from __future__ import annotations

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle
from kivy.graphics.texture import Texture
from kivy.uix.widget import Widget

from pi_face_greeter.app.camera_source import CameraSource


class CameraPreview(Widget):
    def __init__(self, camera_source: CameraSource, **kwargs) -> None:
        super().__init__(**kwargs)
        self.camera_source = camera_source
        self._texture: Texture | None = None
        self._update_event = Clock.schedule_interval(self._update_preview, 1 / 15)

    def on_parent(self, _widget, parent) -> None:
        if parent is None and self._update_event is not None:
            self._update_event.cancel()
            self._update_event = None

    def _update_preview(self, _dt) -> None:
        snapshot = self.camera_source.get_snapshot()
        if snapshot.frame is None:
            return

        frame = snapshot.frame
        height, width = frame.shape[:2]
        if self._texture is None or self._texture.size != (width, height):
            self._texture = Texture.create(size=(width, height), colorfmt="rgb")
            self._texture.flip_vertical()

        self._texture.blit_buffer(frame.tobytes(), colorfmt="rgb", bufferfmt="ubyte")
        self._redraw(snapshot.boxes, width, height)

    def _redraw(self, boxes, frame_width: int, frame_height: int) -> None:
        self.canvas.clear()
        if self._texture is None or self.width <= 0 or self.height <= 0:
            return

        with self.canvas:
            Color(0.1, 0.1, 0.1, 1)
            Rectangle(pos=self.pos, size=self.size)

            Color(1, 1, 1, 1)
            Rectangle(texture=self._texture, pos=self.pos, size=self.size)

            scale_x = self.width / frame_width
            scale_y = self.height / frame_height

            Color(1, 0.85, 0, 1)
            line_width = max(1.5, min(self.width, self.height) * 0.015)
            for x, y, w, h in boxes:
                left = self.x + x * scale_x
                bottom = self.y + (frame_height - y - h) * scale_y
                right = left + w * scale_x
                top = bottom + h * scale_y
                Line(
                    rectangle=(left, bottom, right - left, top - bottom),
                    width=line_width,
                )
