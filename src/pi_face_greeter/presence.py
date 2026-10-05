from __future__ import annotations


def should_trigger_greeting(face_frame_count: int, presence_frames_required: int) -> bool:
    return face_frame_count >= presence_frames_required
