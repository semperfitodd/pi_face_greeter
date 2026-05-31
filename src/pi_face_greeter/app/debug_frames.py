from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import numpy as np

from pi_face_greeter.app.detector import FaceBox

logger = logging.getLogger("pi_face_greeter.debug_frames")


def save_debug_frame(
    frame: np.ndarray,
    boxes: tuple[FaceBox, ...],
    output_dir: Path | str,
) -> Path:
    from PIL import Image, ImageDraw

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    image = Image.fromarray(frame)
    draw = ImageDraw.Draw(image)
    line_width = max(2, min(frame.shape[:2]) // 100)
    for x, y, w, h in boxes:
        draw.rectangle(
            [x, y, x + w, y + h],
            outline=(255, 217, 0),
            width=line_width,
        )

    filename = f"frame_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    output_path = directory / filename
    image.save(output_path, format="JPEG")
    logger.debug("Saved debug snapshot to %s", output_path)
    return output_path
