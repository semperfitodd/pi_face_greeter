from __future__ import annotations

from pi_face_greeter.app.preview_geometry import (
    kivy_tex_coords,
    map_box_to_widget,
    square_crop_rect,
    texture_tex_coords,
)


def test_square_crop_landscape_frame() -> None:
    crop = square_crop_rect(640, 480)
    assert crop.x0 == 80
    assert crop.y0 == 0
    assert crop.size == 480


def test_texture_tex_coords_landscape() -> None:
    u_left, v_bottom, u_right, v_top = texture_tex_coords(640, 480)
    assert u_left == 0.125
    assert u_right == 0.875
    assert v_bottom == 0.0
    assert v_top == 1.0


def test_kivy_tex_coords_has_eight_values() -> None:
    coords = kivy_tex_coords(640, 480)
    assert len(coords) == 8


def test_map_box_inside_crop() -> None:
    mapped = map_box_to_widget(
        (100, 50, 80, 100),
        frame_width=640,
        frame_height=480,
        widget_width=200.0,
        widget_height=200.0,
    )
    assert mapped is not None
    left, bottom, width, height = mapped
    assert width > 0
    assert height > 0
    assert 0 <= left <= 200
    assert 0 <= bottom <= 200


def test_map_box_outside_crop_returns_none() -> None:
    mapped = map_box_to_widget(
        (0, 0, 40, 40),
        frame_width=640,
        frame_height=480,
        widget_width=200.0,
        widget_height=200.0,
    )
    assert mapped is None
