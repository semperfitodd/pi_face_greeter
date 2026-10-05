from __future__ import annotations


class IdentityPending:
    """Sentinel returned while identity confirmation is in progress."""


PENDING = IdentityPending()


class IdentityVoter:
    def __init__(self, required: int) -> None:
        self.required = max(1, required)
        self._streak_name: str | None | object = object()
        self._streak_count = 0

    def push(self, name: str | None) -> str | None | IdentityPending:
        if name == self._streak_name:
            self._streak_count += 1
        else:
            self._streak_name = name
            self._streak_count = 1

        if self._streak_count >= self.required:
            return name
        return PENDING

    def reset(self) -> None:
        self._streak_name = object()
        self._streak_count = 0
