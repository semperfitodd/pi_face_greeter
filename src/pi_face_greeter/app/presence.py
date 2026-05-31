from __future__ import annotations

from pi_face_greeter.cooldown import CooldownGate


def should_trigger_greeting(
    face_frame_count: int,
    presence_frames_required: int,
    cooldown: CooldownGate,
) -> bool:
    if face_frame_count < presence_frames_required:
        return False
    return cooldown.can_trigger()
