from __future__ import annotations

import hmac
import logging

logger = logging.getLogger("pi_face_greeter.settings_auth")


def settings_pin_configured(settings_pin: str | None) -> bool:
    return bool(settings_pin and settings_pin.strip())


def verify_settings_pin(provided: str, configured: str | None) -> bool:
    if not settings_pin_configured(configured):
        return True
    assert configured is not None
    return hmac.compare_digest(provided.strip(), configured.strip())


def warn_if_settings_unlocked(settings_pin: str | None) -> None:
    if not settings_pin_configured(settings_pin):
        logger.warning(
            "ui.settings_pin is not set; settings screen allows face enrollment and deletion without a PIN"
        )
