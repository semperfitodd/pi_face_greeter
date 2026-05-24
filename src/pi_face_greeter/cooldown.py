from __future__ import annotations

import time


class CooldownGate:
    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self._last_trigger: float | None = None

    def can_trigger(self) -> bool:
        if self._last_trigger is None:
            return True
        return (time.monotonic() - self._last_trigger) >= self.seconds

    def mark_triggered(self) -> None:
        self._last_trigger = time.monotonic()

    def seconds_remaining(self) -> float:
        if self._last_trigger is None:
            return 0.0
        elapsed = time.monotonic() - self._last_trigger
        return max(0.0, self.seconds - elapsed)
