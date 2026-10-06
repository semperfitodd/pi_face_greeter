from __future__ import annotations

import logging
import re
import shutil
import subprocess

logger = logging.getLogger("pi_face_greeter.alsa_devices")

_ALSA_DEVICE_PATTERN = re.compile(r"^(default|plughw:\d+,\d+|hw:\d+,\d+)$")
_CARD_LINE = re.compile(r"^card (\d+):", re.IGNORECASE)
_DEVICE_SUFFIX = re.compile(r"^(?:plughw|hw):(\d+),\d+$")


def normalize_alsa_device(device: str | None) -> str | None:
    if device is None:
        return None
    token = str(device).strip()
    if not token:
        return None
    if not _ALSA_DEVICE_PATTERN.match(token):
        raise ValueError(f"Invalid ALSA device: {device!r}")
    return token


def card_number_from_device(device: str | None) -> int | None:
    if device is None:
        return None
    match = _DEVICE_SUFFIX.match(device.strip())
    if match is None:
        return None
    return int(match.group(1))


def device_for_card(card: int, subdevice: int = 0) -> str:
    return f"plughw:{card},{subdevice}"


def parse_usb_cards(listing: str) -> list[tuple[int, str]]:
    cards: list[tuple[int, str]] = []
    for line in listing.splitlines():
        if "usb" not in line.lower():
            continue
        match = _CARD_LINE.match(line.strip())
        if match is None:
            continue
        cards.append((int(match.group(1)), line.strip()))
    return cards


def parse_usb_playback_device(aplay_listing: str) -> str | None:
    cards = parse_usb_cards(aplay_listing)
    if not cards:
        return None
    return device_for_card(cards[0][0])


def parse_usb_capture_device(arecord_listing: str, *, exclude_card: int | None = None) -> str | None:
    cards = parse_usb_cards(arecord_listing)
    if not cards:
        return None
    if exclude_card is not None and len(cards) > 1:
        for card, _line in cards:
            if card != exclude_card:
                return device_for_card(card)
    return device_for_card(cards[0][0])


def _run_list_command(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        logger.warning("Failed to list ALSA devices: %s", command[0], exc_info=True)
        return None
    return completed.stdout


def detect_usb_playback_device() -> str | None:
    if shutil.which("aplay") is None:
        logger.debug("aplay not found; cannot detect USB playback device")
        return None
    listing = _run_list_command(["aplay", "-l"])
    if listing is None:
        return None
    device = parse_usb_playback_device(listing)
    if device is not None:
        logger.info("Auto-selected USB playback device: %s", device)
    else:
        logger.debug("No USB playback card found in aplay -l output")
    return device


def detect_usb_capture_device(*, exclude_card: int | None = None) -> str | None:
    if shutil.which("arecord") is None:
        logger.debug("arecord not found; cannot detect USB capture device")
        return None
    listing = _run_list_command(["arecord", "-l"])
    if listing is None:
        return None
    device = parse_usb_capture_device(listing, exclude_card=exclude_card)
    if device is not None:
        if exclude_card is not None and card_number_from_device(device) != exclude_card:
            logger.info(
                "Auto-selected USB capture device: %s (playback uses card %s)",
                device,
                exclude_card,
            )
        else:
            logger.info("Auto-selected USB capture device: %s", device)
    else:
        logger.debug("No USB capture card found in arecord -l output")
    return device


def resolve_playback_device(configured: str | None) -> str | None:
    explicit = normalize_alsa_device(configured)
    if explicit is not None:
        return explicit
    return detect_usb_playback_device()


def resolve_capture_device(
    configured: str | None,
    *,
    playback_device: str | None = None,
) -> str | None:
    explicit = normalize_alsa_device(configured)
    if explicit is not None:
        return explicit

    playback_card: int | None = None
    if playback_device is not None:
        playback_card = card_number_from_device(playback_device)
    else:
        playback_card = card_number_from_device(detect_usb_playback_device())

    exclude = playback_card
    listing = _run_list_command(["arecord", "-l"]) if shutil.which("arecord") else None
    if listing is not None:
        capture_cards = parse_usb_cards(listing)
        if len(capture_cards) <= 1:
            exclude = None

    return detect_usb_capture_device(exclude_card=exclude)


def resolve_audio_devices(
    *,
    playback_configured: str | None,
    capture_configured: str | None,
) -> tuple[str | None, str | None]:
    playback = resolve_playback_device(playback_configured)
    capture = resolve_capture_device(capture_configured, playback_device=playback)
    return playback, capture
