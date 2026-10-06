from __future__ import annotations

from pi_face_greeter import alsa_devices

DUAL_USB_APLAY = """
**** List of PLAYBACK Hardware Devices ****
card 0: vc4hdmi0 [vc4-hdmi-0], device 0: MAI PCM vc4-hdmi-0 [MAI PCM vc4-hdmi-0]
card 2: Speaker [USB Audio Device], device 0: USB Audio [USB Audio]
card 3: MicOnly [USB PnP Sound Device], device 0: USB Audio [USB Audio]
"""

DUAL_USB_ARECORD = """
**** List of CAPTURE Hardware Devices ****
card 2: Mic [USB PnP Sound Device], device 0: USB Audio [USB Audio]
card 3: Speaker [USB Audio Device], device 0: USB Audio [USB Audio]
"""


def test_parse_usb_capture_first_usb() -> None:
    assert alsa_devices.parse_usb_capture_device(DUAL_USB_ARECORD) == "plughw:2,0"


def test_parse_usb_playback_first_usb() -> None:
    assert alsa_devices.parse_usb_playback_device(DUAL_USB_APLAY) == "plughw:2,0"


def _patch_arecord_available(monkeypatch) -> None:
    monkeypatch.setattr(
        alsa_devices.shutil,
        "which",
        lambda name: "/usr/bin/arecord" if name == "arecord" else None,
    )
    monkeypatch.setattr(
        alsa_devices,
        "_run_list_command",
        lambda cmd: DUAL_USB_ARECORD if cmd[0] == "arecord" else None,
    )


def test_resolve_capture_uses_first_usb_card(monkeypatch) -> None:
    _patch_arecord_available(monkeypatch)
    assert alsa_devices.resolve_capture_device(None) == "plughw:2,0"


def test_resolve_audio_devices_pairing(monkeypatch) -> None:
    _patch_arecord_available(monkeypatch)
    playback, capture = alsa_devices.resolve_audio_devices(
        playback_configured="plughw:2,0",
        capture_configured=None,
    )
    assert playback == "plughw:2,0"
    assert capture == "plughw:2,0"
