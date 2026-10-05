from __future__ import annotations

from pi_face_greeter.settings_auth import (
    settings_pin_configured,
    verify_settings_pin,
)


def test_verify_settings_pin_open_when_unconfigured() -> None:
    assert verify_settings_pin("anything", None)
    assert verify_settings_pin("", "")


def test_verify_settings_pin_requires_match() -> None:
    assert verify_settings_pin("1234", "1234")
    assert not verify_settings_pin("1235", "1234")


def test_settings_pin_configured() -> None:
    assert not settings_pin_configured(None)
    assert not settings_pin_configured("  ")
    assert settings_pin_configured("1234")
