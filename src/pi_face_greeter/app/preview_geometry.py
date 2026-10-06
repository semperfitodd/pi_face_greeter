from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SquareCrop:
    x0: int
    y0: int
    size: int


def square_crop_rect(frame_width: int, frame_height: int) -> SquareCrop:
    size = min(frame_width, frame_height)
    x0 = (frame_width - size) // 2 if frame_width > frame_height else 0
    y0 = (frame_height - size) // 2 if frame_height > frame_width else 0
    return SquareCrop(x0=x0, y0=y0, size=size)


def texture_tex_coords(frame_width: int, frame_height: int) -> tuple[float, float, float, float]:
    """Normalized UV bounds (u_left, v_bottom, u_right, v_top) for center square crop."""
    crop = square_crop_rect(frame_width, frame_height)
    u_left = crop.x0 / frame_width
    u_right = (crop.x0 + crop.size) / frame_width
    v_bottom = crop.y0 / frame_height
    v_top = (crop.y0 + crop.size) / frame_height
    return u_left, v_bottom, u_right, v_top


def kivy_tex_coords(frame_width: int, frame_height: int) -> tuple[float, ...]:
    """Eight UV coordinates for Kivy Rectangle.tex_coords (flipped-V friendly)."""
    u_left, v_bottom, u_right, v_top = texture_tex_coords(frame_width, frame_height)
    return (
        u_left,
        v_top,
        u_right,
        v_top,
        u_right,
        v_bottom,
        u_left,
        v_bottom,
    )


def _intersect_box_with_crop(
    x: int,
    y: int,
    w: int,
    h: int,
    crop: SquareCrop,
) -> tuple[int, int, int, int] | None:
    x1, y1 = x, y
    x2, y2 = x + w, y + h
    cx1, cy1 = crop.x0, crop.y0
    cx2, cy2 = crop.x0 + crop.size, crop.y0 + crop.size
    ix1 = max(x1, cx1)
    iy1 = max(y1, cy1)
    ix2 = min(x2, cx2)
    iy2 = min(y2, cy2)
    if ix2 <= ix1 or iy2 <= iy1:
        return None
    return ix1 - crop.x0, iy1 - crop.y0, ix2 - ix1, iy2 - iy1


def map_box_to_widget(
    box: tuple[int, int, int, int],
    *,
    frame_width: int,
    frame_height: int,
    widget_width: float,
    widget_height: float,
) -> tuple[float, float, float, float] | None:
    """Map a top-left origin box in frame coords to widget-local left, bottom, width, height."""
    crop = square_crop_rect(frame_width, frame_height)
    cropped = _intersect_box_with_crop(*box, crop)
    if cropped is None:
        return None

    x, y, w, h = cropped
    scale = widget_width / crop.size
    left = x * scale
    crop_y_from_bottom = crop.size - y - h
    bottom = crop_y_from_bottom * scale
    return left, bottom, w * scale, h * scale
