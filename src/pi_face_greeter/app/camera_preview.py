from __future__ import annotations

from kivy.clock import Clock
from kivy.graphics import Color, Line, Rectangle
from kivy.graphics.texture import Texture
from kivy.uix.widget import Widget

from pi_face_greeter.app.camera_source import CameraSource
from pi_face_greeter.app.preview_geometry import kivy_tex_coords, map_box_to_widget


class CameraPreview(Widget):
    def __init__(self, camera_source: CameraSource, **kwargs) -> None:
        super().__init__(**kwargs)
        self.camera_source = camera_source
        self._texture: Texture | None = None
        self._frame_size: tuple[int, int] | None = None
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
        if self._texture is None or self._frame_size != (width, height):
            self._texture = Texture.create(size=(width, height), colorfmt="rgb")
            self._texture.flip_vertical()
            self._frame_size = (width, height)

        self._texture.blit_buffer(frame.tobytes(), colorfmt="rgb", bufferfmt="ubyte")
        self._redraw(snapshot.boxes, width, height)

    def _redraw(self, boxes, frame_width: int, frame_height: int) -> None:
        self.canvas.clear()
        if self._texture is None or self.width <= 0 or self.height <= 0:
            return

        tex_coords = kivy_tex_coords(frame_width, frame_height)

        with self.canvas:
            Color(0.1, 0.1, 0.1, 1)
            Rectangle(pos=self.pos, size=self.size)

            Color(1, 1, 1, 1)
            Rectangle(
                texture=self._texture,
                pos=self.pos,
                size=self.size,
                tex_coords=tex_coords,
            )

            Color(1, 0.85, 0, 1)
            line_width = max(1.5, min(self.width, self.height) * 0.015)
            for box in boxes:
                mapped = map_box_to_widget(
                    box,
                    frame_width=frame_width,
                    frame_height=frame_height,
                    widget_width=self.width,
                    widget_height=self.height,
                )
                if mapped is None:
                    continue
                left, bottom, rect_w, rect_h = mapped
                left += self.x
                bottom += self.y
                Line(
                    rectangle=(left, bottom, rect_w, rect_h),
                    width=line_width,
                )
