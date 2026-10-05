from __future__ import annotations

from pi_face_greeter.cooldown import CooldownGate

UNKNOWN_COOLDOWN_KEY = "__unknown__"


def cooldown_key(name: str | None) -> str:
    if name:
        return name
    return UNKNOWN_COOLDOWN_KEY


class PerPersonCooldown:
    def __init__(self, default_seconds: float) -> None:
        self.default_seconds = default_seconds
        self._durations: dict[str, float] = {}
        self._gates: dict[str, CooldownGate] = {}

    def set_duration(self, key: str, seconds: float) -> None:
        self._durations[key] = seconds
        if key in self._gates:
            self._gates[key].seconds = seconds

    def can_trigger(self, key: str) -> bool:
        return self._gate_for(key).can_trigger()

    def mark_triggered(self, key: str) -> None:
        self._gate_for(key).mark_triggered()

    def seconds_remaining(self, key: str) -> float:
        return self._gate_for(key).seconds_remaining()

    def _gate_for(self, key: str) -> CooldownGate:
        if key not in self._gates:
            seconds = self._durations.get(key, self.default_seconds)
            self._gates[key] = CooldownGate(seconds)
        return self._gates[key]
